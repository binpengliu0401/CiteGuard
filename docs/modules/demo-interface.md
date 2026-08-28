# Demo Interface

> Status: planned; no FastAPI or React source exists.
> Owning source: future API and web packages.

## 1. Purpose

The demo makes CiteGuard's research trace visible. It is not a general chat product and does not include user management or nonessential settings in the first release.

FastAPI and React share one document initially because both implement one progress-and-report contract. Split them only after either side has substantial independent design.

## 2. Required user-visible behaviors

1. show Planner subquestions and their `new` or `reused_from_memory` status;
2. show Researcher tasks running concurrently and completing independently;
3. show infrastructure retry separately from content correction;
4. show the final report with clickable sources and verification state.

## 3. API responsibilities

- start a research Workflow and return its durable identifier;
- query current Workflow progress without changing execution;
- stream state changes to the browser;
- return the final verified report;
- expose explicit development/demo endpoints for the two failure injections.

Server-Sent Events are the first-choice transport because progress is primarily server-to-client. Use WebSocket only if later requirements need bidirectional real-time interaction.

## 4. Minimal progress model

The interface needs stable states for:

- planning;
- planned/reused/researching/retrying/completed subquestions;
- writing;
- verifying;
- content correction;
- approved;
- terminal failure or cancellation.

The API translates durable Workflow state into this public model. The React client must not infer business state by parsing log text.

The underlying exactly-one-Researcher Workflow and command-line client now
exist, but the Workflow exposes no progress queries and there is still no HTTP
or SSE boundary. The demo must build on durable state rather than treating the
CLI JSON result as a progress API.

## 5. Failure injection

Two controls remain independent:

| Control | Injected failure | Expected display |
| --- | --- | --- |
| Infrastructure | One transient Researcher Activity failure | Same input retries; other results remain intact |
| Content | One unsupported Writer claim | Verifier reason appears; selected Researcher receives changed input |

The controls are test/demo features, off by default, and must not be implemented as hidden behavior in production paths.

## 6. Non-goals

- authentication and user administration;
- settings pages;
- arbitrary Workflow management UI;
- editing reports in the browser;
- production monitoring and alerting;
- mobile-specific design.

## 7. Coupled-change checklist

When changing the interface contract, review Workflow progress state, API serialization, React rendering and demo acceptance traces together. A new internal state does not require a public state unless the user needs to understand or act on it.

## 8. Verification

- reconnecting to the progress stream recovers current state;
- state transitions remain ordered and idempotent in the UI;
- both failure classes are visually distinct;
- source links and verification results are inspectable;
- connection errors do not change Workflow execution;
- the demo shows real Workflow state rather than scripted animation.

## 9. Split condition

Split this document into API and Web documents when the API serves another client, the React application gains independent behavior, or their contracts can no longer be reviewed coherently in one file.

## 10. Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Recorded the implemented minimum Workflow/client as the demo's backend baseline while keeping FastAPI, progress queries, SSE, and React planned. |
| 2026-08-23 | Defined the minimal demo boundary, chose SSE as the initial progress transport and kept API/UI documentation combined. |
