"""重建公開頁資料投影，同時驗證公司內容設定。"""
from pathlib import Path
from src.public_content import catalogue
from src.report import write_json

ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    data = catalogue(ROOT)
    write_json(ROOT / 'data/results/public.json', data)
    m = data['meta']
    print(f"已建立網頁資料，議題 {m['topic_count']}、已審閱 {m['reviewed_count']}、正式排名 {m['ranked_count']}")
