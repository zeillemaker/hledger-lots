from datetime import datetime

from .avg import get_avg_cost
from .hl import hledger2txn
from .info import AllInfo, Info, LotsInfo
from .lib import dt_list2table
from .types import AdjustedTxn, Txn


class AvgInfo(Info):
    def __init__(
        self,
        journals: tuple[str, ...],
        commodity: str,
        txns_or_check: list[AdjustedTxn] | bool,
        check: bool | None = None,
        no_desc: str | None = None,
        commodity_directive=None,
    ):
        # Backwards-compatible constructor: either pass (journals, commodity, txns, check)
        # or the legacy form (journals, commodity, check) where txns will be fetched.
        if isinstance(txns_or_check, (list, tuple)):
            txns = txns_or_check
            if check is None:
                raise TypeError("missing required argument: 'check'")
            check_flag = check
        else:
            check_flag = bool(txns_or_check)
            txns = hledger2txn(journals, commodity)

        super().__init__(journals, commodity, txns, no_desc, commodity_directive)
        self.check = check_flag
        self.avg_lots = get_avg_cost(self.txns, self.check)
        self.table = dt_list2table(self.avg_lots)

    def get_info(self):
        if len(self.txns) == 0:
            return

        commodity = self.commodity
        cur = self.txns[0].base_cur
        qtty = self.avg_lots[-1].total_qtty
        amount = self.avg_lots[-1].total_amount
        avg_cost = self.avg_lots[-1].avg_cost
        last_buy_date = datetime.strptime(self.avg_lots[-1].date, "%Y-%m-%d").date()
        xirr = self.get_lots_xirr(last_buy_date)

        if self.market_price and self.market_date:
            market_price_str = f"{self.market_price:,.4f}"
            market_amount = self.market_price * qtty
            market_amount_str = f"{market_amount:,.2f}"
            market_profit = market_amount - amount
            market_profit_str = f"{market_profit:,.2f}"
            market_date = self.market_date.strftime("%Y-%m-%d")
            if xirr is not None:
                xirr_str = f"{xirr:,.4f}%"
            else:
                xirr_str = "N/A"
        else:
            market_amount_str = ""
            market_profit_str = ""
            market_date = ""
            market_price_str = ""
            xirr_str = "N/A"

        return LotsInfo(
            comm=commodity,
            cur=cur,
            qtty=str(qtty),
            amount=f"{amount:,.2f}",
            avg_cost=f"{avg_cost:,.4f}",
            mkt_price=market_price_str,
            mkt_amount=market_amount_str,
            mkt_profit=market_profit_str,
            mkt_date=market_date,
            xirr=xirr_str,
        )

    @property
    def info_txt(self):
        info = self.get_info()
        if not info:
            return f"No transaction for {self.commodity}"

        return self.get_info_txt(info)


class AllAvgInfo(AllInfo):
    def __init__(
        self,
        journals: tuple[str, ...],
        no_desc: str,
        all_txns: dict[str, list[AdjustedTxn]],
        check: bool,
        commodity_directive=None,
    ):
        super().__init__(journals, no_desc)
        self.commodity_directive = commodity_directive
        self.check = check
        self.all_txns = all_txns

    def get_info(self, commodity: str):
        avg_obj = AvgInfo(
            self.journals,
            commodity,
            self.all_txns[commodity.upper()],
            self.check,
            None,
            commodity_directive=getattr(self, "commodity_directive", None),
        )
        if len(avg_obj.txns) == 0:
            return
        else:
            return avg_obj.get_info()

    @property
    def infos(self):
        infos = [self.get_info(com) for com in self.commodities]
        infos = [info for info in infos if info]
        return infos

    @property
    def infos_with_qtty(self):
        result = []
        for x in self.infos:
            try:
                if float(x["qtty"]) > 0.0:
                    result.append(x)
            except Exception:
                continue
        return result

    def infos_table(self, output_format: str, exclude_no_quantity=False):
        if exclude_no_quantity:
            return self.get_infos_table(self.infos_with_qtty, output_format)
        return self.get_infos_table(self.infos, output_format)

    def infos_csv(self, exclude_no_quantity=False):
        if exclude_no_quantity:
            return self.get_infos_csv(self.infos_with_qtty)
        return self.get_infos_csv(self.infos)
