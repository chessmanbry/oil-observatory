"""Company-spec public projection and reviewed-answer retrieval.

No raw comments, account identifiers, or video-level details enter this projection.
"""
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import json
import re
import unicodedata
import yaml

ROLES = {'spread': '散播主張', 'question': '提出疑問', 'clarify': '反駁或澄清'}
KINDS = {'迷思', '疑問', '澄清', '待判讀'}
SOCIAL_DOMAINS = ('youtube.com', 'youtu.be', 'facebook.com', 'dcard.tw', 'ptt.cc')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def content_hash(topic):
    """Approvals apply to a specific editorial content version."""
    fields = ('id', 'category', 'question', 'kind', 'common_claim', 'gap', 'answer',
              'sources', 'representative_summary', 'qa_aliases')
    content = {key: topic.get(key) for key in fields}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def valid_source(source):
    if not isinstance(source, dict):
        return False
    url = urlsplit(source.get('url', ''))
    host = (url.hostname or '').lower()
    return (source.get('type') in ('official', 'academic')
            and bool(source.get('title')) and url.scheme == 'https'
            and bool(host) and not url.username and not url.password
            and not any(host == domain or host.endswith('.' + domain) for domain in SOCIAL_DOMAINS))


def approved(topic):
    if topic.get('withdrawn') or topic.get('kind') not in ('迷思', '疑問', '澄清'):
        return False
    if not topic.get('answer', '').strip() or not topic.get('sources'):
        return False
    if topic['kind'] == '迷思' and not topic.get('gap', '').strip():
        return False
    if not all(valid_source(source) for source in topic['sources']):
        return False
    fingerprint = content_hash(topic)
    for role in ('teacher', 'company'):
        review = topic.get('approvals', {}).get(role)
        if not isinstance(review, dict) or review.get('approved') is not True:
            return False
        if not review.get('reviewer', '').strip() or review.get('content_hash') != fingerprint:
            return False
        try:
            date.fromisoformat(review['reviewed_at'])
        except (ValueError, KeyError, TypeError):
            return False
    return True


def load_editorial(root):
    root = Path(root)
    config = yaml.safe_load((root / 'config/company.yaml').read_text(encoding='utf-8'))
    start, end = date.fromisoformat(config['date_from']), date.fromisoformat(config['date_to'])
    if start > end:
        raise ValueError('公司資料範圍的起日晚於迄日')
    topics = read_json(root / 'data/editorial/topics.json')
    if not isinstance(topics, list):
        raise ValueError('topics.json 須為議題陣列')
    seen = set()
    for topic in topics:
        if not isinstance(topic, dict) or not isinstance(topic.get('id'), str) or not topic['id'] or topic['id'] in seen:
            raise ValueError('議題 ID 缺少或重複')
        if topic.get('category') not in config['categories'] or topic.get('kind') not in KINDS:
            raise ValueError('議題分類或類型不在公司設定內')
        if not all(isinstance(topic.get(key), str) and topic[key].strip() for key in ('question', 'common_claim')):
            raise ValueError('議題須有問題與概括說法')
        seen.add(topic['id'])
    observation_path = root / 'data/editorial/observations.json'
    if not observation_path.exists():
        observation_path = root / 'data/editorial/observations.example.json'
    observations = read_json(observation_path)
    if not isinstance(observations, list):
        raise ValueError('observations.json 須為已標註樣本陣列')
    records, identities, excluded = [], {}, Counter()
    for observation in observations:
        if not isinstance(observation, dict):
            excluded['invalid'] += 1
            continue
        if observation.get('is_mock') is not False or observation.get('validated') is not True:
            excluded['mock_or_unvalidated'] += 1
            continue
        try:
            day = date.fromisoformat(observation['day'])
            valid = (observation['topic_id'] in seen and observation['role'] in ROLES
                     and observation['channel'] in config['required_channels']
                     and isinstance(observation['id'], str) and bool(observation['id']))
        except (KeyError, ValueError, TypeError):
            valid = False
        if not valid:
            excluded['invalid'] += 1
            continue
        if not start <= day <= end:
            excluded['out_of_range'] += 1
            continue
        key = (observation['channel'], observation['id'], observation['topic_id'])
        if key in identities:
            if identities[key] != observation['role']:
                raise ValueError('同一樣本議題出現衝突標註，請先完成覆核')
            excluded['duplicate'] += 1
            continue
        identities[key] = observation['role']
        records.append(observation)
    return config, topics, records, dict(excluded)


def catalogue(root, loaded=None):
    config, topics, records, excluded = loaded if loaded is not None else load_editorial(root)
    result = []
    for topic in topics:
        if topic.get('withdrawn'):
            continue
        published = approved(topic)
        samples = [r for r in records if r['topic_id'] == topic['id']]
        channels = []
        counts = Counter(r['role'] for r in samples)
        for channel in config['required_channels']:
            subset = [r for r in samples if r['channel'] == channel]
            roles = Counter(r['role'] for r in subset)
            channels.append({'name': channel, 'total': len(subset), 'roles': [
                {'key': key, 'label': label, 'count': roles[key],
                 'percent': round(100 * roles[key] / len(subset), 1) if subset else None}
                for key, label in ROLES.items()]})
        # Explicit allowlist: the unpublished answer and raw research data stay private.
        public = {key: topic.get(key, '') for key in ('id', 'category', 'question', 'common_claim')}
        public.update(status='已審閱' if published else '待審閱',
                      origin=topic.get('origin', 'research'),
                      kind=topic['kind'] if published else '待判讀',
                      search_terms=topic.get('aliases', []),
                      gap=topic.get('gap', '') if published else '',
                      answer=topic['answer'] if published else '',
                      sources=topic['sources'] if published else [],
                      representative_summary=topic.get('representative_summary', '') if published else '',
                      reviewed_at=max(topic['approvals'][r]['reviewed_at'] for r in ('teacher', 'company')) if published else None,
                      sample_count=len(samples), spread_count=counts['spread'],
                      channels=channels, rank=None)
        result.append(public)
    ranked = sorted([t for t in result if t['status'] == '已審閱' and t['kind'] == '迷思' and t['spread_count'] > 0],
                    key=lambda topic: (-topic['spread_count'], topic['id']))[:config['ranking_limit']]
    for rank, topic in enumerate(ranked, 1):
        topic['rank'] = rank
    unique = {(r['channel'], r['id']) for r in records}
    return {'meta': {
        'title': config['site_title'], 'cooperation': config['cooperation'],
        'document_version': config['document_version'], 'version': '3.0.0',
        'date_from': config['date_from'], 'date_to': config['date_to'],
        'categories': config['categories'], 'channels': config['required_channels'],
        'sample_count': len(unique), 'annotation_count': len(records),
        'reviewed_count': sum(t['status'] == '已審閱' for t in result),
        'ranked_count': len(ranked), 'topic_count': len(result),
        'ranking_basis': config['ranking_basis'], 'youtube_target': config['youtube_target'],
        'ranking_limit': config['ranking_limit'],
        'excluded_counts': excluded,
    }, 'topics': result}


def normalize_question(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    return ''.join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith('P'))


def ask(root, question):
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError('請輸入 1 至 500 字的問題')
    normalized = normalize_question(question)
    loaded = load_editorial(root)
    public = catalogue(root, loaded)
    topics = loaded[1]
    matches = [t for t in topics if approved(t) and normalized in {
        normalize_question(q) for q in [t['question'], *t.get('qa_aliases', [])] if isinstance(q, str) and len(q.strip()) >= 5}]
    if len(matches) == 1:
        topic = next(t for t in public['topics'] if t['id'] == matches[0]['id'])
        return {'status': 'answered', 'topic_id': topic['id'], 'question': topic['question'],
                'answer': topic['answer'], 'sources': topic['sources'], 'reviewed_at': topic['reviewed_at']}
    related = []
    for topic in public['topics']:
        words = topic['search_terms'] + [topic['question']]
        if any(len(word) >= 2 and normalize_question(word) in normalized for word in words):
            related.append({'id': topic['id'], 'question': topic['question'], 'status': topic['status']})
    return {'status': 'not_collected', 'message': '目前沒有收錄這個問題的已審閱答案。',
            'related_topics': related[:4]}
