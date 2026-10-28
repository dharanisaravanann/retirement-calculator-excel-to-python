"""Retirement balance projection: the Python rebuild of retirement_model.xlsx.

Illustrative model, not financial advice. It does not predict anything.

Calculation method (identical to the Excel model), for each year t = 1..N:
    contribution    = annual_contribution * (1 + contribution_growth) ** (t - 1)
    investment_return = (opening_balance + contribution) * expected_return
    fees            = (opening_balance + contribution + investment_return) * fee_rate
    closing_balance = opening_balance + contribution + investment_return - fees
The next year's opening balance is this year's closing balance.
N = retirement_age - current_age. Contributions are made at the start of
each year, so they earn a full year of return. Fees are charged at the end of
the year on the balance after returns.
"""

from dataclasses import dataclass

import pandas as pd

COLUMNS = [
    "Year",
    "Age",
    "Opening balance",
    "Contribution",
    "Investment return",
    "Fees",
    "Closing balance",
]


@dataclass(frozen=True)
class Inputs:
    current_age: int
    retirement_age: int
    starting_balance: float
    annual_contribution: float
    expected_return: float  # e.g. 0.07 for 7% a year
    fee_rate: float  # e.g. 0.01 for 1% of the balance a year
    contribution_growth: float  # e.g. 0.03 for contributions rising 3% a year

    def validate(self) -> None:
        if self.retirement_age <= self.current_age:
            raise ValueError("Retirement age must be greater than current age.")
        if self.starting_balance < 0 or self.annual_contribution < 0:
            raise ValueError("Balance and contribution cannot be negative.")
        if not 0 <= self.fee_rate < 1:
            raise ValueError("Fee rate must be between 0% and 100%.")
        if self.expected_return <= -1:
            raise ValueError("Expected return must be greater than -100%.")


def project(inputs: Inputs) -> pd.DataFrame:
    """Return the year-by-year projection table, one row per year."""
    inputs.validate()
    rows = []
    opening = inputs.starting_balance
    for year in range(1, inputs.retirement_age - inputs.current_age + 1):
        contribution = inputs.annual_contribution * (1 + inputs.contribution_growth) ** (year - 1)
        investment_return = (opening + contribution) * inputs.expected_return
        fees = (opening + contribution + investment_return) * inputs.fee_rate
        closing = opening + contribution + investment_return - fees
        rows.append([year, inputs.current_age + year - 1, opening, contribution, investment_return, fees, closing])
        opening = closing
    return pd.DataFrame(rows, columns=COLUMNS)


# The five reconciliation cases. Made-up example numbers, not real customer data.
# Shared by build_excel.py (writes them into the workbook) and test_reconciliation.py.
TEST_CASES = {
    "Base case": Inputs(30, 67, 50_000, 10_000, 0.07, 0.01, 0.03),
    "Zero return": Inputs(30, 67, 50_000, 10_000, 0.00, 0.01, 0.03),
    "Zero fees": Inputs(30, 67, 50_000, 10_000, 0.07, 0.00, 0.03),
    "High return": Inputs(30, 67, 50_000, 10_000, 0.12, 0.01, 0.03),
    "Late start": Inputs(55, 67, 0, 15_000, 0.07, 0.01, 0.03),
}
