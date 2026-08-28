# Researcher and arXiv MCP

> Status: formal single Researcher implemented, offline-tested, and
> live-validated at its provider/MCP boundaries.
> Owning source: `src/citeguard/researcher/`.

## 1. Purpose

One Researcher owns one subquestion. It searches arXiv through MCP, evaluates the returned papers and produces one source-backed `ResearchResult`.

The Researcher and arXiv MCP integration share one document during the first release because Researcher is the only planned tool consumer and arXiv is the only tool. A general MCP abstraction is not introduced until another real consumer or tool requires it.

## 2. Why Researcher is an Agent

Each Researcher has:

- an independent subquestion and context;
- independent arXiv tool access;
- responsibility for choosing queries and evaluating results;
- an independent result and retry scope.

Researchers do not modify the plan, write the final report or approve their own evidence.

## 3. Input and output

Implemented input:

```python
ResearchTaskInput(
    sub_question=...,
    verifier_feedback=None,
)
```

The current Activity accepts only `status=new` and no Verifier feedback. A
nonempty `verifier_feedback` is an explicit nonretryable capability gate until
the Verifier content-retry slice is implemented. On an infrastructure retry,
the input remains unchanged.

Output is a domain `ResearchResult` containing structured, provenance-bound
Claims. A supported result also contains the minimum-cardinality evidence group
selected from the assessed papers. It does not contain a free-form factual
answer paragraph.

## 4. Implemented research behavior

One Activity executes this fixed sequence:

```text
ResearchTaskInput
    -> structured LLM call: choose 1-5 search queries
    -> one MCP session: execute queries concurrently
    -> deduplicate and cap candidate papers
    -> structured LLM call: assess every paper and freeze atomic Claims
    -> bottom-up MEG search: judge candidate groups by cardinality
    -> deterministic ResearchResult assembly
```

The query count is adaptive within a hard ceiling of five. The Prompt asks for
the smallest useful set and permits additional queries only for materially
different terminology, methods, or aspects. Five superficial paraphrases are
invalid. Each Tool call returns at most five papers and deterministic assembly
retains at most twelve unique candidates.

The evidence-analysis call evaluates every candidate using six required
criteria:

1. research-object match;
2. problem match;
3. method, setting, time, population, and other constraint match;
4. actual abstract method or finding rather than keyword overlap;
5. exact supported aspects;
6. unsupported aspects and limitations.

The model no longer chooses a final relevance label directly. It reports
factorized `object_match`, `problem_match`, `constraint_match`, `evidence_kind`,
and `answer_coverage` judgments. `relevance.py` applies one deterministic policy
to derive `direct`, `partial`, `background`, or `irrelevant` and rejects mutually
inconsistent factors. A minimal `unknown` abstention is reserved for candidates
whose title and abstract omit information needed to classify them; it is not a
fallback for difficult judgments. This keeps semantic judgment with the model
while making the classification rule explicit and testable.

Only direct and partial papers may be Claim candidates. Unknown candidates
cannot support a Claim; when no other usable source exists they produce
`insufficient_evidence`, not `no_relevant_sources`. Direct and partial papers'
`supported_aspects` must be a real explanation; background, irrelevant, and
unknown assessments require it to be null.

The same call freezes a structured Claim set. Every Claim has one atomic
statement, the answer-requirement IDs it addresses, and the candidate source
IDs that may support it. Project code assigns stable Claim IDs and verifies that
Claim requirements plus explicitly unmet requirements form an exact partition
of the Planner contract. The model cannot replace the fixed answer target or
add a free factual conclusion. Group support may cite only the candidate source
IDs frozen for that exact Claim; membership in the broader group is not enough.

Minimum Evidence Group (MEG) selection runs after per-paper assessment and
before `ResearchResult` assembly. Project code enumerates source combinations
by increasing cardinality, safely prunes combinations that cannot cover every
Claim, and asks the model to label bounded batches of exact remaining groups as
`FULL`, `PARTIAL`, or `NONE`. Search stops at the first `FULL` group after all
smaller cardinalities have failed, so the returned group is minimum-cardinality
under those judgments. A `FULL` group must support every frozen Claim, satisfy
every fixed requirement, and use every member source for at least one Claim.

For every retained paper, its arXiv abstract, supported aspects, and limitations
are preserved on `ResearchSource`. The provider adapter may still call the raw
arXiv field `summary`, but the domain contract deliberately names it required
`abstract`. No-evidence and insufficient-evidence results require an
`evidence_reason`; only a fully supporting MEG produces `supported`.

## 5. MCP boundary

- MCP, subprocess and HTTP calls run inside an Activity or adapter called by an Activity;
- MCP return objects are converted immediately into project-owned domain/transport objects;
- Workflow code never imports MCP client types;
- malformed tool output is a permanent protocol error unless evidence shows it is transient;
- tool-returned text is untrusted data and cannot override Researcher instructions.

The formal MCP server returns full normalized abstracts rather than the spike's
300-character truncation. The adapter starts that server as a module using the
current Python executable, initializes one stdio session, and multiplexes all
queries through that session.

## 6. Implemented boundaries and retained spike findings

The existing experiment validated:

- a stdio MCP Server exposing `search_arxiv`;
- concurrent calls within one MCP session;
- conversion from structured or text JSON MCP results;
- a Temporal Activity wrapping MCP execution;
- Worker interruption recovery.

The formal Activity owns one subquestion. Multiple search queries remain an
internal retrieval detail and do not reduce per-subquestion failure isolation.

## 7. Failure behavior

Infrastructure failures such as HTTP timeout, rate limiting or subprocess termination are eligible for bounded Temporal retry. Invalid input and structurally invalid MCP output are nonretryable.

A content retry remains planned. The current Activity rejects Verifier feedback
instead of silently ignoring it.

## 8. Coupled-change checklist

| Change | Also review |
| --- | --- |
| Research output/source fields | Domain contracts, Writer, Verifier, Memory and UI |
| Tool input/output | MCP server, adapter parser, Activity tests and retry classification |
| Activity granularity | Orchestration failure isolation, progress state and concurrency |
| Feedback behavior | Verifier reason contract and targeted retry tests |

## 9. Verification

Implemented offline tests verify:

- the bounded query, evidence-analysis, and cardinality-batched MEG sequence;
- one-to-five distinct query bounds;
- required assessment of every candidate and exact source-ID provenance;
- factorized assessment, deterministic four-class relevance derivation, and a
  narrow unknown abstention for insufficient abstract information;
- rejection of contradictory factors and unsupported-aspect claims from
  background or irrelevant candidates;
- atomic Claim validation, answer-requirement coverage, and deterministic IDs;
- bottom-up MEG minimality, safe pruning, exact batch provenance, and rejection
  of fabricated group output or Claim-to-source reassignment;
- all three evidence statuses and their explanatory-field invariants;
- structured or JSON-text MCP result parsing;
- permanent malformed-result handling and explicit capability gates;
- the six relevance criteria in the trusted English system Prompt;
- no evidence-analysis or MEG call when retrieval returns no candidates.

Python compilation and all 73 formal offline tests pass. A real MCP stdio
handshake discovers `search_arxiv`, and real concurrent Tool calls return arXiv
papers. The earlier assessment-and-assembly path passed live; the newly added
Claim and MEG stages are covered offline and require a fresh explicit live smoke
before being described as live-validated end to end. A 2026-08-27 smoke reached
and completed real arXiv retrieval, then remained in the structured analysis or
MEG model stage without producing a result and was terminated after a bounded
wait. It does not count as a completed live validation.

### 9.1 Paper relevance and MEG Eval

Researcher semantic quality is evaluated in stages so retrieval failure is not
misreported as synthesis failure. [BEIR](https://arxiv.org/abs/2104.08663)
provides the retrieval precedent and a robust BM25 baseline;
[SciFact](https://arxiv.org/abs/2004.14974) motivates separate scientific
document retrieval, evidence selection, support labels, and rationales.
CiteGuard adapts both at title-and-abstract level:

- query uniqueness, constraint retention, and diversity;
- Recall@K, Precision@K, MRR, or nDCG against graded paper-relevance labels;
- macro F1 for direct, partial, background, and irrelevant assessments;
- FULL/PARTIAL/NONE support for exact source groups and fabricated-ID rejection;
- macro F1 for the three `EvidenceStatus` values;
- report-level Claim support against the selected abstract evidence.

The executable dataset now covers both paper assessment and MEG selection. Its
12 paper annotations form three manually authored Agent Memory cases with four
candidates each. The cases deliberately require minimum evidence groups of
size one, two, and three. They remain `draft` until the planned two-person human
review is complete.

The offline runner reports factor accuracy, four-class relevance macro F1,
direct precision, unknown-abstention rate, group-support macro F1, complete-case
MEG rate, mean cardinality error, and redundant-source rate. Exact candidate,
case, group, and source identities are validated before scoring. Unknown remains
a prediction abstention rather than a fifth Gold relevance class.

The draft subquestions are manually authored rather than produced by a Planner
run. Every case retains the original question, fixed primary answer target, and
answer requirements. Whether those subquestions faithfully cover the original
question belongs to Planner Eval and is not inferred from a high Researcher or
MEG score.

The planned ranking formulas are:

```text
Recall@K = relevant items retrieved in top K / all gold relevant items
Precision@K = relevant items retrieved in top K / K
MRR = (1 / N) * sum_t(1 / rank_t(first relevant item))

DCG@K = sum_r((2^rel_r - 1) / log2(r + 1))
nDCG@K = DCG@K / IDCG@K
```

An initial reviewable nDCG relevance mapping is `direct=3`, `partial=2`,
`background=1`, and `irrelevant=0`. It belongs to the versioned dataset and is
never selected by the runtime LLM. Evaluation also freezes an arXiv snapshot or
candidate pool so changing online search results do not change the denominator.

One, three, or five queries are all valid outcomes; the goal is relevant-paper
coverage without redundant paraphrases. The existing six Prompt criteria become
the annotation rubric, while Prompt-content assertions remain ordinary unit
tests. Each stage reports its own score and confusion matrix so query-planning,
retrieval, assessment, source-selection, evidence-state, and answer-support
failures remain attributable. Dataset structure, lexical and LLM baselines,
fixed-model use, ablations, and threshold calibration are owned by
[evaluation.md](evaluation.md).

## 10. Split condition

Create a separate `mcp-tools.md` only when at least one of these becomes true:

- a second runtime module uses MCP;
- Researcher can choose between multiple research tools;
- transport/authentication lifecycle becomes shared infrastructure;
- the adapter has independent contracts and tests beyond arXiv.

## 11. Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Connected the formal single Researcher Activity to the exactly-one-Researcher Workflow with bounded Temporal infrastructure retries. |
| 2026-08-27 | Bound every MEG Claim support reference to that Claim's frozen candidate sources and added swapped-provenance regression coverage. |
| 2026-08-26 | Replaced free-form synthesis with frozen structured Claims and bottom-up minimum evidence-group selection inside Researcher; added Agent Memory cases and group/MEG metrics. |
| 2026-08-26 | Synchronized verification with the passing 64-test suite and retained the Assessment dataset's draft-only quality boundary. |
| 2026-08-25 | Split the compound SciFact Eval question into three atomic subquestions and re-annotated four candidates per question in draft version `0.4.0-draft`. |
| 2026-08-25 | Added original-question and manual/Planner provenance to Researcher Eval records so local relevance cannot be mistaken for valid Planner decomposition. |
| 2026-08-25 | Added the first executable Assessment-only Eval runner and four-item draft candidate set; annotations remain pending human review. |
| 2026-08-25 | Added a narrow `unknown` abstention for insufficient title/abstract information; unknown candidates cannot be used as evidence and lead to `insufficient_evidence` when no usable source exists. |
| 2026-08-25 | Replaced model-selected relevance labels with factorized judgments and deterministic four-class derivation; semantic Gold evaluation remains the next slice. |
| 2026-08-24 | Expanded Researcher Eval with BEIR/SciFact foundations, ranking formulas, graded relevance, a frozen candidate pool, and staged attribution. |
| 2026-08-24 | Added the planned staged Researcher Eval from query quality through abstract-level answer support. |
| 2026-08-24 | Implemented the two-call single Researcher, formal arXiv MCP server/adapter, six-criterion relevance assessment, and explicit evidence-state behavior. |
| 2026-08-23 | Defined the formal Researcher boundary, preserved validated spike findings and deferred a generic MCP abstraction. |
