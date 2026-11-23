from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid
from .configuration import load_config, digest
from .collectors import collect
from .preprocess import preprocess
from .analyzers import analyze
from .storage import save_run, snapshot
from .report import write_json, exports


def execute(root, source='mock'):
    root = Path(root)
    config = load_config(root)
    evidence = json.loads((root / 'data/references/library.json').read_text(encoding='utf-8'))
    ids = [r['id'] for r in evidence]
    if len(ids) != len(set(ids)):
        raise ValueError('文獻 id 重複')
    for ref in evidence:
        for field in ('title', 'url', 'study_type', 'conditions', 'summary', 'limitations', 'review_status'):
            if not ref.get(field):
                raise ValueError(f'文獻 {ref["id"]} 缺少 {field}')
    for case in config['analysis']['cases']:
        if set(case['reference_ids']) - set(ids):
            raise ValueError(f'案例 {case["id"]} 引用不存在的文獻')
    rows, collection = collect(root, source, config)
    comments, audit = preprocess(rows, config)
    scope = digest({'config': config, 'evidence': evidence})
    claims = []
    for row in comments:
        for claim in analyze(row, config):
            claim['fingerprint'] = digest([scope, row, claim])
            claims.append(claim)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    manifest = {
        'id': run_id, 'created_at': datetime.now(timezone.utc).isoformat(), 'source': source,
        'engine_version': '1.0.0', 'config_hash': digest(config), 'evidence_hash': digest(evidence),
        'input_hash': digest(rows), 'config_snapshot': config, 'collection': collection,
        'counts': dict(Counter(x['status'] for x in audit)), 'raw_count': len(rows),
        'comment_count': len(comments), 'claim_count': len(claims),
        'mock_count': sum(c['is_mock'] for c in comments),
        'real_count': sum(not c['is_mock'] for c in comments),
        'warnings': ['規則分類僅為初篩；主張片段保留提問與轉述，不等於已確立的事實陳述。', '文字重複但來源 ID 不同者保留為獨立留言，另以重複文字群組提示；不推論獨立人數。'],
    }
    save_run(root, manifest, comments, claims, evidence)
    write_json(root / 'data/raw' / f'{run_id}.json', {'manifest': manifest, 'records': rows})
    write_json(root / 'data/processed' / f'{run_id}.json', {'audit': audit, 'comments': comments})
    result = snapshot(root)
    exports(root, result)
    return result
