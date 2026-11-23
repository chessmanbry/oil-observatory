# 油品風向標 Oil Observatory — 第一階段 v1.0.0 歷史說明

供企業內部使用的油品輿情監測與科學證據對照系統。本機執行、離線 Demo、前端唯讀。設定、處理程式、資料與呈現分離。初始資料全部是假設留言，文獻不是虛構，但未經毒物醫學專業人員全文評讀；所有主張初始均為「待查核」。

## 快速啟動

需要 Python 3.10 以上（此版本在 Python 3.12.14 驗證）。不需要 Node.js、npm、模型服務或 API 金鑰即可使用 Demo。唯一第三方 Python 依賴為 PyYAML。

Windows：解壓縮後雙擊 `start_windows.bat`。首次啟動需連網安裝 PyYAML，之後 Demo 可離線使用。

Mac／Linux：在專案目錄開啟終端機執行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
python serve.py --research
```

Windows 手動操作：

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
.venv\Scripts\python.exe serve.py
```

瀏覽器開啟 http://localhost:8501 。Ctrl+C 停止。若連接埠被占用可使用 `python serve.py --research --port 8502`。網站不會在關閉終端機後持續執行；附帶的 SQLite 與 JSON 保留在專案目錄。

隨附已執行的 Demo 快照，`serve.py` 不會自行覆蓋既有結果。刪除或移走資料庫之後首次啟動才會建立 mock 結果。資料夾請放在可寫入的本機位置。

## 已實作的作業範圍

| 模組 | 已完成 |
|---|---|
| config | sources.yaml、keywords.yaml、analysis.yaml；格式驗證；設定快照與雜湊 |
| 蒐集 | 本機 mock JSON、人工 CSV、指定影片 YouTube Data API |
| 前處理 | HTML 實體還原、Unicode 正規化、斷句、日期與資料格式驗證、來源 ID 去重、三類關鍵詞與排除詞 |
| 分析 | 可複選疑慮分類、態度線索、提問／轉述／否定提示、自述消費意圖、本人年齡自述及長輩提及、使用條件線索 |
| 證據 | 候選文獻配對、研究條件與限制、書目與 DOI、人工文獻評讀及主張審核 |
| 儲存 | SQLite 執行快照、原始與處理後 JSON、逐筆排除原因、審核事件紀錄 |
| 網站 | 總覽、主張明細、文獻庫、執行紀錄、設定快照、來源／日期／主題／文字篩選、篩選結果 CSV 匯出 |
| 維護 | 命令列修正分類及態度、證據版本變更後自動讓舊審核失效 |

未實作：PTT／Dcard／FB 自動爬蟲、LLM 語意分析、自動論文搜尋或全文擷取、跨平台身分辨識、實際購買行為推論、正式分類準確率評估、定期背景排程及網路部署。這些不影響第一階段兩案例流程驗證。

YouTube 已實作，可在提供 API 金鑰與影片 ID 後執行；目前僅以離線 API 模擬回應驗證，未進行實際金鑰端到端測試。第一階段不宣稱自動醫學查核成立。

## Demo 資料與案例

`data/mock/comments.json` 有 33 筆假設紀錄，包含一筆重複匯入、一筆排除詞命中、一筆沒有關鍵詞命中。預設產出 30 則相關留言、36 個待判讀片段。

- 案例一：植物油加熱與健康疑慮。
- 案例二：油種比較與健康宣稱。
- 包含否定、轉述、複數主張、購買猶豫及本人／家人年齡等測試情境。
- 討論來源名稱只是模擬標籤，不代表真的向該平台取得資料。模擬資料沒有原始網路連結。
- 所有假設留言明確設 `is_mock: true`，網站不提供混合兩種資料類型的統計模式。

預設的 3 份候選來源：Fullana 等（2004），DOI 10.1021/jf035241f；EFSA（2011），DOI 10.2903/j.efsa.2011.2033；IARC 官方危害／風險方法說明。摘要只用於描述研究範圍與限制，均保留「待專業審核」。IARC 來源是方法說明，不是直接的油品效果研究。

## 設定公司關鍵詞

編輯 `config/keywords.yaml`：名稱對應同義詞清單，支援油種、油相關詞、品牌；`exclude_phrases` 設排除詞。新增品牌不用修改程式。

```yaml
brands:
  得意的一天: [得意的一天]
  公司品牌: [公司品牌, 品牌別名]
```

規則採 Unicode 正規化後的文字子字串比對，不是完整中文斷詞或簡繁轉換；必要的簡繁與英文別名需明列。這讓匹配依據容易檢查，但語意召回及精度需要真實標註集驗證。

`config/analysis.yaml` 定義分類、態度詞、購買意圖詞與案例配對。`method: rules` 為目前唯一支援模式；設為 LLM 會明確報錯，不會靜默換用其他服務。

`config/sources.yaml` 設來源與日期（台北時區，含起訖日；null 為不限）。更改設定後重新執行：

```bash
python run.py --source mock
```

網站的設定頁是「當次執行快照」，不會只因磁碟設定修改而改寫舊結果。

## 人工 CSV 匯入

將資料加入 `data/imports/comments.csv`，或在 sources.yaml 設另一個專案內相對路徑。CSV 用 UTF-8／UTF-8 BOM，含逗號或換行的欄位須以雙引號包住。

| 欄位 | 必填 | 規則 |
|---|---|---|
| id | 是 | 平台留言 ID；人工整理需提供穩定且不重複的 ID |
| source | 是 | YouTube、PTT、Dcard、FB 或自訂來源名稱 |
| text | 是 | 原始文字；勿填模型摘要取代原文 |
| published_at | 是 | ISO 8601，例如 2026-10-22T18:30:00+08:00；無時區視為台北 |
| is_mock | 是 | true 或 false；真實資料填 false，不接受缺漏或模糊值 |
| url | 否 | 原文 HTTP(S) 連結；模擬資料可空白 |
| author_key | 否 | 去識別化作者代碼，非必要時不保存姓名 |
| parent_id | 否 | 回覆所屬的頂層留言 ID |

```bash
python run.py --source csv
```

格式不正確的資料列保留在 `data/processed/<run_id>.json` 的 audit 中，不納入分析。若整批沒有相關留言，仍保留當次執行與排除統計，網站顯示空狀態；來源檔案完全沒有資料則明確報錯。

## YouTube 蒐集

1. 於 Google Cloud 啟用 YouTube Data API v3，取得適用的 API 金鑰。
2. 編輯 sources.yaml 的 youtube 區塊：`enabled: true`、`video_ids: ["影片11碼ID"]`。
3. 金鑰只放在環境變數，切勿寫進設定檔、README 或提交程式庫。

Mac／Linux：

```bash
export YOUTUBE_API_KEY='你的金鑰'
python run.py --source youtube
```

Windows PowerShell：

```powershell
$env:YOUTUBE_API_KEY='你的金鑰'
.venv\Scripts\python.exe run.py --source youtube
```

支援頂層留言分頁及 `comments.list` 的回覆分頁；不把 commentThreads 的部分回覆當成全部。可設定 include_replies、max_top_level_per_video、max_requests、timeout_seconds。

按最新時間排序蒐集，再以本機設定日期篩選。筆數上限可能使較舊留言未被涵蓋，因此不保證日期區間的完整性。達到請求上限或遇到無法恢復的 API 錯誤時，本次不寫入新執行，既有結果不受影響。HTTP 429／部分 5xx 有有限次退避重試，不會無限請求。作者頻道代碼僅保留雜湊，並未保存顯示名稱；雜湊屬去識別代碼，不承諾完全匿名。

應依實際來源權限與平台條件使用；第一階段不提供繞過登入或防爬蟲機制。

官方 API 文件：
- https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list
- https://developers.google.com/youtube/data/reference/rest/v3/comments/list

## 人工審核流程

先完成實際全文評讀、檢查研究條件、結果、限制與利益衝突，必要時編輯 `data/references/library.json`。審核指令只記錄人工責任，不驗證執行人的專業資格；必須由公司指定適任人員操作。

```bash
python review.py reference REF-HEAT-2004 --reviewer "實際審核者" --note "請填入全文評讀、適用條件及限制"
python run.py --source mock
```

文獻變更後要重新跑同一來源，把新文獻版本帶入執行。接著在主張明細取得主張 ID：

```bash
python review.py claim 主張ID --decision "證據不足" --reviewer "實際審核者" --rationale "條件資訊不足，無法判定此情境"
```

如要判定「支持」「部分支持／有條件成立」或「不支持」，必須指定至少一份已審核文獻：

```bash
python review.py claim 主張ID --decision "部分支持／有條件成立" --references REF-HEAT-2004 --reviewer "實際審核者" --rationale "請以實際研究與原文情境填寫判讀理由"
```

亦可修正分類及態度（選填）：

```bash
python review.py claim 主張ID --decision "證據不足" --reviewer "實際審核者" --rationale "已重新判讀否定語句" --categories 健康風險 使用方式 --sentiment "混合／待判讀"
```

可選判定：支持、部分支持／有條件成立、不支持、證據不足、不適用於目前情境。

以上命令中的理由是操作示例，不代表本系統已作出該科學結論。

主張審核存在 SQLite `reviews`，文獻評讀事件存在 `data/references/history/`。同一份留言、設定與文獻內容未改變時重跑會沿用審核；任何內容版本變更則保守失效，回到待審核，避免把舊審核直接移植到新條件。過去快照仍保留原有結果。沒有新增待辦排程或自動健康判定。

## 重要計數與分析定義

- 留言單位：資料類型＋來源＋原始 ID。相同 ID 相同文字只保留一筆；相同 ID 不同文字記為衝突待處理，不自動選新版。
- 相同文字但不同 ID 保留為獨立留言，提示重複群組，不將留言數當成獨立人數。
- 主張單位：依句號、問號、驚嘆號、分號及換行拆分的片段；並非完整語意主張抽取。所有片段可回看完整原文；第二句的指涉不自動繼承。
- 分類可複選，兩案例可重疊；各類加總不必等於片段總數。
- 态度是文字規則提示，討論對象為留言命中的油種／品牌候選，不代表精確的實體情緒關聯。
- 年齡只解析明確本人自述，如「我今年62歲」。提及媽媽／長輩分開記錄。沒有自述為未知，不依平台或頭像猜測。
- 自述消費意圖僅表示文字線索，不代表實際行為或因果影響。
- 文獻配對是主題規則，並未自動判斷證據支持程度。所有初始結果待審核；不存在虛構的分類準確率或醫學評分。

## 檔案結構

| 路徑 | 用途 |
|---|---|
| config/ | 三份 YAML 設定 |
| src/collectors.py | mock／CSV／YouTube 取得 |
| src/preprocess.py | 清理、驗證、日期、去重及關鍵詞 |
| src/analyzers.py | 分類、態度、線索、文獻候選 |
| src/pipeline.py | 四階段流程與版本管理 |
| src/storage.py | SQLite 與快照 |
| src/report.py | JSON、CSV、摘要輸出 |
| data/mock/ | 假設留言 |
| data/imports/ | 人工匯入 CSV |
| data/raw/ | 每次原始匯入紀錄 |
| data/processed/ | 每次相關留言及逐筆審計 |
| data/references/ | 文獻庫、審核與限制 |
| data/results/ | SQLite、最新 JSON、CSV、摘要 |
| web/ | 無外部 CDN 的 HTML／CSS／JavaScript |
| run.py / serve.py / review.py | 執行、網站、人工審核入口 |
| docs/ | 架構與驗收紀錄 |
| tests/ | 自動驗證 |

## 測試與維護

```bash
python -m unittest discover -s tests -v
```

測試用臨時資料夾，不會改動使用者資料。涵蓋離線流程、CSV、去重、日期、族群、審核版本、HTTP 唯讀、YouTube 分頁／錯誤／請求預算。

備份時先停止程式，再複製整個專案或至少 config 與 data。資料與原文為本機檔案，須由公司自行管理電腦存取及備份。此版預設綁定 127.0.0.1，沒有登入與多使用者權限管理，不應直接對外開放；`--host` 參數僅供受控測試使用。

網站用唯讀 SQLite 連線、固定靜態資源白名單及文字轉義。CSV 匯出對公式起始字元加引號前綴；API 金鑰不輸出至結果或網站。
