#!/usr/bin/env python3
"""Apply one consistent, study-friendly semantic colour palette to the PDFs.

Only PDF colour operators are changed. Text, page geometry, fonts, images,
links, and page order remain untouched. The transformation is idempotent.

Requires PyMuPDF (`python -m pip install pymupdf`).
"""

from __future__ import annotations

import argparse
import re
import tempfile
from collections import Counter
from pathlib import Path

import pymupdf

# Existing RGB colours -> accessible study palette.
# Semantic meaning:
#   blue   structure / headings / questions
#   green  answers / rules to remember
#   amber  calculations / warnings
#   purple exam tips
#   red    critical safety warning
PALETTE: dict[tuple[int, int, int], tuple[int, int, int]] = {
    # Main text and hierarchy
    (0, 0, 0): (31, 41, 55),              # black -> soft charcoal
    (26, 26, 26): (31, 41, 55),
    (31, 56, 100): (24, 58, 99),           # dark navy headings / table headers
    (47, 84, 150): (29, 95, 158),          # secondary blue
    (46, 116, 181): (29, 95, 158),
    (21, 101, 192): (11, 103, 178),         # info / source call-outs
    # Semantic accents
    (46, 125, 50): (31, 122, 66),          # answers / "Merke"
    (84, 130, 53): (31, 122, 66),
    (106, 27, 154): (124, 58, 171),         # exam tips
    (112, 48, 160): (124, 58, 171),
    (230, 81, 0): (194, 65, 12),            # warnings / calculations
    (197, 90, 17): (194, 65, 12),
    (176, 0, 32): (177, 26, 46),            # critical safety warning
    # Supporting text, rules, and table borders
    (84, 110, 122): (71, 85, 105),
    (70, 70, 70): (71, 85, 105),
    (144, 164, 174): (100, 116, 139),
    (127, 127, 127): (100, 116, 139),
    (176, 190, 197): (203, 213, 225),
    (201, 213, 227): (203, 213, 225),
    # Quiet table rows
    (245, 247, 250): (241, 245, 249),
    (243, 247, 251): (241, 245, 249),
    (246, 246, 246): (248, 250, 252),
    # Semantic call-out backgrounds
    (227, 242, 253): (232, 244, 255),       # blue: source / deeper study
    (222, 235, 247): (232, 244, 255),
    (232, 245, 233): (232, 247, 237),       # green: remember / answer
    (226, 240, 217): (232, 247, 237),
    (243, 229, 245): (247, 237, 250),       # purple: exam tip
    (236, 228, 245): (247, 237, 250),
    (255, 243, 224): (255, 241, 230),       # amber: caution / calculation
    (251, 229, 214): (255, 241, 230),
}

_NUMBER = rb"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
_RGB_OPERATOR = re.compile(
    rb"(?<![\d.])(" + _NUMBER + rb")\s+(" + _NUMBER + rb")\s+(" + _NUMBER + rb")\s+(rg|RG)\b"
)


def _pdf_component(value: int) -> bytes:
    """Return a short, deterministic PDF colour component in the range 0..1."""
    if value == 0:
        return b"0"
    if value == 255:
        return b"1"
    return (f"{value / 255:.6f}".rstrip("0").rstrip(".")).encode("ascii")


def recolour_stream(data: bytes, replacements: Counter) -> bytes:
    """Replace known non-stroking/stroking RGB operators in one content stream."""

    def replace(match: re.Match[bytes]) -> bytes:
        source = tuple(round(float(match.group(i)) * 255) for i in (1, 2, 3))
        target = PALETTE.get(source)
        if target is None:
            return match.group(0)
        replacements[(source, target)] += 1
        operator = match.group(4)
        return b" ".join((*(_pdf_component(c) for c in target), operator))

    return _RGB_OPERATOR.sub(replace, data)


def document_stream_xrefs(document: pymupdf.Document) -> set[int]:
    """Find page content streams and reusable Form XObjects containing artwork."""
    xrefs: set[int] = set()
    for page in document:
        xrefs.update(page.get_contents())
    for xref in range(1, document.xref_length()):
        if document.xref_get_key(xref, "Subtype")[1] == "/Form":
            xrefs.add(xref)
    return xrefs


def recolour_pdf(path: Path, dry_run: bool = False) -> tuple[int, Counter]:
    """Recolour a PDF in place and return (changed stream count, replacements)."""
    document = pymupdf.open(path)
    replacements: Counter = Counter()
    changed_streams = 0

    # These invariants guard against accidental educational-content changes.
    text_before = tuple(page.get_text("text") for page in document)
    page_boxes_before = tuple(tuple(page.rect) for page in document)

    for xref in document_stream_xrefs(document):
        try:
            original = document.xref_stream(xref)
        except (RuntimeError, ValueError):
            continue
        if not original:
            continue
        updated = recolour_stream(original, replacements)
        if updated != original:
            changed_streams += 1
            if not dry_run:
                document.update_stream(xref, updated)

    if dry_run or not changed_streams:
        document.close()
        return changed_streams, replacements

    with tempfile.NamedTemporaryFile(
        prefix=f".{path.stem}-", suffix=".pdf", dir=path.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)

    try:
        # Preserve the original object/resource graph. In particular, do not
        # clean or garbage-collect image resources while changing colours.
        document.save(
            temporary_path,
            garbage=0,
            deflate=True,
            clean=False,
            pretty=False,
        )
        document.close()

        check = pymupdf.open(temporary_path)
        text_after = tuple(page.get_text("text") for page in check)
        page_boxes_after = tuple(tuple(page.rect) for page in check)
        check.close()

        if text_after != text_before:
            raise RuntimeError(f"Text changed while recolouring {path.name}")
        if page_boxes_after != page_boxes_before:
            raise RuntimeError(f"Page geometry changed while recolouring {path.name}")

        temporary_path.replace(path)
    except Exception:
        document.close()
        temporary_path.unlink(missing_ok=True)
        raise

    return changed_streams, replacements


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="PDFs to recolour (default: every PDF in the repository root)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report matches without writing files"
    )
    args = parser.parse_args()

    paths = args.paths or sorted(Path.cwd().glob("*.pdf"))
    if not paths:
        parser.error("no PDF files found")

    total_streams = 0
    total_replacements: Counter = Counter()
    for path in paths:
        changed_streams, replacements = recolour_pdf(path, dry_run=args.dry_run)
        total_streams += changed_streams
        total_replacements.update(replacements)
        print(
            f"{path.name}: {changed_streams} streams, "
            f"{sum(replacements.values())} colour operators"
        )

    mode = "would update" if args.dry_run else "updated"
    print(
        f"\n{mode} {len(paths)} PDFs: {total_streams} streams, "
        f"{sum(total_replacements.values())} colour operators"
    )


if __name__ == "__main__":
    main()
