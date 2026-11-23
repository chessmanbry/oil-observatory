import csv
import io
import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from src.configuration import load_config, local_path
from src.collectors import YouTubeCollector, collect
from src.preprocess import preprocess
from src.analyzers import analyze
from src.pipeline import execute
from src.storage import snapshot, connect
from src.report import claims_csv, safe_cell
from review import review_claim, review_reference
from serve import make_handler
ROOT=Path(__file__).resolve().parents[1]
def fixture(id='a',text='植物油高溫加熱有毒嗎？'):
    return dict(id=id,text=text,source='YouTube',is_mock=True,published_at='2026-10-22T16:00:00Z')
class SystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        shutil.copytree(ROOT/'config',self.root/'config')
        for name in ('mock','references','imports'):shutil.copytree(ROOT/'data'/name,self.root/'data'/name)
        self.config=load_config(self.root)
    def tearDown(self):self.tmp.cleanup()
    def test_mock_end_to_end_no_network(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('offline')):result=execute(self.root)
        self.assertEqual((result['manifest']['raw_count'],len(result['comments']),len(result['claims'])),(33,30,36))
        self.assertEqual(result['manifest']['counts']['duplicate'],1)
        self.assertTrue(all(r['is_mock'] for r in result['comments']))
        self.assertTrue(all(c['decision']=='待查核' and c['review_status']=='待審核' for c in result['claims']))
        self.assertTrue((self.root/'data/results/claims.csv').exists())
        self.assertEqual(snapshot(self.root)['manifest']['id'],result['manifest']['id'])
    def test_dedup_only_same_identity(self):
        kept,audit=preprocess([fixture(),fixture(),fixture(id='b')],self.config)
        self.assertEqual(len(kept),2);self.assertEqual(kept[0]['repeat_count'],2)
        self.assertEqual(audit[1]['status'],'duplicate')
    def test_id_collision_audited(self):
        kept,audit=preprocess([fixture(),fixture(text='橄欖油健康')],self.config)
        self.assertEqual(len(kept),1);self.assertEqual(audit[1]['status'],'invalid')
    def test_mock_real_identity_separated(self):
        a=fixture();b=dict(a,is_mock=False)
        kept,_=preprocess([a,b],self.config)
        self.assertEqual(len(kept),2);self.assertNotEqual(kept[0]['uid'],kept[1]['uid'])
    def test_validation_and_exclusions(self):
        rows=[fixture(text='機油高溫故障'),fixture(id='b',text='謝謝分享'),dict(fixture(id='c'),is_mock='yes'),dict(fixture(id='d'),published_at='bad')]
        kept,audit=preprocess(rows,self.config)
        self.assertFalse(kept);self.assertEqual([a['status'] for a in audit],['excluded','irrelevant','invalid','invalid'])
    def test_taipei_dates_inclusive(self):
        self.config['sources'].update(date_from='2026-10-23',date_to='2026-10-23')
        kept,_=preprocess([fixture()],self.config);self.assertEqual(kept[0]['day'],'2026-10-23')
        self.config['sources'].update(date_from='2026-10-22',date_to='2026-10-22')
        kept,_=preprocess([fixture()],self.config);self.assertFalse(kept)
    def test_age_self_report_vs_family(self):
        kept,_=preprocess([fixture(text='我媽65歲，叫我買橄欖油。'),fixture(id='b',text='我今年62歲，想知道橄欖油健康嗎？')],self.config)
        family=analyze(kept[0],self.config)[0];person=analyze(kept[1],self.config)[0]
        self.assertEqual(family['population'],'未知');self.assertTrue(family['mentions_older'])
        self.assertEqual(person['population'],'自述中高齡')
    def test_multiple_claims_no_automatic_verdict(self):
        kept,_=preprocess([fixture(text='植物油高溫有毒；橄欖油最健康。')],self.config)
        claims=analyze(kept[0],self.config);self.assertEqual(len(claims),2)
        self.assertIn('heating',claims[0]['cases']);self.assertIn('comparison',claims[1]['cases'])
        self.assertTrue(all(c['decision']=='待查核' for c in claims))
    def test_negation_uncertain(self):
        kept,_=preprocess([fixture(text='植物油不是一定有毒，不買才怪。')],self.config)
        c=analyze(kept[0],self.config)[0]
        self.assertEqual(c['sentiment'],'混合／待判讀');self.assertEqual(c['intentions'],['語意需人工確認'])
    def test_path_safety(self):
        with self.assertRaises(ValueError):local_path(self.root,'../secret')
    def test_llm_rejected(self):
        p=self.root/'config/analysis.yaml';p.write_text(p.read_text(encoding='utf-8').replace('method: rules','method: llm'),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'僅支援'):load_config(self.root)
    def test_csv_schema(self):
        (self.root/'data/imports/comments.csv').write_text('text\n植物油\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'缺少'):collect(self.root,'csv',self.config)
    def test_csv_real_pipeline(self):
        row=dict(fixture(),is_mock=False)
        with (self.root/'data/imports/comments.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
        r=execute(self.root,'csv');self.assertEqual(r['manifest']['real_count'],1);self.assertEqual(r['manifest']['mock_count'],0)
    def test_csv_formula_escaped(self):
        for value in ('=1+1',' +CMD','-2','@x'):self.assertTrue(safe_cell(value).startswith("'"))
        r=execute(self.root);lines=list(csv.reader(io.StringIO(claims_csv(r).lstrip('\ufeff'))))
        self.assertEqual(len(lines),len(r['claims'])+1);self.assertIn('資料類型',lines[0])
    def test_review_requires_evidence(self):
        cid=execute(self.root)['claims'][0]['id']
        with self.assertRaisesRegex(ValueError,'尚未審核'):review_claim(self.root,cid,'支持',['REF-HEAT-2004'],'審核人','理由')
        with self.assertRaisesRegex(ValueError,'至少需要'):review_claim(self.root,cid,'支持',[],'審核人','理由')
    def test_review_persists_and_invalidates(self):
        cid=execute(self.root)['claims'][0]['id']
        review_claim(self.root,cid,'證據不足',[],'測試審核人','條件不完整',{'categories':['健康風險'],'sentiment':'混合／待判讀'})
        r=execute(self.root);self.assertEqual(r['claims'][0]['review_status'],'已審核');self.assertEqual(r['claims'][0]['categories'],['健康風險'])
        p=self.root/'config/analysis.yaml';p.write_text(p.read_text(encoding='utf-8').replace("version: '1.0.0'","version: '1.0.1'"),encoding='utf-8')
        r=execute(self.root);self.assertEqual(r['claims'][0]['review_status'],'待審核')
        with connect(self.root,readonly=True) as c:self.assertEqual(c.execute('SELECT count(*) FROM reviews').fetchone()[0],1)
    def test_reference_review_then_claim(self):
        execute(self.root);review_reference(self.root,'REF-HEAT-2004','測試審核人','測試評讀')
        cid=execute(self.root)['claims'][0]['id']
        review_claim(self.root,cid,'部分支持／有條件成立',['REF-HEAT-2004'],'測試審核人','測試判定')
        self.assertEqual(snapshot(self.root)['claims'][0]['decision'],'部分支持／有條件成立')
        self.assertEqual(len(list((self.root/'data/references/history').glob('*.json'))),1)
    def test_failed_run_preserves_latest(self):
        old=execute(self.root)
        with self.assertRaises(ValueError):execute(self.root,'youtube')
        self.assertEqual(snapshot(self.root)['manifest']['id'],old['manifest']['id'])
    def test_http_readonly_whitelist(self):
        execute(self.root);shutil.copytree(ROOT/'web',self.root/'web')
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.root, research=True));t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        url='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(url+'/api/snapshot') as r:self.assertEqual(len(json.load(r)['comments']),30)
            with urllib.request.urlopen(url+'/') as r:self.assertIn('油品風向標',r.read().decode())
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url+'/config/sources.yaml')
            self.assertEqual(e.exception.code,404)
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(url+'/api/snapshot',data=b'{}'))
            self.assertEqual(e.exception.code,405)
            with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(url+'/api/health',headers={'Host':'evil.test'}))
            self.assertEqual(e.exception.code,403)
        finally:server.shutdown();server.server_close();t.join()
class YouTubeTests(unittest.TestCase):
    def spec(self):return dict(video_ids=['abcdefghijk'],include_replies=True,max_top_level_per_video=10,max_requests=20,timeout_seconds=1)
    def item(self,id,parent=''):
        s={'textOriginal':'植物油加熱','publishedAt':'2026-10-22T00:00:00Z','authorChannelId':{'value':'channel-private'}}
        if parent:s['parentId']=parent
        return {'id':id,'snippet':s}
    def test_pagination(self):
        def opener(request,timeout):
            u=urllib.parse.urlsplit(request.full_url);q=urllib.parse.parse_qs(u.query)
            if u.path.endswith('commentThreads'):r={'items':[{'snippet':{'topLevelComment':self.item('c1'),'totalReplyCount':2}}]}
            elif 'pageToken' not in q:r={'items':[self.item('r1','c1')],'nextPageToken':'two'}
            else:r={'items':[self.item('r2','c1')]}
            return io.StringIO(json.dumps(r))
        rows,m=YouTubeCollector(self.spec(),'dummy',opener=opener).collect()
        self.assertEqual([r['id'] for r in rows],['c1','r1','r2']);self.assertEqual(m['requests'],3)
        self.assertTrue(all(not r['is_mock'] for r in rows));self.assertNotEqual(rows[0]['author_key'],'channel-private')
    def test_key_redacted(self):
        def opener(request,timeout):raise urllib.error.HTTPError(request.full_url,403,'forbidden',{},None)
        with self.assertRaises(ValueError) as e:YouTubeCollector(self.spec(),'sensitive-key',opener=opener).collect()
        self.assertNotIn('sensitive-key',str(e.exception));self.assertNotIn('googleapis',str(e.exception))
    def test_budget(self):
        spec=self.spec();spec['max_requests']=1
        def opener(request,timeout):return io.StringIO(json.dumps({'items':[{'snippet':{'topLevelComment':self.item('c1'),'totalReplyCount':2}}]}))
        with self.assertRaisesRegex(ValueError,'max_requests'):YouTubeCollector(spec,'dummy',opener=opener).collect()
    def test_retry(self):
        calls=[]
        def opener(request,timeout):
            calls.append(1)
            if len(calls)==1:raise urllib.error.HTTPError(request.full_url,503,'temporary',{},None)
            return io.StringIO('{"items":[]}')
        rows,m=YouTubeCollector(self.spec(),'dummy',opener=opener,sleeper=lambda _:None).collect()
        self.assertFalse(rows);self.assertEqual(m['requests'],2)
if __name__=='__main__':unittest.main()
