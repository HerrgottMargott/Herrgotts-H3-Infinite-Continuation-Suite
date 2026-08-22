"""Pure MiniMax H3 timeline/latent math used by the continuous-generation nodes."""

FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
FRAME_RESCALE = 5.0 / 3.0  # 40 Hz audio positions / 24 fps video positions
FPS = 24.0
AUDIO_HZ = 40.0

# Canonical legacy windows. v0.4 can also reuse phase-shifted direct-latent
# windows while preserving the source token spacing.
CONTEXT_TO_STEPS = {
    5: 2,
    22: 7,
    39: 12,
}


def pixel_frames(latent_t: int) -> int:
    """Number of pixel frames represented by the first latent_t H3 video steps."""
    latent_t = int(latent_t)
    if latent_t < 0:
        raise ValueError("latent_t must be >= 0")
    return sum(FRAME_PER_TOKEN[k % 5] for k in range(latent_t))


def latent_boundaries(latent_t: int):
    """Exclusive pixel-frame boundary after each H3 video latent step.

    For a normal H3 target the boundaries start at 0 and follow the exact
    cumulative ``1,4,4,4,4`` span pattern used by MiniMax H3's RoPE timeline.
    The returned list has ``latent_t + 1`` elements, including 0.
    """
    latent_t = int(latent_t)
    if latent_t < 0:
        raise ValueError("latent_t must be >= 0")
    out = [0]
    acc = 0
    for k in range(latent_t):
        acc += FRAME_PER_TOKEN[k % 5]
        out.append(acc)
    return out


def step_offsets(latent_t: int):
    """Pixel-frame offset at which every latent step begins, relative to phase 0."""
    return latent_boundaries(latent_t)[:-1]


def align_frame_count(length: int) -> int:
    """Snap requested H3 length upward to the model's 17k+5 pixel-frame grid."""
    n = max(5, int(length))
    while n % 17 != 5:
        n += 1
    return n


def video_latent_t(frame_count: int) -> int:
    frame_count = int(frame_count)
    return 2 if frame_count <= 5 else ((frame_count - 5) // 17) * 5 + 2


def temporal_shape(length: int):
    frame_count = align_frame_count(length)
    vt = video_latent_t(frame_count)
    at = round((frame_count / FPS) * AUDIO_HZ)
    return frame_count, vt, at


def context_slice(video_latent_t: int, context_frames: int, landing_tail_frames: int):
    """Legacy v0.3 direct-latent slice using complete 17-frame phase groups.

    This remains available as ``legacy_17`` fallback. The tail must be a
    multiple of 17 so the source window restarts on H3 phase 0 when moved to the
    head of the next clip.
    """
    video_latent_t = int(video_latent_t)
    context_frames = int(context_frames)
    landing_tail_frames = int(landing_tail_frames)

    if context_frames not in CONTEXT_TO_STEPS:
        raise ValueError(f"context_frames must be one of {sorted(CONTEXT_TO_STEPS)}")
    if landing_tail_frames < 0 or landing_tail_frames % 17 != 0:
        raise ValueError("landing_tail_frames must be 0 or a positive multiple of 17")

    discard_steps = (landing_tail_frames // 17) * 5
    end_t = video_latent_t - discard_steps
    ctx_steps = CONTEXT_TO_STEPS[context_frames]
    start_t = end_t - ctx_steps
    if start_t < 0:
        raise ValueError("Previous latent is too short for this context + landing tail")

    if end_t % 5 != 2 or start_t % 5 != 0:
        raise ValueError(
            f"H3 temporal phase mismatch (slice {start_t}:{end_t}). "
            "The saved latent may not be a normal 17k+5 H3 clip."
        )

    source_end_frame = pixel_frames(end_t)
    source_start_frame = source_end_frame - context_frames
    if source_start_frame < 0:
        raise ValueError("Context starts before the beginning of the previous clip")

    return {
        "mode": "legacy_17",
        "start_t": start_t,
        "end_t": end_t,
        "context_steps": ctx_steps,
        "offsets": step_offsets(ctx_steps),
        "source_start_frame": source_start_frame,
        "source_end_frame": source_end_frame,
        "previous_frame_count": pixel_frames(video_latent_t),
        "requested_context_frames": context_frames,
        "actual_context_frames": context_frames,
        "ignored_tail_frames": landing_tail_frames,
        "cutoff_loss_frames": 0,
        "source_start_phase": start_t % 5,
        "source_end_phase": end_t % 5,
    }


def _latest_boundary_at_or_before(boundaries, desired_end_exclusive: int) -> int:
    """Return latent end index whose pixel boundary is latest <= desired limit."""
    desired_end_exclusive = int(desired_end_exclusive)
    # Small lists (H3 10 s is only 73 boundaries); a reverse scan is clearer
    # than introducing a dependency or edge-case-prone bisect arithmetic.
    for i in range(len(boundaries) - 1, 0, -1):
        if boundaries[i] <= desired_end_exclusive:
            return i
    return 0


def phase_aware_context_slice(
    video_latent_t: int,
    context_frames: int,
    *,
    ideal_last_frame: int | None = None,
    desired_tail_frames: int | None = None,
):
    """Pick the latest direct-latent handover before a pixel cutoff.

    v0.4 Mode A no longer throws away complete 17-frame groups merely to make
    the reused window restart on phase 0. Instead it:

      1. keeps the latest *existing source latent boundary* at/before the desired
         pixel cutoff (therefore losing at most the remainder of one source
         latent span, normally 0..3 frames),
      2. slices consecutive source latent steps ending there, and
      3. preserves their ORIGINAL source-relative pixel offsets when positioning
         the conditioning rows at the next clip's head.

    The source window is chosen as the largest duration not exceeding
    ``context_frames``. Depending on source phase, a requested 22-frame context
    therefore becomes 21 or 22 pixel frames (rather than stretching/compressing
    source time or cutting through a latent step).
    """
    video_latent_t = int(video_latent_t)
    context_frames = int(context_frames)
    if context_frames <= 0:
        raise ValueError("context_frames must be > 0")
    if (ideal_last_frame is None) == (desired_tail_frames is None):
        raise ValueError("Provide exactly one of ideal_last_frame or desired_tail_frames")

    boundaries = latent_boundaries(video_latent_t)
    previous_frame_count = boundaries[-1]

    if ideal_last_frame is not None:
        ideal_last_frame = max(context_frames - 1, min(previous_frame_count - 1, int(ideal_last_frame)))
        desired_end_exclusive = ideal_last_frame + 1
    else:
        desired_tail_frames = max(0, int(desired_tail_frames))
        desired_end_exclusive = max(context_frames, previous_frame_count - desired_tail_frames)
        ideal_last_frame = desired_end_exclusive - 1

    end_t = _latest_boundary_at_or_before(boundaries, desired_end_exclusive)
    if end_t <= 0:
        raise ValueError("No H3 latent boundary exists before the requested cutoff")

    # Choose the longest whole-step source history that does not exceed the
    # requested duration. This keeps the delivered overlap predictable and never
    # time-warps a source latent. For 22 frames the actual span is 21 or 22.
    start_t = end_t - 1
    while start_t > 0 and (boundaries[end_t] - boundaries[start_t - 1]) <= context_frames:
        start_t -= 1

    actual_context_frames = boundaries[end_t] - boundaries[start_t]
    if actual_context_frames <= 0:
        raise ValueError("Phase-aware context window is empty")
    if actual_context_frames > context_frames:
        raise RuntimeError("Internal phase-aware context exceeded requested duration")

    source_start_frame = boundaries[start_t]
    source_end_frame = boundaries[end_t]
    if source_start_frame < 0 or source_end_frame > previous_frame_count:
        raise RuntimeError("Internal phase-aware source bounds are invalid")

    offsets = [boundaries[k] - source_start_frame for k in range(start_t, end_t)]
    if not offsets or offsets[0] != 0:
        raise RuntimeError("Internal phase-aware offsets do not start at zero")
    if any(offsets[i] >= offsets[i + 1] for i in range(len(offsets) - 1)):
        raise RuntimeError("Internal phase-aware offsets are not strictly increasing")

    ignored_tail_frames = previous_frame_count - source_end_frame
    cutoff_loss_frames = desired_end_exclusive - source_end_frame
    if cutoff_loss_frames < 0:
        raise RuntimeError("Phase-aware latent cutoff crossed the desired pixel cutoff")

    return {
        "mode": "phase_aware_head",
        "start_t": start_t,
        "end_t": end_t,
        "context_steps": end_t - start_t,
        "offsets": offsets,
        "source_start_frame": source_start_frame,
        "source_end_frame": source_end_frame,
        "previous_frame_count": previous_frame_count,
        "requested_context_frames": context_frames,
        "actual_context_frames": actual_context_frames,
        "ideal_handover_end_frame": ideal_last_frame,
        "ignored_tail_frames": ignored_tail_frames,
        "cutoff_loss_frames": cutoff_loss_frames,
        "source_start_phase": start_t % 5,
        "source_end_phase": end_t % 5,
    }



def phase_aligned_extended_context_slice(
    video_latent_t: int,
    context_frames: int,
    *,
    ideal_last_frame: int | None = None,
    desired_tail_frames: int | None = None,
):
    """Pick the latest cutoff while forcing the reused run to start on H3 phase 0.

    v0.4.3 keeps the late cutoff introduced by phase-aware mode, but avoids the
    non-zero source-start phase that produced visible head flicker in testing.
    The end boundary is still the latest *existing* H3 latent boundary at/before
    the requested pixel cutoff. The start boundary is then moved backward to the
    latest latent index whose phase is 0 and whose span is at least
    ``context_frames``.

    The resulting context can therefore be longer than requested (by at most the remainder needed to reach the previous phase-0 start
    (13 extra pixel frames for the current 5/22/39 presets)), but its source-relative offsets exactly
    match the canonical target head timeline. No latent is split, resampled, or
    time-warped.
    """
    video_latent_t = int(video_latent_t)
    context_frames = int(context_frames)
    if context_frames <= 0:
        raise ValueError("context_frames must be > 0")
    if (ideal_last_frame is None) == (desired_tail_frames is None):
        raise ValueError("Provide exactly one of ideal_last_frame or desired_tail_frames")

    boundaries = latent_boundaries(video_latent_t)
    previous_frame_count = boundaries[-1]

    if ideal_last_frame is not None:
        ideal_last_frame = max(context_frames - 1, min(previous_frame_count - 1, int(ideal_last_frame)))
        desired_end_exclusive = ideal_last_frame + 1
    else:
        desired_tail_frames = max(0, int(desired_tail_frames))
        desired_end_exclusive = max(context_frames, previous_frame_count - desired_tail_frames)
        ideal_last_frame = desired_end_exclusive - 1

    end_t = _latest_boundary_at_or_before(boundaries, desired_end_exclusive)
    if end_t <= 0:
        raise ValueError("No H3 latent boundary exists before the requested cutoff")

    # Start on canonical H3 phase 0. Pick the LATEST such boundary that still
    # supplies at least the requested history. This extends the context backward
    # only as much as necessary while making its offsets identical to a normal
    # target clip head.
    start_t = None
    for candidate in range(end_t - 1, -1, -1):
        if candidate % 5 != 0:
            continue
        if boundaries[end_t] - boundaries[candidate] >= context_frames:
            start_t = candidate
            break
    if start_t is None:
        raise ValueError(
            "Previous latent is too short to provide a phase-0 aligned context "
            f"of at least {context_frames} frames before the requested cutoff"
        )

    actual_context_frames = boundaries[end_t] - boundaries[start_t]
    source_start_frame = boundaries[start_t]
    source_end_frame = boundaries[end_t]
    context_steps = end_t - start_t
    offsets = [boundaries[k] - source_start_frame for k in range(start_t, end_t)]
    canonical_offsets = step_offsets(context_steps)

    if start_t % 5 != 0:
        raise RuntimeError("Internal phase-aligned context did not start on phase 0")
    if offsets != canonical_offsets:
        raise RuntimeError(
            "Internal phase-aligned offsets do not match the canonical H3 target head"
        )
    if actual_context_frames < context_frames:
        raise RuntimeError("Internal phase-aligned context is shorter than requested")

    ignored_tail_frames = previous_frame_count - source_end_frame
    cutoff_loss_frames = desired_end_exclusive - source_end_frame
    if cutoff_loss_frames < 0:
        raise RuntimeError("Phase-aligned latent cutoff crossed the desired pixel cutoff")

    return {
        "mode": "phase_aligned_extended",
        "start_t": start_t,
        "end_t": end_t,
        "context_steps": context_steps,
        "offsets": offsets,
        "source_start_frame": source_start_frame,
        "source_end_frame": source_end_frame,
        "previous_frame_count": previous_frame_count,
        "requested_context_frames": context_frames,
        "actual_context_frames": actual_context_frames,
        "context_extension_frames": actual_context_frames - context_frames,
        "ideal_handover_end_frame": ideal_last_frame,
        "ignored_tail_frames": ignored_tail_frames,
        "cutoff_loss_frames": cutoff_loss_frames,
        "source_start_phase": start_t % 5,
        "source_end_phase": end_t % 5,
    }


def is_exact_masked_av_context(frame_count: int) -> bool:
    """Return True for joint H3 video/audio prefix durations.

    A masked AV prefix must be a normal H3 video-VAE run (17k+5 frames)
    and end on an integer 40 Hz audio-latent tick.  At 24 fps this yields
    39, 90, 141, 192, ... frames.
    """
    frame_count = int(frame_count)
    return frame_count >= 39 and (frame_count - 39) % 51 == 0


def snap_masked_av_context_length(requested: int, available: int, target_frames: int) -> int:
    """Snap a requested protected prefix down to the largest exact AV run."""
    cap = min(int(requested), int(available), int(target_frames) - 1)
    if cap < 39:
        raise ValueError(
            "Masked AV continuation needs at least 39 usable source frames and "
            "a target clip longer than 39 frames"
        )
    run = 39 + ((cap - 39) // 51) * 51
    if not is_exact_masked_av_context(run):
        raise RuntimeError("Internal masked AV context snap failed")
    return run


def masked_av_context_slice(
    video_latent_t: int,
    context_frames: int,
    target_frames: int,
    *,
    ideal_last_frame: int | None = None,
    desired_tail_frames: int | None = None,
):
    """Select a phase-canonical source run for in-place masked AV continuation.

    The copied run must fit the target prefix, have an exact joint 24-fps /
    40-Hz duration, and start on H3 video-latent phase 0 so the copied latent
    tokens occupy the same temporal phase at the new target head.  The source
    end is therefore snapped to the latest phase-2 latent boundary at/before
    the requested handover cutoff.
    """
    video_latent_t = int(video_latent_t)
    target_frames = int(target_frames)
    boundaries = latent_boundaries(video_latent_t)
    previous_frame_count = boundaries[-1]
    n = snap_masked_av_context_length(context_frames, previous_frame_count, target_frames)
    if (ideal_last_frame is None) == (desired_tail_frames is None):
        raise ValueError("Provide exactly one of ideal_last_frame or desired_tail_frames")

    if ideal_last_frame is not None:
        ideal_last_frame = max(n - 1, min(previous_frame_count - 1, int(ideal_last_frame)))
        desired_end_exclusive = ideal_last_frame + 1
    else:
        desired_tail_frames = max(0, int(desired_tail_frames))
        desired_end_exclusive = max(n, previous_frame_count - desired_tail_frames)
        ideal_last_frame = desired_end_exclusive - 1

    # n is guaranteed to lie on H3's 17k+5 grid.
    context_steps = 2 + 5 * ((n - 5) // 17)

    end_t = None
    for candidate in range(video_latent_t, context_steps - 1, -1):
        if candidate % 5 != 2:
            continue
        if boundaries[candidate] <= desired_end_exclusive:
            start = candidate - context_steps
            if start >= 0 and start % 5 == 0:
                end_t = candidate
                break
    if end_t is None:
        raise ValueError(
            "Previous latent has no phase-aligned masked AV context before the requested handover cutoff"
        )

    start_t = end_t - context_steps
    source_start_frame = boundaries[start_t]
    source_end_frame = boundaries[end_t]
    actual_context_frames = source_end_frame - source_start_frame
    if actual_context_frames != n:
        raise RuntimeError(
            f"Internal masked AV run has {actual_context_frames} frames, expected {n}"
        )
    if start_t % 5 != 0 or end_t % 5 != 2:
        raise RuntimeError("Internal masked AV source phase is not canonical")

    ignored_tail_frames = previous_frame_count - source_end_frame
    cutoff_loss_frames = desired_end_exclusive - source_end_frame
    if cutoff_loss_frames < 0:
        raise RuntimeError("Masked AV latent cutoff crossed the desired pixel cutoff")

    return {
        "mode": "masked_av",
        "start_t": start_t,
        "end_t": end_t,
        "context_steps": context_steps,
        "offsets": step_offsets(context_steps),
        "source_start_frame": source_start_frame,
        "source_end_frame": source_end_frame,
        "previous_frame_count": previous_frame_count,
        "requested_context_frames": int(context_frames),
        "actual_context_frames": n,
        "ideal_handover_end_frame": ideal_last_frame,
        "ignored_tail_frames": ignored_tail_frames,
        "cutoff_loss_frames": cutoff_loss_frames,
        "source_start_phase": start_t % 5,
        "source_end_phase": end_t % 5,
    }

def audio_slice_for_pixel_window(audio_t: int, source_start_frame: int, source_end_frame: int):
    """Map a source pixel-frame window onto the saved 40 Hz audio latent grid."""
    audio_t = int(audio_t)
    source_start_frame = int(source_start_frame)
    source_end_frame = int(source_end_frame)
    if source_end_frame <= source_start_frame:
        raise ValueError("Audio source window must be non-empty")

    a0 = round(source_start_frame * AUDIO_HZ / FPS)
    a1 = round(source_end_frame * AUDIO_HZ / FPS)
    a0 = max(0, min(audio_t, a0))
    a1 = max(0, min(audio_t, a1))
    if a1 <= a0:
        raise ValueError("Mapped H3 audio context window is empty")

    exact_end = source_end_frame * AUDIO_HZ / FPS
    end_error_steps = float(a1) - float(exact_end)
    return a0, a1, end_error_steps



def normalize_audio_tail_mode(value: str) -> str:
    """Normalize the v1.4 audio-tail carryover policy."""
    text = str(value).strip().lower().replace("_", " ")
    aliases = {
        "full previous tail": "full_previous_tail",
        "full tail": "full_previous_tail",
        "full": "full_previous_tail",
        "match video handover": "match_video_handover",
        "match video context": "match_video_handover",
        "match video": "match_video_handover",
        "video": "match_video_handover",
    }
    if text not in aliases:
        raise ValueError(f"Unknown audio tail carryover mode {value!r}")
    return aliases[text]


def masked_av_audio_context_plan(audio_t: int, source_start_frame: int,
                                 video_source_end_frame: int, previous_frame_count: int,
                                 mode: str = "Full Previous Tail"):
    """Plan independent H3 audio protection for a Masked-AV continuation.

    Video stays anchored to the freeze-safe Masked-AV handover window.  Audio
    may either end at the same visual handover (legacy Candidate-4 behavior) or
    continue through the original previous clip's full remaining audio tail.
    All frame endpoints are exclusive pixel-frame positions.
    """
    audio_t = int(audio_t)
    start = int(source_start_frame)
    video_end = int(video_source_end_frame)
    previous_end = int(previous_frame_count)
    if previous_end <= 0:
        raise ValueError("previous_frame_count must be > 0")
    if start < 0 or video_end <= start or video_end > previous_end:
        raise ValueError(
            f"Invalid Masked-AV audio source geometry start={start}, video_end={video_end}, previous={previous_end}"
        )
    normalized = normalize_audio_tail_mode(mode)
    audio_end_frame = previous_end if normalized == "full_previous_tail" else video_end
    a0, a1, end_error = audio_slice_for_pixel_window(audio_t, start, audio_end_frame)
    _, video_a1, _ = audio_slice_for_pixel_window(audio_t, start, video_end)
    baseline_steps = int(video_a1 - a0)
    steps = int(a1 - a0)
    extra_ticks = max(0, steps - baseline_steps)
    return {
        "mode": normalized,
        "source_start_frame": start,
        "video_source_end_frame": video_end,
        "audio_source_end_frame": audio_end_frame,
        "start_tick": int(a0),
        "end_tick": int(a1),
        "audio_steps": steps,
        "video_context_audio_steps": baseline_steps,
        "extra_tail_ticks": int(extra_ticks),
        "extra_tail_seconds": float(extra_ticks) / float(AUDIO_HZ),
        "extra_tail_frame_equivalent": max(0, audio_end_frame - video_end),
        "end_error_steps": float(end_error),
    }


def snap_landing_tail(frame_count: int, ideal_last_frame: int, context_frames: int):
    """Legacy snap of an inclusive desired handover end to a 17-frame tail."""
    import math
    frame_count = int(frame_count)
    ideal_last_frame = int(ideal_last_frame)
    context_frames = int(context_frames)
    if frame_count < context_frames:
        raise ValueError("Clip is shorter than requested context")
    desired_end = max(context_frames, min(frame_count, ideal_last_frame + 1))
    delta = max(0, frame_count - desired_end)
    tail = int(math.ceil(delta / 17.0) * 17) if delta else 0
    max_tail = max(0, ((frame_count - context_frames) // 17) * 17)
    tail = min(tail, max_tail)
    return tail, frame_count - tail - 1
