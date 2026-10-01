#!/usr/bin/env python3
"""Build the bilingual 2026 study navigator and technical update PDF."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import arabic_reshaper
import pymupdf
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#0A3D75")
BLUE = colors.HexColor("#005EB8")
PALE_BLUE = colors.HexColor("#DE EFFF".replace(" ", ""))
GREEN = colors.HexColor("#007A3D")
PALE_GREEN = colors.HexColor("#DEF6E6")
ORANGE = colors.HexColor("#D14900")
PALE_ORANGE = colors.HexColor("#FFE5CC")
PURPLE = colors.HexColor("#7B2CBF")
PALE_PURPLE = colors.HexColor("#F0E0FA")
RED = colors.HexColor("#B00020")
PALE_RED = colors.HexColor("#FDE7EA")
YELLOW = colors.HexColor("#FFE070")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#455A64")
GRID = colors.HexColor("#B8C7D9")
ROW = colors.HexColor("#EAF2FB")
WHITE = colors.white

FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def ar(text: str) -> str:
    """Shape Arabic text for ReportLab's left-to-right text engine."""
    return get_display(arabic_reshaper.reshape(text))


def build_styles():
    pdfmetrics.registerFont(TTFont("DejaVu", FONT_REGULAR))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD))
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="DejaVu-Bold",
            fontSize=23,
            leading=28,
            textColor=NAVY,
            spaceAfter=7 * mm,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="DejaVu",
            fontSize=11,
            leading=16,
            textColor=MUTED,
            spaceAfter=5 * mm,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="DejaVu-Bold",
            fontSize=17,
            leading=21,
            textColor=NAVY,
            spaceBefore=2 * mm,
            spaceAfter=4 * mm,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="DejaVu-Bold",
            fontSize=12.5,
            leading=16,
            textColor=BLUE,
            spaceBefore=2 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="DejaVu",
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
            spaceAfter=2.2 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="DejaVu",
            fontSize=7.5,
            leading=10.2,
            textColor=MUTED,
        ),
        "table": ParagraphStyle(
            "Table",
            parent=base["BodyText"],
            fontName="DejaVu",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "table_bold": ParagraphStyle(
            "TableBold",
            parent=base["BodyText"],
            fontName="DejaVu-Bold",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "white": ParagraphStyle(
            "White",
            parent=base["BodyText"],
            fontName="DejaVu-Bold",
            fontSize=8,
            leading=10,
            textColor=WHITE,
        ),
        "arabic": ParagraphStyle(
            "Arabic",
            parent=base["BodyText"],
            fontName="DejaVu",
            fontSize=10,
            leading=15,
            textColor=INK,
            alignment=TA_RIGHT,
            spaceAfter=2.5 * mm,
        ),
        "arabic_title": ParagraphStyle(
            "ArabicTitle",
            parent=base["Heading1"],
            fontName="DejaVu-Bold",
            fontSize=18,
            leading=24,
            textColor=BLUE,
            alignment=TA_RIGHT,
            spaceAfter=4 * mm,
        ),
        "center": ParagraphStyle(
            "Center",
            parent=base["BodyText"],
            fontName="DejaVu-Bold",
            fontSize=9.5,
            leading=13,
            textColor=INK,
            alignment=TA_CENTER,
        ),
    }
    return styles


class NavigatorDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, styles: dict, **kwargs):
        super().__init__(filename, pagesize=A4, **kwargs)
        self.styles = styles
        width, height = A4
        frame = Frame(
            18 * mm,
            17 * mm,
            width - 36 * mm,
            height - 32 * mm,
            id="normal",
            leftPadding=0,
            rightPadding=0,
            topPadding=3 * mm,
            bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=self._decorate))

    def _decorate(self, canvas, doc):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, height - 8 * mm, width, 8 * mm, fill=1, stroke=0)
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 8 * mm, "Lernnavigator Meisterprüfung Elektrotechnik · Stand 01.10.2026")
        canvas.drawRightString(width - 18 * mm, 8 * mm, f"Seite {doc.page}")
        canvas.restoreState()


def p(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def box(text: str, style, background, border, width=174 * mm) -> Table:
    table = Table([[p(text, style)]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 1.2, border),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def styled_table(data, widths, styles, repeat_rows=1, row_background=True) -> Table:
    table = Table(data, colWidths=widths, repeatRows=repeat_rows, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if row_background:
        for row in range(2, len(data), 2):
            commands.append(("BACKGROUND", (0, row), (-1, row), ROW))
    table.setStyle(TableStyle(commands))
    return table


def build_story(styles):
    S = styles
    story = []

    # Page 1 — start
    story += [
        Spacer(1, 14 * mm),
        p("Lernnavigator 2026", S["title"]),
        p("Meisterprüfung Elektrotechnik · fachliche Aktualisierung, Lernreihenfolge und aktives Wiederholen", S["subtitle"]),
        p(ar("دليل الدراسة المحدث: ترتيب واضح، مراجعة فنية وطريقة حفظ عملية"), S["arabic_title"]),
        box(
            "<b>START HIER:</b> Lies zuerst diese Datei. Danach arbeitest du mit Skript 00 und der aktualisierten 12-Wochen-Reihenfolge auf Seite 3 dieses Navigators. Die technischen Skripte bleiben deine Hauptquelle; die markierten Normen-Updates in einzelnen Dateien haben Vorrang vor älteren Aussagen.",
            S["body"], PALE_BLUE, BLUE,
        ),
        Spacer(1, 5 * mm),
        p("Das neue Merksystem", S["h1"]),
    ]
    colour_rows = [
        [p("Farbe", S["white"]), p("Bedeutung", S["white"]), p("Was du damit machst", S["white"])],
        [p("Blau", S["table_bold"]), p("Frage / Struktur / Norm", S["table"]), p("Frage zuerst laut beantworten; dann lesen.", S["table"])],
        [p("Grün", S["table_bold"]), p("Antwort / Merksatz", S["table"]), p("In einen eigenen Satz umformulieren.", S["table"])],
        [p("Gelb", S["table_bold"]), p("Schlüsselbegriff", S["table"]), p("Begriff erklären können, nicht nur erkennen.", S["table"])],
        [p("Orange", S["table_bold"]), p("Grenzwert / Prüfungsfalle", S["table"]), p("Wert immer mit Einheit und Quelle lernen.", S["table"])],
        [p("Lila", S["table_bold"]), p("Fachgespräch-Tipp", S["table"]), p("Antwort nach dem 4-Schritte-Schema formulieren.", S["table"])],
        [p("Rot", S["table_bold"]), p("Normen-Update / Sicherheit", S["table"]), p("Diese Aussage hat Vorrang; aktuelle TAB prüfen.", S["table"])],
    ]
    story += [
        styled_table(colour_rows, [27 * mm, 52 * mm, 95 * mm], S),
        Spacer(1, 6 * mm),
        box(
            ar("مهم: لا تحفظ الرقم وحده. احفظ دائمًا: ما الذي يقيسه الرقم، وحدته، القاعدة أو المعيار، وسبب استخدامه."),
            S["arabic"], PALE_GREEN, GREEN,
        ),
        Spacer(1, 4 * mm),
        p("Stand der Prüfung: 01.10.2026. Bei Arbeiten in der Praxis gelten immer der aktuelle Normenbestand, die TAB deines VNB, Herstellerangaben und die Gefährdungsbeurteilung.", S["small"]),
        PageBreak(),
    ]

    # Page 2 — technical review
    story += [
        p("Fachliche Aktualisierung – was du anders lernen musst", S["h1"]),
        p("Die ursprünglichen Skripte wurden mit aktuellen offiziellen Normenständen und DGUV-Hinweisen gegengeprüft. Die folgenden Punkte sind prüfungsrelevant.", S["body"]),
    ]
    updates = [
        [p("Thema", S["white"]), p("Prüfungssichere Fassung", S["white"]), p("Betroffene Skripte", S["white"])],
        [p("AFDD", S["table_bold"]), p("DIN VDE 0100-420:2022-06 fordert bei besonderen Risiken eine Risiko- und Sicherheitsbewertung. Ein AFDD ist eine mögliche anlagentechnische Maßnahme bzw. Empfehlung – <b>keine pauschale Einbaupflicht</b> für die früher aufgezählten Räume.", S["table"]), p("02, 20, 21", S["table"])],
        [p("TAR NS", S["table_bold"]), p("Aktuell ist VDE-AR-N 4100:2026-04. Neu bzw. integriert: § 14a EnWG, mehrere Netzanschlüsse, Messwerte im Vorzählerbereich, zusätzliches Verteilerfeld und halbindirekte Messung bis 1000 A. Direkte Messung bleibt bis 63 A.", S["table"]), p("06 sowie Verweise in 01–05, 08, 19, 21, 22, 24, 25", S["table"])],
        [p("TAR EZA NS", S["table_bold"]), p("Aktuell ist VDE-AR-N 4105:2026-03. Die 2018er Fassung wurde ersetzt. Neu sind u. a. vereinfachte Bedingungen bis 800 VA, P<sub>AV,E</sub>-Schutz, Q(U), erweiterte P(f)/RoCoF- und NA-Schutz-Varianten sowie rückspeisefähige Ladeeinrichtungen. Alte 2011er Einstellzeiten nicht unkritisch als aktuellen Sollwert lernen.", S["table"]), p("12, 20, 21, 22", S["table"])],
        [p("Kabelabstand", S["table_bold"]), p("Im Erdreich: nach der im Buch zitierten VDE-0800-Regel mindestens 0,1 m; als Planungs-/VNB-Empfehlung häufig 0,3 m. Im Fachgespräch immer Mindestwert und empfohlenen Wert auseinanderhalten.", S["table"]), p("08, 18, 26, 27", S["table"])],
        [p("Bad", S["table_bold"]), p("DIN VDE 0100-701:2025-06 ist gültig und ersetzt 2008-10. Skript 07 berücksichtigt die Neufassung bereits; Begriffe und Bereiche nicht aus alten Skizzen übernehmen.", S["table"]), p("07, 27", S["table"])],
        [p("Prüfnormen", S["table_bold"]), p("DIN VDE 0100-600:2017-06 bleibt veröffentlichte Norm; 2025-12 ist ein Entwurf. Ebenso ersetzt ein Entwurf zur DIN VDE 0105-100 nicht automatisch die gültige Ausgabe mit A1/Berichtigung.", S["table"]), p("09, 20, 21", S["table"])],
    ]
    story += [
        styled_table(updates, [30 * mm, 112 * mm, 32 * mm], S),
        Spacer(1, 5 * mm),
        box("<b>Prüfungsregel:</b> Wenn Kursunterlage, altes Fachbuch und neue Norm voneinander abweichen, nenne die Ausgabe. Sage im Fachgespräch: „Nach aktuellem Normenstand …; der ältere Wert stammt aus …“", S["body"], PALE_RED, RED),
        PageBreak(),
    ]

    # Page 3 — plan
    story += [
        p("Aktualisierte Lernreihenfolge – 12 Wochen", S["h1"]),
        p("Plane an fünf Tagen pro Woche je 60–90 Minuten. Ein sechster Tag ist nur für Wiederholung; ein Tag bleibt frei.", S["body"]),
    ]
    plan = [
        [p("Woche", S["white"]), p("Skripte", S["white"]), p("Lernziel", S["white"]), p("Aktiver Test", S["white"])],
        [p("1", S["table_bold"]), p("01 + 15", S["table_bold"]), p("Recht, Begriffe, Personen, 5 Sicherheitsregeln", S["table"]), p("10 Antworten mit Norm + Begründung", S["table"])],
        [p("2", S["table_bold"]), p("02", S["table_bold"]), p("Schutz gegen elektrischen Schlag", S["table"]), p("TN/TT, RCD, Abschaltbedingungen zeichnen", S["table"])],
        [p("3", S["table_bold"]), p("03 + 04 + 19 (1–6)", S["table_bold"]), p("Schutzgeräte und Leitungsdimensionierung", S["table"]), p("Rechenschema ohne Vorlage", S["table"])],
        [p("4", S["table_bold"]), p("05 + 06", S["table_bold"]), p("Erdung, PA, Hausanschluss, Zählerplatz", S["table"]), p("Anlage vom HAK bis Verbraucher erklären", S["table"])],
        [p("5", S["table_bold"]), p("07 + 08 + 23 + 24", S["table_bold"]), p("Sonderräume, Planung, KNX, praktische Installation", S["table"]), p("Bad/KNX/Installationszonen aus dem Kopf", S["table"])],
        [p("6", S["table_bold"]), p("09", S["table_bold"]), p("Prüfen und Messen", S["table"]), p("Reihenfolge: Besichtigen – Erproben – Messen", S["table"])],
        [p("7", S["table_bold"]), p("10", S["table_bold"]), p("Grundlagen, Trafo, Motor", S["table"]), p("Typenschild + Stern/Dreieck laut erklären", S["table"])],
        [p("8", S["table_bold"]), p("11", S["table_bold"]), p("Maschinen und Sicherheitstechnik", S["table"]), p("Not-Halt, Stoppkategorien, Prüfung", S["table"])],
        [p("9", S["table_bold"]), p("12 + 13 + 14", S["table_bold"]), p("PV/Speicher/E-Mobilität, Licht, Kommunikation", S["table"]), p("Normen-Update in 12 zuerst lesen", S["table"])],
        [p("10", S["table_bold"]), p("16 + 17 + 18 + 26 + 27", S["table_bold"]), p("VOB, Ex/EMV/GMA, MS, TK und Ergänzungen", S["table"]), p("Je Thema 5 Kernfragen", S["table"])],
        [p("11", S["table_bold"]), p("25 + 19 komplett + 21", S["table_bold"]), p("Planen, Rechnen, Grenzwerte", S["table"]), p("Werte-Spalte abdecken; Aufgaben unter Zeit", S["table"])],
        [p("12", S["table_bold"]), p("20 + 22", S["table_bold"]), p("Fachgespräch und Prüfungssimulation", S["table"]), p("Probeprüfung + mündlich mit Partner", S["table"])],
    ]
    story += [
        styled_table(plan, [16 * mm, 43 * mm, 64 * mm, 51 * mm], S),
        Spacer(1, 5 * mm),
        box(ar("إذا كان الوقت قصيرًا: ركّز أولًا على 01–11 و15 و19–22، ثم أضف 23–27 حسب نقاط ضعفك."), S["arabic"], PALE_ORANGE, ORANGE),
        PageBreak(),
    ]

    # Page 4 — active recall
    story += [
        p("Aktiv lernen statt nur lesen", S["h1"]),
        p("Eine Lerneinheit pro Thema (60–90 Minuten)", S["h2"]),
    ]
    cycle = [
        [p("1", S["center"]), p("Überblick · 5 min", S["table_bold"]), p("Nur Überschriften, blaue Kästen und Lernziel lesen.", S["table"])],
        [p("2", S["center"]), p("Verstehen · 25 min", S["table_bold"]), p("Abschnitt lesen; jeden gelben Begriff in eigenen Worten erklären.", S["table"])],
        [p("3", S["center"]), p("Abrufen · 15 min", S["table_bold"]), p("Grüne Antwort abdecken und die blaue Frage laut beantworten.", S["table"])],
        [p("4", S["center"]), p("Anwenden · 20 min", S["table_bold"]), p("Skizze, Messablauf, Rechenweg oder Praxisbeispiel ohne Vorlage.", S["table"])],
        [p("5", S["center"]), p("Fehlerliste · 5 min", S["table_bold"]), p("Nur Fehler notieren: Frage vorne, kurze Antwort + Quelle hinten.", S["table"])],
        [p("6", S["center"]), p("Mini-Prüfung · 10 min", S["table_bold"]), p("Drei Fragen aus Skript 20, Antwort nach dem 4-Schritte-Schema.", S["table"])],
    ]
    table = Table(cycle, colWidths=[12 * mm, 42 * mm, 120 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [table, Spacer(1, 6 * mm), p("Wiederholungsabstände", S["h2"])]
    intervals = [
        [p("Tag 0", S["center"]), p("direkt nach dem Lernen", S["table"])],
        [p("Tag 1", S["center"]), p("erste Wiederholung", S["table"])],
        [p("Tag 3", S["center"]), p("nur unsichere Karten", S["table"])],
        [p("Tag 7", S["center"]), p("gemischter Abruf", S["table"])],
        [p("Tag 14", S["center"]), p("unter Zeitdruck", S["table"])],
        [p("Tag 30", S["center"]), p("Prüfungssimulation", S["table"])],
    ]
    table = Table(intervals, colWidths=[29 * mm, 58 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("BACKGROUND", (0, 0), (0, -1), PALE_GREEN),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [
        table,
        Spacer(1, 6 * mm),
        box(ar("لا تعد قراءة كل شيء. أعد فقط الأسئلة التي أخطأت فيها، وبذلك تختصر الوقت وتثبت المعلومات."), S["arabic"], PALE_PURPLE, PURPLE),
        PageBreak(),
    ]

    # Page 5 — oral answer schema
    story += [
        p("Fachgespräch: Antworten in 4 Schritten", S["h1"]),
        p("Nutze immer dieselbe Struktur. Dadurch klingst du sicher und vergisst weniger.", S["body"]),
    ]
    answer_steps = [
        [p("1 · Begriff", S["white"]), p("Was ist es?", S["white"]), p("Ein kurzer, fachlich sauberer Satz.", S["white"])],
        [p("2 · Norm", S["table_bold"]), p("Wo ist es geregelt?", S["table"]), p("Norm oder Regelwerk nennen, wenn du sicher bist.", S["table"])],
        [p("3 · Wert / Ablauf", S["table_bold"]), p("Welche Zahl, Formel oder Reihenfolge?", S["table"]), p("Wert immer mit Einheit und Randbedingung.", S["table"])],
        [p("4 · Begründung", S["table_bold"]), p("Warum ist das notwendig?", S["table"]), p("Personenschutz, Brandschutz oder Betriebssicherheit.", S["table"])],
    ]
    table = Table(answer_steps, colWidths=[40 * mm, 55 * mm, 79 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("BACKGROUND", (0, 2), (-1, 2), ROW),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [
        table,
        Spacer(1, 8 * mm),
        p("Musterformulierung", S["h2"]),
        box("„Nach <b>[Norm]</b> gilt <b>[Regel/Wert mit Einheit]</b> unter der Bedingung <b>[Randbedingung]</b>. Der Zweck ist <b>[Personen-/Brand-/Betriebsschutz]</b>. In diesem Fall würde ich praktisch <b>[Maßnahme]</b> ausführen und dokumentieren.“", S["body"], PALE_GREEN, GREEN),
        Spacer(1, 6 * mm),
        p("Wenn du eine Zahl nicht sicher weißt", S["h2"]),
        box("Nicht raten. Sage: „Den exakten Einstellwert würde ich in der aktuellen Norm, der TAB des VNB bzw. im Herstellerzertifikat prüfen. Sicher ist: überwacht werden … und die Anlage muss bei unzulässigem Netzbetrieb sicher trennen.“", S["body"], PALE_ORANGE, ORANGE),
        Spacer(1, 6 * mm),
        p(ar("في الامتحان الشفهي: التعريف أولًا، ثم المعيار، ثم القيمة أو الخطوات، وأخيرًا سبب الحماية."), S["arabic"]),
        PageBreak(),
    ]

    # Page 6 — dependency and priority
    story += [
        p("Prioritäten und Themenabhängigkeiten", S["h1"]),
        p("Nicht alle Dateien haben dieselbe Priorität. Lerne zuerst die Themen, auf denen andere Themen aufbauen.", S["body"]),
    ]
    priorities = [
        [p("Priorität", S["white"]), p("Dateien", S["white"]), p("Warum", S["white"])],
        [p("A · Kern", S["table_bold"]), p("01–11, 15, 19–22", S["table_bold"]), p("Direkte Prüfungsbasis: Schutz, Dimensionierung, Prüfung, Maschinen, Arbeitsschutz, Rechnen und Fachgespräch.", S["table"])],
        [p("B · wichtig", S["table_bold"]), p("12–14, 16–18, 23–25", S["table_bold"]), p("Häufige Ergänzungs- und Planungsthemen; abhängig von den Grundlagen.", S["table"])],
        [p("C · vertiefen", S["table_bold"]), p("26–27", S["table_bold"]), p("Schließt Buchlücken; gezielt nach Schwäche und Prüfungsprofil lernen.", S["table"])],
    ]
    story += [styled_table(priorities, [28 * mm, 45 * mm, 101 * mm], S), Spacer(1, 7 * mm)]
    dependencies = [
        [p("Zuerst", S["white"]), p("Danach", S["white"]), p("Verbindung", S["white"])],
        [p("01", S["table_bold"]), p("alle", S["table_bold"]), p("Normen, Personen und Begriffe bilden die Sprache der Prüfung.", S["table"])],
        [p("02 → 03 → 04", S["table_bold"]), p("09, 19, 22", S["table_bold"]), p("Schutzprinzip → Schutzgerät → Leitung → Nachweis durch Messung/Rechnung.", S["table"])],
        [p("05 → 06", S["table_bold"]), p("08, 12, 25", S["table_bold"]), p("Erdung/PA → Netzanschluss/Zähler → Gebäude- und Energieplanung.", S["table"])],
        [p("10", S["table_bold"]), p("11", S["table_bold"]), p("Motor/Trafo verstehen, bevor Maschinen-Sicherheitstechnik gelernt wird.", S["table"])],
        [p("08", S["table_bold"]), p("23, 24, 25", S["table_bold"]), p("Planungsgrundlage → KNX, praktische Installation, vollständiges Projekt.", S["table"])],
        [p("07, 14, 15, 17, 18", S["table_bold"]), p("26, 27", S["table_bold"]), p("Ergänzungsdateien schließen Lücken, ersetzen aber nicht die Grundskripte.", S["table"])],
    ]
    story += [
        styled_table(dependencies, [35 * mm, 42 * mm, 97 * mm], S),
        Spacer(1, 6 * mm),
        box("<b>Abbruchregel:</b> Wenn du eine Frage nach 60 Sekunden nicht beantworten kannst, markiere sie. Lies nicht sofort fünf Seiten nach – prüfe erst die kurze Antwort, formuliere sie neu und wiederhole sie am nächsten Tag.", S["body"], PALE_BLUE, BLUE),
        PageBreak(),
    ]

    # Page 7 — file navigator
    story += [p("Dateinavigator – wofür ist welche Datei?", S["h1"])]
    groups = [
        [p("Gruppe", S["white"]), p("Dateien", S["white"]), p("Verwendung", S["white"])],
        [p("Orientierung", S["table_bold"]), p("00, 00b, 00c", S["table_bold"]), p("Plan, Quellenabgleich und dieser aktuelle Lernnavigator.", S["table"])],
        [p("Grundlagen", S["table_bold"]), p("01–06", S["table_bold"]), p("Recht, Schutz, Überstrom, Leitungen, Erdung und Netzanschluss.", S["table"])],
        [p("Anwendung", S["table_bold"]), p("07–11", S["table_bold"]), p("Sonderräume, Installation, Prüfung, Motoren und Maschinen.", S["table"])],
        [p("Ergänzung", S["table_bold"]), p("12–18", S["table_bold"]), p("Energie, Licht, Kommunikation, Arbeitsschutz, Betrieb und Spezialthemen.", S["table"])],
        [p("Trainieren", S["table_bold"]), p("19", S["table_bold"]), p("Rechenaufgaben erst selbst lösen; Lösung anschließend vergleichen.", S["table"])],
        [p("Abrufen", S["table_bold"]), p("20", S["table_bold"]), p("Frage lesen, grüne Antwort abdecken, laut antworten.", S["table"])],
        [p("Auswendig", S["table_bold"]), p("21", S["table_bold"]), p("Orange Wertespalte abdecken; Wert + Einheit + Quelle aufsagen.", S["table"])],
        [p("Simulieren", S["table_bold"]), p("22", S["table_bold"]), p("Unter Zeitdruck bearbeiten; erst danach Lösung öffnen.", S["table"])],
        [p("Buchlücken", S["table_bold"]), p("23–27", S["table_bold"]), p("KNX, Praxis, Projekt, Kabel/MS/Ersatzstrom, TK/Sonderräume/UVV.", S["table"])],
    ]
    story += [
        styled_table(groups, [32 * mm, 31 * mm, 111 * mm], S),
        Spacer(1, 7 * mm),
        p("Tägliche Auswahl", S["h2"]),
        box("<b>Montag–Donnerstag:</b> neues Thema · <b>Freitag:</b> Rechnen/Messen · <b>Samstag:</b> Fragen aus 20 + Werte aus 21 · <b>Sonntag:</b> frei oder nur Fehlerkarten.", S["body"], PALE_GREEN, GREEN),
        Spacer(1, 6 * mm),
        p(ar("استخدم الملف 20 للاختبار الشفهي، والملف 21 للأرقام، والملف 22 لمحاكاة الامتحان الكامل."), S["arabic"]),
        PageBreak(),
    ]

    # Pages 8–9 — glossary
    glossary = [
        ("Elektrofachkraft (EFK)", "شخص مختص كهربائيًا"),
        ("elektrotechnisch unterwiesene Person (EuP)", "شخص مُدرَّب كهربائيًا"),
        ("Basisschutz", "الحماية الأساسية من اللمس المباشر"),
        ("Fehlerschutz", "الحماية عند حدوث عطل"),
        ("Zusatzschutz", "حماية إضافية"),
        ("Schutzleiter (PE)", "موصل الحماية"),
        ("Neutralleiter (N)", "الموصل المحايد"),
        ("PEN-Leiter", "موصل يجمع الحماية والمحايد"),
        ("Fehlerstrom", "تيار العطل أو التسرب"),
        ("Fehlerstrom-Schutzeinrichtung (RCD)", "قاطع الحماية من تيار التسرب"),
        ("Leitungsschutzschalter (LS)", "قاطع حماية الخط"),
        ("Überlast", "تحميل زائد"),
        ("Kurzschluss", "قصر كهربائي"),
        ("Selektivität", "انتقائية الفصل"),
        ("Schleifenimpedanz", "ممانعة حلقة العطل"),
        ("Abschaltbedingung", "شرط الفصل الآمن"),
        ("Spannungsfall", "هبوط الجهد"),
        ("Strombelastbarkeit", "قدرة الموصل على حمل التيار"),
        ("Potentialausgleich", "ربط تساوي الجهد"),
        ("Erdungsanlage", "منظومة التأريض"),
        ("Haupterdungsschiene (HES)", "قضيب التأريض الرئيسي"),
        ("Hausanschlusskasten (HAK)", "صندوق توصيل المبنى بالشبكة"),
        ("Zählerplatz", "مكان العداد"),
        ("Technische Anschlussbedingungen (TAB)", "شروط التوصيل الفنية"),
        ("Verteilnetzbetreiber (VNB)", "مشغل شبكة التوزيع"),
        ("Besichtigen", "الفحص البصري"),
        ("Erproben", "الاختبار الوظيفي"),
        ("Messen", "القياس"),
        ("Prüfprotokoll", "محضر أو تقرير الفحص"),
        ("Gefährdungsbeurteilung", "تقييم المخاطر"),
        ("Not-Halt", "إيقاف طارئ لحركة خطرة"),
        ("Not-Aus", "فصل طارئ للطاقة"),
        ("Netz- und Anlagenschutz (NA-Schutz)", "حماية الشبكة والمنشأة"),
        ("Kuppelschalter", "قاطع فصل المنشأة عن الشبكة"),
        ("Blindleistung", "القدرة غير الفعالة"),
        ("Wirkleistung", "القدرة الفعالة"),
        ("Scheinleistung", "القدرة الظاهرية"),
        ("Fachgespräch", "المقابلة أو المناقشة الفنية الشفهية"),
        ("Prüfungsfalle", "خطأ شائع في الامتحان"),
        ("Grenzwert", "قيمة حدية"),
    ]
    for page_index, chunk in enumerate((glossary[:20], glossary[20:])):
        story += [
            p("Deutsch–Arabisch: zentrale Prüfungsbegriffe" + ("" if page_index == 0 else " (Fortsetzung)"), S["h1"]),
            p(ar("استخدم المصطلح الألماني في الامتحان، واستعمل الترجمة العربية فقط لفهم المعنى."), S["arabic"]),
        ]
        rows = [[p("Deutscher Fachbegriff", S["white"]), p(ar("المعنى بالعربية"), S["white"])]]
        for german, arabic in chunk:
            rows.append([p(german, S["table_bold"]), p(ar(arabic), S["arabic"])])
        story += [styled_table(rows, [95 * mm, 79 * mm], S), PageBreak()]

    # Page 10 — checklist and sources
    story += [
        p("Fortschrittskontrolle und Quellen", S["h1"]),
        p("Wöchentliche Checkliste", S["h2"]),
    ]
    checklist = [
        [p("☐", S["center"]), p("Ich kann die fünf wichtigsten Begriffe der Woche ohne Vorlage erklären.", S["body"])],
        [p("☐", S["center"]), p("Ich kann mindestens fünf Fragen aus Skript 20 laut beantworten.", S["body"])],
        [p("☐", S["center"]), p("Ich kenne die relevanten Werte mit Einheit und Randbedingung.", S["body"])],
        [p("☐", S["center"]), p("Ich habe mindestens eine Skizze, Messfolge oder Rechnung aus dem Kopf erstellt.", S["body"])],
        [p("☐", S["center"]), p("Meine Fehlerkarten sind an Tag 1, 3 und 7 wiederholt.", S["body"])],
        [p("☐", S["center"]), p("Ich kann eine Antwort mit Begriff – Norm – Wert/Ablauf – Begründung geben.", S["body"])],
    ]
    table = Table(checklist, colWidths=[12 * mm, 162 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [table, Spacer(1, 6 * mm), p("Geprüfte Primärquellen (Stand 01.10.2026)", S["h2"])]
    sources = [
        "VDE-AR-N 4100:2026-04 – VDE VERLAG: https://www.vde-verlag.de/normen/0100932/",
        "VDE-AR-N 4105:2026-03 – VDE VERLAG: https://www.vde-verlag.de/normen/0100940/",
        "DIN VDE 0100-701:2025-06 – VDE VERLAG: https://www.vde-verlag.de/normen/0100866/",
        "DIN VDE 0100-420:2022-06 – VDE VERLAG: https://www.vde-verlag.de/normen/0100688/",
        "DIN VDE 0100-560:2022-10 + Berichtigung 2023-10 – VDE VERLAG",
        "DIN 18014:2023-06 – DIN Media: https://www.dinmedia.de/en/standard/din-18014/367767975",
        "DGUV Information 203-006 – Elektrische Anlagen und Betriebsmittel auf Bau- und Montagestellen",
    ]
    for source in sources:
        story.append(p("• " + source, S["small"]))
    story += [
        Spacer(1, 5 * mm),
        box("<b>Wichtiger Hinweis:</b> Dieser Navigator ist eine Lern- und Orientierungshilfe. Er ersetzt weder den vollständigen Normtext noch TAB, Herstellerunterlagen, Gefährdungsbeurteilung oder fachliche Verantwortung.", S["body"], PALE_RED, RED),
        Spacer(1, 5 * mm),
        p(ar("الهدف من هذا الدليل هو تسهيل الدراسة، لكنه لا يستبدل النص الكامل للمعايير أو تعليمات مشغل الشبكة والشركة المصنعة."), S["arabic"]),
    ]
    return story


def build(output: Path) -> None:
    styles = build_styles()
    output.parent.mkdir(parents=True, exist_ok=True)
    document = NavigatorDocTemplate(
        str(output),
        styles,
        title="00c – Lernnavigator und Normen-Update 2026",
        author="Lernskript",
        subject="Meisterprüfung Elektrotechnik – Lernplan und fachliche Aktualisierung",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=17 * mm,
    )
    document.build(build_story(styles))

    # Add a compact, clickable outline after ReportLab has finished the pages.
    toc = [
        [1, "Start und Farbsystem", 1],
        [1, "Fachliche Aktualisierung", 2],
        [1, "12-Wochen-Lernplan", 3],
        [1, "Aktives Wiederholen", 4],
        [1, "Fachgespräch: 4-Schritte-Antwort", 5],
        [1, "Prioritäten und Abhängigkeiten", 6],
        [1, "Dateinavigator", 7],
        [1, "Deutsch-Arabisches Glossar", 8],
        [2, "Glossar – Fortsetzung", 9],
        [1, "Checkliste und Quellen", 10],
    ]
    pdf = pymupdf.open(output)
    pdf.set_toc(toc)
    pdf.xref_set_key(pdf.pdf_catalog(), "StudyReviewVersion", "(review-2026-10-01)")
    pdf.xref_set_key(pdf.pdf_catalog(), "StudyPaletteVersion", "(semantic-v2)")
    with tempfile.NamedTemporaryFile(
        prefix=f".{output.stem}-", suffix=".pdf", dir=output.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    pdf.save(temporary_path, garbage=0, deflate=True, clean=False)
    pdf.close()
    temporary_path.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path("00c_Lernnavigator_und_Normenupdate_2026.pdf"),
    )
    args = parser.parse_args()
    build(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
