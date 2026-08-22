"""Release-facing helpers for Herrgotts H3 Infinite Continuation Suite.

These helpers are intentionally pure Python so duration conversion, preset
selection, dropdown compatibility, and stitch planning can be regression-tested
without importing ComfyUI.
"""

from __future__ import annotations

import math

try:
    from .latent_math import FPS, align_frame_count, video_latent_t, phase_aligned_extended_context_slice, phase_aware_context_slice, snap_landing_tail, masked_av_context_slice
except ImportError:  # direct test import from package directory
    from latent_math import FPS, align_frame_count, video_latent_t, phase_aligned_extended_context_slice, phase_aware_context_slice, snap_landing_tail, masked_av_context_slice


BALANCED_FREEZE_PRESET = {
    "analysis_window": 72,
    "freeze_hold": 8,
    "safety_margin": 3,
    "analysis_size": 192,
    "final_mean_diff_threshold": 0.0120,
    "final_active_pixel_threshold": 0.025,
    "max_final_active_area_percent": 3.0,
    "transition_mean_diff_threshold": 0.0020,
    "transition_active_pixel_threshold": 0.010,
    "max_transition_active_area_percent": 1.0,
    "min_static_transition_percent": 70.0,
    "max_consecutive_motion_outliers": 2,
    "final_reference_frames": 15,
    "min_final_match_percent": 75.0,
    "max_consecutive_final_outliers": 3,
    "safety_mode": "fixed",
}

# Motion Safe deliberately keeps the detector thresholds that were validated in
# real H3 clips and moves only the handover farther in front of the detected
# lock. This avoids creating a second, less-tested detector personality while
# giving high-motion scenes a larger buffer against freeze frames entering the
# next clip's context.
MOTION_SAFE_FREEZE_PRESET = {
    **BALANCED_FREEZE_PRESET,
    "safety_margin": 6,
}


def duration_to_requested_frames(duration_seconds: float, fps: float = FPS) -> int:
    """Convert user-facing seconds to a raw frame request before H3 grid snap.

    H3's existing temporal_shape() remains the source of truth for the actual
    17k+5 frame count. For example 10.0 s -> 240 requested frames -> 243 actual.
    """
    seconds = float(duration_seconds)
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("duration_seconds must be a positive finite number")
    return max(5, int(math.floor(seconds * float(fps) + 0.5)))


def normalize_duration_mode(value: str) -> str:
    text = str(value).strip().lower().replace("_", " ")
    aliases = {
        "total generation": "total_generation",
        "total generation (legacy)": "total_generation",
        "total": "total_generation",
        "legacy": "total_generation",
        "net new content": "net_new_content",
        "net": "net_new_content",
    }
    if text not in aliases:
        raise ValueError(f"Unknown duration mode {value!r}")
    return aliases[text]


def nearest_h3_frame_count(requested_frames: int, *, min_frames: int = 5) -> int:
    """Return the nearest normal H3 17k+5 frame count.

    ``align_frame_count`` intentionally rounds upward.  For user-facing net-new
    duration, however, rounding 159 frames up to 175 would overshoot by almost
    0.7 s.  Choosing the nearest legal H3 count keeps the visible *new* duration
    close to the user's request.  Ties prefer the larger count so we do not
    shorten the request unnecessarily.
    """
    requested = max(int(min_frames), int(requested_frames))
    lower_k = max(0, (requested - 5) // 17)
    lower = 17 * lower_k + 5
    upper = lower if lower >= requested else lower + 17
    lower = max(5, lower)
    upper = max(5, upper)
    if lower < int(min_frames):
        lower = align_frame_count(int(min_frames))
    if upper < int(min_frames):
        upper = align_frame_count(int(min_frames))
    dl = abs(requested - lower)
    du = abs(upper - requested)
    return int(upper if du <= dl else lower)


def masked_av_duration_plan(duration_seconds: float, context_frames: int,
                            duration_mode: str = "Net New Content") -> dict:
    """Resolve total H3 frames for v1.4 Masked-AV Continue.

    ``total_generation`` preserves the historical meaning of Duration: the
    whole generated clip, including the reused protected head.

    ``net_new_content`` instead targets approximately ``duration_seconds`` of
    visible newly-generated body *after* the protected head is removed.  The
    total is chosen on the nearest legal H3 17k+5 grid rather than always being
    rounded upward.
    """
    context = int(context_frames)
    if context < 0:
        raise ValueError("context_frames must be >= 0")
    mode = normalize_duration_mode(duration_mode)
    requested_visible = duration_to_requested_frames(duration_seconds)

    if mode == "total_generation":
        total = align_frame_count(requested_visible)
    else:
        desired_total = requested_visible + context
        total = nearest_h3_frame_count(desired_total, min_frames=context + 1)
        while total <= context:
            total += 17

    net = max(0, int(total) - context)
    return {
        "duration_mode": mode,
        "requested_duration_seconds": float(duration_seconds),
        "requested_visible_frames": int(requested_visible),
        "total_frame_count": int(total),
        "net_new_frames": int(net),
        "net_new_seconds": float(net) / float(FPS),
        "total_seconds": float(total) / float(FPS),
        "context_frames": context,
    }


def normalize_alignment_mode(value: str) -> str:
    text = str(value).strip().lower()
    aliases = {
        "phase_aligned_extended": "phase_aligned_extended",
        "phase-aware (legacy)": "phase_aware",
        "phase_aware (legacy)": "phase_aware",
        "phase_aware": "phase_aware",
        "legacy_17 (legacy)": "legacy_17",
        "legacy-17 (legacy)": "legacy_17",
        "legacy_17": "legacy_17",
    }
    if text not in aliases:
        raise ValueError(f"Unknown alignment mode {value!r}")
    return aliases[text]


def normalize_safety_mode(value: str) -> str:
    text = str(value).strip().lower()
    aliases = {
        "fixed": "fixed",
        "adaptive": "adaptive",
        "adaptive (legacy)": "adaptive",
    }
    if text not in aliases:
        raise ValueError(f"Unknown safety mode {value!r}")
    return aliases[text]


def normalize_freeze_preset(value: str) -> str:
    text = str(value).strip().lower().replace("_", " ")
    aliases = {
        "balanced": "balanced",
        "motion safe": "motion_safe",
        "motionsafe": "motion_safe",
        "custom": "custom",
    }
    if text not in aliases:
        raise ValueError(f"Unknown freeze preset {value!r}")
    return aliases[text]


def resolve_freeze_settings(preset: str, custom: dict) -> tuple[str, dict]:
    """Return normalized preset id and effective detector settings."""
    preset_id = normalize_freeze_preset(preset)
    if preset_id == "balanced":
        return preset_id, dict(BALANCED_FREEZE_PRESET)
    if preset_id == "motion_safe":
        return preset_id, dict(MOTION_SAFE_FREEZE_PRESET)

    out = dict(custom)
    out["safety_mode"] = normalize_safety_mode(out.get("safety_mode", "fixed"))
    return preset_id, out




def masked_av_render_trim(frame_count: int, *, freeze_detected: bool,
                          ideal_handover_end_frame: int | None, freeze_hold: int,
                          safety_margin: int = 0,
                          soft_final_candidate_start_frame: int | None = None) -> dict:
    """Resolve v1.4 render-only tail safety for native Masked AV.

    This helper proposes the safe visual endpoint. Candidate 4 then snaps that
    endpoint to the latest exact shared AV boundary and uses the snapped endpoint
    for BOTH Stitch Ready and the next Masked-AV protected source window.

    The visual policy remains three-tier:
      1. Hard freeze detected -> detector's conservative safe pixel endpoint.
      2. No hard freeze, but the primary final-state consensus found a candidate
         -> trim before that candidate plus the configured safety margin. This
         catches visually frozen / shimmering tails that fail only the residual
         motion gate.
      3. No usable final-state candidate -> remove one complete freeze_hold plus
         safety_margin as a render-only fallback.

    The returned endpoint itself is pixel-based; Candidate 4 performs the final
    AV-compatible snap in the v1.4 analyzer so render and continuation stay exact.
    """
    total = int(frame_count)
    if total <= 0:
        raise ValueError("frame_count must be > 0")
    hold = int(freeze_hold)
    if hold < 1:
        raise ValueError("freeze_hold must be >= 1")
    margin = max(0, int(safety_margin))

    if bool(freeze_detected):
        end = total - 1 if ideal_handover_end_frame is None else int(ideal_handover_end_frame)
        end = max(0, min(total - 1, end))
        tail = max(0, total - 1 - end)
        return {
            "handover_end_frame": end,
            "landing_tail_frames": tail,
            "render_safety_frames": 0,
            "render_safety_applied": False,
            "render_safety_mode": "hard_freeze",
            "soft_final_candidate_used": False,
            "policy": "freeze detected -> exact safe pixel trim",
        }

    candidate = -1 if soft_final_candidate_start_frame is None else int(soft_final_candidate_start_frame)
    if 0 <= candidate < total:
        # Candidate itself already belongs to the stable final-state consensus.
        # Keep a small buffer before it, exactly like the hard-freeze endpoint.
        end = max(0, min(total - 1, candidate - 1 - margin))
        tail = max(0, total - 1 - end)
        return {
            "handover_end_frame": end,
            "landing_tail_frames": tail,
            "render_safety_frames": tail,
            "render_safety_applied": tail > 0,
            "render_safety_mode": "soft_final_state",
            "soft_final_candidate_used": True,
            "policy": f"soft final-state tail -> trim {tail}f (candidate {candidate}, safety {margin}f)",
        }

    # A one-frame hold is treated as an explicit opt-out for backwards-compatible
    # tests/debugging, although the normal UI presets use >= 2.
    fallback = 0 if hold <= 1 else hold + margin
    fallback = min(fallback, max(0, total - 1))
    end = total - 1 - fallback
    return {
        "handover_end_frame": end,
        "landing_tail_frames": fallback,
        "render_safety_frames": fallback,
        "render_safety_applied": fallback > 0,
        "render_safety_mode": "no_lock_fallback",
        "soft_final_candidate_used": False,
        "policy": f"no freeze candidate -> render-only safety trim {fallback}f",
    }

def masked_av_safe_handover_plan(frame_count: int, visual_trim: dict, context_frames: int = 39) -> dict:
    """Snap a safe visual endpoint to one exact shared Masked-AV boundary.

    Candidate 4 uses this returned endpoint as the single source of truth for
    both the previous clip's Stitch Ready tail and the next clip's protected
    source window.
    """
    total = int(frame_count)
    if total <= 0:
        raise ValueError("frame_count must be > 0")
    desired_end = int(visual_trim.get("handover_end_frame", total - 1))
    desired_end = max(0, min(total - 1, desired_end))
    if desired_end < 38:
        raise ValueError(
            f"safe visual endpoint {desired_end} is too early for the minimum 39-frame Masked-AV context"
        )
    sl = masked_av_context_slice(
        video_latent_t(total), int(context_frames), total, ideal_last_frame=desired_end
    )
    actual_end = int(sl["source_end_frame"] - 1)
    cutoff_loss = int(desired_end - actual_end)
    if cutoff_loss < 0:
        raise RuntimeError("Masked-AV handover crossed the safe visual endpoint")
    return {
        **dict(visual_trim),
        "desired_handover_end_frame": desired_end,
        "handover_end_frame": actual_end,
        "landing_tail_frames": total - 1 - actual_end,
        "masked_av_cutoff_loss_frames": cutoff_loss,
        "masked_av_source_start_frame": int(sl["source_start_frame"]),
        "masked_av_source_end_frame": int(sl["source_end_frame"]),
        "masked_av_context_frames": int(sl["actual_context_frames"]),
        "masked_av_slice": sl,
    }


def apply_no_lock_fallback(handover: dict, *, freeze_hold: int, context_frames: int) -> dict:
    """Apply v1.2's safe no-lock fallback to handover metadata.

    When no final-frame lock is detected, the final ``freeze_hold - 1`` pixel
    frames are never allowed into continuation context. The desired pixel cutoff
    is then snapped backward to the latest valid phase-aligned H3 latent boundary.
    The full render/latent stays untouched; only handover metadata changes.
    """
    if not isinstance(handover, dict):
        raise TypeError("handover must be a dict")
    out = dict(handover)
    if out.get("freeze_detected"):
        out["no_lock_fallback_applied"] = False
        return out

    frame_count = int(out.get("frame_count", 0))
    freeze_hold = int(freeze_hold)
    context_frames = int(context_frames)
    if frame_count <= 0:
        raise ValueError("handover frame_count must be > 0")
    if freeze_hold < 2:
        raise ValueError("freeze_hold must be >= 2")
    if context_frames <= 0:
        raise ValueError("context_frames must be > 0")

    requested_excluded = freeze_hold - 1
    desired_last_frame = frame_count - 1 - requested_excluded
    desired_last_frame = max(context_frames - 1, desired_last_frame)
    vt = video_latent_t(frame_count)

    aligned = phase_aligned_extended_context_slice(
        vt, context_frames, ideal_last_frame=desired_last_frame
    )
    aware = phase_aware_context_slice(
        vt, context_frames, ideal_last_frame=desired_last_frame
    )
    legacy_tail, legacy_end = snap_landing_tail(
        frame_count, desired_last_frame, context_frames
    )

    out.update({
        "no_lock_fallback_applied": True,
        "no_lock_fallback_reason": "freeze_hold_minus_one",
        "no_lock_fallback_requested_excluded_frames": requested_excluded,
        "no_lock_fallback_target_end_frame": desired_last_frame,
        "ideal_handover_end_frame": desired_last_frame,
        "phase_aware_target_end_frame": desired_last_frame,
        "phase_aligned_target_end_frame": desired_last_frame,
        "phase_aware_effective_safety_margin": requested_excluded,
        "handover_end_frame": int(aligned["source_end_frame"] - 1),
        "landing_tail_frames": int(aligned["ignored_tail_frames"]),
        "phase_aligned_end_t": int(aligned["end_t"]),
        "phase_aligned_start_t": int(aligned["start_t"]),
        "phase_aligned_context_frames": int(aligned["actual_context_frames"]),
        "phase_aligned_context_extension_frames": int(aligned["context_extension_frames"]),
        "phase_aligned_cutoff_loss_frames": int(aligned["cutoff_loss_frames"]),
        "phase_aligned_source_start_frame": int(aligned["source_start_frame"]),
        "phase_aligned_source_end_frame": int(aligned["source_end_frame"]),
        "phase_aware_handover_end_frame": int(aware["source_end_frame"] - 1),
        "phase_aware_landing_tail_frames": int(aware["ignored_tail_frames"]),
        "phase_aware_end_t": int(aware["end_t"]),
        "phase_aware_start_t": int(aware["start_t"]),
        "phase_aware_context_frames": int(aware["actual_context_frames"]),
        "phase_aware_cutoff_loss_frames": int(aware["cutoff_loss_frames"]),
        "legacy_handover_end_frame": int(legacy_end),
        "legacy_landing_tail_frames": int(legacy_tail),
    })
    return out

def normalize_output_mode(value: str) -> str:
    text = str(value).strip().lower().replace("_", " ")
    aliases = {
        "full": "full",
        "stitch ready": "stitch_ready",
        "stitch-ready": "stitch_ready",
        "stitchready": "stitch_ready",
        "final clip": "final_clip",
        "final-clip": "final_clip",
        "finalclip": "final_clip",
    }
    if text not in aliases:
        raise ValueError(f"Unknown output mode {value!r}")
    return aliases[text]


def stitch_trim_plan(total_frames: int, output_mode: str, head_context_frames: int, handover) -> dict:
    """Resolve rendered-output head/tail trimming from continuation metadata.

    Tail trim is anchored to the exact phase-aligned latent handover boundary,
    not merely the unsnapped visual detector frame. This guarantees that the
    tail removed from clip N matches the latent history reused at clip N+1.
    """
    total = int(total_frames)
    if total <= 0:
        raise ValueError("total_frames must be > 0")
    mode = normalize_output_mode(output_mode)
    if mode == "full":
        return {
            "mode": mode,
            "head_trim_frames": 0,
            "tail_trim_frames": 0,
            "kept_frames": total,
        }

    head = max(0, int(head_context_frames))
    if head >= total:
        raise ValueError(
            f"output trim would remove the whole clip: head={head}, total={total}"
        )

    # The final segment still contains the reused continuation head, but there is
    # no next clip that needs a freeze-safe handover tail. Keep the complete
    # landing/final-keyframe region and trim only the duplicated head overlap.
    if mode == "final_clip":
        return {
            "mode": mode,
            "head_trim_frames": head,
            "tail_trim_frames": 0,
            "kept_frames": total - head,
        }

    if not isinstance(handover, dict) or not handover.get("available"):
        raise ValueError("stitch_ready requires H3_CONTINUOUS_HANDOVER metadata from the analyzer")

    meta_frames = int(handover.get("frame_count", total))
    if meta_frames != total:
        raise ValueError(
            f"handover frame_count {meta_frames} does not match rendered clip frame_count {total}"
        )

    end_frame = int(handover.get("handover_end_frame", total - 1))
    end_frame = max(-1, min(total - 1, end_frame))
    tail = total - (end_frame + 1)

    stored_tail = handover.get("landing_tail_frames")
    if stored_tail is not None and int(stored_tail) != tail:
        raise ValueError(
            f"handover metadata is internally inconsistent: end_frame={end_frame} implies tail={tail}, "
            f"but landing_tail_frames={stored_tail}"
        )

    if head + tail >= total:
        raise ValueError(
            f"stitch trim would remove the whole clip: head={head}, tail={tail}, total={total}"
        )

    return {
        "mode": mode,
        "head_trim_frames": head,
        "tail_trim_frames": tail,
        "kept_frames": total - head - tail,
        "handover_end_frame": end_frame,
    }
