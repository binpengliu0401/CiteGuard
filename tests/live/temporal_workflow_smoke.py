"""Run approved and rejected pipelines against a local Temporal server."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from temporalio import activity
from temporalio.api.enums.v1 import EventType
from temporalio.client import Client
from temporalio.worker import Worker

from citeguard.domain.report import (
    ReportSection,
    ReportStatement,
    WrittenReport,
)
from citeguard.domain.research import (
    AnswerRequirement,
    EvidenceGroup,
    EvidenceStatus,
    ResearchClaim,
    ResearchResult,
    ResearchSource,
    SubQuestion,
    SubQuestionStatus,
)
from citeguard.infrastructure.temporal import (
    TEMPORAL_DATA_CONVERTER,
    TEMPORAL_WORKFLOW_RUNNER,
)
from citeguard.planner.contracts import (
    PlannerActivityInput,
    PlannerActivityOutput,
)
from citeguard.researcher.contracts import ResearchTaskInput
from citeguard.verifier.activity import verify_written_report
from citeguard.writer.activity import write_report
from citeguard.writer.assembly import assemble_report
from citeguard.writer.contracts import WriterInput
from citeguard.workflows.citeguard_workflow import CiteGuardWorkflow
from citeguard.workflows.contracts import (
    CiteGuardWorkflowInput,
    CiteGuardWorkflowResult,
)

DEFAULT_OUTPUT = Path("tmp/temporal_workflow_smoke_result.json")
RESEARCH_RETRY_ATTEMPTS: list[int] = []


def _sub_question() -> SubQuestion:
    """Build the fixed Planner output used by the local smoke."""

    return SubQuestion(
        id="sq-001",
        question="What finding does the synthetic abstract report?",
        primary_answer_target="The synthetic abstract's finding",
        answer_requirements=[
            AnswerRequirement(
                id="req-001",
                description="State the evidence-backed finding.",
            )
        ],
        status=SubQuestionStatus.NEW,
    )


@activity.defn(name="plan_research")
async def plan_fixture(
    planner_input: PlannerActivityInput,
) -> PlannerActivityOutput:
    """Return one fixed subquestion without calling a model."""

    if not planner_input.research_question.strip():
        raise ValueError("research question must not be blank")
    return PlannerActivityOutput(sub_questions=[_sub_question()])


@activity.defn(name="research_sub_question")
async def research_fixture(
    research_input: ResearchTaskInput,
) -> ResearchResult:
    """Return one supported Claim without network retrieval."""

    source_id = "synthetic-001"
    statement = "The synthetic abstract reports a supported finding."
    if research_input.sub_question.id != "sq-001":
        raise ValueError("unexpected subquestion")
    return ResearchResult(
        claims=[
            ResearchClaim(
                id="claim-001",
                statement=statement,
                source_ids=[source_id],
            )
        ],
        evidence_status=EvidenceStatus.SUPPORTED,
        sources=[
            ResearchSource(
                title="Synthetic evidence study",
                url="https://example.test/synthetic-001",
                source_id=source_id,
                abstract=statement,
                supported_aspects="The requested synthetic finding.",
                limitations="This is deterministic smoke-test evidence.",
            )
        ],
        evidence_group=EvidenceGroup(source_ids=[source_id]),
    )


@activity.defn(name="research_sub_question")
async def research_retry_fixture(
    research_input: ResearchTaskInput,
) -> ResearchResult:
    """Fail once transiently, then return the deterministic research result."""

    attempt = activity.info().attempt
    RESEARCH_RETRY_ATTEMPTS.append(attempt)
    if attempt == 1:
        raise RuntimeError("synthetic transient Researcher failure")
    return await research_fixture(research_input)


@activity.defn(name="write_report")
async def write_changed_report(
    writer_input: WriterInput,
) -> WrittenReport:
    """Inject one changed statement to exercise Verifier rejection."""

    report = assemble_report(writer_input)
    original = report.sections[0].statements[0]
    return WrittenReport(
        research_question=report.research_question,
        sections=[
            ReportSection(
                sub_question_id="sq-001",
                evidence_status=EvidenceStatus.SUPPORTED,
                statements=[
                    ReportStatement(
                        id=original.id,
                        text="The report adds an unsupported conclusion.",
                        sub_question_id="sq-001",
                        claim_ids=list(original.claim_ids),
                        source_ids=list(original.source_ids),
                    )
                ],
            )
        ],
        limitations=list(report.limitations),
    )


async def _run_case(
    client: Client,
    case_name: str,
    writer_activity,
    research_activity=research_fixture,
) -> dict[str, object]:
    """Run one real Workflow and summarize its result and history."""

    task_queue = f"citeguard-smoke-{case_name}-{uuid4()}"
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[CiteGuardWorkflow],
        activities=[
            plan_fixture,
            research_activity,
            writer_activity,
            verify_written_report,
        ],
        workflow_runner=TEMPORAL_WORKFLOW_RUNNER,
    )
    async with worker:
        handle = await client.start_workflow(
            CiteGuardWorkflow.run,
            CiteGuardWorkflowInput(
                research_question="What is the synthetic finding?",
                session_id="temporal-smoke",
            ),
            id=f"citeguard-smoke-{case_name}-{uuid4()}",
            task_queue=task_queue,
            result_type=CiteGuardWorkflowResult,
        )
        result = await handle.result()

    event_names = [
        EventType.Name(event.event_type)
        async for event in handle.fetch_history_events()
    ]
    return {
        "approved": result.verification.approved,
        "failed_sub_question_ids": (
            result.verification.failed_sub_question_ids
        ),
        "issue_types": [
            issue.type.value for issue in result.verification.issues
        ],
        "report_statement": (
            result.report.sections[0].statements[0].text
        ),
        "completed_activity_events": event_names.count(
            "EVENT_TYPE_ACTIVITY_TASK_COMPLETED"
        ),
        "workflow_completed_events": event_names.count(
            "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"
        ),
        "history_event_count": len(event_names),
    }


async def run_smoke(address: str) -> dict[str, object]:
    """Execute both business terminal states on a local Temporal server."""

    client = await Client.connect(
        address,
        data_converter=TEMPORAL_DATA_CONVERTER,
    )
    approved = await _run_case(
        client,
        "approved",
        write_report,
    )
    rejected = await _run_case(
        client,
        "rejected",
        write_changed_report,
    )
    RESEARCH_RETRY_ATTEMPTS.clear()
    retried = await _run_case(
        client,
        "retried",
        write_report,
        research_retry_fixture,
    )
    retried["research_attempts"] = list(RESEARCH_RETRY_ATTEMPTS)
    if not approved["approved"]:
        raise AssertionError("approved smoke case was rejected")
    if rejected["approved"]:
        raise AssertionError("rejected smoke case was approved")
    if RESEARCH_RETRY_ATTEMPTS != [1, 2]:
        raise AssertionError("Researcher retry attempts did not match [1, 2]")
    for case in (approved, rejected, retried):
        if case["completed_activity_events"] != 4:
            raise AssertionError("expected four completed Activities")
        if case["workflow_completed_events"] != 1:
            raise AssertionError("expected one completed Workflow")
    return {
        "temporal_address": address,
        "approved_case": approved,
        "rejected_case": rejected,
        "retried_case": retried,
    }


def main() -> None:
    """Run the smoke and save its human-reviewable JSON evidence."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--address", default="127.0.0.1:7233")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = asyncio.run(run_smoke(args.address))
    serialized = json.dumps(result, indent=2, ensure_ascii=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
