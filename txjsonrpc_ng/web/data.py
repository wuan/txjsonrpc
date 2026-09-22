from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CacheableResult:
    value: Any
    string_value: Optional[str] = None
    compressed_value: Optional[bytes] = None
    #: The ``(version, id)`` pair the cached ``string_value``/``compressed_value``
    #: were rendered for.  The serialized envelope embeds both, so a cached
    #: rendering may only be reused for a request carrying the same pair.
    render_key: Optional[tuple] = None


