from __future__ import annotations

import json
from pathlib import Path

import pytest

from interview_guide.modules.knowledge_base.opentrek_seed import update_mapping_env_file


def test_update_mapping_env_file_preserves_other_values(tmp_path: Path) -> None:
    path = tmp_path / ".env.campus"
    path.write_text(
        "APP_COMPETITION_MODE=true\n"
        "APP_OPENTREK_KB_MAPPINGS_JSON='[]'\n"
        "POSTGRES_DB=interview_guide\n",
        encoding="utf-8",
    )

    update_mapping_env_file(path, "a" * 64, "kb-one")

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "APP_COMPETITION_MODE=true"
    assert lines[2] == "POSTGRES_DB=interview_guide"
    value = lines[1].split("=", 1)[1].strip("'")
    assert json.loads(value) == [{"fileHash": "a" * 64, "kbCode": "kb-one"}]


def test_update_mapping_env_file_rejects_conflict_without_replace(tmp_path: Path) -> None:
    path = tmp_path / ".env.campus"
    path.write_text(
        f"APP_OPENTREK_KB_MAPPINGS_JSON='{{\"{'a' * 64}\":\"kb-one\"}}'\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="--replace-mapping"):
        update_mapping_env_file(path, "a" * 64, "kb-two")

    update_mapping_env_file(path, "a" * 64, "kb-two", replace=True)
    assert "kb-two" in path.read_text(encoding="utf-8")


def test_update_mapping_env_file_refuses_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="拒绝自动创建"):
        update_mapping_env_file(tmp_path / ".env.campus", "a" * 64, "kb-one")
