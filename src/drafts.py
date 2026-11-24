"""議題答案草稿接口（data/drafts/topic_drafts.json）。

草稿與公開內容分離：check 只做格式與完整度檢查；apply 需明確 --confirm 才把單一議題的草稿
寫入 data/editorial/topics.json，且一律清空雙方審閱，必須重新審閱才會公開。
此接口預設不連接網站，不會因為草稿存在而改變任何公開頁面。
"""
from datetime import datetime, timezone

from .public_content import KINDS, content_hash, valid_source
from .research_common import read_json, write_json

DRAFT_FIELDS = ('kind', 'gap', 'answer', 'sources', 'qa_aliases', 'representative_summary')


def drafts_path(settings):
    return settings['out'] / 'drafts/topic_drafts.json'


def load_drafts(settings):
    path = drafts_path(settings)
    if not path.exists():
        raise ValueError(f'找不到草稿檔 {path}')
    data = read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get('drafts'), list):
        raise ValueError('草稿檔須為 {"drafts": [...]}')
    return data


def readiness(draft, topic_ids):
    """Return list of blocking problems; empty means ready to submit for review."""
    problems = []
    if draft.get('topic_id') not in topic_ids:
        problems.append('topic_id 不存在')
    if draft.get('kind') not in KINDS - {'待判讀'}:
        problems.append('kind 須為 迷思／疑問／澄清')
    if not str(draft.get('answer', '')).strip():
        problems.append('缺少答案')
    if draft.get('kind') == '迷思' and not str(draft.get('gap', '')).strip():
        problems.append('迷思須填落差')
    sources = draft.get('sources') or []
    if not sources:
        problems.append('缺少出處')
    for s in sources:
        if not valid_source(s):
            problems.append(f"出處未就緒：{s.get('title') or s.get('organization') or '未命名'}（需官方／學術 HTTPS 網址）")
    aliases = draft.get('qa_aliases') or []
    if not all(isinstance(a, str) and len(a.strip()) >= 5 for a in aliases):
        problems.append('qa_aliases 須為至少 5 字的完整問句')
    return problems


def check(settings):
    topics = read_json(settings['root'] / 'data/editorial/topics.json')
    ids = {t['id'] for t in topics}
    report = []
    seen = set()
    for draft in load_drafts(settings)['drafts']:
        tid = draft.get('topic_id')
        problems = readiness(draft, ids)
        if tid in seen:
            problems.append('同一議題有多份草稿')
        seen.add(tid)
        report.append({'topic_id': tid, 'ready': not problems, 'problems': problems,
                       'verify_points': len(draft.get('verify_points') or [])})
    return report


def apply(settings, topic_id, confirm=False, editor=''):
    if not confirm:
        raise ValueError('套用草稿會改寫 topics.json 並重置審閱；請確認後加上 --confirm。')
    if not editor.strip():
        raise ValueError('請以 --editor 填入實際負責人')
    path = settings['root'] / 'data/editorial/topics.json'
    topics = read_json(path)
    topic = next((t for t in topics if t['id'] == topic_id), None)
    draft = next((d for d in load_drafts(settings)['drafts'] if d.get('topic_id') == topic_id), None)
    if topic is None or draft is None:
        raise ValueError('找不到議題或其草稿')
    problems = readiness(draft, {t['id'] for t in topics})
    if problems:
        raise ValueError('草稿尚未就緒：' + '；'.join(problems))
    before = content_hash(topic)
    for field in DRAFT_FIELDS:
        topic[field] = draft.get(field, [] if field in ('sources', 'qa_aliases') else '')
    topic['approvals'] = {'teacher': None, 'company': None}
    event = {'action': 'apply_draft', 'topic_id': topic_id, 'editor': editor, 'before_hash': before,
             'after_hash': content_hash(topic), 'timestamp': datetime.now(timezone.utc).isoformat()}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    write_json(settings['root'] / 'data/editorial/history' / f'{stamp}.json', event)
    write_json(path, topics)
    return event
