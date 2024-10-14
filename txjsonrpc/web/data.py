from dataclasses import dataclass
from typing import Union, Dict, List, Optional


@dataclass
class CacheableResult:
    value: Union[Dict, List]
    string_value: Optional[str] = None
    compressed_value: Optional[bytes] = None


