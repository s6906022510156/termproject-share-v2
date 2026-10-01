"""Reusable input validation helpers. Normal invalid input never crashes."""

from __future__ import annotations

import config
from utils import find_non_ascii_characters, is_ascii_text, round_price

MAX_ATTEMPTS = 10


class ValidationError(ValueError):
    """Raised when a value cannot be accepted after several attempts."""


def _reader(input_fn):
    return input if input_fn is None else input_fn


def read_line(prompt: str, input_fn=None) -> str:
    """Read one raw line and strip it.

    EOFError and KeyboardInterrupt are passed through so the application can
    shut down safely instead of treating them as invalid input.
    """
    return _reader(input_fn)(prompt).strip()


def read_int(
    prompt: str,
    input_fn=None,
    minimum: int = None,
    maximum: int = None,
    default: int = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> int:
    """Read an integer, re-prompting until it is valid or attempts run out."""
    label = prompt.strip().rstrip(":")
    for _ in range(max(1, max_attempts)):
        raw = read_line(prompt, input_fn)
        if not raw and default is not None:
            return int(default)
        try:
            value = int(raw, 10)
        except ValueError:
            print(f"  [!] '{raw}' is not a whole number. Please enter digits only.")
            continue
        if minimum is not None and value < minimum:
            print(f"  [!] Value must be >= {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"  [!] Value must be <= {maximum}.")
            continue
        return value
    raise ValidationError(f"too many invalid attempts for '{label}'")


def read_float(
    prompt: str,
    input_fn=None,
    minimum: float = None,
    maximum: float = None,
    default: float = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> float:
    """Read a float, re-prompting until it is valid or attempts run out."""
    label = prompt.strip().rstrip(":")
    for _ in range(max(1, max_attempts)):
        raw = read_line(prompt, input_fn)
        if not raw and default is not None:
            return float(default)
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            print(f"  [!] '{raw}' is not a number. Please enter a valid number.")
            continue
        if minimum is not None and value < minimum:
            print(f"  [!] Value must be >= {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"  [!] Value must be <= {maximum}.")
            continue
        return round_price(value)
    raise ValidationError(f"too many invalid attempts for '{label}'")


def read_non_empty(
    prompt: str,
    input_fn=None,
    max_length: int = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    """Read a non-empty, printable ASCII string (long input is truncated)."""
    label = prompt.strip().rstrip(":")
    for _ in range(max(1, max_attempts)):
        raw = read_line(prompt, input_fn)
        if not raw:
            print("  [!] This field is required and cannot be empty.")
            continue
        if not is_ascii_text(raw):
            bad = find_non_ascii_characters(raw)
            print(
                "  [!] Only printable ASCII characters are allowed "
                f"(rejected: {', '.join(repr(ch) for ch in bad[:5])})."
            )
            continue
        if max_length is not None and len(raw) > max_length:
            print(
                f"  [!] Input is longer than {max_length} characters; "
                f"stored as '{raw[:max_length]}'."
            )
            return raw[:max_length]
        return raw
    raise ValidationError(f"too many invalid attempts for '{label}'")


def read_optional(
    prompt: str,
    current: str,
    input_fn=None,
    max_length: int = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    """Read an optional value: an empty answer keeps `current`."""
    label = prompt.strip().rstrip(":")
    for _ in range(max(1, max_attempts)):
        raw = read_line(prompt, input_fn)
        if not raw:
            return current
        if not is_ascii_text(raw):
            bad = find_non_ascii_characters(raw)
            print(
                "  [!] Only printable ASCII characters are allowed "
                f"(rejected: {', '.join(repr(ch) for ch in bad[:5])})."
            )
            continue
        if max_length is not None and len(raw) > max_length:
            print(
                f"  [!] Input is longer than {max_length} characters; "
                f"stored as '{raw[:max_length]}'."
            )
            return raw[:max_length]
        return raw
    raise ValidationError(f"too many invalid attempts for '{label}'")


def read_choice(
    prompt: str,
    choices,
    input_fn=None,
    default: str = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    """Read a menu choice restricted to `choices`."""
    valid = {str(choice).lower() for choice in choices}
    for _ in range(max(1, max_attempts)):
        raw = read_line(prompt, input_fn).lower()
        if not raw and default is not None:
            return str(default)
        if raw in valid:
            return raw
        print(f"  [!] '{raw}' is not one of: {', '.join(str(c) for c in choices)}")
    raise ValidationError("too many invalid menu choices")


def read_yes_no(prompt: str, input_fn=None, max_attempts: int = MAX_ATTEMPTS) -> bool:
    """Read a y/n confirmation."""
    for _ in range(max(1, max_attempts)):
        raw = read_line(prompt, input_fn).lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  [!] Please answer 'y' or 'n'.")
    raise ValidationError("too many invalid confirmation answers")


def validate_equipment_id(raw, existing_ids=()) -> int:
    """Validate an equipment id: numeric, positive, not duplicated."""
    if isinstance(raw, bool):
        raise ValidationError("equipment id must be a number")
    if isinstance(raw, int):
        value = raw
    else:
        text = str(raw).strip()
        if not text:
            raise ValidationError("equipment id is required")
        try:
            value = int(text, 10)
        except ValueError:
            raise ValidationError(f"'{raw}' is not a valid equipment id (digits only)")
    if value < config.ID_MIN:
        raise ValidationError("equipment id must be a positive number")
    if value > config.ID_MAX:
        raise ValidationError("equipment id is too large for the record format")
    if existing_ids and value in {int(item) for item in existing_ids}:
        raise ValidationError(f"equipment id {value} already exists")
    return value


def validate_category_id(raw, allowed_ids) -> int:
    """Validate a category id against the known category ids."""
    try:
        value = int(str(raw).strip(), 10)
    except (TypeError, ValueError):
        raise ValidationError(f"'{raw}' is not a valid category id (digits only)")
    if value not in {int(item) for item in allowed_ids}:
        names = ", ".join(str(item) for item in sorted(allowed_ids)) or "none"
        raise ValidationError(
            f"category {value} does not exist (available: {names})"
        )
    return value


def validate_price(raw) -> float:
    """Validate a price: numeric, not negative, inside the 32 bit float range."""
    if isinstance(raw, bool):
        raise ValidationError("price must be a number")
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip()
        if not text:
            raise ValidationError("price is required")
        try:
            value = float(text.replace(",", ""))
        except ValueError:
            raise ValidationError(f"'{raw}' is not a valid price")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValidationError("price must be a finite number")
    if value < config.PRICE_MIN:
        raise ValidationError("price cannot be negative")
    if value > config.PRICE_MAX:
        raise ValidationError(f"price cannot exceed {config.PRICE_MAX:,.2f}")
    return round_price(value)


def validate_status(raw) -> int:
    """Validate an equipment status code."""
    try:
        value = int(str(raw).strip(), 10)
    except (TypeError, ValueError):
        raise ValidationError(f"'{raw}' is not a valid status code")
    if value not in config.STATUS_NAMES:
        allowed = ", ".join(str(code) for code in sorted(config.STATUS_NAMES))
        raise ValidationError(f"status must be one of: {allowed}")
    if value == config.STATUS_FREE:
        raise ValidationError("status 0 (Free) is reserved for deleted records")
    return value


def validate_fixed_text(raw, field: str) -> str:
    """Validate a fixed length ASCII field value, truncating when too long."""
    text = "" if raw is None else str(raw).strip()
    if not text:
        raise ValidationError(f"{field} cannot be empty")
    if not is_ascii_text(text):
        bad = find_non_ascii_characters(text)
        raise ValidationError(
            f"{field} contains unsupported characters: "
            + ", ".join(repr(ch) for ch in bad[:5])
        )
    size = config.FIELD_SIZES.get(field)
    if size is not None and len(text) > size:
        return text[:size]
    return text


def validate_integer_field(raw, field: str, minimum: int, maximum: int) -> int:
    """Validate any unsigned 32 bit integer field."""
    try:
        value = int(str(raw).strip(), 10)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a whole number")
    if value < minimum:
        raise ValidationError(f"{field} must be >= {minimum}")
    if value > maximum:
        raise ValidationError(f"{field} must be <= {maximum}")
    return value
