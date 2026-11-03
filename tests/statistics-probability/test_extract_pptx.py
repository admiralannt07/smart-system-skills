"""Synthetic PPTX fixtures, not lecturer content or student datasets."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("extract_pptx", ROOT / "scripts/extract_pptx.py")
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)
NS = extractor.NS
DECL = " ".join(f'xmlns:{key}="{value}"' for key, value in NS.items())
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def rels(*entries):
    return f'<Relationships xmlns="{REL_NS}">' + "".join(
        f'<Relationship Id="{rid}" Type="{NS["r"]}/{kind}" Target="{target}"/>'
        for rid, kind, target in entries
    ) + '</Relationships>'


def shape(content, identity="2"):
    return f'<p:sp><p:nvSpPr><p:cNvPr id="{identity}" name="Synthetic"/></p:nvSpPr><p:txBody><a:p>{content}</a:p></p:txBody></p:sp>'


def slide(content):
    return f'<p:sld {DECL}><p:cSld><p:spTree>{content}</p:spTree></p:cSld></p:sld>'


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "synthetic.pptx"

    def make_deck(self, content, slide_relationships=None, extra=None):
        parts = {
            "ppt/presentation.xml": f'<p:presentation {DECL}><p:sldIdLst><p:sldId id="256" r:id="first"/></p:sldIdLst></p:presentation>',
            "ppt/_rels/presentation.xml.rels": rels(("first", "slide", "slides/slide9.xml")),
            "ppt/slides/slide9.xml": slide(content),
        }
        if slide_relationships:
            parts["ppt/slides/_rels/slide9.xml.rels"] = slide_relationships
        parts.update(extra or {})
        with ZipFile(self.source, "w") as archive:
            for part, payload in parts.items():
                archive.writestr(part, payload)

    def run_extract(self):
        target, created = extractor.extract(self.source)
        result = json.loads((target / "content.json").read_text(encoding="utf-8"))
        return target, created, result

    def test_equation_structure_fallback_and_unicode(self):
        math = '<m:oMath><m:f><m:num><m:r><m:t>𝑛</m:t></m:r></m:num><m:den><m:r><m:t>𝑁</m:t></m:r></m:den></m:f></m:oMath>'
        content = shape('<a:r><a:t>Sampel μ: </a:t></a:r><mc:AlternateContent><mc:Choice Requires="m">' + math + '</mc:Choice><mc:Fallback><a:r><a:t>DO NOT DUPLICATE</a:t></a:r></mc:Fallback></mc:AlternateContent>')
        self.make_deck(content)
        _, _, result = self.run_extract()
        element = result["slides"][0]["elements"][0]
        self.assertEqual(element["paragraphs"], ["Sampel μ: 𝑛𝑁"])
        self.assertEqual(element["equations"][0]["structural_text"], "(𝑛)/(𝑁)")
        self.assertIn("num", element["equations"][0]["original_xml"])
        self.assertIn("equation-structure-and-notation", result["slides"][0]["review_flags"])

    def test_physical_slide_order_comes_from_presentation(self):
        self.make_deck(shape('<a:r><a:t>First</a:t></a:r>'), extra={
            "ppt/presentation.xml": f'<p:presentation {DECL}><p:sldIdLst><p:sldId id="300" r:id="first"/><p:sldId id="256" r:id="second"/></p:sldIdLst></p:presentation>',
            "ppt/_rels/presentation.xml.rels": rels(("first", "slide", "slides/slide9.xml"), ("second", "slide", "slides/slide1.xml")),
            "ppt/slides/slide1.xml": slide(shape('<a:r><a:t>Second</a:t></a:r>')),
        })
        _, _, result = self.run_extract()
        self.assertEqual([s["part"] for s in result["slides"]], ["ppt/slides/slide9.xml", "ppt/slides/slide1.xml"])
        self.assertEqual([s["slide_index"] for s in result["slides"]], [1, 2])

    def test_image_only_is_unresolved_and_exported(self):
        self.make_deck('<p:pic><p:nvPicPr><p:cNvPr id="3" name="Image"/></p:nvPicPr><p:blipFill><a:blip r:embed="image"/></p:blipFill></p:pic>',
                       rels(("image", "image", "../media/image.png")), {"ppt/media/image.png": b"synthetic image bytes"})
        target, _, result = self.run_extract()
        first = result["slides"][0]
        self.assertIn("no-native-text", first["review_flags"])
        self.assertEqual(first["status"], "review-needed")
        self.assertEqual((target / first["assets"][0]["path"]).read_bytes(), b"synthetic image bytes")

    def test_table_chart_and_notes(self):
        cell = '<a:tc><a:txBody><a:p><a:r><a:t>12,5</a:t></a:r></a:p></a:txBody></a:tc>'
        table = '<p:graphicFrame><a:graphic><a:graphicData><a:tbl><a:tr>' + cell + cell + '</a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>'
        chart = '<p:graphicFrame><a:graphic><a:graphicData><c:chart r:id="chart"/></a:graphicData></a:graphic></p:graphicFrame>'
        note = f'<p:notes {DECL}><p:cSld><p:spTree>' + shape('<a:r><a:t>Lecturer note</a:t></a:r>') + '<p:sp><p:nvSpPr><p:nvPr><p:ph type="sldNum"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>99</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>'
        self.make_deck(table + chart, rels(("chart", "chart", "../charts/chart1.xml"), ("notes", "notesSlide", "../notesSlides/notesSlide1.xml")), {
            "ppt/charts/chart1.xml": f'<c:chartSpace {DECL}><c:chart><c:ser><c:val><c:numRef><c:numCache><c:pt idx="0"><c:v>12.5</c:v></c:pt></c:numCache></c:numRef></c:val></c:ser></c:chart></c:chartSpace>',
            "ppt/notesSlides/notesSlide1.xml": note,
        })
        _, _, result = self.run_extract()
        first = result["slides"][0]
        self.assertEqual(first["elements"][0]["tables"], [[[["12,5"], ["12,5"]]]])
        self.assertEqual(first["notes"], ["Lecturer note"])
        self.assertEqual(first["elements"][1]["charts"][0]["series"][0]["caches"][0]["points"], [{"index": "0", "value": "12.5"}])

    def test_repeat_import_and_tamper_protection_preserve_source(self):
        self.make_deck(shape('<a:r><a:t>Original</a:t></a:r>'))
        original = sha256(self.source.read_bytes()).hexdigest()
        target, created, _ = self.run_extract()
        self.assertTrue(created)
        modified = (target / "content.md").stat().st_mtime_ns
        self.assertFalse(self.run_extract()[1])
        self.assertEqual((target / "content.md").stat().st_mtime_ns, modified)
        self.assertEqual(sha256(self.source.read_bytes()).hexdigest(), original)
        (target / "content.md").write_text("Manual review", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            self.run_extract()

    def test_changed_source_retains_previous_version(self):
        self.make_deck(shape('<a:r><a:t>Original</a:t></a:r>'))
        previous, _, _ = self.run_extract()
        self.make_deck(shape('<a:r><a:t>Revision</a:t></a:r>'))
        current, _, _ = self.run_extract()
        self.assertNotEqual(previous, current)
        self.assertTrue((previous / "content.md").exists())

    def test_invalid_relationship_publishes_nothing(self):
        self.make_deck('', rels(("image", "image", "../../../outside.png")))
        with self.assertRaisesRegex(ValueError, "unsafe relationship"):
            self.run_extract()
        self.assertFalse((self.folder / "parsed").exists())

    def test_corrupt_input_exits_cleanly(self):
        self.source.write_bytes(b"not a PPTX")
        process = subprocess.run([sys.executable, str(ROOT / "scripts/extract_pptx.py"), str(self.source)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 1)
        self.assertIn("Extraction failed", process.stderr)
        self.assertNotIn("Traceback", process.stderr)
        self.assertFalse((self.folder / "parsed").exists())


if __name__ == "__main__":
    unittest.main()
