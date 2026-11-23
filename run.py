"""執行一次完整流程；未指定來源時使用離線假設資料。"""
import argparse
from pathlib import Path
from src.pipeline import execute

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['mock', 'csv', 'youtube'], default='mock')
    args = parser.parse_args()
    try:
        result = execute(ROOT, args.source)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'執行失敗：{exc}\n')
    m = result['manifest']
    print(f"完成 {m['id']}：原始 {m['raw_count']}、相關留言 {m['comment_count']}、片段 {m['claim_count']}")
    print('結果：data/results/observatory.sqlite、latest.json、claims.csv、summary.md')
    print('啟動網站：python serve.py')


if __name__ == '__main__':
    main()
