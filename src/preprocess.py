import html
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from .configuration import digest

TAIPEI = timezone(timedelta(hours=8))


def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', html.unescape(text))).strip()


def contains(text, terms):
    low = text.casefold()
    return any(t.casefold() in low for t in terms)


def parse_date(value):
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TAIPEI)
    return dt.astimezone(TAIPEI)


def parse_bool(value):
    if value is True or str(value).casefold() == 'true':
        return True
    if value is False or str(value).casefold() == 'false':
        return False
    raise ValueError('is_mock 必須為 true 或 false')


def preprocess(rows, config):
    retained, audit, seen, fingerprints = [], [], {}, {}
    keywords, sources = config['keywords'], config['sources']
    for index, original in enumerate(rows):
        entry = {'index': index, 'original': original}
        try:
            if not isinstance(original, dict):
                raise ValueError('資料列必須是物件')
            for field in ('id', 'source', 'text', 'published_at'):
                if not isinstance(original.get(field), str) or not original[field].strip():
                    raise ValueError(f'缺少文字欄位 {field}')
            text = normalize(original['text'])
            if not text:
                raise ValueError('文字為空')
            is_mock = parse_bool(original.get('is_mock'))
            dt = parse_date(original['published_at'])
            row = {k: original.get(k, '') for k in ('id', 'source', 'url', 'author_key', 'parent_id', 'video_id')}
            row.update(text=original['text'], normalized_text=text, published_at=dt.isoformat(), day=dt.date().isoformat(), is_mock=is_mock)
            row['uid'] = digest([is_mock, row['source'], row['id']])[:24]
            if row['uid'] in seen:
                if seen[row['uid']] != text:
                    entry.update(status='invalid', reason='相同來源 ID 出現不同文字；需確認更新或 ID 衝突')
                else:
                    entry.update(status='duplicate', reason='相同資料類型、來源及 ID 重複匯入')
                audit.append(entry)
                continue
            seen[row['uid']] = text
            if sources.get('date_from') and row['day'] < sources['date_from'] or sources.get('date_to') and row['day'] > sources['date_to']:
                entry.update(status='out_of_range', reason='不在指定日期範圍內')
                audit.append(entry)
                continue
            hits = {group: [name for name, aliases in keywords[group].items() if contains(text, aliases)] for group in ('oil_types', 'oil_terms', 'brands')}
            if contains(text, keywords.get('exclude_phrases', [])):
                entry.update(status='excluded', reason='命中排除詞')
            elif not any(hits.values()):
                entry.update(status='irrelevant', reason='未命中三類關鍵詞')
            else:
                row['hits'] = hits
                fp = digest([is_mock, text.casefold()])[:16]
                row['repeat_group'] = fp
                fingerprints[fp] = fingerprints.get(fp, 0) + 1
                retained.append(row)
                entry.update(status='retained', uid=row['uid'], reason='命中關鍵詞')
            audit.append(entry)
        except (ValueError, TypeError, KeyError) as exc:
            entry.update(status='invalid', reason=str(exc))
            audit.append(entry)
    for row in retained:
        row['repeat_count'] = fingerprints[row['repeat_group']]
    return retained, audit
