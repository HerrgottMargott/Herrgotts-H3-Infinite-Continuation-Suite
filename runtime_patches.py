"""Select the safe H3 continuation compatibility path on first Continue use."""

import logging
import threading

from . import patch_layout, patch_payload

_LOG = logging.getLogger("h3_continuous")
_LOCK = threading.RLock()
_RUNTIME_MODE = None


def _conflict_message(kind, status, err):
    if status is None:
        return f"{kind}: {err}"
    if status.state == "foreign":
        return f"{kind}: {status.owner} already owns {status.module}"
    return None


def get_h3_runtime_mode():
    """Detect the live ComfyUI H3 layout generation without modifying it."""
    mode, _, err = patch_layout.detect_layout_api()
    if err:
        raise RuntimeError(f"Herrgotts H3 Infinite could not identify the live MiniMax H3 API: {err}")
    return mode


def ensure_h3_runtime_patches():
    """Return ``legacy`` or ``native`` after installing only required hooks.

    Legacy ComfyUI requires both historical hooks. ComfyUI 0.33+ supplies
    arbitrary keyframes and keyframe/ref coexistence natively, so the payload
    monkey patch is skipped and the layout wrapper is restricted to the audio
    timeline correction used by direct AV-latent continuation.
    """
    global _RUNTIME_MODE
    with _LOCK:
        mode = get_h3_runtime_mode()
        if _RUNTIME_MODE is not None and _RUNTIME_MODE != mode:
            raise RuntimeError(
                f"h3_continuous: live H3 API changed from {_RUNTIME_MODE} to {mode}; restart ComfyUI"
            )

        layout_status, layout_err = patch_layout.get_layout_patch_status()
        payload_status, payload_err = patch_payload.get_payload_patch_status()

        # Even in native mode, do not quietly run under another chaining pack's
        # wrapper. It could rewrite the same layout/payload in incompatible ways.
        problems = [
            p for p in (
                _conflict_message("PackedLayout", layout_status, layout_err),
                _conflict_message("MiniMaxH3.extra_conds", payload_status, payload_err),
            ) if p
        ]
        if problems:
            detail = "; ".join(problems)
            raise RuntimeError(
                "Herrgotts H3 Infinite Continuation Suite cannot prepare its H3 runtime: "
                f"{detail}. Disable/remove the other H3 chaining pack, restart ComfyUI, then retry."
            )

        if mode == patch_layout.NATIVE_LAYOUT_MODE:
            # v0.33+: stock core now handles arbitrary keyframes and preserves
            # keyframes alongside refs. Keep MiniMaxH3.extra_conds completely stock.
            if patch_payload.is_applied():
                # This can only be our stale legacy wrapper in the same process.
                if not patch_payload.uninstall_payload_patch_if_owned():
                    raise RuntimeError(
                        "h3_continuous: legacy payload wrapper is still active but could not be removed; restart ComfyUI"
                    )
            if not patch_layout.install_layout_patch(mode=mode):
                raise RuntimeError(
                    "Herrgotts H3 Infinite Continuation Suite could not validate/install the ComfyUI 0.33+ "
                    "audio timeline compatibility wrapper. See the console self-test error."
                )
            _RUNTIME_MODE = mode
            _LOG.info(
                "h3_continuous v1.3.0: native ComfyUI H3 keyframe/ref path active; payload monkey patch not required"
            )
            return mode

        # Legacy path: preserve v1.2.1 behavior atomically.
        if patch_layout.is_applied() and patch_payload.is_applied():
            _RUNTIME_MODE = mode
            return mode

        payload_was_ours = payload_status is not None and payload_status.state == "ours"
        layout_was_ours = layout_status is not None and layout_status.state == "ours"

        if not patch_payload.install_payload_patch():
            raise RuntimeError(
                "Herrgotts H3 Infinite Continuation Suite could not install the legacy MiniMax H3 "
                "payload hook. See the ComfyUI console for the compatibility-check error."
            )
        if not patch_layout.install_layout_patch(mode=mode):
            if not payload_was_ours:
                patch_payload.uninstall_payload_patch_if_owned()
            raise RuntimeError(
                "Herrgotts H3 Infinite Continuation Suite could not install the legacy MiniMax H3 "
                "layout hook. The temporary payload hook was rolled back. See the ComfyUI console."
            )

        if not (patch_layout.is_applied() and patch_payload.is_applied()):
            if not layout_was_ours:
                patch_layout.uninstall_layout_patch_if_owned()
            if not payload_was_ours:
                patch_payload.uninstall_payload_patch_if_owned()
            raise RuntimeError("h3_continuous: legacy runtime hooks did not reach a consistent active state")

        _RUNTIME_MODE = mode
        _LOG.info(
            "h3_continuous v1.3.0: legacy H3 runtime hooks ready; unrelated H3 graphs remain on stock behavior"
        )
        return mode
