"""Shared Agent Framework wiring for the Contoso travel workshop."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

import httpx
from agent_framework import (
    Agent,
    AgentModeProvider,
    FileSystemAgentFileStore,
    InMemoryHistoryProvider,
    MCPStreamableHTTPTool,
    create_harness_agent,
    todos_remaining,
    todos_remaining_message,
)
from agent_framework.foundry import FoundryChatClient, FoundryToolbox
from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

FOUNDRY_PROJECT_ENDPOINT_ENV = "FOUNDRY_PROJECT_ENDPOINT"
FOUNDRY_MODEL_ENV = "FOUNDRY_MODEL"
SEARCH_SERVICE_ENDPOINT_ENV = "AZURE_AI_SEARCH_SERVICE_ENDPOINT"
KNOWLEDGE_BASE_NAME_ENV = "AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME"
TOOLBOX_NAME_ENV = "TOOLBOX_NAME"

DEFAULT_KNOWLEDGE_BASE_NAME = "contoso-travel-knowledge-lab"
DEFAULT_TOOLBOX_NAME = "contoso-travel-toolbox"
# Luna is supported by the August API (Microsoft Learn, retrieved 2026-09-10).
FOUNDRY_IQ_API_VERSION = "2026-08-01-preview"
SEARCH_TOKEN_SCOPE = "https://search.azure.com/.default"

HARNESS_AGENT_NAME = "travel_harness_agent"
HARNESS_AGENT_DESCRIPTION = (
    "Plans a travel request, retrieves Contoso policy, loads Toolbox Skills, "
    "and uses Tool Search to select the required travel tools."
)
HARNESS_AGENT_INSTRUCTIONS = """
あなたは Contoso 社内向けの出張・経費 Harness Agent です。

複雑な依頼は todo に分解し、各 todo を完了してから最終回答を作成してください。
情報源と機能の役割を混同してはいけません。
plan mode では計画と todos の作成だけを行い、Foundry IQ、Skill、Toolbox tool、
Web Search を実行しないでください。ユーザーが計画を承認して execute mode へ移った後に実行します。

- 社内規程と承認手続きの根拠は Foundry IQ で検索し、引用を付ける。
- 操作手順が必要なら Toolbox の Skill を読み込み、その手順に従う。
- Toolbox の tool が必要なら、Tool Search の tool_search で候補を探し、call_tool で実行する。
- tool_search の query は日本語の説明文にせず、目的に合う英語の tool 名を1つ使う。
  見積もりは createTripEstimate、日当照会は getPerDiem、明示された承認シミュレーションは
  createPreapproval、数値計算は code_interpreter、明示された公開情報検索は web_search。
  検索結果の正式な name と inputSchema を確認して call_tool を呼び、未発見の tool を推測しない。
- 費用・日当・承認シミュレーションは Travel Ops API の結果を使い、値を創作しない。
- 比率や複数結果の比較は Code Interpreter を使う。
- Web Search は、現在の公開情報をユーザーが明示的に求めた場合だけ使い、取得時点と出典を示す。

予約や実際の承認は行いません。事前承認シミュレーションはユーザーが明示的に依頼した
場合だけ実行し、実際の承認とは区別してください。必要情報が不足している場合は推測せず、
確認事項を示してください。
""".strip()

PLAIN_AGENT_INSTRUCTIONS = """
あなたは Contoso 社内向けの出張・経費アシスタントです。
社内規程に関する質問は Foundry IQ を使って調べ、回答に根拠を付けてください。
確認できない値を推測せず、検索結果にない場合は情報が見つからないと伝えてください。
この Agent はまだ費用計算や承認シミュレーションの tool を持っていません。
""".strip()


class AzureTokenCredentialAuth(httpx.Auth):
    """Attach a fresh Azure bearer token to every HTTP request."""

    def __init__(self, credential: TokenCredential, scope: str) -> None:
        self._credential = credential
        self._scope = scope

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self._credential.get_token(self._scope).token}"
        yield request


class FoundryIQTool(MCPStreamableHTTPTool):
    """MCP tool that owns its authenticated Azure AI Search HTTP client."""

    def __init__(
        self,
        credential: TokenCredential,
        *,
        search_endpoint: str,
        knowledge_base_name: str = DEFAULT_KNOWLEDGE_BASE_NAME,
    ) -> None:
        endpoint = (
            f"{search_endpoint.rstrip('/')}/knowledgebases/{knowledge_base_name}"
            f"/mcp?api-version={FOUNDRY_IQ_API_VERSION}"
        )
        self._owned_http_client = httpx.AsyncClient(
            auth=AzureTokenCredentialAuth(credential, SEARCH_TOKEN_SCOPE),
            timeout=120.0,
        )
        super().__init__(
            name="contoso-travel-knowledge",
            url=endpoint,
            http_client=self._owned_http_client,
            allowed_tools=["knowledge_base_retrieve"],
            load_prompts=False,
            approval_mode="never_require",
        )

    async def close(self) -> None:
        try:
            await super().close()
        finally:
            await self._owned_http_client.aclose()


def create_credential() -> TokenCredential:
    """Use Azure CLI locally and the Hosted Agent identity after deployment."""
    return DefaultAzureCredential()


def create_chat_client(
    credential: TokenCredential,
    *,
    project_endpoint: str | None = None,
    model: str | None = None,
) -> FoundryChatClient:
    """Create the single Foundry chat client shared by workshop agents."""
    return FoundryChatClient(
        project_endpoint=project_endpoint or os.environ[FOUNDRY_PROJECT_ENDPOINT_ENV],
        model=model or os.environ[FOUNDRY_MODEL_ENV],
        credential=credential,
    )


def create_foundry_iq_tool(
    credential: TokenCredential,
    *,
    search_endpoint: str | None = None,
    knowledge_base_name: str | None = None,
) -> FoundryIQTool:
    """Create the Foundry IQ MCP adapter from explicit values or environment."""
    return FoundryIQTool(
        credential,
        search_endpoint=search_endpoint or os.environ[SEARCH_SERVICE_ENDPOINT_ENV],
        knowledge_base_name=(
            knowledge_base_name
            or os.environ.get(KNOWLEDGE_BASE_NAME_ENV, DEFAULT_KNOWLEDGE_BASE_NAME)
        ),
    )


def create_toolbox(
    credential: TokenCredential,
    *,
    toolbox_name: str | None = None,
    toolbox_endpoint: str | None = None,
) -> FoundryToolbox:
    """Create the authenticated Toolbox MCP adapter used by tools and Skills."""
    resolved_name = toolbox_name or os.environ.get(TOOLBOX_NAME_ENV, DEFAULT_TOOLBOX_NAME)
    return FoundryToolbox(
        credential,
        name=resolved_name,
        url=toolbox_endpoint,
        load_tools=True,
        approval_mode="never_require",
    )


def build_plain_travel_agent(
    *,
    chat_client: Any,
    foundry_iq_tool: Any,
) -> Agent[Any]:
    """Build the beginner Agent that has one Foundry IQ tool."""
    return Agent(
        client=chat_client,
        name="travel_policy_agent",
        description="Answers Contoso travel-policy questions with Foundry IQ.",
        instructions=PLAIN_AGENT_INSTRUCTIONS,
        tools=[foundry_iq_tool],
    )


def build_harness_travel_agent(
    *,
    chat_client: Any,
    foundry_iq_tool: Any,
    toolbox: Any,
    default_mode: str = "plan",
    history_provider: Any | None = None,
    file_memory_store: Any | None = None,
    default_options: dict[str, Any] | None = None,
) -> Agent[Any]:
    """Build the shared Harness Agent used interactively and in the workflow."""
    skills_provider = toolbox.as_skills_provider(
        disable_load_skill_approval=True,
        disable_read_skill_resource_approval=True,
    )
    memory_store = (
        file_memory_store
        if file_memory_store is not None
        else FileSystemAgentFileStore(
            str(Path(os.environ.get("HOME") or os.getcwd()) / "agent-file-memory")
        )
    )
    return create_harness_agent(
        client=chat_client,
        name=HARNESS_AGENT_NAME,
        description=HARNESS_AGENT_DESCRIPTION,
        agent_instructions=HARNESS_AGENT_INSTRUCTIONS,
        tools=[foundry_iq_tool, toolbox],
        history_provider=(
            history_provider if history_provider is not None else InMemoryHistoryProvider()
        ),
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        file_memory_store=memory_store,
        skills_provider=skills_provider,
        mode_provider=AgentModeProvider(default_mode=default_mode),
        disable_web_search=True,
        disable_tool_auto_approval=True,
        loop_should_continue=todos_remaining(looping_modes=["execute"]),
        loop_next_message=todos_remaining_message,
        loop_max_iterations=6,
        default_options=default_options,
    )


def build_environment_harness_agent(
    *,
    default_mode: str,
    hosted: bool,
    file_memory_store: Any | None = None,
) -> Agent[Any]:
    """Build the full travel Harness Agent from deployed environment values."""
    credential = create_credential()
    chat_client = create_chat_client(credential)
    foundry_iq_tool = create_foundry_iq_tool(credential)
    toolbox = create_toolbox(credential)
    return build_harness_travel_agent(
        chat_client=chat_client,
        foundry_iq_tool=foundry_iq_tool,
        toolbox=toolbox,
        default_mode=default_mode,
        # Stateless service calls still need one local history for the Harness tool loop.
        # Disabling loads makes Agent inject a second provider with the same source ID.
        history_provider=InMemoryHistoryProvider(),
        file_memory_store=file_memory_store,
        default_options={"store": False} if hosted else None,
    )
