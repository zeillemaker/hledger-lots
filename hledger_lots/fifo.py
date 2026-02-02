import copy
import subprocess
from datetime import datetime
from decimal import Decimal
from textwrap import dedent

from . import checks
from .file_utils import format_number
from .lib import CostMethodError, adjust_commodity, get_avg_fifo
from .options import Options
from .utils import get_xirr
from .types import AdjustedTxn, Txn


def check_sell(sell: AdjustedTxn, previous_buys: list[AdjustedTxn], check: bool, options: Options | None = None):
    if not check:
        return

    diff_zero = [
        previous_buy for previous_buy in previous_buys if previous_buy.qtty != 0
    ]
    if len(diff_zero) == 0:
        return

    previous_buy = diff_zero[0]
    max_decimal = options.max_decimal_totalvalue_lots_sell if options else None
    if max_decimal is not None:
        sell_total = round(sell.price * abs(sell.qtty), max_decimal)
        buy_total = round(previous_buy.price * abs(sell.qtty), max_decimal)
        if sell_total != buy_total or sell.base_cur != previous_buy.base_cur:
            raise CostMethodError(sell, previous_buy.price, previous_buy.base_cur)
    else:
        if sell.price != previous_buy.price or sell.base_cur != previous_buy.base_cur:
            raise CostMethodError(sell, previous_buy.price, previous_buy.base_cur)


def get_lots(txns: list[AdjustedTxn], check: bool, options: Options | None = None) -> list[AdjustedTxn]:
    local_txns = copy.deepcopy(txns)
    checks.check_base_currency(txns)

    buys = [txn for txn in local_txns if txn.qtty >= 0]
    sells = [txn for txn in local_txns if txn.qtty < 0]

    buys_lot: list[AdjustedTxn] = buys if len(sells) == 0 else []
    for sell in sells:
        previous_buys = [txn for txn in buys if txn.date <= sell.date]
        checks.check_short_sell_past(previous_buys, sell)
        later_buys = [txn for txn in buys if txn.date > sell.date]
        sell_qtty = abs(sell.qtty)

        i = 0
        while i < len(previous_buys) and sell_qtty > 0:
            previous_buy = previous_buys[i]
            check_sell(sell, previous_buys, check, options)
            if sell_qtty >= previous_buy.qtty:
                sell_qtty -= previous_buy.qtty
                previous_buys[i].qtty = 0
            else:
                previous_buys[i].qtty -= sell_qtty
                sell_qtty = 0

            i += 1

        buys_lot = [*previous_buys, *later_buys]

    return buys_lot


def get_sell_lots(
    lots: list[AdjustedTxn], sell_date: str, sell_qtty: float, check: bool, options: Options | None = None
):
    checks.check_short_sell_current(lots, sell_qtty)
    buy_lots = get_lots(lots, check, options)
    previous_buys = [lot for lot in buy_lots.copy() if lot.date <= sell_date]

    fifo_lots: list[AdjustedTxn] = []
    # Use Decimal for exact arithmetic to avoid floating point errors
    sell_qtty_curr = Decimal(str(sell_qtty))

    i = 0
    while sell_qtty_curr > 0 and i < len(lots):
        buy = previous_buys[i]
        buy_qtty = Decimal(str(buy.qtty))
        
        if buy.qtty == 0:
            pass
        elif sell_qtty_curr > buy_qtty:
            fifo_lots.append(
                AdjustedTxn(buy.date, buy.price, buy.base_cur, buy.qtty, buy.acct)
            )
            sell_qtty_curr -= buy_qtty
        else:
            # Convert back to float for AdjustedTxn
            fifo_lots.append(
                AdjustedTxn(buy.date, buy.price, buy.base_cur, float(sell_qtty_curr), buy.acct)
            )
            sell_qtty_curr = Decimal(0)
        i += 1

    return fifo_lots


def txn2hl(
    txns: list[AdjustedTxn],
    date: str,
    cur: str,
    cash_account: str,
    revenue_account: str,
    value: float,
    commodity_directive=None,
):
    adj_comm = adjust_commodity(cur)
    base_curr = txns[0].base_cur
    fmt_cur = commodity_directive.get_format(cur) if commodity_directive else None
    fmt_base = commodity_directive.get_format(base_curr) if commodity_directive else None
    avg_cost = get_avg_fifo(txns)
    total_cost = sum(txn.qtty * txn.price for txn in txns)
    sum_qtty = sum(txn.qtty for txn in txns)
    price = value / sum_qtty
    dt = datetime.strptime(date, "%Y-%m-%d").date()
    xirr = get_xirr(price, dt, txns) or 0 * 100

    sum_qtty_fmt = format_number(sum_qtty, fmt_cur, include_symbol=False, min_precision=2)
    price_fmt = format_number(price, fmt_base, include_symbol=False, min_precision=2)

    txn_hl = dedent(f"""\
        {date} Sold {cur}  ; cost_method:fifo
            ; commodity:{cur}, qtty:{sum_qtty_fmt}, price:{price_fmt}
            ; avg_cost:{avg_cost:,.4f}, total_cost:{total_cost:.2f}, xirr:{xirr:.2f}% annual percent rate 30/360US
            {cash_account}  {format_number(value, fmt_base, include_symbol=False, precision=2)} {base_curr}
    """)

    for txn in txns:
        qty_fmt = format_number(txn.qtty * -1, fmt_cur, include_symbol=False, min_precision=2)
        total = txn.qtty * txn.price
        total_fmt = format_number(total, fmt_base, include_symbol=False, precision=2)
        txn_hl += f"        {txn.acct}    {qty_fmt} {adj_comm} @@ {total_fmt} {base_curr}  ; buy_date:{txn.date}, base_cur:{txn.base_cur}\n"

    txn_hl += f"    {revenue_account}   "
    comm = ["hledger", "-f-", "print", "--explicit"]
    txn_proc = subprocess.run(
        comm,
        input=txn_hl.encode(),
        capture_output=True,
    )
    txn_print: str = txn_proc.stdout.decode("utf8")
    return txn_print
