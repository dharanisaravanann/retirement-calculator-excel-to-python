"""Reconciles the Python model against the Excel model across 5 test cases.

Excel values come from retirement_model.xlsx itself when it has been saved in
Excel (so it stores calculated values); otherwise from excel_outputs.csv, which
export_excel_values.py captures from Excel. Every cell of every year is compared.

Run with:  python test_reconciliation.py   (prints a report)
      or:  pytest test_reconciliation.py
"""

from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from build_excel import FIRST_ROW, OUTPUT
from export_excel_values import CSV_OUTPUT
from model import COLUMNS, TEST_CASES, project

TOLERANCE = 0.01  # dollars
MONEY_COLUMNS = COLUMNS[2:]


def load_excel_values() -> dict:
    """Return {case name: DataFrame of Excel's calculated projection}."""
    wb = openpyxl.load_workbook(OUTPUT, data_only=True)
    if wb["Base case"].cell(row=FIRST_ROW, column=1).value is not None:
        tables = {}
        for name in TEST_CASES:
            rows = [r for r in wb[name].iter_rows(min_row=FIRST_ROW, max_col=7, values_only=True)
                    if r[0] not in (None, "")]
            tables[name] = pd.DataFrame(rows, columns=COLUMNS)
        return tables
    if not Path(CSV_OUTPUT).exists():
        raise FileNotFoundError(
            f"{OUTPUT} has no calculated values. Open and save it in Excel, "
            f"or run export_excel_values.py to create {CSV_OUTPUT}."
        )
    csv = pd.read_csv(CSV_OUTPUT)
    return {name: g.drop(columns="Case").reset_index(drop=True) for name, g in csv.groupby("Case")}


def compare(name: str, excel: pd.DataFrame) -> dict:
    python = project(TEST_CASES[name])
    assert len(python) == len(excel), f"{name}: {len(python)} Python rows vs {len(excel)} Excel rows"
    assert (python[["Year", "Age"]].values == excel[["Year", "Age"]].values).all(), f"{name}: year/age mismatch"
    diff = (python[MONEY_COLUMNS] - excel[MONEY_COLUMNS].astype(float)).abs()
    return {
        "Case": name,
        "Years": len(python),
        "Python final balance": python["Closing balance"].iloc[-1],
        "Excel final balance": float(excel["Closing balance"].iloc[-1]),
        "Max abs difference": diff.values.max(),
    }


EXCEL = load_excel_values()


@pytest.mark.parametrize("name", list(TEST_CASES))
def test_python_matches_excel(name):
    result = compare(name, EXCEL[name])
    assert result["Max abs difference"] < TOLERANCE


if __name__ == "__main__":
    report = pd.DataFrame([compare(name, EXCEL[name]) for name in TEST_CASES])
    pd.set_option("display.width", 120)
    print(report.to_string(index=False, formatters={
        "Python final balance": "${:,.2f}".format,
        "Excel final balance": "${:,.2f}".format,
        "Max abs difference": "{:.2e}".format,
    }))
    worst = report["Max abs difference"].max()
    status = "PASS" if worst < TOLERANCE else "FAIL"
    print(f"\nMaximum difference across all cases, years and columns: ${worst:.2e} "
          f"(tolerance ${TOLERANCE}) -> {status}")
