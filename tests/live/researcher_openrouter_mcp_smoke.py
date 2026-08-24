"""Explicit live Researcher smoke test; excluded from unit-test discovery."""

import asyncio

from citeguard.domain.research import SubQuestion, SubQuestionStatus
from citeguard.researcher.activity import research_sub_question
from citeguard.researcher.contracts import ResearchTaskInput


async def main() -> None:
    """Run the two-call Researcher path against OpenRouter and arXiv MCP.

    Side effects:
        Sends two paid OpenRouter requests, starts a local MCP subprocess,
        performs arXiv requests, and prints validated result fields. Credentials
        are read from the process environment and are never printed.
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
                status=SubQuestionStatus.NEW,
            )
        )
    )

    print(f"Evidence status: {result.evidence_status.value}")
    print(f"Answer: {result.answer}")
    if result.evidence_reason is not None:
        print(f"Evidence reason: {result.evidence_reason}")
    print(f"Used sources: {len(result.sources)}")
    for source in result.sources:
        print(f"- {source.source_id}: {source.title} ({source.url})")


if __name__ == "__main__":
    asyncio.run(main())
