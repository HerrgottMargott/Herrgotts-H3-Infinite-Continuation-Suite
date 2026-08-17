# Example workflows

All examples include in-canvas guidance for the v1.3 conditioning rules, Qwen Picture mapping, continuation settings and stitching behavior.

## 1. `Herrgotts_H3_Infinite_v1.3_01_Start.json`
Creates Clip 1 with **H3 Infinite - Flexible Start / Conditioning v1.3**.

First Frame and Last Frame are independent optional inputs, so the same node can run as:

- **T2VA** — no keyframes
- **I2VA** — First Frame only
- **L2VA** — Last Frame only
- **FL2VA** — First + Last Frame

The workflow still connects First + Last by default because repeated keyframe anchors — especially Last Frames — are the recommended Infinite Continuation path for periodic visual **quality resets**. Qwen Reference 1 is optional; connecting it reveals additional Qwen Reference sockets automatically.

The workflow analyzes the end boundary and saves the **full AV latent** for later continuation or Saved Chain Stitching.

## 2. `Herrgotts_H3_Infinite_v1.3_02_Continue.json`
Loads a manually selected saved AV latent and creates Clip 2+ with **H3 Infinite - Continue from Latent v1.3**.

The new Last Frame is optional, but recommended for long chains because it provides a fresh endpoint / quality-reset keyframe. Qwen References are optional and auto-grow from Reference 1 onward. The direct latent handover itself is not a Qwen Picture.

Recommended continuation settings remain selected (`auto`, `phase_aligned_extended`, context 22). Save / Load clip indices remain manual and predictable.

## 3. `Herrgotts_H3_Infinite_v1.3_03_3Clip_Showcase_AutoStitch.json`
Complete one-queue demonstration:

`Clip 1 Flexible Start -> Clip 2 Continue -> Clip 3 Continue -> Seamless AV Joins -> Save final video`

The example intentionally uses First + Last for Clip 1 and a new Last Frame for each continuation because that is the recommended quality-reset workflow, even though the v1.3 inputs are optional.

Release seam defaults remain **Safe Tail Bridge max 2 frames**, **4 context-aligned video crossfade frames** and a separate **15 ms audio de-click crossfade**. Boundary luminance matching remains an experimental fallback and is off by default.

## 4. `Herrgotts_H3_Infinite_v1.3_04_Stitch_Saved_Chain.json`
For longer projects generated clip-by-clip. It loads the manually numbered full AV latents, reconstructs saved boundaries, applies the same proven Safe Tail Bridge / seam logic and writes a final MP4.

The stitcher decodes **one clip at a time**, so peak RAM/VRAM does not grow with total chain length in the same way as a giant decoded IMAGE/AUDIO batch.
