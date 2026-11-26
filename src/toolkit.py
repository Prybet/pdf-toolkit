"""PDF toolkit built on PyMuPDF, pdf2docx and Ghostscript"""

import argparse
import sys
from pathlib import Path
import shutil
import subprocess
from contextlib import closing
from io import BytesIO

import pymupdf

LEVELS = {"extreme": (72, 40), "recommended": (150, 60), "low": (300, 85)}
PROFILES = {"extreme": "/screen", "recommended": "/ebook", "low": "/printer"}


def opened(data):
    return pymupdf.open(stream=data, filetype="pdf")


def dump(doc):
    return doc.tobytes(garbage=4, deflate=True)


def merge(files):
    with pymupdf.open() as result:
        for data in files:
            with opened(data) as source:
                result.insert_pdf(source)
        return dump(result)


def split(data, first, last):
    with opened(data) as doc:
        if not 1 <= first <= last <= doc.page_count:
            raise ValueError(f"range {first}-{last} is outside 1-{doc.page_count}")
        doc.select(range(first - 1, last))
        return dump(doc)


def pack(images):
    with pymupdf.open() as doc:
        for data in images:
            pix = pymupdf.Pixmap(data)
            page = doc.new_page(width=pix.width, height=pix.height)
            page.insert_image(page.rect, stream=data)
        return dump(doc)


def render(data, dpi, fmt):
    with opened(data) as doc:
        return {f"p{page.number + 1:03d}.{fmt}": page.get_pixmap(dpi=dpi).tobytes(fmt) for page in doc}


def rgb(pix):
    return pymupdf.Pixmap(pymupdf.csRGB, pix) if pix.colorspace.n > 3 else pix


def picture(doc, xref, mask):
    if not mask:
        info = doc.extract_image(xref)
        return info["ext"], info["image"]
    base = rgb(pymupdf.Pixmap(doc, xref))
    return "png", pymupdf.Pixmap(base, pymupdf.Pixmap(doc, mask)).tobytes("png")


def extract(data, minimum):
    found = {}
    seen = set()
    with opened(data) as doc:
        for number, page in enumerate(doc, 1):
            for item in page.get_images(full=True):
                xref, mask, width, height = item[:4]
                if xref in seen or min(width, height) < minimum:
                    continue
                seen.add(xref)
                ext, content = picture(doc, xref, mask)
                found[f"p{number:03d}-{xref}.{ext}"] = content
    return found


def pages(spec, count):
    result = []
    for part in spec.split(","):
        first, _, last = part.partition("-")
        start, stop = int(first), int(last or first)
        step = 1 if stop >= start else -1
        result.extend(range(start, stop + step, step))
    if not all(1 <= number <= count for number in result):
        raise ValueError(f"pages must be within 1-{count}")
    return result


def rotate(data, degrees, spec):
    with opened(data) as doc:
        for number in pages(spec or f"1-{doc.page_count}", doc.page_count):
            page = doc[number - 1]
            page.set_rotation((page.rotation + degrees) % 360)
        return dump(doc)


def reorder(data, spec):
    with opened(data) as doc:
        doc.select([number - 1 for number in pages(spec, doc.page_count)])
        return dump(doc)


def mupdf(data, level):
    dpi, quality = LEVELS[level]
    with opened(data) as doc:
        doc.rewrite_images(dpi_threshold=dpi + dpi // 2, dpi_target=dpi, quality=quality)
        doc.subset_fonts()
        return dump(doc)


def ghost(data, level):
    if not shutil.which("gs"):
        raise ValueError("Ghostscript (gs) is not installed")
    result = subprocess.run(
        [
            "gs", "-sDEVICE=pdfwrite", f"-dPDFSETTINGS={PROFILES[level]}",
            "-dNOPAUSE", "-dBATCH", "-dQUIET", "-sOutputFile=-", "-",
        ],
        input=data,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode().strip() or "Ghostscript failed")
    return result.stdout


ENGINES = {"mupdf": mupdf, "ghost": ghost}


def shrink(data, level, engine):
    return min(ENGINES[engine](data, level), data, key=len)


def word(data):
    from pdf2docx import Converter

    out = BytesIO()
    with closing(Converter(stream=data)) as converter:
        converter.convert(out)
    return out.getvalue()


def read(path):
    return path.read_bytes()


def write(path, data):
    path.write_bytes(data)
    print(f"{path} ({len(data)} bytes)", file=sys.stderr)


def save(folder, files):
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (folder / name).write_bytes(content)
    print(f"{len(files)} files -> {folder}", file=sys.stderr)


COMMANDS = {
    "merge": lambda a: write(a.output, merge([read(p) for p in a.inputs])),
    "split": lambda a: write(a.output, split(read(a.input), a.first, a.last)),
    "pack": lambda a: write(a.output, pack([read(p) for p in a.inputs])),
    "shrink": lambda a: write(a.output, shrink(read(a.input), a.level, a.engine)),
    "render": lambda a: save(a.folder, render(read(a.input), a.dpi, a.format)),
    "extract": lambda a: save(a.folder, extract(read(a.input), a.min)),
    "rotate": lambda a: write(a.output, rotate(read(a.input), a.degrees, a.pages)),
    "reorder": lambda a: write(a.output, reorder(read(a.input), a.order)),
    "word": lambda a: write(a.output, word(read(a.input))),
}


def build():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    join = commands.add_parser("merge", help="merge PDFs in the given order")
    join.add_argument("output", type=Path)
    join.add_argument("inputs", type=Path, nargs="+")

    cut = commands.add_parser("split", help="keep a page range (1-based, inclusive)")
    cut.add_argument("input", type=Path)
    cut.add_argument("output", type=Path)
    cut.add_argument("first", type=int)
    cut.add_argument("last", type=int)

    gather = commands.add_parser("pack", help="build a PDF from images, one per page")
    gather.add_argument("output", type=Path)
    gather.add_argument("inputs", type=Path, nargs="+")

    small = commands.add_parser("shrink", help="reduce file size")
    small.add_argument("input", type=Path)
    small.add_argument("output", type=Path)
    small.add_argument("-l", "--level", choices=LEVELS, default="recommended")
    small.add_argument("-e", "--engine", choices=ENGINES, default="mupdf")

    draw = commands.add_parser("render", help="render every page to an image")
    draw.add_argument("input", type=Path)
    draw.add_argument("folder", type=Path)
    draw.add_argument("-d", "--dpi", type=int, default=150)
    draw.add_argument("-f", "--format", choices=["png", "jpg"], default="png")

    pull = commands.add_parser("extract", help="extract embedded images without recompressing")
    pull.add_argument("input", type=Path)
    pull.add_argument("folder", type=Path)
    pull.add_argument("-m", "--min", type=int, default=0, help="skip images whose smallest side is below this many pixels")

    turn = commands.add_parser("rotate", help="rotate pages clockwise")
    turn.add_argument("input", type=Path)
    turn.add_argument("output", type=Path)
    turn.add_argument("degrees", type=int, choices=[90, 180, 270])
    turn.add_argument("-p", "--pages", help='pages to rotate, e.g. "1,3-5" (default: all)')

    order = commands.add_parser("reorder", help="set a new page order")
    order.add_argument("input", type=Path)
    order.add_argument("output", type=Path)
    order.add_argument("order", help='new order, e.g. "3,1,2-4"; omitted pages are dropped')

    docx = commands.add_parser("word", help="convert a PDF to an editable Word document")
    docx.add_argument("input", type=Path)
    docx.add_argument("output", type=Path)
    return parser


def main():
    args = build().parse_args()
    try:
        COMMANDS[args.command](args)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())