import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
WORKFLOWS = sorted(EXAMPLES.glob("Herrgotts_H3_Infinite_v1.4_*.json"))
REGISTRY_ID = "herrgotts-h3-infinite-continuation-suite"
RELEASE_VERSION = "1.4.0"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _suite_nodes(data):
    return [n for n in data.get("nodes", []) if str(n.get("type", "")).startswith("H3Continuous")]


def _node(data, node_type):
    return next(n for n in _suite_nodes(data) if n.get("type") == node_type)


def test_expected_v14_workflows_are_shipped_and_valid_json():
    assert [p.name for p in WORKFLOWS] == [
        "Herrgotts_H3_Infinite_v1.4_01_Start.json",
        "Herrgotts_H3_Infinite_v1.4_02_Continue.json",
        "Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json",
        "Herrgotts_H3_Infinite_v1.4_04_Stitch_Saved_Chain.json",
        "Herrgotts_H3_Infinite_v1.4_05_EncodeExistingVideo.json",
    ]
    for path in WORKFLOWS:
        data = _load(path)
        assert isinstance(data.get("nodes"), list)
        assert data["nodes"]


def test_all_suite_nodes_have_candidate_registry_metadata():
    for path in WORKFLOWS:
        data = _load(path)
        for node in _suite_nodes(data):
            props = node.get("properties", {})
            assert props.get("cnr_id") == REGISTRY_ID, (path.name, node.get("id"), node.get("type"))
            assert props.get("ver") == RELEASE_VERSION, (path.name, node.get("id"), node.get("type"))
            assert props.get("Node name for S&R") == node.get("type")


def test_start_workflow_uses_v14_nodes():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_01_Start.json")
    types = [n.get("type") for n in data["nodes"]]
    assert "H3ContinuousStartV14" in types
    assert "H3ContinuousAnalyzeHandoverV14" in types
    assert "H3ContinuousStitchOutputV14" in types
    assert "H3ContinuousStartV13" not in types
    assert "H3ContinuousContinueV14" not in types


def test_continue_workflow_uses_native_masked_v14_and_manual_clip_indexing():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_02_Continue.json")
    nodes = _suite_nodes(data)
    types = [n.get("type") for n in nodes]
    assert "H3ContinuousContinueV14" in types
    assert "H3ContinuousAnalyzeHandoverV14" in types
    assert "H3ContinuousStitchOutputV14" in types
    assert "H3ContinuousContinueV13" not in types

    cont = _node(data, "H3ContinuousContinueV14")
    assert cont.get("widgets_values")[4:6] == ["39", 0]
    assert cont.get("widgets_values")[-2:] == ["Net New Content", "Full Previous Tail"]
    input_names = [i.get("name") for i in cont.get("inputs", [])]
    assert "previous_latent" in input_names
    assert "handover" in input_names
    assert next(i for i in cont.get("inputs", []) if i.get("name") == "handover").get("link") is not None

    analyzer = _node(data, "H3ContinuousAnalyzeHandoverV14")
    assert analyzer.get("widgets_values")[4] == "39"

    load = _node(data, "H3ContinuousLoadLatent")
    save = _node(data, "H3ContinuousSaveLatent")
    assert load.get("widgets_values")[-1] == 1
    assert save.get("widgets_values")[-1] == 2


def test_showcase_uses_only_v14_generation_handover_and_stitch_nodes():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json")
    types = [n.get("type") for n in data["nodes"]]
    assert types.count("H3ContinuousStartV14") == 1
    assert types.count("H3ContinuousContinueV14") == 2
    assert types.count("H3ContinuousAnalyzeHandoverV14") == 3
    assert types.count("H3ContinuousStitchOutputV14") == 3
    assert types.count("H3ContinuousSeamlessJoinV14") == 2
    assert "H3ContinuousContinueV13" not in types
    assert "H3ContinuousSeamlessJoinV11" not in types

    continues = [n for n in data["nodes"] if n.get("type") == "H3ContinuousContinueV14"]
    for node in continues:
        assert node.get("widgets_values")[4:6] == ["39", 0]
        assert "handover" in [i.get("name") for i in node.get("inputs", [])]
        assert next(i for i in node.get("inputs", []) if i.get("name") == "handover").get("link") is not None

    analyzers = [n for n in data["nodes"] if n.get("type") == "H3ContinuousAnalyzeHandoverV14"]
    assert all(n.get("widgets_values")[4] == "39" for n in analyzers)

    joins = [n for n in data["nodes"] if n.get("type") == "H3ContinuousSeamlessJoinV14"]
    assert all(n.get("widgets_values")[-1] == 0 for n in joins)



def test_candidate4_continue_handover_links_come_from_previous_clip_metadata():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_02_Continue.json")
    cont = _node(data, "H3ContinuousContinueV14")
    hand_input = next(i for i in cont["inputs"] if i.get("name") == "handover")
    link = next(l for l in data["links"] if l[0] == hand_input["link"])
    load = _node(data, "H3ContinuousLoadLatent")
    assert (link[1], link[2]) == (load["id"], 3)

    showcase = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json")
    continues = sorted(
        [n for n in showcase["nodes"] if n.get("type") == "H3ContinuousContinueV14"],
        key=lambda n: n["id"],
    )
    analyzers = sorted(
        [n for n in showcase["nodes"] if n.get("type") == "H3ContinuousAnalyzeHandoverV14"],
        key=lambda n: n["id"],
    )
    for cont_node, analyzer in zip(continues, analyzers[:2]):
        hand = next(i for i in cont_node["inputs"] if i.get("name") == "handover")
        lnk = next(l for l in showcase["links"] if l[0] == hand["link"])
        assert (lnk[1], lnk[2]) == (analyzer["id"], 0)


def test_showcase_output_modes_are_two_stitch_ready_then_final_clip():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json")
    outputs = [n for n in data["nodes"] if n.get("type") == "H3ContinuousStitchOutputV14"]
    outputs.sort(key=lambda n: n.get("id"))
    assert [n.get("widgets_values")[0] for n in outputs] == [
        "Stitch Ready",
        "Stitch Ready",
        "Final Clip",
    ]


def test_showcase_uses_one_shared_audio_vae_loader():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json")
    audio_loaders = [
        n for n in data["nodes"]
        if n.get("type") == "VAELoader" and "audio" in str(n.get("widgets_values", [])).lower()
    ]
    assert len(audio_loaders) == 1


def test_saved_chain_workflow_uses_v14_memory_bounded_stitcher_and_no_bridge():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_04_Stitch_Saved_Chain.json")
    nodes = [n for n in data["nodes"] if n.get("type") == "H3ContinuousStitchSavedChainV14"]
    assert len(nodes) == 1
    widgets = nodes[0].get("widgets_values")
    assert widgets[0] == "h3_continuous/clip"
    assert widgets[1] == 1
    assert widgets[2] == 0
    assert widgets[-1] == 0


def test_node_list_covers_every_registered_node_mapping():
    node_list = json.loads((ROOT / "node_list.json").read_text(encoding="utf-8"))
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    mapping_block = source.split("NODE_CLASS_MAPPINGS = {", 1)[1].split("}\n\nNODE_DISPLAY_NAME_MAPPINGS", 1)[0]
    registered = set()
    for line in mapping_block.splitlines():
        line = line.strip()
        if line.startswith('"') and '":' in line:
            registered.add(line.split('"', 2)[1])
    assert registered
    assert set(node_list) == registered


def test_v14_continue_static_contract_uses_native_masks_not_legacy_runtime_patch():
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    block = source.split("class H3ContinuousContinueV14", 1)[1].split("# ---------------------------------------------------------------------------\n# v1.2 release-facing nodes", 1)[0]
    assert "_require_masked_av_support()" in block
    assert "_masked_av_latent(" in block
    assert "_require_patches(" not in block
    assert "handover_mode" not in block
    assert "safe_end = int(handover.get(\"handover_end_frame\", -1))" in block
    assert "ideal_last_frame=safe_end" in block
    assert "phase_aligned_extended" not in block
    assert "masked_av_duration_plan" in block
    assert 'duration_mode="Net New Content"' in block
    assert 'audio_tail_carryover="Full Previous Tail"' in block
    assert "audio_tail_mode=audio_tail_carryover" in block
    assert "alignment_recovery" not in block.lower()

    latent_math_source = (ROOT / "latent_math.py").read_text(encoding="utf-8")
    assert "def masked_av_audio_context_plan" in latent_math_source

    helper = source.split("def _masked_av_latent", 1)[1].split("def _context_tail_offset_from_handover", 1)[0]
    assert 'out["noise_mask"] = comfy.nested_tensor.NestedTensor((video_mask, audio_mask))' in helper
    assert 'out["samples"] = comfy.nested_tensor.NestedTensor((out_video, out_audio))' in helper


def test_v14_render_guard_consumes_soft_final_state_candidate_and_snaps_shared_boundary():
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    block = source.split("class H3ContinuousAnalyzeHandoverV14", 1)[1].split("class H3ContinuousStitchOutputV11", 1)[0]
    assert 'soft_final_candidate_start_frame=result.get("primary_candidate_start_frame", -1)' in block
    assert 'safety_margin=int(result.get("safety_margin", safety_margin))' in block
    assert '"masked_av_render_safety_mode"' in block
    assert "masked_av_safe_handover_plan(frame_count, render_trim, 39)" in block
    assert '"masked_av_source_policy": "safe_handover_window"' in block


def test_v14_comfyui_requirement_is_explicit():
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    guard = source.split("def _require_masked_av_support", 1)[1].split("def _apply_audio_context_feather", 1)[0]
    assert "_native_masked_av_capability_status" in guard
    assert "PR #15375" in guard
    assert "latest build" in guard



def test_v14_qwen_autogrow_frontend_targets_v14_nodes():
    js = (ROOT / "web" / "js" / "qwenReferenceAutogrow.js").read_text(encoding="utf-8")
    assert '"H3ContinuousStartV14"' in js
    assert '"H3ContinuousContinueV14"' in js


def test_readme_places_v14_update_information_after_installation_before_usage():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    install = text.index("## Installation")
    update = text.index("## v1.4 native Masked AV continuation")
    usage = text.index("## Usage")
    assert install < update < usage


def test_candidate_docs_and_examples_use_v14_names_without_stale_v13_workflow_names():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    examples_readme = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    validation = (ROOT / "VALIDATION.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    for text in (readme, examples_readme):
        assert "Herrgotts_H3_Infinite_v1.3_" not in text
        assert "Herrgotts_H3_Infinite_v1.4_" in text
    assert "# v1.4.0 validation notes" in validation
    assert "## 1.4.0 —" in changelog
    section = changelog.split("## 1.4.0 —", 1)[1].split("## 1.4.0-rc4", 1)[0]
    assert "live testing" in section.lower()


def test_candidate6_removes_alignment_recovery_from_v14_public_nodes():
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    v14_join = source.split("class H3ContinuousSeamlessJoinV14", 1)[1].split("class H3ContinuousStitchSavedChainV14", 1)[0]
    v14_saved = source.split("class H3ContinuousStitchSavedChainV14", 1)[1].split("# Shared release nodes", 1)[0]
    assert "alignment_recovery" not in v14_join.lower()
    assert "alignment_recovery" not in v14_saved.lower()
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8").lower()
        assert "alignment recovery" not in text
        assert "previous_full_audio" not in text


def test_candidate6_v14_fallback_seam_controls_are_advanced_in_source_contract():
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    v14_join = source.split("class H3ContinuousSeamlessJoinV14", 1)[1].split("class H3ContinuousStitchSavedChainV14", 1)[0]
    v14_saved = source.split("class H3ContinuousStitchSavedChainV14", 1)[1].split("# Shared release nodes", 1)[0]
    for block in (v14_join, v14_saved):
        assert 'required["luminance_match"]' in block
        assert '"advanced": True' in block
        assert 'required["max_safe_tail_bridge_frames"]' in block


def test_encode_existing_video_workflow_trims_encodes_and_saves():
    data = _load(EXAMPLES / "Herrgotts_H3_Infinite_v1.4_05_EncodeExistingVideo.json")
    types = [n.get("type") for n in data["nodes"]]

    assert "H3ContinuousTrimToBoundary" in types
    assert "H3ContinuousSaveLatent" in types
    assert "VAEEncode" in types
    assert "VAEEncodeAudio" in types
    assert "LTXVConcatAVLatent" in types

    def by_type(node_type):
        return next(n for n in data["nodes"] if n.get("type") == node_type)

    trim = by_type("H3ContinuousTrimToBoundary")
    assert trim.get("widgets_values") == [39]

    save = by_type("H3ContinuousSaveLatent")
    assert save.get("widgets_values")[-1] == 1

    concat_inputs = [i.get("name") for i in by_type("LTXVConcatAVLatent").get("inputs", [])]
    assert concat_inputs == ["video_latent", "audio_latent"]

    # The concat output feeds the save node's latent input.
    assert next(i for i in save["inputs"] if i.get("name") == "latent").get("link") is not None
    concat = by_type("LTXVConcatAVLatent")
    save_latent_link = next(i for i in save["inputs"] if i.get("name") == "latent")["link"]
    concat_latent_links = next(o for o in concat["outputs"] if o.get("name") == "latent")["links"]
    assert save_latent_link == concat_latent_links[0]

    # The trim node emits a handover that feeds the save node so a later
    # H3ContinuousLoadLatent returns valid metadata for H3ContinuousContinueV14.
    save_handover_link = next(i for i in save["inputs"] if i.get("name") == "handover")["link"]
    assert save_handover_link is not None
    trim_handover_links = next(o for o in trim["outputs"] if o.get("name") == "handover")["links"]
    assert save_handover_link == trim_handover_links[0]


def test_trim_node_accepts_mapping_audio_not_just_dict():
    source = (ROOT / "nodes.py").read_text(encoding="utf-8")
    block = source.split("class H3ContinuousTrimToBoundary", 1)[1].split("class H3ContinuousAnalyzeHandover", 1)[0]
    # VHS returns a lazily-evaluated Mapping (LazyAudioMap), not a plain dict.
    assert "collections.abc" in source
    assert "Mapping" in block
    assert 'isinstance(audio, Mapping)' in block
    assert '"waveform" not in audio' in block
