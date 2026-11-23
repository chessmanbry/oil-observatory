from datetime import date
from pathlib import Path
import hashlib
import json
import yaml


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load_config(root):
    root = Path(root)
    result = {}
    for name in ('sources', 'keywords', 'analysis'):
        try:
            with (root / 'config' / f'{name}.yaml').open(encoding='utf-8') as f:
                result[name] = yaml.safe_load(f)
        except yaml.YAMLError:
            raise ValueError(f'{name}.yaml 語法錯誤，請檢查縮排、引號與清單格式') from None
        if not isinstance(result[name], dict):
            raise ValueError(f'{name}.yaml 必須為物件')
    sources, keywords, analysis = (result[k] for k in ('sources', 'keywords', 'analysis'))
    if analysis.get('method') != 'rules':
        raise ValueError('第一階段僅支援 method: rules；尚未啟用 LLM，不會傳送資料至模型服務。')
    for group in ('oil_types', 'oil_terms', 'brands'):
        if not isinstance(keywords.get(group), dict):
            raise ValueError(f'keywords.{group} 必須為名稱對應別名清單')
        for aliases in keywords[group].values():
            if not isinstance(aliases, list) or not aliases or not all(isinstance(x, str) and x.strip() for x in aliases):
                raise ValueError(f'{group} 別名必須是非空文字清單')
    for key in ('categories', 'purchase_rules'):
        if not isinstance(analysis.get(key), dict) or not all(isinstance(v, list) and all(isinstance(x, str) and x for x in v) for v in analysis[key].values()):
            raise ValueError(f'analysis.{key} 格式錯誤')
    for key in ('positive_terms', 'negative_terms', 'question_terms', 'negation_terms'):
        if not isinstance(analysis.get(key), list) or not all(isinstance(x, str) and x for x in analysis[key]):
            raise ValueError(f'analysis.{key} 必須為文字清單')
    threshold = analysis.get('older_age_threshold')
    if type(threshold) is not int or not 18 <= threshold <= 100:
        raise ValueError('older_age_threshold 必須介於 18–100')
    cases = analysis.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('至少定義一個案例')
    case_ids = set()
    for case in cases:
        if not isinstance(case, dict) or not all(case.get(k) for k in ('id', 'title', 'triggers', 'reference_ids')) or not isinstance(case['id'], str) or case['id'] in case_ids:
            raise ValueError('案例缺少欄位或 id 重複')
        for key in ('triggers', 'reference_ids'):
            if not isinstance(case[key], list) or not all(isinstance(x, str) and x for x in case[key]):
                raise ValueError(f'案例 {key} 必須為文字清單')
        case_ids.add(case['id'])
    if not isinstance(keywords.get('exclude_phrases', []), list) or not all(isinstance(x, str) and x for x in keywords.get('exclude_phrases', [])):
        raise ValueError('exclude_phrases 必須為文字清單')
    for source in ('mock', 'csv', 'youtube'):
        if not isinstance(sources.get(source), dict) or type(sources[source].get('enabled')) is not bool:
            raise ValueError(f'sources.{source} 必須有 enabled 布林值')
    for source in ('mock', 'csv'):
        if not isinstance(sources[source].get('path'), str) or not sources[source]['path']:
            raise ValueError(f'sources.{source}.path 必須為非空文字')
    for key in ('date_from', 'date_to'):
        value = sources.get(key)
        if value is not None:
            sources[key] = str(value)
            date.fromisoformat(sources[key])
    if sources.get('date_from') and sources.get('date_to') and sources['date_from'] > sources['date_to']:
        raise ValueError('date_from 不得晚於 date_to')
    return result


def local_path(root, relative):
    path = (Path(root) / relative).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('資料路徑必須位於專案目錄內')
    return path
