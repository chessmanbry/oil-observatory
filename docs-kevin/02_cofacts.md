# Cofacts 資料取得

- 資料：Hugging Face `Cofacts/line-msg-fact-check-tw`，CC BY-SA 4.0；須登入並同意 Cofacts Data User Agreement 後下載 articles、article_replies（可加 reply_requests）。放入 `data-kevin/raw/cofacts/`（csv 或 zip）。
- 執行：`python research.py cofacts`；輸出 `data-kevin/processed/cofacts_candidates.json`（含資料版本、取得時間、篩選統計、授權與出處標示）。
- 篩選順序：狀態、文字類型、期間、關鍵詞、排除詞、簡體、僅 NOT_ARTICLE 回覆。
- 不輸出 userIdsha256；文字做網址、電話、電子郵件、@、LINE ID 遮蔽。
- API 模式需向 cofacts@googlegroups.com 申請 app-id，設環境變數 COFACTS_APP_ID。
- 報告與網站須標示：Cofacts 訊息回報機器人與查證協作社群，CC BY-SA 4.0。
