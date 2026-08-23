import pytest

from jetlinks_ai_api.chat_payload_utils import (
    infer_attachment_kind,
    safe_load_attachments,
    safe_outputs_path,
    truncate_title,
)
from jetlinks_ai_api.env_utils import env_bool, env_int, env_str


def test_env_str_prefers_new_prefix(monkeypatch):
    # 验证新前缀环境变量优先于旧前缀
    monkeypatch.setenv("JETLINKS_AI_TEST_VALUE", "new")
    monkeypatch.setenv("AISTAFF_TEST_VALUE", "legacy")
    assert env_str("TEST_VALUE") == "new"


def test_env_str_falls_back_to_legacy_prefix(monkeypatch):
    # 验证仅设置旧前缀时使用旧值
    monkeypatch.setenv("AISTAFF_TEST_VALUE", "legacy")
    assert env_str("TEST_VALUE") == "legacy"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("  spaced  ", "spaced"),
        ("", "fallback"),
        ("   ", "fallback"),
    ],
)
def test_env_str_normalizes_value(monkeypatch, raw_value, expected):
    # 验证环境变量会去除首尾空白且空值回退默认值
    monkeypatch.setenv("JETLINKS_AI_TEST_VALUE", raw_value)
    assert env_str("TEST_VALUE", "fallback") == expected


def test_env_str_returns_default_when_unset(monkeypatch):
    # 验证未设置环境变量时返回默认值
    monkeypatch.delenv("JETLINKS_AI_TEST_VALUE", raising=False)
    monkeypatch.delenv("AISTAFF_TEST_VALUE", raising=False)
    assert env_str("TEST_VALUE", "fallback") == "fallback"


@pytest.mark.parametrize(
    ("raw_value", "default", "expected"),
    [
        ("1", False, True),
        (" TRUE ", False, True),
        ("yes", False, True),
        ("On", False, True),
        ("0", True, False),
        ("false", True, False),
        ("NO", True, False),
        ("off", True, False),
        ("unknown", True, True),
        ("unknown", False, False),
    ],
)
def test_env_bool_parses_values(monkeypatch, raw_value, default, expected):
    # 验证布尔环境变量的常见取值和无效取值回退
    monkeypatch.setenv("JETLINKS_AI_TEST_VALUE", raw_value)
    assert env_bool("TEST_VALUE", default) is expected


def test_env_bool_returns_default_when_unset(monkeypatch):
    # 验证未设置布尔环境变量时返回默认值
    monkeypatch.delenv("JETLINKS_AI_TEST_VALUE", raising=False)
    monkeypatch.delenv("AISTAFF_TEST_VALUE", raising=False)
    assert env_bool("TEST_VALUE", True) is True


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [("42", 42), ("invalid", 7), ("  18  ", 18)],
)
def test_env_int_parses_values(monkeypatch, raw_value, expected):
    # 验证整数环境变量支持合法解析和无效值回退
    monkeypatch.setenv("JETLINKS_AI_TEST_VALUE", raw_value)
    assert env_int("TEST_VALUE", 7) == expected


def test_safe_outputs_path_accepts_valid_file_id(tmp_path):
    # 验证合法文件标识会解析到输出目录内
    assert safe_outputs_path(tmp_path, "report_2026.txt") == tmp_path.resolve() / "report_2026.txt"


@pytest.mark.parametrize("file_id", ["bad/id", "..", "", "   "])
def test_safe_outputs_path_rejects_invalid_file_id(tmp_path, file_id):
    # 验证非法字符、路径穿越、空值和空白文件标识被拒绝
    with pytest.raises(ValueError, match="invalid file_id"):
        safe_outputs_path(tmp_path, file_id)


def test_truncate_title_normalizes_and_truncates():
    # 验证标题归一化空白并按最大长度截断
    assert truncate_title("  Alpha\n Beta ", 12) == "Alpha Beta"


@pytest.mark.parametrize(
    ("attachment", "expected"),
    [
        ({"kind": "Image"}, "image"),
        ({"type": "FILE"}, "file"),
        ({"content_type": "image/png"}, "image"),
        ({"file_id": "photo.JPG"}, "image"),
        ({"file_id": "document.pdf"}, "file"),
    ],
)
def test_infer_attachment_kind(attachment, expected):
    # 验证附件类型按显式类型、MIME 和图片扩展名推断
    assert infer_attachment_kind(attachment) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, []),
        ([{"id": "1"}, "invalid", {"id": "2"}], [{"id": "1"}, {"id": "2"}]),
        ('[{"id": "1"}, null]', [{"id": "1"}]),
        ('{"id": "1"}', []),
        ("invalid-json", []),
        ({"id": "1"}, []),
    ],
)
def test_safe_load_attachments(value, expected):
    # 验证附件载荷解析仅保留列表中的字典项
    assert safe_load_attachments(value) == expected
