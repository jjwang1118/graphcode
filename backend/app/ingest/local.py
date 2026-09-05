"""本機路徑：檢查是否落在允許清單內，交出一個可安全走訪的根目錄。

規則見 docs/backend/ingest.md。
"""

import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.ingest.errors import IngestError

#: 允許清單的環境變數名。多筆以 os.pathsep 分隔。
ALLOWED_ROOTS_ENV = "CODEGRAPH_ALLOWED_ROOTS"


def allowed_roots_from_env(env: Mapping[str, str] | None = None) -> list[Path]:
    """從環境變數組出允許清單。未設定時回空清單，代表本機路徑模式停用。"""
    raw = (os.environ if env is None else env).get(ALLOWED_ROOTS_ENV, "")
    return [Path(part).resolve() for part in raw.split(os.pathsep) if part]


def from_local_path(raw_path: str, allowed_roots: Sequence[Path]) -> Path:
    """回傳可安全走訪的根目錄；不被允許時丟 `IngestError`。"""
    if not allowed_roots:
        raise IngestError(f"{ALLOWED_ROOTS_ENV} 未設定，本機路徑模式停用")

    root = Path(raw_path).resolve()
    # 先判斷在不在清單內，再判斷存不存在：否則錯誤訊息會變成探測工具。
    if not any(root.is_relative_to(allowed.resolve()) for allowed in allowed_roots):
        raise IngestError(f"路徑不在允許清單內：{root}")
    if not root.is_dir():
        raise IngestError(f"路徑不存在或不是目錄：{root}")
    return root
