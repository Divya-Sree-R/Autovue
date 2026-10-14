"""Optional hosting hooks. Local application behavior needs no cloud SDK."""
from collections.abc import Callable
from typing import Any

commit_storage: Callable[[], None] = lambda: None
dispatch_analysis: Callable[[str], dict[str, Any]] | None = None
