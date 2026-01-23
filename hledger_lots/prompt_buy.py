import subprocess
from dataclasses import dataclass
from textwrap import dedent

import questionary

from . import prompt
from .info import LotsInfo


@dataclass
class BuyInfo(prompt.Tradeinfo):
    base_cur: str


def val_buy_qtty(answer: str):
    try:
        answer_float = float(answer)
    except ValueError:
        return "Invalid number"

    if answer_float <= 0:
        return "Quantity should be positive"

    return True


class PromptBuy(prompt.Prompt):
    def __init__(
        self,
        file: tuple[str, ...],
        avg_cost: bool,
        check: bool,
        no_desc: str | None = None,
        options: Options | None = None,
    ) -> None:
        super().__init__(file, avg_cost, check, no_desc, options)
        all_commodities_txt = self.run_hledger_no_query_desc("commodities")
        self.all_commodities = [
            com for com in all_commodities_txt.split("\n") if com != ""
        ]

        print(self.initial_info)
        self.info = self.get_info()
        self.last_purchase = self.get_last_purchase(self.info)

    def get_info(self):
        commodity = prompt.ask_commodities_text(self.all_commodities)
        info_not_found = LotsInfo(
            comm=commodity,
            cur="",
            qtty="0",
            amount="0",
            avg_cost="0",
            mkt_price=None,
            mkt_date=None,
            mkt_amount=None,
            mkt_profit=None,
            xirr=None,
        )
        info = next(
            (info for info in self.infos if info["comm"] == commodity), info_not_found
        )
        return info

    def ask_base_cur_text(self):
        if self.info["cur"] == "":
            answer: str = prompt.custom_autocomplete(
                "Base Currency", self.all_commodities
            ).ask()
        else:
            answer = self.info["cur"]
        return answer

    def ask_buy_qtty(self, info: LotsInfo):
        available = float(info["qtty"])

        answer_str: str = questionary.text(
            f"Quantity (available {available})",
            validate=val_buy_qtty,
            instruction="",
        ).ask()
        return answer_str

    def ask_commodity_account(self):
        accts_txt = self.run_hledger("accounts")
        accts = [acct for acct in accts_txt.split("\n") if acct != ""]
        answer: str = prompt.custom_autocomplete("Commodity Account", accts).ask()
        return answer

    def prompt(self):
        commodity = self.info["comm"]
        base_cur = self.ask_base_cur_text()
        sell_date = self.ask_date(self.last_purchase)
        qtty = float(self.ask_buy_qtty(self.info))
        price_str = self.ask_price(self.info)

        if price_str == "":
            value_str = self.ask_total(qtty, self.info)
            value = float(value_str)
            price = value / qtty
        else:
            price = float(price_str)
            value = qtty * price

        cash_acct = self.ask_cash_account()

        commodity_acct = self.ask_commodity_account()

        result = BuyInfo(
            date=sell_date,
            quantity=qtty,
            commodity=commodity,
            base_cur=base_cur,
            cash_account=cash_acct,
            commodity_account=commodity_acct,
            price=price,
            value=value,
        )
        return result

    def get_hl_txn(self):
        from hledger_lots.file_utils import format_number

        buy = self.prompt()

        # Get formatting options from self.options
        fmt = None
        precision = 2
        if self.options:
            # Try to get commodity-specific format, fallback to options
            try:
                fmt = self.commodity_directive.get_format(buy.base_cur)
            except Exception:
                pass
            if not fmt:
                fmt = {
                    "decimal_mark": self.options.decimal_mark or ".",
                    "thousands_sep": self.options.thousands_sep or "",
                    "currency_symbol": None,
                    "currency_position": "right",
                    "space": True,
                    "precision": self.options.max_decimal_totalvalue_lots_sell or 2,
                }
            if self.options.max_decimal_totalvalue_lots_sell is not None:
                precision = self.options.max_decimal_totalvalue_lots_sell
            else:
                precision = fmt.get("precision", 2)
        else:
            fmt = {
                "decimal_mark": ".",
                "thousands_sep": "",
                "currency_symbol": None,
                "currency_position": "right",
                "space": True,
                "precision": 2,
            }

        # Format asset quantity using format_number to respect decimal_mark and thousands_sep
        qty_str = format_number(buy.quantity, fmt, include_symbol=False, min_precision=2, precision=2)
        # Format total cost (value) using format_number
        total_cost_str = format_number(buy.value, fmt, include_symbol=False, min_precision=precision, precision=precision)
        neg_total_cost_str = format_number(-buy.value, fmt, include_symbol=False, min_precision=precision, precision=precision)

        # Compose the transaction using @@ totalcost
        txn_raw = dedent(f"""\
            {buy.date} Buy {buy.commodity}
                {buy.commodity_account}    {qty_str} {buy.commodity} @@ {total_cost_str} {buy.base_cur}
                {buy.cash_account}           {neg_total_cost_str} {buy.base_cur}
        """)

        return txn_raw
