"""Explicit live Researcher smoke test; excluded from unit-test discovery."""

import asyncio

from citeguard.domain.research import (
    AnswerRequirement,
    SubQuestion,
    SubQuestionStatus,
)
from citeguard.researcher.activity import research_sub_question
from citeguard.researcher.contracts import ResearchTaskInput


async def main() -> None:
    """Run the Researcher path against OpenRouter and arXiv MCP.

    Side effects:
        Sends paid OpenRouter requests, starts a local MCP subprocess, performs
        arXiv requests, and prints validated result fields. Credentials are
        read from the process environment and are never printed.
    """

    result = await research_sub_question(
        ResearchTaskInput(
            sub_question=SubQuestion(
                id="sq-smoke-001",
                question=(
                    "What evidence do arXiv abstracts report about retrieval-"
                    "augmented generation reducing factual hallucinations in "
                    "large language models?"
                ),
                primary_answer_target=(
                    "Reported abstract-level evidence that retrieval-augmented "
                    "generation reduces factual hallucinations in LLMs."
                ),
                answer_requirements=[
                    AnswerRequirement(
                        id="req-001",
                        description=(
                            "Identify an evaluated retrieval-augmented "
                            "generation intervention."
                        ),
                    ),
                    AnswerRequirement(
                        id="req-002",
                        description=(
                            "Report the observed effect on factual "
                            "hallucinations and its evaluation setting."
                        ),
                    ),
                ],
                status=SubQuestionStatus.NEW,
            )
        )
    )

    print(f"Evidence status: {result.evidence_status.value}")
    for claim in result.claims:
        source_ids = ", ".join(claim.source_ids)
        print(f"- {claim.id}: {claim.statement} [{source_ids}]")
    if result.evidence_group is not None:
        print(
            "Evidence group: "
            f"{', '.join(result.evidence_group.source_ids)}"
        )
    if result.evidence_reason is not None:
        print(f"Evidence reason: {result.evidence_reason}")
    print(f"Used sources: {len(result.sources)}")
    for source in result.sources:
        print(f"- {source.source_id}: {source.title} ({source.url})")


if __name__ == "__main__":
    asyncio.run(main())
