from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..schema import Reading


class BaseOutput(ABC):
    name: str = "base"

    def __init__(self, **options: Any):
        self.options = options

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    @abstractmethod
    async def write(self, reading: Reading) -> None:
        ...
