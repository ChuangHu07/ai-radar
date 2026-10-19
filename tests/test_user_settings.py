import json

import pytest

from app.errors import AppError
from app.user_settings import read_settings, update_settings


def test_custom_category_tags_survive_reload(tmp_path):
    initial = read_settings(tmp_path)
    assert initial == {"revision": 0, "ui_language": "zh", "report_language": "zh", "custom_categories": []}
    saved = update_settings(tmp_path, 0, ["cs.AI", "math"])
    assert saved["revision"] == 1
    assert read_settings(tmp_path)["custom_categories"] == ["cs.AI", "math"]
    with pytest.raises(AppError) as stale:
        update_settings(tmp_path, 0, [])
    assert stale.value.code == "REVISION_CONFLICT"
    with pytest.raises(AppError) as invalid:
        update_settings(tmp_path, 1, ["cs.AI", "not-real"])
    assert invalid.value.code == "INVALID_CATEGORY"
    assert read_settings(tmp_path) == saved


def test_invalid_settings_do_not_silently_reset(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"revision": 2, "ui_language": "zh",
       "report_language": "zh", "custom_categories": ["made-up"]}), encoding="utf-8")
    with pytest.raises(AppError) as exc:
        read_settings(tmp_path)
    assert exc.value.code == "SETTINGS_INVALID"
