import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from latent_math import temporal_shape
from release_utils import (
    BALANCED_FREEZE_PRESET,
    MOTION_SAFE_FREEZE_PRESET,
    duration_to_requested_frames,
    normalize_alignment_mode,
    normalize_safety_mode,
    resolve_freeze_settings,
    stitch_trim_plan,
    apply_no_lock_fallback,
)


def test_duration_10_seconds_matches_h3_243_frame_clip():
    requested = duration_to_requested_frames(10.0)
    frames, _, _ = temporal_shape(requested)
    assert requested == 240
    assert frames == 243


def test_duration_5_seconds_matches_h3_124_frame_clip():
    requested = duration_to_requested_frames(5.0)
    frames, _, _ = temporal_shape(requested)
    assert requested == 120
    assert frames == 124


def test_release_dropdown_legacy_labels_normalize():
    assert normalize_alignment_mode("phase_aligned_extended") == "phase_aligned_extended"
    assert normalize_alignment_mode("phase_aware (Legacy)") == "phase_aware"
    assert normalize_alignment_mode("legacy_17 (Legacy)") == "legacy_17"
    assert normalize_safety_mode("adaptive (Legacy)") == "adaptive"


def test_balanced_preset_is_calibrated_baseline():
    preset_id, settings = resolve_freeze_settings("Balanced", {"safety_margin": 99})
    assert preset_id == "balanced"
    assert settings == BALANCED_FREEZE_PRESET
    assert settings["safety_margin"] == 3
    assert settings["freeze_hold"] == 8
    assert settings["safety_mode"] == "fixed"


def test_motion_safe_changes_only_prelock_margin():
    _, balanced = resolve_freeze_settings("Balanced", {})
    _, safe = resolve_freeze_settings("Motion Safe", {})
    assert safe == MOTION_SAFE_FREEZE_PRESET
    assert safe["safety_margin"] == 6
    keys = set(balanced) | set(safe)
    assert [k for k in keys if balanced.get(k) != safe.get(k)] == ["safety_margin"]


def test_stitch_ready_start_clip_trims_phase_aligned_tail():
    handover = {"available": True, "frame_count": 243, "handover_end_frame": 212, "landing_tail_frames": 30}
    plan = stitch_trim_plan(243, "Stitch Ready", 0, handover)
    assert plan["head_trim_frames"] == 0
    assert plan["tail_trim_frames"] == 30
    assert plan["kept_frames"] == 213


def test_stitch_ready_continuation_trims_dynamic_head_and_tail():
    handover = {"available": True, "frame_count": 243, "handover_end_frame": 225, "landing_tail_frames": 17}
    plan = stitch_trim_plan(243, "Stitch Ready", 26, handover)
    assert plan["head_trim_frames"] == 26
    assert plan["tail_trim_frames"] == 17
    assert plan["kept_frames"] == 200


def test_full_mode_is_true_bypass_without_metadata():
    plan = stitch_trim_plan(243, "Full", 999, None)
    assert plan == {"mode": "full", "head_trim_frames": 0, "tail_trim_frames": 0, "kept_frames": 243}


def test_v117_final_clip_trims_dynamic_head_but_preserves_complete_tail():
    handover = {"available": True, "frame_count": 243, "handover_end_frame": 221, "landing_tail_frames": 21}
    plan = stitch_trim_plan(243, "Final Clip", 22, handover)
    assert plan == {"mode": "final_clip", "head_trim_frames": 22, "tail_trim_frames": 0, "kept_frames": 221}


def test_v117_final_clip_does_not_require_handover_metadata():
    plan = stitch_trim_plan(243, "Final Clip", 35, None)
    assert plan == {"mode": "final_clip", "head_trim_frames": 35, "tail_trim_frames": 0, "kept_frames": 208}


def test_v11_motion_safe_uses_eight_frame_hold():
    _, safe = resolve_freeze_settings("Motion Safe", {})
    assert safe["freeze_hold"] == 8
    assert safe["safety_margin"] == 6


def test_v11_no_lock_fallback_excludes_hold_minus_one_then_phase_aligns():
    result = apply_no_lock_fallback(
        {"available": True, "frame_count": 243, "freeze_detected": False},
        freeze_hold=8,
        context_frames=22,
    )
    assert result["no_lock_fallback_applied"] is True
    assert result["no_lock_fallback_requested_excluded_frames"] == 7
    assert result["no_lock_fallback_target_end_frame"] == 235
    assert result["handover_end_frame"] == 233
    assert result["landing_tail_frames"] == 9
    assert result["phase_aligned_context_frames"] == 30
    assert result["phase_aligned_context_extension_frames"] == 8
    assert result["phase_aligned_cutoff_loss_frames"] == 2


def test_v11_stitch_ready_uses_effective_no_lock_fallback_cutoff():
    handover = apply_no_lock_fallback(
        {"available": True, "frame_count": 243, "freeze_detected": False},
        freeze_hold=8,
        context_frames=22,
    )
    plan = stitch_trim_plan(243, "Stitch Ready", 0, handover)
    assert plan["tail_trim_frames"] == 9
    assert plan["handover_end_frame"] == 233
    assert plan["kept_frames"] == 234


def test_v11_full_output_ignores_no_lock_fallback_and_remains_complete():
    handover = apply_no_lock_fallback(
        {"available": True, "frame_count": 243, "freeze_detected": False},
        freeze_hold=8,
        context_frames=22,
    )
    plan = stitch_trim_plan(243, "Full", 30, handover)
    assert plan["head_trim_frames"] == 0
    assert plan["tail_trim_frames"] == 0
    assert plan["kept_frames"] == 243


def test_v11_no_lock_fallback_does_not_modify_detected_lock_cutoff():
    source = {
        "available": True,
        "frame_count": 243,
        "freeze_detected": True,
        "handover_end_frame": 212,
        "landing_tail_frames": 30,
    }
    result = apply_no_lock_fallback(source, freeze_hold=8, context_frames=22)
    assert result["no_lock_fallback_applied"] is False
    assert result["handover_end_frame"] == 212
    assert result["landing_tail_frames"] == 30
