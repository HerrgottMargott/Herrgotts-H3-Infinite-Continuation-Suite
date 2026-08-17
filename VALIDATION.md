# v1.3.0 validation notes

This file summarizes the release checks for **Herrgotts H3 Infinite Continuation Suite v1.3.0**.

## Release scope

v1.3.0 extends the conditioning layer while deliberately keeping the proven continuation and stitching core stable.

Validated release behavior includes:

- `H3ContinuousStartV13` with independent optional First Frame and Last Frame inputs.
- T2VA, I2VA, L2VA and FL2VA start modes from the same v1.3 Start node.
- `H3ContinuousContinueV13` with the existing direct phase-aligned video/audio latent handover plus optional Last Frame conditioning.
- Auto-growing Qwen-only reference inputs from `Qwen Reference 1` through `Qwen Reference 9`.
- Deterministic Qwen `<Picture N>` ordering: connected First Frame, connected Last Frame, then connected Qwen References in numeric socket order.
- Continue-mode picture mapping that does **not** count the carried direct latent context as a Qwen Picture.
- `picture_map` diagnostics for the exact image-to-Picture assignment.
- Existing v1.2.x Start/Continue classes retained for workflow compatibility.
- Manual Save/Load clip indexing retained unchanged for v1.3.0.

## Live validation carried into the release

The v1.3 conditioning path was live-tested in ComfyUI with:

- Qwen Reference socket autogrow behavior.
- First/Last Frame Picture ordering.
- Multiple Qwen References used for separate prompt roles.
- Longer multi-clip continuation through the v1.3 Continue node.

The underlying direct AV-latent continuation, freeze analysis, phase-aligned cutoff, Safe Tail Bridge and seamless stitching path remains the established v1.2.x implementation.

## ComfyUI 0.33 compatibility

The v1.2.2 runtime compatibility work remains in place:

- Native MiniMax H3 keyframe placement is used on the newer ComfyUI H3 layout API.
- The legacy payload patch is skipped where ComfyUI preserves keyframes and reference payloads natively.
- The remaining native audio-timeline compatibility wrapper is installed lazily and is gated to suite-marked continuation graphs.
- Repeated Continue calls in one ComfyUI session retain the corrected wrapper/signature handling.
- Older supported H3 layouts retain the legacy compatibility path.

## Automated regression suite

Run from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Release result for this source tree:

```text
82 passed
```

The automated suite covers:

- latent continuation math and phase alignment;
- freeze/motion handover analysis;
- release metadata and saved latent helpers;
- runtime patch gating and native/legacy API safety;
- seamless stitch and Safe Tail Bridge behavior;
- v1.3 Qwen dynamic-input collection and Picture mapping;
- all four shipped v1.3 workflows and Registry metadata;
- release documentation invariants, including the README section order.

## Additional release checks

Before packaging, the v1.3.0 source tree was also checked for:

- Python compilation errors;
- valid JSON in all shipped workflow files;
- consistent `1.3.0` package/workflow Registry version metadata;
- stale v1.3 release-candidate wording in the final release section;
- local Markdown links to files shipped in the repository.

No model weights are included in the repository or release package.
