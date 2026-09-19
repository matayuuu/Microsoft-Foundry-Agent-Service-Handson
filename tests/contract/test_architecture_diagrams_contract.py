"""Diagram contracts for lab-specific connections and custom-template ownership."""

from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS = ROOT / "docs" / "diagrams"
SPEC_NAMES = ("azure-architecture.json", "azure-architecture-deployment.json")
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def load_spec(name: str) -> dict:
    return json.loads((DIAGRAMS / name).read_text(encoding="utf-8"))


def indexed(spec: dict, key: str) -> dict:
    return {item["id"]: item for item in spec[key]}


def assert_service_paths(spec: dict) -> None:
    nodes = indexed(spec, "nodes")
    edges = indexed(spec, "edges")
    assert {"agent", "iq", "search", "toolbox", "api", "models"} <= nodes.keys()
    assert nodes["iq"]["parent"] == nodes["search"]["parent"] == "search-service"
    expected = {
        "agent-search": ("agent", "search"),
        "agent-iq": ("agent", "iq"),
        "iq-search": ("iq", "search"),
        "iq-planning": ("iq", "models"),
        "agent-toolbox": ("agent", "toolbox"),
        "toolbox-api": ("toolbox", "api"),
    }
    for edge_id, endpoints in expected.items():
        assert (edges[edge_id]["source"], edges[edge_id]["target"]) == endpoints
    assert not any(edge["source"] == "agent" and edge["target"] == "api" for edge in spec["edges"])
    assert "Lab 2" in edges["agent-search"]["label"]
    assert "Lab 3 で解除" in edges["agent-search"]["label"]
    assert "Lab 3 以降" in edges["agent-iq"]["label"]
    assert "Project MI" in edges["agent-toolbox"]["label"]
    assert "匿名" in edges["toolbox-api"]["label"]
    assert "gpt-5.5" in edges["iq-planning"]["label"]
    assert "埋め込み" not in edges["iq-planning"]["label"]
    for node_id, lab in (("agent", "Lab 2"), ("iq", "Lab 3"), ("toolbox", "Lab 4")):
        assert lab in nodes[node_id]["detail"]


def assert_deployment_ownership(spec: dict) -> None:
    nodes = indexed(spec, "nodes")
    edges = indexed(spec, "edges")
    participant = {"create-rg", "load-template", "start", "confirm"}
    internal = {
        "resources",
        "connections",
        "bootstrap",
        "source",
        "seed",
        "evaluation",
        "validation",
        "outputs",
    }
    assert set(nodes) == participant | internal
    for name in participant:
        assert nodes[name]["parent"] == "participant-actions"
    for name in internal:
        assert nodes[name]["parent"] == "template-internal"
    expected = {
        "start-resources": ("start", "resources"),
        "connections-bootstrap": ("connections", "bootstrap"),
        "bootstrap-source": ("bootstrap", "source"),
        "source-seed": ("source", "seed"),
        "seed-evaluation": ("seed", "evaluation"),
        "evaluation-validation": ("evaluation", "validation"),
        "validation-outputs": ("validation", "outputs"),
        "outputs-confirm": ("outputs", "confirm"),
    }
    for edge_id, endpoints in expected.items():
        assert (edges[edge_id]["source"], edges[edge_id]["target"]) == endpoints
    assert "--prepare-only" in nodes["evaluation"]["detail"]
    assert "ジョブ実行なし" in nodes["evaluation"]["detail"]
    assert "Python で埋め込み" in nodes["seed"]["detail"]
    assert "全段階成功後" in nodes["outputs"]["detail"]
    assert "complete" in nodes["confirm"]["detail"]
    assert "Succeeded" in nodes["confirm"]["detail"]


def test_diagram_service_paths_match_the_lab_boundaries() -> None:
    assert_service_paths(load_spec(SPEC_NAMES[0]))


def test_diagram_deployment_actions_match_the_bootstrap_boundaries() -> None:
    assert_deployment_ownership(load_spec(SPEC_NAMES[1]))


@pytest.mark.parametrize("mutation", ["direct-api", "separate-iq", "simultaneous-search"])
def test_service_contract_rejects_incorrect_architectures(mutation: str) -> None:
    spec = copy.deepcopy(load_spec(SPEC_NAMES[0]))
    if mutation == "direct-api":
        spec["edges"].append({"id": "invalid", "source": "agent", "target": "api"})
    elif mutation == "separate-iq":
        indexed(spec, "nodes")["iq"]["parent"] = "azure"
    else:
        indexed(spec, "edges")["agent-search"]["label"] = "Lab 2: 直接検索"
    with pytest.raises(AssertionError):
        assert_service_paths(spec)


@pytest.mark.parametrize("mutation", ["user-bootstrap", "eval-job", "early-complete"])
def test_deployment_contract_rejects_incorrect_execution(mutation: str) -> None:
    spec = copy.deepcopy(load_spec(SPEC_NAMES[1]))
    if mutation == "user-bootstrap":
        indexed(spec, "nodes")["bootstrap"]["parent"] = "participant-actions"
    elif mutation == "eval-job":
        indexed(spec, "nodes")["evaluation"]["detail"] = "評価ジョブを実行"
    else:
        indexed(spec, "edges")["validation-outputs"]["source"] = "resources"
    with pytest.raises(AssertionError):
        assert_deployment_ownership(spec)


def test_diagram_uses_model_and_index_names_from_repository_sources() -> None:
    nodes = indexed(load_spec(SPEC_NAMES[0]), "nodes")
    template = json.loads((ROOT / "infra" / "azuredeploy.json").read_text(encoding="utf-8"))
    models = [
        resource
        for resource in template["resources"]
        if resource["type"] == "Microsoft.CognitiveServices/accounts/deployments"
    ]
    assert len(models) == 3
    for resource in models:
        assert resource["properties"]["model"]["name"] in nodes["models"]["detail"]
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["search_indexes"]) == 2
    for index in manifest["search_indexes"]:
        assert index["name"] in nodes["search"]["detail"]


def test_published_presentation_contains_current_native_nodes_and_flows() -> None:
    with zipfile.ZipFile(DIAGRAMS / "azure-architecture.pptx") as package:
        for number, name in enumerate(SPEC_NAMES, 1):
            spec = load_spec(name)
            root = ET.fromstring(package.read(f"ppt/slides/slide{number}.xml"))
            properties = root.findall(".//p:cNvPr", NS)
            names = {item.attrib.get("name", "") for item in properties}
            assert {item for item in names if item.startswith("service:")} == {
                f"service:{node['id']}" for node in spec["nodes"]
            }
            assert {item.rsplit(":", 1)[0] for item in names if item.startswith("flow:")} == {
                f"flow:{edge['id']}" for edge in spec["edges"]
            }
            visible = "".join(item.text or "" for item in root.findall(".//a:t", NS))
            normalized = "".join(visible.split())
            for node in spec["nodes"]:
                assert "".join(node["label"].split()) in normalized
                assert "".join(node.get("detail", "").split()) in normalized
            assert "Codespaces" not in visible
            assert "Dev Container" not in visible


def test_published_presentation_has_no_personal_author_metadata() -> None:
    with zipfile.ZipFile(DIAGRAMS / "azure-architecture.pptx") as package:
        core = ET.fromstring(package.read("docProps/core.xml"))
    for name in ("dc:creator", "cp:lastModifiedBy"):
        node = core.find(name, NS)
        assert node is None or not (node.text or "").strip()
