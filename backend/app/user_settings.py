"""Small, local preferences with revision checks and atomic replacement."""
import json
from pathlib import Path

from .errors import AppError
from .sources.categories import INDEX


DEFAULTS = {"revision": 0, "ui_language": "zh", "report_language": "zh", "custom_categories": []}


def read_settings(data_dir: Path) -> dict:
    path = data_dir / "settings.json"
    if not path.exists():
        return dict(DEFAULTS)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or not isinstance(value.get("revision"), int)
                or value.get("ui_language") not in {"zh", "en"}
                or value.get("report_language") not in {"zh", "en", "bilingual"}
                or not isinstance(value.get("custom_categories"), list)
                or any(code not in INDEX for code in value["custom_categories"])):
            raise ValueError("invalid settings")
        return value
    except (OSError, ValueError, TypeError) as exc:
        raise AppError("SETTINGS_INVALID", "本机设置文件无法读取，请检查 settings.json。", 409) from exc


def update_settings(data_dir: Path, expected_revision: int, custom_categories: list[str] | None = None,
                    ui_language: str | None = None, report_language: str | None = None) -> dict:
    current = read_settings(data_dir)
    if expected_revision != current["revision"]:
        raise AppError("REVISION_CONFLICT", "设置已被其他页面更改，请刷新后重试。", 409)
    custom_categories = current['custom_categories'] if custom_categories is None else custom_categories
    if (len(custom_categories) > 30 or len(set(custom_categories)) != len(custom_categories)
            or any(code not in INDEX for code in custom_categories)):
        raise AppError("INVALID_CATEGORY", "自定义标签须为不重复的 arXiv 官方分类，最多 30 个。", 422)
    ui_language = current['ui_language'] if ui_language is None else ui_language
    report_language = current['report_language'] if report_language is None else report_language
    if ui_language not in {'zh', 'en'} or report_language not in {'zh', 'en', 'bilingual'}:
        raise AppError('INVALID_LANGUAGE', '界面只支持中文或英语；报告支持中文、英语或中英双语。', 422)
    updated = {**current, "revision": current["revision"] + 1, "custom_categories": custom_categories,
               'ui_language': ui_language, 'report_language': report_language}
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "settings.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return updated
