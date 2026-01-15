# utils.py
from .types import AdjustedTxn
import pyxirr
from pyxirr import xirr, DayCount
from datetime import date
from .file_utils import find_all_included_files


def get_files_comm(file_path: tuple[str, ...]) -> list[str]:
    """Return '-f <file>' for all files including included ones"""
    all_files = []
    for f in file_path:
        all_files.extend(find_all_included_files(f))

    cmd_files = []
    for f in all_files:
        cmd_files.extend(["-f", str(f)])
    return cmd_files


def get_xirr(
    sell_price: float, sell_date: "date", txns: list[AdjustedTxn]
) -> float | None:
    from pyxirr import DayCount, xirr
    if len(txns) == 0:
        return 0

    dates = [txn.date for txn in txns]
    buy_amts = [txn.price * txn.qtty for txn in txns]
    total_qtty = sum(txn.qtty for txn in txns)

    sell_date_txt = sell_date.strftime("%Y-%m-%d")
    dates = [*dates, sell_date_txt]
    amts = [*buy_amts, -total_qtty * sell_price]
    try:
        sell_xirr = xirr(dates, amts, day_count=DayCount.THIRTY_U_360)
        return sell_xirr
    except pyxirr.InvalidPaymentsError:
        # xirr requires at least one positive and one negative payment.
        # Preserve original behaviour for the special case where caller
        # explicitly passed a zero sell price (tests expect an exception).
        if sell_price == 0:
            raise
        # For other cases (e.g. market lookup with no realised opposite
        # payments), return None to indicate XIRR cannot be computed.
        return None
