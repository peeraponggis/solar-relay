from __future__ import annotations

import json
import sys
from typing import Any

from ..schema import Reading
from .base import BaseOutput


class ConsoleOutput(BaseOutput):
    """Print each reading as one JSON line (used by --dry-run)."""

    name = "console"

    def __init__(self, compact: bool = True, **options: Any):
        super().__init__(**options)
        self.compact = compact

    async def write(self, reading: Reading) -> None:
        d = reading.to_dict()
        if self.compact:
            d = {k: v for k, v in d.items() if v not in (None, {}, [])}
        sys.stdout.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
