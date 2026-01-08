import os
import re
import shlex
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from .info import Info
from .types import AdjustedTxn, Txn

from pyxirr import DayCount, xirr
from tabulate import tabulate




class CostMethodError(Exception):
    def __init__(self, sell: AdjustedTxn, price: float, base_cur: str) -> None:
        self.message = f"Error in sale {sell}. Correct price should be {price} in currency {base_cur}"
        super().__init__(self.message)


def get_file_from_stdin():
    tmp_file = tempfile.NamedTemporaryFile(suffix=".journal", delete=False)
    name = tmp_file.name

    with open(tmp_file.name, "w") as f:
        for line in sys.stdin:
            f.write(line)

    return name


def get_default_file():
    ledger_file = os.getenv("LEDGER_FILE")
    if ledger_file:
        return (ledger_file,)

    default_path = Path.home() / ".hledger.journal"
    if default_path.exists():
        return (str(default_path),)





def get_avg_fifo(txns: list[AdjustedTxn]):
    total_qtty = sum(txn.qtty for txn in txns)
    if total_qtty == 0:
        return 0
    mult = [txn.qtty * txn.price for txn in txns]
    total_mult = sum(mult)
    avg = total_mult / total_qtty
    return avg


def dt_list2table(dt_list: list, tablefmt: str = "simple"):
    lots_dict = [asdict(dt) for dt in dt_list]
    table = tabulate(
        lots_dict,
        headers="keys",
        numalign="decimal",
        floatfmt=",.4f",
        tablefmt=tablefmt,
    )
    return table


def adjust_commodity(comm: str):
    has_non_word = re.search(r"\W", comm)
    adjusted = f'"{comm}"' if has_non_word else comm
    return adjusted


# Backwards-compatible wrapper for get_xirr (historically exposed from lib)
from .utils import get_xirr as _utils_get_xirr


def get_xirr(sell_price: float, sell_date: date, txns: list[AdjustedTxn]):
    return _utils_get_xirr(sell_price, sell_date, txns)


def get_sell_comm(
    commodity: str,
    no_desc: str,
    commodity_account: str,
    cash_account: str,
    revenue_account: str,
    date: str,
    quantity: float,
    price: float,
    avg_cost: bool,
):
    avg_comm = ["-g"] if avg_cost else []
    no_desc_comm = ["n", no_desc] if no_desc else []

    comm = [
        "hledger-lots",
        "sell",
        *avg_comm,
        *no_desc_comm,
        "-c",
        commodity,
        "-s",
        commodity_account,
        "-a",
        cash_account,
        "-r",
        revenue_account,
        "-d",
        date,
        "-q",
        str(quantity),
        "-p",
        str(price),
    ]
    comm_str: str = shlex.join(comm)

    return comm_str
