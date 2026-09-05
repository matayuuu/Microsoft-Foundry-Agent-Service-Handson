from __future__ import annotations

from types import SimpleNamespace

import pytest
from azure.core.exceptions import ResourceNotFoundError

from scripts import connect_toolbox

CONTEXT = {
    "terraform_outputs": {
        "foundry_project_endpoint": {"value": "https://project.example.invalid"},
        "foundry_project_id": {
            "value": "/subscriptions/test/resourceGroups/test/providers/project"
        },
    }
}


def test_connect_only_reads_existing_toolbox_and_adds_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Toolboxes:
        def get(self, name: str) -> SimpleNamespace:
            calls.append(("get", name))
            return SimpleNamespace(default_version="7")

        def get_version(self, name: str, version: str) -> None:
            calls.append(("get_version", name, version))

    def ensure_connection(**kwargs: object) -> dict:
        calls.append(("connect", kwargs))
        return {}

    def attach(client: object, **kwargs: object) -> dict:
        calls.append(("attach", kwargs))
        return {"action": "attached"}

    monkeypatch.setattr(connect_toolbox, "ensure_toolbox_connection", ensure_connection)
    monkeypatch.setattr(connect_toolbox, "attach_toolbox_to_agent", attach)
    result = connect_toolbox.connect_existing_toolbox(
        SimpleNamespace(toolboxes=Toolboxes()),
        credential="fake",
        context=CONTEXT,
        toolbox_name="contoso-travel-toolbox",
        agent_name="contoso-travel-assistant",
        connection_name="contoso-travel-toolbox-mcp",
    )

    assert result == {"action": "attached"}
    assert [call[0] for call in calls] == ["get", "get_version", "connect", "attach"]
    assert calls[2][1]["toolbox_endpoint"] == (
        "https://project.example.invalid/toolboxes/contoso-travel-toolbox/mcp?api-version=v1"
    )
    assert calls[3][1]["connection_name"] == "contoso-travel-toolbox-mcp"


def test_connect_refuses_missing_toolbox_before_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    class Toolboxes:
        def get(self, name: str) -> None:
            raise ResourceNotFoundError("Publish the toolbox first.")

    def forbidden(**kwargs: object) -> None:
        pytest.fail("Must not create a connection for an unpublished toolbox.")

    monkeypatch.setattr(connect_toolbox, "ensure_toolbox_connection", forbidden)
    with pytest.raises(ResourceNotFoundError):
        connect_toolbox.connect_existing_toolbox(
            SimpleNamespace(toolboxes=Toolboxes()),
            credential="fake",
            context=CONTEXT,
            toolbox_name="contoso-travel-toolbox",
            agent_name="contoso-travel-assistant",
            connection_name="contoso-travel-toolbox-mcp",
        )
