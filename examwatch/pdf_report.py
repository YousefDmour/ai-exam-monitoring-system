"""Paginated session PDF with embedded Unicode fonts and Arabic shaping."""
import json
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape


def export_pdf(root, report_path, destination):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    import arabic_reshaper
    from bidi.algorithm import get_display

    root = Path(root).resolve()
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    fonts = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/arial.ttf',
             Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font = next((p for p in fonts if p.is_file()), None)
    if font is None:
        raise FileNotFoundError('A Unicode font is required (Arial on Windows or DejaVu Sans on Linux).')
    pdfmetrics.registerFont(TTFont('ExamWatch', str(font)))
    styles = getSampleStyleSheet()
    for name in ('Normal', 'Title', 'Heading1', 'Heading2'):
        styles[name].fontName = 'ExamWatch'
    styles['Normal'].fontSize, styles['Normal'].leading = 10, 16
    styles['Title'].textColor = colors.HexColor('#123451')
    styles.add(ParagraphStyle('RTL', parent=styles['Normal'], alignment=TA_RIGHT))

    def paragraph(value, style='Normal'):
        text = str(value)
        rtl = bool(re.search('[\u0600-\u06ff]', text))
        # Shape each line before escaping so user notes cannot inject markup.
        lines = [get_display(arabic_reshaper.reshape(line)) if rtl else line
                 for line in text.splitlines() or ['']]
        selected = ParagraphStyle('RTL-' + style, parent=styles[style], alignment=TA_RIGHT) if rtl else styles[style]
        return Paragraph('<br/>'.join(escape(line) for line in lines), selected)

    story = [paragraph('ExamWatch | Session report', 'Title'), Spacer(1, 16),
             paragraph(report.get('session_name') or report.get('session_id'), 'Heading1'), Spacer(1, 10)]
    events = report.get('events', [])
    metadata = [
        ('Session ID', report.get('session_id', '-')),
        ('Source', report.get('source_name', 'Camera')),
        ('Duration', f"{report.get('duration_seconds', 0):.1f} seconds"),
        ('Review episodes', len(events)),
        ('Calibration complete', str(report.get('calibration_complete', False))),
        ('Processing speed', f"{report.get('processing_fps', 0):.1f} frames/second"),
    ]
    table = Table([[paragraph(a), paragraph(b)] for a, b in metadata], colWidths=[145, 350])
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#edf3f8')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
                               ('TOPPADDING', (0, 0), (-1, -1), 9)]))
    story += [table, Spacer(1, 18), paragraph('Detection summary', 'Heading2')]
    for reason, count in report.get('confirmed_reason_counts', {}).items():
        story.append(paragraph(f'{reason}: {count}'))
    evaluation_path = root / 'outputs/evaluations' / (Path(report_path).stem + '_evaluation.json')
    if evaluation_path.is_file():
        try:
            evaluation = json.loads(evaluation_path.read_text(encoding='utf-8'))
            if evaluation.get('session_id') == report.get('session_id'):
                story += [Spacer(1, 14), paragraph('Independent interval evaluation', 'Heading2')]
                for name in ('precision', 'recall', 'f1'):
                    value = evaluation.get(name)
                    story.append(paragraph(name.upper() + ': ' + ('N/A' if value is None else f'{value:.1%}')))
                story.append(paragraph(f"IoU threshold: {evaluation.get('iou_threshold', .3)}. Reason-level interval matching, not overall cheating accuracy."))
        except (OSError, ValueError, TypeError, AttributeError):
            story.append(paragraph('Saved evaluation could not be read.'))
    story += [Spacer(1, 14), paragraph('Event timeline and reviewer notes', 'Heading2')]
    if not events:
        story.append(paragraph('No confirmed events in this session.'))
    for index, event in enumerate(events, 1):
        start = event.get('start_seconds', 0)
        end = event.get('end_seconds', event.get('last_signal_seconds', start))
        review = event.get('review', {})
        block = [Spacer(1, 12), paragraph(f'Event {index} | {start:.1f}s - {end:.1f}s', 'Heading2'),
                  paragraph(', '.join(event.get('reasons', []))),
                  paragraph('Review: ' + review.get('status', 'Unreviewed'))]
        if event.get('clip'):
            block.append(paragraph('Evidence clip: ' + Path(event['clip']).name))
        if event.get('screenshot'):
            path = Path(event['screenshot'])
            path = (path if path.is_absolute() else root / path).resolve()
            try:
                path.relative_to((root / 'outputs/screenshots').resolve())
                width, height = ImageReader(str(path)).getSize()
                scale = min(495 / width, 210 / height)
                block += [Spacer(1, 8), Image(str(path), width=width * scale, height=height * scale)]
            except (OSError, ValueError):
                block.append(paragraph('Screenshot unavailable.'))
        notes = review.get('notes') or 'No reviewer notes.'
        note_block = [Spacer(1, 6), paragraph('Reviewer notes:'), paragraph(notes)]
        if len(notes) < 500:
            story.append(KeepTogether(block + note_block))
        else:
            story += [KeepTogether(block)] + note_block
    story += [Spacer(1, 20), paragraph('Flags are observations for human review and do not establish cheating.')]

    def footer(canvas, doc):
        canvas.setFont('ExamWatch', 8)
        canvas.setFillColor(colors.HexColor('#62768a'))
        canvas.drawString(42, 25, 'ExamWatch | University project')
        canvas.drawRightString(553, 25, f'Page {doc.page}')

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(destination), pagesize=(595, 842), rightMargin=50,
                      leftMargin=50, topMargin=42, bottomMargin=48).build(
                          story, onFirstPage=footer, onLaterPages=footer)
    return destination
