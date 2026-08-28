# Report Synthesis and Verification

> Status: Writer/Verifier boundary contracts, deterministic Writer and Verifier,
> independent Writer Gold, and a combined synthetic fixture implemented;
> semantic synthesis and classification planned.
> Owning source: `src/citeguard/domain/report.py`,
> `src/citeguard/writer/`, and `src/citeguard/verifier/`.

## 1. Purpose

This module turns individual research results into a readable report and checks whether the report's claims are supported by the evidence returned by Researchers.

Writer, Verifier and content-aware retry share one document because they depend on one provenance chain. They remain separate code components.

## 2. Writer boundary

Writer is a node rather than an Agent. It receives completed and memory-reused research results and performs a structured synthesis. It has no search tool and does not decide whether evidence is sufficient.

Implemented `WriterInput` contains the original question and a nonempty list of
unique `SubQuestionResult` pairs. Each pair binds the planned subquestion to the
exact completed or memory-reused `ResearchResult`.

Writer output must preserve:

```text
ReportStatement
    → originating sub_question_id
    → ResearchClaim identifiers
    → source identifiers
```

Without this mapping, Verifier cannot reliably identify the failed research scope.

Writer returns a `WrittenReport` containing one or more `ReportSection` objects.
Section and statement identities are unique, while report limitations remain
separate from material provenance-bearing statements.

The implemented minimal Writer is deterministic. It preserves research-result
order, emits one section per subquestion and one statement per Claim, copies the
frozen Claim text, retains exact Claim/source IDs, and carries evidence status
and reason without reinterpretation. Source limitations are deduplicated by
normalized text in stable input order. `write_report` exposes this assembly as a
Temporal Activity with no tools, model calls, or side effects.

## 3. Verifier boundary

Verifier checks claim-to-evidence support. It does not establish that a paper is objectively true and does not replace peer review.

Implemented boundary:

```python
VerifierInput(
    writer_input=...,
    report=...,
)

VerificationResult(
    approved=...,
    issues=[VerificationIssue(...)],
    failed_sub_question_ids=[...],
)
```

`failed_sub_question_ids` identifies the `SubQuestion.id` values whose results need correction. It never contains Activity IDs, Worker IDs or arbitrary labels.

Approval requires empty issues and failed IDs. Rejection requires typed issues,
and the failed-ID set must exactly match their subquestion scope. The contract
checks structure only: unknown or semantically invalid provenance remains valid
Verifier input so the implementation can return an attributable failure.

The implemented deterministic Verifier checks exact section and Claim coverage,
subquestion-scoped Claim IDs, known source IDs, Claim/source edges, duplicate
Claim use, evidence status/reason inheritance, and frozen Claim text. Exact text
is the safe baseline: changed text is rejected as `unsupported` rather than
being assigned an uncalibrated causal, numeric, modality, contradiction, or
scope label. Content rejection returns `VerificationResult`; an invented section
causes a nonretryable Activity error because it cannot map to a valid retry ID.

## 4. Verification rules

- every material factual claim has explicit source provenance;
- every referenced source exists in the aggregated Researcher results;
- the cited evidence supports the claim as written, including scope and qualifiers;
- unsupported synthesis introduced by Writer is rejected;
- a failed ID belongs to the input result set;
- approval requires no failed IDs.

## 5. Researcher Claim and planned report evidence boundary

Verifier must distinguish an unsupported Claim from a Claim that expands a
narrower supported conclusion. Researcher now emits atomic `ResearchClaim`
objects with exact source IDs, and a supported result carries a minimum evidence
group. The implemented Writer preserves that provenance. Verifier will add a
structured report-evidence boundary bound to cited evidence. Candidate
dimensions include:

```text
research object, population, setting, method, time range,
outcome, quantitative interval, relation type, modality
```

`supported_aspects` and `limitations` remain necessary explanatory fields, but
free text alone cannot support deterministic containment checks. The exact
semantic production schema remains planned beyond the implemented
deterministic Writer and Verifier baseline.

### 5.1 Causality and modality

Causality describes the relationship asserted by a Claim, such as association,
prediction, or causal effect. Modality describes certainty, such as may,
suggests, supports, demonstrates, or proves. They are separate axes and use
explicit allowed-transition tables rather than an LLM-selected strength score.

An association source cannot authorize a causal Claim. A source that only
suggests a result cannot authorize `proves`, even when its population and
outcome otherwise match.

### 5.2 Typed Verifier issues

Implemented issue types include:

- `missing_provenance`, `unknown_claim`, `unknown_source`, and
  `invalid_provenance`;
- `unsupported` and `contradicted`;
- `scope_expansion`;
- `causal_upgrade` and `modality_upgrade`;
- `unsupported_number`;
- `evidence_status_overstatement`.

Population expansion, causal upgrade, unsupported numbers, and incompatible
scope are hard failures. A diagnostic aggregate must not average them away.

### 5.3 Fixed development fixture

`eval/datasets/writer_verifier_gold_draft_v0.json` is the first executable
fixture over this boundary. Each synthetic case fixes `WriterInput`, expected
section evidence state and Claim coverage, a candidate `WrittenReport`, and the
Gold `VerificationResult`. It covers:

- supported single-source output;
- supported multi-source MEG output;
- invalid Claim/source provenance;
- association rewritten as causation;
- insufficient evidence rewritten as supported;
- exact failure localization in a two-subquestion report.

The fixture intentionally does not require one exact Writer prose string beyond
the controlled candidate report. Its `draft` and `synthetic` metadata prevent
schema validation from being misreported as production quality evidence.

### 5.4 Independent Writer Gold

`eval/datasets/writer_gold_draft_v0.json` evaluates Writer responsibility
without embedding a Verifier decision. Six cases cover supported singleton,
multi-Claim MEG, jointly supported Claim, partial insufficient evidence, no
relevant sources, and ordered new-plus-reused results. The dataset validator
requires every v0 case kind, all evidence states, both subquestion statuses,
zero/one/many Claims, singleton/multi-source MEGs, and a multi-section case.

The deterministic evaluator compares report structure with exact Gold
Claim/source edges. It reports section coverage, Claim recall, provenance
precision/recall, evidence-state and reason accuracy, unknown IDs, and typed
hard failures. It deliberately leaves paraphrase and prose quality for a later
calibrated semantic evaluation.

## 6. Content-aware retry (planned)

```text
Verifier rejects Q2
    → preserve all unrelated research results
    → rerun only Researcher for Q2
    → include the Verifier reason as new input
    → rerun Writer and Verifier over the corrected aggregate
```

This is Workflow business logic, not Temporal's automatic infrastructure retry. Content correction is bounded by a maximum number of rounds.

## 7. Multiple failures

Independent failures use separate `VerificationIssue` objects with their own
subquestion and reason. Workflow derives retry selection from the exact
`failed_sub_question_ids` set and does not parse prose reasons.

## 8. Failure injection

The demo's content-failure control intentionally creates an unsupported Writer claim. It must demonstrate:

- Verifier identifies the affected subquestion;
- only that Researcher is run again;
- feedback differs from an infrastructure retry;
- unrelated research results remain unchanged;
- the corrected report passes another verification round.

Failure injection is demo/test support and must be disabled by default outside an explicit test path.

## 9. Coupled-change checklist

| Change | Also review |
| --- | --- |
| Report/claim schema | Writer, Verifier, API and React report rendering |
| Source provenance | Domain contracts, Researcher output, Memory and Verifier |
| Verifier result | Workflow selection logic, Researcher feedback and progress UI |
| Correction limit | Orchestration terminal states and acceptance traces |

## 10. Verification

Implemented contract tests verify statement provenance, unique identities,
approval/rejection invariants, exact issue scope, reused-result identity, and a
full nested round trip through the configured Temporal converter. Fixture tests
also verify six-case coverage, upstream Claim/status preservation, typed Gold
decisions, and sibling-safe localization. Independent Writer Gold tests verify
all v0 boundary partitions, perfect valid reports, every hard-failure mutation,
and cross-provenance created by merged Claims. Writer and Verifier runtime
behavior coverage now proves that:

- supported report passes;
- unsupported claim fails with the correct subquestion ID;
- missing or unknown source identifiers fail;
- unrelated subquestions are not selected for retry;
- evidence status and reason cannot be overstated;
- changed Claim text is conservatively rejected as `unsupported`;
- content rejection is a normal Activity result;
- invented sections fail nonretryably because they have no retry target.

The minimum orchestration is implemented: exactly one Researcher result reaches
Writer and Verifier, approval and rejection both return a complete Workflow
result, and infrastructure retry remains distinct from content rejection.
Semantic correction behavior remains planned:

- a corrected result can pass on the next round;
- repeated failure terminates at the configured bound;
- report rendering exposes sources and verification state.

### 10.1 Planned Eval metrics

Writer/Verifier Eval uses material atomic claims and exact provenance to report
citation recall, citation precision, unsupported-claim rate, overclaim type,
issue-localization accuracy, and correction success. A frozen NLI or alignment
model may supply entailment, neutral, and contradiction probabilities, but
non-entailment alone is not labeled exaggeration. Deterministic boundary rules
identify why the Claim exceeds its evidence.

The method choices have four direct precedents:

- [ALCE](https://aclanthology.org/2023.emnlp-main.398/) separates fluency,
  correctness, and citation quality and motivates claim-level citation
  completeness and correctness;
- [SummaC](https://arxiv.org/abs/2111.09525) shows that factual-consistency NLI
  benefits from sentence-level segmentation and aggregation, motivating atomic
  Claim comparison rather than one report-to-document score;
- [AlignScore](https://arxiv.org/abs/2305.16739) supplies a fixed alignment-model
  baseline across several factual-consistency settings;
- [RIGOURATE](https://aclanthology.org/2026.findings-acl.1699/) directly studies
  evidence retrieval and scientific overstatement, motivating evidential
  proportionality and a dedicated overclaim evaluation.

CiteGuard does not copy any one metric as its decision rule. It combines fixed
model probabilities with deterministic provenance and boundary checks:

```text
CitationRecall = supported material claims / all material claims
CitationPrecision = supporting attached citations / all attached citations

violation_d = 1 when Claim_d is not licensed by Evidence_d, else 0
OverclaimRate = sum_d(weight_d * violation_d) / sum_d(weight_d)
```

`OverclaimRate` is diagnostic only. Scope expansion, causal or modality
upgrade, unsupported numbers, and incompatible method, setting, or time are
typed hard failures. Relation type and modality remain separate axes with
explicit allowed-transition tables. The minimum experiment compares fixed NLI
only, structured rules only, and NLI plus rules, then reports false acceptance,
false rejection, issue-localization accuracy, and targeted correction success.

The shared formulas, baselines, hard-gate policy, calibration, and separation
from final report Eval are owned by [evaluation.md](evaluation.md).

## 11. Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Connected deterministic Writer and Verifier to the exactly-one-Researcher Workflow; content rejection now returns as an inspectable business result. |
| 2026-08-28 | Implemented deterministic Verifier provenance/state gates and Activity with exact retry localization and generic rejection for semantic-only changes. |
| 2026-08-28 | Implemented deterministic Writer assembly and Activity with one statement per Claim, exact evidence-state preservation, stable ordering, and limitation aggregation. |
| 2026-08-28 | Added independent Writer Gold with all v0 state partitions, deterministic metrics, and complete hard-failure mutation coverage. |
| 2026-08-27 | Added a six-case synthetic Writer/Verifier draft fixture covering supported output, provenance, overclaiming, and exact localization. |
| 2026-08-27 | Implemented and froze the Writer/Verifier data boundary with SubQuestionResult aggregation, structured report provenance, typed issues, exact retry scope, and Temporal round-trip coverage. |
| 2026-08-24 | Expanded Writer/Verifier Eval with ALCE, SummaC, AlignScore, and RIGOURATE foundations, formulas, hard-gate rationale, and planned ablations. |
| 2026-08-24 | Added the planned atomic Claim, structured evidence boundary, causality/modality rules, typed issues, and Writer/Verifier Eval boundary. |
| 2026-08-23 | Combined Writer, Verifier, provenance and content-retry design; defined the semantics of failed subquestion IDs. |
