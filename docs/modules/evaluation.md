# Evaluation Design

> Status: Researcher paper-relevance and MEG Eval implemented with draft labels;
> synthetic Writer-only and combined Writer/Verifier fixed-contract fixtures
> are implemented; remaining semantic metrics, calibrated thresholds, and
> production quality gates are planned.
> Owning source: `src/citeguard/evaluation/`, `eval/`, and versioned evaluation
> datasets.

## 1. Purpose

Evaluation measures whether each CiteGuard module performs its own business
decision correctly and whether the complete system produces a useful,
source-bounded report. It must make failures attributable to Planner,
Researcher, Writer, Verifier, or orchestration instead of reducing the entire
run to one opaque score.

The primary evaluation path is:

```text
human-annotated structure or gold labels
    -> deterministic metrics and rules
    -> fixed semantic similarity or NLI model where language matching is needed
    -> optional human review for a calibrated gray band
```

A generative LLM judge is not the primary regression oracle. It may later help
inspect ambiguous cases, but its result must remain separate from deterministic
and fixed-model metrics.

## 2. Evaluation layers and ownership

| Layer | Owns | Does not duplicate |
| --- | --- | --- |
| Planner Eval | decomposition coverage, retained constraints, overlap, fragmentation and dependency structure | Research evidence quality or final prose |
| Researcher Eval | retrieval quality, paper relevance, source selection, evidence status and answer support | Writer omissions or claim expansion |
| Writer/Verifier Eval | claim provenance, citation support, evidence-boundary violations and issue localization | Planner decomposition quality |
| End-to-end Eval | final task completion, report coverage, citation correctness, overclaim rate, cost and latency | internal diagnosis already reported by module Evals |

Module Eval explains where a failure was introduced. End-to-end Eval measures
the user-visible outcome and correlates it with those module failures. Rechecking
the same property at both levels is avoided unless the final layer measures the
effect of an earlier error on the delivered report.

## 3. Shared evaluation principles

1. Keep evaluation data outside runtime prompts and production domain objects
   unless the business workflow also needs the same field.
2. Separate hard constraints from continuous quality scores. A missing explicit
   time range, fabricated source ID, causal upgrade, or unsupported number must
   not be hidden by a good average.
3. Report a metric vector and typed failures instead of one weighted total.
4. Calibrate every learned-model threshold on a development split and freeze
   the model name, version, preprocessing, threshold, and dataset version.
5. Reserve a held-out test split for final comparison. Do not tune thresholds
   on the same cases used to report results.
6. Use at least two independent human annotators for subjective gold labels and
   record disagreement rather than forcing silent consensus.
7. Treat arXiv title and abstract as abstract-level evidence only. Current
   Researcher evaluation cannot claim full-paper support.

## 4. Planner evaluation

### 4.0 Method basis and adaptation

[BREAK/QDMR](https://arxiv.org/abs/2001.11770) represents a question as the
ordered natural-language steps required to answer it. Its
[official evaluator](https://github.com/allenai/break-evaluator) includes exact
and normalized match, SARI, and graph edit distance. CiteGuard adopts the idea
that decomposition has an evaluable structure, but does not use one exact
reference as the primary oracle: open research questions can have several
valid decompositions.

[Sentence-BERT](https://arxiv.org/abs/1908.10084) provides efficient sentence
embeddings that can be compared with cosine similarity. A frozen SBERT-family
model or fixed cross-encoder is therefore a candidate for the reproducible
aspect-to-subquestion matrix. This is a semantic matcher, not a generative LLM
judge. Exact model selection remains an implementation spike and must be
calibrated before acceptance.

### 4.1 Gold case structure

Each Planner case records the original question, independently verifiable
required aspects, explicit hard constraints, and optional acceptable dependency
graphs. Multiple reference decompositions are allowed when more than one plan is
valid.

```json
{
  "question": "...",
  "required_aspects": [
    {"id": "A1", "description": "..."},
    {"id": "A2", "description": "..."}
  ],
  "hard_constraints": {
    "population": "...",
    "time_range": "..."
  },
  "acceptable_dependency_graphs": []
}
```

Required aspects are research units, not every noun in the question. This
prevents a legitimate comparison question from being penalized merely because
it mentions two methods.

### 4.2 Aspect-to-subquestion similarity

Let `A = {a_i}` be the required aspects and `Q = {q_j}` the generated
subquestions. A frozen sentence-embedding or cross-encoder model supplies:

```text
s_ij = semantic_similarity(a_i, q_j), where 0 <= s_ij <= 1
```

The model supplies a reproducible representation; it does not freely apply a
rubric or produce a quality score in natural language.

### 4.3 Coverage

The first version uses equal aspect weights:

```text
Coverage = sum_i(max_j(s_ij)) / |A|
```

This asks whether every required aspect has at least one good matching
subquestion. Per-case LLM-selected weights are forbidden. Explicitly required
objects, populations, methods, settings, and time ranges are checked separately
as hard constraints rather than given a larger weight that other scores could
offset.

### 4.4 Redundancy

For `m` generated subquestions:

```text
Redundancy = duplicate_pair_count / (m * (m - 1) / 2)
duplicate(q_j, q_k) when similarity(q_j, q_k) >= tau_dup
```

`tau_dup` is not a universal constant. Human annotators label duplicate,
distinct, and ambiguous subquestion pairs. Candidate thresholds are swept on
the development split, and CiteGuard selects the highest-recall threshold that
still meets the chosen duplicate-precision target. A low and high threshold may
define a gray band instead of forcing every pair into a binary decision.

This is currently an Eval-only design. Runtime assembly retains its normalized
exact-duplicate hard gate but does not call an embedding model, merge questions,
or reject paraphrased duplicates using `tau_dup`.

### 4.5 Fragmentation

For each required aspect:

```text
n_i = count_j(s_ij >= tau_match)
extra_fragments_i = max(0, n_i - 1)
FragmentationRaw = sum_i(extra_fragments_i) / |A|
```

One matching subquestion is the expected coverage, so only matches beyond the
first are counted as extra fragments. `n_i = 0` is an omission detected by
Coverage, `n_i = 1` is normal, and `n_i > 1` contributes fragmentation. This is
a diagnostic average and is not necessarily bounded by one.

### 4.6 Broadness and structure

For each generated subquestion:

```text
b_j = count_i(s_ij >= tau_match)
```

A high `b_j` flags a subquestion that may combine several independent research
units. Broadness and Coverage use the same alignment matrix in opposite
directions: Coverage asks whether every aspect has a subquestion; Broadness asks
whether one subquestion owns too many independent aspects. Broadness remains a
diagnostic until annotated data proves a reliable gate, because comparative
questions can legitimately cover closely related aspects.

The Planner Prompt separately requires one primary answer target and asks for
independently answerable aspects to be split. That production instruction
reduces obvious compound questions but is not treated as proof of semantic
atomicity; Broadness Eval remains necessary.

When reference dependency graphs exist, evaluation also checks DAG validity,
cycles, unresolved dependencies, and normalized graph edit distance. Exact or
normalized decomposition match is reported only for cases with a valid gold
logical form; it is too strict as the sole metric for open research questions.

Requirement quality is evaluated below the subquestion level as two additional
diagnostics. Sufficiency checks whether the requirements can justify the stated
strength of the primary target; a prevalence claim such as `trend` requires
multi-source and temporal or distributional evidence rather than isolated
examples. Ownership checks whether semantically equivalent evidence needs are
repeated across subquestions or assigned to the wrong target. These diagnostics
remain human-reviewed until a calibrated semantic matcher is available.

The first real Planner review case demonstrated both failures: its trend target
required only papers about vector-store limitations and structured designs, and
the limitations requirement duplicated the separate driver subquestion. The
case remains a diagnostic artifact rather than Planner Gold. Prompt and schema
descriptions now encode the accepted policy, but semantic sufficiency and
ownership are not deterministic runtime gates.

### 4.7 Planner result

A Planner evaluation record should expose causes rather than one score:

```json
{
  "coverage": 0.91,
  "constraint_recall": 0.80,
  "redundancy": 0.00,
  "fragmentation_raw": 0.25,
  "broad_subquestion_ids": ["q1"],
  "graph_edit_distance": 1,
  "hard_failures": ["time_range_missing"]
}
```

## 5. Researcher evaluation

Researcher Eval separates retrieval, paper relevance, group support, and
minimum-set selection so a poor result can be attributed correctly.

The production Researcher asks the model for factorized object, problem,
constraint, evidence-kind, and answer-coverage judgments, then derives the
four-class relevance label deterministically. This makes the decision policy
testable but does not establish semantic correctness.

The executable slice is implemented in `citeguard.evaluation.researcher`. Its
versioned Agent Memory dataset is explicitly a mechanism-only `draft`: four
candidates are assessed in each of three cases, and the current labels exercise
minimum evidence groups of size one, two, and three. The annotations must
complete two-person review before their status can change to `reviewed` or
`frozen`. Versioned arXiv URLs freeze source identity; online retrieval is not
part of this slice.

Each case retains `original_question`, `subquestion`, `primary_answer_target`,
fixed answer requirements, exact candidate item IDs, group labels, and one or
more Gold MEGs. Dataset-level `subquestion_origin=manual` and
`evaluation_scope=researcher_meg_mechanism_only` state that Planner did not
create these cases and that they must not be used as Planner decomposition
Gold. Paper relevance remains local to each supplied subquestion; the original
question supports a separate Planner audit.

The draft also carries an explicit `open_adjudications` queue. In the current
version, the A-MEM label for the Memory-R1-specific case and the cross-paper
evolution-relation group/MEG labels in the two multi-source cases remain open.
Chronology or the union of stage descriptions does not by itself establish an
evolution relation. Until those entries are resolved, scores from the bundled
fixture validate only schema, runner, and metric mechanics.

Long human-readable dataset values use JSON arrays of text segments solely to
keep every Eval data line within the repository's 80-character limit. Dataset
validation joins those segments with spaces before semantic checks and metrics.

The runner validates Gold-factor consistency and exact paper, case, group, and
source identity. It reports per-factor accuracy, four-class relevance metrics,
unknown-abstention rate, group-support macro F1 and confusion, MEG complete-case
rate, mean cardinality error, and redundant-source rate. Each prediction set
also carries a required `system_id`. Retrieval and report-level Claim support
remain separate planned stages.

`unknown` is an abstention for title/abstract records that lack enough
information to classify, not a fifth graded relevance level. Evaluation reports
its abstention rate separately. An unknown prediction still counts as a false
negative for the candidate's resolved Gold class and therefore lowers that
class's recall and the four-class macro F1.

The staged design is grounded in two relevant precedents:

- [BEIR](https://arxiv.org/abs/2104.08663) evaluates heterogeneous retrieval
  tasks with standard ranking metrics and finds BM25 a robust baseline, while
  reranking and late-interaction methods can improve results at higher cost.
  CiteGuard therefore reports retrieval separately and retains a simple lexical
  baseline rather than assuming an LLM query planner is better.
- [SciFact](https://arxiv.org/abs/2004.14974) pairs scientific claims with
  evidence-containing abstracts, support/refute labels, and rationales. It
  motivates separating document retrieval, evidence selection, and scientific
  verification. CiteGuard adapts this at title-and-abstract level with four
  relevance grades and three `EvidenceStatus` outcomes.

| Stage | Status and metrics |
| --- | --- |
| Query planning | query uniqueness, constraint retention, useful-query count and query diversity |
| Retrieval | Recall@K for gold relevant papers, Precision@K, MRR or nDCG when graded relevance exists |
| Paper assessment | Implemented: factor accuracy, macro F1 for direct/partial/background/irrelevant, direct precision, per-class confusion, and unknown-abstention rate |
| Group support | Implemented: macro F1 and confusion over FULL/PARTIAL/NONE for exact source groups |
| Minimum evidence group | Implemented: complete-case rate, mean cardinality error, and redundant-source rate |
| Source selection | exact IDs enforced; broader precision/recall remains planned |
| Evidence state | macro F1 over supported/no relevant sources/insufficient evidence |
| Report support | Writer Claim entailment against selected abstract evidence and unsupported-claim rate |

The retrieval metrics are defined as:

```text
Recall@K = relevant items retrieved in top K / all gold relevant items
Precision@K = relevant items retrieved in top K / K
MRR = (1 / N) * sum_t(1 / rank_t(first relevant item))

DCG@K = sum_r((2^rel_r - 1) / log2(r + 1))
nDCG@K = DCG@K / IDCG@K
```

For an initial graded dataset, `direct=3`, `partial=2`, `background=1`, and
`irrelevant=0` is a reviewable mapping for nDCG. The mapping is dataset
metadata, not an LLM choice. Online arXiv results are not a stable evaluation
corpus, so each dataset must freeze an index snapshot or versioned candidate
pool.

Query count by itself is not a quality metric. One, three, or five queries are
acceptable when they maximize relevant-paper coverage without superficial
paraphrases. Retrieval labels must distinguish direct, partial, background, and
irrelevant papers so Recall@K does not reward keyword-only matches.

The six Prompt criteria become the annotation rubric: object match, problem
match, constraint match, actual method or finding, answer coverage, supported
aspects, and unsupported aspects or limitations. Prompt compliance and the
deterministic mapping are normal unit tests; semantic correctness is measured
on the annotated dataset. Direct precision and severe false acceptance remain
visible because incorrectly promoting partial, background, or irrelevant work
to direct can incorrectly enable a supported result.

## 6. Writer and Verifier evaluation

### 6.0 Method basis and adaptation

- [ALCE](https://aclanthology.org/2023.emnlp-main.398/) evaluates cited long-form
  generation along fluency, correctness, and citation-quality dimensions. Its
  citation completeness/correctness direction informs CiteGuard's claim-level
  citation recall and precision.
- [SummaC](https://arxiv.org/abs/2111.09525) shows that document-level factual
  consistency benefits from sentence segmentation and aggregation before NLI.
  CiteGuard therefore atomizes material claims before support comparison.
- [AlignScore](https://arxiv.org/abs/2305.16739) supplies a unified alignment
  baseline across factual-consistency tasks. It can be compared as a frozen
  model, but cannot explain a structured scope or causality violation alone.
- [RIGOURATE](https://aclanthology.org/2026.findings-acl.1699/) retrieves
  scientific claim evidence and predicts an overstatement score. CiteGuard
  adopts its evidential-proportionality motivation while using deterministic
  `EvidenceBoundary` rules to make failures executable and attributable.

### 6.1 Atomic claims and provenance

Writer output must be split into material atomic claims. Each claim points to
its originating subquestion and exact source IDs. Deterministic checks reject
missing or unknown IDs before semantic verification.

Planned citation metrics are:

```text
CitationRecall = supported material claims / all material claims
CitationPrecision = citations that support their attached claim / all citations
```

A frozen NLI or alignment model may provide entailment, neutral, and
contradiction probabilities. Non-entailment alone is not called exaggeration;
the structured boundary rules below distinguish unsupported, contradicted, and
overstated claims.

### 6.1.1 Executable fixed-contract fixture

`eval/datasets/writer_verifier_gold_draft_v0.json` fixes six synthetic cases
over the implemented Writer/Verifier boundary. Each case contains the exact
`WriterInput`, Writer section expectations, one candidate `WrittenReport`, and
the Gold `VerificationResult`. Writer expectations preserve upstream evidence
status, evidence reason, and the complete Claim-ID set without requiring one
exact prose rendering.

The cases cover a supported singleton, a supported multi-source MEG, invalid
Claim/source attribution, causal upgrade, evidence-status overstatement, and a
two-subquestion report whose failure is localized only to the bad sibling. The
dataset is `draft` and its evidence is explicitly `synthetic`; it is a stable
development oracle, not a production-quality or human-performance claim.

### 6.1.2 Independent Writer Gold

`eval/datasets/writer_gold_draft_v0.json` isolates Writer evaluation from
Verifier decisions. Its six cases cover all three `EvidenceStatus` values, new
and memory-reused results, zero/one/many Claims, singleton and multi-source
MEGs, a Claim jointly supported by two sources, and ordered multi-section
isolation. Gold sections preserve the exact evidence state, reason, Claim IDs,
and Claim-to-source edges while leaving free-form wording unscored.

`citeguard.evaluation.writer` evaluates a candidate `WrittenReport` using
deterministic section coverage, Claim recall, provenance precision and recall,
evidence-status accuracy, evidence-reason accuracy, unknown-ID counts, and typed
hard failures. Provenance is checked as exact Claim/source edges, so merging two
Claims with two citations cannot hide invalid cross-attribution behind a valid
source union.

The implemented deterministic Writer is the first evaluated system. It copies
one frozen Claim into one attributable statement, preserves ordered sections and
evidence state, and passes all six Writer Gold cases with perfect deterministic
metrics. This result establishes boundary preservation only; it does not score
semantic paraphrase or prose quality.

### 6.1.3 Deterministic Verifier baseline

The implemented Verifier checks section and Claim coverage, scoped Claim IDs,
known sources, exact Claim/source edges, evidence-state inheritance, duplicate
Claim use, and exact frozen Claim text. The combined six-case fixture now runs
the real implementation. Supported, invalid-provenance, and evidence-status
cases match their structural Gold decisions and retry scopes.

Causal upgrade and unsupported-number cases are rejected with the correct
subquestion scope but use the generic `unsupported` type. This is intentional:
exact deterministic checks can establish that text changed, but cannot reliably
distinguish a paraphrase from a causal, numeric, modality, contradiction, or
scope violation. Fine-grained types remain semantic Gold for the later fixed
NLI/alignment and structured-boundary layer.

### 6.2 Evidence boundary

The Writer/Verifier slice should test a structured evidence boundary containing
only fields justified by a cited source span, such as:

```text
research object, population, setting, method, time range,
outcome, quantitative interval, relation type, modality
```

The semantic production boundary schema remains deferred. The structural
Writer/Verifier contracts are implemented, while free-text `supported_aspects`
and `limitations` cannot by themselves support deterministic containment checks.

### 6.3 Causality and modality

Causality describes the asserted relationship, for example association,
prediction, or causal effect. Modality describes certainty, for example may,
suggests, supports, demonstrates, or proves. They are separate axes: a claim can
express a possible causal relation or a strong association.

Verifier uses explicit allowed-transition tables rather than an LLM-selected
strength score. Evidence that establishes association cannot authorize a causal
claim; evidence that only suggests a result cannot authorize `proves`.

### 6.4 Boundary violations

Let `C_d` be the Writer claim value and `E_d` the evidence boundary value for
dimension `d`:

```text
violation_d = 1 when C_d exceeds or is not licensed by E_d, else 0
OverclaimRate = sum_d(weight_d * violation_d) / sum_d(weight_d)
```

The rate is diagnostic. Population expansion, causal upgrade, unsupported
numbers, and incompatible time or setting are hard failures and cannot be
averaged away. The Verifier returns typed issues such as
`scope_expansion`, `causal_upgrade`, `modality_upgrade`, `unsupported_number`,
`unsupported`, or `contradicted` together with the affected subquestion ID.

## 7. End-to-end evaluation

End-to-end Eval measures the delivered report rather than repeating every
module metric:

- required research-aspect coverage in the final report;
- material-claim citation recall and citation precision;
- unsupported and overclaimed Claim rates;
- successful issue localization to the responsible subquestion;
- correction success after bounded content retry;
- total LLM calls, Tool calls, tokens, latency, and retry count;
- completion and terminal-failure rates.

Module metrics are retained beside the run so end-to-end failures can be traced
back to decomposition, retrieval, evidence assessment, writing, or verification.

## 8. Baselines, ablations, and calibration

Evaluation should compare simple baselines before complex ones:

- single end-to-end model call;
- the current fixed Planner/Researcher path without module quality gates;
- fixed NLI alone for Claim support;
- structured rules alone;
- fixed NLI plus structured rules;
- optional gray-band generative judge only if needed.

Ablations disable one real capability at a time, such as limitations,
structured boundary fields, causality rules, modality rules, or targeted retry.
Every switch must preserve the same dataset and reporting code.

Threshold calibration records precision, recall, F1, confusion matrices, and
confidence intervals where sample size permits. Duplicate detection should
prefer precision to avoid merging distinct work. Overclaim detection should
report both false acceptance and false rejection because either can harm the
research result.

## 9. Implementation order

The Researcher paper-relevance and MEG slice provides a versioned draft
dataset, deterministic metrics, and a CLI runner. Writer/Verifier development
does not depend on those semantic labels because it consumes fixed
`ResearchResult` objects. The remaining order is:

1. Maintain the independent Writer Gold and combined Writer/Verifier fixture.
2. Maintain the implemented minimal Writer and deterministic Verifier gates.
3. Maintain the implemented one-Researcher Workflow and add end-to-end run
   aggregation after a stable external live corpus is available.
4. Create a small versioned Planner Gold dataset and implement its deterministic
   metrics and hard-constraint checks.
5. Add a frozen multilingual embedding model and calibrate duplicate/match
   thresholds on the development split.
6. Extend Researcher Eval to online retrieval and evidence-state classification
   using frozen candidate pools.
7. Expand datasets from real failure traces without changing held-out labels.

In parallel, complete two-person review of all 12 Researcher paper assessments,
group labels, and Gold MEGs before changing that dataset from `draft` to
`reviewed` or `frozen`. This review is a promotion gate for Researcher Gold, not
a start gate for Writer/Verifier fixtures.

Evaluation-only model dependencies should be isolated from production runtime
dependencies unless the production Verifier later needs the same model.

## 10. Verification of the evaluation code

Implemented paper and MEG Eval tests verify:

- perfect predictions score every factor and relevance class;
- unknown predictions are recorded as abstentions and Gold false negatives;
- Gold relevance agrees with the deterministic factor policy;
- paper, case, group, and MEG source coverage match exactly;
- perfect group labels and selected MEGs score all MEG metrics correctly;
- the draft contains 12 candidates across three Agent Memory cases and Gold
  minimum-set sizes one, two, and three.
- the Writer/Verifier draft loads six fixed behavior classes;
- Writer expectations exactly preserve upstream Claim and evidence-state facts;
- Gold failures retain typed decisions and exact statement/subquestion scope;
- one invalid sibling does not select the valid sibling for correction.
- Writer Gold covers every v0 state and cardinality partition;
- valid Writer reports score one on every deterministic metric;
- mutations exercise all Writer hard-failure types;
- merged Claims cannot hide invalid cross-provenance.
- the actual deterministic Writer passes every Writer Gold case;
- repeated local Claim IDs remain valid across distinct subquestions.
- deterministic Verifier structural decisions match combined-fixture Gold;
- semantic-only cases fail safely with exact scope and generic `unsupported`;
- missing/unknown IDs and wrong provenance fail before semantic evaluation.

Planned later-stage verification includes:

- formula unit tests using hand-computed retrieval and alignment matrices;
- threshold selection tests use fixed labeled pairs;
- missing hard constraints cannot be offset by continuous scores;
- `n_i = 0`, `n_i = 1`, and `n_i > 1` distinguish omission, normal coverage,
  and fragmentation;
- one broad question can have full Coverage while still being diagnosed broad;
- unknown source IDs fail before NLI or rule evaluation;
- causal, modality, population, time, and numeric violations have explicit
  positive and negative fixtures;
- evaluation output records dataset, model, threshold, and code versions.

## 11. Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Added Workflow-level approved, rejected, source-free, failure, serialization, and real local Temporal retry coverage; end-to-end semantic aggregation remains planned. |
| 2026-08-28 | Connected the combined fixture to the real deterministic Verifier, matching structural Gold while safely retaining generic semantic rejection. |
| 2026-08-28 | Connected Writer Gold to the real deterministic Writer and fixed evaluation identity to scope Claim IDs by subquestion. |
| 2026-08-28 | Added independent Writer Gold with complete v0 partition checks, deterministic structure/provenance metrics, and mutations for every hard-failure type. |
| 2026-08-27 | Added a six-case synthetic Writer/Verifier draft with fixed Writer expectations, candidate reports, typed Gold decisions, and localization checks. |
| 2026-08-27 | Decoupled Writer/Verifier fixture work from Researcher Gold promotion and recorded the implemented report/verification boundary as its stable input. |
| 2026-08-26 | Recorded the real Planner trend counterexample as diagnostic-only evidence and clarified that semantic sufficiency/ownership remain Prompt plus human-Eval rules. |
| 2026-08-26 | Added Planner requirement-sufficiency and cross-subquestion evidence-ownership diagnostics for prevalence claims and duplicated evidence needs. |
| 2026-08-26 | Restricted the Agent Memory draft to Researcher/MEG mechanism testing, added a promotion-blocking adjudication queue, restored the 2023-2026 scope, and bumped the dataset to `0.6.0-draft`. |
| 2026-08-26 | Replaced the SciFact-only paper fixture with three Agent Memory cases, added exact group labels and Gold MEGs of sizes one through three, and implemented group-support and minimum-set metrics. |
| 2026-08-26 | Synchronized the module status and implementation order with the executable Assessment runner, 12-item draft dataset, and its five offline tests. |
| 2026-08-25 | Clarified that semantic Redundancy and Broadness remain Eval-only while Planner runtime enforces an explicit atomicity instruction plus normalized exact-duplicate rejection. |
| 2026-08-25 | Split the compound SciFact assessment question into three atomic questions, re-annotated all four candidates per question, and bumped the draft dataset to `0.4.0-draft`. |
| 2026-08-25 | Made the draft Eval JSON comply with the repository line limit by normalizing wrapped text segments during dataset validation. |
| 2026-08-25 | Added original-question traceability and explicit manual/Planner subquestion provenance to the draft dataset; Researcher scoring remains local to each subquestion. |
| 2026-08-25 | Implemented the first Assessment-only Researcher Eval runner and a four-item draft annotation set; human review is required before the dataset becomes reviewed or frozen Gold. |
| 2026-08-25 | Defined `unknown` as an assessment abstention and added a separate abstention-rate metric rather than treating it as a fifth relevance grade. |
| 2026-08-25 | Recorded the implemented factorized Researcher assessment boundary and added factor accuracy and direct precision to the planned Gold evaluation. |
| 2026-08-24 | Added primary-paper foundations, retrieval formulas, frozen-corpus requirements, and explicit adaptation boundaries for Planner, Researcher, and Writer/Verifier Eval. |
| 2026-08-24 | Established the planned module and end-to-end Eval framework, quantitative Planner metrics, Researcher metrics, and structured Claim-boundary validation design. |
