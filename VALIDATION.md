# v1.2.2 validation notes


## ComfyUI 0.33 compatibility

The v1.2.1 continuation path was live-tested on an updated ComfyUI installation and failed closed at first Continue use with:

```text
PackedLayout.__init__() got an unexpected keyword argument 'frame_count'
```

The paired payload hook rolled back successfully, confirming the existing atomic failure behavior. v1.2.2 replaces that version-specific assumption with live API detection.

Automated tests now cover both supported layouts:

- legacy H3 API with `frame_count`: keep the v1.2.1 interior-keyframe + payload compatibility path;
- native H3 API without `frame_count`: use stock arbitrary keyframe indices, skip the payload monkey patch, and retain only the marker-gated direct-audio timeline correction.

The native path additionally self-tests interior keyframe placement, exact end-aligned audio coordinates, and stock-equivalent behavior for unmarked H3 graphs before installing its wrapper.

A first live Continue generation on ComfyUI 0.33 completed successfully through sampling, saving, visual continuation, audio continuation and the new Last Frame landing. A subsequent Continue in the same ComfyUI process exposed a lifecycle bug in candidate 3: runtime API re-detection inspected the suite's already-installed generic wrapper instead of recognizing it as the active native-mode wrapper. Candidate 4 fixes that repeated-Continue path and adds a regression test that reproduces the Clip 3+ call sequence.

**Repeated live Continue generation on ComfyUI 0.33 was completed successfully after the candidate-4 lifecycle fix.** The tested chain continued again in the same ComfyUI process without the API re-detection failure, confirming Clip 3+ reuse of the already-installed native audio-only layout wrapper.

## Automated validation

The release regression suite covers:

- H3 temporal/phase-aligned latent timeline math.
- Stable-tail freeze detection and Auto Handover presets.
- No-Lock Fallback behavior.
- Direct AV continuation metadata and saved head-context metadata.
- Lazy/marker-gated runtime patch isolation and conflict detection.
- Full / Stitch Ready / Final Clip trim planning.
- Context-aligned video/audio seam math.
- 15 ms audio de-click crossfade duration and sample-exact A/V alignment.
- Safe Tail Bridge eligibility, safety-cap behavior and unchanged final timeline duration.
- Example-workflow model/VAE wiring and release seam defaults.

Current v1.2.2 release result: **72/72 regression tests passing**.

Run from the repository root:

```bash
python -m pytest -q
```

## Empirical ComfyUI validation before v1.2

- Balanced freeze detection was manually checked against roughly ten H3 clips and matched the visible freeze boundary very closely in those tests.
- Direct latent continuation preserved strong movement and native audio across boundaries.
- The phase-aligned extended context removed startup flicker seen with earlier arbitrary latent cut positions.
- A full three-clip showcase completed successfully with 243-frame segments, dynamic 22/26-frame continuation contexts and `Final Clip` preserving the last keyframe landing.
- Saved Chain Stitching completed on the same three saved clips with **617 video frames @ 24 fps**, **822667 audio samples @ 32000 Hz** and **A/V sample rounding delta 0**.
- The **15 ms audio de-click crossfade** was subjectively reported as seamless in live testing.
- A 4-frame video crossfade reduced the visible seam but left a small brightness change. Increasing it to 8 frames only spread that change over a longer interval.
- Boundary luminance matching successfully measured the decode-to-decode brightness difference, but live frame inspection showed that fading the gain could turn the seam into a visible brightness drift. It is therefore retained only as an experimental fallback and disabled by default in v1.2.

## v1.2 live Safe Tail Bridge validation

A seven-clip Saved Chain Stitching run completed successfully with:

- **1467 video frames @ 24 fps** = 61.125 s.
- **1,956,000 audio samples @ 32,000 Hz** = 61.125 s.
- **A/V sample rounding delta 0**.
- Safe Tail Bridge `2` frames at all six continuation joins.
- Video crossfade `4` frames, audio de-click crossfade `15 ms`, boundary luminance matching off.
- Subjective result reported as **very good**; a few isolated slightly brighter frames remained but were barely noticeable.

This validates the release-default Safe Tail Bridge timeline behavior across a longer seven-segment chain.

## v1.2.1 Manager metadata hotfix

The v1.2.1 patch adds two redundant identification paths for ComfyUI Manager:

1. `node_list.json` explicitly lists every registered node class.
2. Every suite node in every shipped workflow contains the Registry package ID `herrgotts-h3-infinite-continuation-suite`, version `1.2.1`, and an exact `Node name for S&R` matching its workflow node type.

No generation, freeze-detection, continuation, stitching or runtime-patch logic changed in v1.2.1.

