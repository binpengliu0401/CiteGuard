# CiteGuard Engineering Code and Documentation Standard

> Status: active repository-wide convention.
> Applies to: Python modules, classes, functions, Activities, Workflows, MCP/LLM
> tools, runtime prompts, and explanatory inline comments.

## 1. Purpose

Code documentation must explain business meaning, boundaries, invariants, and
failure behavior without duplicating syntax that is already visible in type
annotations and implementation. The goal is to help a developer understand why
the code exists, how to use it correctly, and what assumptions must remain true.

This document owns stable documentation conventions. `docs/STATUS.md` records
only when the convention is adopted or materially changed.

## 2. Documentation layers

| Artifact | Required content | Detail level |
| --- | --- | --- |
| Module docstring | Module responsibility and boundary | Short |
| Class docstring | Business meaning, lifecycle and invariants | Moderate |
| Public function, Activity or Workflow | Purpose, inputs, output, errors and important execution semantics | Full |
| Important private boundary | Purpose, inputs, output and relevant errors | Moderate to full |
| Simple helper or validator | One-line purpose; invariant when non-obvious | Short |
| Inline comment | Why a decision, branch or invariant exists | Only when needed |
| Tool description | Capability, when to use it, inputs, result and constraints | Concise and model-facing |
| Runtime prompt | Role, task, input data, rules and output contract | Structured but token-conscious |

Documentation depth follows behavioral importance. Do not apply a long template
to a trivial helper merely for visual consistency.

### 2.1 Python line length

Formal Python code under `src/`, `tests/`, and `eval/` has a hard maximum of 80
physical characters per line. This adopts the maximum in the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#s3.2-line-length)
as an enforceable repository rule rather than a formatter preference.

- Wrap calls, conditions, imports, annotations, and container literals using
  implicit joining inside parentheses, brackets, or braces.
- Never use a backslash for line continuation.
- Split long human-readable strings into adjacent string literals inside
  parentheses.
- Keep docstring summary lines within the same limit.
- Do not leave a line over 80 characters when it can be wrapped. Formal source
  and test files receive no discretionary line-length exception.

The offline style test scans every Python file under `src/`, `tests/`, and
`eval/`; any line over 80 characters fails the suite.

Human-maintained JSON under `eval/` follows the same physical 80-character
limit. Long prose values are stored as arrays of text segments and normalized
by the owning dataset loader. The style suite scans these JSON files separately.

## 3. Function and method docstrings

Use readable Google-style sections for public functions and important
boundaries. Start with a one-line imperative summary, then explain the problem
or boundary when that context is not obvious.

```python
async def plan_research(
    input: PlannerActivityInput,
) -> PlannerActivityOutput:
    """Decompose a research question into executable subquestions.

    This Activity owns Planner orchestration at the Temporal boundary. Prompt
    construction, provider I/O, validation, and domain assembly remain in their
    owning modules.

    Args:
        input: Validated Planner input containing the research question,
            session identity, and available research notes.

    Returns:
        A Planner result containing at least one validated domain subquestion.

    Raises:
        ApplicationError: If an unsupported capability is requested or the
            model returns a permanently invalid result.

    Retry behavior:
        Transient provider failures propagate for Temporal retry. Deterministic
        input and validation failures are non-retryable.
    """
```

### 3.1 Standard sections

Use only the sections that add information:

- `Args`: explain business meaning, accepted scope, units or trust level;
- `Returns`: explain the semantic result and important guarantees;
- `Raises`: list meaningful exceptions and the conditions that cause them;
- `Side effects`: describe network, storage, process or external-state changes;
- `Retry behavior`: document retryable versus deterministic failure behavior;
- `Notes`: record a critical invariant that does not fit another section;
- `Example`: include only when correct usage is otherwise difficult to infer.

Do not repeat types already visible in the signature. Prefer:

```text
input: Validated Planner input containing session-scoped planning data.
```

over:

```text
input: A PlannerActivityInput object.
```

### 3.2 Detail levels

- Activities, Workflows, public APIs and provider boundaries use the full form;
- domain assembly and storage boundaries include inputs, outputs and errors;
- validators state the invariant they enforce;
- obvious private helpers use a single accurate sentence.

## 4. Class and domain-model documentation

Class docstrings explain what an object represents in the business workflow,
who creates it, who consumes it, and which invariants define a valid state.
Dataclass and Pydantic field types remain in code; docstrings explain semantic
differences such as session identity versus subquestion identity.

For `__post_init__` and validators:

- state the invariant being enforced;
- explain status-dependent field relationships;
- do not narrate each `if` statement;
- do not claim deep immutability when a frozen dataclass contains mutable values.

## 5. Inline comments

Inline comments explain decisions that are not evident from the code. They must
answer why, not translate the next line into English.

Preferred:

```python
# Fail explicitly so the no-memory slice cannot silently ignore reusable notes.
if input.existing_notes:
    ...
```

Avoid:

```python
# Check whether existing_notes is not empty.
if input.existing_notes:
    ...
```

Useful inline-comment subjects include:

- security or trust boundaries;
- deterministic Workflow requirements;
- retry classification;
- non-obvious normalization;
- temporary capability gates;
- deliberately excluded behavior.

Remove comments that become false, merely repeat the implementation, or describe
historical code that no longer exists. Git remains the complete edit history.

## 6. Tool descriptions

Tool descriptions are model-facing interface documentation. They must help an
Agent decide whether to call the tool and how to interpret its result. Keep them
shorter than developer docstrings because they consume model context.

```python
@mcp.tool()
async def search_arxiv(
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """Search arXiv papers by keyword.

    Use this tool when a research task requires candidate academic papers from
    arXiv. Search results are not proof that a paper supports a claim.

    Args:
        query: Keyword query sent to the arXiv API.
        max_results: Maximum number of papers to return.

    Returns:
Papers containing title, arXiv ID, abstract text, and URL.

    Constraints:
        The Researcher must still evaluate relevance and evidence quality.
    """
```

A tool description should cover:

1. capability;
2. when to use or not use it;
3. semantic meaning of inputs;
4. result shape and guarantees;
5. constraints, trust limits or cost-sensitive behavior.

Do not include internal implementation details such as HTTP client lifecycle
unless they affect the calling Agent.

## 7. Runtime prompt structure

Runtime prompts use explicit conceptual sections when the prompt is complex
enough to benefit from them:

```text
Role
Task
Input
Rules
Output
```

- `Role` defines the Agent's responsibility and exclusions;
- `Task` states the decision or transformation to perform;
- `Input` describes the user message or JSON data envelope;
- `Rules` contains behavioral, safety and quality constraints;
- `Output` points to the bound schema and forbids extra prose when required.

Keep simple prompts compact. Structure must improve interpretation rather than
add headings that consume tokens without clarifying behavior.

## 8. Review checklist

Before accepting documentation changes, verify:

1. the summary states business purpose rather than restating the function name;
2. inputs and outputs describe semantics rather than only types;
3. meaningful errors, side effects and retry behavior are documented;
4. inline comments explain why and remain adjacent to the protected decision;
5. Tool descriptions help model selection without leaking irrelevant internals;
6. runtime prompts separate trusted policy from untrusted input data;
7. planned behavior is clearly marked and not described as implemented;
8. documentation agrees with executable source and tests;
9. all code-facing documentation and runtime prompts are written in English.
10. every formal Python line and human-maintained Eval JSON line is at most 80
    characters.

## 9. Change history

| Date | Change |
| --- | --- |
| 2026-08-25 | Extended the 80-character check to human-maintained Eval JSON and added normalized text-segment storage for long dataset prose. |
| 2026-08-25 | Extended the enforced 80-character Python limit to top-level Eval code as well as formal source and tests. |
| 2026-08-25 | Made 80 characters a hard maximum for formal Python source and tests, with an offline enforcement test. |
| 2026-08-23 | Established structured standards for docstrings, inline comments, Tool descriptions and runtime prompts. |
