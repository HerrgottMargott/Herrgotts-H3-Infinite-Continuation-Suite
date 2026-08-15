# Herrgotts-H3-Infinite-Continuation-Suite

A ComfyUI node and workflow suite for creating **long MiniMax H3 videos from connected FL2VA / First-Last-Frame clips** while preserving motion and native audio between segments.

> **Experimental community project.** This is not an official MiniMax continuation mode. Testing is still limited, so reproducible results, failures and examples are very welcome.

## Overview

The project was built to combine two things that normally pull in different directions:

- **FL2VA / First-Last-Frame quality and control:** prepared keyframes give every segment a fixed visual target and can repeatedly pull composition, identity and image quality back toward a clean reference.
- **Ref2VA-style continuity benefits:** motion and native audio should continue naturally instead of restarting at every clip boundary.

Generating FL2VA clips independently gives strong keyframe control, but continuity usually breaks at the cut. Simply reusing the end of the previous clip is also unreliable because H3 often reaches the Last Frame early and then freezes for the final part of the segment.

This suite keeps a short section of the previous clip directly in H3's **video + audio latent context**, automatically finds a safe handover before the frozen tail, aligns that handover to H3's temporal latent structure and uses the same metadata for final stitching.

The goal is therefore **not just to make a clip longer**. It is to preserve motion/audio continuity while repeatedly getting the quality reset and creative control of new FL2VA keyframe anchors.

## Example Generation

▶ **[Watch the 7-clip / ~61-second example generation](https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite/releases/download/v1.2.0/h3-infinite-7-clip-example.mp4)**

This example was generated as seven separate FL2VA segments and stitched automatically with the included Saved Chain workflow.

Tested settings:

- 7 chained H3 segments
- FL2VA First/Last-Frame keyframe workflow
- `Balanced` Auto Handover
- `context_frames = 22`
- Safe Tail Bridge: `2` frames
- Video crossfade: `4` frames
- Audio de-click crossfade: `15 ms`
- Boundary luminance matching: Off

No manual editing was performed at the six clip boundaries. Very small single-frame brightness variations may still occasionally be visible.

### Main features

- Direct **video + audio latent continuation** without decode/re-encode handover.
- Repeated **Last Frame keyframe anchors** for visual control and quality resets.
- **Auto Handover** that detects the frozen FL2VA tail instead of using a fixed trim.
- **Phase-aligned context** to avoid startup flicker from invalid H3 latent cut positions.
- **No-Lock Fallback** when no final freeze is detected.
- **Safe Tail Bridge:** rendered frames lost only because of latent phase alignment can replace the first 1–2 potentially unstable video frames of the next clip.
- Short context-aligned **video crossfade** and independently tested **15 ms audio de-click crossfade**.
- `Full`, `Stitch Ready` and `Final Clip` output modes.
- Save / Load complete AV latents with stitch metadata.
- A **memory-bounded Saved Chain Stitcher** for long projects generated clip by clip.
- Runtime-adaptive H3 compatibility: native arbitrary keyframes on ComfyUI 0.33+, with only the direct-audio timeline wrapper retained; the full legacy hooks remain available for older ComfyUI versions.

### How this differs from other H3 chaining tools

Latent-based H3 chaining is not unique to this project. Other community tools, including [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context), also continue H3 motion/audio context directly.

This suite specifically focuses on **freeze-aware, keyframe-anchored FL2VA chains**: every segment can have a new visual endpoint, the frozen FL2VA tail is analyzed automatically, the handover is moved to a valid H3 phase, and the same metadata is reused for stitching.

For a general Ref2VA graph another chaining pack may be a better fit. Herrgotts-H3-Infinite-Continuation-Suite is aimed at users who specifically want **latent continuity + repeated FL2VA keyframe control + automatic freeze-safe stitching**.

## ComfyUI 0.33 compatibility

**v1.2.2** adapts the continuation path to ComfyUI's new native MiniMax H3 arbitrary-keyframe API.

- On **ComfyUI 0.33+**, continuation keyframes use stock ComfyUI placement directly and the old `MiniMaxH3.extra_conds` payload monkey patch is not installed. A small marker-gated `PackedLayout` wrapper remains only to put the direct carried audio latent on the new clip's own timeline so it ends at the same continuation boundary as the video context.
- On **older ComfyUI H3 implementations**, the previous lazy legacy keyframe/payload compatibility path is retained.
- Runtime detection is based on the live `PackedLayout.__init__` API rather than a hard-coded ComfyUI version. Both paths fail closed if the live layout no longer matches the assumptions validated by the built-in self-test.

The direct video/audio latent handover, freeze analysis, phase-aligned cutoff, Safe Tail Bridge and stitching logic are unchanged.

Live validation on **ComfyUI 0.33.0** confirmed repeated Continue generation in the same ComfyUI session, including direct AV continuation, saving, seamless visual/audio continuation and correct Last Frame landing.

## Installation

### ComfyUI Manager / Registry

Search for **Herrgotts-H3-Infinite-Continuation-Suite** in ComfyUI Manager and install it normally. The v1.2.2 example workflows also embed Registry package metadata so **Check Missing Custom Nodes / Install Missing Custom Nodes** can resolve this pack directly.

### Manual installation

From `ComfyUI/custom_nodes`:

```bash
git clone https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite.git
```

Restart ComfyUI and reload the browser UI.

### MiniMax H3 files

The repository does **not** include model weights. The included workflows use the normal ComfyUI MiniMax H3 setup, including:

- `minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- `minimax_h3_video_vae_fp16.safetensors`
- `minimax_h3_audio_vae_fp32.safetensors`

See the official [MiniMax H3 ComfyUI guide](https://docs.comfy.org/tutorials/video/minimax/minimax-h3) and [Comfy-Org MiniMax-H3 model repository](https://huggingface.co/Comfy-Org/MiniMax-H3).

### Optional SageAttention / KJNodes

The supplied generation workflows include **Patch Sage Attention KJ** as an optional optimization. Install [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) plus a compatible SageAttention setup if you want to use it.

SageAttention is **not required** for continuation. If it causes instability or OOMs in your setup, disable/bypass it.


## Usage

### Included workflows

The `examples/` folder contains four annotated workflows:

**1. Start — `Herrgotts_H3_Infinite_v1.2_01_Start.json`**  
Creates Clip 1 with First/Last-Frame conditioning, analyzes the final freeze and saves the complete AV latent plus handover metadata.

**2. Continue — `Herrgotts_H3_Infinite_v1.2_02_Continue.json`**  
Loads the previous AV latent and creates Clip 2+. Motion and native audio context are injected directly; a new Last Frame can be supplied as the next visual anchor.

**3. 3-Clip Showcase / Auto Stitch — `Herrgotts_H3_Infinite_v1.2_03_3Clip_Showcase_AutoStitch.json`**  
Runs Start -> Continue -> Continue in one queue and automatically creates a stitched final video. The graph is intentionally structured so another continuation block can be added for Clip 4+.

**4. Stitch Saved Chain — `Herrgotts_H3_Infinite_v1.2_04_Stitch_Saved_Chain.json`**  
Combines clips generated separately with Workflows 1/2. It decodes one saved AV latent at a time and writes directly to MP4, so memory usage does not grow with every clip in the chain.

### Tested baseline

Most development/testing used:

- **10 seconds requested duration** per clip -> 243 actual H3 frames / about 10.125 s.
- First + Last Frame for Clip 1.
- A new **Last Frame for every continuation clip**.
- Same resolution, H3 model and VAEs throughout the chain.
- `Balanced` Auto Handover.
- `phase_aligned_extended`.
- `context_frames = 22`.
- `max_safe_tail_bridge_frames = 2`.
- `video_crossfade_frames = 4`.
- `audio_crossfade_ms = 15`.

These are the recommended starting values because they are the settings that have actually been tested.

### Other settings worth testing

H3 itself supports variable duration and optional endpoint inputs, so shorter/longer clips and missing individual keyframes should be possible in principle. They are simply much less tested with this suite.

- **Shorter clips:** may be useful for faster action or more frequent quality resets.
- **Longer clips:** likely work within normal H3 limits, but give the model more time to drift before the next keyframe reset.
- **No Last Frame on an individual continuation:** technically possible, but removes the fixed visual landing/quality reset that motivates this workflow. The No-Lock Fallback becomes more important.
- **Different context lengths:** possible, but `22` is the tested default. More context carries more history but also gives the next clip more previous material to reproduce.

If you test other durations, context lengths or keyframe patterns, please share both successful and unsuccessful results.

## Prompting Guidance

In theory, prompts that work well with normal MiniMax H3 should also work with this suite. A few habits appear helpful for chained FL2VA segments:

- **Prompt continuing action rather than the keyframe landing.** For smooth boundaries, avoid strongly steering the wording toward the exact Last Frame pose. Prefer wording like `she continues walking` over `she settles into the pose`. The image keyframe already provides the endpoint anchor.
- **Keep important audio away from the very end of a segment.** If your prompt describes events chronologically, place critical dialogue/sound earlier rather than making it the final event. The workflow may discard or replace a few rendered frames around the handover, so important audio is safer near the beginning or middle of the clip.
- **Background music can be discouraged** by adding `non_diegetic_music: N/A` at the end of the prompt. This does not guarantee silence, but in testing it can substantially reduce unwanted music.
- **`<Picture 1>` is still experimental.** Its exact influence on the generated video is not fully understood. Identity appears more stable when the reference clearly belongs to the same subject/content as the keyframes. A useful prompt opening is for example:  
  `<Picture 1> is reference for the woman's facial features, clothing and bodily composition.`

## Included Nodes

| Node | Purpose | Main settings |
|---|---|---|
| **H3 Infinite - Start FFLF v1.2** | Creates Clip 1 with native H3 First/Last-Frame conditioning. | Duration, resolution, First Frame, Last Frame, optional `<Picture 1>`. |
| **H3 Infinite - Continue from Latent v1.2** | Creates Clip 2+ from direct previous AV latent context. | Recommended: `auto`, `phase_aligned_extended`, `context_frames = 22`. |
| **H3 Infinite - Auto Handover v1.2** | Detects the frozen FL2VA tail and selects the usable handover. | `Balanced` = tested default; `Motion Safe` = more conservative; `Custom` exposes detector settings. |
| **H3 Infinite - Output / Stitch v1.2** | Prepares one rendered segment. | `Full`, `Stitch Ready`, `Final Clip`. |
| **H3 Infinite - Seamless AV Join v1.2** | Joins the current timeline to the next full decoded clip. | Safe Tail Bridge `2`, video crossfade `4`, audio `15 ms`. Luminance matching is experimental and off by default. |
| **H3 Infinite - Save AV Latent** | Saves the complete video+audio latent and continuation/stitch metadata. | Keep sequential clip indices. |
| **H3 Infinite - Load AV Latent** | Loads a saved full AV latent for later continuation. | Select prefix/index. |
| **H3 Infinite - Stitch Saved Chain v1.2** | Memory-bounded final assembly of separately generated clips. | Clip range, Safe Tail Bridge, video/audio seam settings, CRF. |
| **H3 Infinite - Latent Info** | Shows basic information about a saved/current AV latent. | Mainly useful for troubleshooting. |

### Safe Tail Bridge

The phase-aligned latent cutoff sometimes has to stop **1–3 rendered frames before** Auto Handover's already-safe ideal endpoint. Those frames cannot be used as latent anchors, but they are still valid rendered pixels.

With the default `max_safe_tail_bridge_frames = 2`, the stitcher keeps up to two of those exact frames from the previous clip and skips the same number of early **video** frames in the next clip. It never moves beyond the detector's safe endpoint and does not change total duration.

Audio is intentionally **not shifted** by the bridge. It keeps the tested 15 ms de-click transition on the original audio timeline.

## Examples

If the suite works well for you, example videos are very welcome. Open a GitHub Issue with a short description of the settings/workflow and a link to the result. With permission, good examples can be added to the GitHub showcase with credit.

Bug reports are equally useful. Please include the relevant console log and, when possible, the workflow JSON.

## Limitations / Known Issues

- **Audio quality may drift over very long chains.** Visual quality can repeatedly reset toward new keyframes; there is currently no equivalent HQ audio reset.
- **Dialogue can extend into the frozen visual tail.** The voice itself may continue correctly while words that occur in discarded tail audio are not recreated. Keep important dialogue away from segment endings.
- **Audio context is limited.** Audio before the selected context window is not available to the next clip.
- **The extra `<Picture 1>` reference remains experimental.** It appears more stable when it clearly depicts the same subject/content as the keyframes.
- **Keyframe-free continuation is not well tested.** It removes the main visual reset/anchor that motivated this approach.
- **Durations other than the tested 10-second setup need more testing.**
- **Performance variability in long chained runs:** During testing, one three-clip run showed strongly increasing generation times across successive clips (23:55 -> 39:43 -> 55:52). A later run did not reproduce this behavior (24:53 -> 27:50 -> 27:42). The cause is currently unknown and may depend on ComfyUI memory management, offloading, system state or other runtime factors rather than chain length itself. More testing is welcome.
- **Occasional OOMs have been observed on continuation runs.** The exact cause is not yet known, but current observations suggest a possible interaction with the optional KJ SageAttention patch. In the tested setup, simply queuing the generation again was enough; a ComfyUI restart was not required. If repeated OOMs become annoying during longer chains, disable SageAttention first and retry.
- **Only one H3 chaining pack should own the same runtime hooks.** This suite detects conflicting H3 wrappers and refuses to stack them.
- **Hardware-limited testing.** Development has covered only a limited set of scenes, prompts, resolutions and hardware configurations. Please report unexpected behavior.

## Development History

The project began with the idea of repeatedly using H3's strong First/Last-Frame control without sacrificing continuous motion and audio.

The main problems encountered were:

1. **FL2VA freeze tails:** H3 often reaches the Last Frame early and then remains almost static. Fixed trimming failed because the freeze length varies by clip. This led to the current automatic Stable-Tail freeze detector.
2. **Slow motion vs. real freeze:** simple motion thresholds were unreliable. The detector was reworked around a stable final-state reference plus residual-motion checks and calibrated on real clips.
3. **Latent phase flicker:** the visually latest safe frame is not always a valid H3 latent boundary. `phase_aligned_extended` keeps the safe late endpoint while extending context backward to a canonical H3 phase.
4. **Rendered seam artifacts:** direct AV latent continuation made motion/audio continuous, but separately decoded clips could still show a tiny pixel seam and audio click. A short context-aligned video blend and 15 ms audio de-click crossfade solved most of this.
5. **The first 1–2 video frames could still be unstable:** brightness matching reduced the seam but could create a visible brightness drift. The release solution is **Safe Tail Bridge**: use the real safe pixels from the previous clip that were discarded only because of latent phase alignment, then begin the next clip a couple of video frames later.
6. **Long-project assembly:** storing full AV latents plus metadata made it possible to add a separate memory-bounded stitcher that processes saved clips sequentially instead of keeping the entire chain decoded in RAM.
7. **Public-release safety:** runtime H3 wrappers now install only on first continuation use, are gated to this suite's markers, self-check compatibility and refuse to stack on another chaining patch.

The `Balanced` freeze preset was manually compared with roughly ten H3 clips during development and matched the visible freeze boundary very closely in those tests. This is encouraging, not a guarantee for every scene.

## Acknowledgments

- **[MiniMax / MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3)** — underlying audiovisual model and H3 prompting behavior.
- **[ComfyUI](https://github.com/Comfy-Org/ComfyUI)** and **Comfy-Org's MiniMax H3 integration** — native H3 implementation, latent/VAE support and workflow environment.
- **[ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)** — optional Patch Sage Attention KJ node used during testing.
- **[SageAttention](https://github.com/thu-ml/SageAttention)** — optional attention acceleration.
- **[safetensors](https://github.com/huggingface/safetensors)** — AV latent + metadata storage.
- **[ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) by NikoDemon80** — its public runtime-patch isolation approach prompted the lazy/marker-gated patch hardening in this suite.
- **ChatGPT by OpenAI (GPT-5.6 Sol)** — substantial assistance with implementation, debugging, regression-test design and documentation.

**Author / maintainer:** [HerrgottMargott](https://github.com/HerrgottMargott)

OpenAI is not a maintainer, sponsor or publisher of this project.

## Technical Notes

- H3 runs at 24 fps and uses a `17k+5` temporal frame grid. `10.0 s` becomes 243 actual frames (~10.125 s).
- Continuation uses the **full sampler AV latent**, not a decoded/re-encoded handover.
- Video and audio context are taken from the same source time range.
- `phase_aligned_extended` can reuse more than the requested 22 frames so the next clip begins on a valid H3 phase.
- `actual_head_context_frames` is therefore the correct rendered head trim value.
- Safe Tail Bridge uses only `phase_aligned_cutoff_loss_frames` that are also still before the detector's conservative ideal endpoint. It never reduces the configured freeze safety margin.
- `Stitch Ready` is for intermediate clips. `Final Clip` keeps the complete final landing.
- Video and audio seam lengths are intentionally independent: default 4 frames for video and 15 ms for audio.
- Boundary luminance matching remains available only as an **experimental fallback** and is off by default in the release workflows.
- `Stitch Saved Chain` decodes one full saved AV latent at a time and encodes H.264/AAC through PyAV, avoiding a giant all-clips IMAGE/AUDIO batch.
- If no freeze is found, Auto Handover excludes `freeze_hold - 1` final frames before selecting a valid phase-aligned cutoff.
- `<Picture 1>` is Qwen-only in the supplied conditioning nodes; it is not inserted as a persistent DiT reference latent.
- The H3 runtime wrappers are installed lazily on the first continuation use and return stock behavior for graphs without this suite's markers.

## Testing

Run the regression suite from the repository root:

```bash
python -m pip install pytest
python -m pytest -q
```

See [`VALIDATION.md`](VALIDATION.md) for the current validation notes and [`CHANGELOG.md`](CHANGELOG.md) for the main release milestones.

## License

The custom-node code is licensed under **GPL-3.0-only**. See [`LICENSE`](LICENSE).

MiniMax H3 model weights are not included and remain subject to their own license terms.
