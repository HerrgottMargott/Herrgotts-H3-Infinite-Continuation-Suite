import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
WORKFLOWS = sorted(EXAMPLES.glob("Herrgotts_H3_Infinite_v1.3_*.json"))
REGISTRY_ID = "herrgotts-h3-infinite-continuation-suite"
RELEASE_VERSION = "1.3.0"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _suite_nodes(data):
    return [n for n in data.get("nodes", []) if str(n.get("type", "")).startswith("H3Continuous")]


def test_expected_v13_workflows_are_shipped_and_valid_json():
    assert [p.name for p in WORKFLOWS] == [
        "Herrgotts_H3_Infinite_v1.3_01_Start.json",
        "Herrgotts_H3_Infinite_v1.3_02_Continue.json",
        "Herrgotts_H3_Infinite_v1.3_03_3Clip_Showcase_AutoStitch.json",
        "Herrgotts_H3_Infinite_v1.3_04_Stitch_Saved_Chain.json",
    ]
    for path in WORKFLOWS:
        data = _load(path)
        assert isinstance(data.get("nodes"), list)
        assert data["nodes"]


def test_all_suite_nodes_have_release_registry_metadata():
    for path in WORKFLOWS:
        data = _load(path)
        for node in _suite_nodes(data):
            props = node.get("properties", {})
            assert props.get("cnr_id") == REGISTRY_ID, (path.name, node.get("id"), node.get("type"))
            assert props.get("ver") == RELEASE_VERSION, (path.name, node.get("id"), node.get("type"))
            assert props.get("Node name for S&R") == node.get("type")


def test_start_workflow_uses_v13_flexible_start_node():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.3_01_Start.json")
    types = [n.get("type") for n in data["nodes"]]
    assert "H3ContinuousStartV13" in types
    assert "H3ContinuousStartV11" not in types
    assert "H3ContinuousContinueV13" not in types


def test_continue_workflow_uses_v13_continue_and_manual_clip_indexing():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.3_02_Continue.json")
    nodes = _suite_nodes(data)
    types = [n.get("type") for n in nodes]
    assert "H3ContinuousContinueV13" in types
    load = next(n for n in nodes if n.get("type") == "H3ContinuousLoadLatent")
    save = next(n for n in nodes if n.get("type") == "H3ContinuousSaveLatent")
    assert load.get("widgets_values")[-1] == 1
    assert save.get("widgets_values")[-1] == 2


def test_showcase_uses_v13_start_and_continue_with_stable_v11_stitch_core():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.3_03_3Clip_Showcase_AutoStitch.json")
    types = [n.get("type") for n in data["nodes"]]
    assert types.count("H3ContinuousStartV13") == 1
    assert types.count("H3ContinuousContinueV13") == 2
    assert types.count("H3ContinuousAnalyzeHandoverV11") == 3
    assert types.count("H3ContinuousStitchOutputV11") == 3
    assert types.count("H3ContinuousSeamlessJoinV11") == 2


def test_showcase_output_modes_are_two_stitch_ready_then_final_clip():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.3_03_3Clip_Showcase_AutoStitch.json")
    outputs = [
        n for n in data["nodes"] if n.get("type") == "H3ContinuousStitchOutputV11"
    ]
    outputs.sort(key=lambda n: n.get("id"))
    assert [n.get("widgets_values")[0] for n in outputs] == [
        "Stitch Ready",
        "Stitch Ready",
        "Final Clip",
    ]


def test_showcase_uses_one_shared_audio_vae_loader():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.3_03_3Clip_Showcase_AutoStitch.json")
    audio_loaders = [n for n in data["nodes"] if n.get("type") == "VAELoader" and "audio" in str(n.get("widgets_values", [])).lower()]
    assert len(audio_loaders) == 1


def test_saved_chain_workflow_uses_memory_bounded_v11_stitcher():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.3_04_Stitch_Saved_Chain.json")
    nodes = [n for n in data["nodes"] if n.get("type") == "H3ContinuousStitchSavedChainV11"]
    assert len(nodes) == 1
    widgets = nodes[0].get("widgets_values")
    assert widgets[0] == "h3_continuous/clip"
    assert widgets[1] == 1
    assert widgets[2] == 0


def test_node_list_covers_every_registered_node_mapping():
    node_list = json.loads((ROOT / "node_list.json").read_text(encoding="utf-8"))
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    # The public mappings are declared in one literal near the end of nodes.py.
    mapping_block = source.split("NODE_CLASS_MAPPINGS = {", 1)[1].split("}\n\nNODE_DISPLAY_NAME_MAPPINGS", 1)[0]
    registered = set()
    for line in mapping_block.splitlines():
        line = line.strip()
        if line.startswith('"') and '":' in line:
            registered.add(line.split('"', 2)[1])
    assert registered
    assert set(node_list) == registered


def test_readme_places_v13_update_information_after_installation_before_usage():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    install = text.index("## Installation")
    update = text.index("## v1.3 flexible conditioning")
    usage = text.index("## Usage")
    assert install < update < usage


def test_release_files_do_not_label_v13_as_release_candidate():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = changelog.split("## 1.3.0", 1)[1].split("## 1.2.2", 1)[0]
    assert "release candidate" not in section.lower()
