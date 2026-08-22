import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from latent_math import temporal_shape
from release_utils import (
    BALANCED_FREEZE_PRESET,
    MOTION_SAFE_FREEZE_PRESET,
    duration_to_requested_frames,
    normalize_duration_mode,
    nearest_h3_frame_count,
    masked_av_duration_plan,
    normalize_alignment_mode,
    normalize_safety_mode,
    resolve_freeze_settings,
    stitch_trim_plan,
    apply_no_lock_fallback,
    masked_av_render_trim,
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


def test_v14_masked_av_no_lock_fallback_uses_full_hold_plus_safety_and_is_not_phase_snapped():
    result = masked_av_render_trim(
        124, freeze_detected=False, ideal_handover_end_frame=None, freeze_hold=8, safety_margin=3
    )
    assert result["render_safety_applied"] is True
    assert result["render_safety_mode"] == "no_lock_fallback"
    assert result["render_safety_frames"] == 11
    assert result["landing_tail_frames"] == 11
    assert result["handover_end_frame"] == 112
    assert result["policy"] == "no freeze candidate -> render-only safety trim 11f"


def test_v14_masked_av_soft_final_state_candidate_beats_fixed_fallback():
    result = masked_av_render_trim(
        124, freeze_detected=False, ideal_handover_end_frame=None, freeze_hold=8, safety_margin=3,
        soft_final_candidate_start_frame=112,
    )
    assert result["render_safety_applied"] is True
    assert result["render_safety_mode"] == "soft_final_state"
    assert result["soft_final_candidate_used"] is True
    assert result["handover_end_frame"] == 108
    assert result["landing_tail_frames"] == 15
    assert result["policy"] == "soft final-state tail -> trim 15f (candidate 112, safety 3f)"


def test_v14_masked_av_detected_freeze_uses_detector_endpoint_without_extra_fallback():
    result = masked_av_render_trim(124, freeze_detected=True, ideal_handover_end_frame=108, freeze_hold=8, safety_margin=3)
    assert result["render_safety_applied"] is False
    assert result["render_safety_frames"] == 0
    assert result["landing_tail_frames"] == 15
    assert result["handover_end_frame"] == 108
    assert result["policy"] == "freeze detected -> exact safe pixel trim"


def test_v14_masked_av_render_safety_can_be_disabled_with_hold_one():
    result = masked_av_render_trim(124, freeze_detected=False, ideal_handover_end_frame=None, freeze_hold=1)
    assert result["render_safety_applied"] is False
    assert result["landing_tail_frames"] == 0
    assert result["handover_end_frame"] == 123


def test_masked_av_safe_handover_uses_one_shared_boundary():
    from release_utils import masked_av_safe_handover_plan
    visual = {
        "handover_end_frame": 113,
        "landing_tail_frames": 10,
        "policy": "test safe visual endpoint",
    }
    plan = masked_av_safe_handover_plan(124, visual, 39)
    assert plan["desired_handover_end_frame"] == 113
    assert plan["handover_end_frame"] == 106
    assert plan["landing_tail_frames"] == 17
    assert plan["masked_av_cutoff_loss_frames"] == 7
    assert plan["masked_av_source_start_frame"] == 68
    assert plan["masked_av_source_end_frame"] == 107
    assert plan["masked_av_context_frames"] == 39


def test_masked_av_safe_handover_never_crosses_visual_cutoff():
    from release_utils import masked_av_safe_handover_plan
    for desired in range(38, 124):
        plan = masked_av_safe_handover_plan(124, {"handover_end_frame": desired}, 39)
        assert plan["handover_end_frame"] <= desired
        assert plan["masked_av_source_end_frame"] - 1 == plan["handover_end_frame"]
        assert plan["masked_av_source_end_frame"] - plan["masked_av_source_start_frame"] == 39
        assert plan["landing_tail_frames"] == 123 - plan["handover_end_frame"]


def test_candidate4_shared_boundary_matches_stitch_ready_and_next_context():
    from release_utils import masked_av_safe_handover_plan, stitch_trim_plan
    visual = {"handover_end_frame": 113, "policy": "test"}
    plan = masked_av_safe_handover_plan(124, visual, 39)
    handover = {
        "available": True,
        "frame_count": 124,
        "handover_end_frame": plan["handover_end_frame"],
        "landing_tail_frames": plan["landing_tail_frames"],
        "masked_av_source_policy": "safe_handover_window",
        "masked_av_source_start_frame": plan["masked_av_source_start_frame"],
        "masked_av_source_end_frame": plan["masked_av_source_end_frame"],
    }
    trim = stitch_trim_plan(124, "Stitch Ready", 0, handover)
    assert trim["tail_trim_frames"] == 17
    assert trim["kept_frames"] == 107
    # Stitch Ready keeps frames 0..106, and the next protected context ends at 106.
    assert handover["masked_av_source_end_frame"] - 1 == handover["handover_end_frame"] == 106



def test_candidate6_net_new_content_5s_targets_about_five_visible_new_seconds():
    plan = masked_av_duration_plan(5.0, 39, "Net New Content")
    assert plan["duration_mode"] == "net_new_content"
    assert plan["total_frame_count"] == 158
    assert plan["net_new_frames"] == 119
    assert abs(plan["net_new_seconds"] - (119 / 24.0)) < 1e-9


def test_candidate6_total_generation_5s_preserves_legacy_whole_clip_meaning():
    plan = masked_av_duration_plan(5.0, 39, "Total Generation")
    assert plan["duration_mode"] == "total_generation"
    assert plan["total_frame_count"] == 124
    assert plan["net_new_frames"] == 85


def test_candidate6_net_new_content_10s_uses_nearest_legal_h3_grid():
    plan = masked_av_duration_plan(10.0, 39, "Net New Content")
    assert plan["total_frame_count"] == 277
    assert plan["net_new_frames"] == 238
    assert abs(plan["net_new_seconds"] - (238 / 24.0)) < 1e-9


def test_candidate6_duration_mode_default_is_net_new_content():
    plan = masked_av_duration_plan(5.0, 39)
    assert plan["duration_mode"] == "net_new_content"
    assert normalize_duration_mode("Net New Content") == "net_new_content"
    assert nearest_h3_frame_count(159, min_frames=40) == 158
