"""Recursive PII walker shared by COPPA / privacy invariant tests.

This module is a generic utility — it has no dependence on FastAPI, the
project's domain, or any specific data shape. It walks an arbitrary
JSON-decoded payload (dicts, lists, scalars) and asserts that:

  1. No dictionary key (compared case-insensitively) appears in the
     ``forbidden_keys`` set.
  2. No string value contains any substring from ``forbidden_strings``
     (case-sensitive — these are typically canary tokens deliberately
     planted in test fixtures).

On the first violation, an ``AssertionError`` is raised with a JSONPath
locator to make failures easy to diagnose.
"""

from __future__ import annotations

from typing import Any, Iterable


def assert_no_pii(
    payload: Any,
    *,
    forbidden_keys: Iterable[str],
    forbidden_strings: Iterable[str],
    path: str = "$",
) -> None:
    """Walk ``payload`` recursively and raise on any forbidden key or substring.

    Args:
        payload: JSON-decoded value (dict, list, or scalar).
        forbidden_keys: Keys that must never appear at any depth. Comparison
            is case-insensitive, so ``user_id`` blocks ``User_ID`` and
            ``userId`` alike.
        forbidden_strings: Substrings (case-sensitive) that must never appear
            inside any string value at any depth. Used for canary tokens.
        path: JSONPath of the current node — used to build informative
            error messages. Callers normally leave this at the default.

    Raises:
        AssertionError: With a JSONPath pointing at the violating node.
    """
    forbidden_keys_lower = {key.lower() for key in forbidden_keys}
    forbidden_strings_set = set(forbidden_strings)

    _walk(
        payload,
        forbidden_keys_lower=forbidden_keys_lower,
        forbidden_strings=forbidden_strings_set,
        path=path,
    )


def _walk(
    node: Any,
    *,
    forbidden_keys_lower: set[str],
    forbidden_strings: set[str],
    path: str,
) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            key_str = str(key)
            if key_str.lower() in forbidden_keys_lower:
                raise AssertionError(
                    f"Forbidden user-table key '{key_str}' found at "
                    f"{path}.{key_str} — hub responses must never expose "
                    f"users-table fields (COPPA invariant)."
                )
            child_path = f"{path}.{key_str}"
            _walk(
                value,
                forbidden_keys_lower=forbidden_keys_lower,
                forbidden_strings=forbidden_strings,
                path=child_path,
            )
    elif isinstance(node, list):
        for index, item in enumerate(node):
            child_path = f"{path}[{index}]"
            _walk(
                item,
                forbidden_keys_lower=forbidden_keys_lower,
                forbidden_strings=forbidden_strings,
                path=child_path,
            )
    elif isinstance(node, str):
        for needle in forbidden_strings:
            if needle and needle in node:
                raise AssertionError(
                    f"Forbidden canary substring '{needle}' found in "
                    f"string value at {path} — a users-table value leaked "
                    f"into the hub response (COPPA invariant)."
                )
