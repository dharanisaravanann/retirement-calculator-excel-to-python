"""Builds retirement_model.xlsx: an Inputs sheet plus one projection sheet per case.

Every projection cell is a live Excel formula that reads the Inputs sheet, so the
workbook works on its own: change an input in Excel and the table recalculates.
openpyxl writes formulas but cannot calculate them, so after running this,
open the file in Excel and save it once (or run export_excel_values.py) so
the calculated values are stored for test_reconciliation.py to read.
"""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from model import COLUMNS, TEST_CASES

OUTPUT = "retirement_model.xlsx"
MAX_YEARS = 80  # projection rows per sheet; years beyond retirement show blank
FIRST_ROW = 5  # first data row on projection sheets (row 4 is the header)

# Inputs sheet layout: row number for each assumption.
INPUT_ROWS = {
    "current_age": 4,
    "retirement_age": 5,
    "starting_balance": 6,
    "annual_contribution": 7,
    "expected_return": 8,
    "fee_rate": 9,
    "contribution_growth": 10,
}
LABELS = {
    "current_age": "Current age",
    "retirement_age": "Retirement age",
    "starting_balance": "Starting balance ($)",
    "annual_contribution": "Annual contribution, year 1 ($)",
    "expected_return": "Expected annual return",
    "fee_rate": "Annual fee (% of balance)",
    "contribution_growth": "Contribution growth rate",
}
YEARS_ROW = 11
RESULT_ROW = 13

TITLE = Font(bold=True, size=14)
BOLD = Font(bold=True)
NOTE = Font(italic=True, color="666666")
HEADER_FILL = PatternFill("solid", fgColor="DCE6F1")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")  # yellow = editable input
MONEY = '"$"#,##0.00'
PCT = "0.00%"


def build_inputs(ws):
    ws.title = "Inputs"
    ws["A1"] = "Retirement Balance Calculator: Inputs"
    ws["A1"].font = TITLE
    ws["A2"] = "Illustrative model, not financial advice. Made-up example numbers. Yellow cells are inputs."
    ws["A2"].font = NOTE
    ws["A3"] = "Assumption"
    ws["A3"].font = BOLD
    ws.column_dimensions["A"].width = 34

    for col, (name, inputs) in enumerate(TEST_CASES.items(), start=2):
        letter = get_column_letter(col)
        ws.column_dimensions[letter].width = 16
        head = ws.cell(row=3, column=col, value=name)
        head.font = BOLD
        head.fill = HEADER_FILL
        head.alignment = Alignment(horizontal="center")
        for field, row in INPUT_ROWS.items():
            cell = ws.cell(row=row, column=col, value=getattr(inputs, field))
            cell.fill = INPUT_FILL
            if field in ("starting_balance", "annual_contribution"):
                cell.number_format = MONEY
            elif field in ("expected_return", "fee_rate", "contribution_growth"):
                cell.number_format = PCT
        ws.cell(row=YEARS_ROW, column=col, value=f"={letter}{INPUT_ROWS['retirement_age']}-{letter}{INPUT_ROWS['current_age']}")
        sheet = f"'{name}'"
        last = FIRST_ROW + MAX_YEARS - 1
        result = ws.cell(
            row=RESULT_ROW, column=col,
            value=f"=INDEX({sheet}!$G${FIRST_ROW}:$G${last},{letter}{YEARS_ROW})",
        )
        result.number_format = MONEY
        result.font = BOLD

    for field, row in INPUT_ROWS.items():
        ws.cell(row=row, column=1, value=LABELS[field])
    ws.cell(row=YEARS_ROW, column=1, value="Years to retirement (calculated)")
    ws.cell(row=RESULT_ROW, column=1, value="Balance at retirement").font = BOLD


def build_projection(wb, name, col):
    ws = wb.create_sheet(name)
    letter = get_column_letter(col)

    def inp(field):
        return f"Inputs!${letter}${INPUT_ROWS[field]}"

    years = f"Inputs!${letter}${YEARS_ROW}"
    ws["A1"] = f"Year-by-year projection: {name}"
    ws["A1"].font = TITLE
    ws["A2"] = ("Illustrative model, not financial advice. Closing = (opening + contribution) x (1 + return), "
                "then fees deducted as a % of that balance.")
    ws["A2"].font = NOTE
    for c, header in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=4, column=c, value=header)
        cell.font = BOLD
        cell.fill = HEADER_FILL
        ws.column_dimensions[get_column_letter(c)].width = 8 if c <= 2 else 18
    ws.freeze_panes = "A5"

    for r in range(FIRST_ROW, FIRST_ROW + MAX_YEARS):
        if r == FIRST_ROW:
            year = f'=IF(1<={years},1,"")'
            opening = f'=IF(A{r}="","",{inp("starting_balance")})'
        else:
            year = f'=IF(A{r-1}="","",IF(A{r-1}+1<={years},A{r-1}+1,""))'
            opening = f'=IF(A{r}="","",G{r-1})'
        formulas = [
            year,
            f'=IF(A{r}="","",{inp("current_age")}+A{r}-1)',
            opening,
            f'=IF(A{r}="","",{inp("annual_contribution")}*(1+{inp("contribution_growth")})^(A{r}-1))',
            f'=IF(A{r}="","",(C{r}+D{r})*{inp("expected_return")})',
            f'=IF(A{r}="","",(C{r}+D{r}+E{r})*{inp("fee_rate")})',
            f'=IF(A{r}="","",C{r}+D{r}+E{r}-F{r})',
        ]
        for c, formula in enumerate(formulas, start=1):
            cell = ws.cell(row=r, column=c, value=formula)
            if c >= 3:
                cell.number_format = MONEY


def main():
    wb = Workbook()
    build_inputs(wb.active)
    for col, name in enumerate(TEST_CASES, start=2):
        build_projection(wb, name, col)
    wb.save(OUTPUT)
    print(f"Wrote {OUTPUT} (formulas only; open and save in Excel to store calculated values)")


if __name__ == "__main__":
    main()
