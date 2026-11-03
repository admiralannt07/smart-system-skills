# Initial runtime validation

Date: 2026-10-18. Authorization: user requested proceeding with skill creation and validating necessary unchecked aspects.

## Delivered

- [Course root](../../skills/statistics-probability/SKILL.md) and eight direct concept skills: data-foundations, data-presentation, central-tendency, data-dispersion, sample-space-events, counting-principles, permutations, combinations.
- Shared routing manifest, prerequisite map, explicit context contract, scoped notation, source caveats, two full source hashes, and eight focused evidence files preserving semantic classifications, source quotations, discrepancy interpretations, and limitations.
- Dependency-free runtime calculator for descriptive summaries with explicit dataset identity/scope and three elementary counting models. The agent still selects the model and handles other mathematics with deterministic Python checks.
- Package validator and 12 new runtime tests, alongside 16 existing extraction/controller tests.
- General course-root bootstrap in AGENTS.md; updated implementation status in SPEC.md and reproducible commands/host instructions in scripts/README.md.

## Actual checks

| Check | Observed result | Limit |
| --- | --- | --- |
| Automated suite | 28/28 pass | Deterministic code tests, not model accuracy |
| Package validation | 9 skill files, 2 exact source versions, 769 evidence entries pass | Controlled authored YAML frontmatter, not a general YAML parser |
| Metadata and references | Names match folders, descriptions bounded, local links exist | Native host metadata parser could not be exercised |
| Structure/context | Direct nesting and DAG validated; missing dataset identity, units, scope and invalid types rejected by calculator | Context merge decisions remain agent responsibilities |
| Source traceability | Packaged units, classifications, quotations and caveats match the hash-bound ingestion analysis | Ingestion retains its partial-validation status |
| Mathematics | Sample/population distinction; modes; edge cases; small ordered/unordered/replacement counts compared against enumeration | No unrestricted solver or probability model inferred |
| Behavioral self-checks | 20 scenarios recorded; quantitative examples checked by Python | Author-executed, not independent or blinded routing evaluation |
| Re-import current decks | Both reported UNCHANGED | No automatic semantic skill merge/publication implemented |
| Source integrity | Both deck SHA-256 hashes still match imported bytes | No source edits made |
| Bootstrap/file access | Root, routing index, shared references and all eight children read in this agent session | Hosts must support filesystem reads and either AGENTS.md or explicit bootstrap |

Commands actually run:

```powershell
python scripts/validate_skills.py
python -m unittest discover -s tests/statistics-probability -p "test_*.py" -v
python scripts/extract_pptx.py materials/statistics-probability
```

Machine evidence: [runtime-test-results.json](runtime-test-results.json), including actual test output and package file hashes; [behavioral-checks.json](behavioral-checks.json), including prompts, selected routes, observed decisions and calculation/enumeration checks. The behavioral record does not measure or claim the SPEC's 90% routing targets.

## Behavioral coverage

The active authoring agent checked sample mean plus SD, outlier-sensitive center, nominal codes, chart selection, four/eight-outcome spaces, locally indexed event labels, forbidden configurations, precedence orders, ordered roles versus unordered teams, full versus partial multiset arrangements, grouped interpolation, unspecified quartile algorithms, direct invocation with missing scope, dataset-version switching, conflicting N meanings, absent t-test coverage, source instruction injection, source formula corrections, and zero-SD standardization.

Examples independently recomputed by Python include mean 150/sample variance 5600 for D1:69; the D2:14 intersection {AOW}; 10 allowed configurations from a labeled synthetic 3x2x2 constrained space; 12 four-deployment orders with A before B; 12 full and 7 length-two distinct arrangements from synthetic AABC; and grouped median/mode estimates 16 under labeled synthetic equal-width interpolation assumptions. These computations check the mathematics, not the correctness of every teaching decision.

## Host compatibility

The installed CLI reports codex-cli 0.162.1. Its app-server JSON schema was inspected before attempting the metadata-only discovery probe. Initialization failed with `Could not find home directory`; process-local extra-root registration and skills/list could therefore not run. No model session was launched and no global configuration was changed.

[Official Codex documentation](https://learn.chatgpt.com/docs/build-skills) describes repository discovery under `.agents/skills`. This package is canonically under `skills/`, so native automatic registration is not established. The supported workspace path is AGENTS.md's course-root instruction or the explicit file-based bootstrap in scripts/README.md. This is not a claim that the skill appears in a native picker.

Skill Creator's quick_validate.py was attempted and failed because PyYAML is unavailable. The repository validator instead verifies the exact controlled frontmatter format authored here; all nine metadata headers use simple names and JSON-quoted descriptions, which are valid YAML scalars. No dependency was installed merely for this check.

## Remaining limits and release status

The files are usable through explicit filesystem bootstrap in a capable agent host. Native automatic discovery and independent routing accuracy are unverified; this is not a full release-gate pass across all target hosts. An independent evaluation needs actual permitted model execution with a held-out query set, rather than a fabricated accuracy score.

The source baseline remains 123 full LibreOffice slides inspected, 110 reviewed with evidence, 13 partial, and 88 passing ingestion calculations. Partial cases have bounded operational handling in source-notes.md. No PowerPoint rendering equivalence is claimed. The missing quantile/whisker conventions and other source ambiguities were retained rather than invented.

No durable cross-session dataset store, unattended AI ingestion service, or automatic semantic diff/skill publisher was added. Existing parser/controller tests protect source-version preservation; they do not prove future automated runtime merges. New or revised decks still require AI impact analysis and the ingestion workflow through its final report.

AGENTS.md and SPEC.md changed to document/bootstrap the newly authorized runtime milestone. The previous ingestion context remains an immutable record of its original policies. Its old context check may now reject current-policy mismatch; do not rewrite its historical hashes. Runtime provenance validation checks the preserved source, extraction and analysis bytes directly.

No routine slide-review tasks were assigned to the user. The remaining gaps concern runtime/evaluation capabilities and unresolved source conventions, with explicit abstention paths in the skills.
