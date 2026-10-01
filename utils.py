"""Low level helpers: fixed length ASCII encoding, formatting, small utilities."""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

ASCII_MIN = 0x20
ASCII_MAX = 0x7E
ASCII_NULL = b"\x00"


class EncodingError(ValueError):
    """Raised when a value cannot be stored in a fixed length ASCII field."""


def is_ascii_text(value: str) -> bool:
    """Return True when every character is printable ASCII (0x20-0x7E)."""
    if value is None:
        return False
    return all(ASCII_MIN <= ord(ch) <= ASCII_MAX for ch in value)


def find_non_ascii_characters(value: str) -> list[str]:
    """Return the list of characters that are not printable ASCII."""
    if not value:
        return []
    return [ch for ch in value if not ASCII_MIN <= ord(ch) <= ASCII_MAX]


def encode_fixed_string(value: str, size: int) -> bytes:
    """Encode a string into exactly `size` bytes of NUL padded ASCII.

    Non printable ASCII is rejected with a clear error, oversized values are
    truncated safely to the field limit.
    """
    if size <= 0:
        raise EncodingError("field size must be positive")
    text = "" if value is None else str(value)
    bad = find_non_ascii_characters(text)
    if bad:
        raise EncodingError(
            "value contains non ASCII or control characters: "
            + ", ".join(repr(ch) for ch in bad[:5])
        )
    data = text.encode("ascii")
    if len(data) > size:
        data = data[:size]
    return data.ljust(size, ASCII_NULL)


def decode_fixed_string(value: bytes) -> str:
    """Decode a fixed length ASCII field, dropping trailing NUL padding."""
    if isinstance(value, str):
        value = value.encode("ascii", errors="replace")
    return value.split(ASCII_NULL, 1)[0].decode("ascii", errors="replace").strip()


def now_timestamp() -> int:
    """Return the current UNIX time in whole seconds (unsigned 64 bit)."""
    return int(time.time())


def format_timestamp(timestamp: int) -> str:
    """Format a stored UNIX timestamp as YYYY-MM-DD HH:MM:SS."""
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return str(timestamp)


def format_money(amount: float) -> str:
    """Format a price with thousands separators and two decimals."""
    return f"{float(amount):,.2f}"


def pad(value: object, width: int) -> str:
    """Right align `value` in a field of `width` characters."""
    text = "" if value is None else str(value)
    return text.ljust(width)[:width]


def rule(char: str = "-", width: int = 40) -> str:
    """Return a horizontal rule line."""
    return char * width


def ensure_directory(path: Path) -> Path:
    """Create `path` (and parents) when missing and return it."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_size(path: Path) -> int:
    """Return the size of a file in bytes, or 0 when it does not exist."""
    path = Path(path)
    return path.stat().st_size if path.exists() else 0


def flush_and_sync(handle) -> None:
    """Flush buffered writes and push them to the storage device."""
    handle.flush()
    try:
        os.fsync(handle.fileno())
    except (OSError, ValueError):
        pass


def round_price(value: float) -> float:
    """Round a price to cents and clamp it into the 32 bit float range."""
    price = round(float(value), 2)
    if price < 0:
        price = 0.0
    return price
