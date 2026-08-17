"""Lazy MiniMax H3 layout compatibility for direct AV continuation.

ComfyUI <= 0.32 needs the historical Herrgotts layout wrapper for interior
keyframes *and* timeline-pinned continuation audio.  ComfyUI 0.33 introduced
native arbitrary H3 keyframe anchors and removed ``frame_count`` from
``PackedLayout.__init__``.  On that API we leave keyframe placement entirely to
stock ComfyUI and install only the small marker-gated audio-coordinate fix that
is still required for backward-looking direct audio continuation.

Nothing is patched at import time.  The wrapper is installed only on first
Continue use and unrelated H3 graphs remain on the exact stock path.
"""

import inspect
import logging

from .patch_utils import classify_callable

HC_INDEX = "h3_continuous_index"
HC_AUDIO_END_FRAME = "h3_continuous_audio_end_frame"
LAYOUT_PATCH_MARKER = "_herrgotts_h3_infinite_layout_patch"

LEGACY_LAYOUT_MODE = "legacy"
NATIVE_LAYOUT_MODE = "native"

_LOG = logging.getLogger("h3_continuous")
_ORIGINAL_INIT = None
_INSTALLED_WRAPPER = None
_APPLIED = False
_APPLIED_MODE = None
_MM = None

_KNOWN_EXTERNAL_MARKERS = (
    ("_h3_motion_context_layout_patch", "ComfyUI-H3-Motion-Context"),
)


def _import_mm():
    import comfy.ldm.minimax.model as mm
    return mm


def get_layout_patch_status():
    try:
        mm = _import_mm()
    except Exception as exc:
        return None, f"cannot import comfy.ldm.minimax.model: {exc}"
    cls = getattr(mm, "PackedLayout", None)
    fn = getattr(cls, "__init__", None) if cls is not None else None
    if cls is None or fn is None:
        return None, "ComfyUI PackedLayout.__init__ is unavailable"
    status = classify_callable(cls, fn, LAYOUT_PATCH_MARKER, _KNOWN_EXTERNAL_MARKERS)
    return status, None


def detect_layout_api():
    """Return ``(mode, signature, error)`` for the live ComfyUI H3 layout API.

    ``legacy`` means the old constructor still exposes ``frame_count`` and needs
    the interior-keyframe workaround. ``native`` means ``frame_count`` is gone
    while named keyframe/reference inputs remain, matching ComfyUI 0.33's public
    arbitrary-keyframe layout.
    """
    try:
        mm = _import_mm()
        fn = mm.PackedLayout.__init__
    except Exception as exc:
        return None, None, f"cannot import PackedLayout.__init__: {exc}"

    # If our marker-gated wrapper is already live, do not re-detect the stock
    # constructor from the wrapper's generic (*args, **kwargs) call signature.
    # This is the normal state on Clip 3+ in the same ComfyUI process.
    wrapped_mode = getattr(fn, "_herrgotts_h3_layout_mode", None)
    if getattr(fn, LAYOUT_PATCH_MARKER, False) and wrapped_mode in (LEGACY_LAYOUT_MODE, NATIVE_LAYOUT_MODE):
        try:
            sig = inspect.signature(fn)
        except Exception:
            sig = None
        return wrapped_mode, sig, None

    try:
        sig = inspect.signature(fn)
    except Exception as exc:
        return None, None, f"cannot inspect PackedLayout.__init__: {exc}"

    names = set(sig.parameters)
    common = {"text_len", "latent_t", "latent_h", "latent_w", "audio_t", "keyframes", "refs"}
    missing = common - names
    if missing:
        return None, sig, f"PackedLayout.__init__ is missing expected parameters {sorted(missing)}"
    if "frame_count" in names:
        return LEGACY_LAYOUT_MODE, sig, None
    return NATIVE_LAYOUT_MODE, sig, None


def _ref_cursor_advance(mm, refs):
    if not refs:
        return 0.0
    cursor = 0.0
    for blk in refs:
        kind = blk.get("kind")
        if kind == "image":
            cursor += 1.0
        elif kind == "audio":
            cursor += float(blk.get("ref_audio_t", 0))
        elif kind in ("video", "video_audio"):
            rt = float(blk.get("ref_audio_t", 0))
            vt = int(blk.get("latent_t", 0))
            cursor += max(rt, sum(mm._video_t_spans(vt)))
    return cursor


def _cond_t(mm, text_len, latent_t, frame_count, p):
    p = float(p)
    if p == 0.0:
        return float(text_len)
    if frame_count is not None and p == float(frame_count - 1):
        return float(text_len) + sum(mm._video_t_spans(latent_t)) - mm.FRAME_RESCALE
    return float(text_len) + mm.FRAME_RESCALE * p


def _fix_keyframes_legacy(mm, layout, text_len, latent_t, frame_count, keyframes, refs):
    """Move only Herrgotts-marked keyframes onto the target timeline (legacy API)."""
    offset = _ref_cursor_advance(mm, refs)
    cond_spans = [(a, b) for a, b, kind in layout.segments if kind == "cond"]
    if len(cond_spans) != len(keyframes):
        raise RuntimeError(
            "h3_continuous: PackedLayout cond segment count changed; refusing unsafe continuation"
        )
    for (a, b), kf in zip(cond_spans, keyframes):
        if HC_INDEX not in kf:
            continue
        p = kf[HC_INDEX]
        layout.position_ids[a:b, 0] = _cond_t(mm, text_len, latent_t, frame_count, p) + offset


def _rows_for_segment(layout, kind):
    """Return absolute packed-row indices for a named legacy segment if present."""
    import torch

    rows = []
    for item in getattr(layout, "segments", ()) or ():
        if not isinstance(item, (tuple, list)) or len(item) < 3:
            continue
        a, b, k = item[:3]
        if k == kind:
            rows.extend(range(int(a), int(b)))
    if not rows:
        return None
    return torch.as_tensor(rows, dtype=torch.long)


def _rows_from_update_map(layout, pos_name, update_name, want_update):
    """Resolve absolute packed rows from ComfyUI's modality update maps.

    ComfyUI 0.33 changed the H3 layout internals used for guide placement.  The
    durable information the model still needs is the mapping from image/audio
    modality rows into the packed sequence plus a boolean telling which rows are
    target (updated) versus conditioning/reference (pinned).  Prefer that public
    execution data whenever the old ``segments`` labels are absent.
    """
    import torch

    pos = getattr(layout, pos_name, None)
    update = getattr(layout, update_name, None)
    if pos is None or update is None:
        return None
    try:
        pos = torch.as_tensor(pos, dtype=torch.long).reshape(-1)
        update = torch.as_tensor(update, dtype=torch.bool).reshape(-1)
    except Exception:
        return None
    if pos.numel() != update.numel():
        return None
    rows = pos[update if want_update else ~update]
    return rows if rows.numel() else None


def _target_video_rows(layout):
    rows = _rows_for_segment(layout, "video")
    if rows is not None:
        return rows
    return _rows_from_update_map(layout, "img_pos", "img_update", True)


def _conditioning_image_rows(layout):
    rows = _rows_for_segment(layout, "cond")
    if rows is not None:
        return rows
    return _rows_from_update_map(layout, "img_pos", "img_update", False)


def _reference_audio_rows(layout, expected_rt=None):
    """Return the first reference-audio block's packed rows.

    Herrgotts continuation supplies its direct audio context as the first and
    only MiniMax audio reference.  When named segments are unavailable, all
    non-updated audio rows are reference rows; selecting the first ``rt*2`` rows
    therefore recovers exactly our stereo context block while remaining
    independent of the concrete PackedLayout segment representation.
    """
    rows = _rows_for_segment(layout, "ref_audio")
    if rows is None:
        rows = _rows_from_update_map(layout, "audio_pos", "audio_update", False)
    if rows is None:
        return None
    if expected_rt is not None:
        need = max(0, int(expected_rt)) * 2
        if need and int(rows.numel()) >= need:
            rows = rows[:need]
    return rows


def _layout_same(a, b):
    """Compare execution-relevant layout state without depending on one schema."""
    import torch

    pa = getattr(a, "position_ids", None)
    pb = getattr(b, "position_ids", None)
    if pa is None or pb is None or not torch.equal(pa, pb):
        return False
    for name in ("img_pos", "img_update", "audio_pos", "audio_update"):
        xa, xb = getattr(a, name, None), getattr(b, name, None)
        if (xa is None) != (xb is None):
            return False
        if xa is not None:
            try:
                if not torch.equal(torch.as_tensor(xa), torch.as_tensor(xb)):
                    return False
            except Exception:
                if xa != xb:
                    return False
    sa, sb = getattr(a, "segments", None), getattr(b, "segments", None)
    if sa is not None or sb is not None:
        if sa != sb:
            return False
    return True


def _audio_ref_slot_rows(layout, text_len, rt):
    """Resolve the stock reference-audio rows by their original time slot.

    ComfyUI 0.33 changed the concrete PackedLayout helper structures
    (``segments``, ``audio_pos``/``audio_update`` and friends).  The stable
    contract we actually need is simpler: before any Herrgotts rewrite, an
    audio reference of ``rt`` latent steps occupies the half-open time slot
    ``[text_len, text_len + rt)``.  Select that slot directly from
    ``position_ids`` instead of depending on private row-index containers.

    Native 0.33 also compensates keyframe positions for references, so native
    keyframe rows live on the target timeline after the reference cursor and do
    not alias this slot.  Legacy mode keeps its explicit cond-segment exclusion
    as an extra guard.
    """
    import torch

    t = layout.position_ids[:, 0]
    sel = (t >= float(text_len) - 1e-4) & (t < float(text_len) + float(rt) - 1e-4)

    # On the legacy layout a first-frame cond row can share text_len.  Never
    # allow it to be swept into the audio rewrite.  New 0.33 layouts no longer
    # expose the same tuple segment schema, and their native ref compensation
    # puts keyframe rows after the reference cursor anyway.
    for item in getattr(layout, "segments", ()) or ():
        if not isinstance(item, (tuple, list)) or len(item) < 3:
            continue
        a, b, kind = item[:3]
        if kind == "cond":
            sel[int(a):int(b)] = False

    rows = torch.nonzero(sel, as_tuple=False).flatten()
    return rows


def _fix_audio(mm, layout, text_len, refs):
    """Put the marked direct-audio tail on the new clip's own timeline.

    This path intentionally depends only on ``position_ids`` plus ComfyUI's
    reference cursor arithmetic.  It therefore survives the PackedLayout
    container refactor in ComfyUI 0.33 while leaving all stock row construction,
    ordering and non-time coordinates untouched.
    """
    marked = [(i, r) for i, r in enumerate(refs or []) if HC_AUDIO_END_FRAME in r]
    if not marked:
        return
    if len(marked) != 1:
        raise RuntimeError("h3_continuous: exactly one timeline audio context block is supported")
    ref_index, blk = marked[0]
    if ref_index != 0 or blk.get("kind") != "audio":
        raise RuntimeError(
            "h3_continuous: timeline audio context must be the first H3 ref block"
        )
    rt = int(blk.get("ref_audio_t", 0))
    if rt <= 0:
        return

    rows = _audio_ref_slot_rows(layout, text_len, rt)
    count = int(rows.numel())
    # H3 currently has two audio rows per latent step.  Keep a wider sanity
    # band so a harmless upstream packing-factor change fails only when the
    # selected slot is clearly not an audio block.
    if count < rt or count > 8 * rt:
        raise RuntimeError(
            f"h3_continuous: found {count} rows in the {rt}-step reference-audio slot; "
            f"expected between {rt} and {8 * rt}. Upstream H3 layout changed; refusing unsafe audio placement"
        )

    t = layout.position_ids[:, 0]
    current_end = float(t[rows].max()) + 1.0
    target_origin = float(text_len) + _ref_cursor_advance(mm, refs)
    desired_end = target_origin + mm.FRAME_RESCALE * float(blk[HC_AUDIO_END_FRAME])
    layout.position_ids[rows, 0] = t[rows] + (desired_end - current_end)

def _call_layout(original_init, obj, text_len, latent_t, lh, lw, audio_t, *, keyframes=None, refs=None, frame_count=None, mode):
    kwargs = {"keyframes": keyframes, "refs": refs}
    if mode == LEGACY_LAYOUT_MODE:
        kwargs["frame_count"] = frame_count
    return original_init(obj, text_len, latent_t, lh, lw, audio_t, **kwargs)


def _run_legacy_self_test(mm, original_init, patched_init):
    import torch

    text_len, latent_t, lh, lw, audio_t = 7, 7, 22, 38, 16
    frame_count = sum(mm.FRAME_PER_TOKEN[k % 5] for k in range(latent_t))

    stock_kf = [{"resolved_frame_index": 0}, {"resolved_frame_index": frame_count - 1}]
    custom_kf = [
        {"resolved_frame_index": 0, HC_INDEX: 0},
        {"resolved_frame_index": 0, HC_INDEX: frame_count - 1},
    ]
    s = mm.PackedLayout.__new__(mm.PackedLayout)
    _call_layout(original_init, s, text_len, latent_t, lh, lw, audio_t,
                 keyframes=stock_kf, frame_count=frame_count, mode=LEGACY_LAYOUT_MODE)
    c = mm.PackedLayout.__new__(mm.PackedLayout)
    _call_layout(original_init, c, text_len, latent_t, lh, lw, audio_t,
                 keyframes=custom_kf, frame_count=frame_count, mode=LEGACY_LAYOUT_MODE)
    _fix_keyframes_legacy(mm, c, text_len, latent_t, frame_count, custom_kf, None)
    if not torch.equal(s.position_ids, c.position_ids):
        raise RuntimeError("custom endpoint positions differ from stock H3")

    canonical = [
        {"resolved_frame_index": 0, HC_INDEX: p}
        for p in (0, 1, 5, 9, 13, 17, 18, 22)
    ]
    cr = mm.PackedLayout.__new__(mm.PackedLayout)
    _call_layout(original_init, cr, text_len, latent_t, lh, lw, audio_t,
                 keyframes=canonical, frame_count=frame_count, mode=LEGACY_LAYOUT_MODE)
    _fix_keyframes_legacy(mm, cr, text_len, latent_t, frame_count, canonical, None)
    cond_rows = _conditioning_image_rows(cr)
    if cond_rows is None:
        raise RuntimeError("legacy H3 layout exposed no conditioning image rows")
    frame_rows = int(cond_rows.numel()) // len(canonical)
    cts = [float(cr.position_ids[int(cond_rows[i * frame_rows]), 0]) for i in range(len(canonical))]
    expected_cts = [float(text_len) + mm.FRAME_RESCALE * p for p in (0, 1, 5, 9, 13, 17, 18, 22)]
    if any(abs(a - b) > 1e-9 for a, b in zip(cts, expected_cts)):
        raise RuntimeError("canonical phase-aligned keyframe times changed")

    # Isolation: an unmarked stock graph must be byte-for-byte layout-identical.
    unrelated_kf = [{"resolved_frame_index": frame_count - 1}]
    unrelated_refs = [{"kind": "audio", "ref_audio_t": 5}]
    a = mm.PackedLayout.__new__(mm.PackedLayout)
    _call_layout(original_init, a, text_len, latent_t, lh, lw, audio_t,
                 keyframes=unrelated_kf, refs=unrelated_refs, frame_count=frame_count, mode=LEGACY_LAYOUT_MODE)
    b = mm.PackedLayout.__new__(mm.PackedLayout)
    patched_init(b, text_len, latent_t, lh, lw, audio_t,
                 keyframes=unrelated_kf, refs=unrelated_refs, frame_count=frame_count)
    if not _layout_same(a, b):
        raise RuntimeError("unmarked H3 graph changed under the continuation layout wrapper")


def _run_native_self_test(mm, original_init, patched_init):
    """Validate the ComfyUI 0.33+ native path without private schema guesses.

    0.33 is considered native only if stock accepts an interior keyframe.  The
    audio test then proves that our wrapper changes exactly the rows occupying
    the stock reference-audio coordinate slot, by one uniform time translation,
    while every other coordinate remains byte-identical.
    """
    import torch

    text_len, latent_t, lh, lw, audio_t = 7, 7, 22, 38, 16
    interior = [{"resolved_frame_index": 5}]

    # The defining 0.33 capability: arbitrary interior keyframes are accepted by
    # stock ComfyUI.  We deliberately do not inspect its private segment/maps.
    stock = mm.PackedLayout.__new__(mm.PackedLayout)
    _call_layout(original_init, stock, text_len, latent_t, lh, lw, audio_t,
                 keyframes=interior, mode=NATIVE_LAYOUT_MODE)
    if getattr(stock, "position_ids", None) is None:
        raise RuntimeError("native H3 layout produced no position_ids")

    rt = 11
    end_frame = 5.0
    marked_refs = [{"kind": "audio", "ref_audio_t": rt, HC_AUDIO_END_FRAME: end_frame}]

    before = mm.PackedLayout.__new__(mm.PackedLayout)
    _call_layout(original_init, before, text_len, latent_t, lh, lw, audio_t,
                 keyframes=interior, refs=marked_refs, mode=NATIVE_LAYOUT_MODE)
    after = mm.PackedLayout.__new__(mm.PackedLayout)
    patched_init(after, text_len, latent_t, lh, lw, audio_t,
                 keyframes=interior, refs=marked_refs)

    if before.position_ids.shape != after.position_ids.shape:
        raise RuntimeError("audio timeline wrapper changed the packed layout shape")
    if not torch.equal(before.position_ids[:, 1:], after.position_ids[:, 1:]):
        raise RuntimeError("audio timeline wrapper touched a non-time coordinate column")

    rows = _audio_ref_slot_rows(before, text_len, rt)
    count = int(rows.numel())
    if count < rt or count > 8 * rt:
        raise RuntimeError(
            f"native H3 reference-audio slot resolved to {count} rows for {rt} steps; "
            "cannot validate safe timeline placement"
        )

    tb = before.position_ids[:, 0]
    ta = after.position_ids[:, 0]
    changed = torch.nonzero(tb != ta, as_tuple=False).flatten()
    if not torch.equal(changed.cpu(), rows.cpu()):
        raise RuntimeError(
            f"audio timeline wrapper moved unexpected rows (moved {int(changed.numel())}, expected {count})"
        )
    deltas = ta[rows] - tb[rows]
    if deltas.numel() == 0 or not torch.allclose(deltas, torch.full_like(deltas, deltas[0]), atol=1e-7, rtol=0):
        raise RuntimeError("reference-audio rows were not translated by one uniform offset")

    desired_end = float(text_len) + _ref_cursor_advance(mm, marked_refs) + mm.FRAME_RESCALE * end_frame
    actual_end = float(ta[rows].max()) + 1.0
    if abs(actual_end - desired_end) > 1e-6:
        raise RuntimeError(
            f"timeline audio alignment changed (got end {actual_end}, expected {desired_end})"
        )

    # Unmarked graph must remain exactly stock under the wrapper.
    normal_refs = [{"kind": "audio", "ref_audio_t": 5}]
    a = mm.PackedLayout.__new__(mm.PackedLayout)
    _call_layout(original_init, a, text_len, latent_t, lh, lw, audio_t,
                 keyframes=interior, refs=normal_refs, mode=NATIVE_LAYOUT_MODE)
    b = mm.PackedLayout.__new__(mm.PackedLayout)
    patched_init(b, text_len, latent_t, lh, lw, audio_t,
                 keyframes=interior, refs=normal_refs)
    if not _layout_same(a, b):
        raise RuntimeError("unmarked native H3 graph changed under the audio layout wrapper")

def install_layout_patch(mode=None):
    global _ORIGINAL_INIT, _INSTALLED_WRAPPER, _APPLIED, _APPLIED_MODE, _MM
    if _APPLIED:
        if mode is None or mode == _APPLIED_MODE:
            return True
        _LOG.error(
            "h3_continuous: H3 layout API mode changed from %s to %s while ComfyUI is running; restart required",
            _APPLIED_MODE, mode,
        )
        return False

    detected, sig, api_err = detect_layout_api()
    if api_err:
        _LOG.error("h3_continuous: layout API compatibility check FAILED (%s)", api_err)
        return False
    if mode is None:
        mode = detected
    elif mode != detected:
        _LOG.error("h3_continuous: requested layout mode %s but live API is %s", mode, detected)
        return False

    status, err = get_layout_patch_status()
    if status is None:
        _LOG.error("h3_continuous: layout patch unavailable: %s", err)
        return False
    if status.state == "ours":
        _APPLIED = True
        _APPLIED_MODE = mode
        _LOG.info("h3_continuous: compatible Herrgotts H3 layout wrapper is already active")
        return True
    if status.state == "foreign":
        _LOG.error(
            "h3_continuous: H3 runtime-patch conflict: %s already owns "
            "PackedLayout.__init__ (%s). Disable one H3 chaining pack and restart ComfyUI.",
            status.owner, status.module,
        )
        return False

    mm = _import_mm()
    original_init = mm.PackedLayout.__init__

    def patched_init(self, *args, **kwargs):
        # Forward verbatim. This is intentionally resilient to optional upstream
        # additions and lets the live signature do the argument validation.
        original_init(self, *args, **kwargs)
        try:
            bound = sig.bind(self, *args, **kwargs)
            bound.apply_defaults()
            ba = bound.arguments
        except TypeError as exc:
            raise RuntimeError(f"h3_continuous: could not bind live PackedLayout arguments: {exc}") from exc

        keyframes = ba.get("keyframes")
        refs = ba.get("refs")
        has_ours_kf = bool(keyframes) and any(HC_INDEX in k for k in keyframes)
        has_ours_audio = bool(refs) and any(HC_AUDIO_END_FRAME in r for r in refs)

        if mode == LEGACY_LAYOUT_MODE and has_ours_kf:
            _fix_keyframes_legacy(
                mm, self, ba.get("text_len"), ba.get("latent_t"), ba.get("frame_count"), keyframes, refs
            )
        if has_ours_audio:
            _fix_audio(mm, self, ba.get("text_len"), refs)
        # No Herrgotts marker -> exact stock result.

    setattr(patched_init, LAYOUT_PATCH_MARKER, True)
    setattr(patched_init, "_herrgotts_h3_layout_mode", mode)
    # Preserve the live constructor signature for introspection by ComfyUI,
    # diagnostics and repeated Continue calls. The wrapper itself still accepts
    # *args/**kwargs so harmless upstream optional additions remain forwarded.
    patched_init.__signature__ = sig

    try:
        if mode == LEGACY_LAYOUT_MODE:
            _run_legacy_self_test(mm, original_init, patched_init)
        else:
            _run_native_self_test(mm, original_init, patched_init)
    except Exception as exc:
        _LOG.error(
            "h3_continuous: live ComfyUI %s layout self-test FAILED (%s). No layout patch was installed.",
            mode, exc,
        )
        return False

    mm.PackedLayout.__init__ = patched_init
    _ORIGINAL_INIT = original_init
    _INSTALLED_WRAPPER = patched_init
    _MM = mm
    _APPLIED = True
    _APPLIED_MODE = mode
    if mode == NATIVE_LAYOUT_MODE:
        _LOG.info(
            "h3_continuous v1.3.0: ComfyUI native H3 keyframes detected; installed audio-only timeline wrapper"
        )
    else:
        _LOG.info(
            "h3_continuous v1.3.0: legacy marker-gated H3 layout wrapper installed on first continuation use"
        )
    return True


def uninstall_layout_patch_if_owned():
    """Best-effort rollback used only if paired patch installation fails."""
    global _ORIGINAL_INIT, _INSTALLED_WRAPPER, _APPLIED, _APPLIED_MODE, _MM
    if _MM is None or _ORIGINAL_INIT is None or _INSTALLED_WRAPPER is None:
        return False
    current = getattr(getattr(_MM, "PackedLayout", None), "__init__", None)
    if current is not _INSTALLED_WRAPPER:
        return False
    _MM.PackedLayout.__init__ = _ORIGINAL_INIT
    _ORIGINAL_INIT = None
    _INSTALLED_WRAPPER = None
    _MM = None
    _APPLIED = False
    _APPLIED_MODE = None
    _LOG.info("h3_continuous: rolled back Herrgotts H3 layout wrapper")
    return True


def is_applied():
    return _APPLIED


def applied_mode():
    return _APPLIED_MODE
