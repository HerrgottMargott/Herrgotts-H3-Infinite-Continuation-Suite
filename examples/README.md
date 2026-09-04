# Example workflows — v1.4

The v1.4 examples use **native Masked AV continuation** and require a current ComfyUI build containing PR #15375 H3 AV-mask support.

v1.4 uses the validated video architecture: Auto Handover finds a freeze/brightness-safe visual endpoint, snaps it to the exact Masked-AV video boundary, `Stitch Ready` ends there, and the next protected video context ends at that same source point.

Recommended v1.4 defaults:

```text
Duration Mode: Net New Content (default)
Audio Tail Carryover: Full Previous Tail (default)
Audio feather: 0 ticks
Safe Tail Bridge: 0
Luminance Match: Off
```

`Net New Content` samples a longer total latent so the requested Continue duration approximately describes newly generated visible video after the protected head. It therefore increases sampling time/memory compared with `Total Generation`.

`Full Previous Tail` keeps the safe video cut but allows valid original audio to remain protected beyond that cut. This is intended for dialogue that continues into video frames discarded because of freeze/brightness landing. `Match Video Handover` reproduces video-matched audio behavior.

## 1. `Herrgotts_H3_Infinite_v1.4_01_Start.json`

Creates Clip 1 with flexible T2VA/I2VA/L2VA/FL2VA conditioning. First/Last Frames remain optional. The example uses First + Last because repeated endpoints are the recommended quality-reset workflow. Auto Handover analyzes the rendered result and the full AV latent is saved with its handover metadata.

## 2. `Herrgotts_H3_Infinite_v1.4_02_Continue.json`

Loads the previous full AV latent **and its handover metadata**. The Continue node protects the safe 39-frame video history ending before the unusable landing tail. Audio starts at the same source position but, by default, stays protected through the previous clip's actual end.

Picture mapping keeps v1.3 semantics:

```text
Previous masked AV context = not a Picture
Last Frame = Picture 1 (when connected)
Qwen Reference 1 = Picture 2
Qwen Reference 2 = Picture 3
...
```

Save / Load clip indices remain manual and predictable.

## 3. `Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json`

Complete one-queue demonstration:

```text
Clip 1 Start
→ Clip 2 Native Masked AV Continue
→ Clip 3 Native Masked AV Continue
→ v1.4 Seamless AV Joins
→ final video
```

The stable shared video seam is used throughout. Later-frame recovery is intentionally not used because live testing showed visible motion/alignment errors and no net-new content benefit. Extra protected audio is already embedded in each next latent and remains naturally after the normal duplicate-head trim.

## 4. `Herrgotts_H3_Infinite_v1.4_04_Stitch_Saved_Chain.json`

For long projects generated clip-by-clip. It decodes one saved AV latent at a time, uses the saved safe video boundary/head metadata, and preserves extended audio tails automatically. Peak memory stays tied roughly to one decoded clip rather than the whole chain. Older v1.3 and experimental v1.4 metadata remain supported for compatibility.

## 5. `Herrgotts_H3_Infinite_v1.4_05_EncodeExistingVideo.json`

Encodes an existing/loaded video (video + optional audio) into an H3 AV latent so it can be saved and continued from. The workflow:

```text
VHS_LoadVideo
→ H3ContinuousTrimToBoundary  (snap to exact 39 + 51k-frame joint AV boundary)
  → VAEEncode (H3 video VAE)      → video latent  [1,24,T,H/16,W/16]
  → VAEEncodeAudio (H3 audio VAE) → audio latent  [1,32,2,T]
  → handover  (continues from the trimmed clip's absolute end)
→ LTXVConcatAVLatent  (video + audio → joint NestedTensor AV latent)
→ H3ContinuousSaveLatent (handover included)  → h3_continuous/clip_00001.safetensors
```

Continuation side: reload with `H3ContinuousLoadLatent` and feed the Continue workflow. The trim node's handover is saved with the clip, so the reloaded latent carries valid continuation metadata for `H3ContinuousContinueV14` — no manual `landing_tail_frames` is needed. The frame count must match the continuation target's resolution, and is already snapped to a clean 24 fps / 40 Hz boundary by the trim node.

## Dialogue testing

For speech, keep `audio_feather_ticks = 0`. A useful A/B test is a clip whose video becomes unusable before a spoken word has fully finished:

- `Full Previous Tail`: should preserve the already-generated word ending in Clip 2 while video begins generating after the safe visual seam.
- `Match Video Handover`: intentionally cuts protected audio at the visual seam and reproduces the validated video path behavior.

If the original source clip itself ends before the word is complete, v1.4 cannot preserve audio that does not exist.
