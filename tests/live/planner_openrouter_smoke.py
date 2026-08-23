"""Explicit live OpenRouter smoke test; excluded from unit-test discovery."""

import asyncio

from citeguard.planner.activity import plan_research
from citeguard.planner.contracts import PlannerActivityInput


async def main() -> None:
    """Call the live Planner boundary and print its validated subquestions.

    Side effects:
        Sends one paid OpenRouter request using process-environment credentials
        and writes contract-safe result fields, never the API key, to stdout.
    """

    result = await plan_research(
        PlannerActivityInput(
            research_question=(
                "Explain the Transformer architecture, self-attention matrix "
                "calculation, and the purposes of padding and causal masks."
            ),
            session_id="openrouter-smoke",
            existing_notes=[],
        )
    )

    print(f"Planner returned {len(result.sub_questions)} subquestions:")
    for sub_question in result.sub_questions:
        print(f"- {sub_question.id}: {sub_question.question}")


if __name__ == "__main__":
    asyncio.run(main())
