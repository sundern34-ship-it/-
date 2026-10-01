#!/usr/bin/env python3
"""Apply a strong, study-friendly semantic colour system to the exam PDFs.

The script changes colours only: it keeps text, page geometry, fonts, images,
links, and page order untouched. In addition to replacing the original muted
palette, it adds translucent colour bands behind questions, answers, important
bold terms, and the values in PDF 21. The transformation is idempotent.

Requires PyMuPDF (`python -m pip install pymupdf`).
"""

from __future__ import annotations

import argparse
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

# Existing RGB colours (including palette v1) -> stronger accessible palette.
# Semantic meaning:
#   blue   structure / headings / questions
#   green  answers / rules to remember
#   amber  calculations / warnings
#   purple exam tips
#   red    critical safety warning
PALETTE: dict[tuple[int, int, int], tuple[int, int, int]] = {
    # Main text
    (0, 0, 0): (23, 32, 51),
    (26, 26, 26): (23, 32, 51),
    (31, 41, 55): (23, 32, 51),
    # Main headings and table headers
    (31, 56, 100): (10, 61, 117),
    (24, 58, 99): (10, 61, 117),
    # Secondary headings / question labels
    (47, 84, 150): (0, 94, 184),
    (46, 116, 181): (0, 94, 184),
    (29, 95, 158): (0, 94, 184),
    # Information / deeper-study call-outs
    (21, 101, 192): (0, 111, 201),
    (11, 103, 178): (0, 111, 201),
    # Answers / "Merke"
    (46, 125, 50): (0, 122, 61),
    (84, 130, 53): (0, 122, 61),
    (31, 122, 66): (0, 122, 61),
    # Oral-exam tips
    (106, 27, 154): (123, 44, 191),
    (112, 48, 160): (123, 44, 191),
    (124, 58, 171): (123, 44, 191),
    # Warnings / calculations
    (230, 81, 0): (209, 73, 0),
    (197, 90, 17): (209, 73, 0),
    (194, 65, 12): (209, 73, 0),
    # Critical safety warnings
    (176, 0, 32): (176, 0, 32),
    (177, 26, 46): (176, 0, 32),
    # Supporting text
    (84, 110, 122): (69, 90, 100),
    (70, 70, 70): (69, 90, 100),
    (71, 85, 105): (69, 90, 100),
    (144, 164, 174): (96, 125, 139),
    (127, 127, 127): (96, 125, 139),
    (100, 116, 139): (96, 125, 139),
    # Rules and table borders
    (176, 190, 197): (184, 199, 217),
    (201, 213, 227): (184, 199, 217),
    (203, 213, 225): (184, 199, 217),
    # Alternating table rows: deliberately more visible than in v1
    (245, 247, 250): (234, 242, 251),
    (243, 247, 251): (234, 242, 251),
    (241, 245, 249): (234, 242, 251),
    (246, 246, 246): (245, 248, 252),
    (248, 250, 252): (245, 248, 252),
    # Semantic call-out backgrounds
    (227, 242, 253): (220, 238, 255),
    (222, 235, 247): (220, 238, 255),
    (232, 244, 255): (220, 238, 255),
    (232, 245, 233): (220, 244, 228),
    (226, 240, 217): (220, 244, 228),
    (232, 247, 237): (220, 244, 228),
    (243, 229, 245): (240, 224, 250),
    (236, 228, 245): (240, 224, 250),
    (247, 237, 250): (240, 224, 250),
    (255, 243, 224): (255, 229, 204),
    (251, 229, 214): (255, 229, 204),
    (255, 241, 230): (255, 229, 204),
}

# Translucent layers added to make the semantic structure immediately visible.
HIGHLIGHT_STYLES: dict[str, tuple[tuple[int, int, int], float, bool]] = {
    # Question/answer bands are inserted behind the original text so the
    # foreground keeps its full contrast. Marker highlights sit on top with
    # low opacity because table backgrounds are already part of the page.
    "question": ((222, 239, 255), 1.0, False),
    "answer": ((222, 246, 230), 1.0, False),
    "keyword": ((255, 224, 112), 0.34, True),
    "value": ((255, 196, 128), 0.34, True),
}

PALETTE_MARKER_KEY = "StudyPaletteVersion"
PALETTE_MARKER_VALUE = "(semantic-v2)"
BODY_TEXT_COLOURS = {0x000000, 0x1A1A1A, 0x1F2937, 0x172033}
CALLOUT_PREFIXES = (
    "merke:",
    "prüfungsfalle",
    "tipp für das fachgespräch",
    "vertiefen:",
    "warum dieses skript?",
)

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


def _normalised(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(component / 255 for component in rgb)


def recolour_stream(data: bytes, replacements: Counter) -> bytes:
    """Replace known non-stroking/stroking RGB operators in one content stream."""

    def replace(match: re.Match[bytes]) -> bytes:
        source = tuple(round(float(match.group(i)) * 255) for i in (1, 2, 3))
        target = PALETTE.get(source)
        if target is None or target == source:
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


def _expanded_text_rect(
    bbox: tuple[float, float, float, float], page_rect: pymupdf.Rect
) -> pymupdf.Rect:
    """Make a compact marker-like rectangle around a text span."""
    rect = pymupdf.Rect(bbox)
    height = rect.height
    rect.x0 -= 0.9
    rect.x1 += 0.9
    rect.y0 += height * 0.10
    rect.y1 -= height * 0.02
    return rect & page_rect


def _value_column_headers(text_dict: dict) -> list[tuple[float, float, float]]:
    """Return (header-bottom, value-x, source-x) for tables in PDF 21."""
    words: list[tuple[str, tuple[float, float, float, float]]] = []
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                words.append((span["text"].strip(), tuple(span["bbox"])))

    value_headers = [bbox for text, bbox in words if text == "Wert"]
    source_headers = [bbox for text, bbox in words if text == "Quelle"]
    headers: list[tuple[float, float, float]] = []
    for value in value_headers:
        candidates = [
            source
            for source in source_headers
            if abs(source[1] - value[1]) < 3 and source[0] > value[0]
        ]
        if candidates:
            source = min(candidates, key=lambda item: item[0])
            headers.append((max(value[3], source[3]), value[0], source[0]))
    return sorted(headers)


def semantic_highlight_rectangles(
    page: pymupdf.Page, filename: str
) -> dict[str, list[pymupdf.Rect]]:
    """Locate questions, answers, bold terms, and memorisation values."""
    text_dict = page.get_text("dict")
    rectangles: dict[str, list[pymupdf.Rect]] = defaultdict(list)
    page_rect = page.rect

    headers = _value_column_headers(text_dict) if filename.startswith("21_") else []

    for block in text_dict.get("blocks", []):
        lines = block.get("lines", [])
        if not lines:
            continue

        line_texts = ["".join(span["text"] for span in line.get("spans", [])) for line in lines]
        block_text = " ".join(line_texts).strip()
        lowered = block_text.casefold()

        if block_text.startswith("F:"):
            bbox = pymupdf.Rect(block["bbox"])
            band = pymupdf.Rect(54, bbox.y0 - 1.2, page_rect.width - 54, bbox.y1 + 1.2)
            rectangles["question"].append(band & page_rect)
            continue
        if block_text.startswith("A:"):
            bbox = pymupdf.Rect(block["bbox"])
            band = pymupdf.Rect(71, bbox.y0 - 1.0, page_rect.width - 54, bbox.y1 + 1.2)
            rectangles["answer"].append(band & page_rect)
            continue

        is_callout = lowered.startswith(CALLOUT_PREFIXES)
        for line, line_text in zip(lines, line_texts):
            stripped_line = line_text.strip()
            if stripped_line.startswith(("F:", "A:")):
                continue

            for span in line.get("spans", []):
                text = span["text"].strip()
                if not text:
                    continue

                # PDF 21 is a dedicated memorisation table. Highlight every
                # value-column text fragment in amber, while leaving sources
                # and labels untouched.
                if headers and span["color"] in BODY_TEXT_COLOURS:
                    x0, y0, x1, _ = span["bbox"]
                    eligible_headers = [header for header in headers if y0 > header[0] + 1]
                    if eligible_headers:
                        _, value_x, source_x = eligible_headers[-1]
                        centre_x = (x0 + x1) / 2
                        if value_x - 3 <= centre_x < source_x - 2:
                            rectangles["value"].append(
                                _expanded_text_rect(tuple(span["bbox"]), page_rect)
                            )
                            continue

                # A restrained marker effect for short bold keywords in body
                # text. Headings, table headers, and pre-coloured call-outs are
                # intentionally excluded.
                font = span.get("font", "").casefold()
                is_bold = bool(span.get("flags", 0) & pymupdf.TEXT_FONT_BOLD) or "bold" in font
                size = float(span.get("size", 0))
                if (
                    is_bold
                    and not is_callout
                    and 8.5 <= size <= 11.6
                    and span["color"] in BODY_TEXT_COLOURS
                    and 2 <= len(text) <= 64
                    and any(character.isalnum() for character in text)
                    and span["bbox"][1] < page_rect.height - 42
                ):
                    rectangles["keyword"].append(
                        _expanded_text_rect(tuple(span["bbox"]), page_rect)
                    )

    return rectangles


def _draw_semantic_highlights(
    page: pymupdf.Page,
    rectangles: dict[str, list[pymupdf.Rect]],
    apply: bool,
) -> Counter:
    counts: Counter = Counter({name: len(rects) for name, rects in rectangles.items()})
    if not apply:
        return counts

    for name, rects in rectangles.items():
        if not rects:
            continue
        colour, opacity, overlay = HIGHLIGHT_STYLES[name]
        shape = page.new_shape()
        for rect in rects:
            if rect.width > 0 and rect.height > 0:
                shape.draw_rect(rect)
        shape.finish(
            color=None,
            fill=_normalised(colour),
            width=0,
            fill_opacity=opacity,
        )
        shape.commit(overlay=overlay)
    return counts


def _has_semantic_highlights(document: pymupdf.Document) -> bool:
    kind, _ = document.xref_get_key(document.pdf_catalog(), PALETTE_MARKER_KEY)
    return kind != "null"


def recolour_pdf(path: Path, dry_run: bool = False) -> tuple[int, Counter, Counter]:
    """Recolour a PDF in place and report streams, replacements, and highlights."""
    document = pymupdf.open(path)
    replacements: Counter = Counter()
    highlights: Counter = Counter()
    changed_streams = 0

    # These invariants guard against accidental educational-content changes.
    text_before = tuple(page.get_text("text") for page in document)
    page_boxes_before = tuple(tuple(page.rect) for page in document)

    has_highlights = _has_semantic_highlights(document)
    if not has_highlights:
        for page in document:
            rectangles = semantic_highlight_rectangles(page, path.name)
            highlights.update(
                _draw_semantic_highlights(page, rectangles, apply=not dry_run)
            )
        if not dry_run and sum(highlights.values()):
            document.xref_set_key(
                document.pdf_catalog(), PALETTE_MARKER_KEY, PALETTE_MARKER_VALUE
            )

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

    if dry_run or (not changed_streams and not sum(highlights.values())):
        document.close()
        return changed_streams, replacements, highlights

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

    return changed_streams, replacements, highlights


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
    total_highlights: Counter = Counter()
    for path in paths:
        changed_streams, replacements, highlights = recolour_pdf(
            path, dry_run=args.dry_run
        )
        total_streams += changed_streams
        total_replacements.update(replacements)
        total_highlights.update(highlights)
        highlight_summary = ", ".join(
            f"{name}={highlights[name]}" for name in HIGHLIGHT_STYLES
            if highlights[name]
        ) or "none"
        print(
            f"{path.name}: {changed_streams} streams, "
            f"{sum(replacements.values())} colour operators, "
            f"highlights: {highlight_summary}"
        )

    mode = "would update" if args.dry_run else "updated"
    totals = ", ".join(
        f"{name}={total_highlights[name]}" for name in HIGHLIGHT_STYLES
    )
    print(
        f"\n{mode} {len(paths)} PDFs: {total_streams} streams, "
        f"{sum(total_replacements.values())} colour operators; {totals}"
    )


if __name__ == "__main__":
    main()
