import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _load_examples():
    for path in sorted(EXAMPLES.glob("*.json")):
        yield path, json.loads(path.read_text(encoding="utf-8"))


def test_example_workflows_use_correct_h3_vae_files():
    for path, workflow in _load_examples():
        for node in workflow.get("nodes", []):
            if node.get("type") != "VAELoader":
                continue
            title = str(node.get("title", ""))
            values = node.get("widgets_values") or []
            selected = str(values[0]) if values else ""
            if title == "Video VAE":
                assert "minimax_h3_video_vae" in selected, (path.name, title, selected)
            elif title == "Audio VAE":
                assert "minimax_h3_audio_vae" in selected, (path.name, title, selected)


def test_showcase_contains_one_shared_audio_vae_loader():
    path = EXAMPLES / "Herrgotts_H3_Infinite_v1.2_03_3Clip_Showcase_AutoStitch.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    audio_loaders = [
        n for n in workflow.get("nodes", [])
        if n.get("type") == "VAELoader" and n.get("title") == "Audio VAE"
    ]
    assert len(audio_loaders) == 1
    assert audio_loaders[0]["widgets_values"][0] == "minimax_h3_audio_vae_fp32.safetensors"


def test_showcase_uses_stitch_ready_for_intermediate_clips_and_final_clip_for_last_segment():
    path = EXAMPLES / "Herrgotts_H3_Infinite_v1.2_03_3Clip_Showcase_AutoStitch.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    outputs = {
        n.get("title"): (n.get("widgets_values") or [None])[0]
        for n in workflow.get("nodes", [])
        if n.get("type") == "H3ContinuousStitchOutputV11"
    }
    assert outputs["CLIP 1 — Stitch Ready"] == "Stitch Ready"
    assert outputs["CLIP 2 — Stitch Ready"] == "Stitch Ready"
    assert outputs["CLIP 3 — Final Clip"] == "Final Clip"


def test_showcase_uses_release_safe_tail_bridge_defaults_and_bridge_sources():
    path = EXAMPLES / "Herrgotts_H3_Infinite_v1.2_03_3Clip_Showcase_AutoStitch.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    joins = [n for n in workflow.get("nodes", []) if n.get("type") == "H3ContinuousSeamlessJoinV11"]
    assert len(joins) == 2
    modes = {(n.get("widgets_values") or [None])[0] for n in joins}
    assert modes == {"Stitch Ready", "Final Clip"}
    for n in joins:
        widgets = n.get("widgets_values") or []
        assert widgets[1:] == [4, 15.0, False, 16, 10.0, 2]
        inputs = {i.get("name"): i for i in n.get("inputs", [])}
        assert inputs["previous_full_images"].get("link") is not None
        assert inputs["previous_handover"].get("link") is not None
    assert not any(n.get("type") in {"ImageBatch", "AudioConcat"} for n in workflow.get("nodes", []))


def test_saved_chain_workflow_uses_memory_bounded_release_defaults():
    path = EXAMPLES / "Herrgotts_H3_Infinite_v1.2_04_Stitch_Saved_Chain.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    stitchers = [n for n in workflow.get("nodes", []) if n.get("type") == "H3ContinuousStitchSavedChainV11"]
    assert len(stitchers) == 1
    widgets = stitchers[0].get("widgets_values") or []
    assert widgets[:3] == ["h3_continuous/clip", 1, 0]
    assert widgets[4:] == [4, 15.0, False, 16, 10.0, 18, 2]


def test_continue_examples_save_actual_head_context_metadata():
    for name, continue_title in [
        ("Herrgotts_H3_Infinite_v1.2_02_Continue.json", "SAVE New AV Latent + Robust Handover Metadata (Clip 2)"),
        ("Herrgotts_H3_Infinite_v1.2_03_3Clip_Showcase_AutoStitch.json", "CLIP 2 — Save Full AV Latent"),
        ("Herrgotts_H3_Infinite_v1.2_03_3Clip_Showcase_AutoStitch.json", "CLIP 3 — Save Full AV Latent"),
    ]:
        workflow = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
        save = next(n for n in workflow["nodes"] if n.get("title") == continue_title)
        head = next(i for i in save.get("inputs", []) if i.get("name") == "head_context_frames")
        assert head.get("link") is not None, (name, continue_title)


def test_generic_info_boxes_use_neutral_non_blue_backgrounds():
    for path, workflow in _load_examples():
        for node in workflow.get("nodes", []):
            if node.get("type") != "MarkdownNote":
                continue
            title = str(node.get("title", ""))
            if title.startswith("INFO") and node.get("bgcolor") is not None:
                assert node.get("bgcolor") != "#376b99", (path.name, title)
                assert node.get("color") != "#27496d", (path.name, title)


def test_saved_chain_and_showcase_document_safe_tail_bridge_and_audio_defaults():
    showcase = json.loads((EXAMPLES / "Herrgotts_H3_Infinite_v1.2_03_3Clip_Showcase_AutoStitch.json").read_text(encoding="utf-8"))
    saved = json.loads((EXAMPLES / "Herrgotts_H3_Infinite_v1.2_04_Stitch_Saved_Chain.json").read_text(encoding="utf-8"))
    show_notes = "\n".join((n.get("widgets_values") or [""])[0] for n in showcase["nodes"] if n.get("type") == "MarkdownNote")
    saved_notes = "\n".join((n.get("widgets_values") or [""])[0] for n in saved["nodes"] if n.get("type") == "MarkdownNote")
    for text in (show_notes, saved_notes):
        lower = text.lower()
        assert "safe tail bridge" in lower
        assert "15 ms" in lower
        assert "luminance" in lower
        assert "off" in lower


def test_all_suite_nodes_embed_registry_metadata_for_missing_node_resolution():
    registry_id = "herrgotts-h3-infinite-continuation-suite"
    node_list = json.loads((ROOT / "node_list.json").read_text(encoding="utf-8"))
    suite_types = set(node_list)
    seen = set()
    for path, workflow in _load_examples():
        for node in workflow.get("nodes", []):
            node_type = node.get("type")
            if node_type not in suite_types:
                continue
            seen.add(node_type)
            props = node.get("properties") or {}
            assert props.get("cnr_id") == registry_id, (path.name, node_type, props)
            assert props.get("ver") == "1.2.2", (path.name, node_type, props)
            assert props.get("Node name for S&R") == node_type, (path.name, node_type, props)
    # Every release-facing/persistence node used by the shipped workflows should be covered.
    expected_used = {
        "H3ContinuousStartV11",
        "H3ContinuousContinueV11",
        "H3ContinuousAnalyzeHandoverV11",
        "H3ContinuousStitchOutputV11",
        "H3ContinuousSeamlessJoinV11",
        "H3ContinuousStitchSavedChainV11",
        "H3ContinuousSaveLatent",
        "H3ContinuousLoadLatent",
    }
    assert expected_used <= seen


def test_node_list_matches_all_registered_node_class_mapping_keys():
    import ast

    tree = ast.parse((ROOT / "nodes.py").read_text(encoding="utf-8"))
    mapping_keys = None
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "NODE_CLASS_MAPPINGS" for target in statement.targets):
            assert isinstance(statement.value, ast.Dict)
            mapping_keys = {key.value for key in statement.value.keys if isinstance(key, ast.Constant)}
            break
    assert mapping_keys is not None
    node_list = json.loads((ROOT / "node_list.json").read_text(encoding="utf-8"))
    assert set(node_list) == mapping_keys
