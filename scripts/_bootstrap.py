from __future__ import annotations

from pathlib import Path
import sys


def ensure_project_root_on_path(current_file: str) -> None:
    project_root = Path(current_file).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
