"""第一階段：離線 mock、人工 CSV、明確指定影片的 YouTube API。"""
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from .configuration import local_path


def load_local(root, kind, config):
    spec = config['sources'][kind]
    if not spec.get('enabled'):
        raise ValueError(f'{kind} 來源未啟用')
    path = local_path(root, spec['path'])
    if kind == 'mock':
        rows = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(rows, list):
            raise ValueError('mock 必須是 JSON 陣列')
        if not all(isinstance(r, dict) and r.get('is_mock') is True for r in rows):
            raise ValueError('mock 每筆必須明確設為 is_mock: true')
    else:
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            required = {'id', 'source', 'text', 'published_at', 'is_mock'}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError('CSV 缺少必要欄位：' + ', '.join(sorted(required)))
            rows = list(reader)
    if not rows:
        raise ValueError('來源沒有資料；請先加入 CSV 紀錄或確認來源設定')
    return rows, {'collector': kind, 'network_used': False, 'warnings': []}


class YouTubeCollector:
    def __init__(self, spec, key, opener=None, sleeper=time.sleep):
        self.spec, self.key = spec, key
        self.opener, self.sleeper = opener or urllib.request.urlopen, sleeper
        self.requests = 0
        self.warnings = []
        self.incomplete = set()

    def request(self, endpoint, **params):
        for attempt in range(3):
            if self.requests >= self.spec['max_requests']:
                raise ValueError('已達 max_requests 上限；請縮小範圍或提高上限後重新蒐集。此次不寫入新結果。')
            self.requests += 1
            url = 'https://www.googleapis.com/youtube/v3/' + endpoint + '?' + urllib.parse.urlencode({**params, 'key': self.key})
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'OilObservatory/1.0'})
                with self.opener(request, timeout=self.spec['timeout_seconds']) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    self.sleeper(2 ** attempt)
                    continue
                # Never surface request URLs or API keys in error messages.
                raise ValueError(f'YouTube HTTP {exc.code}：請檢查配額、影片可見性、留言狀態及金鑰權限。') from None
            except (urllib.error.URLError, TimeoutError, OSError):
                raise ValueError('YouTube 連線失敗；此次不寫入新結果。') from None
        raise ValueError('YouTube 請求失敗')

    @staticmethod
    def row(item, video_id):
        s = item['snippet']
        channel = s.get('authorChannelId', {}).get('value', '')
        return {
            'id': item['id'], 'source': 'YouTube', 'text': s.get('textOriginal', s.get('textDisplay', '')),
            'published_at': s['publishedAt'], 'is_mock': False,
            'url': f'https://www.youtube.com/watch?v={video_id}&lc={urllib.parse.quote(item["id"])}',
            'author_key': hashlib.sha256(channel.encode()).hexdigest()[:20] if channel else '',
            'parent_id': s.get('parentId', ''), 'video_id': video_id,
        }

    def collect(self):
        rows = []
        for video in self.spec['video_ids']:
            token, count = None, 0
            while True:
                params = dict(part='snippet', videoId=video, maxResults=min(100, self.spec['max_top_level_per_video'] - count), order='time', textFormat='plainText')
                if token:
                    params['pageToken'] = token
                page = self.request('commentThreads', **params)
                for thread in page.get('items', []):
                    comment = thread['snippet']['topLevelComment']
                    rows.append(self.row(comment, video))
                    count += 1
                    if thread['snippet'].get('totalReplyCount', 0):
                        if not self.spec.get('include_replies'):
                            self.incomplete.add(video)
                        else:
                            reply_token = None
                            while True:
                                args = dict(part='snippet', parentId=comment['id'], maxResults=100, textFormat='plainText')
                                if reply_token:
                                    args['pageToken'] = reply_token
                                replies = self.request('comments', **args)
                                rows.extend(self.row(x, video) for x in replies.get('items', []))
                                reply_token = replies.get('nextPageToken')
                                if not reply_token:
                                    break
                token = page.get('nextPageToken')
                if count >= self.spec['max_top_level_per_video'] or not token:
                    if token:
                        self.incomplete.add(video)
                    break
        if self.incomplete:
            self.warnings.append('蒐集範圍受筆數上限或回覆設定限制，非完整留言母體：' + ', '.join(sorted(self.incomplete)))
        self.warnings.append('依指定影片與最新排序蒐集；不代表平台全體或消費者母體。日期於取得後篩選，早期留言可能因上限未涵蓋。')
        return rows, {'collector': 'youtube', 'network_used': True, 'requests': self.requests, 'warnings': self.warnings}


def collect(root, kind, config):
    if kind in ('mock', 'csv'):
        return load_local(root, kind, config)
    if kind != 'youtube':
        raise ValueError('來源僅支援 mock、csv、youtube；其他平台請使用 CSV 匯入')
    spec = config['sources']['youtube']
    if not spec.get('enabled') or not spec.get('video_ids'):
        raise ValueError('請先在 sources.yaml 啟用 YouTube 並指定 video_ids')
    if not isinstance(spec['video_ids'], list) or not all(isinstance(v, str) and len(v) == 11 and all(c.isalnum() or c in '_-' for c in v) for v in spec['video_ids']):
        raise ValueError('video_ids 必須為 YouTube 11 碼影片 ID 清單')
    for field in ('max_top_level_per_video', 'max_requests', 'timeout_seconds'):
        if type(spec.get(field)) is not int or spec[field] <= 0:
            raise ValueError(f'youtube.{field} 必須為正整數')
    key = os.environ.get(spec['api_key_env'])
    if not key:
        raise ValueError(f'缺少環境變數 {spec["api_key_env"]}；請勿把金鑰填入設定檔')
    return YouTubeCollector(spec, key).collect()
