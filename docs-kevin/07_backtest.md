# 回測紀錄（2026-11-23）

- 既有 31 項測試於 Windows 原本失敗（SQLite 檔案鎖定、cp950 讀檔）；修正後全綠。
- 新增 19 項 research 測試（遮蔽、期間、關鍵詞、Cofacts dump/api、YouTube 排名與錯誤不洩金鑰、kappa、標註往返、草稿不外洩、報告空狀態）。總計 50 項通過。
- CLI 冒煙：drafts-check（0/20 可送審）、report（樣本 0）、cofacts 缺資料時給出協議說明。
- 未驗證：真實 Cofacts／YouTube 資料、macOS、真實標註效能。
