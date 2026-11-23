# pdf-toolkit

Small PDF toolkit built on [PyMuPDF](https://pymupdf.readthedocs.io) and, optionally, Ghostscript.
Use it as a command line tool or import it as a Python module.

Operations: merge, split, rotate, reorder, images to PDF, PDF to images, extract embedded images, compress.

## Install

```bash
pip install https://github.com/Prybet/pdf-toolkit/archive/refs/tags/v1.0.0.zip
```

This installs the `pdftoolkit` command and `pymupdf`. Ghostscript is only needed for `shrink -e ghost` and is installed separately (`apt install ghostscript`).

## Command line

```bash
pdftoolkit merge out.pdf a.pdf b.pdf c.pdf        # merge in the given order
pdftoolkit split in.pdf out.pdf 2 5               # keep pages 2 to 5 (1-based, inclusive)
pdftoolkit rotate in.pdf out.pdf 90               # rotate all pages clockwise (90, 180, 270)
pdftoolkit rotate in.pdf out.pdf 90 -p "1,3-5"    # rotate only some pages
pdftoolkit reorder in.pdf out.pdf "3,1,2-4"       # new order, omitted pages are dropped
pdftoolkit pack out.pdf one.png two.jpg           # one image per page
pdftoolkit render in.pdf pages/ -d 150 -f png     # every page to an image (png or jpg)
pdftoolkit extract in.pdf images/ -m 50           # embedded images, skipping those under 50 px
pdftoolkit shrink in.pdf out.pdf -l recommended   # compress
```

Compression options:

| Option           | Values                          | Default       |
| ---------------- | ------------------------------- | ------------- |
| `-l`, `--level`  | `extreme`, `recommended`, `low` | `recommended` |
| `-e`, `--engine` | `mupdf`, `ghost`                | `mupdf`       |

`shrink` never returns a file larger than the original.

Page specs accept single pages, ranges and reversed ranges: `1,3-5`, `5-1`.

## Python

```python
import toolkit

data = open("in.pdf", "rb").read()

merged = toolkit.merge([data, data])
part = toolkit.split(data, 1, 3)
small = toolkit.shrink(data, "recommended", "mupdf")
images = toolkit.render(data, 150, "png")   # {"p001.png": bytes, ...}
```

Every function takes and returns `bytes` (or a `dict` of name to `bytes`), so nothing touches the disk.
Invalid input raises `ValueError`.

## Interactive launcher

`cli.py` is prompt-based launcher for local use. Drop files onto it or run it directly:

```bash
python cli.py file1.pdf file2.pdf
```

It imports the module from `src/`, so it works from a clone without installing anything else than `pymupdf`.

## Development

```bash
python -m venv .venv
source .venv/bin/activate.fish   # bash/zsh: source .venv/bin/activate

pip install -e .
```

The editable install picks up changes in `src/toolkit.py` without reinstalling.

## License

AGPL-3.0-or-later, the same license PyMuPDF uses. See `LICENSE`.
