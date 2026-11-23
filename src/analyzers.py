import re
from .configuration import digest
from .preprocess import contains

DECISIONS = ['支持', '部分支持／有條件成立', '不支持', '證據不足', '不適用於目前情境']


def analyze(row, config):
    spec = config['analysis']
    # 斷句保留原片段；不假裝具備完整語意、指涉或反諷理解能力。
    fragments = [s.strip() for s in re.split(r'(?<=[。！？!?；;])|[\r\n]+', row['normalized_text']) if s.strip()]
    claims = []
    for i, text in enumerate(fragments):
        cases = [c['id'] for c in spec['cases'] if contains(text, c['triggers'])]
        categories = [name for name, terms in spec['categories'].items() if contains(text, terms)] or ['未分類']
        positive, negative = contains(text, spec['positive_terms']), contains(text, spec['negative_terms'])
        negated = contains(text, spec['negation_terms'])
        question = contains(text, spec['question_terms'])
        quoted = contains(text, ['媽媽說', '我媽', '聽說', '有人說', '影片說', '長輩說'])
        sentiment = '混合／待判讀' if negated or positive and negative else '正面' if positive else '負面' if negative else '中性／未明'
        stance = '轉述／待判讀' if quoted else '提問' if question else '反駁線索／待判讀' if negated else '表述／待判讀'
        intentions = [name for name, terms in spec['purchase_rules'].items() if contains(text, terms)]
        if negated and intentions:
            intentions = ['語意需人工確認']
        age_match = re.search(r'(?:我今年|本人今年|本人|我已經|我)(\d{2,3})歲', text)
        age = int(age_match.group(1)) if age_match and 18 <= int(age_match.group(1)) <= 120 else None
        population = '自述中高齡' if age is not None and age >= spec['older_age_threshold'] else '自述未達門檻' if age is not None else '未知'
        mentions_older = contains(text, ['媽媽', '我媽', '爸爸', '長輩', '老人', '中高齡', '父母', '爺爺', '奶奶'])
        conditions = []
        for pattern in (r'\d+(?:\.\d+)?\s*°?\s*[Cc℃度]', r'(?:\d+|[一二三四五六七八九十]+)\s*(?:小時|分鐘|天)', r'反覆(?:加熱|使用)?', r'油煙|食入|吸入'):
            conditions.extend(re.findall(pattern, text))
        candidates = list(dict.fromkeys(r for c in spec['cases'] if c['id'] in cases for r in c['reference_ids']))
        claims.append({
            'id': digest([row['uid'], i, text])[:24], 'comment_uid': row['uid'], 'text': text,
            'cases': cases or ['other'], 'categories': categories, 'sentiment': sentiment,
            'sentiment_target': '／'.join(row['hits']['brands'] + row['hits']['oil_types']) or '油品議題，待確認對象',
            'stance': stance, 'intentions': intentions or ['未明示'], 'age': age, 'population': population,
            'mentions_older': mentions_older, 'age_basis': age_match.group(0) if age is not None else '未有明確本人年齡自述',
            'conditions': conditions, 'candidate_reference_ids': candidates,
            'decision': '待查核', 'review_status': '待審核', 'reference_ids': [],
            'rationale': '主題配對僅提供候選文獻，不代表支持此說法；請核對上下文、暴露條件及研究限制。' if candidates else '目前無對應候選文獻；保留待查核，不能據此認定說法錯誤。',
            'rule_basis': {'positive_terms': [t for t in spec['positive_terms'] if contains(text, [t])], 'negative_terms': [t for t in spec['negative_terms'] if contains(text, [t])], 'negation_detected': negated, 'question_detected': question},
            'limitations': '規則初篩；可能誤讀反諷、引述、指涉與否定。未明示購買行為者不推論；年齡線索限本片段。',
        })
    return claims
