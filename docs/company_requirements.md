# 公司需求對照

依 2026-11-19 公司文件整理，供開發與驗收使用。

| 公司要求 | 目前實作 | 待完成 |
|---|---|---|
| 資訊頁與簡易問答 | 首頁、議題列表、對照明細、查詢、方法說明 | 填入經審閱的實際內容 |
| Top 20 迷思 | 已覆核樣本計數、依散播筆數排名、正式排名入口 | 真實樣本、研究方法確認、正式名單 |
| 常見說法、落差、答案、出處 | 獨立欄位與議題明細 | 各題文獻查核與審閱 |
| Cofacts 必做 | 渠道欄位與標註資料接口 | 開放資料取得與資料版本紀錄 |
| YouTube 前 100 支 | 原有指定影片留言蒐集器；本版網站採渠道彙整 | 候選搜尋、觀看數排序、廣告與品牌頻道排除、附件報表 |
| 近兩年、繁體中文 | company.yaml 可調整期間、語言與完整初版關鍵詞 | 真實資料覆蓋與語言判定 |
| 散播、疑問、澄清 | observations 標註、去重、筆數與渠道比例 | 人工標註樣本與可信度檢驗 |
| 每個結論附筆數、占比與代表內容 | 明細計數與比例、審閱後代表性摘要欄位 | 真實且去識別化的代表摘要 |
| 問答只回覆已審閱內容 | 內容雜湊、雙方審閱、精確問句／同義問法比對、未收錄回覆 | 實際審閱答案與同義問法集合 |
| 隱私、品牌中立、創作者不點名 | 預設 API 不提供原始留言與影片個別資訊 | 正式資料的人工去識別化覆核 |
| 上線前共同審閱 | teacher 與 company 雙方審閱紀錄；內容變更失效；可撤回 | 真實審閱與部署環境 |
| 操作可重跑、關鍵詞可替換 | Python 原始碼、YAML、啟動腳本與 README | 公司電腦實機驗證 |

## 資料格式

正式標註另存於 data/editorial/observations.json，未提供時讀取 observations.example.json 的空陣列。每筆格式如下，示例 ID 只供格式參考。

```json
{
  "id": "來源紀錄的內部穩定代碼",
  "topic_id": "canola-fry",
  "channel": "Cofacts",
  "day": "2026-11-01",
  "role": "question",
  "is_mock": false,
  "validated": true
}
```

role 可為 spread、question、clarify。只有明確 is_mock=false、validated=true、日期在指定期間內、渠道符合設定的資料才納入計數。相同渠道＋紀錄 ID＋議題去重。衝突標註會中止公開資料建立。

topics.json 的 sources 每筆包含 title、url、type，type 為 official 或 academic，可另附 doi、organization。qa_aliases 僅放人工核對的完整同義問句。尚未經審閱的 answer、gap 與 sources 不傳至公開 API。

## 參考接口

- Cofacts 官方 API 文件 https://api.cofacts.tw/
- YouTube 官方搜尋接口 https://developers.google.com/youtube/data/reference/rest/v3/search/list
- YouTube 影片資訊接口 https://developers.google.com/youtube/data/reference/rest/v3/videos/list

搜尋排序與日期條件可能影響 YouTube 結果涵蓋，正式研究須交代候選來源和排除流程。
