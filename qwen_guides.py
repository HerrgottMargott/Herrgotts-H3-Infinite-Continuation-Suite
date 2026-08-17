"""Qwen-only guide input helpers for Herrgotts H3 Infinite v1.3.

This module deliberately has no ComfyUI imports so its ordering / dynamic-input
rules can be unit tested in isolation.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

MAX_QWEN_REFERENCES = 9
QWEN_REFERENCE_PREFIX = "qwen_reference_"
_QWEN_REFERENCE_RE = re.compile(r"^qwen_reference_([1-9][0-9]*)$")


def qwen_reference_index(name: str) -> int | None:
    """Return the 1-based Qwen reference index encoded in an input name."""
    match = _QWEN_REFERENCE_RE.match(str(name))
    if not match:
        return None
    index = int(match.group(1))
    if 1 <= index <= MAX_QWEN_REFERENCES:
        return index
    return None


class DynamicQwenReferenceInputs(dict):
    """V1 INPUT_TYPES mapping that recognizes JS-created Qwen image sockets.

    ComfyUI's V1 executor asks the input mapping whether an incoming prompt key
    is valid before it forwards that value to the node. The frontend only needs
    the first visible socket in object_info; later sockets are added on demand.
    This mapping therefore enumerates the static inputs normally while also
    recognizing qwen_reference_2 ... qwen_reference_9 at execution time.
    """

    def __init__(self, *args, tooltip: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._qwen_tooltip = tooltip or (
            "Optional Qwen-only image guide. It is shown to the MiniMax H3 text/vision "
            "encoder as the next <Picture N>, but is not inserted into minimax_refs and "
            "does not become a persistent Ref2VA/DiT reference latent."
        )

    def _dynamic_spec(self, key: str):
        index = qwen_reference_index(key)
        if index is None:
            raise KeyError(key)
        return (
            "IMAGE",
            {
                "tooltip": f"Qwen Reference {index}. {self._qwen_tooltip}",
            },
        )

    def __contains__(self, key: object) -> bool:
        if super().__contains__(key):
            return True
        return isinstance(key, str) and qwen_reference_index(key) is not None

    def __getitem__(self, key: str):
        try:
            return super().__getitem__(key)
        except KeyError:
            return self._dynamic_spec(key)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def collect_qwen_reference_entries(
    qwen_reference_1=None, dynamic_inputs: dict[str, Any] | None = None
) -> list[tuple[int, Any]]:
    """Collect connected Qwen references as ``(socket_index, image)`` pairs."""
    refs: dict[int, Any] = {}
    if qwen_reference_1 is not None:
        refs[1] = qwen_reference_1
    for name, value in (dynamic_inputs or {}).items():
        index = qwen_reference_index(name)
        if index is None or value is None:
            continue
        refs[index] = value
    return [(i, refs[i]) for i in sorted(refs)]


def collect_qwen_references(qwen_reference_1=None, dynamic_inputs: dict[str, Any] | None = None) -> list[Any]:
    """Collect connected Qwen reference images in numeric socket order."""
    return [
        image for _, image in collect_qwen_reference_entries(qwen_reference_1, dynamic_inputs)
    ]


def picture_roles(
    *, first_frame: bool, last_frame: bool, qwen_reference_count: int,
    qwen_reference_indices: Iterable[int] | None = None,
) -> list[str]:
    """Return the exact Qwen <Picture N> role order for v1.3."""
    roles: list[str] = []
    if first_frame:
        roles.append("First Frame")
    if last_frame:
        roles.append("Last Frame")
    indices = list(qwen_reference_indices or range(1, int(qwen_reference_count) + 1))
    roles.extend(f"Qwen Reference {int(i)}" for i in indices)
    return roles


def keyframe_mode(*, first_frame: bool, last_frame: bool) -> str:
    if first_frame and last_frame:
        return "FL2VA"
    if first_frame:
        return "I2VA"
    if last_frame:
        return "L2VA"
    return "T2VA"


def format_picture_map(
    *,
    first_frame: bool,
    last_frame: bool,
    qwen_reference_count: int,
    continuation: bool = False,
    qwen_reference_indices: Iterable[int] | None = None,
) -> str:
    roles = picture_roles(
        first_frame=first_frame,
        last_frame=last_frame,
        qwen_reference_count=qwen_reference_count,
        qwen_reference_indices=qwen_reference_indices,
    )
    if continuation:
        mode_line = "Qwen presentation for Continue"
    else:
        mode_line = f"H3 keyframe mode: {keyframe_mode(first_frame=first_frame, last_frame=last_frame)}"
    lines = [mode_line]
    if roles:
        lines.extend(f"Picture {i} = {role}" for i, role in enumerate(roles, start=1))
    else:
        lines.append("No <Picture N> inputs")
    if qwen_reference_count:
        lines.append(
            f"Qwen References: {qwen_reference_count} (Qwen-only; not minimax_refs / not native Ref2VA latents)"
        )
    if continuation:
        lines.append("Direct latent handover context is not a Qwen <Picture N> unless an image input is explicitly connected.")
    return "\n".join(lines)
