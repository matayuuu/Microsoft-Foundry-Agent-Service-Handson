"""Simple sequential Agent Framework workflow for the travel workshop."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from agent_framework.orchestrations import SequentialBuilder

WORKFLOW_NAME = "contoso-travel-planning-workflow"
WORKFLOW_DESCRIPTION = (
    "A simple policy review -> travel plan -> final review workflow. "
    "It produces a training-only estimate and never books or approves travel."
)

FOUNDRY_PROJECT_ENDPOINT_ENV = "FOUNDRY_PROJECT_ENDPOINT"
FOUNDRY_MODEL_ENV = "FOUNDRY_MODEL"

SIMULATION_NOTICE = "これはハンズオン用のシミュレーションであり、実際の予約・承認ではありません。"

WORKSHOP_POLICY = """
このハンズオンでは、次の簡略化した架空の規程だけを使います。
- 出発地、目的地、出発日、帰着日、座席クラス、出張目的が必要です。
- 国内出張は economy のみ利用できます。
- 国内出張の食事日当は 1 人 1 日 3,000 円、宿泊上限は 1 人 1 泊 15,000 円です。
- 海外出張はマネージャーの事前確認が必要です。business は部門 VP の確認も必要です。
- 航空券価格はこのサンプルでは計算せず「要見積もり」とします。
""".strip()

POLICY_AGENT_INSTRUCTIONS = f"""
あなたは Contoso の policy_agent です。
ユーザーの出張依頼を読み、必要情報の不足と規程上の注意点を日本語で簡潔に整理してください。
値を推測せず、不足項目は不足していると明記してください。

{WORKSHOP_POLICY}

実際の予約や承認を行ったとは絶対に表現しないでください。
""".strip()

PLANNER_AGENT_INSTRUCTIONS = f"""
あなたは Contoso の planner_agent です。
元の依頼と policy_agent の確認結果を読み、食事・宿泊の概算と次のアクションを含む
短い出張案を日本語で作成してください。不足情報がある場合は計算せず、確認事項を列挙します。

{WORKSHOP_POLICY}

航空券は「要見積もり」とし、実際の予約や承認を行ったとは表現しないでください。
""".strip()

REVIEWER_AGENT_INSTRUCTIONS = f"""
あなたは Contoso の reviewer_agent です。
元の依頼、policy_agent の確認結果、planner_agent の案を読み、矛盾や計算ミスを修正して
最終回答を日本語で返してください。回答は「規程確認」「概算」「次のアクション」の順にし、
最後に必ず次の一文をそのまま付けてください。

{SIMULATION_NOTICE}
""".strip()

SAMPLE_REQUEST = (
    "2026年9月10日から11日まで、東京から大阪へ1名で社内レビューに行きます。"
    "座席クラスは economy です。規程確認と概算を作ってください。"
)


def create_chat_client() -> Any:
    """Create the Foundry client used by every participant agent."""
    from agent_framework_foundry import FoundryChatClient
    from azure.identity import DefaultAzureCredential

    return FoundryChatClient(
        project_endpoint=os.environ[FOUNDRY_PROJECT_ENDPOINT_ENV],
        model=os.environ[FOUNDRY_MODEL_ENV],
        # Uses `az login` locally and the Hosted Agent managed identity after deployment.
        credential=DefaultAzureCredential(),
    )


def build_workflow(*, chat_client: Any | None = None) -> Any:
    """Create three agents and connect them in one readable sequence."""
    client = chat_client or create_chat_client()

    policy_agent = client.as_agent(
        name="policy_agent",
        instructions=POLICY_AGENT_INSTRUCTIONS,
    )
    planner_agent = client.as_agent(
        name="planner_agent",
        instructions=PLANNER_AGENT_INSTRUCTIONS,
    )
    reviewer_agent = client.as_agent(
        name="reviewer_agent",
        instructions=REVIEWER_AGENT_INSTRUCTIONS,
    )

    participants = [policy_agent, planner_agent, reviewer_agent]
    return SequentialBuilder(participants=participants).build()


async def run_workflow(user_text: str, *, chat_client: Any | None = None) -> str:
    """Run the sequence once and return the final reviewer's text."""
    result = await build_workflow(chat_client=chat_client).run(user_text)
    outputs = result.get_outputs()
    if not outputs or not outputs[-1].text:
        raise RuntimeError("Workflow completed without a final reviewer response.")
    return outputs[-1].text


async def _demo() -> None:
    print(await run_workflow(SAMPLE_REQUEST))


if __name__ == "__main__":
    asyncio.run(_demo())
