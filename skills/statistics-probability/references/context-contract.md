# Shared context contract

The root creates one task context. Children receive only relevant fields and exact evidence, then return results to the root. No hidden context inheritance, circular delegation, or recursive sibling loading.

## Required context

- `objective`: requested calculation, explanation, comparison, or interpretation.
- `sources`: deck IDs and full SHA-256 revisions from sources.json; physical slide locators for lecture claims.
- For a dataset: `dataset_id`, `dataset_version`, `dataset_sha256` when file-backed, origin, observation unit, variable type, units, population/sample scope, row count, missing values, preprocessing, and actual values or a readable file path.
- For counting: outcomes/stages, allowed values, order relevance, replacement/repetition, distinctness, selection size, and all constraints. Finite sample spaces need not be equiprobable. Do not infer probabilities from counts without a model.
- `symbols`: meaning with task/slide scope; do not apply a glyph globally.
- `assumptions`, `rounding`, `prior_results` with provenance, and `unresolved` dependencies.

Retrieve or ask for critical absent fields. Do not invent scope, units, class boundaries, probabilities, or missing-data treatment. Fields irrelevant to a conceptual explanation may be explicitly marked not applicable. Do not demand a file hash for values typed directly in the conversation; use an explicit local identity/version and bind the exact values used.

## Handoff and merge

Each child returns: context/dataset identity and version, method, results, assumptions, evidence labels and locators, checks actually performed, and unresolved dependencies. Include units and population/sample scope for numeric results.

Before merging, compare identities and versions, actual input values, preprocessing, units, symbols, and assumptions. Different versions or conflicting scopes require reconciliation; recompute affected results. A child may report a prerequisite need to the root, which chooses whether to load another child. Never duplicate shared mutable datasets inside child instructions.

## Deterministic helper

`python scripts/compute.py <request.json>` from the package directory accepts explicit `describe` or `count` requests and prints JSON without writing data. For `describe`, supply `context` with `dataset_id`, `dataset_version`, `observation_unit`, `units`, `variable_type: quantitative`, and `scope: sample|population`, plus a nonempty finite numeric `values` array. It deliberately does not choose missing-data or quantile conventions. Sample variance with fewer than two observations is unavailable, not zero.

For `count`, supply integer `n`, `r`, and `model: ordered-distinct|unordered-distinct|ordered-replacement`. Full repeated-object arrangements require the explicit factorial formula and multiplicity checks in permutations. The helper does not decide which model fits a task.
