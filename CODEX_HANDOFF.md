# Codex 專案交接

## 使用者目前要求

依公司 2026-11-19 提供的《食用油網路迷思分析 專案需求文件》修改網頁，並將專案交給 Codex 持續開發、同步到 GitHub。專案先在本機預覽。公司要求上線前由指導老師與公司共同審閱。

## 已交接的版本

v2.0.0 為公司需求版的可操作網頁，已完成首頁、六類議題、議題搜尋、正式 Top 20 入口、說法／落差／答案／出處明細、Cofacts 與 YouTube 的渠道比較、簡易問答與方法說明。預設 20 個候選議題由編輯撰寫，真實樣本、已審閱答案與正式排名目前都是 0。

資訊頁投影只提供白名單欄位。未完成雙方審閱的答案與引用不會送到前端。Q&A 用已審閱的完整問題與人工同義問法做正規化後的精確比對，未命中時告知尚未收錄並列相關議題。內容編輯使審閱雜湊失效，撤回即停止提供答案。公司需要更廣的語意搜尋時，先評估查詢召回並保留審閱限制。

v1 研究管線保留於 src/ 與 run.py。舊版分析面向含健康風險、價格、情緒與族群，並未全面改造成公司研究的散播／疑問／澄清標註器。公開頁目前讀取人工覆核的 data/editorial/observations.json，以正式研究資料和早期 Demo 分開管理。

## 主要入口

```bash
python -m pip install -r requirements.txt
python build_public.py
python serve.py
python -m unittest discover -s tests -q
```

公開頁 http://localhost:8501。舊版本機研究介面用 `python serve.py --research --port 8502`。

## 關鍵檔案

| 檔案 | 用途 |
|---|---|
| web/index.html、app.js、style.css | 公司需求版網站 |
| web/research/ | 舊版研究人員介面 |
| config/company.yaml | 公司六類議題、關鍵詞、期間與來源 |
| data/editorial/topics.json | 編輯候選議題、定稿答案、出處與審閱 |
| data/editorial/observations.example.json | 空白標註模板，正式樣本另放 observations.json |
| src/public_content.py | 公開資料投影、排名、渠道比例、審閱檢查、問答 |
| editorial.py | 本機雙方審閱與撤回指令 |
| build_public.py | 驗證並產生公開 JSON 快照 |
| serve.py | 本機伺服器，預設封鎖原始研究 API |
| tests/test_company_site.py | 新版網站與內容邊界測試 |
| docs/company_requirements.md | 公司需求對照與待完成工作 |

## 驗證與技術選擇

2026-11-23，31 項 unittest 通過。瀏覽器已操作首頁、議題搜尋、議題明細、尚未收錄問答、正式排名空狀態及方法說明。Windows／macOS 實機啟動仍待驗證。

近兩年目前明確設定為 2024-11-23 至 2026-11-23，含起訖日。這是本次開發採用的研究截點，正式資料蒐集前須依雙方確認的日期調整。

「流傳最廣」目前實作為已覆核真實樣本中的散播筆數，同分以議題 ID 排序。Cofacts 收錄次數與 YouTube 留言筆數有不同偏差，研究方法及正式排名需再確認是否採用分渠道排序或權重。

## 接續完成順序

1. 從私人儲存庫 chessmanbry/oil-observatory 取得最新 main，執行現有測試與公開投影建置。不得把 GitHub 同步寫成網站已對外上線。
2. 接取 Cofacts 公開資料，記錄資料版本、合法使用條件、取得時間與期間篩選，維護原始與去識別化資料。
3. 依關鍵詞建立 YouTube 影片候選清單，取得觀看數，再人工覆核廣告與品牌官方頻道排除條件，形成前 100 清單。現有蒐集器只支援指定 video_ids 的留言與完整回覆分頁。
4. 建立議題歸併與散播／疑問／澄清的標註規則、雙人標註樣本及一致性或分類效能評估。對接 observations.json。
5. 逐題建立官方或學術證據、落差與適用條件，取得公司與指導老師審閱後發布答案與 Top 20。
6. 產出 Q1–Q3 的期末報告、Top 20 對照表與僅供附件的 YouTube 前 100 清單。

## GitHub 狀態

2026-11-23 已確認帳號 chessmanbry，並建立私人儲存庫 https://github.com/chessmanbry/oil-observatory ，預設分支 main。GitHub 連線工具可讀寫此庫；gh CLI 尚未登入。本次使用連線工具匯入程式與交接文件，核對本機與遠端 Git tree 雜湊以驗證檔案內容；匯入提交與先前本機提交的歷史不同。先前交接包的 repository.bundle 保存同步前兩筆本機提交。實際匯入提交與最終核對結果以此次操作回報為準。

## 給下一個 Codex 工作階段的起始指令

請讀 AGENTS.md 與 CODEX_HANDOFF.md，確認目前工作目錄來自 chessmanbry/oil-observatory 的 main，執行現有測試。接著依 docs/company_requirements.md 補實際 Cofacts 與 YouTube 樣本，維護已審閱答案的問答限制，保留候選內容與研究結果的清楚標記。
