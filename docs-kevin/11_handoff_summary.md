# 修改摘要與交接（2026-11-24）

分支 `v3-iteration`，自 `origin/main`（v2.0.0）起共 4 個本地 commit。範圍：研究資料收集、整理與接口，不含人工覆核與答案撰寫。

## 一、改了什麼

| commit | 內容 |
|---|---|
| `bda88d4` v3 研究管線 | 新增 `research.py` 與 `src/` 下 Cofacts、YouTube、標註、草稿、報告模組；`docs-kevin/` 規格；`data-kevin/` 草稿區；修 Windows 問題（SQLite 連線未關閉、cp950 編碼）；網站版本改 3.0.0；測試共 50 項 |
| `a9e959f` YouTube 篩選修正 | 讀 `.env` 金鑰；英文關鍵詞改詞界比對（`BaP` 不再誤中 `bap`）；加標題與語言篩選；API 原始結果存檔，`youtube-rerank` 不耗配額 |
| `308bc11` 中立化 | 公開頁移除單位名稱（改「產學合作專題」）；改寫 `AGENTS.md`、`README.md`，移除私人庫網址 |
| `ce84c90` 留言蒐集修正 | 新增 `youtube_comments` 上限設定（每支 200 則、4000 次請求）；個別影片 400 `processingFailure` 改為記錄後略過（全部失敗仍報錯）；修正 `@帳號` 遮蔽規則（黏在文字中的帳號會漏）；測試 51 項 |

## 二、目前資料狀態

| 項目 | 狀態 |
|---|---|
| YouTube 前 100 | 完成。候選 1561、合格 573、選取 100；品牌頻道已排除 2 個 |
| YouTube 留言 | 完成。14,633 筆（含回覆 4,684），97 支影片，已去識別化；1 支關閉留言被略過 |
| Cofacts | **未做**。`data-kevin/raw/cofacts/` 是空的 |
| 標註、答案草稿、報告 | 程式完成，內容為空（樣本 0、草稿 0/20） |

資料以壓縮檔交付（`yt_handoff_20261124.zip`，內有說明與 SHA256）。解壓到專案根目錄即可，資料夾被 `.gitignore` 排除，不進版控。

## 三、接手後依序做

1. **Cofacts**：登入 Hugging Face 同意 Cofacts Data User Agreement，下載 `Cofacts/line-msg-fact-check-tw` 的 `articles`、`article_replies`（可加 `reply_requests`），放進 `data-kevin/raw/cofacts/`，執行 `python research.py cofacts`。不使用 API 模式（需向 Cofacts 申請 app-id）。
2. **YouTube 人工覆核**：看 `data-kevin/reports/youtube_top100_appendix.csv` 的「需人工覆核」列；品牌官方頻道 ID 補進 `config/research.yaml` 的 `excluded_channel_ids` 後執行 `youtube-rerank`（不耗配額）。
3. **標註**：`annotate-export --sample 300` → 兩人標註 → `annotate-import <表> --install`。
4. **答案草稿**：編輯依官方或學術 HTTPS 出處填 `data-kevin/drafts/topic_drafts.json`，`drafts-check` 檢查，`drafts-apply` 寫入後重置審閱。
5. **審閱與報告**：指導老師與公司雙方審閱後，執行 `research.py report` 產生 Q1–Q3 草稿。

完整指令見 `10_operator_guide.md`。

## 四、注意事項

- **YouTube 配額**：日配額 10,000 單位。`youtube-discover` 約 6,000、`youtube-comments` 約 2,500。同一天不要兩個都跑。2026-11-24 已用掉大部分，需隔天才能重抓。
- **留言上限**：每支影片只取最新 200 則頂層留言，熱門影片不完整，報告資料限制要寫明。
- **去識別化**：只降低再識別風險，不保證匿名。影片層級資訊只能放報告附件，不可進公開網站。
- **待決議**：排名是否分渠道加權（見 `05_decisions.md` 第 7 項）；「近兩年」截止日（目前 2024-11-23 至 2026-11-23）。
- **推送前**：`git remote -v` 顯示 `passin0/oil-observatory`，但 `CODEX_HANDOFF.md` 寫 `chessmanbry/oil-observatory`，須先確認目標。遠端 `main` 歷史與本地不同（遠端為匯入建立），建議推 `v3-iteration` 新分支，不要直接推 `main`。推送不等於網站上線。
- `CODEX_HANDOFF.md` 是 v2.0.0 時期的紀錄，現況以 `docs-kevin/` 為準。
- 金鑰在 `.env`（變數名 `yt_api_key`），不要提交，也不要放進壓縮檔。
