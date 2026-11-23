"""v3 研究資料管線命令列。操作說明見 docs-kevin/10_operator_guide.md。

  python research.py cofacts [--mode dump|api]
  python research.py youtube-discover
  python research.py youtube-comments
  python research.py annotate-export --out data-kevin/annotation/sheet.csv [--sample 300]
  python research.py annotate-import data-kevin/annotation/sheet.csv [--install]
  python research.py drafts-check
  python research.py drafts-apply TOPIC_ID --editor 姓名 --confirm
  python research.py report

所有指令可加 --keywords 另一份關鍵詞 YAML（oil_types、terms 清單）以新關鍵詞重跑。
"""
import argparse
import json
import sys
from pathlib import Path

from src import annotation, cofacts, drafts, research_report, youtube_discovery
from src.research_common import load_settings

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--keywords', help='替代關鍵詞 YAML 路徑')
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('cofacts', help='篩選 Cofacts 資料（dump 或 api）')
    c.add_argument('--mode', choices=['dump', 'api'])
    sub.add_parser('youtube-discover', help='建立 YouTube 前 100 支影片清單')
    sub.add_parser('youtube-comments', help='蒐集前 100 支影片留言')
    e = sub.add_parser('annotate-export', help='匯出雙人標註表')
    e.add_argument('--out', default='data-kevin/annotation/sheet.csv')
    e.add_argument('--sample', type=int)
    e.add_argument('--seed', type=int, default=20261119)
    i = sub.add_parser('annotate-import', help='匯入標註表、計算一致性、產生正式樣本')
    i.add_argument('sheet')
    i.add_argument('--install', action='store_true', help='同時寫入 data/editorial/observations.json')
    sub.add_parser('drafts-check', help='檢查答案草稿完整度')
    a = sub.add_parser('drafts-apply', help='把單一議題草稿寫入 topics.json（重置審閱）')
    a.add_argument('topic_id')
    a.add_argument('--editor', default='')
    a.add_argument('--confirm', action='store_true')
    sub.add_parser('report', help='產生期末報告草稿、Top 20 表與 YouTube 附件')
    args = p.parse_args(argv)
    try:
        settings = load_settings(ROOT, args.keywords)
        if args.command == 'cofacts':
            manifest, records = cofacts.run(settings, args.mode)
            print(f"Cofacts 保留 {len(records)} 筆；篩選 {manifest['audit']}")
        elif args.command == 'youtube-discover':
            manifest, videos = youtube_discovery.discover(settings)
            print(f"YouTube 候選 {manifest['candidates']} 支，選取 {len(videos)} 支；配額約 {manifest['quota_units']} 單位")
        elif args.command == 'youtube-comments':
            manifest, records = youtube_discovery.collect_comments(settings)
            print(f"YouTube 留言保留 {len(records)} 筆；略過影片 {len(manifest['skipped_videos'])} 支")
        elif args.command == 'annotate-export':
            n = annotation.export_sheet(settings, ROOT / args.out, args.sample, args.seed)
            print(f'已匯出 {n} 列至 {args.out}（UTF-8，Excel 可直接開啟）')
        elif args.command == 'annotate-import':
            observations, metrics, audit = annotation.import_sheet(settings, ROOT / args.sheet)
            annotation.save_import(settings, observations, metrics, audit, args.install)
            print(f"正式樣本 {len(observations)} 筆；表態 kappa {metrics['role_kappa']}；"
                  + ('已寫入 observations.json' if args.install else '未寫入網站資料（加 --install）'))
        elif args.command == 'drafts-check':
            report = drafts.check(settings)
            for row in report:
                status = '可送審' if row['ready'] else '未就緒：' + '；'.join(row['problems'])
                print(f"{row['topic_id']}：{status}（待查核要點 {row['verify_points']}）")
            print(f"可送審 {sum(r['ready'] for r in report)}／{len(report)}")
        elif args.command == 'drafts-apply':
            event = drafts.apply(settings, args.topic_id, args.confirm, args.editor)
            print('已套用草稿並重置審閱：' + json.dumps(event, ensure_ascii=False))
        elif args.command == 'report':
            result = research_report.build(settings)
            print(f"報告草稿：{result['report']}；樣本 {result['samples']}，正式排名 {result['ranked']}")
    except (ValueError, OSError) as error:
        p.exit(1, f'錯誤：{error}\n')


if __name__ == '__main__':
    main()
