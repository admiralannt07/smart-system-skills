"""Prepare resumable AI ingestion tasks and check their evidence before delivery."""

import argparse
import ast
from collections import Counter
import json
import math
import operator
from pathlib import Path
import re
import statistics
import sys

from extract_pptx import digest, extract


ROOT = Path(__file__).resolve().parents[1]
TYPES = {"declarative", "procedural", "formula", "worked-example", "exercise", "instructor-convention", "caveat"}
DISPOSITIONS = {"resolved-supported", "resolved-source-discrepancy", "unresolved"}
FUNCTIONS = {name: getattr(statistics, name) for name in ["mean", "median", "multimode", "variance", "pvariance", "stdev", "pstdev"]}
FUNCTIONS.update({name: getattr(math, name) for name in ["sqrt", "factorial", "perm", "comb"]})
FUNCTIONS.update(sum=sum, min=min, max=max, abs=abs, len=len, round=round)
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
             ast.Pow: operator.pow}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def save(path, value):
    path = Path(path)
    payload = encoded(value)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Refusing to replace an existing artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def inside(base, relative):
    base = Path(base).resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"Path escapes evidence directory: {relative}")
    return path


def calculate(expression):
    """Bounded arithmetic interpreter. Never eval or execute model/source code."""
    if not isinstance(expression, str) or len(expression) > 4000:
        raise ValueError("Calculation expression is missing or too large")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 1000:
        raise ValueError("Calculation has too many terms")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            value = node.value
        elif isinstance(node, (ast.List, ast.Tuple)):
            return [visit(child) for child in node.elts]
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                raise ValueError("Arithmetic operands must be numbers")
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent exceeds calculation limit")
            value = OPERATORS[type(node.op)](left, right)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS and not node.keywords:
            args = [visit(arg) for arg in node.args]
            if node.func.id in {"factorial", "perm", "comb"} and any(not isinstance(a, int) or not 0 <= a <= 1000 for a in args):
                raise ValueError("Combinatorial input exceeds calculation limit")
            value = FUNCTIONS[node.func.id](*args)
        else:
            raise ValueError("Only numeric literals, lists, arithmetic, and approved functions are allowed")
        values = value if isinstance(value, list) else [value]
        if any(type(v) not in {int, float} or abs(v) > 10**100 or not math.isfinite(v) for v in values):
            raise ValueError("Calculation result exceeds numeric limits")
        return value

    return visit(tree.body)


def section(spec, title):
    text = spec.split(title, 1)[1]
    return text.split("\n## ", 1)[0].strip()


def prepare(course_dir):
    course_dir = Path(course_dir).resolve()
    sources = sorted(course_dir.glob("*.pptx"))
    if not sources:
        raise ValueError(f"No PPTX files found: {course_dir}")
    spec_path = ROOT / "plan" / course_dir.name / "SPEC.md"
    spec = spec_path.read_text(encoding="utf-8")
    policy = (ROOT / "AGENTS.md").read_bytes()
    guide = (ROOT / "scripts/INGESTION_WORKFLOW.md").read_bytes()
    context = {"course": course_dir.name, "objective": "Source-faithful course ingestion and evidence-based validation; no runtime skill publication.",
               "spec_path": str(spec_path), "spec_sha256": digest(spec_path.read_bytes()),
               "policy_sha256": digest(policy), "workflow_sha256": digest(guide),
               "controller_sha256": digest(Path(__file__).read_bytes()),
               "notation": section(spec, "## 8. Global Conventions and Mathematical Notation Protocol"),
               "baseline": section(spec, "## 2. Observed Lecture Baseline"),
               "context_contract": section(spec, "### Nesting and context contract"),
               "dataset": None, "dataset_scope": "No user dataset; preserve each lecture example's units, scope, and hypothetical status."}
    context_hash = digest(encoded(context))
    decks = []
    seen = {}
    for source in sources:
        source_hash = digest(source.read_bytes())
        if source_hash in seen:
            seen[source_hash]["aliases"].append(source.name)
            continue
        parsed, _ = extract(source)
        data = load(parsed / "content.json")
        record = {"source_id": data["source_id"], "source_path": str(source), "source_sha256": source_hash,
                  "parsed_path": str(parsed), "manifest_sha256": digest((parsed / "manifest.json").read_bytes()),
                  "aliases": [], "slide_count": data["slide_count"],
                  "slides": [{"slide_index": s["slide_index"], "sha256": s["sha256"]} for s in data["slides"]]}
        decks.append(record)
        seen[source_hash] = record
    run_hash = digest(encoded({"context": context_hash, "decks": decks}))
    run = course_dir / "analysis" / run_hash[:20]
    save(run / "context.json", context)
    catalog = []
    for deck in decks:
        data = load(Path(deck["parsed_path"]) / "content.json")
        for slide in data["slides"]:
            task_id = deck["source_sha256"][:16] + f"-s{slide['slide_index']:03}"
            elements = []
            for element in slide["elements"]:
                elements.append({k: v for k, v in element.items() if k != "original_xml"})
            packet = {"task_id": task_id, "context_sha256": context_hash, "source_id": deck["source_id"],
                      "source_sha256": deck["source_sha256"], "parsed_path": deck["parsed_path"],
                      "slide_index": slide["slide_index"], "slide_sha256": slide["sha256"],
                      "elements": elements, "notes": slide["notes"], "assets": slide["assets"],
                      "review_flags": slide["review_flags"]}
            save(run / "packets" / f"{task_id}.json", packet)
            title = next((p.strip() for e in elements for p in e["paragraphs"] if p.strip()), "[No native title]")
            catalog.append({"task_id": task_id, "source_id": deck["source_id"], "slide_index": slide["slide_index"], "title": title})
    save(run / "plan.json", {"run_id": run.name, "context_sha256": context_hash, "decks": decks, "catalog": catalog,
                             "packet_sha256": {p.name: digest(p.read_bytes()) for p in sorted((run / "packets").glob("*.json"))}})
    return run


def verify_run(run):
    run = Path(run)
    plan = load(run / "plan.json")
    context = load(run / "context.json")
    if digest(encoded(context)) != plan["context_sha256"]:
        raise ValueError("Shared context was modified")
    if digest(Path(context["spec_path"]).read_bytes()) != context["spec_sha256"] or digest((ROOT / "AGENTS.md").read_bytes()) != context["policy_sha256"]:
        raise ValueError("Course context is stale; prepare a new run")
    if digest((ROOT / "scripts/INGESTION_WORKFLOW.md").read_bytes()) != context["workflow_sha256"] or digest(Path(__file__).read_bytes()) != context["controller_sha256"]:
        raise ValueError("Workflow changed; prepare a new run")
    for deck in plan["decks"]:
        if digest(Path(deck["source_path"]).read_bytes()) != deck["source_sha256"]:
            raise ValueError("Source changed; prepare a new run")
        parsed = Path(deck["parsed_path"])
        if digest((parsed / "manifest.json").read_bytes()) != deck["manifest_sha256"]:
            raise ValueError("Extraction manifest changed")
        for name, expected in load(parsed / "manifest.json")["artifact_sha256"].items():
            if digest(inside(parsed, name).read_bytes()) != expected:
                raise ValueError(f"Extraction artifact changed: {name}")
    for name, expected in plan["packet_sha256"].items():
        if digest(inside(run / "packets", name).read_bytes()) != expected:
            raise ValueError(f"Task packet changed: {name}")
    return plan, context


def task_packet(run, task_id):
    plan, context = verify_run(run)
    packet = load(inside(Path(run) / "packets", task_id + ".json"))
    if packet["context_sha256"] != plan["context_sha256"]:
        raise ValueError("Task and shared context disagree")
    catalog = plan["catalog"]
    position = next(i for i, c in enumerate(catalog) if c["task_id"] == task_id)
    neighbors = []
    for neighbor in catalog[max(0, position - 1):position + 2]:
        if neighbor["task_id"] != task_id and neighbor["source_id"] == packet["source_id"]:
            neighbors.append(load(Path(run) / "packets" / (neighbor["task_id"] + ".json")))
    return {"context": context, "task": packet, "neighbors": neighbors,
            "course_catalog": catalog, "instructions_path": str(ROOT / "scripts/INGESTION_WORKFLOW.md")}


def element_text(element):
    parts = element["paragraphs"] + [q["structural_text"] for q in element["equations"]]
    for key in ["tables", "charts"]:
        if element[key]:
            parts.append(json.dumps(element[key], ensure_ascii=False))
    return "\n".join(parts)


def validate_report(packet, report, references):
    """Check auditable evidence and computations, not the truth of free-form AI prose."""
    for key in ["task_id", "context_sha256", "source_sha256", "slide_sha256"]:
        if report.get(key) != packet[key]:
            raise ValueError(f"Missing or stale report identity: {key}")
    elements = {e["locator"]: e for e in packet["elements"]}
    coverage = report.get("coverage", {})
    if set(coverage) != set(elements) or any(v not in {"semantic", "decorative", "unresolved"} for v in coverage.values()):
        raise ValueError("Every source element needs an explicit coverage disposition")
    units = report.get("units", [])
    covered = set()
    for unit in units:
        if unit.get("type") not in TYPES or not unit.get("statement") or unit.get("evidence_label") not in {"LECTURE", "VERIFIED", "INFERENCE", "EXTENSION", "UNRESOLVED"}:
            raise ValueError("Invalid semantic unit")
        if not unit.get("concepts") or any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", c) for c in unit["concepts"]):
            raise ValueError("Concepts must use shallow canonical slugs")
        if not unit.get("evidence"):
            raise ValueError("Semantic unit has no source evidence")
        for evidence in unit["evidence"]:
            locator = evidence.get("locator")
            if locator not in elements:
                raise ValueError("Unknown source locator")
            text = element_text(elements[locator])
            if not evidence.get("quote") or evidence["quote"] not in text:
                raise ValueError("Source quote does not match the extraction")
            covered.add(locator)
        refs = unit.get("references", [])
        if any(r not in references for r in refs) or (unit["evidence_label"] == "VERIFIED" and not refs):
            raise ValueError("Verified claims require registered independent references")
    if any(v == "semantic" and k not in covered for k, v in coverage.items()):
        raise ValueError("A semantic element has no cited unit")
    investigations = report.get("investigations", [])
    if {x.get("flag") for x in investigations} != set(packet["review_flags"]):
        raise ValueError("Every parser flag needs an AI investigation")
    for investigation in investigations:
        if investigation.get("disposition") not in DISPOSITIONS or not investigation.get("reason"):
            raise ValueError("Investigation needs a disposition and supporting reason")
    for issue in report.get("issues", []):
        if issue.get("disposition") not in DISPOSITIONS or not issue.get("original") or not issue.get("interpretation"):
            raise ValueError("Issue is missing its source or interpretation")
        if not issue.get("locators") or any(p not in elements for p in issue["locators"]):
            raise ValueError("Issue needs real source locators")
        if issue["original"] not in "\n".join(element_text(elements[p]) for p in issue["locators"]):
            raise ValueError("Issue source quote does not match")
        if issue["disposition"] != "unresolved" and (not issue.get("references") or any(r not in references for r in issue["references"])):
            raise ValueError("Resolved issues require independent supporting evidence")
    visual = report.get("visual", {})
    mode = visual.get("mode")
    if mode not in {"slide-inspected", "regions-inspected", "unavailable"} or not visual.get("reason"):
        raise ValueError("Visual inspection scope must be explicit")
    if mode == "regions-inspected":
        available = {a["path"] for a in packet["assets"]}
        if not visual.get("assets") or not set(visual["assets"]).issubset(available):
            raise ValueError("Region inspection needs real exported assets")
    if mode == "slide-inspected":
        render = visual.get("render", {})
        image = inside(Path(packet["parsed_path"]), render.get("path", ""))
        if not image.is_file() or image.suffix.lower() not in {".png", ".jpg", ".jpeg"} or digest(image.read_bytes()) != render.get("sha256"):
            raise ValueError("Slide inspection needs a hashed rendered image")
    if not report.get("summary") or not isinstance(report.get("limitations"), list):
        raise ValueError("Review needs a summary and explicit limitations")
    computations = []
    for check in report.get("checks", []):
        if not check.get("description") or not check.get("locators") or any(p not in elements for p in check["locators"]):
            raise ValueError("Computation needs a description and source locators")
        actual = calculate(check["expression"])
        expected = check["expected"]
        tolerance = check.get("abs_tol", 1e-9)
        if type(tolerance) not in {int, float} or not 0 <= tolerance <= 0.5:
            raise ValueError("Invalid computation tolerance")
        passed = actual == expected if isinstance(actual, list) else type(expected) in {int, float} and math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance)
        computations.append({**check, "actual": actual, "passed": passed})
    return computations


def finalize(run):
    run = Path(run)
    plan, _ = verify_run(run)
    analysis = load(run / "analysis.json")
    references = analysis.get("references", {})
    for key, ref in references.items():
        if not key or not all(ref.get(k) for k in ["url", "title", "locator", "support", "retrieved_at", "retrieval_method"]):
            raise ValueError("Independent reference record is incomplete")
        if not ref["url"].startswith("https://"):
            raise ValueError("Independent references need HTTPS provenance")
    reports = analysis.get("reports", [])
    ids = [r.get("task_id") for r in reports]
    expected_ids = {c["task_id"] for c in plan["catalog"]}
    if len(ids) != len(set(ids)) or not set(ids).issubset(expected_ids):
        raise ValueError("Duplicate or unknown review task")
    results, concepts, issues = [], {}, []
    for report in reports:
        packet = load(run / "packets" / (report["task_id"] + ".json"))
        checks = validate_report(packet, report, references)
        unresolved = any(x["disposition"] == "unresolved" for x in report["investigations"] + report.get("issues", []))
        unresolved |= any(u["evidence_label"] == "UNRESOLVED" for u in report["units"])
        failed = any(not c["passed"] for c in checks)
        status = "checks-failed" if failed else "partial-validation" if unresolved or report["visual"]["mode"] != "slide-inspected" or report["limitations"] else "reviewed-with-evidence"
        results.append({"task_id": report["task_id"], "source_id": packet["source_id"], "slide_index": packet["slide_index"],
                        "status": status, "summary": report["summary"], "checks": checks, "visual": report["visual"]})
        for unit in report["units"]:
            for concept in unit["concepts"]:
                concepts.setdefault(concept, []).append({"task_id": report["task_id"], "type": unit["type"], "evidence_label": unit["evidence_label"], "statement": unit["statement"]})
        issues.extend({"task_id": report["task_id"], **issue} for issue in report.get("issues", []))
    relationships = analysis.get("relationships", [])
    graph = {c: set() for c in concepts}
    for relation in relationships:
        a, b = relation.get("from"), relation.get("to")
        if a not in concepts or b not in concepts or a == b or relation.get("evidence_label") not in {"LECTURE", "INFERENCE"} or not relation.get("reason"):
            raise ValueError("Invalid concept relationship")
        if not relation.get("tasks") or not set(relation["tasks"]).issubset(set(ids)):
            raise ValueError("Concept relationship needs reviewed source tasks")
        if relation.get("kind") == "prerequisite":
            graph[a].add(b)
        elif relation.get("kind") != "related":
            raise ValueError("Unknown relationship kind")
    active, done = set(), set()
    def visit(concept):
        if concept in active:
            raise ValueError("Circular concept prerequisites")
        if concept in done:
            return
        active.add(concept)
        for child in graph[concept]:
            visit(child)
        active.remove(concept)
        done.add(concept)
    for concept in graph:
        visit(concept)
    missing = sorted(expected_ids - set(ids))
    failed = sum(r["status"] == "checks-failed" for r in results)
    partial = sum(r["status"] == "partial-validation" for r in results)
    result = {"run_id": plan["run_id"], "analysis_sha256": digest((run / "analysis.json").read_bytes()),
              "status": "checks-failed" if failed else "incomplete" if missing else "partial-validation" if partial else "reviewed-with-evidence",
              "total_slides": len(expected_ids), "reviewed_slides": len(results), "missing_tasks": missing,
              "computation_count": sum(len(r["checks"]) for r in results), "failed_slides": failed,
              "visual_modes": dict(Counter(r["visual"]["mode"] for r in results)),
              "results": results, "issues": issues, "concepts": concepts, "relationships": relationships,
              "limitations": ["Evidence gates check identities, source quotes, coverage, bounded calculations, and concept dependencies.",
                              "The AI remains responsible for actual visual inspection, reference retrieval, and whether cited evidence supports its interpretation.",
                              "Reviewed source content is not automatically a validated or published runtime skill."]}
    revision = run / "results" / result["analysis_sha256"][:16]
    save(revision / "validation.json", result)
    lines = ["# AI ingestion validation", "", f"Status: **{result['status']}**", "",
             f"Reviewed: {len(results)}/{len(expected_ids)} slides. Calculations: {result['computation_count']}. Failed slides: {failed}.", "",
             "## Source issues", ""]
    for issue in issues:
        lines.extend([f"### {issue['task_id']}: {issue['disposition']}", "", f"Source: {issue['original']}", "", issue["interpretation"], ""])
        lines.extend(f"- [{references[r]['title']}]({references[r]['url']}) ({references[r]['locator']})" for r in issue.get("references", []))
        lines.append("")
    lines.extend(["## Slide results", "", "| Source | Slide | Status | Summary |", "| --- | ---: | --- | --- |"])
    for r in results:
        summary = r['summary'].replace('|', '\\|').replace('\n', ' ')
        lines.append(f"| {r['source_id']} | {r['slide_index']} | {r['status']} | {summary} |")
    lines.extend(["", "## Limits", "", *[f"- {limit}" for limit in result["limitations"]], ""])
    path = revision / "report.md"
    content = "\n".join(lines).encode("utf-8")
    if path.exists() and path.read_bytes() != content:
        raise ValueError("Refusing to replace an existing report")
    path.write_bytes(content)
    return revision, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare").add_argument("course", type=Path)
    packet = commands.add_parser("packet")
    packet.add_argument("run", type=Path)
    packet.add_argument("task_id")
    commands.add_parser("finalize").add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            print(prepare(args.course))
        elif args.command == "packet":
            print(json.dumps(task_packet(args.run, args.task_id), ensure_ascii=False, indent=2))
        else:
            path, result = finalize(args.run)
            print(f"{result['status']}: {result['reviewed_slides']}/{result['total_slides']} slides; {result['computation_count']} computations; {path}")
            if result["status"] in {"incomplete", "checks-failed"}:
                return 1
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, ArithmeticError) as error:
        parser.exit(1, f"Ingestion failed: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
