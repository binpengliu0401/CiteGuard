# Domain Contracts

> Status: partially implemented.
> Owning source: `src/citeguard/domain/`.

## 1. Purpose

This module defines the stable, serializable business objects exchanged between Planner, Workflow, Researcher, Writer, Verifier and Memory. It prevents any one module from making the rest of the system depend on an LLM SDK, MCP SDK or storage-specific object.

## 2. Current implementation

`src/citeguard/domain/research.py` currently defines:

- `SubQuestionStatus.NEW`;
- `SubQuestionStatus.REUSED_FROM_MEMORY`;
- `EvidenceStatus` with `supported`, `no_relevant_sources`, and
  `insufficient_evidence`;
- `AnswerRequirement`;
- `ResearchClaim` and `EvidenceGroup`;
- `ResearchSource`;
- `ResearchResult`;
- `ResearchNote`;
- `SubQuestion` and its status-dependent invariants.

The objects are frozen dataclasses. Required text is validated without silently trimming or rewriting caller input.

`src/citeguard/planner/contracts.py` defines validated `PlannerActivityInput` and
`PlannerActivityOutput` durable-boundary contracts.

`src/citeguard/researcher/contracts.py` defines `ResearchTaskInput`, which carries
one domain subquestion and the optional Verifier feedback reserved for a future
content-retry slice.

`src/citeguard/domain/report.py` defines `SubQuestionResult`,
`ReportStatement`, `ReportSection`, `WrittenReport`, `VerificationIssue`, and
`VerificationResult`. `src/citeguard/writer/contracts.py` and
`src/citeguard/verifier/contracts.py` define the durable inputs for the
implemented deterministic Writer and Verifier Activities.

`src/citeguard/workflows/contracts.py` defines the session-scoped Workflow
input and the final result containing the sole subquestion, its ResearchResult,
the WrittenReport, and the VerificationResult. Verifier rejection is a valid
Workflow result rather than an infrastructure exception.

## 3. Contract boundaries

Three model categories must remain distinct:

| Category | Purpose | Example |
| --- | --- | --- |
| Domain model | Stable business meaning shared across modules | `ResearchResult`, `WrittenReport` |
| Activity contract | Serializable input/output at a durable boundary | `WriterInput`, `VerifierInput` |
| LLM schema | Strict validation of one model call | `DecompositionOutput`, `PlanningOutput` |

An LLM schema must be assembled into a domain model before it leaves its owning Activity. Temporal Workflow code must not interpret provider-specific or Pydantic-specific response objects.

## 4. Current invariants

### `ResearchSource`

- `title`, `url`, `source_id`, and `abstract` are required and nonblank;
- `supported_aspects` records exactly what the source contributes to the answer;
- `limitations` records unsupported scope and evidence limitations;
- `abstract` is the assessed evidence boundary, not a generated summary or
  proof of full-paper support.

### `AnswerRequirement`, `ResearchClaim`, and `EvidenceGroup`

- every requirement has a stable ID and one nonblank completeness condition;
- every Claim has a project-owned ID, one atomic statement, and one or more
  unique source IDs;
- every evidence group is a nonempty unique source-ID set;
- Claim statements and answer requirements are frozen before group search.

### `ResearchResult`

- output is a structured Claim list; free factual answer paragraphs are not a
  Researcher contract;
- `evidence_status` is an `EvidenceStatus` value;
- `supported` requires Claims, used sources, and an `EvidenceGroup` whose IDs
  exactly match the result sources, and forbids an evidence reason;
- every result source must support at least one Claim, and every Claim source
  ID must exist in the result;
- `no_relevant_sources` requires an explanatory reason and forbids Claims,
  sources, and an evidence group;
- `insufficient_evidence` requires an explanatory reason; it may retain a
  partially useful Claim/source set, but never an evidence group;
- `sources` contains only sources that support a returned Claim.

### `ResearchNote`

- `id` and `question` are nonblank;
- `primary_answer_target` is required;
- `answer_requirements` is nonempty and its IDs are unique;
- `result` is the reusable unit stored by Memory.

### `SubQuestion`

- `id` and `question` are nonblank;
- `status=new` requires `reused_result=None` and `source_note_id=None`;
- `status=reused_from_memory` requires both a reusable result and a real source-note ID.

### Report and verification

- `SubQuestionResult` keeps every completed result paired with its planned
  scope; reused work must exactly match the result embedded by Planner;
- every material `ReportStatement` has a globally unique ID, one originating
  subquestion ID, and nonempty Claim and source provenance;
- section statements must use their section's subquestion ID;
- report section IDs are unique and limitations are nonblank and distinct;
- approved verification has no issues or failed IDs;
- rejected verification has typed issues and an exact matching set of failed
  business subquestion IDs;
- report shape validation does not decide evidence support or reject unknown
  provenance, because Verifier must observe those failures and localize them.

## 5. Frozen Writer/Verifier boundary

The short-term boundary consumed by the Writer/Verifier slice is:

```python
WriterInput(
    research_question=...,
    research_results=[SubQuestionResult(...)],
)

WrittenReport(
    research_question=...,
    sections=[ReportSection(...)],
)

VerifierInput(writer_input=..., report=...)

VerificationResult(
    approved=...,
    issues=[VerificationIssue(...)],
    failed_sub_question_ids=[...],
)
```

`failed_sub_question_ids` contains business `SubQuestion.id` values, not Temporal Activity IDs or process IDs. Every returned ID must exist in the results being verified.

Issues carry their own subquestion and reason because one report can fail for
independent provenance, support, scope, causality, modality, numeric, or
evidence-state violations. Workflow consumes only the deduplicated failed ID
set for retry selection.

While the implemented Writer, Verifier, and minimum Workflow consume this
boundary, changes to
`AnswerRequirement`, `ResearchClaim`, `ResearchSource`, `EvidenceGroup`,
`ResearchResult`, or their provenance meaning require a separate upstream
contract task before dependent work continues. Researcher prompts, retrieval,
relevance policy, and MEG search internals may evolve without changing this
boundary.

The Researcher-level atomic Claim and source provenance are implemented.
Writer/Verifier still needs semantic evidence-boundary dimensions, including
population, setting, method, time range, outcome, quantitative interval,
relation type, and modality. Those fields remain deferred until that slice.

## 6. Deferred status

`needs_recheck` exists in the original product design but not in the current enum. It must not be used in runtime behavior until its exact invariants are defined. When introduced, review Planner prompts, memory behavior, Workflow scheduling and all `SubQuestion` validation together.

## 7. Coupled-change checklist

When changing a domain contract:

1. update every Activity contract that embeds it;
2. update Planner/Researcher LLM schemas and assembly code where relevant;
3. check Temporal serialization compatibility for active Workflows;
4. update Writer, Verifier and Memory consumers;
5. add invariant and serialization tests;
6. update this document and `docs/STATUS.md`.

Backward-compatibility or Workflow-versioning work is added only when a deployed, still-running Workflow makes it necessary. The current local development phase has no such compatibility requirement.

## 8. Verification

Required tests for the current domain layer:

- valid construction for every status;
- blank required fields are rejected;
- status-specific forbidden and required fields are enforced;
- nested Writer/Verifier dataclasses round-trip through the configured Pydantic
  Temporal converter.
- nested Workflow input/result dataclasses round-trip through the same
  converter.

## 9. Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Added the exactly-one-Researcher Workflow input/result boundary and validated its nested Temporal round trip. |
| 2026-08-27 | Froze the Writer/Verifier durable boundary with attributable report statements, typed verification issues, exact failed-subquestion scope, and tested Temporal serialization. |
| 2026-08-26 | Replaced free-form Researcher answers with provenance-bound Claims, made source abstracts explicit and required, added fixed answer requirements and minimum evidence groups, and enforced their status-dependent invariants. |
| 2026-08-25 | Allowed source-free `insufficient_evidence` when candidate abstracts are explicitly classified as unknown; unknown candidates are not used as evidence. |
| 2026-08-24 | Recorded the planned atomic Claim and provenance-bound evidence boundary without prematurely fixing its production schema. |
| 2026-08-24 | Added explicit evidence statuses, per-source support/limitation notes, status-dependent `ResearchResult` invariants, and the Researcher Activity input contract. |
| 2026-08-23 | Added the implemented Planner Activity input/output contracts to the current contract inventory. |
| 2026-08-23 | Documented current domain objects, contract layers, invariants, planned retry identifiers and the deferred `needs_recheck` status. |
