import json
from pathlib import Path
from ..errors import AppError

CATALOG = json.loads(Path(__file__).with_name('categories.json').read_text(encoding='utf-8'))
CATEGORIES = CATALOG['categories']
INDEX = {item['code']: item for item in CATEGORIES}


def candidates(query=''):
    query = query.strip().casefold()
    exact = [row for row in CATEGORIES if query and query in [value.casefold() for value in [row['code'], row['official_name'], row['zh_name'], *row['aliases']]]]
    if exact:
        return sorted(exact, key=lambda row: row['code'])
    rows = CATEGORIES if not query else [row for row in CATEGORIES if any(query in value.casefold() for value in
            [row['code'], row['official_name'], row['zh_name'], *row['aliases']])]
    return sorted(rows, key=lambda row: (0 if query in [v.casefold() for v in [row['code'], *row['aliases']]] else 1, row['code']))


def category_members(codes):
    if not codes or any(code not in INDEX for code in codes):
        raise AppError('INVALID_CATEGORY', '请从候选中选择有效的 arXiv 官方分类。', 422)
    return sorted({member for code in codes for member in INDEX[code]['members']})
