"""Deterministic orchestration for the minimal CiteGuard pipeline."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from citeguard.domain.report import (
    SubQuestionResult,
    VerificationResult,
    WrittenReport,
)
from citeguard.domain.research import ResearchResult
from citeguard.planner.contracts import (
    PlannerActivityInput,
    PlannerActivityOutput,
)
from citeguard.researcher.contracts import ResearchTaskInput
from citeguard.verifier.contracts import VerifierInput
from citeguard.writer.contracts import WriterInput
from citeguard.workflows.contracts import (
    CiteGuardWorkflowInput,
    CiteGuardWorkflowResult,
)

PLANNER_RETRY_POLICY = RetryPolicy(maximum_attempts=3)
RESEARCHER_RETRY_POLICY = RetryPolicy(maximum_attempts=3)
DETERMINISTIC_RETRY_POLICY = RetryPolicy(maximum_attempts=1)


@workflow.defn(name="citeguard_research")
class CiteGuardWorkflow:
    """Run Planner through Verifier with exactly one Researcher.

    The first vertical slice rejects plans containing more than one
    subquestion instead of silently dropping work. Verifier content rejection
    completes normally so callers can inspect the report and failed scope.

    Args:
        workflow_input: Original question and session identity.

    Returns:
        Results from Researcher, Writer, and Verifier for the sole subquestion.

    Raises:
        ApplicationError: If Planner does not produce exactly one subquestion.
        ActivityError: If a scheduled Activity exhausts its retry policy.

    Retry behavior:
        Planner and Researcher receive bounded infrastructure retries.
        Deterministic Writer and Verifier run once. Content correction remains
        outside this minimal slice.
    """

    @workflow.run
    async def run(
        self,
        workflow_input: CiteGuardWorkflowInput,
    ) -> CiteGuardWorkflowResult:
        plan = await workflow.execute_activity(
            "plan_research",
            PlannerActivityInput(
                research_question=workflow_input.research_question,
                session_id=workflow_input.session_id,
                existing_notes=[],
            ),
            result_type=PlannerActivityOutput,
            start_to_close_timeout=timedelta(minutes=3),
            schedule_to_close_timeout=timedelta(minutes=10),
            retry_policy=PLANNER_RETRY_POLICY,
        )
        if len(plan.sub_questions) != 1:
            raise ApplicationError(
                "The minimal Workflow requires exactly one subquestion; "
                f"Planner returned {len(plan.sub_questions)}",
                type="SingleResearcherLimitExceeded",
                non_retryable=True,
            )

        sub_question = plan.sub_questions[0]
        research_result = await workflow.execute_activity(
            "research_sub_question",
            ResearchTaskInput(sub_question=sub_question),
            result_type=ResearchResult,
            start_to_close_timeout=timedelta(minutes=15),
            schedule_to_close_timeout=timedelta(minutes=30),
            retry_policy=RESEARCHER_RETRY_POLICY,
        )
        writer_input = WriterInput(
            research_question=workflow_input.research_question,
            research_results=[
                SubQuestionResult(
                    sub_question=sub_question,
                    result=research_result,
                )
            ],
        )
        report = await workflow.execute_activity(
            "write_report",
            writer_input,
            result_type=WrittenReport,
            start_to_close_timeout=timedelta(seconds=30),
            schedule_to_close_timeout=timedelta(minutes=1),
            retry_policy=DETERMINISTIC_RETRY_POLICY,
        )
        verification = await workflow.execute_activity(
            "verify_report",
            VerifierInput(writer_input=writer_input, report=report),
            result_type=VerificationResult,
            start_to_close_timeout=timedelta(seconds=30),
            schedule_to_close_timeout=timedelta(minutes=1),
            retry_policy=DETERMINISTIC_RETRY_POLICY,
        )
        return CiteGuardWorkflowResult(
            sub_question=sub_question,
            research_result=research_result,
            report=report,
            verification=verification,
        )
