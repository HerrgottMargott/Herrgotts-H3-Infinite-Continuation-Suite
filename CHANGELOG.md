# Changelog

Only major user-facing or technically important milestones are listed here. Experimental micro-iterations are intentionally omitted.

## 1.4.1 — Encode an existing video and continue from it

- Adds **`H3ContinuousTrimToBoundary`**: snaps an existing/loaded video (and optional aligned audio) down to the largest exact joint 24 fps / 40 Hz Masked-AV boundary (`39 + 51k` frames) so the result lands on a clean shared video/audio grid that the continuation nodes can work with cleanly.
- Adds the **`Herrgotts_H3_Infinite_v1.4_05_EncodeExistingVideo.json`** example workflow: `VHS_LoadVideo -> TrimToBoundary -> VAEEncode (H3 video VAE) + VAEEncodeAudio (H3 audio VAE) -> LTXVConcatAVLatent -> H3ContinuousSaveLatent`. This produces a `.safetensors` identical to a normally saved clip, which `H3ContinuousLoadLatent` reloads for continuation.
- `H3ContinuousTrimToBoundary` now also emits a valid H3 handover that continues from the trimmed clip's absolute end. Wiring that handover into `H3ContinuousSaveLatent` stores it with the clip, so the reloaded latent carries continuation metadata that `H3ContinuousContinueV14` accepts automatically — the manual `landing_tail_frames` workaround is no longer required. Resolution must still match the continuation target.

## 1.4.0 — Native Masked AV continuation + independent dialogue tail

- Uses the **live-validated freeze/brightness-safe video continuation path**: Auto Handover selects a freeze/brightness-safe visual endpoint, snaps it to the exact Masked-AV video boundary, and both Stitch Ready and the next protected video context use that same point.
- Drops the Candidate-5 Alignment Recovery experiment. Live testing with `Balanced` showed visible motion/alignment errors, and the method did not add net-new timeline content because every recovered old frame required skipping a corresponding newly generated frame. The released v1.4 workflows expose no recovery mode.
- Adds **Duration Mode** to v1.4 Continue and makes `Net New Content` the default. The node chooses the nearest legal H3 `17k+5` total so approximately the requested duration remains after the protected video head is removed. `Total Generation` preserves the old duration semantics. Net New Content samples a longer latent and therefore increases sampling time/memory.
- Adds **Audio Tail Carryover** with `Full Previous Tail` as the default and `Match Video Handover` as the conservative A/B fallback. The protected video still stops at the safe visual boundary, while audio can remain hard-protected through the previous clip's actual remaining audio tail. This is intended to preserve dialogue/phoneme endings that continue into visually discarded freeze/brightness frames.
- Keeps `audio_feather_ticks = 0` as the recommended dialogue setting and marks it Advanced. Safe Tail Bridge and luminance matching also remain as Advanced legacy/diagnostic fallbacks with v1.4 defaults off/zero.
- Retains all legacy node class registrations and runtime-patch modules so existing v1.3/v1.2/older workflows do not break. A larger cleanup of those compatibility layers is deferred to a future breaking major release.
- Live H3 testing confirmed the targeted visual seam and dialogue-tail cases before release.

## 1.4.0-rc4 — Freeze-safe native Masked AV handover

- Restores the original suite's key safety rule: continuation context is selected **before** the unusable FL2VA freeze / brightness landing instead of copying the true final latent tail.
- Auto Handover now produces one shared boundary: hard-freeze / soft-final-state / conservative safety first determines a safe visual cutoff, then that cutoff is snapped backward to the latest exact native Masked-AV boundary.
- `Stitch Ready` trims Clip N to that exact AV-compatible boundary, while Clip N+1 protects the 39-frame (or larger exact) AV context ending at the same boundary. This prevents a temporal mismatch between what is shown and what is reused.
- Continue once again consumes the previous clip's `H3_CONTINUOUS_HANDOVER` metadata. Separate workflows receive it from `Load AV Latent`; the 3-clip showcase connects the previous analyzer directly.
- Candidate 1-3 `true_final_tail` saved metadata remains stitchable through the existing offset compatibility path, but Candidate 4 generation requires a safe handover input.
- Added v1.4 Qwen-reference frontend autogrow registration and regression coverage for the shared safe boundary.
- Candidate 4 remains a **live testing** release candidate; the main validation target is freeze-free stitching with no temporal jump at the shared boundary.

## 1.4.0-rc3 — Adaptive render freeze guard

- Live testing of Candidate 2 showed that the fixed 7-frame No-Lock trim could still leave a few visible FL2VA freeze frames in the final stitched result.
- Added a **soft final-state render guard**. The existing detector now exposes the earliest tail that already matches the final visual state even when the stricter residual-motion gate rejects it because of tiny shimmer/micro-motion.
- `Stitch Ready` uses that soft candidate dynamically: it trims to just before the final-state-like tail plus the configured safety margin, without changing the Masked-AV continuation source.
- If neither a hard freeze nor a soft final-state candidate is available, the render-only fallback is now one full `freeze_hold` plus `safety_margin` (11 frames with the Balanced defaults) instead of the fixed 7-frame Candidate-2 fallback.
- The native Masked-AV Continue path remains unchanged: it still copies and protects the true final 39-frame AV latent tail. Crossfade anchoring continues to use the actual rendered tail trim, so removed freeze frames are not reintroduced through the next protected head.
- Added regression coverage for soft-candidate metadata, adaptive render trimming and v1.4 analyzer wiring.

## 1.4.0-rc2 — Render-only freeze safety for Masked AV

- Live testing confirmed the native Masked-AV continuation path works, but Candidate 1 could still leave short FL2VA freeze tails in the stitched result when the detector did not confidently classify the ending as frozen.
- Reintroduced the proven **hold-minus-one No-Lock safety** as a **render/stitch-only** fallback. With the default `freeze_hold = 8`, Stitch Ready removes 7 ending frames when no freeze is detected.
- Crucially, this safety trim no longer changes the continuation source: the next v1.4 clip still receives the true final 39-frame AV latent tail via native masks. There is no latent phase snap and no additional cutoff loss.
- The Masked-AV-aware stitcher already maps the render-tail trim back into the protected next head, so video/audio overlap remains time-aligned even though the visible previous clip ends a few frames earlier.
- Detected freezes still use the detector's exact conservative pixel endpoint; the 7-frame fallback is applied only when no freeze lock is found.
- `Final Clip` remains unchanged and keeps its complete tail by design. Use `Stitch Ready` for a final segment too if you explicitly want the safety trim applied to the very end of the finished video.
- Added regression tests for the new render-only fallback; Candidate 2 automated suite: 94 tests.

## 1.4.0-rc1 — Native Masked AV continuation

- Added `H3ContinuousStartV14` and `H3ContinuousContinueV14`. Start keeps v1.3 flexible T2VA/I2VA/L2VA/FL2VA and Qwen Picture behavior; Continue switches the previous-clip handover to ComfyUI's native in-place video/audio denoise masks.
- v1.4 Masked AV requires a **current ComfyUI build containing native PR #15375 H3 AV-mask support**. Candidate 1 capability-probes the live runtime instead of trusting the version string alone. No older-core compatibility shim is added for the new path; the registered v1.3 guide nodes remain available for legacy workflows and A/B comparison.
- Continue now copies the **true final exact AV latent run** from the previous clip directly into the new target head and protects it from normal denoising. The protected context is not a Qwen Picture.
- Added exact shared AV context lengths `39 / 90 / 141 / 192 / ...` frames (`39 + 51k`). The shipped workflows default to 39 frames (~1.625 s / 65 audio-latent ticks).
- Added optional audio-mask feathering; Candidate 1 defaults to hard audio protection (`audio_feather_ticks = 0`). Nonzero release values remain experimental and follow the live ComfyUI H3 mask semantics.
- Reworked v1.4 Auto Handover semantics: freeze detection remains, but it is now **render/stitch-only**. A detected freeze trims to the detector's safe pixel endpoint; if no freeze is found, the complete moving tail is preserved. The old no-lock fallback and latent phase cutoff are not used by v1.4.
- Added Masked-AV-aware seam alignment. When a previous rendered freeze tail is trimmed, video/audio crossfade anchors shift to the time-corresponding earlier position inside the next protected context head while the full reused head is still removed from final duration.
- Safe Tail Bridge defaults to `0` in v1.4 because native in-place continuation no longer loses rendered frames solely to guide-latent phase quantization. The legacy option remains available.
- Added four v1.4 Candidate workflows and updated their in-canvas guidance for current ComfyUI builds containing PR #15375, 39-frame Masked AV context, Picture mapping and render-only Handover behavior.
- Kept manual Save/Load clip indexing unchanged in Candidate 1.
- Candidate 1 is **not yet live-model validated**; automated regression/static checks are intended to catch structural regressions before ComfyUI/H3 A/B testing.

## 1.3.0 — Flexible H3 conditioning and Qwen References

- Added new `H3ContinuousStartV13` and `H3ContinuousContinueV13` class IDs while retaining all v1.2.x nodes unchanged for workflow compatibility.
- First Frame and Last Frame are independent optional inputs on the new Start node, enabling T2VA, I2VA, L2VA and FL2VA starts from one conditioning node.
- Keyframes remain the recommended Infinite Continuation workflow even though they are optional: repeated Last Frames provide the visual endpoint / **quality reset** that helps counter drift across long chains.
- Restored native MiniMax/Qwen Picture priority: connected First Frame is presented first, connected Last Frame second, and additional Qwen References follow consecutively as the next `<Picture N>` inputs.
- Added Qwen Reference autogrow UX: the node starts with `Qwen Reference 1`; connecting it reveals `Qwen Reference 2`, then 3, and so on up to nine.
- Qwen References are deliberately text/vision-encoder-only images. They are not inserted into `minimax_refs` and therefore are not native Ref2VA/DiT reference latents.
- Added a `picture_map` string output and console diagnostic showing the exact Picture-to-input mapping used for the current graph.
- Live testing confirmed the autogrow UI, First/Last Picture ordering, multiple Qwen References with separate prompt roles, and a longer multi-clip continuation using the new v1.3 Continue node.
- Continue keeps the proven v1.2 phase-aligned video/audio latent handover, freeze handling and stitching path unchanged. Its direct latent context is not silently decoded and added as a Qwen Picture.
- Save / Load latent clip indexing remains the proven manual workflow from v1.2.x. No automatic chain-index behavior is introduced in v1.3.
- Updated all four shipped workflows, in-canvas guidance, example documentation and Registry metadata to v1.3.0.
- The dynamic Qwen sockets use a small v1-compatible frontend/backend bridge so the existing node pack can keep its stable legacy class registrations instead of requiring an all-at-once V3 migration.

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
