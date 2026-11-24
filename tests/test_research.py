import csv
import io
import json
import shutil
import tempfile
import unittest
import urllib.error
import zipfile
from datetime import date
from pathlib import Path

from src import annotation, cofacts, drafts, research_report, youtube_discovery
from src.research_common import deidentify, language, load_settings, rfc3339_bounds, taipei_day
from src.storage import connect

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def fake_opener(routes):
    calls = []

    def opener(request, timeout=None):
        url = request.full_url if hasattr(request, 'full_url') else request
        calls.append(url)
        for marker, payload in routes:
            if marker in url:
                return FakeResponse(json.dumps(payload).encode())
        raise urllib.error.HTTPError(url, 404, 'nf', {}, None)
    opener.calls = calls
    return opener


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / 'config', self.root / 'config')
        shutil.copytree(ROOT / 'data/editorial', self.root / 'data/editorial')
        self.settings = load_settings(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    # ---- common
    def test_deidentify_masks_contact_details(self):
        text = '看這個 https://x.com/a 打 0912-345-678 或寄 a.b@c.com @小明哥 LINE ID: abc123'
        masked = deidentify(text)
        for leak in ('x.com', '0912', 'a.b@c.com', '小明哥', 'abc123'):
            self.assertNotIn(leak, masked)

    def test_deidentify_masks_glued_mentions(self):
        for text, leak in (('@t@threecats1219oogle 義美', 'threecats'), ('@張@張思聰-s2t。是的', '張思聰'),
                           ('@C@CH-jn4qw惜它不是', 'CH-jn4qw')):
            self.assertNotIn(leak, deidentify(text))

    def test_language_and_window(self):
        self.assertEqual(language('芥花油發煙點很高嗎'), 'zh-Hant')
        self.assertEqual(language('这个油发烟点高吗'), 'zh-Hans')
        self.assertEqual(taipei_day('2026-01-01T16:30:00Z'), date(2026, 1, 2))
        after, before = rfc3339_bounds(self.settings)
        self.assertEqual(after, '2024-11-22T16:00:00Z')
        self.assertEqual(before, '2026-11-23T16:00:00Z')

    def test_custom_keywords_file(self):
        path = self.root / 'kw.yaml'
        path.write_text('oil_types: [椰子油]\nterms: [中鏈脂肪]\n', encoding='utf-8')
        settings = load_settings(self.root, path)
        self.assertEqual(settings['keywords']['oil_types'], ['椰子油'])
        path.write_text('oil_types: []\nterms: [a]\n', encoding='utf-8')
        path.write_text('oil_types: [1]\nterms: [a]\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            load_settings(self.root, path)

    # ---- cofacts
    def articles(self):
        return [
            {'id': 'a1', 'status': 'NORMAL', 'articleType': 'TEXT', 'createdAt': '2025-03-01T00:00:00Z',
             'text': '芥花油高溫會產生反式脂肪！電話 0912345678 https://spam.example/x'},
            {'id': 'a2', 'status': 'NORMAL', 'articleType': 'TEXT', 'createdAt': '2023-01-01T00:00:00Z', 'text': '芥花油不能吃'},
            {'id': 'a3', 'status': 'NORMAL', 'articleType': 'TEXT', 'createdAt': '2025-03-01T00:00:00Z', 'text': '今天天氣很好'},
            {'id': 'a4', 'status': 'BLOCKED', 'articleType': 'TEXT', 'createdAt': '2025-03-01T00:00:00Z', 'text': '橄欖油'},
            {'id': 'a5', 'status': 'NORMAL', 'articleType': 'IMAGE', 'createdAt': '2025-03-01T00:00:00Z', 'text': '橄欖油'},
            {'id': 'a6', 'status': 'NORMAL', 'articleType': 'TEXT', 'createdAt': '2025-03-01T00:00:00Z', 'text': '汽油價格與橄欖油'},
            {'id': 'a7', 'status': 'NORMAL', 'articleType': 'TEXT', 'createdAt': '2025-03-01T00:00:00Z', 'text': '这个橄欖油发烟点'},
            {'id': 'a8', 'status': 'NORMAL', 'articleType': 'TEXT', 'createdAt': '2025-03-01T00:00:00Z', 'text': '橄欖油其實是謠言嗎'},
        ]

    def test_cofacts_filter_audit(self):
        from collections import Counter
        records, audit = cofacts.filter_articles(self.articles(), self.settings, {'a8': Counter({'NOT_ARTICLE': 1})})
        self.assertEqual([r['source_id'] for r in records], ['a1'])
        self.assertEqual(audit['out_of_range'], 1)
        self.assertEqual(audit['no_keyword'], 1)
        self.assertEqual(audit['blocked_or_deleted'], 1)
        self.assertEqual(audit['non_text'], 1)
        self.assertEqual(audit['excluded_phrase'], 1)
        self.assertEqual(audit['simplified_chinese'], 1)
        self.assertEqual(audit['not_article'], 1)
        self.assertNotIn('0912', records[0]['text'])
        self.assertNotIn('spam.example', records[0]['text'])
        self.assertNotIn('userIdsha256', json.dumps(records))

    def test_cofacts_dump_from_zip_and_manifest(self):
        dump = self.root / 'data/raw/cofacts'
        dump.mkdir(parents=True)
        for name, rows in (('articles', self.articles()), ('article_replies', [
                {'articleId': 'a1', 'replyType': 'RUMOR', 'status': 'NORMAL'},
                {'articleId': 'a1', 'replyType': 'NOT_RUMOR', 'status': 'DELETED'}])):
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=sorted({k for r in rows for k in r}))
            writer.writeheader()
            writer.writerows(rows)
            with zipfile.ZipFile(dump / f'{name}.zip', 'w') as zf:
                zf.writestr(f'{name}.csv', buf.getvalue())
        manifest, records = cofacts.run(self.settings, 'dump')
        self.assertEqual([r['source_id'] for r in records], ['a1', 'a8'])
        self.assertEqual(records[0]['reply_types']['RUMOR'], 1)
        self.assertEqual(records[0]['reply_types']['NOT_RUMOR'], 0)
        self.assertEqual(manifest['license'], 'CC BY-SA 4.0')
        self.assertTrue((self.settings['out'] / 'processed/cofacts_candidates.json').exists())

    def test_cofacts_dump_missing_explains_agreement(self):
        with self.assertRaisesRegex(ValueError, 'Cofacts Data User Agreement'):
            cofacts.run(self.settings, 'dump')

    def test_cofacts_api_requires_own_app_id(self):
        with self.assertRaisesRegex(ValueError, 'app-id'):
            cofacts.from_api(self.settings, environ={})

    def test_cofacts_api_paginates_and_caps(self):
        node = lambda i: {'cursor': f'c{i}', 'node': {'id': f'n{i}', 'text': '芥花油可以炸嗎', 'createdAt': '2025-05-01T00:00:00Z',
                                                      'articleType': 'TEXT', 'status': 'NORMAL', 'replyRequestCount': 2,
                                                      'articleReplies': [{'replyType': 'NOT_RUMOR'}]}}
        settings = load_settings(self.root)
        settings['research']['cofacts'].update(api_page_size=1, api_max_requests=2)
        opener = fake_opener([('graphql', {'data': {'ListArticles': {'edges': [node(1)]}}})])
        with self.assertRaisesRegex(ValueError, 'api_max_requests'):
            cofacts.from_api(settings, opener=opener, sleeper=lambda s: None, environ={'COFACTS_APP_ID': 'APP'})
        settings['research']['cofacts'].update(api_page_size=50, api_max_requests=100)
        records, audit, detail = cofacts.from_api(settings, opener=opener, sleeper=lambda s: None, environ={'COFACTS_APP_ID': 'APP'})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['request_count'], 2)

    # ---- youtube
    def video(self, vid, title, views, day='2025-05-01T00:00:00Z', channel='UC1', desc='', paid=False):
        item = {'id': vid, 'snippet': {'title': title, 'description': desc, 'channelId': channel, 'channelTitle': 'ch',
                                        'publishedAt': day}, 'statistics': {'viewCount': str(views), 'commentCount': '5'}}
        if paid:
            item['paidProductPlacementDetails'] = {'hasPaidProductPlacement': True}
        return item

    def test_youtube_rank_exclusions_and_order(self):
        s = load_settings(self.root)
        s['research']['youtube_discovery'].update(excluded_channel_ids=['UCBRAND'], target=2)
        videos = [self.video('v1', '芥花油可以炸嗎', 100), self.video('v2', '橄欖油煎炒', 300),
                  self.video('v3', '芥花油官方', 999, channel='UCBRAND'), self.video('v4', '橄欖油 業配', 500, desc='合作 業配'),
                  self.video('v5', '汽油橄欖油', 50), self.video('v6', '天氣', 60), self.video('v7', '橄欖油', 70, day='2020-01-01T00:00:00Z'),
                  self.video('v8', '橄欖油置入', 800, paid=True)]
        top, audit = youtube_discovery.rank(videos, {}, s)
        self.assertEqual([v['video_id'] for v in top], ['v4', 'v2'])
        self.assertEqual(top[0]['rank'], 1)
        self.assertEqual(top[0]['review_status'], '需人工覆核')
        for key, expected in (('brand_channel', 1), ('paid_placement', 1), ('excluded_phrase', 1), ('no_keyword_in_title', 1), ('out_of_range', 1)):
            self.assertEqual(audit[key], expected, key)
        self.assertEqual(audit['eligible'], 3)

    def test_youtube_discover_requires_key_and_hides_it_in_errors(self):
        with self.assertRaisesRegex(ValueError, 'YOUTUBE_API_KEY'):
            youtube_discovery.discover(self.settings, environ={})
        def boom(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 403, 'quota', {}, None)
        with self.assertRaises(ValueError) as ctx:
            youtube_discovery.discover(self.settings, opener=boom, environ={'YOUTUBE_API_KEY': 'SECRETKEY'})
        self.assertNotIn('SECRETKEY', str(ctx.exception))

    def test_youtube_discover_end_to_end_with_fake_api(self):
        s = load_settings(self.root)
        s['research']['youtube_discovery'].update(pages_per_keyword=1, target=2)
        search = {'items': [{'id': {'videoId': 'v1'}}, {'id': {'videoId': 'v2'}}, {'id': {'videoId': 'v3'}}]}
        videos = {'items': [self.video('v1', '芥花油', 10), self.video('v2', '橄欖油', 30), self.video('v3', '豬油', 20)]}
        opener = fake_opener([('/search', search), ('/videos', videos)])
        manifest, top = youtube_discovery.discover(s, opener=opener, environ={'YOUTUBE_API_KEY': 'K'})
        self.assertEqual([v['video_id'] for v in top], ['v2', 'v3'])
        self.assertTrue((s['out'] / 'reports/youtube_top100_appendix.csv').exists())
        self.assertEqual(manifest['quota_units'], manifest['search_requests'] * 100 + manifest['videos_requests'])
        # published window is sent to the API in UTC
        self.assertTrue(any('publishedAfter=2024-11-22T16%3A00%3A00Z' in u for u in opener.calls))
        header = (s['out'] / 'reports/youtube_top100_appendix.csv').read_text(encoding='utf-8-sig').splitlines()[0]
        self.assertIn('dominant_role', header)

    # ---- annotation
    def test_kappa(self):
        self.assertEqual(annotation.cohen_kappa([('a', 'a'), ('b', 'b'), ('a', 'a'), ('b', 'b')]), 1.0)
        self.assertEqual(annotation.cohen_kappa([('a', 'b'), ('b', 'a')]), -1.0)
        self.assertIsNone(annotation.cohen_kappa([]))
        self.assertAlmostEqual(annotation.cohen_kappa([('a', 'a')] * 20 + [('a', 'b')] * 5 + [('b', 'a')] * 5 + [('b', 'b')] * 20), 0.6, places=2)

    def test_suggest_and_roles(self):
        topics = json.loads((self.root / 'data/editorial/topics.json').read_text(encoding='utf-8'))
        self.assertEqual(annotation.suggest_topic('橄欖油可以用來煎炒嗎', topics), 'olive-heat')
        self.assertEqual(annotation.suggest_topic('今天天氣', topics), '')
        rules = self.settings['research']['annotation']
        self.assertEqual(annotation.suggest_role('這是謠言，其實不會', rules), 'clarify')
        self.assertEqual(annotation.suggest_role('芥花油可以炸嗎？', rules), 'question')
        self.assertEqual(annotation.suggest_role('芥花油有毒', rules), 'spread')

    def seed_candidates(self):
        cofacts_path = self.settings['out'] / 'processed'
        cofacts_path.mkdir(parents=True)
        records = [{'record_id': f'cofacts:{i}', 'channel': 'Cofacts', 'source_id': str(i), 'day': '2025-05-01',
                    'text': '橄欖油可以用來煎炒嗎', 'keywords': ['橄欖油']} for i in range(1, 6)]
        (cofacts_path / 'cofacts_candidates.json').write_text(json.dumps({'manifest': {}, 'records': records}), encoding='utf-8')

    def test_sheet_roundtrip_builds_validated_observations(self):
        self.seed_candidates()
        sheet = self.root / 'sheet.csv'
        self.assertEqual(annotation.export_sheet(self.settings, sheet), 5)
        with sheet.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]['suggested_topic'], 'olive-heat')
        for i, row in enumerate(rows):
            row.update(annotator_a_relevant='是', annotator_b_relevant='是', annotator_a_role='疑問', annotator_b_role='疑問',
                       annotator_a_topic='olive-heat', annotator_b_topic='olive-heat',
                       final_relevant='否' if i == 4 else '是', final_topic='olive-heat', final_role='疑問')
        with sheet.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=annotation.SHEET_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        observations, metrics, audit = annotation.import_sheet(self.settings, sheet)
        self.assertEqual(len(observations), 4)
        self.assertTrue(all(o['validated'] is True and o['is_mock'] is False for o in observations))
        self.assertEqual(metrics['role_kappa'], 1.0)
        self.assertEqual(audit['irrelevant'], 1)
        annotation.save_import(self.settings, observations, metrics, audit, install=True)
        from src.public_content import catalogue
        result = catalogue(self.root)
        self.assertEqual(result['meta']['sample_count'], 4)
        self.assertEqual(result['meta']['ranked_count'], 0)  # 未審閱，不進正式排名
        self.assertTrue((self.settings['out'] / 'reports/agreement.md').exists())

    def test_import_rejects_unknown_topic_and_role(self):
        self.seed_candidates()
        sheet = self.root / 'sheet.csv'
        annotation.export_sheet(self.settings, sheet)
        text = sheet.read_text(encoding='utf-8-sig').splitlines()
        header = text[0].split(',')
        for bad in ({'final_relevant': '是', 'final_topic': 'nope', 'final_role': '疑問'},):
            with sheet.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=annotation.SHEET_FIELDS)
                writer.writeheader()
                writer.writerow({'record_id': 'cofacts:1', **bad})
            with self.assertRaisesRegex(ValueError, 'topics.json'):
                annotation.import_sheet(self.settings, sheet)
        with sheet.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=annotation.SHEET_FIELDS)
            writer.writeheader()
            writer.writerow({'record_id': 'cofacts:1', 'annotator_a_relevant': '是', 'annotator_b_relevant': '是', 'annotator_a_role': '亂寫'})
        with self.assertRaisesRegex(ValueError, '表態'):
            annotation.import_sheet(self.settings, sheet)

    # ---- drafts
    def write_drafts(self, **override):
        draft = {'topic_id': 'olive-heat', 'kind': '迷思', 'gap': '待查', 'answer': '草稿答案',
                 'sources': [{'title': 't', 'url': 'https://www.fda.gov.tw/', 'type': 'official'}],
                 'qa_aliases': ['橄欖油可以用來煎炒嗎'], 'verify_points': ['x']}
        draft.update(override)
        path = self.settings['out'] / 'drafts/topic_drafts.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'drafts': [draft]}, ensure_ascii=False), encoding='utf-8')

    def test_drafts_never_reach_public_without_review(self):
        self.write_drafts()
        self.assertTrue(drafts.check(self.settings)[0]['ready'])
        from src.public_content import catalogue
        self.assertNotIn('草稿答案', json.dumps(catalogue(self.root), ensure_ascii=False))
        with self.assertRaisesRegex(ValueError, '--confirm'):
            drafts.apply(self.settings, 'olive-heat', confirm=False, editor='e')
        drafts.apply(self.settings, 'olive-heat', confirm=True, editor='編輯')
        topics = json.loads((self.root / 'data/editorial/topics.json').read_text(encoding='utf-8'))
        topic = next(t for t in topics if t['id'] == 'olive-heat')
        self.assertEqual(topic['answer'], '草稿答案')
        self.assertEqual(topic['approvals'], {'teacher': None, 'company': None})
        public = catalogue(self.root)
        self.assertEqual(public['meta']['reviewed_count'], 0)
        self.assertNotIn('草稿答案', json.dumps(public, ensure_ascii=False))

    def test_drafts_with_placeholder_sources_not_ready(self):
        self.write_drafts(sources=[{'title': 'YouTube', 'url': 'https://www.youtube.com/watch?v=1', 'type': 'official'}])
        self.assertFalse(drafts.check(self.settings)[0]['ready'])
        self.write_drafts(sources=[{'title': '待補', 'url': '', 'type': 'official'}])
        with self.assertRaisesRegex(ValueError, '未就緒'):
            drafts.apply(self.settings, 'olive-heat', confirm=True, editor='e')

    # ---- report
    def test_report_without_data_states_empty(self):
        result = research_report.build(self.settings)
        text = Path(result['report']).read_text(encoding='utf-8')
        self.assertEqual(result['samples'], 0)
        self.assertIn('尚無已覆核真實樣本', text)
        self.assertIn('資料限制', text)
        self.assertNotIn('第 1 名', text)

    def test_sqlite_connections_released(self):
        (self.root / 'data/results').mkdir(parents=True)
        with connect(self.root) as conn:
            conn.execute('SELECT 1')
        (self.root / 'data/results/observatory.sqlite').unlink()


if __name__ == '__main__':
    unittest.main()
