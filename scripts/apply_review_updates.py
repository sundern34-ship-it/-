#!/usr/bin/env python3
"""Append visible 2026 correction sheets and navigation to the study PDFs."""

from __future__ import annotations

import argparse
import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0A3D75")
BLUE = colors.HexColor("#005EB8")
GREEN = colors.HexColor("#007A3D")
ORANGE = colors.HexColor("#D14900")
RED = colors.HexColor("#B00020")
PALE_RED = colors.HexColor("#FDE7EA")
PALE_BLUE = colors.HexColor("#DE EFFF".replace(" ", ""))
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#455A64")
GRID = colors.HexColor("#B8C7D9")
WHITE = colors.white

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MARKER_KEY = "StudyReviewVersion"
MARKER_VALUE = "(review-2026-10-01)"


@dataclass(frozen=True)
class ReviewUpdate:
    pages: tuple[int, ...]  # zero-based pages receiving the visible badge
    sections: tuple[tuple[str, str], ...]
    exam_answer: str
    sources: tuple[str, ...]


UPDATES: dict[str, ReviewUpdate] = {
    "02_Schutz_gegen_elektrischen_Schlag.pdf": ReviewUpdate(
        pages=(4, 6),
        sections=((
            "AFDD: keine pauschale Einbaupflicht",
            "Die Aussagen „gefordert“ bzw. „vorgeschrieben“ auf den markierten Seiten sind zu pauschal. Nach DIN VDE 0100-420:2022-06 ist bei besonderen Risiken durch Fehlerlichtbögen bereits in der Planung eine Risiko- und Sicherheitsbewertung durchzuführen und zu dokumentieren. Ein AFDD nach DIN EN 62606 ist eine mögliche anlagentechnische Maßnahme und für bestimmte Risiken empfohlen; die Entscheidung kann je nach Bewertung auch andere geeignete Maßnahmen umfassen.",
        ),),
        exam_answer="„Bei besonderen Risiken fordert die aktuelle DIN VDE 0100-420 eine Risiko- und Sicherheitsbewertung. Der AFDD ist eine mögliche anlagentechnische Schutzmaßnahme, aber keine pauschale Pflicht für jede früher aufgezählte Raumart.“",
        sources=("DIN VDE 0100-420:2022-06 (VDE VERLAG 0100688)", "DIN EN 62606 (VDE 0665-10)"),
    ),
    "06_Netzanschluss_TAB_Zaehlerplatz_Kompensation.pdf": ReviewUpdate(
        pages=(0, 1),
        sections=((
            "TAR Niederspannung aktualisiert",
            "Aktuell ist VDE-AR-N 4100:2026-04; der Hinweis „seit 04/2019“ beschreibt nur die Vorgängerfassung. Die neue Ausgabe gilt für direkte Messung bis 63 A und halbindirekte Messung bis 1000 A. Sie integriert insbesondere § 14a EnWG, mehrere Netzanschlüsse, Messwerterfassung im Vorzählerbereich, ein zusätzliches Verteilerfeld sowie normierte Wandleranlagen. Für die konkrete Ausführung gilt zusätzlich immer die aktuelle TAB des zuständigen VNB.",
        ),),
        exam_answer="„Planung nach VDE-AR-N 4100:2026-04 und der aktuellen TAB des VNB; direkte Messung bis 63 A, halbindirekte Messung bis 1000 A. § 14a und der Kommunikations-/Steuerraum sind früh zu berücksichtigen.“",
        sources=("VDE-AR-N 4100:2026-04 (VDE VERLAG 0100932)",),
    ),
    "08_Gebaeudeinstallation_Leitungen_Planung.pdf": ReviewUpdate(
        pages=(2, 6),
        sections=((
            "Starkstrom- und Fernmeldekabel im Erdreich",
            "Die Angabe 10 cm ist als Mindestabstand aus dem im Buch zitierten VDE-0800-Kontext zu verstehen. Für Planung und Netzbetreiberpraxis wird bei Näherung und Kreuzung häufig 30 cm empfohlen bzw. gefordert. Weniger Abstand ist nur mit geeigneten Schutzmaßnahmen und nach den konkreten Vorgaben zulässig. Im Fachgespräch Mindestwert und Empfehlungs-/VNB-Wert ausdrücklich unterscheiden.",
        ),),
        exam_answer="„Mindestens 0,1 m nach dem zitierten Fernmelde-Regelwerk; planerisch bzw. nach VNB häufig 0,3 m. Maßgeblich sind Verlegefall, Schutzmaßnahmen und TAB.“",
        sources=("Elektro-Installationstechnik, PDF-S. 166 und 212", "Skripte 26 und 27"),
    ),
    "12_PV_Speicher_EMobilitaet_Waermepumpe.pdf": ReviewUpdate(
        pages=(1, 4),
        sections=((
            "VDE-AR-N 4105: neue Ausgabe 2026-03",
            "Die auf den markierten Seiten ausdrücklich aus der Fassung 2011 übernommenen NA-Schutzwerte sind historisches Lernwissen. VDE-AR-N 4105:2026-03 ersetzt die Ausgabe 2018 und erweitert u. a. Q(U), P(f), RoCoF, NA-Schutz-Varianten, PAV,E-Schutz, Kleinsterzeugungsanlagen bis 800 VA und rückspeisefähige Ladeeinrichtungen. Daher alte pauschale Zeitangaben nicht als aktuelle Sollwerte auswendig lernen; Einstellwerte aus aktueller Norm, Einheitenzertifikat und VNB-Vorgaben entnehmen.",
        ),(
            "Was weiterhin prüfungstauglich ist",
            "Der NA-Schutz überwacht insbesondere Spannung und Frequenz und verhindert unzulässigen Inselbetrieb. Bis 30 kVA ist grundsätzlich ein integrierter NA-Schutz ausreichend; darüber ist grundsätzlich ein zentraler NA-Schutz erforderlich. Die zulässige Schieflast bleibt 4,6 kVA. Die exakten Schutzfunktionen und Zeiten immer mit Ausgabe und Anlagenkonzept nennen.",
        )),
        exam_answer="„Aktuell gilt VDE-AR-N 4105:2026-03. Der NA-Schutz überwacht Netzparameter; bis 30 kVA grundsätzlich integriert, darüber grundsätzlich zentral. Exakte Einstellwerte prüfe ich in Norm, Zertifikat und VNB-Vorgabe.“",
        sources=("VDE-AR-N 4105:2026-03 (VDE VERLAG 0100940)",),
    ),
    "18_Energieversorgung_Mittelspannung_Elektrowaerme.pdf": ReviewUpdate(
        pages=(1,),
        sections=((
            "Kabelabstand richtig einordnen",
            "Die genannten 0,3 m sind ein empfohlener Planungs-/Netzbetreiberwert für Näherung und Kreuzung. Als Mindestabstand nennt der im Buch zitierte VDE-0800-Kontext 0,1 m; mit Schutzhauben kann je nach Vorgabe weniger zulässig sein. Nicht als Widerspruch lernen: Mindestwert und empfohlener Ausführungswert haben unterschiedliche Funktion.",
        ),),
        exam_answer="„Mindestens 0,1 m; empfohlen und bei VNB häufig 0,3 m. Die konkrete Trasse wird nach TAB und Schutzmaßnahmen geplant.“",
        sources=("Elektro-Installationstechnik, PDF-S. 166 und 212", "Skript 26, Prüfungsfalle"),
    ),
    "20_Fachgespraech_Fragen_aus_Karteikarten.pdf": ReviewUpdate(
        pages=(13, 53),
        sections=((
            "Korrektur zu AFDD-Fragen (Thema 03)",
            "Seit DIN VDE 0100-420:2019-10 und weiterhin in 2022-06 gibt es keine pauschale AFDD-Pflicht für die aufgezählten Räume. Erforderlich ist bei besonderen Risiken eine dokumentierte Risiko- und Sicherheitsbewertung; AFDD ist eine mögliche anlagentechnische Maßnahme.",
        ),(
            "Korrektur zu PV-/NA-Schutz-Fragen (Thema 12)",
            "Aktuell gilt VDE-AR-N 4105:2026-03. Die Aussagen bis/über 30 kVA und zur Schieflast sind als Grundprinzip brauchbar. Die alten 2011er Einstell- und Abschaltzeiten jedoch nicht pauschal als aktuellen Sollwert wiedergeben; die Neufassung enthält erweiterte P(f), Q(U), RoCoF- und NA-Schutz-Varianten sowie Regeln für 800-VA-Anlagen und bidirektionales Laden.",
        )),
        exam_answer="„Ich nenne immer die Normausgabe. Beim AFDD: Risikobewertung statt pauschaler Pflicht. Beim NA-Schutz: Ausgabe 2026-03 und exakte Parametrierung nach Norm, Zertifikat und VNB.“",
        sources=("DIN VDE 0100-420:2022-06", "VDE-AR-N 4105:2026-03"),
    ),
    "21_Grenzwerte_und_Zahlen.pdf": ReviewUpdate(
        pages=(2, 11),
        sections=((
            "AFDD-Zeile",
            "„Einphasige Endstromkreise bis 16 A“ beschreibt den Anwendungsbereich der Bewertung/Empfehlung, nicht eine automatische Einbaupflicht. Zuerst Risiko- und Sicherheitsbewertung, dann geeignete Maßnahme wählen und dokumentieren.",
        ),(
            "NA-Schutz-Werte",
            "Die Werte auf Seite 12 stammen laut Quelle aus älterem Buchstand. Für VDE-AR-N 4105:2026-03 nicht alle alten Zeiten pauschal übernehmen. Lerne sicher: überwachte Netzparameter, Grundgrenze 30 kVA, 4,6-kVA-Schieflast und die Pflicht, exakte Einstellungen aus aktueller Norm/Zertifikat/VNB zu entnehmen.",
        ),(
            "TAR NS",
            "Alle Einträge zur VDE-AR-N 4100 sind mit Ausgabe 2026-04 zu lesen; bei Zählerplatz und Anmeldung zusätzlich aktuelle TAB beachten.",
        )),
        exam_answer="„Eine Zahl ist nur vollständig mit Einheit, Randbedingung, Normausgabe und Quelle. Alte Tabellenwerte kennzeichne ich als Altstand.“",
        sources=("DIN VDE 0100-420:2022-06", "VDE-AR-N 4105:2026-03", "VDE-AR-N 4100:2026-04"),
    ),
    "22_Probepruefung_mit_Loesungen.pdf": ReviewUpdate(
        pages=(7, 14),
        sections=((
            "Lösungsteile mit aktuellem Normstand beantworten",
            "Für PV/NA-Schutz gilt VDE-AR-N 4105:2026-03. Bis 30 kVA ist grundsätzlich integrierter, darüber grundsätzlich zentraler NA-Schutz das prüfungstaugliche Grundprinzip. Alte pauschale Einstellzeiten nicht ohne Normausgabe nennen. Die Neufassung berücksichtigt u. a. 800-VA-Anlagen, PAV,E-Schutz, Q(U), P(f), RoCoF, neue NA-Varianten und rückspeisefähige Ladeeinrichtungen.",
        ),(
            "Zählerplatz und § 14a",
            "Bei Fragen zu Wallbox, Wärmepumpe, Speicher und Zählerplatz auf VDE-AR-N 4100:2026-04 plus aktuelle TAB verweisen. Die neue Ausgabe integriert die netzdienliche Steuerung nach § 14a und erweitert die Zählerplatz-/Wandlerregeln.",
        )),
        exam_answer="„Ich beginne die Lösung mit der aktuellen Ausgabe 2026-03 bzw. 2026-04 und nenne danach Anlagenleistung, Messkonzept, Schutzkonzept und VNB/TAB.“",
        sources=("VDE-AR-N 4105:2026-03", "VDE-AR-N 4100:2026-04"),
    ),
}

OUTLINE_FILES = {
    "00b_Abgleich_EIT_mit_Skripten.pdf",
    "23_KNX_Gebaeudesystemtechnik.pdf",
    "24_Praktische_Installation.pdf",
    "25_Planungsprojekt_Verbraucheranlage.pdf",
    "26_Kabel_Mittelspannung_Ersatzstrom.pdf",
    "27_Ergaenzungen_Fernmelde_Sonderraeume_UVV.pdf",
}


def correction_page(update: ReviewUpdate, document_title: str) -> bytes:
    """Build one A4 correction sheet as a PDF byte string."""
    buffer = io.BytesIO()
    pdfmetrics.registerFont(TTFont("DejaVu", FONT_REGULAR))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD))
    base = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=base["Title"], fontName="DejaVu-Bold", fontSize=20, leading=25, textColor=NAVY)
    subtitle = ParagraphStyle("Subtitle", parent=base["Normal"], fontName="DejaVu", fontSize=9, leading=13, textColor=MUTED)
    heading = ParagraphStyle("Heading", parent=base["Heading2"], fontName="DejaVu-Bold", fontSize=12.5, leading=16, textColor=BLUE, spaceBefore=4 * mm, spaceAfter=2 * mm)
    body = ParagraphStyle("Body", parent=base["BodyText"], fontName="DejaVu", fontSize=9.2, leading=13.5, textColor=INK, spaceAfter=2 * mm)
    white = ParagraphStyle("White", parent=body, fontName="DejaVu-Bold", textColor=WHITE)
    small = ParagraphStyle("Small", parent=body, fontSize=7.5, leading=10.2, textColor=MUTED)

    def decorate(canvas, doc):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, height - 9 * mm, width, 9 * mm, fill=1, stroke=0)
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 9 * mm, "Fachliche Aktualisierung · Stand 01.10.2026")
        canvas.drawRightString(width - 18 * mm, 9 * mm, "Normen-Update")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Normen-Update 2026 – {document_title}",
    )
    story = [
        Paragraph("Normen-Update 2026", title),
        Paragraph(document_title, subtitle),
        Spacer(1, 3 * mm),
    ]
    for section_title, text in update.sections:
        story.extend([Paragraph(section_title, heading), Paragraph(text, body)])
    story.extend([
        Spacer(1, 4 * mm),
        Table([[Paragraph("Prüfungssichere Kurzantwort", white)], [Paragraph(update.exam_answer, body)]], colWidths=[174 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#DEF6E6")),
            ("BOX", (0, 0), (-1, -1), 1, GREEN),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])),
        Spacer(1, 5 * mm),
        Paragraph("Quellen", heading),
    ])
    for source in update.sources:
        story.append(Paragraph("• " + source, small))
    story.extend([
        Spacer(1, 4 * mm),
        Table([[Paragraph("Aktuelle Norm, TAB des VNB, Herstellerunterlagen und Gefährdungsbeurteilung haben in der Praxis Vorrang. Diese Seite ersetzt nur die widersprüchliche bzw. veraltete Aussage im Lernskript.", body)]], colWidths=[174 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PALE_RED),
            ("BOX", (0, 0), (-1, -1), 1, RED),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])),
    ])
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()


def infer_toc(document: pymupdf.Document) -> list[list]:
    """Infer a compact outline from large bold heading blocks."""
    entries: list[list] = []
    seen: set[tuple[int, str]] = set()
    for page in document:
        for block in page.get_text("dict").get("blocks", []):
            heading_lines: list[tuple[str, float]] = []
            for line in block.get("lines", []):
                spans = [span for span in line.get("spans", []) if span["text"].strip()]
                if not spans:
                    continue
                size = max(float(span["size"]) for span in spans)
                bold = all((span.get("flags", 0) & pymupdf.TEXT_FONT_BOLD) or "bold" in span.get("font", "").lower() for span in spans)
                if size >= 14 and bold:
                    heading_lines.append(("".join(span["text"] for span in line["spans"]).strip(), size))
            if not heading_lines:
                continue
            text = " ".join(item[0] for item in heading_lines)
            max_size = max(item[1] for item in heading_lines)
            if max_size >= 20:
                level = 1
            elif text[0].isdigit() or text.startswith("Teil "):
                level = 2
            else:
                continue
            key = (page.number, text)
            if key not in seen:
                entries.append([level, text, page.number + 1])
                seen.add(key)
    if entries and entries[0][0] != 1:
        entries[0][0] = 1
    return entries


def add_badge(page: pymupdf.Page, target_page: int) -> None:
    # Use the otherwise empty top margin so no original lesson content is
    # covered. A direct text insertion is more robust than a tight textbox.
    rect = pymupdf.Rect(56, 13, 284, 29)
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(color=(176 / 255, 0, 32 / 255), fill=(253 / 255, 231 / 255, 234 / 255), width=0.8)
    shape.commit(overlay=True)
    page.insert_text(
        pymupdf.Point(rect.x0 + 5, rect.y0 + 10.8),
        "NORMEN-UPDATE 2026  ->  KORREKTUR AUF LETZTER SEITE",
        fontname="helv",
        fontsize=6.8,
        color=(176 / 255, 0, 32 / 255),
        overlay=True,
    )
    page.insert_link({"kind": pymupdf.LINK_GOTO, "from": rect, "page": target_page})


def process_pdf(path: Path, dry_run: bool = False) -> tuple[bool, int]:
    document = pymupdf.open(path)
    marker_kind, _ = document.xref_get_key(document.pdf_catalog(), MARKER_KEY)
    update = UPDATES.get(path.name)
    needs_outline = path.name in OUTLINE_FILES and not document.get_toc()
    if marker_kind != "null":
        document.close()
        return False, 0

    original_page_count = len(document)
    badges = 0
    if update and marker_kind == "null":
        if not dry_run:
            update_pdf = pymupdf.open(stream=correction_page(update, document.metadata.get("title") or path.stem), filetype="pdf")
            document.insert_pdf(update_pdf)
            update_pdf.close()
            correction_page_number = len(document) - 1
            for page_number in update.pages:
                add_badge(document[page_number], correction_page_number)
                badges += 1
            document.xref_set_key(document.pdf_catalog(), MARKER_KEY, MARKER_VALUE)
        else:
            badges = len(update.pages)

    toc = document.get_toc()
    if not toc and path.name in OUTLINE_FILES:
        toc = infer_toc(document)
    if update and marker_kind == "null":
        correction_page_human = original_page_count + 1
        toc = [[1, "Normen-Update 2026", correction_page_human]] + toc
    if not dry_run and toc:
        document.set_toc(toc)

    if dry_run:
        document.close()
        return bool(update or needs_outline), badges

    metadata = document.metadata
    keywords = metadata.get("keywords", "").strip()
    marker_keyword = "fachlich geprüft 2026-10-01"
    if marker_keyword not in keywords:
        metadata["keywords"] = (keywords + ", " + marker_keyword).strip(", ")
    if not metadata.get("subject"):
        metadata["subject"] = "Meisterprüfung Elektrotechnik – farbcodiertes Lernskript"
    document.set_metadata(metadata)
    document.xref_set_key(document.pdf_catalog(), MARKER_KEY, MARKER_VALUE)

    with tempfile.NamedTemporaryFile(prefix=f".{path.stem}-", suffix=".pdf", dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        document.save(temporary_path, garbage=0, deflate=True, clean=False)
        document.close()
        check = pymupdf.open(temporary_path)
        expected_pages = original_page_count + (1 if update and marker_kind == "null" else 0)
        if len(check) != expected_pages:
            raise RuntimeError(f"Unexpected page count in {path.name}")
        check.close()
        temporary_path.replace(path)
    except Exception:
        document.close()
        temporary_path.unlink(missing_ok=True)
        raise
    return True, badges


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    paths = args.paths or sorted(Path.cwd().glob("*.pdf"))
    changed = 0
    badges = 0
    for path in paths:
        did_change, badge_count = process_pdf(path, dry_run=args.dry_run)
        if did_change:
            changed += 1
            badges += badge_count
            print(f"{path.name}: update={'yes' if path.name in UPDATES else 'no'}, badges={badge_count}")
    verb = "would update" if args.dry_run else "updated"
    print(f"{verb} {changed} PDFs; {badges} visible update badges")


if __name__ == "__main__":
    main()
