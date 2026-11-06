"""Read-only, consistently calculated financial exports. No database access here.

All formats receive the *same* period_data snapshot returned by the API; financial
aggregation remains centralized in app.main.totals().
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, KeepTogether

MIME_TYPES = {
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'pdf': 'application/pdf',
}
NAVY = '202C4B'
ACCENT = '4F46E5'
PALE = 'EEF2FF'
CURRENCY_FORMAT = '"₹"#,##0.00;[Red]("₹"#,##0.00)'


def money(value: str | Decimal) -> str:
    return f'₹{Decimal(value):,.2f}'


def report_name(report_type: str) -> str:
    return {'monthly': 'Monthly Financial Report', 'yearly': 'Yearly Financial Report',
            'custom': 'Custom Date Range Report', 'transactions': 'Transaction Report'}[report_type]


def month_totals(data: dict[str, Any]) -> list[tuple[str, Decimal, Decimal, Decimal]]:
    """Aggregate existing two transaction types without rounding or float conversion."""
    by_month: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {'income': Decimal('0.00'), 'expense': Decimal('0.00')})
    for item in data['transactions']:
        by_month[item.date.strftime('%Y-%m')][item.type] += item.amount
    begin = date.fromisoformat(data['start_date'])
    end = date.fromisoformat(data['end_date'])
    rows: list[tuple[str, Decimal, Decimal, Decimal]] = []
    y, m = begin.year, begin.month
    while (y, m) <= (end.year, end.month):
        entry = by_month[f'{y:04d}-{m:02d}']
        rows.append((f'{y:04d}-{m:02d}', entry['income'], entry['expense'],
                     entry['income'] - entry['expense']))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return rows


def has_months(data: dict[str, Any], report_type: str) -> bool:
    return report_type == 'yearly' or len(month_totals(data)) > 1


def transaction_rows(data: dict[str, Any]):
    for item in data['transactions']:
        yield (str(item.id), item.date, item.type.title(), item.category,
               item.description or '', item.amount)


def _safe_excel_text(cell, value: str):
    """Prevent spreadsheet formula execution from imported transaction text."""
    cell.value = value
    cell.data_type = 's'  # openpyxl otherwise converts leading '=' into formulas


def create_xlsx(data: dict[str, Any], report_type: str, generated: str) -> bytes:
    wb = Workbook()
    sheet = wb.active
    sheet.title = 'Financial Summary'
    sheet.merge_cells('A1:D1')
    sheet['A1'] = f'GharKhata | {report_name(report_type)}'
    sheet['A1'].font = Font(size=16, bold=True, color='FFFFFF')
    sheet['A1'].fill = PatternFill('solid', fgColor=NAVY)
    sheet['A1'].alignment = Alignment(vertical='center')
    sheet.row_dimensions[1].height = 34
    for idx, (label, val) in enumerate([
        ('Reporting period', f"{data['start_date']} to {data['end_date']}"),
        ('Generated (UTC)', generated),
        ('Transactions', len(data['transactions'])),
        ('Total income', Decimal(data['total_income'])),
        ('Total expenses', Decimal(data['total_expenses'])),
        ('Remaining balance', Decimal(data['remaining_balance'])),
    ], 3):
        sheet.cell(idx, 1, label).font = Font(bold=True, color=NAVY)
        value_cell = sheet.cell(idx, 2, val)
        if isinstance(val, Decimal):
            value_cell.number_format = CURRENCY_FORMAT
            value_cell.font = Font(bold=True, color=ACCENT)
    sheet['A10'] = 'Category-wise expenses'
    sheet['A10'].font = Font(bold=True, color=NAVY, size=12)
    sheet['A11'] = 'Category'
    sheet['B11'] = 'Amount (INR)'
    for i, row in enumerate(data['categories'], 12):
        _safe_excel_text(sheet.cell(i, 1), row['category'])
        amount = sheet.cell(i, 2, Decimal(row['amount']))
        amount.number_format = CURRENCY_FORMAT
    sheet.column_dimensions['A'].width = 28
    sheet.column_dimensions['B'].width = 36
    sheet.column_dimensions['C'].width = 18
    sheet.column_dimensions['D'].width = 16
    sheet.freeze_panes = 'A3'

    transactions = wb.create_sheet('Transactions')
    headings = ['Transaction ID', 'Date', 'Type', 'Category', 'Description', 'Amount (INR)']
    transactions.append(headings)
    for row_index, row in enumerate(transaction_rows(data), 2):
        for col_index, value in enumerate(row, 1):
            cell = transactions.cell(row_index, col_index)
            if col_index in (1, 3, 4, 5):
                _safe_excel_text(cell, str(value))
            else:
                cell.value = value
            if col_index == 2:
                cell.number_format = 'dd mmm yyyy'
            if col_index == 6:
                cell.number_format = CURRENCY_FORMAT
            if col_index == 5:
                cell.alignment = Alignment(wrap_text=True, vertical='top')
    for i, width in enumerate([39, 17, 16, 20, 65, 20], 1):
        transactions.column_dimensions[get_column_letter(i)].width = width
    transactions.freeze_panes = 'A2'
    transactions.auto_filter.ref = f'A1:F{max(2, transactions.max_row)}'
    transactions.sheet_view.showGridLines = False

    if has_months(data, report_type):
        monthly = wb.create_sheet('Monthly Breakdown')
        monthly.append(['Month', 'Income (INR)', 'Expenses (INR)', 'Balance (INR)'])
        for month, inc, exp, balance in month_totals(data):
            monthly.append([month, inc, exp, balance])
        for col in 'BCD':
            for cells in monthly.iter_cols(min_col=ord(col) - 64, max_col=ord(col) - 64, min_row=2):
                for cell in cells:
                    cell.number_format = CURRENCY_FORMAT
        for col in 'ABCD':
            monthly.column_dimensions[col].width = 22
        monthly.freeze_panes = 'A2'
    for ws in wb:
        for cell in ws[1]:
            cell.font = Font(name='Aptos', bold=True, color='FFFFFF', size=11 if ws != sheet else 16)
            cell.fill = PatternFill('solid', fgColor=NAVY)
        if ws != sheet:
            ws.row_dimensions[1].height = 27
        ws.sheet_properties.pageSetUpPr.fitToPage = True
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _set_cell_text(cell, text: str, *, bold: bool = False):
    cell.text = text
    for p in cell.paragraphs:
        for run in p.runs:
            run.font.size = Pt(8.5)
            run.font.name = 'Arial'
            run.bold = bold
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _docx_table(doc: Document, headers: list[str], rows: list[list[str]]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Light Shading Accent 1'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    widths = ({2: [3.0, 3.8], 4: [1.1, 1.9, 1.9, 1.9],
               5: [1.05, .82, 1.14, 2.72, 1.07]})[len(headers)]
    for i, width in enumerate(widths):
        table.columns[i].width = Inches(width)
    for i, heading in enumerate(headers):
        _set_cell_text(table.rows[0].cells[i], heading, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            _set_cell_text(cells[i], value)
    # Repeat header rows and prevent row splits for long tables.
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    trPr = table.rows[0]._tr.get_or_add_trPr()
    trPr.append(OxmlElement('w:tblHeader'))
    for row in table.rows:
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for i, cell in enumerate(row.cells):
            cell.width = Inches(widths[i])
    return table


def create_docx(data: dict[str, Any], report_type: str, generated: str) -> bytes:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(.75)
    section.bottom_margin = Inches(.75)
    section.left_margin = Inches(.65)
    section.right_margin = Inches(.65)
    normal = doc.styles['Normal']
    normal.font.name = 'Arial'
    normal.font.size = Pt(9)
    normal.font.color.rgb = RGBColor.from_string(NAVY)
    doc.add_heading(f'GharKhata | {report_name(report_type)}', 0)
    doc.add_paragraph(f"Period: {data['start_date']} to {data['end_date']}")
    doc.add_paragraph(f'Generated (UTC): {generated}')
    doc.add_heading('Financial summary', level=1)
    _docx_table(doc, ['Metric', 'Amount'], [
        ['Total income', money(data['total_income'])],
        ['Total expenses', money(data['total_expenses'])],
        ['Remaining balance', money(data['remaining_balance'])],
        ['Transactions', str(len(data['transactions']))],
    ])
    doc.add_heading('Expense categories', level=1)
    _docx_table(doc, ['Category', 'Amount'],
                [[r['category'], money(r['amount'])] for r in data['categories']] or [['No expenses in this period', '—']])
    if has_months(data, report_type):
        doc.add_heading('Monthly breakdown', level=1)
        _docx_table(doc, ['Month', 'Income', 'Expenses', 'Balance'], [
            [label, money(inc), money(exp), money(bal)] for label, inc, exp, bal in month_totals(data)])
    doc.add_heading('Transactions', level=1)
    doc.add_paragraph(f"{len(data['transactions'])} record(s) in selected period.")
    _docx_table(doc, ['Date', 'Type', 'Category', 'Description', 'Amount'], [
        [item.date.isoformat(), item.type.title(), item.category, item.description or '', money(item.amount)]
        for item in data['transactions']] or [['—', '—', '—', 'No transactions in this period', '—']])
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    footer.add_run('GharKhata  •  Private financial report  •  Page ')
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    footer._p.append(fld)
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def _pdf_fonts() -> bool:
    # Embedded open-source font carries ₹ and Unicode user-supplied descriptions.
    regular = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    bold = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    if not regular.exists() or not bold.exists():
        return False  # safe INR fallback when the host has no DejaVu fonts
    if 'GharDejaVu' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('GharDejaVu', str(regular)))
    if 'GharDejaVuBold' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('GharDejaVuBold', str(bold)))
    return True


def create_pdf(data: dict[str, Any], report_type: str, generated: str) -> bytes:
    unicode_font = _pdf_fonts()
    regular_font = 'GharDejaVu' if unicode_font else 'Helvetica'
    bold_font = 'GharDejaVuBold' if unicode_font else 'Helvetica-Bold'
    out = BytesIO()
    pdf = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=17*mm, bottomMargin=17*mm, title=report_name(report_type),
                            author='GharKhata')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='GharTitle', fontName=bold_font, fontSize=15,
                              leading=19, textColor=colors.HexColor('#'+NAVY), spaceAfter=9))
    styles.add(ParagraphStyle(name='GharHeading', fontName=bold_font, fontSize=10,
                              leading=15, textColor=colors.HexColor('#'+NAVY), spaceBefore=13, spaceAfter=6))
    styles.add(ParagraphStyle(name='GharCell', fontName=regular_font, fontSize=7, leading=10, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='GharHead', parent=styles['GharCell'], fontName=bold_font,
                              textColor=colors.white))
    styles.add(ParagraphStyle(name='GharNote', fontName=regular_font, fontSize=8, leading=12))

    def p(value, style='GharCell'):
        return Paragraph(escape(str(value) if unicode_font else str(value).replace('₹', 'INR ')).replace('\n', '<br/>'), styles[style])

    def tbl(headers, rows, widths):
        data_rows = [[p(h, 'GharHead') for h in headers]]
        data_rows += [[p(v) for v in row] for row in rows]
        table = LongTable(data_rows, colWidths=[mm*w for w in widths], repeatRows=1,
                          hAlign='LEFT', splitByRow=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#'+NAVY)),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F5FC')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEBELOW', (0, 0), (-1, 0), .5, colors.HexColor('#'+ACCENT)),
        ]))
        return table

    story = [p(f'GharKhata | {report_name(report_type)}', 'GharTitle'),
             p(f"Period: {data['start_date']} to {data['end_date']}", 'GharNote'),
             p(f'Generated (UTC): {generated}', 'GharNote'),
             p('Financial summary', 'GharHeading'),
             tbl(['Metric', 'Value'], [
                 ['Total income', money(data['total_income'])],
                 ['Total expenses', money(data['total_expenses'])],
                 ['Remaining balance', money(data['remaining_balance'])],
                 ['Transactions', str(len(data['transactions']))]], [58, 74]),
             p('Expense categories', 'GharHeading'),
             tbl(['Category', 'Amount'], [[r['category'], money(r['amount'])] for r in data['categories']]
                 or [['No expenses in this period', '—']], [58, 74])]
    if has_months(data, report_type):
        story += [p('Monthly breakdown', 'GharHeading'),
                  tbl(['Month', 'Income', 'Expenses', 'Balance'], [
                      [m, money(i), money(e), money(b)] for m, i, e, b in month_totals(data)], [37, 53, 53, 53])]
    story += [p('Transactions', 'GharHeading'),
              p(f"{len(data['transactions'])} record(s) in selected period.", 'GharNote'),
              tbl(['Date', 'Type', 'Category', 'Description', 'Amount'], [
                  [t.date.isoformat(), t.type.title(), t.category, t.description or '', money(t.amount)]
                  for t in data['transactions']] or [['—', '—', '—', 'No transactions in this period', '—']],
                  [27, 24, 36, 132, 48])]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular_font, 8)
        canvas.setFillColor(colors.HexColor('#64748B'))
        canvas.drawString(15*mm, 10*mm, 'GharKhata • Private household financial report')
        canvas.drawRightString(282*mm, 10*mm, f'Page {doc.page}')
        canvas.restoreState()

    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()


def build_export(data: dict[str, Any], kind: str, report_type: str) -> bytes:
    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    return {'xlsx': create_xlsx, 'docx': create_docx, 'pdf': create_pdf}[kind](data, report_type, generated)
