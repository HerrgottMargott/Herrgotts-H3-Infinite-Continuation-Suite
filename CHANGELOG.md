# Changelog

Only major user-facing or technically important milestones are listed here. Experimental micro-iterations are intentionally omitted.

## 1.2.2 — ComfyUI 0.33 compatibility

- Added runtime detection for the new ComfyUI 0.33 MiniMax H3 layout API, where `PackedLayout.__init__` no longer exposes the legacy `frame_count` argument.
- On the new API, continuation video anchors now use native `resolved_frame_index` placement instead of the old interior-keyframe marker workaround.
- The legacy `MiniMaxH3.extra_conds` payload monkey patch is skipped on the new API because ComfyUI now preserves keyframes together with reference payloads natively.
- Retained a much smaller marker-gated layout wrapper only for direct-audio continuation timing. It moves the carried audio latent onto the new clip timeline so its end matches the video continuation boundary.
- Reworked the native audio timing correction to depend only on the live `position_ids` timeline plus ComfyUI's reference-cursor arithmetic, avoiding assumptions about the refactored 0.33 segment/update-map containers.
- Added separate live self-tests for legacy and native H3 layout APIs. Unmarked H3 workflows must remain identical to stock behavior in both modes.
- Fixed repeated Continue calls in one ComfyUI session: runtime detection now recognizes the suite's already-installed native layout wrapper and preserves the original constructor signature for introspection, preventing Clip 3+ from being misidentified as an unknown H3 API.
- Older ComfyUI H3 layouts remain supported through the existing lazy legacy compatibility path.
- Updated workflow Registry metadata to `1.2.2`.

## 1.2.1 — ComfyUI Manager integration hotfix

- Added explicit `node_list.json` coverage for all registered suite nodes.
- Embedded `cnr_id = herrgotts-h3-infinite-continuation-suite` and `ver = 1.2.1` into every suite node in all four shipped workflows, and normalized `Node name for S&R` to the actual registered node type. This improves **Check Missing Custom Nodes / Install Missing Custom Nodes** identification without changing generation or stitching behavior.

## 1.2.0 — First public release candidate

- Added **Safe Tail Bridge** for video seams. When phase alignment forces the latent handover 1–3 frames before Auto Handover's already-safe ideal endpoint, the stitcher can keep up to **2** of those exact rendered frames from the previous clip and skip the same number of early video frames in the next clip. The detector safety margin and total timeline length remain unchanged.
- Kept the tested seam defaults at **4 context-aligned video crossfade frames + 15 ms audio de-click crossfade**. Audio timing is intentionally independent from Safe Tail Bridge.
- Boundary luminance matching remains available as an **experimental fallback**, but is now **off by default** after live testing showed that it could turn a short brightness seam into a longer brightness drift.
- Updated the 3-clip Auto-Stitch and Saved-Chain workflows to use Safe Tail Bridge and refreshed all in-canvas guidance.
- Reworked the public README: clearer FFLF quality-reset / keyframe-control positioning, Prompting Guidance, current limitations/OOM observations, simplified node descriptions and less development-detail noise.
- Public node display names now use **v1.2** while the existing internal class IDs remain registered for workflow compatibility.

## 1.1 — Release hardening and complete long-form workflow

- Added `Balanced`, `Motion Safe` and `Custom` Auto Handover presets plus the No-Lock Fallback.
- Added `Full`, `Stitch Ready` and `Final Clip` output modes.
- Added the annotated Start, Continue and 3-clip automatic-stitch workflows.
- Added context-aligned rendered video smoothing and the separately tuned **15 ms audio de-click crossfade**.
- Added self-describing saved AV latents and the **memory-bounded Stitch Saved Chain** workflow/node.
- Changed H3 runtime hooks to lazy, marker-gated installation with compatibility self-checks and explicit conflict detection instead of patching ComfyUI at startup.

## 1.0 — Usable release interface

- Switched from raw frame counts to **Duration (Seconds)**.
- Added non-destructive full AV latent Save / Load support and rendered-output trimming.
- Kept older experimental alignment/safety modes as Legacy options for reproducibility.

## 0.x — Core continuation research

- Built the first direct **video + audio latent continuation** prototype.
- Added automatic FL2VA freeze-tail detection after fixed trimming proved unreliable.
- Reworked freeze detection into the current stable-tail / residual-motion approach.
- Solved continuation startup flicker with **`phase_aligned_extended`** context selection.
- Restored native First/Last-Frame anchoring while keeping optional `<Picture 1>` Qwen-only.
