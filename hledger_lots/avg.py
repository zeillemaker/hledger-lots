import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from . import checks
from .file_utils import format_number
from .lib import CostMethodError, adjust_commodity
from .options import Options
from .utils import get_xirr
from .types import AdjustedTxn, Txn


@dataclass
class AvgCost:
    date: str
    total_qtty: float = 0
    total_amount: float = 0
    avg_cost: float = 0


def check_sell(sell: AdjustedTxn, avg_cost: float, check: bool, options: Options | None = None):
    if not check:
        return

    max_decimal = options.max_decimal_totalvalue_lots_sell if options else None
    
    if max_decimal is not None:
        # Use total value rounding instead of price precision
        sell_total = round(sell.price * abs(sell.qtty), max_decimal)
        avg_total = round(avg_cost * abs(sell.qtty), max_decimal)
        if sell_total != avg_total:
            raise CostMethodError(sell, avg_cost, sell.base_cur)
    else:
        # Original logic: compare prices with decimal precision
        decimals_price = Decimal(str(sell.price)).as_tuple().exponent
        decimals_avg = Decimal(str(avg_cost)).as_tuple().exponent
        if isinstance(decimals_price, int) and isinstance(decimals_avg, int):
            decimals = min(abs(decimals_price), abs(decimals_avg))
        else:
            raise ValueError("Not a decimal")

        if abs(sell.price - avg_cost) > 10 ** (-decimals):
            raise CostMethodError(sell, avg_cost, sell.base_cur)


def get_avg_cost(
    txns: list[AdjustedTxn], check: bool, until: date | None = None, options: Options | None = None
) -> list[AvgCost]:
    if until:
        included_txns = [
            txn
            for txn in txns
            if datetime.strptime(txn.date, "%Y-%m-%d").date() <= until
        ]
    else:
        included_txns = txns

    checks.check_base_currency(included_txns)

    total_qtty = 0
    total_amount = 0
    avg_cost = 0

    avg_costs: list[AvgCost] = []

    for txn in included_txns:
        total_qtty += txn.qtty

        if txn.qtty >= 0:
            total_amount += txn.qtty * txn.price
        else:
            check_sell(txn, avg_cost, check, options)
            total_amount += txn.qtty * avg_cost

        avg_cost = total_amount / total_qtty if total_qtty != 0 else 0
        avg_costs.append(AvgCost(txn.date, total_qtty, total_amount, avg_cost))

    return avg_costs


def avg_sell(
    txns: list[AdjustedTxn],
    date: str,
    qtty: float,
    cur: str,
    cash_account: str,
    revenue_account: str,
    comm_account: str,
    value: float,
    check: bool,
    options: Options | None = None,
):
    adj_comm = adjust_commodity(cur)
    checks.check_short_sell_current(txns, qtty)
    checks.check_base_currency(txns)
    checks.check_available(txns, comm_account, qtty)

    sell_date = datetime.strptime(date, "%Y-%m-%d").date()
    avg_cost = get_avg_cost(txns, check, options=options)
    cost = avg_cost[-1].avg_cost
    total_cost = cost * qtty

    base_curr = txns[0].base_cur
    price = value / qtty
    xirr = get_xirr(price, sell_date, txns) or 0 * 100

    qtty_fmt = format_number(qtty, None, include_symbol=False, min_precision=2)
    price_fmt = format_number(price, None, include_symbol=False, min_precision=2)
    qty_neg_fmt = format_number(qtty * -1, None, include_symbol=False, min_precision=2)

    txn_hl = f"""{date} Sold {cur}  ; cost_method:avg_cost
    ; commodity:{cur}, qtty:{qtty_fmt}, price:{price_fmt}
    ; avg_cost:{cost:.4f}, total_cost:{total_cost:.2f}, xirr:{xirr:.2f}% annual percent rate 30/360US
    {cash_account}    {value:.2f} {base_curr}
    {comm_account}    {qty_neg_fmt} {adj_comm} @ {cost} {base_curr}
    {revenue_account}    {format((-(Decimal(str(value)) - Decimal(str(cost)) * Decimal(str(qtty))).normalize()), 'f')} {base_curr}"""

    comm = ["hledger", "-f-", "print", "--explicit"]
    txn_proc = subprocess.run(comm, input=txn_hl.encode(), capture_output=True)

    txn_print: str = txn_proc.stdout.decode("utf8")
    return txn_print
