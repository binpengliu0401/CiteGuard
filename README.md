# CiteGuard

CiteGuard is an academic deep-research system under active development. Its goal is to decompose research questions, search arXiv in parallel, produce source-backed reports and independently verify whether report claims are supported by retrieved evidence.

The formal source tree currently contains shared research-domain contracts, an
executable Planner path without memory reuse, and a single-subquestion
Researcher. The complete business Workflow is not implemented yet.

## Target capabilities

- **Autonomous planning:** Planner decomposes a research topic into independently executable subquestions.
- **Parallel research:** Researcher Agents retrieve and evaluate arXiv papers through MCP.
- **Report synthesis:** Writer combines research results into a structured report with source provenance.
- **Evidence verification:** Verifier checks whether report claims are supported by the retrieved sources.
- **Durable execution:** Temporal preserves completed work and handles bounded retries and recovery.
- **Session memory:** Verified subquestion-level research notes can be reused within the same session.

## Intended workflow

```mermaid
flowchart LR
    A[Research question] --> B[Planner]
    B --> C1[Researcher 1]
    B --> C2[Researcher 2]
    B --> C3[Researcher N]
    C1 --> D[Writer]
    C2 --> D
    C3 --> D
    D --> E[Verifier]
    E --> F[Verified report]
```

## Technology

- **Python:** primary implementation language for Agents and research workflows;
- **Temporal:** durable orchestration, retries and state recovery;
- **MCP:** connection to arXiv and future research tools;
- **MathMind-RAG:** intended source of reusable grounding and verification behavior.

## Current implementation

- validated Planner Activity input and output contracts;
- strict structured-output schemas for Planner model responses;
- arXiv-only Planner tasks with smallest-sufficient, non-overlapping answer
  requirements and explicit evidence-strength rules for prevalence targets;
- a 4,000-token Planner completion ceiling with malformed-output finish-reason
  diagnostics;
- an OpenRouter boundary restricted to DeepSeek, Qwen and Z.ai GLM models;
- deterministic conversion from model output to domain subquestions;
- a single Researcher that plans bounded arXiv searches, freezes structured
  claims, and searches bottom-up for a minimum-cardinality evidence group;
- explicit evidence statuses and deterministic relevance labels derived from
  factorized per-paper assessments, with a conservative `unknown` abstention;
- a draft Agent Memory dataset and offline metrics for paper relevance,
  group-level support, and minimal evidence-group selection;
- 73 passing offline tests covering Planner, Researcher, domain contracts,
  evaluation, and repository style rules;
- explicit live Planner and Researcher smoke tests under `tests/live`.

## Planner live-validation status

The no-memory Planner and its arXiv-only/action-free requirement policy have
produced valid live structured outputs. The latest successful reviewed output is
stored in `tmp/planner_arxiv_only_demo.json`; it predates the newer requirement
sufficiency and evidence-ownership rules and is retained as a failure-analysis
example, not Gold.

The strengthened current contract is offline-tested but still awaits a complete
live revalidation. Two 2,500-token attempts returned truncated JSON. Planner now
uses 4,000 completion tokens, but the first request at that budget remained
unresponsive and was terminated without saving partial output.

After completing the editable installation below, run one test module directly:

```powershell
python .\tests\planner\test_activity.py
```

Run the complete formal offline suite:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Run the review fixture through the Researcher assessment metrics:

```powershell
python -m citeguard.evaluation.runner `
  --dataset eval/datasets/researcher_assessment_draft_v0.json `
  --predictions eval/fixtures/researcher_assessment_predictions_v0.json
```

The bundled assessment dataset is still a human-reviewable, mechanism-only
draft. Its manually authored subquestions are not Planner Gold, and unresolved
paper and evolution-relation labels are listed in the dataset itself. The
fixture validates runner and metric behavior; its score is not a semantic
quality claim about either Planner or Researcher.

## Local development

Requirements: Python 3.10+ and the [Temporal CLI](https://github.com/temporalio/cli/releases).

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
temporal --version
```

### macOS and Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
temporal --version
```

The editable installation is required by the repository's `src/` layout. It
adds `src/citeguard` to the active virtual environment without copying the
package, so source changes take effect immediately. If the package is not
installed, PowerShell can run a one-off command by setting `PYTHONPATH` first:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python .\tests\planner\test_activity.py
```

Start a local Temporal development server in another terminal:

```bash
temporal server start-dev --db-filename temporal.db
```

The Temporal UI is available at <http://localhost:8233> by default.
