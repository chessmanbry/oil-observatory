"""規則預標註、雙人標註表匯出入、一致性（Cohen's kappa）與正式 observations 產生。

規則只提供建議欄位（suggested_*）。只有人工填寫 final_topic／final_role 且 relevant=是 的列，
才會成為 validated=true 的正式樣本。規則與人工的差異會列入可信度報告。
"""
from collections import Counter
from pathlib import Path
import csv
import random

from .research_common import normalize, read_json, write_json

ROLES = ('spread', 'question', 'clarify')
ROLE_LABELS = {'spread': '散播', 'question': '疑問', 'clarify': '澄清'}
LABEL_ROLES = {**{v: k for k, v in ROLE_LABELS.items()}, **{r: r for r in ROLES}}
SHEET_FIELDS = ['record_id', 'channel', 'day', 'text', 'keywords', 'suggested_topic', 'suggested_role',
                'annotator_a_relevant', 'annotator_a_topic', 'annotator_a_role',
                'annotator_b_relevant', 'annotator_b_topic', 'annotator_b_role',
                'final_relevant', 'final_topic', 'final_role', 'notes']


def suggest_topic(text, topics, min_score=1):
    """依議題 aliases（≥2 字）命中數排序；同分取較長命中詞。"""
    norm = normalize(text)
    best, best_key = '', (0, 0)
    for topic in topics:
        if topic.get('withdrawn'):
            continue
        words = [w for w in topic.get('aliases', []) if isinstance(w, str) and len(w) >= 2]
        hits = [w for w in words if normalize(w) in norm]
        key = (len(hits), max((len(w) for w in hits), default=0))
        if key > best_key:
            best, best_key = topic['id'], key
    return best if best_key[0] >= min_score else ''


def suggest_role(text, rules):
    norm = normalize(text)
    if any(normalize(t) in norm for t in rules['clarify_terms']):
        return 'clarify'
    if any(normalize(t) in norm for t in rules['question_terms']):
        return 'question'
    return 'spread'


def load_candidates(settings):
    records = []
    for name in ('cofacts_candidates.json', 'youtube_comment_candidates.json'):
        path = settings['out'] / 'processed' / name
        if path.exists():
            records.extend(read_json(path)['records'])
    return records


def export_sheet(settings, path, sample=None, seed=20261119):
    topics = read_json(settings['root'] / 'data/editorial/topics.json')
    rules = settings['research']['annotation']
    records = load_candidates(settings)
    if not records:
        raise ValueError('尚無候選資料；請先執行 cofacts 或 youtube-comments。')
    if sample and sample < len(records):
        # 依渠道分層抽樣，避免單一渠道主導可信度評估。
        rng = random.Random(seed)
        by_channel = {}
        for r in records:
            by_channel.setdefault(r['channel'], []).append(r)
        picked = []
        for channel, rows in sorted(by_channel.items()):
            n = max(1, round(sample * len(rows) / len(records)))
            picked.extend(rng.sample(rows, min(n, len(rows))))
        records = picked
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=SHEET_FIELDS)
        writer.writeheader()
        for r in records:
            writer.writerow({'record_id': r['record_id'], 'channel': r['channel'], 'day': r['day'],
                             'text': r['text'], 'keywords': '、'.join(r.get('keywords', [])),
                             'suggested_topic': suggest_topic(r['text'], topics, rules.get('topic_min_score', 1)),
                             'suggested_role': ROLE_LABELS[suggest_role(r['text'], rules)]})
    return len(records)


def cohen_kappa(pairs):
    """pairs: list of (label_a, label_b). Returns None when undefined."""
    pairs = [(a, b) for a, b in pairs if a and b]
    n = len(pairs)
    if not n:
        return None
    observed = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if expected == 1:
        return 1.0 if observed == 1 else None
    return round((observed - expected) / (1 - expected), 3)


def _yes(value):
    return str(value).strip().lower() in ('是', 'y', 'yes', 'true', '1')


def _role(value):
    value = str(value or '').strip()
    if value and value not in LABEL_ROLES:
        raise ValueError(f'未知的表態標籤：{value}（可用 散播／疑問／澄清）')
    return LABEL_ROLES.get(value, '')


def import_sheet(settings, path):
    topics = {t['id'] for t in read_json(settings['root'] / 'data/editorial/topics.json')}
    candidates = {r['record_id']: r for r in load_candidates(settings)}
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    role_pairs, topic_pairs, relevant_pairs, rule_vs_final = [], [], [], []
    observations, audit = [], Counter()
    for row in rows:
        audit['rows'] += 1
        a_rel, b_rel = row.get('annotator_a_relevant', '').strip(), row.get('annotator_b_relevant', '').strip()
        if a_rel and b_rel:
            relevant_pairs.append((_yes(a_rel), _yes(b_rel)))
            if _yes(a_rel) and _yes(b_rel):
                role_pairs.append((_role(row.get('annotator_a_role')), _role(row.get('annotator_b_role'))))
                topic_pairs.append((row.get('annotator_a_topic', '').strip(), row.get('annotator_b_topic', '').strip()))
        final_role, final_topic = _role(row.get('final_role')), row.get('final_topic', '').strip()
        if not row.get('final_relevant', '').strip():
            audit['not_adjudicated'] += 1
            continue
        if not _yes(row['final_relevant']):
            audit['irrelevant'] += 1
            continue
        if not final_role or not final_topic:
            audit['incomplete'] += 1
            continue
        if final_topic not in topics:
            raise ValueError(f'final_topic 不存在於 topics.json：{final_topic}（新議題請先建立）')
        rule_vs_final.append((LABEL_ROLES.get(row.get('suggested_role', ''), ''), final_role))
        source = candidates.get(row['record_id'], {})
        channel, _, source_id = row['record_id'].partition(':')
        obs = {'id': source_id or row['record_id'], 'topic_id': final_topic,
               'channel': row.get('channel') or source.get('channel'), 'day': row.get('day') or source.get('day'),
               'role': final_role, 'is_mock': False, 'validated': True, 'annotation_source': Path(path).name}
        if source.get('video_id'):
            obs['video_id'] = source['video_id']
        observations.append(obs)
        audit['validated'] += 1
    metrics = {
        'double_annotated': len(relevant_pairs),
        'relevance_kappa': cohen_kappa(relevant_pairs),
        'relevance_agreement': _agreement(relevant_pairs),
        'role_kappa': cohen_kappa(role_pairs), 'role_agreement': _agreement(role_pairs),
        'topic_kappa': cohen_kappa(topic_pairs), 'topic_agreement': _agreement(topic_pairs),
        'rule_role_vs_final': per_class(rule_vs_final),
    }
    return observations, metrics, dict(audit)


def _agreement(pairs):
    pairs = [(a, b) for a, b in pairs if a != '' and b != '']
    return round(sum(a == b for a, b in pairs) / len(pairs), 3) if pairs else None


def per_class(pairs):
    """規則建議（預測）對人工定稿（標準）的各類精確率與召回率。"""
    result = {}
    for label in ROLES:
        tp = sum(p == label and g == label for p, g in pairs)
        fp = sum(p == label and g != label for p, g in pairs)
        fn = sum(p != label and g == label for p, g in pairs)
        result[label] = {'precision': round(tp / (tp + fp), 3) if tp + fp else None,
                         'recall': round(tp / (tp + fn), 3) if tp + fn else None, 'support': tp + fn}
    result['accuracy'] = round(sum(p == g for p, g in pairs) / len(pairs), 3) if pairs else None
    return result


def agreement_markdown(metrics, audit):
    fmt = lambda v: '—（樣本不足）' if v is None else v
    lines = ['# 標註可信度報告', '',
             f"雙人標註列數：{metrics['double_annotated']}", '',
             '| 項目 | Cohen\'s kappa | 一致率 |', '|---|---|---|',
             f"| 是否食用油相關 | {fmt(metrics['relevance_kappa'])} | {fmt(metrics['relevance_agreement'])} |",
             f"| 表態（散播／疑問／澄清） | {fmt(metrics['role_kappa'])} | {fmt(metrics['role_agreement'])} |",
             f"| 議題歸併 | {fmt(metrics['topic_kappa'])} | {fmt(metrics['topic_agreement'])} |", '',
             '## 規則預標註對人工定稿', '', '| 表態 | 精確率 | 召回率 | 定稿筆數 |', '|---|---|---|---|']
    for label in ROLES:
        m = metrics['rule_role_vs_final'][label]
        lines.append(f"| {ROLE_LABELS[label]} | {fmt(m['precision'])} | {fmt(m['recall'])} | {m['support']} |")
    lines += ['', f"規則整體正確率：{fmt(metrics['rule_role_vs_final']['accuracy'])}", '',
              '## 匯入統計', '', *[f'- {k}：{v}' for k, v in sorted(audit.items())], '',
              '判讀參考：kappa 0.61–0.80 一般視為高度一致，0.81 以上為幾乎完全一致（Landis & Koch, 1977）。',
              '只有人工定稿列成為正式樣本；規則建議不直接計入統計。']
    return '\n'.join(lines) + '\n'


def save_import(settings, observations, metrics, audit, install=False):
    out = settings['out']
    write_json(out / 'processed/observations.validated.json', observations)
    (out / 'reports').mkdir(parents=True, exist_ok=True)
    (out / 'reports/agreement.md').write_text(agreement_markdown(metrics, audit), encoding='utf-8')
    write_json(out / 'reports/agreement.json', {'metrics': metrics, 'audit': audit})
    if install:
        write_json(settings['root'] / 'data/editorial/observations.json', observations)
