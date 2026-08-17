import importlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = "herrgotts_h3_suite_testpkg"


def _load(name):
    if PKG not in sys.modules:
        pkg = types.ModuleType(PKG)
        pkg.__path__ = [str(ROOT)]
        pkg.__package__ = PKG
        sys.modules[PKG] = pkg
    return importlib.import_module(f"{PKG}.{name}")


def test_callable_classifier_distinguishes_stock_ours_and_foreign():
    pu = _load("patch_utils")

    class Owner:
        pass
    Owner.__module__ = "comfy.fake"

    def stock(self):
        pass
    stock.__module__ = "comfy.fake"
    st = pu.classify_callable(Owner, stock, "_ours", (("_other", "Other Pack"),))
    assert st.state == "stock"

    stock._ours = True
    st = pu.classify_callable(Owner, stock, "_ours", (("_other", "Other Pack"),))
    assert st.state == "ours"
    del stock._ours
    stock._other = True
    st = pu.classify_callable(Owner, stock, "_ours", (("_other", "Other Pack"),))
    assert st.state == "foreign"
    assert st.owner == "Other Pack"
    del stock._other

    def foreign(self):
        pass
    foreign.__module__ = "some_other_chaining_pack.patch"
    st = pu.classify_callable(Owner, foreign, "_ours")
    assert st.state == "foreign"


def test_payload_patch_is_gated_on_our_markers():
    pp = _load("patch_payload")
    assert not pp._graph_has_our_markers(
        [{"resolved_frame_index": 0}], [{"kind": "audio", "ref_audio_t": 3}]
    )
    assert pp._graph_has_our_markers(
        [{"resolved_frame_index": 0, pp.HC_INDEX: 0}],
        [{"kind": "audio", "ref_audio_t": 3}],
    )
    assert pp._graph_has_our_markers(
        [{"resolved_frame_index": 0}],
        [{"kind": "audio", "ref_audio_t": 3, pp.HC_AUDIO_END_FRAME: 2.0}],
    )


def test_marked_payload_keeps_keyframe_video_and_audio_ref():
    pp = _load("patch_payload")

    class Holder:
        def __init__(self):
            self.cond = {"cond_video_latents": ["stock-overwrite"]}
    out = {"minimax_payload": Holder()}
    keyframes = [{"latent": "kf0", pp.HC_INDEX: 0}, {"latent": "kf1", pp.HC_INDEX: 5}]
    refs = [{"kind": "audio", "audio_latent": "audio", pp.HC_AUDIO_END_FRAME: 5.0}]
    result = pp._rewrite_marked_payload(out, keyframes, refs, frame_count=243)
    payload = result["minimax_payload"].cond
    assert payload["cond_video_latents"] == ["kf0", "kf1"]
    assert payload["cond_audio_latents"] == ["audio"]
    assert payload["frame_count"] == 243


def test_known_motion_context_patch_is_reported_as_conflict(monkeypatch):
    pl = _load("patch_layout")

    class FakeLayout:
        pass
    FakeLayout.__module__ = "comfy.ldm.minimax.model"

    def other_init(self, *args, **kwargs):
        pass
    other_init.__module__ = "foreign.patch_layout"
    setattr(other_init, "_h3_motion_context_layout_patch", True)
    FakeLayout.__init__ = other_init
    fake_mm = types.SimpleNamespace(PackedLayout=FakeLayout)
    monkeypatch.setattr(pl, "_import_mm", lambda: fake_mm)
    status, err = pl.get_layout_patch_status()
    assert err is None
    assert status.state == "foreign"
    assert status.owner == "ComfyUI-H3-Motion-Context"


def test_nodepack_import_file_has_no_startup_patch_install_calls():
    text = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert "install_layout_patch()" not in text
    assert "install_payload_patch()" not in text
    assert "from .nodes import NODE_CLASS_MAPPINGS" in text


def test_continuation_keyframe_builder_supports_native_and_legacy_modes():
    text = (ROOT / "nodes.py").read_text(encoding="utf-8")
    assert 'if runtime_mode == NATIVE_LAYOUT_MODE' in text
    assert '{"resolved_frame_index": pixel_index, "latent": latent}' in text
    assert 'HC_INDEX: pixel_index' in text


def test_layout_api_detection_distinguishes_legacy_and_native(monkeypatch):
    pl = _load("patch_layout")

    class Legacy:
        def __init__(self, text_len, latent_t, latent_h, latent_w, audio_t,
                     keyframes=None, refs=None, frame_count=None):
            pass

    monkeypatch.setattr(pl, "_import_mm", lambda: types.SimpleNamespace(PackedLayout=Legacy))
    mode, sig, err = pl.detect_layout_api()
    assert err is None
    assert mode == pl.LEGACY_LAYOUT_MODE
    assert "frame_count" in sig.parameters

    class Native:
        def __init__(self, text_len, latent_t, latent_h, latent_w, audio_t,
                     keyframes=None, refs=None):
            pass

    monkeypatch.setattr(pl, "_import_mm", lambda: types.SimpleNamespace(PackedLayout=Native))
    mode, sig, err = pl.detect_layout_api()
    assert err is None
    assert mode == pl.NATIVE_LAYOUT_MODE
    assert "frame_count" not in sig.parameters


def test_native_runtime_skips_payload_monkey_patch(monkeypatch):
    rp = _load("runtime_patches")
    pl = rp.patch_layout
    pp = rp.patch_payload

    monkeypatch.setattr(rp, "_RUNTIME_MODE", None)
    monkeypatch.setattr(rp, "get_h3_runtime_mode", lambda: pl.NATIVE_LAYOUT_MODE)
    stock = types.SimpleNamespace(state="stock", owner=None, module="comfy.fake")
    monkeypatch.setattr(pl, "get_layout_patch_status", lambda: (stock, None))
    monkeypatch.setattr(pp, "get_payload_patch_status", lambda: (stock, None))
    monkeypatch.setattr(pp, "is_applied", lambda: False)
    called = {"layout": 0, "payload": 0}
    monkeypatch.setattr(pl, "install_layout_patch", lambda mode=None: called.__setitem__("layout", called["layout"] + 1) or True)
    monkeypatch.setattr(pp, "install_payload_patch", lambda: called.__setitem__("payload", called["payload"] + 1) or True)

    assert rp.ensure_h3_runtime_patches() == pl.NATIVE_LAYOUT_MODE
    assert called == {"layout": 1, "payload": 0}


def _fake_native_layout_module(pl):
    import torch

    class NativeLayout:
        """0.33-style fake: no named segments, only packed modality maps."""
        def __init__(self, text_len, latent_t, latent_h, latent_w, audio_t,
                     keyframes=None, refs=None):
            pos_blocks = []
            img_pos = []
            img_update = []
            audio_pos = []
            audio_update = []
            row = 0

            def add(times):
                nonlocal row
                t = torch.as_tensor(times, dtype=torch.float64).reshape(-1)
                pos = torch.zeros((t.numel(), 3), dtype=torch.float64)
                pos[:, 0] = t
                start = row
                row += t.numel()
                pos_blocks.append(pos)
                return torch.arange(start, row, dtype=torch.long)

            add(torch.arange(text_len, dtype=torch.float64))
            ref_advance = sum(float(r.get("ref_audio_t", 0)) for r in (refs or []) if r.get("kind") == "audio")
            target_origin = float(text_len) + ref_advance
            for kf in keyframes or []:
                rows = add([target_origin + (5.0 / 3.0) * float(kf["resolved_frame_index"])])
                img_pos.append(rows)
                img_update.append(torch.zeros(rows.numel(), dtype=torch.bool))
            cursor = float(text_len)
            for r in refs or []:
                if r.get("kind") == "audio":
                    rt = int(r.get("ref_audio_t", 0))
                    ts = torch.cat([cursor + torch.arange(rt, dtype=torch.float64),
                                    cursor + torch.arange(rt, dtype=torch.float64)])
                    rows = add(ts)
                    audio_pos.append(rows)
                    audio_update.append(torch.zeros(rows.numel(), dtype=torch.bool))
                    cursor += rt
            rows = add(torch.cat([cursor + torch.arange(audio_t, dtype=torch.float64),
                                  cursor + torch.arange(audio_t, dtype=torch.float64)]))
            audio_pos.append(rows)
            audio_update.append(torch.ones(rows.numel(), dtype=torch.bool))
            rows = add([target_origin])
            img_pos.append(rows)
            img_update.append(torch.ones(rows.numel(), dtype=torch.bool))
            self.position_ids = torch.cat(pos_blocks, dim=0)
            self.img_pos = torch.cat(img_pos) if img_pos else torch.empty(0, dtype=torch.long)
            self.img_update = torch.cat(img_update) if img_update else torch.empty(0, dtype=torch.bool)
            self.audio_pos = torch.cat(audio_pos) if audio_pos else torch.empty(0, dtype=torch.long)
            self.audio_update = torch.cat(audio_update) if audio_update else torch.empty(0, dtype=torch.bool)

    return types.SimpleNamespace(
        PackedLayout=NativeLayout,
        FRAME_RESCALE=5.0 / 3.0,
        FRAME_PER_TOKEN=(1, 4, 4, 4, 4),
        _video_t_spans=lambda n: [(5.0 / 3.0) * (1, 4, 4, 4, 4)[i % 5] for i in range(n)],
    )


def test_native_layout_wrapper_self_test_and_audio_alignment(monkeypatch):
    pl = _load("patch_layout")
    fake_mm = _fake_native_layout_module(pl)
    monkeypatch.setattr(pl, "_import_mm", lambda: fake_mm)
    monkeypatch.setattr(pl, "_APPLIED", False)
    monkeypatch.setattr(pl, "_APPLIED_MODE", None)
    monkeypatch.setattr(pl, "_ORIGINAL_INIT", None)
    monkeypatch.setattr(pl, "_INSTALLED_WRAPPER", None)
    monkeypatch.setattr(pl, "_MM", None)
    assert pl.install_layout_patch(pl.NATIVE_LAYOUT_MODE)
    assert pl.applied_mode() == pl.NATIVE_LAYOUT_MODE
    refs = [{"kind": "audio", "ref_audio_t": 11, pl.HC_AUDIO_END_FRAME: 5.0}]
    layout = fake_mm.PackedLayout(7, 7, 22, 38, 16, keyframes=[{"resolved_frame_index": 5}], refs=refs)
    ref_rows = layout.audio_pos[~layout.audio_update]
    video_rows = layout.img_pos[layout.img_update]
    assert abs(float(layout.position_ids[ref_rows, 0].max()) + 1.0 -
               (float(layout.position_ids[int(video_rows[0]), 0]) + (5.0 / 3.0) * 5.0)) < 1e-9


def test_native_layout_api_detection_stays_native_after_our_wrapper_is_installed(monkeypatch):
    pl = _load("patch_layout")
    fake_mm = _fake_native_layout_module(pl)
    monkeypatch.setattr(pl, "_import_mm", lambda: fake_mm)
    monkeypatch.setattr(pl, "_APPLIED", False)
    monkeypatch.setattr(pl, "_APPLIED_MODE", None)
    monkeypatch.setattr(pl, "_ORIGINAL_INIT", None)
    monkeypatch.setattr(pl, "_INSTALLED_WRAPPER", None)
    monkeypatch.setattr(pl, "_MM", None)
    assert pl.install_layout_patch(pl.NATIVE_LAYOUT_MODE)
    mode, sig, err = pl.detect_layout_api()
    assert err is None
    assert mode == pl.NATIVE_LAYOUT_MODE
    assert sig is not None
    assert {"text_len", "latent_t", "latent_h", "latent_w", "audio_t", "keyframes", "refs"} <= set(sig.parameters)
