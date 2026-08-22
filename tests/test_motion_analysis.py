import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motion_analysis import analyze_freeze_tail


def moving_bar_clip(frames=243, lock_start=None, noise=0.0):
    """Moving bright bar; at lock_start it snaps to a fixed final position."""
    h, w = 48, 64
    x = torch.zeros(frames, h, w, 3)
    if lock_start is None:
        lock_start = frames
    for t in range(min(lock_start, frames)):
        left = (t * 3) % 44
        x[t, 16:32, left:left + 8] = 1.0
    if lock_start < frames:
        final = torch.zeros(h, w, 3)
        final[16:32, 50:58] = 1.0
        x[lock_start:] = final
        if noise:
            x[lock_start:] += torch.randn_like(x[lock_start:]) * noise
            x.clamp_(0, 1)
    return x


def slow_converge_then_lock_clip(frames=243, lock_start=228):
    h, w = 64, 96
    x = torch.zeros(frames, h, w, 3)
    final_left = 70
    for t in range(max(0, lock_start - 30)):
        left = (t * 2) % 60
        x[t, 18:50, left:left + 16] = 1.0
    begin = max(0, lock_start - 30)
    for t in range(begin, lock_start):
        progress = (t - begin) / max(1, lock_start - begin)
        left = int(round(48 + progress * (final_left - 2 - 48)))
        x[t, 18:50, left:left + 16] = 1.0
    final = torch.zeros(h, w, 3)
    final[18:50, final_left:final_left + 16] = 1.0
    x[lock_start:] = final
    return x


def test_final_frame_lock_detects_actual_lock_not_generic_low_motion():
    r = analyze_freeze_tail(slow_converge_then_lock_clip(lock_start=228))
    assert r["freeze_detected"] is True
    assert r["detector_mode"] == "stable_tail_consensus"
    assert r["freeze_start_frame"] == 228
    assert r["trailing_locked_frames"] == 15
    assert r["safety_mode"] == "fixed"
    assert r["phase_aware_effective_safety_margin"] == 3
    assert r["phase_aware_target_end_frame"] == 224
    assert r["handover_end_frame"] == 221
    assert r["landing_tail_frames"] == 21
    assert r["phase_aligned_context_frames"] == 35
    assert r["phase_aligned_context_extension_frames"] == 13
    assert r["phase_aligned_cutoff_loss_frames"] == 3
    assert r["phase_aware_handover_end_frame"] == 221


def test_obvious_lock_is_detected():
    r = analyze_freeze_tail(moving_bar_clip(lock_start=221))
    assert r["freeze_detected"] is True
    assert r["freeze_start_frame"] == 221
    assert r["trailing_locked_frames"] == 22
    assert r["confidence"] >= 0.80
    assert r["phase_aware_target_end_frame"] == 217
    assert r["handover_end_frame"] == 216
    assert r["landing_tail_frames"] == 26


def test_no_final_lock_keeps_tail_zero():
    r = analyze_freeze_tail(moving_bar_clip())
    assert r["freeze_detected"] is False
    assert r["landing_tail_frames"] == 0
    assert r["handover_end_frame"] == 242
    assert r["legacy_landing_tail_frames"] == 0


def test_tiny_residual_noise_still_counts_as_lock():
    torch.manual_seed(123)
    r = analyze_freeze_tail(moving_bar_clip(lock_start=221, noise=0.00035))
    assert r["freeze_detected"] is True
    assert r["freeze_start_frame"] == 221


def test_short_final_lock_is_not_forced():
    r = analyze_freeze_tail(moving_bar_clip(lock_start=238))
    assert r["freeze_detected"] is False
    assert r["landing_tail_frames"] == 0


def test_phase_aligned_metadata_for_lock_213_matches_observed_case():
    r = analyze_freeze_tail(moving_bar_clip(lock_start=213))
    assert r["freeze_detected"] is True
    assert r["freeze_start_frame"] == 213
    assert r["phase_aligned_target_end_frame"] == 209
    assert r["handover_end_frame"] == 208
    assert r["landing_tail_frames"] == 34
    assert r["phase_aligned_context_frames"] == 22
    assert r["phase_aligned_context_extension_frames"] == 0


def lock_with_isolated_residual_outlier(frames=243, lock_start=207):
    h, w = 48, 64
    x = torch.full((frames, h, w, 3), 0.25)
    for t in range(lock_start):
        left = (t * 3) % 44
        x[t, 16:32, left:left + 8] = 0.75
    final = torch.full((h, w, 3), 0.25)
    final[16:32, 50:58] = 0.75
    x[lock_start:] = final
    x[239] = (final + 0.0014).clamp(0, 1)
    x[240] = (final - 0.0014).clamp(0, 1)
    return x


def lock_with_sustained_residual_motion(frames=243, lock_start=207):
    h, w = 48, 64
    x = torch.full((frames, h, w, 3), 0.25)
    for t in range(lock_start):
        left = (t * 3) % 44
        x[t, 16:32, left:left + 8] = 0.75
    final = torch.full((h, w, 3), 0.25)
    final[16:32, 50:58] = 0.75
    for t in range(lock_start, frames):
        delta = 0.0014 if (t - lock_start) % 2 == 0 else -0.0014
        x[t] = (final + delta).clamp(0, 1)
    x[-1] = final
    return x


def test_robust_gate_ignores_isolated_transition_outlier():
    r = analyze_freeze_tail(lock_with_isolated_residual_outlier())
    assert r["freeze_detected"] is True
    assert r["detector_mode"] == "stable_tail_consensus"
    assert r["freeze_start_frame"] == 207
    assert r["primary_final_match_frames"] == 36
    assert r["residual_motion_outliers"] >= 1
    assert r["residual_static_ratio_percent"] >= 85.0
    assert r["residual_max_consecutive_outliers"] <= 2


def test_robust_gate_rejects_sustained_residual_motion():
    r = analyze_freeze_tail(lock_with_sustained_residual_motion())
    assert r["primary_final_match_frames"] >= 6
    assert r["freeze_detected"] is False
    assert r["no_lock_reason"] == "residual_motion_gate_failed"
    assert r["residual_gate_passed"] is False
    # Candidate 4 keeps this weaker visual-final-state onset for safe-handover
    # trimming even though it is intentionally rejected as a hard freeze.
    assert r["primary_candidate_start_frame"] >= 0
    assert r["primary_candidate_trailing_frames"] >= r["freeze_hold"]


def stable_tail_with_last_frame_outlier(frames=243, lock_start=215):
    h, w = 48, 64
    x = torch.full((frames, h, w, 3), 0.25)
    for t in range(lock_start):
        left = (t * 3) % 44
        x[t, 16:32, left:left + 8] = 0.75
    final = torch.full((h, w, 3), 0.25)
    final[16:32, 50:58] = 0.75
    x[lock_start:] = final
    x[-1] = (final + 0.0018).clamp(0, 1)
    return x


def test_stable_tail_consensus_ignores_last_frame_visual_outlier():
    r = analyze_freeze_tail(stable_tail_with_last_frame_outlier())
    assert r["freeze_detected"] is True
    assert r["detector_mode"] == "stable_tail_consensus"
    assert r["freeze_start_frame"] == 215
    assert r["trailing_locked_frames"] == 28
    assert r["final_reference_frames"] == 15
    assert r["primary_final_match_ratio_percent"] >= 75.0


def test_v046_fixed_safety_is_never_reduced_by_confidence():
    r = analyze_freeze_tail(stable_tail_with_last_frame_outlier())
    assert r["freeze_detected"] is True
    assert r["freeze_start_frame"] == 215
    assert r["confidence"] >= 0.80
    assert r["safety_mode"] == "fixed"
    assert r["safety_margin"] == 3
    assert r["phase_aware_effective_safety_margin"] == 3
    assert r["phase_aware_target_end_frame"] == 211
    assert r["handover_end_frame"] == 208


def test_v046_adaptive_mode_preserves_legacy_high_confidence_behavior():
    r = analyze_freeze_tail(stable_tail_with_last_frame_outlier(), safety_mode="adaptive")
    assert r["freeze_detected"] is True
    assert r["confidence"] >= 0.80
    assert r["safety_mode"] == "adaptive"
    assert r["phase_aware_effective_safety_margin"] == 0
    assert r["phase_aware_target_end_frame"] == 214
    assert r["handover_end_frame"] == 212


def test_v046_calibrated_defaults_still_reject_serious_continuous_motion():
    r = analyze_freeze_tail(moving_bar_clip())
    assert r["freeze_detected"] is False
    assert r["landing_tail_frames"] == 0


def test_v046_default_configuration_is_calibrated_safe_early():
    r = analyze_freeze_tail(stable_tail_with_last_frame_outlier())
    assert r["freeze_hold"] == 12
    assert r["safety_margin"] == 3
    assert r["safety_mode"] == "fixed"
    assert r["final_reference_frames"] == 15
    assert r["min_final_match_percent"] == 75.0
    assert r["max_consecutive_final_outliers"] == 3
    assert r["min_static_transition_percent"] == 70.0
    assert r["max_consecutive_motion_outliers"] == 2
    assert r["final_mean_diff_threshold"] == 0.012
    assert r["final_active_pixel_threshold"] == 0.025
    assert r["max_final_active_area_percent"] == 3.0
    assert r["transition_mean_diff_threshold"] == 0.002
    assert r["transition_active_pixel_threshold"] == 0.010
    assert r["max_transition_active_area_percent"] == 1.0
