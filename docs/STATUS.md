# CiteGuard Implementation Status

> Updated: 2026-08-28.
> This file records current implementation status, not the full product vision.

## 1. Current phase

The no-memory Planner is implemented and offline-tested. Its earlier contract
and the intermediate arXiv-only requirement policy produced valid live results;
the latest sufficiency and evidence-ownership policy awaits live revalidation.
Every planned subquestion freezes one primary answer target and explicit
completeness requirements limited to arXiv title-and-abstract evidence. The
formal single Researcher plans bounded arXiv retrieval,
derives paper relevance from factorized judgments, freezes provenance-bound
atomic Claims, and searches source combinations by increasing cardinality for a
fully supporting Minimum Evidence Group (MEG). Free-form Researcher factual
answers are no longer part of the runtime contract.

A Researcher paper-relevance and MEG Eval runner and 12-item Agent Memory draft
are implemented. The three manually authored cases each contain four candidate
papers and test Gold MEG sizes one, two, and three. Paper labels, group labels,
and Gold MEGs remain draft until two-person review. The dataset is explicitly
restricted to Researcher/MEG mechanism testing: its subquestions are not
Planner Gold, and its unresolved A-MEM and evolution-relation labels are stored
in an adjudication queue. Real MCP discovery and
concurrent arXiv retrieval passed previously; the new Claim/MEG path is verified
offline. Its fresh live smoke completed retrieval but not the later structured
model stage.

The first formal end-to-end Temporal Workflow is now implemented. It schedules
Planner, enforces exactly one new subquestion, schedules one Researcher, then
runs deterministic Writer and Verifier. Verifier rejection completes normally
as an inspectable result; infrastructure failure remains a Temporal retry or
Workflow failure. The production Worker registers all four Activities, and a
command-line client can start the Workflow. Local Temporal smokes validated
approved, rejected, and retry-then-success histories with synthetic upstream
Activities and the real Writer/Verifier.

The Writer/Verifier upstream and downstream boundary is now frozen over the
Researcher contract. `WriterInput` aggregates exact SubQuestion/ResearchResult
pairs, `WrittenReport` preserves statement-to-Claim-to-source provenance, and
`VerificationResult` returns typed issues plus an exact failed-subquestion set.
These nested contracts round-trip through the configured Temporal converter.
Deterministic Verifier decision behavior is now implemented.

A versioned six-case Writer/Verifier fixture is now implemented over that
boundary. It uses synthetic evidence and remains `draft`. The fixture covers a
single-source pass, multi-source MEG pass, invalid provenance, causal upgrade,
evidence-status overstatement, and exact localization of one failed sibling
subquestion. It fixes Writer Claim/status coverage and Gold Verifier decisions;
it does not treat exact prose as the Writer oracle.

Writer now also has an independent six-case Gold draft. It covers all three
evidence states, new and memory-reused results, zero/one/many Claims, singleton
and multi-source MEGs, one jointly supported Claim, and multi-section isolation.
The deterministic evaluator measures section and Claim coverage, evidence-state
preservation, and Claim/source provenance. Twelve typed mutations exercise every
Writer hard-failure category without treating free-form prose as deterministic
Gold.

The minimal Writer is now executable as deterministic assembly and a Temporal
Activity. It emits one `ReportSection` per ordered research result and one
`ReportStatement` per Claim, copies Claim text without paraphrase, preserves
Claim/source edges and evidence state, and retains distinct source limitations.
All six Writer Gold cases pass against this real implementation. Semantic prose
synthesis remains deferred rather than being hidden behind an uncalibrated
model call.

The deterministic Verifier is also executable as a Temporal Activity. It checks
section and Claim coverage, subquestion-scoped Claim identity, known sources,
exact Claim/source edges, evidence status/reason inheritance, duplicate Claim
use, and exact frozen Claim text. Content failures return a normal
`VerificationResult` with ordered failed subquestion IDs; an invented section
is a nonretryable Activity error because it has no valid Researcher retry target.
Free-text changes are conservatively rejected as `unsupported`. Fine-grained
causal, modality, numeric, contradiction, and scope classification remains a
planned semantic layer.

The quantitative Eval design is now documented. Researcher Assessment has a
draft dataset and metric runner, while Planner has no Gold dataset, calibrated
threshold, fixed semantic model, or semantic runner. Writer has an independent
fixed-contract Gold draft and deterministic structural metrics; the combined
Writer/Verifier fixture supplies candidate verification decisions. Minimal
deterministic Writer synthesis is implemented; semantic synthesis, Verifier
semantic classification, and end-to-end Eval remain unimplemented. Deterministic
Verifier gates are implemented. Evaluation quality must not be inferred from
schema-validation tests.

## 2. Capability status

| Capability | Status | Evidence |
| --- | --- | --- |
| Temporal hello Workflow | Validated spike | `test/temporal_test/hello_*` |
| MCP stdio arXiv search | Validated spike | `test/mcp_test/arxiv_client.py`, `arxiv_server.py` |
| Temporal Activity calling MCP | Validated spike | `test/temporal_test/arxiv_*` |
| Worker interruption recovery | Manually validated spike | Git history and the archived spike summary |
| Shared research-domain objects | Partial implementation with Claim/MEG contracts | `src/citeguard/domain/research.py` |
| Shared OpenRouter structured-output boundary | Implemented and live-validated through Planner | `src/citeguard/infrastructure/openrouter.py`, `tests/planner/test_llm.py` |
| Planner no-memory path | Implemented and offline-tested; current policy live revalidation pending | `src/citeguard/planner/`, `tests/planner/` |
| Planner memory-reuse path | Not implemented | Prompt/schema exist; Activity rejects nonempty notes explicitly |
| Formal CiteGuard Workflow and Worker | Exactly-one-Researcher slice implemented and locally validated | `src/citeguard/workflows/`, `src/citeguard/worker.py`, `tests/live/temporal_workflow_smoke.py` |
| Session memory store | Not implemented | No storage module exists |
| Formal single Researcher | Implemented, offline-tested and live-boundary validated | `src/citeguard/researcher/`, `tests/researcher/` |
| Researcher paper and MEG Eval | Implemented with draft labels | `src/citeguard/evaluation/`, `eval/`, `tests/evaluation/` |
| Writer/Verifier fixed fixture | Implemented as synthetic draft | `src/citeguard/evaluation/report.py`, `eval/datasets/writer_verifier_gold_draft_v0.json` |
| Writer Gold and hard-gate Eval | Implemented as synthetic draft | `src/citeguard/evaluation/writer.py`, `eval/datasets/writer_gold_draft_v0.json` |
| Remaining module and end-to-end Eval | Planned | Planner, retrieval, source-selection, evidence-state, Writer/Verifier, and end-to-end stages remain unimplemented |
| Writer | Minimal deterministic synthesis implemented | `src/citeguard/writer/assembly.py`, `src/citeguard/writer/activity.py` |
| Verifier | Deterministic hard gates implemented | `src/citeguard/verifier/verification.py`, `src/citeguard/verifier/activity.py` |
| Targeted content retry | Not implemented | Workflow behavior remains design only |
| FastAPI and React demo | Not implemented | Design only |

## 3. Known design-to-code differences

- The product design mentions `needs_recheck`; the current `SubQuestionStatus` implements only `new` and `reused_from_memory`.
- The formal Researcher now owns one subquestion per Activity. Its several
  search queries share one MCP session only inside that Activity.
- The Planner's memory-aware Prompt and schema exist, but the Activity intentionally supports only the no-memory path.
- Existing spike scripts live under `test/`, although they are manual experiments rather than an automated test suite.
- Planner uses a 4,000-token completion ceiling after two live responses to the
  strengthened decomposition policy truncated invalid JSON at 2,500 tokens.
- The first 4,000-token validation request remained unresponsive and was
  terminated, so the current strengthened policy is not yet live-validated.
- The current Planner output has no dependency field, so conditional relations
  such as "if so" are flattened into parallel tasks and must later be preserved
  during synthesis.
- The first OpenRouter request reached the service but the documentation example alias returned HTTP 404. The replacement `deepseek/deepseek-v4-flash-0731` default has since passed a live structured-output smoke test.
- A first live Researcher attempt exposed a 2,500-token synthesis ceiling that
  could be consumed by reasoning plus twelve paper assessments. Synthesis now
  has an 8,000-token per-call ceiling; the fixed retrieval, synthesis, and
  assembly stages passed live with four retained sources.

These differences are intentional status facts, not approved final behavior.

## 4. Current development slice

### Goal

Implement the first durable end-to-end Workflow without widening the frozen
module contracts:

```text
SubQuestion + ResearchResult
    → SubQuestionResult
    → WriterInput
    → WrittenReport with statement/Claim/source provenance
    → VerifierInput
    → VerificationResult with typed issues and failed subquestion IDs
```

### Implemented

- `EvidenceStatus` and status-dependent `ResearchResult` invariants;
- frozen `SubQuestionResult`, `WriterInput`, `WrittenReport`, `VerifierInput`,
  and `VerificationResult` boundary contracts;
- globally unique report statement identities with explicit subquestion,
  Claim, and source IDs;
- typed verification issues and approval/rejection invariants with exact retry
  scope;
- a shared Pydantic Temporal converter with nested contract round-trip tests;
- stable `ResearchTaskInput` with explicit gates for reused work and content retry;
- shared concrete OpenRouter code used by Planner and Researcher;
- one-to-five distinct search queries selected by the first structured model call;
- a formal arXiv MCP server returning full abstracts and a project-owned adapter
  that multiplexes concurrent queries through one session;
- an evidence-analysis model call constrained by six relevance criteria,
  factorized object/problem/constraint/evidence/coverage judgments, and required
  per-paper support/limitation fields;
- deterministic `direct`, `partial`, `background`, and `irrelevant` derivation
  that rejects contradictory factor combinations;
- a minimal `unknown` abstention that cannot be used as evidence and maps a
  source-free result to `insufficient_evidence`;
- structured Claim output with project-owned IDs and exact source provenance;
- fixed Planner answer requirements whose coverage is validated before MEG
  search;
- bottom-up, cardinality-batched MEG search with safe deterministic pruning and
  exact FULL/PARTIAL/NONE group validation, including enforcement that every
  Claim support source belongs to that Claim's frozen candidate set;
- required source `abstract` fields and supported-result evidence groups;
- Eval metrics for paper relevance, group support, complete MEG selection,
  cardinality error, and redundant sources;
- a versioned 12-item Agent Memory draft covering three cases, four papers per
  case, all relevance classes, and MEG sizes one through three;
- a versioned six-case synthetic Writer/Verifier draft with fixed Writer
  expectations, candidate reports, and Gold verification decisions;
- an independent six-case Writer Gold covering every v0 state partition, plus
  deterministic metrics and all typed hard-failure mutations;
- deterministic Writer assembly and a `write_report` Temporal Activity with no
  tools, model calls, or side effects;
- one statement per Claim, stable input ordering, evidence-state preservation,
  local Claim-ID scoping, and distinct source-limitations aggregation;
- deterministic Verifier checks for section/Claim coverage, known IDs, exact
  Claim/source edges, evidence-state inheritance, and frozen Claim text;
- a `verify_report` Temporal Activity that returns content failures normally and
  rejects unmappable invented sections as nonretryable input failures;
- `CiteGuardWorkflowInput` and an inspectable `CiteGuardWorkflowResult` that
  retains output from every completed downstream stage;
- a deterministic `citeguard_research` Workflow scheduling Planner, exactly one
  Researcher, Writer, and Verifier in order;
- explicit Planner/Researcher infrastructure retry policies and single-attempt
  deterministic Writer/Verifier policies;
- production Worker registration for the Workflow and all four Activities;
- a command-line client for starting a Workflow and printing its typed result;
- a real local Temporal smoke for approved, rejected, and retry-then-success
  paths, with four completed Activities per final execution;
- an enforced 80-character maximum for formal Python code and tests;
- 117 total formal offline tests covering style, Planner, domain, Researcher,
  Writer/Verifier, Workflow contracts/orchestration, Worker registration, and
  Eval;
- an explicit live Researcher smoke script that never prints credentials.

### Evaluation design completed today

- established one cross-module Eval source of truth and routed it from
  `SYSTEM.md`;
- reorganized the architecture guide so global Eval precedes business modules,
  while Planner, Researcher, and planned Writer/Verifier each own a nested,
  module-specific Eval section;
- defined equal-weight Planner aspect Coverage, explicit constraint hard gates,
  calibrated pairwise Redundancy, Fragmentation, Broadness diagnostics, and
  optional dependency-graph comparison;
- grounded Planner Eval in BREAK/QDMR and Sentence-BERT-style fixed semantic
  matching, with exact/graph metrics limited to compatible gold structures;
- separated Researcher query, retrieval, paper-assessment, source-selection,
  evidence-state, and abstract-level answer-support metrics;
- added BEIR/SciFact-based retrieval and evidence-evaluation rationale,
  Recall@K, Precision@K, MRR, nDCG formulas, graded relevance, and a frozen
  candidate-pool requirement;
- implemented the Researcher atomic Claim/provenance boundary and retained the
  richer Writer/Verifier EvidenceBoundary design for causality, modality,
  scope, and quantitative violations;
- added ALCE, SummaC, AlignScore, and RIGOURATE as Writer/Verifier baselines and
  method references, while retaining deterministic hard gates for attribution;
- separated module diagnosis from final report outcome, cost, latency, and
  correction-success evaluation;
- recorded that generative LLM judging is not the primary regression oracle and
  that any semantic-model threshold must be calibrated and versioned.
- implemented paper-relevance, group-support, and MEG metrics plus the Agent
  Memory draft; two-person review remains required before freezing Gold.

### Intentionally deferred

- Verifier-feedback content retry;
- multiple Researcher execution;
- memory persistence and semantic matching;
- semantic Writer synthesis, semantic Verifier classification, and UI;
- generic model-provider and MCP abstractions.
- quantitative Planner Gold, broader Researcher datasets, calibrated semantic
  models, and end-to-end Eval aggregation.

### Verification

- Python compilation passes for `src` and `tests`;
- all 117 formal offline tests pass;
- the actual deterministic Writer passes all six Writer Gold cases with perfect
  structure, Claim, provenance, and evidence-state metrics;
- the real deterministic Verifier runs all six combined cases, exactly matches
  structural Gold types, and safely maps semantic-only cases to `unsupported`;
- nested Writer/Verifier dataclasses and Enums round-trip through the configured
  Temporal converter;
- a real MCP stdio handshake discovers the formal `search_arxiv` Tool;
- real concurrent arXiv retrieval passed on the prior synthesis contract; the
  new Claim/MEG smoke reached successful live retrieval on 2026-08-27 but was
  terminated after the later structured model stage remained unresponsive;
- earlier no-memory Planner contracts passed live with
  `deepseek/deepseek-v4-flash-0731`; the current strengthened contract has 25
  passing Planner tests but still needs one complete live result;
- the Activity's variable MEG-call sequence and capability gates are covered by
  offline orchestration tests.
- Workflow tests cover supported, source-free, rejected, multi-plan failure,
  Activity failure, converter round-trip, and complete Worker registration;
- local Temporal executions on 2026-08-28 validated approved and rejected
  results, each with 29 history events, four completed Activities, and one
  completed Workflow;
- a local retry smoke failed Researcher attempt one, succeeded on attempt two,
  and still completed with an approved result.

## 5. Next development slice

Implement Planner memory reuse and session note persistence over the now-working
minimum Workflow. Researcher dataset review continues in parallel and does not
block this slice.

The Eval document is an accepted design input, not a requirement to build the
full evaluation platform before this slice. Small gold fixtures should accompany
the implemented Writer/Verifier rules; broad datasets and end-to-end aggregation
remain later work.

## 6. Ordered roadmap

1. Minimal Planner vertical slice without memory — implemented and
   offline-tested; the current strengthened policy needs live revalidation.
2. Formal single-Researcher vertical slice using arXiv MCP — implemented,
   offline-tested, and live-boundary validated.
3. Writer/Verifier boundary with claim provenance — implemented and
   offline-tested.
4. Minimal Writer and deterministic Verifier behavior — implemented.
5. End-to-end Temporal Workflow with exactly one Researcher — implemented and
   locally Temporal-validated.
6. Planner memory reuse and session note persistence.
7. Dynamic `Researcher × N` fan-out with a concurrency cap.
8. Targeted content retry using failed subquestion IDs.
9. FastAPI progress API and SSE stream.
10. React demo and the two independent failure-injection paths.

Every step must leave an executable end-to-end or module-level capability before the next layer is added.

Module-level gold fixtures and metrics are added alongside the module whose
semantic behavior they evaluate. The exactly-one-Researcher Workflow now makes
incremental end-to-end aggregation possible, but semantic aggregation still
requires a stable external live corpus and reviewed labels.

## 7. Historical records

The original Chinese spike documents were removed after their active conclusions were transferred to the module documents. Their complete content remains available in Git history. [archive/README.md](archive/README.md) describes the remaining experiment scripts and removal condition.

## 8. Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Implemented and locally Temporal-validated the exactly-one-Researcher Workflow, production Worker/client, and distinct approval, content-rejection, and infrastructure-retry paths. |
| 2026-08-28 | Implemented deterministic Verifier gates and Activity with exact provenance/state checks, safe generic semantic rejection, and targeted failure scope. |
| 2026-08-28 | Implemented deterministic Writer assembly and Activity, passed all six Writer Gold cases, and corrected Claim identity to be subquestion-scoped. |
| 2026-08-28 | Added an independent six-case Writer Gold, deterministic structure/provenance metrics, complete v0 partition checks, and mutations for every Writer hard-failure type. |
| 2026-08-27 | Added a six-case synthetic Writer/Verifier draft fixture with fixed Claim coverage, Gold decisions, and exact failure localization. |
| 2026-08-27 | Froze the Writer/Verifier boundary with attributable report statements, typed issues, exact retry scope, and Temporal round-trip coverage. |
| 2026-08-27 | Recorded that the fresh Researcher smoke completed live arXiv retrieval but did not return from the later structured model stage within the bounded wait. |
| 2026-08-27 | Closed the MEG provenance boundary by rejecting Claim support sources outside each Claim's frozen candidate set. |
| 2026-08-26 | Corrected Planner validation status: earlier contracts passed live, but the current sufficiency/ownership policy has 25 passing tests and no complete live result yet. |
| 2026-08-26 | Raised the Planner completion ceiling to 4,000 after repeated live JSON truncation and exposed provider finish reasons in malformed-output errors. |
| 2026-08-26 | Required Planner requirements to be sufficient for target strength and uniquely owned across subquestions; documented prevalence and evidence-overlap diagnostics. |
| 2026-08-26 | Aligned Planner output with the arXiv-only Researcher boundary, rejected procedural answer requirements, and raised the passing suite to 72 tests. |
| 2026-08-26 | Marked the Agent Memory draft as mechanism-only, added unresolved-label adjudication gates, restored its 2023-2026 constraint scope, and retained 70 passing offline tests. |
| 2026-08-26 | Added fixed Planner answer requirements, structured Researcher Claims, required source abstracts, bottom-up MEG selection, and Agent Memory paper/group/MEG evaluation with 70 passing offline tests. |
| 2026-08-26 | Synchronized current status with the implemented 12-item Assessment Eval, its draft-label boundary, and the passing 64-test suite. |
| 2026-08-25 | Added a one-primary-answer-target Planner rule and regression test; semantic duplicate and Broadness checks remain planned Eval rather than runtime embedding gates. |
| 2026-08-25 | Replaced one manually authored compound Researcher Eval subquestion with three atomic subquestions, re-annotated four candidates for each question, and bumped the draft dataset to `0.4.0-draft`. |
| 2026-08-25 | Extended line-length enforcement to Eval JSON data and raised the passing offline suite to 62 tests. |
| 2026-08-25 | Added original-question and manual-subquestion provenance to the draft Researcher data, enforced an 80-character Python line limit, and raised the passing offline suite to 61 tests. |
| 2026-08-25 | Implemented an Assessment-only Researcher Eval runner plus a four-item draft annotation set; 60 offline tests pass, and human review is required before freezing Gold. |
| 2026-08-25 | Added a narrow `unknown` abstention for title/abstract insufficiency without adding runtime scoring; unknown candidates cannot be used as evidence. |
| 2026-08-25 | Replaced model-selected paper relevance with factorized semantic judgments and deterministic four-class derivation; 55 offline tests pass, while Gold semantic evaluation remains unimplemented. |
| 2026-08-24 | Reorganized the architecture guide around an Eval-first hierarchy; nested module content under Planner/Researcher and expanded each module Eval with primary references, formulas, rationale, and CiteGuard adaptation. No Eval runtime was implemented. |
| 2026-08-24 | Documented the planned Eval architecture: equal-weight Planner coverage plus hard constraints, calibrated redundancy, fragmentation/broadness diagnostics, staged Researcher metrics, and provenance-bound Claim verification; implementation remains deferred. |
| 2026-08-24 | Implemented the formal single Researcher with two structured LLM calls, formal arXiv MCP integration, six-criterion relevance assessment, and explicit evidence states; 43 offline tests and live retrieval/synthesis boundaries pass. |
| 2026-08-23 | Applied structured code-documentation conventions to Planner and the retained MCP/Temporal spikes; added a Planner prompt-structure regression test. |
| 2026-08-23 | Established a repository-wide structured documentation standard in `docs/ENGINEERING.md` and added it to the system router and architecture guide. |
| 2026-08-23 | Configured editable installation for the `src/` layout so Planner tests and scripts can import `citeguard` without manually setting `PYTHONPATH`. |
| 2026-08-23 | Standardized Planner runtime prompts, schema descriptions, comments and errors in English; added regression tests and an ignored living architecture PDF. |
| 2026-08-23 | Live-validated the no-memory Planner through OpenRouter with DeepSeek V4 Flash; three structured subquestions passed contract validation and deterministic assembly. |
| 2026-08-23 | Switched the Planner default to DeepSeek V4 Flash and limited configured models to DeepSeek, Qwen or Z.ai GLM families. |
| 2026-08-23 | Implemented and offline-tested the first no-memory Planner slice; recorded the pending fixed-model OpenRouter smoke test. |
| 2026-08-23 | Reconciled the product design, completed spike and partial formal source tree; selected the minimal Planner path as the next development slice. |
