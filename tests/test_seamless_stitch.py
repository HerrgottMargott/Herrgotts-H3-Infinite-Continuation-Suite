import torch

from seamless_stitch import (
    context_aligned_video_join,
    context_aligned_audio_join,
    resolve_saved_head_context,
)


def test_context_aligned_video_join_keeps_hard_stitch_duration():
    prev = torch.zeros((10, 2, 2, 3), dtype=torch.float32)
    nxt = torch.ones((8, 2, 2, 3), dtype=torch.float32)
    out, stats = context_aligned_video_join(prev, nxt, next_head_context_frames=4, next_tail_trim_frames=1, crossfade_frames=4)
    assert out.shape[0] == 13
    assert stats["video_crossfade_frames"] == 4
    assert torch.allclose(out[6], torch.zeros_like(out[6]))
    assert torch.allclose(out[9], torch.ones_like(out[9]))


def test_video_join_can_disable_crossfade():
    prev = torch.zeros((5, 1, 1, 3))
    nxt = torch.ones((6, 1, 1, 3))
    out, stats = context_aligned_video_join(prev, nxt, 2, 1, 0)
    assert out.shape[0] == 8
    assert stats["video_crossfade_frames"] == 0
    assert torch.allclose(out[:5], prev)


def test_audio_join_uses_short_corresponding_context_and_exact_total_duration():
    sr = 48000
    fps = 24
    prev_frames = 10
    next_frames = 8
    head = 4
    tail = 1
    prev_samples = round(prev_frames / fps * sr)
    next_samples = round(next_frames / fps * sr)
    prev = {"waveform": torch.zeros((1, 2, prev_samples)), "sample_rate": sr}
    nxt = {"waveform": torch.ones((1, 2, next_samples)), "sample_rate": sr}
    out, stats = context_aligned_audio_join(
        prev, nxt, previous_output_frames=prev_frames, next_total_frames=next_frames,
        next_head_context_frames=head, next_tail_trim_frames=tail,
        crossfade_ms=15.0, fps=fps,
    )
    expected_frames = prev_frames + next_frames - head - tail
    assert out["waveform"].shape[-1] == round(expected_frames / fps * sr)
    assert stats["audio_crossfade_samples"] == 720
    boundary = prev_samples - 1
    assert float(out["waveform"][0, 0, boundary]) > 0.99


def test_saved_head_context_prefers_own_metadata_and_has_v117_fallback():
    head, source = resolve_saved_head_context({"head_context_frames": "26"}, 3, {"phase_aligned_context_frames": 22})
    assert head == 26
    assert source == "saved metadata"

    head, source = resolve_saved_head_context({}, 3, {"phase_aligned_context_frames": 35})
    assert head == 35
    assert "previous handover" in source


def test_clip_one_head_is_always_zero():
    assert resolve_saved_head_context({"head_context_frames": "99"}, 1, None)[0] == 0


def test_luminance_gain_estimator_matches_and_clamps_global_brightness_offset():
    from seamless_stitch import estimate_luminance_gain

    prev = torch.full((8, 16, 16, 3), 0.50)
    nxt = torch.full((8, 16, 16, 3), 0.45)
    open_stats = estimate_luminance_gain(prev, nxt, max_correction_percent=20.0)
    assert abs(open_stats["luminance_measured_gain"] - (0.50 / 0.45)) < 1e-4
    assert abs(open_stats["luminance_applied_gain"] - (0.50 / 0.45)) < 1e-4
    assert open_stats["luminance_clamped"] is False

    clamped = estimate_luminance_gain(prev, nxt, max_correction_percent=10.0)
    assert abs(clamped["luminance_applied_gain"] - 1.10) < 1e-6
    assert clamped["luminance_clamped"] is True


def test_video_join_luminance_match_removes_boundary_step_then_fades_to_native():
    prev = torch.full((10, 8, 8, 3), 0.50)
    nxt = torch.full((8, 8, 8, 3), 0.45)
    out, stats = context_aligned_video_join(
        prev, nxt,
        next_head_context_frames=4,
        next_tail_trim_frames=0,
        crossfade_frames=4,
        luminance_match=True,
        luminance_fade_frames=4,
        max_luminance_correction_percent=20.0,
    )
    assert out.shape[0] == 14
    assert abs(float(out[9].mean()) - 0.50) < 1e-4
    assert abs(float(out[10].mean()) - 0.50) < 1e-4
    assert abs(float(out[13].mean()) - 0.45) < 1e-4
    assert stats["luminance_fade_frames"] == 4


def test_video_join_can_disable_luminance_match_independently_of_crossfade():
    prev = torch.full((10, 8, 8, 3), 0.50)
    nxt = torch.full((8, 8, 8, 3), 0.45)
    out, stats = context_aligned_video_join(
        prev, nxt, 4, 0, 4,
        luminance_match=False,
        luminance_fade_frames=16,
        max_luminance_correction_percent=10.0,
    )
    assert abs(float(out[10].mean()) - 0.45) < 1e-4
    assert stats["luminance_match_enabled"] is False
    assert stats["luminance_applied_gain"] == 1.0


def test_luminance_match_does_not_change_audio_join_math():
    sr = 32000
    prev = {"waveform": torch.zeros((1, 2, round(10 / 24 * sr))), "sample_rate": sr}
    nxt = {"waveform": torch.ones((1, 2, round(8 / 24 * sr))), "sample_rate": sr}
    out, stats = context_aligned_audio_join(prev, nxt, 10, 8, 4, 1, crossfade_ms=15.0, fps=24)
    assert stats["audio_crossfade_samples"] == 480
    assert out["waveform"].shape[-1] == round(13 / 24 * sr)


def test_streaming_luminance_fade_can_modify_only_boundary_frames_in_place():
    from seamless_stitch import apply_luminance_gain_fade

    images = torch.full((6, 4, 4, 3), 0.50)
    ptr = images.data_ptr()
    out, faded = apply_luminance_gain_fade(images, 1.10, fade_frames=4, inplace=True)
    assert out.data_ptr() == ptr
    assert faded == 4
    assert float(out[0].mean()) > 0.54
    assert abs(float(out[3].mean()) - 0.50) < 1e-5
    assert torch.allclose(out[4:], torch.full_like(out[4:], 0.50))


def test_safe_tail_bridge_uses_only_phase_alignment_loss_inside_safe_end():
    from seamless_stitch import safe_tail_bridge_plan
    handover = {
        "available": True,
        "frame_count": 243,
        "handover_end_frame": 208,
        "ideal_handover_end_frame": 210,
        "phase_aligned_cutoff_loss_frames": 2,
    }
    plan = safe_tail_bridge_plan(handover, max_bridge_frames=2)
    assert plan["safe_tail_bridge_frames"] == 2
    assert plan["safe_tail_bridge_start_frame"] == 209
    assert plan["safe_tail_bridge_end_frame"] == 210
    assert plan["safe_tail_bridge_capped"] is False


def test_safe_tail_bridge_never_borrows_from_safety_margin_or_exceeds_cap():
    from seamless_stitch import safe_tail_bridge_plan
    handover = {
        "available": True,
        "frame_count": 243,
        "handover_end_frame": 208,
        "ideal_handover_end_frame": 214,
        "phase_aligned_cutoff_loss_frames": 3,
    }
    plan = safe_tail_bridge_plan(handover, max_bridge_frames=2)
    assert plan["safe_tail_bridge_available_frames"] == 3
    assert plan["safe_tail_bridge_frames"] == 2
    assert plan["safe_tail_bridge_capped"] is True
    assert safe_tail_bridge_plan(handover, max_bridge_frames=0)["safe_tail_bridge_frames"] == 0


def test_extract_safe_tail_bridge_pixels_are_exact_previous_frames():
    from seamless_stitch import extract_safe_tail_bridge_images
    frames = torch.arange(12, dtype=torch.float32).view(12, 1, 1, 1).repeat(1, 1, 1, 3)
    handover = {
        "available": True,
        "frame_count": 12,
        "handover_end_frame": 7,
        "ideal_handover_end_frame": 9,
        "phase_aligned_cutoff_loss_frames": 2,
    }
    bridge, plan = extract_safe_tail_bridge_images(frames, handover, 2)
    assert bridge.shape[0] == 2
    assert torch.allclose(bridge[:, 0, 0, 0], torch.tensor([8.0, 9.0]))
    assert plan["safe_tail_bridge_frames"] == 2


def test_safe_tail_bridge_keeps_video_timeline_length_when_next_video_head_is_shifted():
    prev = torch.zeros((10, 2, 2, 3), dtype=torch.float32)
    bridge = torch.full((2, 2, 2, 3), 0.25, dtype=torch.float32)
    previous_extended = torch.cat((prev, bridge), dim=0)
    nxt = torch.ones((12, 2, 2, 3), dtype=torch.float32)
    original_head = 4
    tail = 1
    out, _ = context_aligned_video_join(
        previous_extended, nxt,
        next_head_context_frames=original_head + 2,
        next_tail_trim_frames=tail,
        crossfade_frames=0,
        luminance_match=False,
    )
    expected = 10 + (12 - original_head - tail)
    assert out.shape[0] == expected
    sr = 32000
    prev_audio = {"waveform": torch.zeros((1, 2, round(10 / 24 * sr))), "sample_rate": sr}
    next_audio = {"waveform": torch.ones((1, 2, round(12 / 24 * sr))), "sample_rate": sr}
    audio, _ = context_aligned_audio_join(
        prev_audio, next_audio, 10, 12, original_head, tail, crossfade_ms=15.0, fps=24
    )
    assert audio["waveform"].shape[-1] == round(expected / 24 * sr)


def test_masked_av_context_tail_offset_moves_video_overlap_anchor_without_changing_body_trim():
    # Reused next head represents source frames 5..9. Previous visible output was
    # trimmed two frames earlier (ends at source frame 7), so the corresponding
    # overlap endpoint is next-head index 3 rather than the end of the 5-frame head.
    prev = torch.full((6, 1, 1, 3), 7.0)
    nxt = torch.zeros((9, 1, 1, 3))
    nxt[:5] = torch.tensor([5., 6., 7., 8., 9.]).view(5, 1, 1, 1)
    nxt[5:] = 20.0
    out, stats = context_aligned_video_join(
        prev, nxt, next_head_context_frames=5, next_tail_trim_frames=0,
        crossfade_frames=1, context_tail_offset_frames=2,
    )
    assert stats["context_tail_offset_frames"] == 2
    assert stats["video_crossfade_frames"] == 1
    # 6 previous + (9-5) future frames: reused head remains fully removed.
    assert out.shape[0] == 10
    # Crossfade uses next context source-frame 7, not source-frame 9.
    assert abs(float(out[5].mean()) - 7.0) < 1e-6
    assert torch.allclose(out[6:], torch.full_like(out[6:], 20.0))


def test_masked_av_context_tail_offset_moves_audio_overlap_anchor_and_keeps_duration():
    sr = 24000
    fps = 24
    prev_frames = 6
    next_frames = 9
    head = 5
    offset = 2
    prev_samples = round(prev_frames / fps * sr)
    next_samples = round(next_frames / fps * sr)
    prev = {"waveform": torch.full((1, 2, prev_samples), 0.7), "sample_rate": sr}
    wave = torch.zeros((1, 2, next_samples))
    # Context source frames 5,6,7,8,9 -> 0.5,0.6,0.7,0.8,0.9.
    for i, value in enumerate((0.5, 0.6, 0.7, 0.8, 0.9)):
        wave[..., i * 1000:(i + 1) * 1000] = value
    wave[..., head * 1000:] = 1.0
    nxt = {"waveform": wave, "sample_rate": sr}
    out, stats = context_aligned_audio_join(
        prev, nxt, previous_output_frames=prev_frames, next_total_frames=next_frames,
        next_head_context_frames=head, next_tail_trim_frames=0,
        crossfade_ms=1.0, fps=fps, context_tail_offset_frames=offset,
    )
    assert stats["context_tail_offset_frames"] == offset
    assert out["waveform"].shape[-1] == round((prev_frames + next_frames - head) / fps * sr)
