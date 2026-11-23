"""本機內容審閱紀錄與撤回。審閱前請完成實際內容及法規核對。"""
import argparse
from datetime import date, datetime, timezone
from pathlib import Path
from src.public_content import read_json, content_hash, approved, valid_source, catalogue
from src.report import write_json

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['review', 'withdraw', 'restore'])
    parser.add_argument('topic_id')
    parser.add_argument('--role', choices=['teacher', 'company'])
    parser.add_argument('--reviewer', required=True)
    parser.add_argument('--note', required=True)
    args = parser.parse_args()
    try:
        path = ROOT / 'data/editorial/topics.json'
        topics = read_json(path)
        topic = next((t for t in topics if t['id'] == args.topic_id), None)
        if topic is None:
            raise ValueError('找不到議題 ID')
        before = content_hash(topic)
        if args.action == 'review':
            if not args.role:
                raise ValueError('審閱必須填入 --role teacher 或 company')
            if topic.get('kind') not in ('迷思', '疑問', '澄清') or not topic.get('answer', '').strip():
                raise ValueError('請先填妥類型與答案')
            if not topic.get('sources') or not all(valid_source(s) for s in topic['sources']):
                raise ValueError('請填妥官方或學術 HTTPS 出處')
            if topic['kind'] == '迷思' and not topic.get('gap', '').strip():
                raise ValueError('迷思須填寫與證據的落差')
            topic.setdefault('approvals', {})[args.role] = {
                'approved': True, 'reviewer': args.reviewer, 'note': args.note,
                'reviewed_at': date.today().isoformat(), 'content_hash': before}
        else:
            topic['withdrawn'] = args.action == 'withdraw'
            if args.action == 'restore':
                topic['approvals'] = {'teacher': None, 'company': None}
        event = {'action': args.action, 'topic_id': topic['id'], 'content_hash': before,
                 'reviewer': args.reviewer, 'note': args.note, 'role': args.role,
                 'timestamp': datetime.now(timezone.utc).isoformat()}
        event_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        write_json(ROOT / 'data/editorial/history' / f'{event_id}.json', event)
        write_json(path, topics)
        write_json(ROOT / 'data/results/public.json', catalogue(ROOT))
        print('內容與審閱紀錄已保存。' + ('目前已完成雙方審閱。' if approved(topic) else '目前等待完整審閱或已撤回。'))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')

if __name__ == '__main__':
    main()
