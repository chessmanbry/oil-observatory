# 標註流程

1. `python research.py annotate-export --sample 300` 產生標註表（依渠道分層抽樣，附規則建議）。
2. 兩位標註者各填 annotator_a_* / annotator_b_*（relevant 是／否、topic 為 topics.json 的 id、role 散播／疑問／澄清）。
3. 雙方討論後填 final_*。
4. `python research.py annotate-import 表.csv [--install]`：產生 agreement.md（kappa、一致率、規則精確率／召回率）與 observations；`--install` 寫入 data/editorial/observations.json。
5. 網站與報告只計 validated=true 的定稿樣本。
