"""Keep the editable and rendered architecture accurate for both environments."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SVG_NS = {"svg": "http://www.w3.org/2000/svg"}


def test_drawio_render_keeps_current_editable_source_and_both_environments() -> None:
    source = REPO_ROOT / "docs" / "diagrams" / "workshop-architecture.drawio"
    rendered = ET.parse(REPO_ROOT / "docs" / "images" / "workshop-architecture.drawio.svg")
    embedded = ET.fromstring(rendered.getroot().attrib["content"])
    assert ET.tostring(embedded) == ET.tostring(ET.parse(source).getroot())

    labels = [node.text for node in rendered.findall(".//svg:text", SVG_NS)]
    assert "Codespaces /" in labels
    assert "Azure Cloud Shell" in labels
    assert "Notebook / Python 3.13" in labels
    assert "Policy Agent" in labels
    assert "Harness Agent" not in labels


def test_legacy_architecture_source_and_render_offer_the_same_environments() -> None:
    source = json.loads(
        (REPO_ROOT / "docs" / "diagrams" / "workshop-architecture.excalidraw").read_text(
            encoding="utf-8"
        )
    )
    label = next(element for element in source["elements"] if element["id"] == "codespaces-text")
    assert "Codespaces" in label["text"]
    assert "Cloud Shell" in label["text"]
    assert label["width"] > 0 and label["height"] > 0

    rendered = ET.parse(REPO_ROOT / "docs" / "images" / "workshop-architecture.svg")
    labels = [node.text for node in rendered.findall(".//svg:text", SVG_NS)]
    assert "Codespaces" in labels
    assert "or Cloud Shell" in labels
