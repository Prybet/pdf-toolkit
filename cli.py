"""Interactive launcher for the PDF toolkit. Drop files onto this script or run it directly."""

import os
import shlex
import sys
from pathlib import Path

HOME = Path(__file__).parent
sys.path.insert(0, str(HOME / "src"))

import toolkit  # noqa: E402


def ask(text, default=""):
    hint = f" [{default}]" * bool(default)
    return input(f"{text}{hint}: ").strip() or default


def choose(text, options, default):
    answer = ask(f"{text} ({'/'.join(options)})", default)
    if answer not in options:
        raise ValueError(f"invalid option: {answer}")
    return answer


def number(text, default=""):
    return int(ask(text, default))


def output(path, default, where, files, suffix=".pdf"):
    name = Path(ask("Output name", default)).name
    result = {"source": path.parent, "script": HOME}[where] / (name + suffix * (not name.lower().endswith(suffix)))
    if result.resolve() in [original.resolve() for original in files]:
        print("That name would overwrite an original file, pick another one")
        return output(path, default, where, files, suffix)
    if result.exists() and ask("Already exists, overwrite? y/n", "n").lower() != "y":
        return output(path, default, where, files, suffix)
    return result


def each(files, tag, where, action):
    for path in files:
        toolkit.write(output(path, f"{path.stem}_{tag}.pdf", where, files), action(toolkit.read(path)))


def merge(files, where):
    toolkit.write(output(files[0], "merged.pdf", where, files), toolkit.merge([toolkit.read(path) for path in files]))


def pack(files, where):
    toolkit.write(output(files[0], "images.pdf", where, files), toolkit.pack([toolkit.read(path) for path in files]))


def split(files, where):
    first = number("First page")
    last = number("Last page")
    each(files, f"{first}-{last}", where, lambda data: toolkit.split(data, first, last))


def shrink(files, where):
    level = choose("Level", toolkit.LEVELS, "recommended")
    engine = choose("Engine", toolkit.ENGINES, "mupdf")
    each(files, "compressed", where, lambda data: toolkit.shrink(data, level, engine))


def rotate(files, where):
    degrees = int(choose("Degrees", ["90", "180", "270"], "90"))
    spec = ask("Pages, e.g. 1,3-5 (empty = all)")
    each(files, "rotated", where, lambda data: toolkit.rotate(data, degrees, spec))


def reorder(files, where):
    order = ask("New order, e.g. 3,1,2-4 (omitted pages are dropped)")
    each(files, "reordered", where, lambda data: toolkit.reorder(data, order))


def render(files, where):
    dpi = number("DPI", "150")
    fmt = choose("Format", ["png", "jpg"], "png")
    for path in files:
        toolkit.save(output(path, f"{path.stem}_pages", where, files, ""), toolkit.render(toolkit.read(path), dpi, fmt))


def extract(files, where):
    minimum = number("Minimum size in px", "0")
    for path in files:
        toolkit.save(output(path, f"{path.stem}_images", where, files, ""), toolkit.extract(toolkit.read(path), minimum))


MENU = {
    "1": ("Merge PDFs", merge),
    "2": ("Split (page range)", split),
    "3": ("Compress", shrink),
    "4": ("Rotate pages", rotate),
    "5": ("Reorder pages", reorder),
    "6": ("Images to PDF", pack),
    "7": ("PDF to images", render),
    "8": ("Extract embedded images", extract),
}


def gather():
    raw = sys.argv[1:] or shlex.split(ask("Drag the files here and press Enter"), posix=os.name != "nt")
    files = [Path(item.strip('"')) for item in raw]
    if not files:
        raise ValueError("no files received")
    for path in files:
        if not path.is_file():
            raise ValueError(f"not found: {path}")
    return files


def main():
    try:
        files = gather()
        print(f"\n{len(files)} file(s) loaded\n")
        for key, (label, _) in MENU.items():
            print(f"  {key}. {label}")
        print()
        action = MENU[choose("Option", MENU, "")][1]
        print(f"\nsource = next to each file, script = folder of {Path(__file__).name}")
        where = choose("Save to", ["source", "script"], "source")
        action(files, where)
        print("\nDone")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"\nerror: {error}")
    input("\nPress Enter to exit")


if __name__ == "__main__":
    main()