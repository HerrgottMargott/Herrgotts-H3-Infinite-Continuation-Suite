import importlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = "herrgotts_h3_suite_qwen_testpkg"


def _load():
    if PKG not in sys.modules:
        pkg = types.ModuleType(PKG)
        pkg.__path__ = [str(ROOT)]
        pkg.__package__ = PKG
        sys.modules[PKG] = pkg
    return importlib.import_module(f"{PKG}.qwen_guides")


def test_qwen_reference_index_accepts_only_supported_numeric_slots():
    qg = _load()
    assert qg.qwen_reference_index("qwen_reference_1") == 1
    assert qg.qwen_reference_index("qwen_reference_9") == 9
    assert qg.qwen_reference_index("qwen_reference_0") is None
    assert qg.qwen_reference_index("qwen_reference_10") is None
    assert qg.qwen_reference_index("qwen_reference_x") is None
    assert qg.qwen_reference_index("first_frame") is None


def test_dynamic_input_mapping_recognizes_frontend_created_qwen_sockets():
    qg = _load()
    inputs = qg.DynamicQwenReferenceInputs({"qwen_reference_1": ("IMAGE", {})})
    assert "qwen_reference_1" in inputs
    assert "qwen_reference_2" in inputs
    assert "qwen_reference_9" in inputs
    assert "qwen_reference_10" not in inputs
    spec = inputs["qwen_reference_4"]
    assert spec[0] == "IMAGE"
    assert "Qwen Reference 4" in spec[1]["tooltip"]


def test_collect_qwen_references_is_numeric_not_lexicographic():
    qg = _load()
    entries = qg.collect_qwen_reference_entries(
        "one",
        {
            "qwen_reference_9": "nine",
            "qwen_reference_3": "three",
            "unrelated": "ignore",
            "qwen_reference_2": "two",
        },
    )
    assert entries == [(1, "one"), (2, "two"), (3, "three"), (9, "nine")]
    assert qg.collect_qwen_references("one", {"qwen_reference_3": "three"}) == ["one", "three"]


def test_keyframe_modes_cover_t2va_i2va_l2va_and_fl2va():
    qg = _load()
    assert qg.keyframe_mode(first_frame=False, last_frame=False) == "T2VA"
    assert qg.keyframe_mode(first_frame=True, last_frame=False) == "I2VA"
    assert qg.keyframe_mode(first_frame=False, last_frame=True) == "L2VA"
    assert qg.keyframe_mode(first_frame=True, last_frame=True) == "FL2VA"


def test_picture_roles_keep_native_first_last_then_qwen_order():
    qg = _load()
    assert qg.picture_roles(first_frame=True, last_frame=True, qwen_reference_count=2) == [
        "First Frame",
        "Last Frame",
        "Qwen Reference 1",
        "Qwen Reference 2",
    ]
    assert qg.picture_roles(first_frame=False, last_frame=True, qwen_reference_count=2) == [
        "Last Frame",
        "Qwen Reference 1",
        "Qwen Reference 2",
    ]


def test_picture_roles_preserve_sparse_socket_numbers():
    qg = _load()
    roles = qg.picture_roles(
        first_frame=True,
        last_frame=False,
        qwen_reference_count=2,
        qwen_reference_indices=[1, 4],
    )
    assert roles == ["First Frame", "Qwen Reference 1", "Qwen Reference 4"]


def test_start_picture_map_reports_exact_picture_assignment():
    qg = _load()
    text = qg.format_picture_map(
        first_frame=True,
        last_frame=True,
        qwen_reference_count=2,
        continuation=False,
    )
    assert "H3 keyframe mode: FL2VA" in text
    assert "Picture 1 = First Frame" in text
    assert "Picture 2 = Last Frame" in text
    assert "Picture 3 = Qwen Reference 1" in text
    assert "Picture 4 = Qwen Reference 2" in text
    assert "not minimax_refs" in text


def test_continue_picture_map_does_not_count_direct_latent_as_picture():
    qg = _load()
    text = qg.format_picture_map(
        first_frame=False,
        last_frame=True,
        qwen_reference_count=2,
        continuation=True,
    )
    assert "Qwen presentation for Continue" in text
    assert "Picture 1 = Last Frame" in text
    assert "Picture 2 = Qwen Reference 1" in text
    assert "Picture 3 = Qwen Reference 2" in text
    assert "Direct latent handover context is not a Qwen <Picture N>" in text


def test_t2va_picture_map_can_have_no_picture_inputs():
    qg = _load()
    text = qg.format_picture_map(
        first_frame=False,
        last_frame=False,
        qwen_reference_count=0,
        continuation=False,
    )
    assert text.splitlines() == ["H3 keyframe mode: T2VA", "No <Picture N> inputs"]
