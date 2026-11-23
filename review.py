"""人工審核介面；網站保持唯讀。所有變更留下審核紀錄。"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from src.analyzers import DECISIONS
from src.configuration import digest
from src.configuration import load_config
from src.storage import connect, snapshot, encode
from src.report import exports, write_json

ROOT = Path(__file__).resolve().parent


def review_claim(root, claim_id, decision, references, reviewer, rationale, corrections=None):
    if decision not in DECISIONS or not reviewer.strip() or not rationale.strip():
        raise ValueError('請提供有效判定、審核人及理由')
    with connect(root) as conn:
        run = conn.execute('SELECT id FROM runs ORDER BY rowid DESC LIMIT 1').fetchone()
        if not run:
            raise ValueError('請先執行 run.py')
        row = conn.execute('SELECT * FROM claims WHERE run_id=? AND id=?', (run['id'], claim_id)).fetchone()
        if not row:
            raise ValueError('找不到最新執行中的主張 ID')
        refs = {r['id']: json.loads(r['payload']) for r in conn.execute('SELECT * FROM evidence WHERE run_id=?', (run['id'],))}
        if any(ref not in refs for ref in references):
            raise ValueError('引用了不存在的文獻')
        if decision in ('支持', '部分支持／有條件成立', '不支持') and not references:
            raise ValueError('此判定至少需要一份已審核文獻')
        if any(refs[r]['review_status'] != '已審核' for r in references):
            raise ValueError('引用文獻尚未審核；請先審核文獻，再重新執行 run.py')
        now = datetime.now(timezone.utc).isoformat()
        review = dict(decision=decision, reference_ids=references, reviewer=reviewer.strip(), rationale=rationale.strip(), reviewed_at=now, review_status='已審核')
        corrections = corrections or {}
        cfg = load_config(root)['analysis']
        if 'categories' in corrections and (not corrections['categories'] or set(corrections['categories']) - set(cfg['categories']) - {'未分類'}):
            raise ValueError('修正分類不在設定標籤內')
        if 'sentiment' in corrections and corrections['sentiment'] not in ('正面', '負面', '中性／未明', '混合／待判讀'):
            raise ValueError('無效的態度標籤')
        if set(corrections) - {'categories', 'sentiment'}:
            raise ValueError('僅接受 categories、sentiment 修正')
        review.update(corrections)
        conn.execute('INSERT INTO reviews (claim_id,fingerprint,created_at,payload) VALUES (?,?,?,?)', (claim_id, row['fingerprint'], now, encode(review)))
        claim = json.loads(row['payload'])
        claim.update(review)
        conn.execute('UPDATE claims SET payload=? WHERE run_id=? AND id=?', (encode(claim), run['id'], claim_id))
    exports(root, snapshot(root))


def review_reference(root, reference_id, reviewer, note):
    path = Path(root) / 'data/references/library.json'
    refs = json.loads(path.read_text(encoding='utf-8'))
    ref = next((r for r in refs if r['id'] == reference_id), None)
    if not ref or not reviewer.strip() or not note.strip():
        raise ValueError('請提供有效文獻 ID、審核人與評讀紀錄')
    before = dict(ref)
    now = datetime.now(timezone.utc).isoformat()
    ref.update(review_status='已審核', reviewer=reviewer.strip(), reviewed_at=now, review_note=note.strip())
    event = dict(before=before, after=ref, timestamp=now)
    # Append-only per-event files preserve reference review history.
    write_json(Path(root) / 'data/references/history' / f'{digest(event)}.json', event)
    write_json(path, refs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('claim')
    c.add_argument('id')
    c.add_argument('--decision', choices=DECISIONS, required=True)
    c.add_argument('--references', nargs='*', default=[])
    c.add_argument('--reviewer', required=True)
    c.add_argument('--rationale', required=True)
    c.add_argument('--categories', nargs='+', help='選填：修正疑慮分類（須為 analysis.yaml 定義的標籤）')
    c.add_argument('--sentiment', choices=['正面', '負面', '中性／未明', '混合／待判讀'])
    r = sub.add_parser('reference')
    r.add_argument('id')
    r.add_argument('--reviewer', required=True)
    r.add_argument('--note', required=True)
    args = p.parse_args()
    try:
        if args.command == 'claim':
            corrections = {key: getattr(args, key) for key in ('categories', 'sentiment') if getattr(args, key) is not None}
            review_claim(ROOT, args.id, args.decision, args.references, args.reviewer, args.rationale, corrections)
            print('主張審核已保存；重新整理網站即可查看。')
        else:
            review_reference(ROOT, args.id, args.reviewer, args.note)
            print('文獻評讀已保存；請重新執行 run.py，讓新的證據版本生效。')
    except (ValueError, OSError) as exc:
        p.exit(1, f'審核失敗：{exc}\n')


if __name__ == '__main__':
    main()
