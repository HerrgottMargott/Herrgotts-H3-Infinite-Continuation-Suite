# v1.4.0 validation notes

v1.4.0 moves continuation to ComfyUI's native MiniMax H3 Masked-AV path while preserving the suite's freeze/brightness-safe source selection. The released build uses one shared safe video boundary for rendering and continuation, defaults Continue duration to Net New Content, and can independently preserve useful audio beyond the visual handover.

## Intended behavior

- require a current ComfyUI build containing native PR #15375 H3 AV-mask support;
- detect and exclude the unusable FL2VA freeze / brightness landing from the protected **video** source;
- snap the safe visual endpoint backward to the latest exact Masked-AV video boundary and use that same endpoint for Stitch Ready and the next protected video head;
- default to 39 protected video frames;
- default `Duration Mode` to **Net New Content**, so requested Continue duration approximates newly generated visible video after the protected head;
- default `Audio Tail Carryover` to **Full Previous Tail**, allowing audio to remain protected beyond the visual handover through valid audio already present in the previous full latent;
- keep `audio_feather_ticks = 0` for hard dialogue protection;
- preserve `Match Video Handover` and `Total Generation` as direct A/B/legacy-semantics fallbacks;
- keep Safe Tail Bridge and luminance matching Advanced/off for new native-mask chains;
- retain older node registrations and saved-metadata compatibility so existing workflows remain loadable.

## Geometry examples

Default 39-frame protected video context:

- 39 rendered frames (~1.625 s at 24 fps);
- 12 H3 video-latent temporal steps;
- 65 corresponding audio-latent ticks at 40 Hz.

Audio may be longer. Example for a 124-frame previous clip with safe video source frames 68..106:

- video protected source: frames 68..106 (39 frames);
- matching audio prefix: ticks 113..177 (65 ticks);
- `Full Previous Tail`: ticks 113..206 (94 ticks total), adding 29 protected ticks / 0.725 s of original audio beyond the visual handover.

Five-second duration example with 39-frame context:

- `Net New Content`: 158 total frames -> 119 new frames (~4.96 s);
- `Total Generation`: 124 total frames -> 85 new frames (~3.54 s).

Net New Content is not a speed optimization; its longer target increases sampling work.

## Automated regression suite

Run from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Release result: **110 passed**.

Coverage includes existing freeze/motion, H3 geometry, Qwen, save/load and stitching regressions plus:

- Net New Content and Total Generation frame planning;
- independent full-tail vs video-matched audio context planning;
- hard 39-frame / 65-tick baseline geometry;
- v1.4 workflow defaults and Registry metadata;
- absence of the rejected Alignment Recovery experiment from v1.4 public workflows/nodes;
- Advanced/default-off status for legacy seam fallbacks.

## Static / package checks

The release is checked for Python compilation, valid workflow JSON, graph-link consistency, consistent `1.4.0` Registry metadata, native mask capability guards, and clean install/source archives.

## Live validation status

The v1.4 video path has been live-tested successfully, including removal of the previously observed brightness mismatch. Independent audio-tail carryover has also been live-tested on a dialogue seam where speech extended beyond the safe visual handover, and the carried audio remained continuous.

The release still retains conservative fallbacks and older node registrations for compatibility. Important limitation: audio-tail carryover can preserve only audio that already exists in the previous full latent. If the source clip itself ends mid-word, missing phonemes cannot be recovered from latent carryover.

No model weights are included.
