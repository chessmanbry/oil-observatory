"""v3 研究管線共用工具：設定、關鍵詞比對、語言判定、去識別化與期間篩選。

此模組不連網。產出只寫入 data/（原始與處理後資料已列入 .gitignore）。
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import re
import unicodedata
import yaml

TAIPEI = timezone(timedelta(hours=8))

# 常見繁簡對應字。只用來粗分語言，不做轉換；無法判定時標為 zh。
_TRAD = set('這們說時為發煙點會沒過還對讓給樣經關麼嗎實東見種處體個來國煉護雞豬蘿蔔糧醫藥署檢驗聽讀寫買賣')
_SIMP = set('这们说时为发烟点会没过还对让给样经关么吗实东见种处体个来国炼护鸡猪萝卜粮医药署检验听读写买卖')
_SIMP -= _TRAD

URL_RE = re.compile(r'https?://\S+|www\.\S+', re.I)
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'(?<!\d)(?:\+?886[-\s]?|0)9\d{2}[-\s]?\d{3}[-\s]?\d{3}(?!\d)|(?<!\d)0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)')
# 不限制 @ 前方字元：YouTube 回覆常見 "@t@handle"、"張@張某某" 這類黏在文字中的帳號。電子郵件已先被遮蔽。
MENTION_RE = re.compile(r'@[\w.\-一-鿿]{1,30}')
LINE_ID_RE = re.compile(r'(?i)(line\s*(?:id)?\s*[:：]\s*)\S+')


def read_yaml(path):
    with Path(path).open(encoding='utf-8') as f:
        value = yaml.safe_load(f)
    if not isinstance(value, dict):
        raise ValueError(f'{Path(path).name} 必須為物件')
    return value


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_settings(root, keywords_path=None):
    """Merge company.yaml (period, channels, keywords) with research.yaml.

    keywords_path lets company staff rerun with another keyword set without editing code:
    a YAML file with oil_types and terms lists.
    """
    root = Path(root)
    company = read_yaml(root / 'config/company.yaml')
    research = read_yaml(root / 'config/research.yaml')
    keywords = company['keywords']
    if keywords_path:
        keywords = read_yaml(keywords_path)
    for key in ('oil_types', 'terms'):
        if not isinstance(keywords.get(key), list) or not all(isinstance(x, str) and x.strip() for x in keywords[key]):
            raise ValueError(f'關鍵詞檔須有非空文字清單 {key}')
    start, end = date.fromisoformat(str(company['date_from'])), date.fromisoformat(str(company['date_to']))
    if start > end:
        raise ValueError('研究期間起日晚於迄日')
    out = (root / research.get('output_dir', 'data')).resolve()
    if not out.is_relative_to(root.resolve()):
        raise ValueError('output_dir 須位於專案內')
    return {
        'root': root, 'company': company, 'research': research,
        'keywords': {'oil_types': list(keywords['oil_types']), 'terms': list(keywords['terms'])},
        'keywords_source': str(keywords_path) if keywords_path else 'config/company.yaml',
        'start': start, 'end': end, 'out': out,
        'exclude': list(research.get('exclude_phrases', [])),
    }


def normalize(text):
    return unicodedata.normalize('NFKC', str(text or '')).casefold()


def _contains(norm, word):
    """中文詞用子字串；純 ASCII 詞須為完整單字，避免 BaP 命中 bap（印地語）等。"""
    w = normalize(word)
    if w.isascii():
        return re.search(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])', norm) is not None
    return w in norm


def keyword_hits(text, keywords):
    """Return matched keywords (oil types and terms)."""
    norm = normalize(text)
    hits = []
    for group in ('oil_types', 'terms'):
        for word in keywords[group]:
            if _contains(norm, word) and word not in hits:
                hits.append(word)
    return hits


def oil_type_hits(text, keywords):
    norm = normalize(text)
    return {w for w in keywords['oil_types'] if _contains(norm, w)}


def excluded(text, phrases):
    norm = normalize(text)
    return [p for p in phrases if normalize(p) in norm]


def language(text):
    """粗略判定 zh-Hant / zh-Hans / zh（無可區分字）/ other（無中文字）/ ja-ko（含假名或韓文）。"""
    if any('぀' <= c <= 'ヿ' or '가' <= c <= '힯' for c in text):
        return 'ja-ko'
    trad = sum(c in _TRAD for c in text)
    simp = sum(c in _SIMP for c in text)
    if trad or simp:
        return 'zh-Hant' if trad >= simp else 'zh-Hans'
    if any('一' <= c <= '鿿' for c in text):
        return 'zh'
    return 'other'


def deidentify(text):
    """遮蔽網址、電子郵件、電話、@提及與 LINE ID。只降低再識別風險，不保證完全匿名。"""
    text = URL_RE.sub('［網址］', str(text or ''))
    text = EMAIL_RE.sub('［電子郵件］', text)
    text = PHONE_RE.sub('［電話］', text)
    text = LINE_ID_RE.sub(lambda m: m.group(1) + '［ID］', text)
    text = MENTION_RE.sub('［帳號］', text)
    return text


def taipei_day(timestamp):
    value = str(timestamp).strip()
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(TAIPEI).date()


def in_window(day, settings):
    return settings['start'] <= day <= settings['end']


def rfc3339_bounds(settings):
    """台北時區含起訖日的期間，轉成 API 用的 UTC RFC 3339。"""
    start = datetime.combine(settings['start'], datetime.min.time(), TAIPEI)
    end = datetime.combine(settings['end'] + timedelta(days=1), datetime.min.time(), TAIPEI)
    fmt = lambda d: d.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return fmt(start), fmt(end)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def read_dotenv(root):
    """讀取專案根目錄 .env（已列入 .gitignore）。鍵名不分大小寫、容許 `=` 前後空白；不寫入 os.environ。"""
    path = Path(root) / '.env'
    values = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                name, _, value = line.partition('=')
                values[name.strip().upper()] = value.strip().strip('"\'')
    return values
