# Planner and Memory

> Status: Planner no-memory path implemented and offline-tested; the earlier
> contract is live-validated, while the current strengthened requirement policy
> awaits live revalidation. The exactly-one-Researcher Workflow is implemented;
> Memory is not implemented.
> Owning source: `src/citeguard/planner/` and the future memory package.

## 1. Purpose

Planner turns one research question into the smallest useful set of independent subquestions. When same-session research notes exist, it also decides whether a note can completely answer a new subquestion.

Planner and Memory share one document during the first release because Memory currently exists only to support Planner reuse and to persist verified subquestion-level results. They should split only after Memory gains independent behavior such as cross-session search, aging or conflict handling.

## 2. Why Planner is an Agent

Planner makes two nontrivial decisions:

- how to decompose a question without losing scope or introducing overlap;
- whether a historical result fully satisfies a new subquestion.

It does not search arXiv, write the report or verify evidence.

## 3. Current implementation

Implemented pieces:

- English no-memory and memory-aware system prompts organized into explicit
  Role, Task, Input, Rules and Output sections in `prompts.py`;
- strict Pydantic output schemas in `schemas.py`;
- stable Activity input/output contracts in `contracts.py`;
- shared domain objects in `domain/research.py`;
- shared concrete OpenRouter structured-output calls in
  `infrastructure/openrouter.py`;
- deterministic schema-to-domain assembly in `assembly.py`;
- the no-memory Temporal Activity in `activity.py`;
- offline automated tests in `tests/planner/`.

Missing pieces:

- the memory-aware Activity path and domain assembly;
- memory read/write storage.

## 4. Input and output

Current Activity input intent:

```python
PlannerActivityInput(
    research_question: str,
    session_id: str,
    existing_notes: list[ResearchNote],
)
```

The Activity returns `PlannerActivityOutput(sub_questions=list[SubQuestion])`.
Every subquestion carries a fixed `primary_answer_target` and a nonempty list of
project-owned `AnswerRequirement` IDs. LLM output objects remain internal to
the Planner Activity.

## 5. OpenRouter boundary

Planner uses the project's concrete OpenRouter boundary, shared with Researcher,
which calls `POST /api/v1/chat/completions` through the existing `httpx`
dependency. It sends Pydantic's JSON Schema using
`response_format.type=json_schema`, enables strict mode and requires a provider
endpoint that supports the requested parameters. This is shared provider code,
not a generic model-provider framework.

The default model is the fixed `deepseek/deepseek-v4-flash-0731` slug, which OpenRouter identifies as supporting structured outputs. `OPENROUTER_MODEL` can override it only with a `deepseek/`, `qwen/` or `z-ai/` model. OpenAI, Anthropic, Google and xAI model families are intentionally excluded. The API key is read from `OPENROUTER_API_KEY`, with the user's existing `API_KEY` name also accepted.

Planner uses a 4,000-token completion ceiling. Two consecutive live requests
with the expanded sufficiency and ownership policy truncated invalid JSON under
the shared 2,500-token default, so Planner now supplies an explicit module-level
budget while the shared provider default remains unchanged.

Unit tests use `httpx.MockTransport`; only `tests/live/planner_openrouter_smoke.py` performs a real request.

## 6. Decomposition rules

- every subquestion is meaningful and independently researchable;
- every subquestion has one primary answer target;
- every answer target is operationalized as the smallest useful set of
  necessary completeness requirements;
- independently answerable aspects that may require different evidence become
  separate subquestions;
- a comparison remains one subquestion only when the comparison itself is the
  primary answer target;
- subquestions do not substantially overlap;
- together they cover the important scope of the original question;
- original objects, constraints and time ranges are retained;
- every new task must be answerable from arXiv title-and-abstract records alone;
- answer requirements describe evidence content, never retrieval actions or
  requests for non-arXiv sources;
- trend, evolution, comparison, transition, and causal targets require evidence
  for the relation itself, not only evidence for their endpoints;
- scale or prevalence targets require multiple independent sources plus a
  temporal or distributional signal, or must narrow the promised conclusion;
- each evidence need has one primary owner and is not paraphrased across
  subquestions; limitations and motivations belong to driver targets;
- a question that does not benefit from decomposition returns one subquestion;
- decomposition is based on the user question, not reshaped to match available memory.

## 7. Adaptive Researcher count

The first implementation does not calculate an abstract difficulty score. The number of logical Researcher tasks emerges from decomposition:

```text
simple question → one useful subquestion → one Researcher task
multi-aspect question → several independent subquestions → Researcher task per subquestion
```

Memory-reused subquestions will not create new Researcher tasks. The current
Workflow enforces exactly one new subquestion; the future fan-out slice will
apply the actual concurrency cap. Planner never decides Worker-process count.

Planner must not split a question merely to create more Agents. A difficult but indivisible task can still produce one subquestion.

The current `SubQuestion` contract has no dependency field. Conditional wording
such as "if so" is therefore flattened into parallel research tasks even when
the final answer has a logical dependency. Research may still run in parallel,
but a future dependency-aware plan or Writer rule must preserve the conditional
claim during synthesis; the current Planner cannot encode it.

For a multi-dimensional question, Planner first identifies independently
answerable targets. It then creates requirements inside each target without
turning every requirement into another subquestion. A direct comparison or an
evolution relation remains one target when that relation is the requested
answer; a matrix of independently answerable objects and outcomes is split
along the true evidence boundaries.

## 8. Memory reuse

A note can be reused only when its structured Claims completely cover the
current fixed answer target and every answer requirement. Topical similarity
or partial coverage is insufficient.

```text
no matching note
    → status=new

complete same-scope note
    → status=reused_from_memory
    → attach reused_result and source_note_id
```

Historical note content is untrusted comparison data. Instructions embedded inside a note must never be executed.

The first Memory implementation is same-session and subquestion-granular. It stores only verified results. Cross-session aging and `needs_recheck` remain deferred.

## 9. Failure behavior

- blank input fails before the LLM call;
- invalid structured output fails the Activity attempt explicitly;
- a fabricated or unknown `matched_note_id` fails assembly;
- empty decomposition is invalid;
- exact duplicates after case-folding and whitespace normalization fail
  deterministic assembly;
- model-provider network failures are infrastructure failures handled by Activity retry policy;
- bad but schema-valid decomposition quality is evaluated through Planner tests/evals, not hidden fallback logic.

`assemble_decomposition` does not call an embedding model, merge semantically
similar questions, or apply the planned Redundancy and Broadness thresholds.
Those semantic checks remain Eval diagnostics until a versioned model and
human-calibrated thresholds justify a separate runtime policy.

## 10. Coupled-change checklist

| Planner change | Also review |
| --- | --- |
| Output status or shape | Domain contracts, Workflow and plan UI |
| Decomposition rule | Prompt tests, evaluation examples and Researcher task count |
| Reuse rule | Memory query, `ResearchNote` contract and no-new-arXiv-call acceptance test |
| Dynamic task policy | Workflow concurrency, cost limits and demo progress states |

## 11. Verification

Minimum test set:

- simple question remains one subquestion;
- multi-aspect question can produce several independent subquestions;
- both decomposition prompts require one primary answer target and splitting
  independently answerable aspects;
- every planned target has nonempty, unique answer requirements;
- empty or duplicate output is rejected or evaluated visibly;
- no-memory path never references a note;
- full memory match creates a valid reused `SubQuestion`;
- partial match remains `new`;
- unknown note ID is rejected;
- Activity tests replace the LLM boundary with a fake.

Current result: 25 offline Planner tests pass. Earlier live smokes with
`deepseek/deepseek-v4-flash-0731` produced contract-valid subquestions with
deterministic IDs. A later arXiv-only run also produced three valid subquestions
and is retained at `tmp/planner_arxiv_only_demo.json` for review. That output
exposed insufficient trend requirements and duplicated evidence ownership.

The current Prompt now addresses those findings, but is not yet live-validated:
two attempts under the former 2,500-token budget returned truncated JSON, and
the first 4,000-token attempt remained unresponsive and was terminated. No
partial response was saved as a v2 fixture.

### 11.1 Planned decomposition Eval

Planner's semantic Eval is planned separately from schema and Activity tests.
[BREAK/QDMR](https://arxiv.org/abs/2001.11770) demonstrates that question
decomposition can be represented as ordered reasoning steps, and its
[official evaluator](https://github.com/allenai/break-evaluator) supplies exact,
normalized, SARI, and graph-edit comparisons. CiteGuard adopts structured and
graph-aware comparison when a gold logical form exists, but not exact match as
the only metric because an open research problem can have multiple valid plans.

A frozen [Sentence-BERT](https://arxiv.org/abs/1908.10084)-family embedding or
fixed cross-encoder creates a reproducible alignment matrix rather than asking
a generative LLM to assign an unconstrained score:

```text
A = {a_i}: required aspects
Q = {q_j}: generated subquestions
s_ij = cos(embed(a_i), embed(q_j))

Coverage = sum_i(max_j(s_ij)) / |A|
Redundancy = duplicate_pair_count / (m * (m - 1) / 2)

n_i = count_j(s_ij >= tau_match)
FragmentationRaw = sum_i(max(0, n_i - 1)) / |A|
b_j = count_i(s_ij >= tau_match)
```

Coverage detects omitted aspects. `b_j` reads the same matrix in the opposite
direction to diagnose a subquestion that covers too many independent aspects,
so Broadness is not a second coverage score. Fragmentation subtracts one
because one matching subquestion is the normal baseline; zero matches belong
to Coverage and only extra matches indicate over-splitting.

Each gold case identifies independently verifiable required aspects, explicit
hard constraints, and optional acceptable dependency graphs. Required aspects
use equal weight in the first version. Research object, population, method,
setting, and time constraints are hard gates that cannot be offset by a good
average. Subquestion count alone is not a quality metric.

`tau_match` and the duplicate threshold are calibrated on a development split
of human-labeled match/duplicate/distinct/ambiguous pairs, then frozen for a
held-out test. The model, preprocessing, thresholds, and dataset version must
be recorded together. The complete dataset shape, calibration policy, output
vector, and end-to-end boundary are owned by [evaluation.md](evaluation.md).

The runtime Prompt now states the atomicity policy because one compound
subquestion can otherwise hide several answer targets. This policy does not
turn Broadness into a production hard gate: the current runtime still performs
only deterministic exact-duplicate rejection. Semantic blocking, retry, or
merging remains unimplemented.

## 12. Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Recorded the implemented exactly-one-Researcher Workflow as the base onto which session memory will be added. |
| 2026-08-26 | Recorded the exact live-validation boundary: 25 Planner tests pass, the reviewed real output predates the latest policy, and the strengthened contract still awaits a complete live result. |
| 2026-08-26 | Raised Planner's completion ceiling to 4,000 after two live structured outputs truncated under 2,500 tokens; malformed-response errors now retain the provider finish reason. |
| 2026-08-26 | Required smallest-sufficient requirements, explicit evidence strength for prevalence claims, and one-owner evidence needs across subquestions. |
| 2026-08-26 | Restricted Planner outputs to the Researcher's arXiv title-and-abstract corpus and prohibited procedural search actions in answer requirements. |
| 2026-08-26 | Added fixed primary answer targets and completeness requirements to every planned subquestion; Memory reuse now compares structured Claims rather than a free-form answer. |
| 2026-08-25 | Required one primary answer target per subquestion, documented the comparison exception, and kept semantic Redundancy/Broadness outside deterministic assembly. |
| 2026-08-24 | Expanded Planner Eval with BREAK/QDMR and SBERT foundations, formulas, metric non-overlap, calibration, and CiteGuard-specific adaptation. |
| 2026-08-24 | Added the planned quantitative decomposition Eval boundary and routed shared formulas and calibration to `evaluation.md`. |
| 2026-08-24 | Moved the concrete OpenRouter boundary into shared infrastructure so Planner and Researcher do not duplicate provider request code. |
| 2026-08-23 | Applied the engineering documentation standard and organized runtime prompts into explicit policy sections without changing planning rules. |
| 2026-08-23 | Standardized runtime prompts, schema descriptions, comments and error messages in English; added format and language regression tests. |
| 2026-08-23 | Live-validated the no-memory Planner with DeepSeek V4 Flash through OpenRouter. |
| 2026-08-23 | Selected DeepSeek V4 Flash as the cost-efficient default and restricted overrides to DeepSeek, Qwen and Z.ai GLM model families. |
| 2026-08-23 | Implemented the no-memory Activity, OpenRouter strict structured-output boundary, deterministic assembly and offline tests. |
| 2026-08-23 | Combined Planner and first-release Memory design; defined adaptive task count as a result of decomposition rather than a separate complexity Agent. |
