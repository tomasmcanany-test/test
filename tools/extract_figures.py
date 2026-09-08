#!/usr/bin/env python3
"""
Extract figure images from a research PDF into a folder, for vision-based
literature review. Saves images above a size threshold (to skip logos/icons)
and prints the saved file paths.

Usage:
    python extract_figures.py --pdf <path> --out <folder> [--min 150]

Dependencies:
    pymupdf  (pip install pymupdf)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import pymupdf  # PyMuPDF >= 1.24
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None


def extract(pdf: Path, out: Path, min_side: int = 150) -> list[Path]:
    if pymupdf is None:
        raise RuntimeError("pymupdf is required. Run: pip install pymupdf")
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf))
    saved: list[Path] = []
    count = 0
    for pno in range(len(doc)):
        page = doc[pno]
        for img in page.get_images(full=True):
            xref = img[0]
            pix = pymupdf.Pixmap(doc, xref)
            if pix.width < min_side or pix.height < min_side:
                continue
            if pix.n - pix.alpha > 3:  # CMYK -> RGB
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            fn = out / f"page{pno+1:02d}_fig{count:02d}_{pix.width}x{pix.height}.png"
            pix.save(str(fn))
            saved.append(fn)
            count += 1
    doc.close()
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract figures from a PDF")
    parser.add_argument("--pdf", required=True, help="Path to the PDF")
    parser.add_argument("--out", required=True, help="Output folder")
    parser.add_argument("--min", type=int, default=150, help="Min side length (px)")
    args = parser.parse_args(argv)

    saved = extract(Path(args.pdf), Path(args.out), args.min)
    print(f"[=] Extracted {len(saved)} figure(s) to {args.out}")
    for s in saved:
        print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
