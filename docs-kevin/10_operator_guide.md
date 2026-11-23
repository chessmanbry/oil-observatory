# 操作說明（公司人員重跑）

```powershell
python -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe research.py cofacts
.venv\Scripts\python.exe research.py youtube-discover
.venv\Scripts\python.exe research.py youtube-comments
.venv\Scripts\python.exe research.py annotate-export --sample 300
.venv\Scripts\python.exe research.py annotate-import data-kevin/annotation/sheet.csv --install
.venv\Scripts\python.exe build_public.py
.venv\Scripts\python.exe research.py report
.venv\Scripts\python.exe serve.py
```

換一組關鍵詞：複製 `config/company.yaml` 的 keywords 區塊為新 YAML（oil_types、terms 兩個清單），所有指令加 `--keywords 新檔.yaml`。
前置：Cofacts CSV 放 data-kevin/raw/cofacts；YOUTUBE_API_KEY 環境變數。
