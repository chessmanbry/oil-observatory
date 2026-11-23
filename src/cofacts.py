"""Cofacts（LINE 轉傳訊息）資料取得與篩選。

合法途徑只有兩種，皆需使用者本人完成：
1. dump：登入 Hugging Face，同意 Cofacts Data User Agreement，下載
   Cofacts/line-msg-fact-check-tw 的 articles、article_replies（可選 reply_requests）CSV 或 zip，
   放到 research.yaml 的 cofacts.dump_dir。
2. api ：向 Cofacts 工作小組申請 app-id，放入環境變數 COFACTS_APP_ID。
   未設定時拒絕執行；不得借用他人或 Cofacts 官方網站的 app-id。

資料授權 CC BY-SA 4.0，報告與網站須保留出處標示（research.yaml cofacts.attribution）。
"""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile

from .research_common import (deidentify, excluded, in_window, keyword_hits, language,
                              now_iso, taipei_day, write_json)

REPLY_TYPES = ('RUMOR', 'NOT_RUMOR', 'OPINIONATED', 'NOT_ARTICLE')


def _raise_csv_limit():
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


def _open_table(dump_dir, name):
    """Yield dict rows of <name>.csv, either plain or inside a zip in dump_dir."""
    dump_dir = Path(dump_dir)
    plain = dump_dir / f'{name}.csv'
    if plain.exists():
        with plain.open(encoding='utf-8-sig', newline='') as f:
            yield from csv.DictReader(f)
        return
    for archive in sorted(dump_dir.glob('*.zip')):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if Path(member).name == f'{name}.csv':
                    with zf.open(member) as raw:
                        yield from csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))
                    return
    raise FileNotFoundError(name)


def _has_table(dump_dir, name):
    try:
        next(iter(_open_table(dump_dir, name)), None)
        return True
    except FileNotFoundError:
        return False


def filter_articles(rows, settings, reply_types=None, requests=None):
    """Apply the study definition to Cofacts articles. Returns (records, audit Counter)."""
    spec = settings['research']['cofacts']
    reply_types = reply_types or {}
    requests = requests or {}
    audit, records = Counter(), []
    for row in rows:
        audit['read'] += 1
        if row.get('status', 'NORMAL') != 'NORMAL':
            audit['blocked_or_deleted'] += 1
            continue
        if row.get('articleType', 'TEXT') not in spec['article_types']:
            audit['non_text'] += 1
            continue
        text = row.get('text') or ''
        try:
            day = taipei_day(row['createdAt'])
        except (KeyError, ValueError):
            audit['bad_date'] += 1
            continue
        if not in_window(day, settings):
            audit['out_of_range'] += 1
            continue
        hits = keyword_hits(text, settings['keywords'])
        if not hits:
            audit['no_keyword'] += 1
            continue
        if excluded(text, settings['exclude']):
            audit['excluded_phrase'] += 1
            continue
        lang = language(text)
        if lang == 'zh-Hans':
            audit['simplified_chinese'] += 1
            continue
        types = reply_types.get(row['id'], Counter())
        if types and set(types) == {'NOT_ARTICLE'}:
            audit['not_article'] += 1
            continue
        audit['kept'] += 1
        records.append({
            'record_id': f"cofacts:{row['id']}", 'channel': 'Cofacts', 'source_id': row['id'],
            'day': day.isoformat(), 'language': lang, 'keywords': hits,
            # 只保留遮蔽後文字，帳號雜湊（userIdsha256）不進入任何輸出。
            'text': deidentify(text),
            'reply_types': {k: types.get(k, 0) for k in REPLY_TYPES},
            'request_count': requests.get(row['id'], 0) or None,
            'url': f"https://cofacts.tw/article/{row['id']}",
        })
    return records, audit


def from_dump(settings):
    spec = settings['research']['cofacts']
    dump_dir = (settings['root'] / spec['dump_dir']).resolve()
    if not dump_dir.is_dir() or not _has_table(dump_dir, 'articles'):
        raise ValueError(f'找不到 Cofacts articles.csv（或含此檔的 zip）於 {dump_dir}。'
                         '請先登入 Hugging Face 並同意 Cofacts Data User Agreement 後下載。')
    _raise_csv_limit()
    reply_types = defaultdict(Counter)
    if _has_table(dump_dir, 'article_replies'):
        for row in _open_table(dump_dir, 'article_replies'):
            if row.get('status', 'NORMAL') == 'NORMAL' and row.get('replyType'):
                reply_types[row['articleId']][row['replyType']] += 1
    requests = Counter()
    if _has_table(dump_dir, 'reply_requests'):
        for row in _open_table(dump_dir, 'reply_requests'):
            if row.get('status', 'NORMAL') == 'NORMAL':
                requests[row['articleId']] += 1
    records, audit = filter_articles(_open_table(dump_dir, 'articles'), settings, reply_types, requests)
    files = sorted(p.name for p in dump_dir.iterdir() if p.suffix in ('.csv', '.zip'))
    return records, audit, {'mode': 'dump', 'files': files,
                            'file_mtimes': {p.name: int(p.stat().st_mtime) for p in dump_dir.iterdir() if p.suffix in ('.csv', '.zip')}}


LIST_QUERY = '''query($filter: ListArticleFilter, $after: String, $first: Int) {
  ListArticles(filter: $filter, after: $after, first: $first, orderBy: [{createdAt: DESC}]) {
    edges { cursor node { id text createdAt articleType status replyRequestCount
      articleReplies(statuses: [NORMAL]) { replyType } } }
  }
}'''


def from_api(settings, opener=None, sleeper=time.sleep, environ=None):
    """GraphQL 取得。每個關鍵詞以 moreLikeThis 搜尋，再於本機做精確關鍵詞篩選。"""
    spec = settings['research']['cofacts']
    environ = os.environ if environ is None else environ
    app_id = environ.get(spec['app_id_env'], '').strip()
    if not app_id:
        raise ValueError(f'缺少環境變數 {spec["app_id_env"]}。Cofacts API 須使用工作小組核發的 app-id；'
                         '請改用 dump 模式或先申請（cofacts@googlegroups.com）。')
    opener = opener or urllib.request.urlopen
    start, end = settings['start'].isoformat(), settings['end'].isoformat()
    seen, rows, used = set(), [], 0
    for word in settings['keywords']['oil_types'] + settings['keywords']['terms']:
        after = None
        while True:
            if used >= spec['api_max_requests']:
                raise ValueError('已達 api_max_requests 上限，此次不寫入結果；請提高上限或縮小關鍵詞。')
            used += 1
            variables = {'first': spec['api_page_size'], 'after': after,
                         'filter': {'moreLikeThis': {'like': word},
                                    'createdAt': {'GTE': start, 'LTE': end + 'T23:59:59+08:00'}}}
            body = json.dumps({'query': LIST_QUERY, 'variables': variables}).encode()
            request = urllib.request.Request(spec['api_url'], data=body, headers={
                'Content-Type': 'application/json', 'x-app-id': app_id,
                'User-Agent': 'OilObservatory-research/3.0'})
            try:
                with opener(request, timeout=spec['timeout_seconds']) as response:
                    payload = json.load(response)
            except urllib.error.HTTPError as exc:
                raise ValueError(f'Cofacts API HTTP {exc.code}；請確認 app-id 與使用條件。') from None
            except (urllib.error.URLError, TimeoutError, OSError):
                raise ValueError('Cofacts API 連線失敗；此次不寫入結果。') from None
            if payload.get('errors'):
                raise ValueError('Cofacts API 回傳錯誤：' + '; '.join(e.get('message', '') for e in payload['errors'])[:300])
            edges = payload['data']['ListArticles']['edges']
            for edge in edges:
                node = edge['node']
                if node['id'] in seen:
                    continue
                seen.add(node['id'])
                rows.append(node)
            if len(edges) < spec['api_page_size']:
                break
            after = edges[-1]['cursor']
            sleeper(0.5)
    reply_types = {n['id']: Counter(r['replyType'] for r in n.get('articleReplies') or [] if r.get('replyType')) for n in rows}
    requests = {n['id']: n.get('replyRequestCount') or 0 for n in rows}
    records, audit = filter_articles(rows, settings, reply_types, requests)
    return records, audit, {'mode': 'api', 'requests': used}


def run(settings, mode=None, **kwargs):
    spec = settings['research']['cofacts']
    mode = mode or spec['mode']
    if mode == 'dump':
        records, audit, detail = from_dump(settings)
    elif mode == 'api':
        records, audit, detail = from_api(settings, **kwargs)
    else:
        raise ValueError('cofacts.mode 須為 dump 或 api')
    manifest = {
        'source': 'Cofacts', 'acquired_at': now_iso(), **detail,
        'date_from': settings['start'].isoformat(), 'date_to': settings['end'].isoformat(),
        'keywords_source': settings['keywords_source'], 'keywords': settings['keywords'],
        'exclude_phrases': settings['exclude'], 'audit': dict(audit),
        'license': 'CC BY-SA 4.0', 'attribution': spec['attribution'].strip(),
    }
    out = settings['out'] / 'processed'
    write_json(out / 'cofacts_candidates.json', {'manifest': manifest, 'records': records})
    return manifest, records
