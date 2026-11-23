"""YouTube 前 100 支影片候選清單與留言蒐集（YouTube Data API v3，免費配額）。

流程：每個關鍵詞 search.list（order=viewCount、期間、台灣、繁中）→ videos.list 取觀看數與
付費置入標記 → 期間／食用油關鍵詞／排除詞／語言／品牌官方頻道篩選 → 依觀看數取前 N。
標題或說明含業配字樣者標為「需人工覆核」，不自動刪除；人工決定後填入 research.yaml。
影片與頻道資訊只供報告附件，永不進入公開網站投影。
"""
from collections import Counter
import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .collectors import YouTubeCollector
from .research_common import (read_dotenv, deidentify, excluded, in_window, keyword_hits, language,
                              now_iso, read_json, rfc3339_bounds, taipei_day, write_json)

API = 'https://www.googleapis.com/youtube/v3/'


class Client:
    def __init__(self, key, timeout, budget, opener=None):
        self.key, self.timeout, self.budget = key, timeout, budget
        self.opener = opener or urllib.request.urlopen
        self.units = Counter()

    def get(self, endpoint, cost, **params):
        if endpoint == 'search' and self.units['search'] >= self.budget:
            raise ValueError('已達 max_search_requests 上限；此次不寫入結果。')
        self.units[endpoint] += 1
        url = API + endpoint + '?' + urllib.parse.urlencode({**params, 'key': self.key})
        try:
            with self.opener(urllib.request.Request(url, headers={'User-Agent': 'OilObservatory-research/3.0'}),
                             timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # 不輸出含金鑰的網址。
            raise ValueError(f'YouTube HTTP {exc.code}：請檢查配額與金鑰權限。') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ValueError('YouTube 連線失敗；此次不寫入結果。') from None

    def quota_used(self):
        return self.units['search'] * 100 + self.units['videos']


def _key(spec, environ, root=None):
    env = environ if environ is not None else os.environ
    key = env.get(spec['api_key_env'], '').strip()
    if not key and environ is None and root is not None:
        dotenv = read_dotenv(root)
        key = (dotenv.get(spec['api_key_env'].upper()) or dotenv.get('YT_API_KEY') or '').strip()
    if not key:
        raise ValueError(f'缺少 {spec["api_key_env"]}（環境變數或 .env 的 YT_API_KEY）；請勿把金鑰寫入設定檔。')
    return key


def discover(settings, opener=None, environ=None):
    spec = settings['research']['youtube_discovery']
    client = Client(_key(spec, environ, settings['root']), spec['timeout_seconds'], spec['max_search_requests'], opener)
    after, before = rfc3339_bounds(settings)
    found = {}
    for word in settings['keywords']['oil_types'] + settings['keywords']['terms']:
        token = None
        for _ in range(spec['pages_per_keyword']):
            params = dict(part='snippet', q=word, type='video', order='viewCount', maxResults=50,
                          publishedAfter=after, publishedBefore=before,
                          regionCode=spec['region_code'], relevanceLanguage=spec['relevance_language'])
            if token:
                params['pageToken'] = token
            page = client.get('search', 100, **params)
            for item in page.get('items', []):
                vid = item.get('id', {}).get('videoId')
                if vid:
                    found.setdefault(vid, []).append(word)
            token = page.get('nextPageToken')
            if not token:
                break
    ids = list(found)
    videos = []
    for i in range(0, len(ids), 50):
        page = client.get('videos', 1, part='snippet,statistics,paidProductPlacementDetails',
                          id=','.join(ids[i:i + 50]), maxResults=50)
        videos.extend(page.get('items', []))
    write_json(settings['out'] / 'raw/youtube_search_raw.json', {'acquired_at': now_iso(), 'found': found, 'videos': videos})
    ranked, audit = rank(videos, found, settings)
    manifest = {'source': 'YouTube', 'acquired_at': now_iso(), 'date_from': settings['start'].isoformat(),
                'date_to': settings['end'].isoformat(), 'keywords_source': settings['keywords_source'],
                'keywords': settings['keywords'], 'search_requests': client.units['search'],
                'videos_requests': client.units['videos'], 'quota_units': client.quota_used(),
                'candidates': len(ids), 'audit': dict(audit), 'target': spec['target'],
                'method': 'search.list order=viewCount per keyword, then videos.list viewCount ranking',
                'limitations': ['search.list 每個關鍵詞最多回傳有限頁數，非平台完整母體。',
                                '廣告判定以付費置入標記與業配字樣初篩，需人工覆核。',
                                '品牌官方頻道清單由人工維護（research.yaml excluded_channel_ids）。']}
    write_outputs(settings, manifest, ranked)
    return manifest, ranked


def rank(videos, found, settings):
    spec = settings['research']['youtube_discovery']
    audit, kept = Counter(), []
    blocked = set(spec.get('excluded_channel_ids') or [])
    markers = [m.casefold() for m in spec.get('ad_markers') or []]
    for video in videos:
        audit['candidates'] += 1
        snip, stats = video.get('snippet', {}), video.get('statistics', {})
        text = f"{snip.get('title', '')}\n{snip.get('description', '')}"
        try:
            day = taipei_day(snip['publishedAt'])
        except (KeyError, ValueError):
            audit['bad_date'] += 1
            continue
        if not in_window(day, settings):
            audit['out_of_range'] += 1
            continue
        if snip.get('channelId') in blocked:
            audit['brand_channel'] += 1
            continue
        if (video.get('paidProductPlacementDetails') or {}).get('hasPaidProductPlacement'):
            audit['paid_placement'] += 1
            continue
        hits = keyword_hits(text, settings['keywords'])
        if spec.get('require_keyword_in_title', True) and not keyword_hits(snip.get('title', ''), settings['keywords']):
            audit['no_keyword_in_title'] += 1
            continue
        if spec.get('require_oil_keyword', True) and not hits:
            audit['no_keyword'] += 1
            continue
        if excluded(text, settings['exclude']):
            audit['excluded_phrase'] += 1
            continue
        lang = language(snip.get('title', '') + snip.get('description', ''))
        if lang not in ('zh-Hant', 'zh'):
            audit['not_traditional_chinese'] += 1
            continue
        if 'viewCount' not in stats:
            audit['hidden_views'] += 1
            continue
        flags = [m for m in markers if m in text.casefold()]
        kept.append({'video_id': video['id'], 'title': snip.get('title', ''),
                     'channel_id': snip.get('channelId', ''), 'channel_title': snip.get('channelTitle', ''),
                     'published_day': day.isoformat(), 'view_count': int(stats['viewCount']),
                     'comment_count': int(stats['commentCount']) if 'commentCount' in stats else None,
                     'search_keywords': sorted(set(found.get(video['id'], []))), 'matched_keywords': hits,
                     'ad_review_flags': flags, 'review_status': '需人工覆核' if flags else '待確認'})
    kept.sort(key=lambda v: (-v['view_count'], v['video_id']))
    top = kept[:spec['target']]
    for i, v in enumerate(top, 1):
        v['rank'] = i
    audit['eligible'] = len(kept)
    audit['selected'] = len(top)
    return top, audit


APPENDIX_FIELDS = ['rank', 'video_id', 'title', 'channel_title', 'channel_id', 'published_day', 'view_count',
                   'comment_count', 'matched_keywords', 'ad_review_flags', 'review_status', 'dominant_role',
                   'spread', 'question', 'clarify']


def write_outputs(settings, manifest, ranked):
    out = settings['out']
    write_json(out / 'processed/youtube_top100.json', {'manifest': manifest, 'videos': ranked})
    write_appendix(out / 'reports/youtube_top100_appendix.csv', ranked)


def write_appendix(path, videos, roles=None):
    """報告附件：每支影片留言以散播／疑問／澄清何者為主。不放網站。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    roles = roles or {}
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=APPENDIX_FIELDS, extrasaction='ignore')
        writer.writeheader()
        for v in videos:
            counts = roles.get(v['video_id'], Counter())
            dominant = max(('spread', 'question', 'clarify'), key=lambda r: (counts[r], r == 'question')) if sum(counts.values()) else '尚無已覆核留言'
            label = {'spread': '散播迷思', 'question': '提出疑問', 'clarify': '澄清'}.get(dominant, dominant)
            writer.writerow({**v, 'matched_keywords': '、'.join(v['matched_keywords']),
                             'ad_review_flags': '、'.join(v['ad_review_flags']), 'dominant_role': label,
                             'spread': counts['spread'], 'question': counts['question'], 'clarify': counts['clarify']})


def rerank(settings):
    """用已保存的原始 API 結果重新篩選排名，不消耗配額（調整排除清單或規則後使用）。"""
    raw = read_json(settings['out'] / 'raw/youtube_search_raw.json')
    ranked, audit = rank(raw['videos'], raw['found'], settings)
    manifest = {'source': 'YouTube', 'acquired_at': raw['acquired_at'], 'reranked_at': now_iso(),
                'date_from': settings['start'].isoformat(), 'date_to': settings['end'].isoformat(),
                'keywords_source': settings['keywords_source'], 'keywords': settings['keywords'],
                'candidates': len(raw['videos']), 'audit': dict(audit), 'target': settings['research']['youtube_discovery']['target'],
                'quota_units': 0, 'search_requests': 0, 'videos_requests': 0,
                'limitations': ['搜尋結果由已保存的原始回應重新篩選。']}
    write_outputs(settings, manifest, ranked)
    return manifest, ranked


def collect_comments(settings, opener=None, environ=None):
    """以前 N 支影片清單蒐集留言（含完整回覆）。留言關閉或無法存取的影片記錄後略過。"""
    spec = settings['research']['youtube_discovery']
    listing = read_json(settings['out'] / 'processed/youtube_top100.json')
    comment_spec = settings['research'].get('youtube_comments', {})
    base = {'include_replies': True, 'max_top_level_per_video': comment_spec.get('max_top_level_per_video', 500),
            'max_requests': comment_spec.get('max_requests', 3000), 'timeout_seconds': spec['timeout_seconds']}
    collector = YouTubeCollector({**base, 'video_ids': []}, _key(spec, environ, settings['root']), opener=opener)
    rows, skipped = [], {}
    for video in listing['videos']:
        collector.spec = {**base, 'video_ids': [video['video_id']]}
        try:
            got, _ = collector.collect()
        except ValueError as exc:
            if 'HTTP 403' in str(exc) or 'HTTP 404' in str(exc):
                skipped[video['video_id']] = str(exc)
                continue
            raise
        rows.extend(got)
    records, audit = [], Counter()
    for row in rows:
        audit['read'] += 1
        day = taipei_day(row['published_at'])
        if not in_window(day, settings):
            audit['out_of_range'] += 1
            continue
        if language(row['text']) == 'zh-Hans':
            audit['simplified_chinese'] += 1
            continue
        audit['kept'] += 1
        records.append({'record_id': f"youtube:{row['id']}", 'channel': 'YouTube', 'source_id': row['id'],
                        'video_id': row['video_id'], 'parent_id': row.get('parent_id', ''),
                        'day': day.isoformat(), 'language': language(row['text']),
                        'keywords': keyword_hits(row['text'], settings['keywords']), 'text': deidentify(row['text'])})
    manifest = {'source': 'YouTube comments', 'acquired_at': now_iso(), 'videos': len(listing['videos']),
                'skipped_videos': skipped, 'requests': collector.requests, 'audit': dict(audit),
                'warnings': collector.warnings[-2:],
                'note': '影片內留言不再要求命中關鍵詞；議題歸併由標註決定。作者僅保留雜湊於原始資料，不輸出。'}
    write_json(settings['out'] / 'processed/youtube_comment_candidates.json', {'manifest': manifest, 'records': records})
    return manifest, records
