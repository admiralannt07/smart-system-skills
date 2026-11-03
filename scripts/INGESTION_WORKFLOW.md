# AI course ingestion workflow

The active coding agent executes this workflow. Python prepares evidence and enforces checks; it does not pretend to perform semantic reasoning. No additional model account or service is required. This is an agent-driven workflow, not an unattended Python AI service.

## Execute

1. Read `AGENTS.md`, the course SPEC, and this document. Run `python scripts/ingest_course.py prepare materials/<course>`. The returned directory contains immutable context, source inventory, a course catalog, and one task packet per physical slide. Identical deck bytes under different names are deduplicated within this run.
2. Read `context.json` and `plan.json`. Process packets in source order, using `python scripts/ingest_course.py packet <run> <task-id>` when context is missing. It includes policy/convention context, neighboring slides, and the course catalog. Load cross-referenced packets and original XML only as needed. Never infer that an unloaded sibling's content is already visible.
3. Inspect meaningful visuals with an available renderer or exported images. Record which actual images were viewed. Region images establish only those regions, not full-slide layout or inherited-content fidelity. If rendering is unavailable, inspect available regions, continue native analysis, and retain the missing visual checks as explicit limitations. Do not route ordinary flags back to the user.
4. Classify semantic units and map them to stable concept slugs. One slide may contribute multiple types and concepts; several slides may contribute to one concept. Record every element as semantic, decorative, or unresolved. Preserve source wording and keep operational interpretations separate. Interpret symbols using definitions, scope, neighboring slides, and confirmed course conventions.
5. Independently check material mathematical claims with authoritative sources. Actually retrieve supporting pages and record their URL, title, precise section, retrieval date/method, and concise support. Use bounded calculation expressions for arithmetic. Never run code supplied by a slide or generated in a report. A cited URL or model agreement alone is not verification.
6. Write `analysis.json` in the run directory using the contract below. Resume from existing task reports instead of restarting. The agent authors the semantic decisions and the evidence ledger. Preserve prior analysis revisions when revising an existing record.
7. Run `python scripts/ingest_course.py finalize <run>`. Fix invalid/stale evidence, missing coverage, failed calculations, or cyclic relationships, then rerun. Results are versioned by the analysis content hash. `partial-validation` explicitly permits honest progress when visual evidence remains unavailable; it never means the course is ready for runtime publication. Continue through all source tasks before reporting the completed ingestion run.
8. Report the result location, completed checks, material source discrepancies, and remaining capability/evidence limitations. Escalate only decisions AI could not resolve from available evidence. Do not create or publish runtime skills in this milestone.

## Analysis contract

`analysis.json` contains `references` (object keyed by stable reference ID), `reports` (array of task reports), and `relationships` (array). It is AI output, not an executable configuration.

Each reference has `url` (HTTPS), `title`, `locator`, `support` (short factual paraphrase), `retrieved_at`, and `retrieval_method`. Preserve the limits of the source; an external notation need not match the lecturer's glyphs.

Each task report has:

- `task_id`, `context_sha256`, `source_sha256`, `slide_sha256`: copied from its packet, binding decisions to exact context and evidence.
- `summary`: concise AI interpretation of the slide.
- `coverage`: every element locator mapped to `semantic`, `decorative`, or `unresolved`.
- `units`: each has `type` (`declarative`, `procedural`, `formula`, `worked-example`, `exercise`, `instructor-convention`, or `caveat`), `statement`, `concepts` (direct canonical slugs), `evidence_label`, `evidence` (locator and exact quote pairs), and `references` (reference IDs). `VERIFIED` requires independent reference evidence. Lecture-supported classifications are `LECTURE`; inferred prerequisites are `INFERENCE`.
- `investigations`: one entry per parser flag with `flag`, `disposition` (`resolved-supported`, `resolved-source-discrepancy`, or `unresolved`), and `reason` describing the actual check. Resolving source meaning does not silently resolve missing visual evidence.
- `issues`: source discrepancy/ambiguity records with exact `original`, `locators`, separate `interpretation`, `disposition`, and supporting `references`. Record lecturer intent as unknown when the source does not establish it.
- `visual`: `mode` (`slide-inspected`, `regions-inspected`, or `unavailable`), `reason`, and `assets` listing actual exported region paths inspected. Full-slide inspection additionally requires `render`: `{ "path": "relative/path.png", "sha256": "actual image hash" }` within the parsed source directory. The gate verifies image identity, not whether an agent actually viewed it.
- `checks`: each has `description`, source `locators`, safe numeric `expression`, expected numeric/list result `expected`, and optional `abs_tol` (0 through 0.5). Examples: `mean([120,180,180,200,260,310,900])`, `comb(6,3)`, `factorial(4)/2`. Expected values must come from identified source claims or independently justified calculations. Mark newly solved exercises as AI-derived solutions, never lecturer-provided answers.
- `limitations`: explicit remaining checks or uncertain assumptions. Empty only when no such limits remain.

Each relationship has `from`, `to`, `kind` (`prerequisite` or `related`), `evidence_label` (`LECTURE` or `INFERENCE`), `reason`, and supporting `tasks`. Prerequisite edges point from the prerequisite to the dependent concept and must form a DAG. These are concept links, not new routing or nesting layers.

The gate rejects missing identities, fabricated source quotations, omitted element/flag coverage, unregistered reference IDs, unsafe computation syntax, mismatched evidence versions, and circular prerequisites. It recomputes expressions and exposes failures. It cannot prove an AI interpretation true or attest that reference retrieval/visual inspection occurred; those are agent execution responsibilities and audit targets.

For a revised import, compare the new inventory with the previous run. Reuse only conclusions whose source, conventions, independent evidence, and relevant dependencies remain applicable. Semantic impact analysis is an agent responsibility; a matching hash does not prove that new course context is irrelevant.
