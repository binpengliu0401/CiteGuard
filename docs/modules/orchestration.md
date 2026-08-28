# Temporal Orchestration

> Status: exactly-one-Researcher Workflow and Worker implemented; memory,
> fan-out, content correction, progress queries, and persistence planned.
> Owning source: `src/citeguard/workflows/`, Activities and `worker.py`.

## 1. Purpose

Temporal provides durable orchestration for a long-running research process. It preserves completed work, records Activity results and restarts only work that has not completed successfully.

Temporal is not used to make research decisions. Planner, Researcher, Writer and Verifier Activities own those decisions or transformations.

## 2. Workflow boundary

The complete Workflow is intended to:

1. schedule Planner;
2. combine memory-reused results with new research tasks;
3. schedule one Researcher Activity per new subquestion;
4. aggregate all results;
5. schedule Writer and Verifier;
6. on content failure, select only failed subquestions for another research pass;
7. on approval, persist verified notes and return the report.

The Workflow may branch on recorded Activity results. It must not directly call an LLM, MCP, HTTP API, database, filesystem, subprocess, ordinary clock, random generator or UUID source.

The implemented first slice schedules Planner, requires exactly one returned
subquestion, schedules one Researcher, then schedules Writer and Verifier. It
returns `CiteGuardWorkflowResult` containing the subquestion, research result,
report, and verification decision. Memory lookup, note persistence, fan-out,
and content correction are not part of this slice.

## 3. Dynamic fan-out

Roles remain fixed, but Researcher task instances are dynamic:

```text
researchable = subquestions whose status requires new work
active concurrency = min(len(researchable), configured concurrency cap)
```

If the plan contains more tasks than the cap, tasks run in waves. Logical task count, simultaneous Activity count and Worker-process count are separate concepts.

The implemented end-to-end Workflow uses exactly one Researcher. A plan with
any other task count fails nonretryably as `SingleResearcherLimitExceeded`
instead of dropping planned work. Parallel fan-out is added in a later slice.

## 4. Determinism

- Planner and other nondeterministic work run as Activities;
- Activity results are recorded in Workflow history;
- replay reads recorded results and recreates the same Temporal commands;
- Workflow data uses project-owned serializable contracts;
- clients and Workers use the project Pydantic Temporal data converter so
  nested dataclasses and string-valued Enums reconstruct as domain types;
- MCP SDK and model-provider objects never enter Workflow state.

## 5. Activity granularity

The implemented `research_sub_question` Activity owns one research subquestion,
which preserves independent infrastructure retry, progress, and future content
correction. Within that one task, its bounded search queries share one MCP stdio
session and execute concurrently. MCP query batching does not cross the Activity
boundary or combine business subquestions.

The implemented `write_report` Activity accepts one aggregated `WriterInput`
after research completion and returns a deterministic `WrittenReport`. It has no
external calls or internal retry policy: it preserves ordered results, Claim and
source provenance, evidence state, and distinct source limitations. The formal
Workflow schedules it after the sole Researcher completes.

The implemented `verify_report` Activity accepts `VerifierInput` and returns
content rejection as a normal `VerificationResult`, preserving the distinction
from infrastructure retry. An invented report section is a deterministic
nonretryable Activity failure because its identifier cannot map to a valid
Researcher content-retry target. The formal Workflow schedules this Activity
after Writer and returns its decision to the caller.

## 6. Two failure classes

| Property | Infrastructure failure | Content failure |
| --- | --- | --- |
| Example | timeout, rate limit, Worker interruption | unsupported claim or inadequate evidence |
| Recovery owner | Temporal Activity Retry Policy | Explicit Workflow logic after Verifier result |
| Retry input | Unchanged | Adds Verifier feedback |
| Retry scope | Failed Activity attempt | Researcher tasks selected by failed subquestion IDs |
| Meaning | Environment may recover | Previous research content must change |

These paths remain separate in the implemented minimum. Retryable Planner and
Researcher failures use Temporal retries. Verifier rejection completes as a
normal Workflow result; targeted correction is planned and does not run yet.

## 7. Retry and limits

The implemented Workflow defines:

- Planner: 3-minute attempt, 10-minute total, at most three attempts;
- Researcher: 15-minute attempt, 30-minute total, at most three attempts;
- Writer and Verifier: 30-second attempt, 1-minute total, one attempt;
- deterministic capability and validation errors remain nonretryable.

The future fan-out and content-correction slices must define:

- maximum parallel Researcher Activities;
- maximum content-correction rounds;
- behavior when Verifier repeatedly rejects the same subquestion;
- cancellation and final failure reporting.

Initial implemented values remain local constants until measurements justify
configuration.

## 8. Progress state (planned)

The Workflow must expose enough state for the API to report:

- plan and subquestion statuses;
- Researcher running/completed/retrying states;
- Writer and Verifier states;
- infrastructure retry attempts;
- content failure reason and selected subquestions;
- final approval or terminal failure.

Progress state is derived from durable business state, not from parsing logs.

## 9. Coupled-change checklist

When changing orchestration:

1. review the scheduled Activity contract;
2. preserve Workflow determinism;
3. review retry and timeout behavior;
4. update Worker registration;
5. update progress-query/API state;
6. add replay or interruption validation where the change affects history;
7. update this document and `docs/STATUS.md`.

## 10. Verification

- one-Researcher end-to-end Workflow completes — validated locally;
- supported and Verifier-rejected executions each record four completed
  Activities and one completed Workflow — validated locally;
- one retryable Researcher failure reaches attempt two and completes without
  becoming content failure — validated locally;
- nested Workflow input and result contracts round-trip through the configured
  Temporal converter — covered offline;
- parallel Activities show measured wall-clock benefit;
- Worker interruption preserves the Workflow;
- one infrastructure failure does not discard other completed results;
- one content failure reruns only selected subquestions with feedback;
- maximum correction rounds terminate predictably;
- replay remains deterministic after supported code changes.

## 11. Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Implemented the exactly-one-Researcher Workflow, production Worker/client, bounded retry policies, and real Temporal approved, rejected, and infrastructure-retried smoke paths. |
| 2026-08-28 | Added the deterministic `verify_report` Activity; content failure returns normally while unmappable sections fail nonretryably. |
| 2026-08-28 | Added the side-effect-free `write_report` Activity over deterministic Writer assembly; formal Workflow scheduling remains planned. |
| 2026-08-27 | Established the shared Pydantic Temporal converter and round-trip-tested the nested Writer/Verifier boundary contracts. |
| 2026-08-24 | Recorded the implemented per-subquestion Researcher Activity and its internal one-session concurrent query behavior. |
| 2026-08-23 | Separated the validated batch spike from the formal per-subquestion Activity target and defined adaptive fan-out and the two retry classes. |
