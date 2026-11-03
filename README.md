# smart-system-skills

A deterministic ingestion pipeline for turning lecture decks into auditable course knowledge, plus the Agent Skills package built from that knowledge.

The repository currently covers one course, `statistics-probability`. It converts PowerPoint decks into structured extraction packets, requires a reviewer to account for every slide element, every parser flag and every checkable calculation, and only then produces a validation report that runtime skills can cite.

## What is in version control

```text
scripts/                       Shared ingestion, rendering and validation utilities
skills/statistics-probability/ Runtime Agent Skills package (root skill, eight concept sub-skills, evidence references)
tests/statistics-probability/  Unit tests, behavioural fixtures and runtime validation records
AGENTS.md                      Cross-course engineering and ingestion rules
LICENSE                        GNU General Public License v3.0
```

`materials/` and `plan/` are deliberately excluded by `.gitignore`. The decks, derived extraction artifacts, course specification and planning documents stay on the machine that produced them.

## Pipeline

1. `scripts/extract_pptx.py` parses a deck into slide elements, notes, tables, equations, charts, assets and parser review flags, and renders the slides.
2. `scripts/ingest_course.py prepare <course-dir>` hashes the course inputs and the governing documents into a run context, then writes one review packet per slide plus a task plan under `materials/<course>/analysis/<run-id>/`.
3. A reviewer files one report per packet: element coverage, semantic units with verbatim evidence quotes, concept slugs, investigations for every parser flag, source issues, bounded arithmetic checks and an explicit visual-inspection scope.
4. `scripts/ingest_course.py finalize <run>` re-validates every report and writes `results/<analysis-hash>/validation.json` with a Markdown report.

The gate rejects stale identities, uncited semantic elements, quotes that do not appear in the extraction, unregistered references for `VERIFIED` claims, missing flag investigations and failed calculations. A slide is never reported as `reviewed-with-evidence` while it has unresolved findings or an unverified visual scope.

`scripts/INGESTION_WORKFLOW.md` describes the reviewer obligations in full.

## Current state

- Three decks are ingested. `Statistika-1` (72 slides) and `Statistika-2` (51 slides) cover data foundations, presentation, central tendency, dispersion, sample spaces, permutations and combinations. `Statistika-3` (53 slides, probability theory) was added in the latest run.
- Latest validation: 176 of 176 slides reviewed, 140 computations checked with zero failures, status `partial-validation`.
- The 123 slides of the first two decks were visually inspected against rendered images. The 53 slides of `Statistika-3` were reviewed from native extraction plus OCR of rendered slides and embedded assets, because the reviewing model could not accept image input; that deck therefore remains `partial-validation` on visual scope.
- One genuine source discrepancy is recorded: the reference book's worked example prints `5/56` where `(5/9)(4/8)(3/7) = 5/42 ≈ 11.9%`.
- The runtime package in `skills/statistics-probability/` still reflects the first two decks (769 evidence entries, manifest bound to that analysis). The probability-theory analysis exists but has not been promoted into skills.

## Usage

```bash
python scripts/extract_pptx.py materials/statistics-probability/Statistika-3.pptx
python scripts/ingest_course.py prepare materials/statistics-probability
python scripts/ingest_course.py packet <run-dir> <task-id>
python scripts/ingest_course.py finalize <run-dir>
python scripts/validate_skills.py
```

Python 3 standard library only; rendering uses LibreOffice or a DeckCraft MCP export.

## Tests

```bash
python -m unittest discover -s tests/statistics-probability -p "test_*.py"
```

The test directory name contains a hyphen, so it is not an importable package; point discovery at the directory itself rather than at `tests/`.

27 of 28 tests pass in the development environment. `test_extract_pptx.py::test_corrupt_input_exits_cleanly` fails only because the bundled LibreOffice Python reports `sys.executable` as a directory, so the subprocess cannot be spawned; it is an environment artifact, not a pipeline regression.

## License

GNU General Public License v3.0. See `LICENSE`.