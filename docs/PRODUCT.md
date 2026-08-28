# CiteGuard Product Definition

> Status: accepted product direction; implementation remains incremental.
> Updated: 2026-08-23.

## 1. Problem

A research answer is useful only when its scope is understandable, its evidence is traceable and failures do not force unrelated completed work to run again. CiteGuard turns one research question into a durable, source-backed research report.

## 2. Intended user experience

The user submits a research question and a `session_id`. CiteGuard shows the generated research plan, performs independent research tasks, displays progress, produces a report with clickable sources and exposes whether each report claim passed verification. A later question in the same session can reuse compatible research notes.

## 3. Product principles

- A component is an Agent only when it has its own context, tools or meaningful decision authority.
- Every component must have a concrete reason to exist.
- Reliability must be demonstrated through real execution traces and measurable outcomes.
- Infrastructure failures and content failures are different and must have different recovery paths.
- Memory is stored at subquestion/result granularity so that Planner reuse operates on the same unit it creates.

## 4. Core release scope

- Planner decomposition and same-session memory reuse;
- independent arXiv-backed Researcher tasks;
- report synthesis with claim/source provenance;
- evidence-grounding verification;
- Temporal durable execution;
- infrastructure retry and content-aware targeted retry;
- a FastAPI and React demo that exposes the research trace.

## 5. Explicit exclusions from the first release

- cross-session memory aging and temporal invalidation;
- recursive tree search or unlimited dynamic Agent spawning;
- a second local FAISS MCP tool;
- production-grade distributed Temporal deployment;
- general user management and nonessential settings UI;
- validation that a cited paper is objectively true rather than merely supportive of a claim.

## 6. Acceptance themes

- parallel Researcher execution has a measured wall-clock benefit;
- an infrastructure failure retries only the failed Activity attempt;
- a content failure identifies the affected subquestion and preserves unrelated results;
- a repeated same-session subquestion can reuse an existing note without a new arXiv call;
- complete execution traces exist for normal execution and both retry classes;
- report citations are inspectable from the demo.

## 7. Origin

This document is the concise product contract derived from the original v2 design notes. Detailed implementation status belongs in [STATUS.md](STATUS.md), not here.

## 8. Change history

| Date | Change |
| --- | --- |
| 2026-08-23 | Extracted a stable product definition from the original v2 design document and separated product intent from implementation status. |
