"""期末報告草稿（Q1–Q3）、Top 20 對照表 CSV、YouTube 前 100 附件。

數字一律由 public_content 的同一套已覆核樣本計算，與網站一致。
未經雙方審閱的落差與答案只顯示「待審閱」，不輸出草稿內容。
"""
from collections import Counter, defaultdict
import csv

from .public_content import catalogue, load_editorial
from .research_common import now_iso, read_json
from .youtube_discovery import write_appendix

ROLE_LABELS = {'spread': '散播', 'question': '疑問', 'clarify': '澄清'}


def pct(n, d):
    return f'{100 * n / d:.1f}%' if d else '—'


def build(settings):
    root, out = settings['root'], settings['out']
    loaded = load_editorial(root)
    data = catalogue(root, loaded)
    meta, topics = data['meta'], data['topics']
    records = loaded[2]
    total = meta['sample_count']
    ranked = sorted([t for t in topics if t['rank']], key=lambda t: t['rank'])
    by_sample = sorted(topics, key=lambda t: (-t['spread_count'], -t['sample_count'], t['id']))

    manifests = {}
    for name in ('cofacts_candidates.json', 'youtube_top100.json', 'youtube_comment_candidates.json'):
        path = out / 'processed' / name
        if path.exists():
            manifests[name] = read_json(path)['manifest']
    agreement = read_json(out / 'reports/agreement.json') if (out / 'reports/agreement.json').exists() else None

    lines = [f"# {meta['title']}｜期末報告草稿", '',
             f"產生時間：{now_iso()}　網站資料版本：v{meta['version']}　需求文件：{meta['document_version']}", '',
             '> 本草稿由程式依已覆核樣本自動產生。結論文字、落差與正確說法須經指導老師與公司審閱後定稿。', '',
             '## 資料範圍', '',
             f"- 期間：{meta['date_from']} 至 {meta['date_to']}（台北時間，含起訖日）",
             f"- 渠道：{'、'.join(meta['channels'])}",
             f"- 已覆核真實樣本：{total} 筆；議題標註：{meta['annotation_count']} 筆",
             f"- 排除統計：{meta['excluded_counts'] or '無'}"]
    cof = manifests.get('cofacts_candidates.json')
    if cof:
        lines += [f"- Cofacts 取得：{cof['acquired_at']}，模式 {cof['mode']}，篩選 {cof['audit']}",
                  f"- {cof['attribution']}"]
    yt = manifests.get('youtube_top100.json')
    if yt:
        lines.append(f"- YouTube 候選 {yt['candidates']} 支，符合條件 {yt['audit'].get('eligible', 0)} 支，選取 {yt['audit'].get('selected', 0)} 支；配額 {yt['quota_units']} 單位")
    ytc = manifests.get('youtube_comment_candidates.json')
    if ytc:
        lines.append(f"- YouTube 留言：{ytc['audit']}；無法取得留言的影片 {len(ytc['skipped_videos'])} 支")

    lines += ['', '## Q1 近兩年流傳最廣的食用油迷思與疑問', '']
    if not total:
        lines.append('尚無已覆核真實樣本，無法產生排名。完成標註匯入（research.py annotate-import --install）後重新產生。')
    else:
        lines += ['依各議題散播筆數排序（未審閱議題以「待審閱」標示，不列入正式 Top 20）。', '',
                  '| 排序 | 議題 | 狀態 | 散播 | 疑問 | 澄清 | 樣本 | 占全部樣本 |', '|---|---|---|---|---|---|---|---|']
        for i, t in enumerate([t for t in by_sample if t['sample_count']][:30], 1):
            roles = Counter()
            for c in t['channels']:
                for r in c['roles']:
                    roles[r['key']] += r['count']
            lines.append(f"| {i} | {t['question']} | {t['status']}{'・正式第 %d 名' % t['rank'] if t['rank'] else ''} | "
                         f"{roles['spread']} | {roles['question']} | {roles['clarify']} | {t['sample_count']} | {pct(t['sample_count'], total)} |")
    lines += ['', '## Q2 與官方或學術資料的落差', '']
    reviewed = [t for t in topics if t['status'] == '已審閱']
    if not reviewed:
        lines.append('尚無完成雙方審閱的議題。落差說明與出處於審閱後自動列入。')
    for t in reviewed:
        lines += [f"### {t['question']}", '', f"- 常見說法：{t['common_claim']}", f"- 落差：{t['gap'] or '（疑問題型）'}",
                  f"- 正確說法：{t['answer']}", '- 出處：' + '；'.join(f"{s['title']} {s['url']}" for s in t['sources']), '']
    lines += ['', '## Q3 同一迷思在不同渠道的樣貌與澄清情形', '']
    if not total:
        lines.append('尚無已覆核樣本。')
    else:
        lines += ['| 議題 | 渠道 | 樣本 | 散播 | 疑問 | 澄清 |', '|---|---|---|---|---|---|']
        for t in by_sample:
            for c in t['channels']:
                if c['total']:
                    cells = ' | '.join(f"{r['count']}（{r['percent']}%）" for r in c['roles'])
                    lines.append(f"| {t['question']} | {c['name']} | {c['total']} | {cells} |")
    lines += ['', '## 可信度依據', '']
    if agreement:
        m = agreement['metrics']
        lines += [f"- 雙人標註 {m['double_annotated']} 筆；表態 kappa {m['role_kappa']}、議題 kappa {m['topic_kappa']}、相關性 kappa {m['relevance_kappa']}",
                  f"- 規則預標註對人工定稿正確率 {m['rule_role_vs_final']['accuracy']}（詳見 agreement.md）"]
    else:
        lines.append('- 尚未匯入雙人標註表；一致性指標待產生。')
    lines += ['- 所有數字可由 research.py report 從同一份 observations 重新計算。',
              '', '## 資料限制', '',
              '- 僅涵蓋 Cofacts 回報的 LINE 轉傳訊息與 YouTube 前 100 支影片留言；Facebook 社團、食譜網站、Threads、Dcard、PTT 等未涵蓋。',
              '- Cofacts 反映「有人主動回報查證」的訊息，非 LINE 全體轉傳量；YouTube 留言者偏向特定年齡與觀看習慣，不代表所有會煮飯的人。',
              '- 長輩、新住民及不使用上述平台的族群可能低估。',
              '- YouTube 搜尋結果受平台排序影響，關鍵詞決定候選範圍；以觀看數排序不等於留言量或影響力。',
              '- 語言判定為字元啟發式，可能誤收少量簡體或混用內容。',
              '- 規則預標註僅供人工參考，正式統計只採人工定稿。']
    out_reports = out / 'reports'
    out_reports.mkdir(parents=True, exist_ok=True)
    (out_reports / 'final_report_draft.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    with (out_reports / 'top20_table.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['排名', '議題', '分類', '常見說法', '落差', '正確說法', '出處', '散播筆數', '樣本數', '占全部樣本', '審閱日期'])
        for t in ranked:
            writer.writerow([t['rank'], t['question'], t['category'], t['common_claim'], t['gap'], t['answer'],
                             '；'.join(f"{s['title']} {s['url']}" for s in t['sources']), t['spread_count'],
                             t['sample_count'], pct(t['sample_count'], total), t['reviewed_at']])

    top_path = out / 'processed/youtube_top100.json'
    if top_path.exists():
        roles = defaultdict(Counter)
        for r in records:
            if r.get('video_id'):
                roles[r['video_id']][r['role']] += 1
        write_appendix(out_reports / 'youtube_top100_appendix.csv', read_json(top_path)['videos'], roles)
    return {'report': str(out_reports / 'final_report_draft.md'), 'ranked': len(ranked), 'samples': total}
