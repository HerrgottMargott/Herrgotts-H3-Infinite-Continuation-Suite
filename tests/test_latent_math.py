import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from latent_math import (
    pixel_frames, temporal_shape, context_slice, phase_aware_context_slice,
    audio_slice_for_pixel_window, latent_boundaries, phase_aligned_extended_context_slice, step_offsets,
)


def test_h3_10s_shape():
    frames, vt, at = temporal_shape(243)
    assert frames == 243
    assert pixel_frames(vt) == 243
    assert vt == 72
    assert at == 405


def test_legacy_default_pre_freeze_slice():
    frames, vt, at = temporal_shape(243)
    s = context_slice(vt, 22, 34)
    assert s["previous_frame_count"] == 243
    assert s["source_end_frame"] == 209
    assert s["source_start_frame"] == 187
    assert s["end_t"] == 62
    assert s["start_t"] == 55
    assert s["offsets"] == [0, 1, 5, 9, 13, 17, 18]
    a0, a1, err = audio_slice_for_pixel_window(at, 187, 209)
    assert 0 <= a0 < a1 <= at
    assert abs(err) <= 0.5


def test_phase_aware_cutoff_keeps_late_motion():
    _, vt, at = temporal_shape(243)
    s = phase_aware_context_slice(vt, 22, ideal_last_frame=218)
    assert s["source_end_frame"] == 217
    assert s["source_end_frame"] - 1 == 216
    assert s["ignored_tail_frames"] == 26
    assert s["cutoff_loss_frames"] == 2
    assert s["actual_context_frames"] == 21
    assert (s["start_t"], s["end_t"]) == (58, 64)
    assert s["offsets"] == [0, 4, 8, 9, 13, 17]
    a0, a1, err = audio_slice_for_pixel_window(at, s["source_start_frame"], s["source_end_frame"])
    assert 0 <= a0 < a1 <= at
    assert abs(err) <= 0.5


def test_phase_aware_no_freeze_matches_full_tail():
    _, vt, _ = temporal_shape(243)
    s = phase_aware_context_slice(vt, 22, ideal_last_frame=242)
    assert s["source_end_frame"] == 243
    assert s["ignored_tail_frames"] == 0
    assert s["actual_context_frames"] == 22
    assert s["offsets"] == [0, 1, 5, 9, 13, 17, 18]


def test_phase_aware_never_crosses_ideal_and_loses_at_most_three_frames():
    _, vt, _ = temporal_shape(243)
    for ideal in range(60, 243):
        s = phase_aware_context_slice(vt, 22, ideal_last_frame=ideal)
        assert s["source_end_frame"] - 1 <= ideal
        assert 0 <= s["cutoff_loss_frames"] <= 3
        assert 1 <= s["actual_context_frames"] <= 22
        assert s["offsets"][0] == 0
        assert all(s["offsets"][i] < s["offsets"][i + 1] for i in range(len(s["offsets"]) - 1))


def test_phase_aware_offsets_preserve_source_boundaries():
    _, vt, _ = temporal_shape(243)
    b = latent_boundaries(vt)
    for ideal in (220, 218, 215, 212, 209):
        s = phase_aware_context_slice(vt, 22, ideal_last_frame=ideal)
        expected = [b[k] - b[s["start_t"]] for k in range(s["start_t"], s["end_t"])]
        assert s["offsets"] == expected


def test_phase_aligned_extended_observed_frame_213_case():
    _, vt, at = temporal_shape(243)
    s = phase_aligned_extended_context_slice(vt, 22, ideal_last_frame=212)
    assert s["source_start_frame"] == 187
    assert s["source_end_frame"] == 213
    assert s["source_end_frame"] - 1 == 212
    assert s["ignored_tail_frames"] == 30
    assert s["actual_context_frames"] == 26
    assert s["context_extension_frames"] == 4
    assert (s["start_t"], s["end_t"]) == (55, 63)
    assert s["source_start_phase"] == 0
    assert s["offsets"] == [0, 1, 5, 9, 13, 17, 18, 22]
    a0, a1, err = audio_slice_for_pixel_window(at, 187, 213)
    assert 0 <= a0 < a1 <= at
    assert abs(err) <= 0.5


def test_phase_aligned_extended_lock_228_case():
    _, vt, _ = temporal_shape(243)
    s = phase_aligned_extended_context_slice(vt, 22, ideal_last_frame=227)
    assert s["source_start_frame"] == 204
    assert s["source_end_frame"] == 226
    assert s["source_end_frame"] - 1 == 225
    assert s["ignored_tail_frames"] == 17
    assert s["actual_context_frames"] == 22
    assert s["context_extension_frames"] == 0
    assert s["source_start_phase"] == 0
    assert s["offsets"] == [0, 1, 5, 9, 13, 17, 18]


def test_phase_aligned_extended_no_freeze_tail_zero():
    _, vt, _ = temporal_shape(243)
    s = phase_aligned_extended_context_slice(vt, 22, ideal_last_frame=242)
    assert s["source_start_frame"] == 221
    assert s["source_end_frame"] == 243
    assert s["actual_context_frames"] == 22
    assert s["ignored_tail_frames"] == 0
    assert s["offsets"] == [0, 1, 5, 9, 13, 17, 18]


def test_phase_aligned_extended_is_canonical_for_all_late_cutoffs():
    _, vt, _ = temporal_shape(243)
    for ideal in range(60, 243):
        s = phase_aligned_extended_context_slice(vt, 22, ideal_last_frame=ideal)
        assert s["source_start_phase"] == 0
        assert s["source_end_frame"] - 1 <= ideal
        assert 0 <= s["cutoff_loss_frames"] <= 3
        assert s["actual_context_frames"] >= 22
        assert s["offsets"] == step_offsets(s["context_steps"])


def test_masked_av_exact_joint_context_lengths():
    from latent_math import is_exact_masked_av_context
    assert [n for n in (39, 90, 141, 192) if is_exact_masked_av_context(n)] == [39, 90, 141, 192]
    for n in (5, 22, 38, 40, 56, 73, 89, 91):
        assert not is_exact_masked_av_context(n)


def test_masked_av_true_tail_39_for_124_frame_clip():
    from latent_math import masked_av_context_slice, video_latent_t
    s = masked_av_context_slice(
        video_latent_t(124), 39, 124, ideal_last_frame=123
    )
    assert s["source_start_frame"] == 85
    assert s["source_end_frame"] == 124
    assert (s["start_t"], s["end_t"]) == (25, 37)
    assert s["context_steps"] == 12
    assert s["actual_context_frames"] == 39
    assert s["ignored_tail_frames"] == 0
    assert s["source_start_phase"] == 0
    assert s["source_end_phase"] == 2


def test_masked_av_true_tail_39_maps_to_exact_65_audio_ticks():
    from latent_math import masked_av_context_slice, video_latent_t, audio_slice_for_pixel_window
    _, _, at = temporal_shape(124)
    s = masked_av_context_slice(video_latent_t(124), 39, 124, ideal_last_frame=123)
    a0, a1, _ = audio_slice_for_pixel_window(at, s["source_start_frame"], s["source_end_frame"])
    assert (a0, a1) == (142, 207)
    assert a1 - a0 == 65


def test_masked_av_context_snaps_down_when_source_is_shorter():
    from latent_math import masked_av_context_slice, video_latent_t
    s = masked_av_context_slice(video_latent_t(124), 141, 124, ideal_last_frame=123)
    assert s["actual_context_frames"] == 90
    assert s["source_end_frame"] == 124
    assert s["ignored_tail_frames"] == 0


def test_masked_av_requires_target_longer_than_minimum_prefix():
    from latent_math import snap_masked_av_context_length
    import pytest
    with pytest.raises(ValueError):
        snap_masked_av_context_length(39, 124, 39)


def test_candidate6_full_previous_audio_tail_extends_beyond_video_handover():
    from latent_math import masked_av_audio_context_plan
    plan = masked_av_audio_context_plan(207, 68, 107, 124, "Full Previous Tail")
    assert plan["mode"] == "full_previous_tail"
    assert (plan["start_tick"], plan["end_tick"]) == (113, 207)
    assert plan["video_context_audio_steps"] == 65
    assert plan["audio_steps"] == 94
    assert plan["extra_tail_ticks"] == 29
    assert plan["extra_tail_frame_equivalent"] == 17
    assert abs(plan["extra_tail_seconds"] - 0.725) < 1e-9


def test_candidate6_match_video_audio_tail_reproduces_candidate4_65_ticks():
    from latent_math import masked_av_audio_context_plan
    plan = masked_av_audio_context_plan(207, 68, 107, 124, "Match Video Handover")
    assert plan["mode"] == "match_video_handover"
    assert (plan["start_tick"], plan["end_tick"]) == (113, 178)
    assert plan["audio_steps"] == 65
    assert plan["extra_tail_ticks"] == 0
    assert plan["extra_tail_seconds"] == 0.0


def test_candidate6_audio_tail_policy_rejects_unknown_mode():
    import pytest
    from latent_math import masked_av_audio_context_plan
    with pytest.raises(ValueError):
        masked_av_audio_context_plan(207, 68, 107, 124, "invented")
