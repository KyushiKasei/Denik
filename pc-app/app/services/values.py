"""JSON hodnoty polí ve source_values a overrides."""

from __future__ import annotations

import json
from typing import Any


def encode_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def decode_value(text: str | None) -> Any:
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def values_equal(left: Any, right: Any) -> bool:
    if left is None and right is None:
        return True
    if isinstance(left, float) and isinstance(right, (int, float)):
        return abs(left - float(right)) < 1e-6
    if isinstance(right, float) and isinstance(left, (int, float)):
        return abs(float(left) - right) < 1e-6
    if isinstance(left, list) and isinstance(right, list):
        return [json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) for item in left] == [
            json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) for item in right
        ]
    return left == right
