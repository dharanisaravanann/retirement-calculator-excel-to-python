"""macOS only: has Microsoft Excel calculate retirement_model.xlsx and exports the
values Excel computed to excel_outputs.csv.

This exists because openpyxl writes formulas but cannot calculate them. Running
this captures Excel's own numbers, so test_reconciliation.py compares Python
against real Excel output. The workbook is closed without being modified.
"""

import json
import subprocess
from pathlib import Path

import pandas as pd

from build_excel import FIRST_ROW, MAX_YEARS, OUTPUT
from model import COLUMNS, TEST_CASES

CSV_OUTPUT = "excel_outputs.csv"

JXA = """
function run(argv) {
    const excel = Application("Microsoft Excel");
    excel.open(Path(argv[0]));
    delay(2);
    excel.calculate();
    const wb = excel.activeWorkbook;
    const out = {};
    for (const name of JSON.parse(argv[1])) {
        out[name] = wb.worksheets[name].ranges[argv[2]].value();
    }
    wb.close({saving: "no"});
    return JSON.stringify(out);
}
"""


def main():
    path = str(Path(OUTPUT).resolve())
    cell_range = f"A{FIRST_ROW}:G{FIRST_ROW + MAX_YEARS - 1}"
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", JXA, path, json.dumps(list(TEST_CASES)), cell_range],
        capture_output=True, text=True, check=True,
    )
    frames = []
    for name, rows in json.loads(result.stdout).items():
        rows = [r for r in rows if r[0] != ""]  # drop blank rows past retirement
        frame = pd.DataFrame(rows, columns=COLUMNS)
        frame.insert(0, "Case", name)
        frames.append(frame)
    pd.concat(frames).to_csv(CSV_OUTPUT, index=False)
    print(f"Wrote Excel-calculated values for {len(frames)} cases to {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
