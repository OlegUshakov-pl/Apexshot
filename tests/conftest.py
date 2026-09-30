from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="shot_test_")
os.environ["SHOT_DATA_DIR"] = _TMP

import app.database as database  # noqa: E402

database._fts_ok = None
database.init_db()
