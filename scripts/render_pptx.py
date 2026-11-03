"""Render each slide using LibreOffice's bundled Python and local UNO bridge."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


def render(sources, output):
    soffice = Path(uno.__file__).parent / "soffice.com"
    if not soffice.is_file():
        raise ValueError("Run this script using LibreOffice/program/python.exe")
    pipe = "course_render_" + uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="course-lo-render-") as profile:
        process = subprocess.Popen([
            str(soffice), "-env:UserInstallation=" + Path(profile).as_uri(), "--headless",
            "--norestore", "--nodefault", "--nofirststartwizard",
            f"--accept=pipe,name={pipe};urp;StarOffice.ComponentContext",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        desktop = None
        try:
            local = uno.getComponentContext()
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            deadline = time.monotonic() + 30
            while True:
                try:
                    context = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
                    break
                except Exception:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("LibreOffice failed to start its isolated rendering bridge")
                    time.sleep(0.2)
            service = context.ServiceManager
            desktop = service.createInstanceWithContext("com.sun.star.frame.Desktop", context)
            for source in sources:
                before = source.read_bytes()
                source_hash = sha256(before).hexdigest()
                with ZipFile(source) as archive:
                    expected = len(ET.fromstring(archive.read("ppt/presentation.xml")).findall(
                        "{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst/"
                        "{http://schemas.openxmlformats.org/presentationml/2006/main}sldId"))
                target = output / source.stem / source_hash[:16]
                if target.exists():
                    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
                    if manifest["source_sha256"] != source_hash or len(manifest["images"]) != expected:
                        raise ValueError(f"Existing render does not match source: {target}")
                    for name, checksum in manifest["images"].items():
                        if Path(name).name != name or sha256((target / name).read_bytes()).hexdigest() != checksum:
                            raise ValueError(f"Existing render was modified: {target}")
                    print(f"UNCHANGED {source.name}: {expected} slides; {target}", flush=True)
                    continue
                document = desktop.loadComponentFromURL(source.resolve().as_uri(), "_blank", 0, (
                    prop("Hidden", True), prop("ReadOnly", True),
                    prop("MacroExecutionMode", uno.getConstantByName("com.sun.star.document.MacroExecMode.NEVER_EXECUTE")),
                    prop("UpdateDocMode", uno.getConstantByName("com.sun.star.document.UpdateDocMode.NO_UPDATE")),
                ))
                if document is None:
                    raise RuntimeError(f"Cannot open {source}")
                try:
                    pages = document.getDrawPages()
                    if pages.getCount() != expected:
                        raise ValueError(f"Slide count mismatch: {source}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.TemporaryDirectory(prefix=".render-", dir=target.parent) as staging:
                        staging = Path(staging)
                        images = {}
                        for index in range(expected):
                            page = pages.getByIndex(index)
                            exporter = service.createInstanceWithContext("com.sun.star.drawing.GraphicExportFilter", context)
                            exporter.setSourceDocument(page)
                            image = staging / f"slide-{index + 1:03}.png"
                            if not exporter.filter((prop("URL", image.as_uri()), prop("MediaType", "image/png"),
                                                    prop("FilterData", uno.Any("[]com.sun.star.beans.PropertyValue", (
                                                        prop("PixelWidth", 1600), prop("PixelHeight", round(1600 * page.Height / page.Width)),
                                                    ))))):
                                raise RuntimeError(f"Cannot export slide {index + 1}: {source}")
                            payload = image.read_bytes()
                            if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                                raise ValueError(f"Invalid PNG: {image}")
                            images[image.name] = sha256(payload).hexdigest()
                        if source.read_bytes() != before:
                            raise ValueError(f"Source changed during rendering: {source}")
                        manifest = {"source_file": source.name, "source_sha256": source_hash, "slide_count": expected,
                                    "renderer": "LibreOffice UNO GraphicExportFilter", "pixel_width": 1600,
                                    "status": "rendered-not-visually-validated", "images": images}
                        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                        staging.rename(target)
                    print(f"RENDERED {source.name}: {expected} slides; {target}", flush=True)
                finally:
                    document.close(True)
        finally:
            if desktop is not None:
                desktop.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("course", type=Path)
    args = parser.parse_args()
    sources = sorted(args.course.glob("*.pptx"))
    if not sources:
        parser.error("No PPTX files found")
    render(sources, (args.course / "rendered/libreoffice/slides").resolve())
