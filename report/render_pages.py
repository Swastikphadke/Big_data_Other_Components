"""Render selected PDF pages to PNG for visual inspection (QA only).
Usage: python report/render_pages.py <out_dir> [page numbers ...]   (1-based; default: first 12)"""
import sys
from pathlib import Path

import pymupdf

pdf = Path(__file__).parent / "BigDataSystems_24CI51_SLA_Report.pdf"
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(pdf)
pages = [int(p) for p in sys.argv[2:]] or list(range(1, 13))
print(f"{pdf.name}: {doc.page_count} pages")
for p in pages:
    if 1 <= p <= doc.page_count:
        pix = doc[p - 1].get_pixmap(dpi=70)
        pix.save(out / f"page_{p:03d}.png")
print("rendered", pages)
