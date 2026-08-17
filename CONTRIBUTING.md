# Contributing

Thanks for helping improve Herrgotts-H3-Infinite-Continuation-Suite.
## Before opening a bug report

Please include enough information to reproduce the issue:

- ComfyUI version / commit
- Operating system
- GPU and VRAM
- H3 model / VAE setup
- node-pack version
- relevant console log lines
- whether `Balanced`, `Motion Safe`, or `Custom` was used
- if the issue concerns a handover, the visually observed freeze start and the analyzer-reported cutoff

A small workflow JSON is especially useful when the problem depends on graph structure.
## Development

Run the regression suite from the repository root:

```bash
python -m pip install pytest
pytest -q
```

Keep the following invariants unless a change deliberately targets them:
- full saved AV latent remains non-destructive
- video/audio handover represents the same time interval
- `phase_aligned_extended` remains canonical-phase aligned
- Stitch Ready uses the same effective cutoff as continuation metadata
- Full output remains untrimmed
- older node schemas continue to load as Legacy nodes
## Pull requests

Prefer focused changes with regression tests. Describe the H3 behavior being addressed and include before/after console output where useful.
