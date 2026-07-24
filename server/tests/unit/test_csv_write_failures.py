import importlib.util
from pathlib import Path
from unittest import mock
from uuid import uuid4

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "module_path",
    [
        REPO_ROOT / "client" / "src" / "csv_writter.py",
        REPO_ROOT / "server" / "src" / "csv_writter.py",
    ],
)
def test_save_csv_reraises_file_error(module_path, tmp_path):
    spec = importlib.util.spec_from_file_location(
        f"csv_write_failure_{uuid4().hex}",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CSV_FILE = tmp_path / "output.csv"

    with (
        mock.patch("builtins.open", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        module.save_csv([["row"]])
