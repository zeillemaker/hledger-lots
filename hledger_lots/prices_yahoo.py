import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yfinance as yf
from requests.exceptions import HTTPError

from .commodity_tag import CommodityDirective, CommodityTag
from .hl import hledger2txn
from .info import get_last_price
from .utils import get_files_comm
from .file_utils import find_all_included_files

@dataclass
class Price:
    name: str
    date: date
    price: float
    cur: str


class YahooPrices:
    TAG = "yahoo_ticker"

    def __init__(self, files: tuple[str, ...]) -> None:
        self.files = files
        self.files_comm = get_files_comm(files)

        self.today = datetime.today()
        yesterday = self.today - timedelta(days=1)
        self.yesterday_str = yesterday.strftime("%Y-%m-%d")

        all_files = []
        for f in self.files:
            all_files.extend(find_all_included_files(f))
        commodity_directive = CommodityDirective(all_files)
        self.commodities = commodity_directive.get_commodity_tag(self.TAG)



    def get_start_date(self, commodity: CommodityTag):
        txns = hledger2txn(self.files, commodity["commodity"])

        qtty = sum(txn.qtty for txn in txns)

        if qtty == 0:
            print(
                f"; stderr: No transaction for {commodity['commodity']}. Not downloading ",
                file=sys.stderr,
            )
            return

        first_date_str = txns[0].date
        first_date = datetime.strptime(first_date_str, "%Y-%m-%d").date()
        last_market_date = get_last_price(self.files_comm, commodity["commodity"])[0]

        if not last_market_date:
            last_date = first_date
        elif last_market_date < first_date:
            last_date = first_date
        else:
            last_date = last_market_date

        start_date = last_date + timedelta(days=1)
        past = date.today() - start_date
        if past.days < 1:
            print(f"; stderr: No new data for {commodity}", file=sys.stderr)
            return

        return start_date

    def prices2hledger(self, prices: list[Price]):
        prices_list = [
            f"P {price.date.strftime('%Y-%m-%d')} {price.name} {format(price.price, ',.20f').rstrip("0").replace(',', 'X').replace('.', ',').replace('X', '.')} {price.cur}"
            for price in prices
        ]
        return "\n".join(prices_list)

    def get_prices(
        self,
        commodity: CommodityTag,
        start_date: str,
    ) -> list[Price]:
        """
        Robustly fetch OHLC history for `commodity['value']` using yfinance.
        Returns a list[Price]. Writes short debug notes to stderr.
        """
        # debug: show which ticker we try to download
        print(f"; stderr: get_prices: ticker={commodity['value']}, start_date={start_date}", file=sys.stderr)

        # create ticker object (yfinance accepts a session param in recent versions)
        try:
            ticker = yf.Ticker(commodity["value"])
        except Exception as exc:
            print(f"; stderr: failed to construct yf.Ticker for {commodity['value']}: {exc}", file=sys.stderr)
            return []

        # Try to fetch some metadata (may be empty depending on yfinance version / rate limits)
        info = {}
        try:
            info = ticker.info or {}
        except Exception as exc:
            # non-fatal: we can still attempt history even if info fails
            print(f"; stderr: ticker.info failed for {commodity['value']}: {exc}", file=sys.stderr)

        # If start_date is falsy bail out
        if not start_date:
            print(f"; stderr: get_prices: no start_date for {commodity}", file=sys.stderr)
            return []

        # history may raise or return an empty DataFrame — handle both
        try:
            df = ticker.history(start=start_date, end=self.yesterday_str, raise_errors=False)
        except Exception as exc:
            print(f"; stderr: history() raised for {commodity['value']}: {exc}", file=sys.stderr)
            return []

        if df is None or df.empty:
            print(f"; stderr: history empty for {commodity['value']} between {start_date} and {self.yesterday_str}", file=sys.stderr)
            return []

        # normalize DataFrame access: prefer 'Close' column; fall back gracefully
        close_col = None
        for candidate in ("Close", "Adj Close", "close", "adjclose"):
            if candidate in df.columns:
                close_col = candidate
                break
        if close_col is None:
            # maybe single-column dataframe with numeric values
            if df.shape[1] == 1:
                close_col = df.columns[0]
            else:
                print(f"; stderr: no Close column for {commodity['value']}; columns={list(df.columns)}", file=sys.stderr)
                return []

        currency = info.get("currency") if isinstance(info, dict) else None
        if not currency:
            # default/fallback
            currency = "USD"

        prices: list[Price] = []
        # iterate rows using .itertuples for speed/clarity
        try:
            for idx, row in df.iterrows():
                # idx is a Timestamp — convert to date
                try:
                    dt = idx.to_pydatetime().date()
                except Exception:
                    try:
                        dt = datetime.strptime(str(idx), "%Y-%m-%d").date()
                    except Exception:
                        # skip if we can't parse the date
                        continue

                try:
                    close_value = float(row[close_col])
                except Exception:
                    # sometimes row is a scalar if single-col df; handle that
                    try:
                        close_value = float(row)
                    except Exception:
                        continue

                prices.append(Price(commodity["commodity"], dt, close_value, currency))
        except Exception as exc:
            print(f"; stderr: error iterating result for {commodity['value']}: {exc}", file=sys.stderr)
            return []

        # debug: how many prices found
        print(f"; stderr: get_prices: found {len(prices)} rows for {commodity['value']}", file=sys.stderr)
        return prices


    def get_commodity_prices(self, commodity: CommodityTag):
        """
        Wrapper that determines start_date and returns list[Price] or None.
        """
        start_date = self.get_start_date(commodity)
        if not start_date:
            return None

        start_date_str = start_date.strftime("%Y-%m-%d")
        try:
            prices = self.get_prices(commodity, start_date_str)
            if not prices:
                # debug: explicit message if prices empty
                print(f"; stderr: no prices returned for {commodity['value']}", file=sys.stderr)
            return prices
        except HTTPError:
            print(f"; stderr: {commodity['value']} not found (HTTPError)", file=sys.stderr)
        except Exception as exc:
            print(
                f"; stderr: Nothing downloaded for {commodity['value']} between {start_date} and {self.yesterday_str}: {exc}",
                file=sys.stderr,
            )

    def print_prices(self):
        if len(self.commodities) == 0:
            print(
                f"\n\n; stderr: No commodities directives with tag {self.TAG}",
                file=sys.stderr,
            )
            return

        for commodity in self.commodities:
            prices = self.get_commodity_prices(commodity)
            if prices:
                print("\n")
                hledger_prices = self.prices2hledger(prices)
                print(hledger_prices)
