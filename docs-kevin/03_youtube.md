# YouTube 前 100 支

1. `set YOUTUBE_API_KEY`（PowerShell：`$env:YOUTUBE_API_KEY='...'`），勿寫入檔案。
2. `python research.py youtube-discover`：每個關鍵詞 search.list（viewCount、期間、TW、zh-Hant，100 配額單位／次）→ videos.list → 篩選 → 前 100。預設最多 60 次搜尋（約 6,000 單位，日配額 10,000）。
3. 人工覆核 `data-kevin/reports/youtube_top100_appendix.csv` 的「需人工覆核」列；品牌官方頻道 ID 填入 `config/research.yaml` 的 `excluded_channel_ids` 後重跑。
4. `python research.py youtube-comments`：蒐集前 100 支留言（含回覆），去識別化輸出。
5. 影片清單只在報告附件，不進網站。
限制：搜尋非完整母體；觀看數排序不等於留言量；留言關閉的影片會記錄略過。
