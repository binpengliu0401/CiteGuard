# Historical Experiments and Documents

This directory describes experiments or superseded planning. Historical documents are not the source of current implementation behavior.

## Temporal × MCP spike

The executable learning-spike scripts remain for historical recovery and MCP
experiments even though the formal Researcher and exactly-one Workflow now
replace their basic Activity-boundary and orchestration examples:

- `../../test/mcp_test/` — manual MCP scripts;
- `../../test/temporal_test/` — manual Temporal and integration scripts.

The spike answered concrete uncertainties about MCP stdio, Temporal Activity
boundaries, serialization and Worker recovery. Formal source now covers the
first three. The old scripts are retained only until interruption/replay
coverage replaces their remaining recovery evidence.

The former `file/process.md` and `file/temporal_mcp_framework.md` documents were removed after their current conclusions were transferred to `STATUS.md`, `orchestration.md` and `researcher-arxiv.md`. Git history retains the original experiment narrative.

Once formal source and automated tests cover the same behavior:

1. transfer still-valid architectural conclusions to the owning module documents;
2. retain important decisions in Git or an ADR;
3. remove obsolete duplicate scripts and documents rather than maintaining two implementations.

## Change history

| Date | Change |
| --- | --- |
| 2026-08-28 | Recorded that formal Researcher and exactly-one Workflow code supersede the basic spike paths; interruption/replay evidence still gates final removal. |
| 2026-08-23 | Classified the existing Temporal/MCP work as a validated historical spike and defined its removal condition. |
