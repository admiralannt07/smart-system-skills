"""Extract PPTX evidence using only the Python standard library, without executing it."""

import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import posixpath
import shutil
import tempfile
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
}


def tag(prefix, name):
    return f"{{{NS[prefix]}}}{name}"


def digest(data):
    return sha256(data).hexdigest()


def xml(element):
    return ET.tostring(element, encoding="unicode")


def relationships(archive, part):
    path = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")
    if path not in archive.namelist():
        return {}
    result = {}
    for node in ET.fromstring(archive.read(path)):
        info = dict(node.attrib)
        if info.get("TargetMode") != "External":
            target = info["Target"]
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
            if target.startswith("/"):
                resolved = posixpath.normpath(target.lstrip("/"))
            if resolved.startswith("../") or resolved not in archive.namelist():
                raise ValueError(f"Missing or unsafe relationship: {part}: {target}")
            info["part"] = resolved
        result[info["Id"]] = info
    return result


def selected(element):
    """Choose native Office content once; retain fallback bytes separately."""
    if element.tag == tag("mc", "AlternateContent"):
        choices = element.findall("mc:Choice", NS)
        preferred = next((c for c in choices if c.find(".//m:oMath", NS) is not None), None)
        branch = preferred if preferred is not None else (choices[0] if choices else element.find("mc:Fallback", NS))
        if branch is not None:
            yield from selected(branch)
        return
    yield element
    for child in element:
        yield from selected(child)


def source_text(element):
    return "".join(
        n.text or "" if n.tag in {tag("a", "t"), tag("m", "t")} else
        "\n" if n.tag == tag("a", "br") else "\t"
        for n in selected(element)
        if n.tag in {tag("a", "t"), tag("m", "t"), tag("a", "br"), tag("a", "tab")}
    )


def math_text(node):
    """Readable structural transcription, never a replacement for original OMML."""
    name = node.tag.split("}")[-1]
    def child(key):
        found = node.find("m:" + key, NS)
        return math_text(found) if found is not None else ""
    def prop(path, default):
        found = node.find(path, NS)
        return found.get(tag("m", "val"), default) if found is not None else default
    if name == "t":
        return node.text or ""
    if name.endswith("Pr"):
        return ""
    if name == "f":
        return f"({child('num')})/({child('den')})"
    if name in {"sSub", "sSup", "sSubSup"}:
        return child("e") + (f"_({child('sub')})" if name != "sSup" else "") + (f"^({child('sup')})" if name != "sSub" else "")
    if name == "nary":
        return prop("m:naryPr/m:chr", "∫") + f"_({child('sub')})^({child('sup')})({child('e')})"
    if name == "d":
        return prop("m:dPr/m:begChr", "(") + "|".join(math_text(e) for e in node.findall("m:e", NS)) + prop("m:dPr/m:endChr", ")")
    if name == "acc":
        return f"accent[{prop('m:accPr/m:chr', '̂')}]({child('e')})"
    if name == "rad":
        return f"root[{child('deg')}]({child('e')})"
    # shortcut: uncommon OMML constructs stay in XML, expand notation after visual review.
    return "".join(math_text(n) for n in node)


def paragraphs(element):
    return [source_text(n) for n in selected(element) if n.tag == tag("a", "p")]


def extract(source, output=None):
    source = Path(source)
    data = source.read_bytes()  # Immutable in-memory processing snapshot.
    source_hash = digest(data)
    parser_hash = digest(Path(__file__).read_bytes())
    output = Path(output) if output else source.parent / "parsed"
    target = output / source.stem / f"{source_hash[:16]}-{parser_hash[:12]}"
    if target.exists():
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        if manifest["source_sha256"] != source_hash or manifest["extractor_sha256"] != parser_hash:
            raise ValueError(f"Version collision: {target}")
        for path, expected in manifest["artifact_sha256"].items():
            if digest((target / path).read_bytes()) != expected:
                raise ValueError(f"Modified artifact, refusing to overwrite: {target / path}")
        return target, False

    artifacts = {}
    slides = []
    with ZipFile(BytesIO(data)) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        rels = relationships(archive, "ppt/presentation.xml")
        ids = presentation.find("p:sldIdLst", NS)
        if ids is None or not len(ids):
            raise ValueError("Presentation has no slides")
        media = {}
        # Keep package assets by content hash, never by untrusted ZIP paths.
        for part in archive.namelist():
            if part.startswith("ppt/media/") and not part.endswith("/"):
                payload = archive.read(part)
                suffix = Path(part).suffix.lower()
                if not suffix[1:].isalnum():
                    suffix = ".bin"
                local = f"assets/{digest(payload)}{suffix}"
                artifacts[local] = payload
                media[part] = local

        for index, slide_id in enumerate(ids, 1):
            part = rels[slide_id.get(tag("r", "id"))]["part"]
            raw = archive.read(part)
            root = ET.fromstring(raw)
            artifacts[f"source/slide-{index:03}.xml"] = raw
            slide_rels = relationships(archive, part)
            flags = set()
            elements = []
            tree = root.find("p:cSld/p:spTree", NS)
            if tree is None:
                raise ValueError(f"Missing shape tree: {part}")
            if any(n.tag == tag("p", "grpSp") for n in root.iter()):
                flags.add("group-transforms-and-reading-order")
            for order, shape in enumerate(n for n in selected(tree) if n.tag in {
                tag("p", "sp"), tag("p", "pic"), tag("p", "graphicFrame"), tag("p", "cxnSp"),
            }):
                props = shape.find(".//p:cNvPr", NS)
                shape_id = props.get("id") if props is not None else str(order)
                locator = f"slide:{index}/shape:{shape_id}"
                equations = [n for n in selected(shape) if n.tag == tag("m", "oMath")]
                tables = shape.findall(".//a:tbl", NS)
                charts = []
                for chart in shape.findall(".//c:chart", NS):
                    relation = slide_rels[chart.get(tag("r", "id"))]
                    if "part" not in relation:
                        flags.add("external-chart")
                        continue
                    chart_part = relation["part"]
                    chart_raw = archive.read(chart_part)
                    artifacts[f"source/chart-{digest(chart_raw)}.xml"] = chart_raw
                    chart_root = ET.fromstring(chart_raw)
                    series = []
                    for series_node in chart_root.findall(".//c:ser", NS):
                        series.append({"xml": xml(series_node), "caches": [
                            {"kind": n.tag.split("}")[-1], "xml": xml(n), "points": [
                                {"index": p.get("idx"), "value": p.findtext("c:v", default="", namespaces=NS)}
                                for p in n.findall("c:pt", NS)
                            ]} for n in series_node.iter()
                            if n.tag in {tag("c", "numCache"), tag("c", "strCache"), tag("c", "numLit"), tag("c", "strLit")}
                        ]})
                    charts.append({"part": chart_part, "series": series})
                    flags.add("chart-layout-and-cached-values")
                xfrm = shape.find(".//a:xfrm", NS)
                if xfrm is None:
                    xfrm = shape.find("p:xfrm", NS)
                elements.append({
                    "locator": locator, "name": props.get("name", "") if props is not None else "",
                    "kind": shape.tag.split("}")[-1], "source_order": order,
                    "coordinates_xml": xml(xfrm) if xfrm is not None else None,
                    "paragraphs": [] if tables else paragraphs(shape),
                    "tables": [[[paragraphs(cell) for cell in row.findall("a:tc", NS)] for row in table.findall("a:tr", NS)] for table in tables],
                    "equations": [{"original_xml": xml(n), "linear_text": source_text(n),
                                   "structural_text": math_text(n), "status": "UNRESOLVED"} for n in equations],
                    "charts": charts, "original_xml": xml(shape), "evidence": "LECTURE",
                })
                if equations:
                    flags.add("equation-structure-and-notation")
                if shape.tag == tag("p", "cxnSp"):
                    flags.add("diagram-connectors")
            notes = []
            related_assets = []
            for rid, rel in slide_rels.items():
                if "part" not in rel:
                    if rel["Type"].rsplit("/", 1)[-1] != "hyperlink":
                        flags.add("external-resource-not-fetched")
                    continue
                related = rel["part"]
                if related in media:
                    related_assets.append({"relationship_id": rid, "part": related, "path": media[related]})
                    flags.add("image-or-equation-fallback")
                if rel["Type"].endswith("/notesSlide"):
                    note_raw = archive.read(related)
                    artifacts[f"source/notes-{index:03}.xml"] = note_raw
                    note_root = ET.fromstring(note_raw)
                    for shape in note_root.findall(".//p:sp", NS):
                        placeholder = shape.find(".//p:ph", NS)
                        if placeholder is None or placeholder.get("type") not in {"sldNum", "hdr", "ftr", "dt", "sldImg"}:
                            notes.extend(paragraphs(shape))
                if rel["Type"].endswith("/slideLayout"):
                    # Inherited content may contain real teaching content, so retain and flag it.
                    artifacts[f"source/layout-{index:03}.xml"] = archive.read(related)
                    for layout_rel in relationships(archive, related).values():
                        if layout_rel["Type"].endswith("/slideMaster") and "part" in layout_rel:
                            artifacts[f"source/master-{index:03}.xml"] = archive.read(layout_rel["part"])
            text = "\n".join(p for e in elements for p in e["paragraphs"])
            if not text.strip():
                flags.add("no-native-text")
            if root.find(".//p:oleObj", NS) is not None:
                flags.add("embedded-object-not-interpreted")
            if root.find(".//a:graphicData", NS) is not None and not any(e["charts"] or e["tables"] for e in elements):
                flags.add("unsupported-graphic")
            slides.append({"slide_index": index, "presentation_slide_id": slide_id.get("id"),
                           "part": part, "sha256": digest(raw), "hidden": root.get("show") == "0",
                           "elements": elements, "notes": notes, "assets": related_assets,
                           "review_flags": sorted(flags), "status": "review-needed" if flags else "parsed"})

        result = {"source_id": source.stem, "source_file": source.name, "source_sha256": source_hash,
                  "source_version": source_hash, "slide_count": len(slides), "slides": slides}
        artifacts["content.json"] = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        lines = [f"# {source.name}", "", f"Source SHA-256: `{source_hash}`", "",
                 "Status: extracted, not mathematically or visually validated.", "",
                 "Text follows source shape order, which may differ from visual reading order.", ""]
        queue = ["# Visual review queue", "", "All slides require a layout/inherited-content check before semantic validation.", "",
                 "Open exported images or render the original slide. Reconcile with native text; do not guess unreadable content.", ""]
        for slide in slides:
            lines.extend([f"## Slide {slide['slide_index']}", "", f"LECTURE | `{source.stem}` | physical slide {slide['slide_index']}", ""])
            for e in slide["elements"]:
                lines.extend([f"### {e['locator']}", "", *e["paragraphs"], ""])
                for table in e["tables"]:
                    lines.extend(["Table rows (cells as JSON arrays):", "", "```json", json.dumps(table, ensure_ascii=False, indent=2), "```", ""])
                for equation in e["equations"]:
                    lines.extend([f"UNRESOLVED structural transcription: `{equation['structural_text']}`", ""])
                for chart in e["charts"]:
                    lines.extend(["Chart cached series (not independently recalculated):", "", "```json", json.dumps(chart["series"], ensure_ascii=False, indent=2), "```", ""])
            if slide["notes"]:
                lines.extend(["### Speaker notes", "", *slide["notes"], ""])
            if slide["review_flags"]:
                queue.extend([f"## Slide {slide['slide_index']}", "", "UNRESOLVED: " + ", ".join(slide["review_flags"]), ""])
                for asset in slide["assets"]:
                    link = f"[{asset['part']}]({asset['path']})"
                    queue.append(link)
                    lines.append(link)
                queue.append("")
                lines.append("")
        artifacts["content.md"] = ("\n".join(lines) + "\n").encode("utf-8")
        artifacts["review-queue.md"] = ("\n".join(queue) + "\n").encode("utf-8")
        manifest = {"source_id": source.stem, "source_file": source.name, "source_sha256": source_hash,
                    "source_size_bytes": len(data), "extractor_sha256": parser_hash,
                    "run_id": target.name, "slide_count": len(slides), "status": "parsed-not-validated",
                    "media_types": dict(Counter(Path(p).suffix.lower() for p in media)),
                    "slides_needing_visual_recovery": sum(bool(s["review_flags"]) for s in slides),
                    "limitations": ["No OCR or slide renderer is run; images need visual transcription.",
                                    "Reading order and layout/master inheritance require visual review.",
                                    "Chart caches may be stale; linked workbooks are not recalculated.",
                                    "No semantic classification, concept mapping, or mathematical validation."],
                    "artifact_sha256": {p: digest(b) for p, b in sorted(artifacts.items())}}
        artifacts["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".extract-", dir=target.parent))
    try:
        for relative, payload in artifacts.items():
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path, nargs="+", help="PPTX files or directories containing PPTX files")
    parser.add_argument("--output", type=Path, help="Output root (default: each source directory / parsed)")
    args = parser.parse_args()
    sources = []
    for path in args.sources:
        found = sorted(path.glob("*.pptx")) if path.is_dir() else [path]
        if not found:
            parser.error(f"No PPTX files found: {path}")
        sources.extend(found)
    for source in sources:
        try:
            target, created = extract(source, args.output)
        except (OSError, ValueError, KeyError, BadZipFile, ET.ParseError) as error:
            parser.exit(1, f"Extraction failed for {source}: {error}\n")
        print(f"{'EXTRACTED' if created else 'UNCHANGED'} {source.name}: {target}")


if __name__ == "__main__":
    main()
