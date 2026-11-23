import csv
import io
import json
from collections import Counter
from pathlib import Path


def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def claims_csv(snapshot):
    comments = {c['uid']: c for c in snapshot['comments']}
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['主張ID', '原始ID', '來源', '資料類型', '日期', '片段', '疑慮分類', '態度', '自述消費意圖', '年齡標記', '提及長輩', '查核結果', '審核狀態', '引用文獻', '判斷理由'])
    for c in snapshot['claims']:
        row = comments[c['comment_uid']]
        values = [c['id'], row['id'], row['source'], '模擬' if row['is_mock'] else '真實', row['published_at'], c['text'], '／'.join(c['categories']), c['sentiment'], '／'.join(c['intentions']), c['population'], '是' if c['mentions_older'] else '否', c['decision'], c['review_status'], '／'.join(c['reference_ids']), c['rationale']]
        writer.writerow([safe_cell(v) for v in values])
    return '\ufeff' + out.getvalue()


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def exports(root, data):
    base = Path(root) / 'data/results'
    write_json(base / 'latest.json', data)
    (base / 'claims.csv').write_text(claims_csv(data), encoding='utf-8')
    counts = Counter(x['decision'] for x in data['claims'])
    report = '\n'.join([
        '# 油品風向標：執行摘要', '',
        f"執行 ID：{data['manifest']['id']}",
        f"資料來源模式：{data['manifest']['source']}",
        f"相關留言：{len(data['comments'])}；主張片段：{len(data['claims'])}",
        f"查核狀態：{dict(counts)}", '',
        '模擬資料只供流程驗證，不代表市場聲量；待審核結果不作為健康建議。',
        '規則初篩尚未經人工標註集評估，不能宣稱分類準確率。', '',
        '## 蒐集限制', *['- ' + x for x in data['manifest']['collection'].get('warnings', [])],
    ])
    (base / 'summary.md').write_text(report + '\n', encoding='utf-8')
