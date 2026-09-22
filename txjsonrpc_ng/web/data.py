from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CacheableResult:
    value: Any
    string_value: Optional[str] = None
    compressed_value: Optional[bytes] = None


