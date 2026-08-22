# Herrgotts-H3-Infinite-Continuation-Suite

A ComfyUI node and workflow suite for creating **long MiniMax H3 videos from connected FL2VA / First-Last-Frame clips** while preserving motion and native audio between segments.

> **v1.4 introduces Native Masked AV continuation.** It keeps the freeze/brightness-safe handover that solved the observed visual seam mismatch, makes **Net New Content** the default Continue duration mode, and adds independent protected audio-tail carryover for dialogue.

## Overview

The project was built around a simple goal: get **FL2VA quality with much of the control people like about Ref2VA**, while making longer H3 sequences practical.

FL2VA gives every segment a strong visual target through First/Last Frames. Repeated Last Frames can also act as **quality resets**, pulling composition, identity and image quality back toward a clean reference before drift accumulates across a long chain.

For continuation, v1.4 changes the core approach. Instead of asking H3 to reconstruct the previous clip through guide/keyframe rows, the suite copies the previous latent directly into the new target and protects it with ComfyUI's native **separate video/audio denoise masks**. v1.4 treats visual and speech continuity as related but not identical timing problems.

Conceptually:

```text
Previous clip FULL AV latent + Auto Handover metadata
        ↓
find safe pre-freeze / pre-brightness VIDEO endpoint
        ↓
snap backward to exact Masked-AV video boundary
        ↓
protected VIDEO window ends exactly there
        +
protected AUDIO starts at the same source time
and may continue through the previous clip's real audio tail
        ↓
H3 generates the future video and, after protected audio ends, future audio
        ↓
optional Last Frame + Qwen References guide where the clip should go
```

This gives motion, framing and color a hard freeze-safe starting constraint without forcing a spoken word to end merely because the picture had to cut earlier.

Auto Handover still chooses the actual **video** continuation boundary. It excludes FL2VA's frozen / unstable landing tail and snaps the safe visual cutoff backward to the latest exact Masked-AV boundary. **The previous visible video and the next protected video context end at that same boundary.** Audio may intentionally remain protected beyond it.

## Example Generation
🎬 v1.4 Example

This example was generated using the new **Native Masked AV continuation** introduced in v1.4. It was stitched together out of 11 individual clips using the example Workflows.

[▶️ Watch the full v1.4 example video](assets/Infinite-Continuation-Suite_v1.4_Example-1.mp4)

The clips are generated individually and continued using the previous clip's video/audio latent context, then stitched into the final sequence.

Older Example (v1.2)
[Watch the 7-clip / ~61-second v1.2 example generation](https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite/releases/download/v1.2.0/h3-infinite-7-clip-example.mp4)**
That public example was generated with the older guide-based continuation path. v1.4 replaces the guide handover with native in-place latent preservation; v1.4 keeps the freeze-safe video source selection and adds independent protected audio-tail carryover plus Net New Content duration control.

### Main features

- **Native Masked AV continuation** on a current ComfyUI build with PR #15375: previous video + audio latent context is copied directly into the next target and protected in-place.
- Exact joint AV context lengths: **39 / 90 / 141 / 192 / ... frames**. The v1.4 workflows default to **39 frames (~1.625 s)**.
- Flexible **T2VA / I2VA / L2VA / FL2VA conditioning** with optional First/Last Frames.
- Auto-growing **Qwen References** with deterministic `picture_map` diagnostics.
- Repeated **Last Frame keyframe anchors** for visual control and quality resets.
- **Auto Handover** detects the frozen / unstable FL2VA landing and selects the continuation boundary. v1.4 keeps that native boundary logic instead of reconstructing legacy RoPE guide rows.
- **One freeze-safe native handover boundary:** hard freezes, visually final-state-like tails, or the conservative fallback first determine a safe visual cutoff. That cutoff is then snapped backward to the latest exact AV boundary and becomes both the Stitch Ready endpoint and the end of the next protected context window.
- Context-aware rendered video crossfade and separate audio de-click handling.
- `Full`, `Stitch Ready` and `Final Clip` output modes.
- Save / Load complete AV latents with stitch metadata.
- A **memory-bounded Saved Chain Stitcher** for very long projects generated clip by clip.
- Old v1.3 guide-based Start/Continue nodes remain registered for A/B comparison and legacy workflows.

### Why the masked approach matters

The older guide path supplied previous latent slices as temporal H3 guide/keyframe conditioning. H3 was still responsible for generating the new clip's beginning, so a future Last Frame, another visual condition or persistent runtime state could sometimes influence the opening more strongly than intended.

v1.4 uses a stricter separation:

- **Previous AV latent:** this is the preserved starting context.
- **Last Frame:** this is the optional future endpoint / quality reset.
- **Qwen References:** these describe people, clothing, objects or other visual details.

The protected prefix is not a Qwen Picture. It exists directly inside the target AV latent.

## Requirements / ComfyUI compatibility

**The v1.4 workflows require a current ComfyUI build containing native MiniMax H3 AV-mask support from PR #15375.**

ComfyUI PR #15375 added the native per-stream denoise-mask support used by v1.4. The suite checks the **actual live H3 mask capabilities** rather than trusting a version string alone, and deliberately does **not** ship a compatibility shim for older/incomplete builds.

If the v1.4 Continue node reports that Masked AV support is unavailable:

1. update ComfyUI to a current version;
2. fully restart ComfyUI;
3. reload the browser UI.

The older v1.3 guide nodes remain in the package for comparison, but the shipped v1.4 workflows use the new native-mask nodes.

## Installation

### ComfyUI Manager / Registry

Search for **Herrgotts-H3-Infinite-Continuation-Suite** in ComfyUI Manager and install it normally.

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

The `examples/` folder contains four annotated v1.4 workflows:

**1. Start — `Herrgotts_H3_Infinite_v1.4_01_Start.json`**  
Creates Clip 1 with flexible T2VA/I2VA/L2VA/FL2VA conditioning. First/Last Frames are optional; the example keeps First + Last connected because repeated endpoints are the recommended quality-reset workflow.

**2. Continue — `Herrgotts_H3_Infinite_v1.4_02_Continue.json`**  
Loads a manually selected previous AV latent **plus its Handover metadata** and creates Clip 2+. The safe 39-frame video run ending before the unusable landing tail is copied into the new target and protected by the native video mask. By default, audio starts at the same source point but can stay protected through the previous full audio tail. `Net New Content` is the default Duration mode. Add a new Last Frame and/or Qwen References as desired.

**3. 3-Clip Showcase / Auto Stitch — `Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json`**  
Runs Start -> Masked Continue -> Masked Continue in one queue and automatically creates a stitched final video. Additional continuation blocks can be duplicated for Clip 4+.

**4. Stitch Saved Chain — `Herrgotts_H3_Infinite_v1.4_04_Stitch_Saved_Chain.json`**  
Combines manually numbered clips generated separately. The stitcher decodes one saved AV latent at a time, so peak memory does not scale like one giant decoded all-clips batch. v1.4 chains use the exact shared video boundary; older experimental v1.4 metadata still retains its compatibility offset path.

See [`examples/README.md`](examples/README.md) for a compact workflow guide.

### Recommended v1.4 baseline

Recommended starting settings:

```text
ComfyUI: current build with native PR #15375 H3 AV-mask support
Continuation: H3ContinuousContinueV14 / Native Masked AV
Masked video context: 39 frames
Duration Mode: Net New Content
Audio Tail Carryover: Full Previous Tail
Audio feather: 0 ticks
Auto Handover: Balanced
Safe Tail Bridge: 0 (Advanced legacy fallback)
Video crossfade: 4 frames
Audio de-click crossfade: 15 ms
Boundary luminance matching: Off (Advanced legacy fallback)
```

With `Net New Content = 5 s`, v1.4 chooses 158 total H3 frames for a 39-frame head, leaving **119 newly generated frames (~4.96 s)**. With `Total Generation = 5 s`, the old 124-total-frame behavior remains and leaves 85 new frames (~3.54 s).

## Prompting Guidance

For the best long-form control, treat each segment like a short storyboard transition:

1. describe the action/motion that should happen during this segment;
2. use a Last Frame when you want a strong endpoint / quality reset;
3. use Qwen References for identity, clothing or visual details and refer to the current `picture_map` rather than assuming fixed Picture numbers;
4. v1.4 can carry existing dialogue beyond the visual handover, but still avoid placing a critical word exactly beyond the **actual end of the source clip**, because audio that was never generated cannot be preserved.

The masked previous AV context does **not** need to be mentioned in the prompt. It is already present in the target latent.

## v1.4 native Masked AV continuation

### Exact AV context lengths

H3's video and audio timelines do not share every possible pixel-frame boundary. Native Masked AV therefore uses context lengths that are exact for both streams:

```text
39, 90, 141, 192, ... frames
```

The supplied workflows use **39 frames** by default. At 24 fps this is about **1.625 seconds** of preserved AV context and corresponds to exactly **65 audio-latent ticks** at H3's 40 Hz audio latent rate.

If a requested context is too large for the source or target, the node snaps down to the largest valid option. It refuses to let the protected context consume the entire new target because there must still be future frames to generate.

### Independent audio-tail protection

v1.4 keeps the freeze/brightness-safe **video** handover, but no longer forces useful audio to stop at a visually motivated cut. The two native H3 masks are independent.

Recommended defaults:

```text
Audio Tail Carryover = Full Previous Tail
audio_feather_ticks = 0
```

With the default 39-frame video context, the first 65 audio-latent ticks still correspond exactly to the protected video head. If the previous full latent contains additional valid speech after the safe visual handover, v1.4 can copy and hard-protect those later audio ticks too. After the normal 39-frame duplicate head is removed during stitching, that extra carried audio remains at the visible beginning of the new clip while H3 generates new video around it.

`Match Video Handover` reproduces the video-matched audio behavior for A/B testing. `audio_feather_ticks` remains an Advanced compatibility/experimental control and should normally stay at `0`, especially for dialogue. Audio carryover can only preserve audio that already exists in the previous latent; if the source clip itself ends mid-word, the missing continuation still has to be generated.

### Duration mode: Net New Content

v1.4 makes **Net New Content** the default interpretation of Continue `Duration`. Instead of counting the protected 39-frame video head against the requested duration, the node chooses the nearest valid H3 `17k+5` total length so that roughly the requested duration remains as newly generated visible video after that head is removed.

Example at 24 fps:

```text
Duration = 5.0 s
Net New Content -> 158 total frames - 39 protected = 119 new frames (~4.96 s)
Total Generation -> 124 total frames - 39 protected = 85 new frames (~3.54 s)
```

This is a convenience/authoring feature, **not a speed optimization**. Net New Content samples a longer total latent, so sampling time and memory usage increase accordingly. `Total Generation` remains available when faster/shorter continuation passes are preferred.

### Auto Handover defines one shared video boundary

v1.4 uses the validated freeze-safe source selection in Auto Handover. The detector first proposes a safe visual endpoint, then the analyzer snaps that endpoint backward to the latest exact shared AV boundary:

```text
Hard freeze detected        -> detector's safe pixel endpoint
Soft final-state tail found  -> trim dynamically before that tail + safety margin
No usable candidate          -> conservative visual fallback (11 frames with Balanced defaults)
                               -> then snap to exact AV boundary
```

The protected **video** continuation source ends at the same freeze-safe boundary used by Stitch Ready. Audio may extend independently beyond that point when `Full Previous Tail` is enabled.

Because exact shared AV boundaries are discrete, this final snap can move the handover up to **16 additional rendered frames earlier** than the detector's ideal visual cutoff. That is intentional: v1.4 keeps this conservative rule because live testing of later-frame recovery produced visible motion/alignment errors. It prioritizes a clean, internally consistent seam over retaining those grid-lost frames.

### Stitch alignment with the shared video boundary

v1.4 uses one shared video boundary for the previous visible clip and the next protected context. If Clip 1 is kept through frame 106, the protected head of Clip 2 contains the safe source history ending at frame 106. The complete duplicated head is removed from Clip 2, and the normal context-aligned crossfade uses the **end of that head** (`context offset = 0`).

The older nonzero masked-head offset logic remains only for saved experimental early-v1.4 chains whose protected source came from the true final tail.

The old **Safe Tail Bridge** remains available for legacy guide chains, but v1.4 workflows default it to `0`.

### Picture mapping

Picture mapping keeps the released v1.3 behavior.

Start with First + Last + two Qwen References:

```text
Picture 1 = First Frame
Picture 2 = Last Frame
Picture 3 = Qwen Reference 1
Picture 4 = Qwen Reference 2
```

Continue with Last + two Qwen References:

```text
Previous masked AV context = not a Picture
Picture 1 = Last Frame
Picture 2 = Qwen Reference 1
Picture 3 = Qwen Reference 2
```

The `picture_map` output and console log show the actual mapping for each run.

Qwen References are Qwen text/vision inputs only; they are not inserted into `minimax_refs` as persistent native Ref2VA/DiT reference latents.

## Included Nodes

| Node | Purpose | Important v1.4 behavior |
|---|---|---|
| **H3 Infinite - Flexible Start / Conditioning v1.4** | Creates Clip 1. | Same flexible conditioning behavior as v1.3. |
| **H3 Infinite - Continue from Latent v1.4** | Creates Clip 2+ with native in-place AV preservation. | Protects a freeze/brightness-safe video window and, by default, independently protects the previous full audio tail; Net New Content is the Duration default. |
| **H3 Infinite - Auto Handover v1.4** | Detects the frozen / unstable FL2VA landing. | Produces the one AV-compatible boundary shared by Stitch Ready and the next Continue source. |
| **H3 Infinite - Output / Stitch v1.4** | Prepares one rendered segment. | `Full`, `Stitch Ready`, `Final Clip`. |
| **H3 Infinite - Seamless AV Join v1.4** | Joins a current timeline to the next decoded clip. | Uses the stable shared video boundary. Experimental seam fallbacks are Advanced/off; compatibility offset remains for saved early-v1.4 chains. |
| **H3 Infinite - Stitch Saved Chain v1.4** | Memory-bounded final assembly of saved clips. | Uses the saved shared boundary; also retains older masked-head-offset compatibility. |
| **H3 Infinite - Save AV Latent** | Saves the complete video+audio latent and metadata. | Keep sequential clip indices. |
| **H3 Infinite - Load AV Latent** | Loads a saved full AV latent. | Manual index selection remains unchanged. |
| **H3 Infinite - Latent Info** | Shows AV latent information. | Useful for troubleshooting. |

The v1.3 Start/Continue classes and v1.2 stitch classes remain registered for workflow compatibility and A/B testing. The shipped v1.4 workflows use the v1.4 nodes.

## Examples

If the suite works well for you, example videos are very welcome. Open a GitHub Issue with a short description of the settings/workflow and a link to the result. With permission, good examples can be added to the GitHub showcase with credit.

Bug reports are equally useful. Please include the relevant console log and, when possible, the workflow JSON.

## Limitations / Known Issues

- **Native Masked AV continuation has passed live testing for the targeted visual and dialogue seam cases.** The freeze/brightness-safe video handover removed the observed brightness mismatch, and independent audio-tail carryover preserved dialogue that extended beyond the visual cut.
- **A current ComfyUI build containing PR #15375 is required** for v1.4 Masked AV. The node probes the live H3 implementation and fails with an actionable update message if native support is incomplete. Older builds can still use the registered legacy guide nodes but not the v1.4 workflows.
- **The 39-frame protected video prefix still exists internally.** `Net New Content` compensates by sampling a longer total sequence, but that increases sampling time/memory; it does not make the context free.
- **Very large context choices leave less new generation time.** 90/141/192 are experimental options; 39 is the recommended starting point.
- **Audio quality may drift over very long chains.** Visual quality can repeatedly reset toward new Last Frames; there is currently no equivalent HQ audio reset.
- **Dialogue tail carryover only preserves existing source audio.** `Full Previous Tail` can retain valid speech that continues into visually discarded frames, but it cannot recover phonemes that were never generated because the original clip itself ended mid-word.
- **Qwen References are a hybrid extension, not native Ref2VA references.** They are Qwen-only Pictures.
- **Keyframe-free continuation is less tested.** It removes the repeated visual endpoint/reset that motivated the FL2VA workflow.
- **Runtime/session stability still needs targeted testing.** v1.3 occasionally produced a bad continuation start that could be cleared by restarting ComfyUI. Native Masked AV is intended to remove the guide-path dependency involved in that failure mode, and v1.4 live testing has been promising; repeated same-session testing should still continue before the historical issue is considered fully closed.
- **Optional SageAttention can affect memory/stability independently of continuation.** If you see repeatable OOMs, disable it first when troubleshooting.
- **Hardware-limited testing.** Please report unexpected behavior with workflow JSON and console logs.

## Development History

The project began with repeated H3 FL2VA keyframes plus direct video/audio latent continuation.

Important milestones:

1. **Freeze-aware FL2VA handover:** fixed trimming was replaced with visual freeze detection because Last-Frame lock duration varies by clip.
2. **Guide phase alignment:** the old continuation path had to place reused latent guide rows on valid H3 temporal phases to avoid startup flicker.
3. **Rendered seam handling:** context-aware video smoothing and a short audio de-click transition improved separately decoded clip boundaries.
4. **Memory-bounded long-chain assembly:** complete AV latents plus metadata can be stitched sequentially instead of decoding an entire project at once.
5. **v1.3 flexible conditioning:** optional First/Last Frames and multiple Qwen Pictures added much more reference control while keeping FL2VA generation.
6. **v1.4 native Masked AV:** after ComfyUI added per-stream H3 denoise masks, continuation moved from regenerated guide/keyframe context to direct in-place preservation. v1.4 combines freeze-safe pre-tail video source selection with a stitch-identical Masked-AV boundary, Net New Content duration semantics, and independent audio-tail protection beyond an earlier visual cut.

## Acknowledgments

- **[MiniMax / MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3)** — underlying audiovisual model and H3 prompting behavior.
- **[ComfyUI](https://github.com/Comfy-Org/ComfyUI)** and **Comfy-Org's MiniMax H3 integration** — native H3 implementation, latent/VAE support and the Masked AV primitives used by v1.4.
- **[ComfyUI-H3-Motion-Context-MultiRef](https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef)** — useful public reference for native masked H3 AV-context handling and exact joint AV context lengths.
- **[ComfyUI-MiniMaxH3-Contex-Loop](https://github.com/ethanfel/ComfyUI-MiniMaxH3-Contex-Loop)** — useful comparison between guide and masked continuation approaches.
- **[ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)** — optional Patch Sage Attention KJ node used during testing.
- **[SageAttention](https://github.com/thu-ml/SageAttention)** — optional attention acceleration.
- **[safetensors](https://github.com/huggingface/safetensors)** — AV latent + metadata storage.
- **ChatGPT by OpenAI (GPT-5.6 Sol)** — substantial assistance with implementation, debugging, regression-test design and documentation.

**Author / maintainer:** [HerrgottMargott](https://github.com/HerrgottMargott)

OpenAI is not a maintainer, sponsor or publisher of this project.

## Technical Notes

- H3 runs at 24 fps and uses a `17k+5` temporal frame grid. `10.0 s` becomes 243 actual frames (~10.125 s).
- v1.4 continuation uses the **full sampler AV latent**, not a decoded/re-encoded handover.
- Exact joint masked AV context lengths are `39 + 51k` pixel frames.
- Default 39-frame context corresponds to 12 H3 video-latent temporal steps and 65 H3 audio-latent ticks.
- Video is copied from the freeze-safe source window ending at the shared visual/Masked-AV boundary. By default, audio starts at the same source point but may extend through the previous full latent tail.
- The copied video prefix receives native denoise mask `0` (preserve); future video receives `1` (generate).
- `Audio Tail Carryover = Full Previous Tail` and `audio_feather_ticks = 0` are v1.4 defaults. The feather control remains Advanced/experimental for compatibility.
- Auto Handover v1.4 first proposes a safe visual endpoint: hard freezes use the detector endpoint, soft final-state consensus can provide an earlier fallback, and a fully ambiguous case uses the 11-frame Balanced safety. v1.4 keeps the validated video path's snap: the endpoint is moved backward to the latest exact video-context boundary and used for both visible video stitching and protected video continuation.
- `actual_head_context_frames` is the correct reused-head trim value for stitching.
- v1.4 uses `context offset = 0` for new chains: the previous visible video endpoint is the same source endpoint represented by the end of the next protected video head. Nonzero offset mapping is retained only for saved experimental early-v1.4 metadata.
- Safe Tail Bridge defaults to `0` and is Advanced because live rejected later-frame recovery recovery/bridging of grid-lost motion produced visible alignment errors. It remains available for legacy guide/A-B chains.
- `Stitch Ready` is for intermediate clips. `Final Clip` keeps the complete final landing.
- Video and audio seam lengths remain independently configurable.
- `Stitch Saved Chain` decodes one saved AV latent at a time and encodes H.264/AAC through PyAV, avoiding a giant all-clips IMAGE/AUDIO batch.
- v1.4 Continue intentionally does **not** install/use the old guide runtime patches. Legacy v1.3 nodes retain their own compatibility path.

## Testing

Run the regression suite from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

See [`VALIDATION.md`](VALIDATION.md) for v1.4 validation status and [`CHANGELOG.md`](CHANGELOG.md) for the main milestones.

## License

The custom-node code is licensed under **GPL-3.0-only**. See [`LICENSE`](LICENSE).

MiniMax H3 model weights are not included and remain subject to their own license terms.
