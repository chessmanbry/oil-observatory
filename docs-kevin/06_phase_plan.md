# 開發階段計畫（v3）

| 階段 | 目標 | 狀態 |
|---|---|---|
| P0 基線 | Windows 下測試全綠、規格文件、分支 v3-iteration | 完成（修正 SQLite 未關閉與測試編碼，31 項通過） |
| P1a Cofacts | dump／API 兩模式、期間、關鍵詞、排除、語言、去識別化、授權標示 | 程式完成；真實資料待使用者同意 HF 協議或取得 app-id |
| P1b YouTube | 各關鍵詞 viewCount 搜尋 → 前 N、廣告與品牌排除、留言蒐集、附件 CSV | 程式完成；真實執行待 YOUTUBE_API_KEY |
| P2 標註 | 預標註、雙人標註表、kappa、定稿匯入 observations.json | 完成 |
| P3 草稿接口 | data-kevin/drafts、drafts-check／apply（需 --confirm，重置審閱） | 完成；內容待編輯填寫（不連接網站） |
| P4 網站 | 版本 3.0.0；公開投影與審閱機制不變 | 完成最小更新 |
| P5 報告 | Q1–Q3 草稿、Top 20 表、YouTube 附件、限制聲明 | 完成產生器；內容待真實資料 |
| P6 回測 | 50 項 unittest、CLI 冒煙、空資料路徑 | 完成 |

後續（需人工）：取得 Cofacts／YouTube 資料 → 雙人標註 → 編輯撰寫並引用官方／學術出處 → 指導老師與公司審閱 → 發布。
