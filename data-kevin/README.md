# data-kevin

v3 研究資料與草稿區。

| 路徑 | 內容 | 版控 |
|---|---|---|
| drafts/topic_drafts.json | 20 題答案草稿模板（目前全空）。接口：`python research.py drafts-check` / `drafts-apply` | 追蹤 |
| raw/cofacts/ | 手動下載的 Cofacts CSV／zip（CC BY-SA 4.0，需先同意使用者協議） | 忽略 |
| processed/ | 篩選與去識別化後的候選資料、YouTube 前 100 清單 | 忽略 |
| annotation/ | 雙人標註表 | 忽略 |
| reports/ | 期末報告草稿、Top 20 表、YouTube 附件、一致性報告 | 忽略 |

草稿不連接網站。`drafts-apply` 需 `--confirm` 與 `--editor`，並重置雙方審閱。
