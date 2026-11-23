# 油品風向標 公司需求版 v3.0.0

食用油迷思資訊頁與簡易問答，依公司 2026-11-19 文件更新。包含首頁、六類議題、對照明細、渠道筆數與比例、研究方法，以及僅查詢已審閱答案的問答。

目前 20 題為編輯建立的候選示範。真實樣本、已審閱答案與正式 Top 20 尚待建立。初始問答會明確回覆尚未收錄。Cofacts 蒐集與 YouTube 前 100 篩選工作列於 CODEX_HANDOFF.md。

## 啟動

需要 Python 3.10+，只需安裝 PyYAML，預覽不需 Node.js 或付費 API。

```bash
python -m pip install -r requirements.txt
python build_public.py
python serve.py
```

同一台電腦開啟 http://localhost:8501 。Windows 可雙擊 start_windows.bat。macOS／Linux 可執行 bash start_mac_linux.sh。首次安裝依賴需要連網。

研究人員可另開舊版儀表板。

```bash
python run.py --source mock
python serve.py --research --port 8502
```

此模式含原始測試資料，只供研究人員本機使用。詳細研究管線操作見 docs/legacy_v1.md。

## 網頁資料與審閱

config/company.yaml 設定六類議題、研究日期、來源與公司關鍵詞。data/editorial/topics.json 編輯題目、概括說法、落差、答案、出處與同義問句。正式標註放在 data/editorial/observations.json，缺檔時使用空白 example。資料格式見 docs/company_requirements.md。

來源需填官方或學術 HTTPS 連結。類型改為迷思、疑問或澄清並完成答案後，由實際審閱人員依角色記錄審閱。

```bash
python editorial.py review smoke-point --role teacher --reviewer "實際老師姓名" --note "實際審閱紀錄"
python editorial.py review smoke-point --role company --reviewer "實際公司審閱人" --note "實際審閱紀錄"
python build_public.py
```

兩個角色的審閱均對應當時的內容雜湊。修改答案、題目、引用、落差或問答同義句後，舊審閱自動失效，須重新審閱。命令列只記錄責任，不驗證人員專業資格。請勿將操作示例當成已取得審閱。

暫時撤回議題及答案。

```bash
python editorial.py withdraw smoke-point --reviewer "維護人" --note "實際撤回原因"
```

恢復後需再次審閱。

```bash
python editorial.py restore smoke-point --reviewer "維護人" --note "修正已完成"
```

公開 API 採資料白名單，並於每次查詢重新檢查審閱，直接使用當前資料。build_public.py 另產生可查驗的快照。

## 測試

```bash
python -m unittest discover -s tests -q
node --check web/app.js
```

目前 31 項測試涵蓋 v1 管線與 v2 公開頁、審閱限制、排名計數、未知問句、撤回、資料版本和公開 API。瀏覽器已操作首頁、搜尋、明細、問答、正式排名空狀態與方法頁。Windows／macOS 實機驗證仍待完成。

## 版本控制與交接

開始前先讀 AGENTS.md、docs-kevin/00_index.md 與 CODEX_HANDOFF.md（歷史交接紀錄）。推送前以 `git remote -v` 確認目標儲存庫。程式碼同步不代表網站已上線；公開網站部署須先完成指導老師與合作單位的共同審閱。
