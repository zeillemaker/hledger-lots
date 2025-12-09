import re
from typing import TypedDict


class CommodityTag(TypedDict):
    commodity: str
    value: str


def get_commodity_name(commodity_directive: str):
    commodity = re.sub(r"(\d[,\d.]*\d)|( )|\'|\"", "", commodity_directive)
    return commodity


def get_comment_tag_value(comment: str, tag: str) -> str:
    search = re.search(f"{tag}:\\s?(\\S+)", comment)
    if search and len(search.groups()) == 1:
        return search.group(1)
    else:
        return ""


class CommodityDirective:
    def __init__(self, files: tuple[str, ...]):
        self.files = files
        self.rows = self.get_commodities_rows()

    def get_commodities_rows(self) -> list[str]:
        rows = []
        for file in self.files:
            with open(file, "r") as f:
                for row in f:
                    if row.startswith("commodity"):
                        clean = row.replace("\t", "").rstrip()
                        rows.append(clean)
        return rows

    def get_commodity_tag(self, tag: str):
        regex = re.compile(r"commodity (.+)(;.+)")
        searches = (regex.search(row) for row in self.rows)
        commented_search = (
            search for search in searches if search and len(search.groups()) == 2
        )
        commodities = (
            CommodityTag(
                commodity=get_commodity_name(comment.group(1)),
                value=get_comment_tag_value(comment.group(2), tag),
            )
            for comment in commented_search
        )
        commodities = [
            commodity for commodity in commodities if "" not in commodity.values()
        ]

        return commodities

    def _all_lines_for_commodity(self, commodity: str):
        """Return all commodity directive lines matching the given commodity name."""
        result = []
        for row in self.rows:
            # Example row: "commodity EUR ; format €1.234,56"
            m = re.match(r"commodity\s+(.+?)(?:\s*;|$)", row)
            if m:
                comm = get_commodity_name(m.group(1)).upper()
                if comm == commodity.upper():
                    result.append(row)
        return result

    def get_format(self, commodity: str) -> dict:
        """
        Parse the commodity's format directive.
        Returns dict:
            decimal_mark, thousands_sep, currency_symbol, currency_position, space
        """
        lines = self._all_lines_for_commodity(commodity)
        fmt_line = None
        for line in lines:
            if line.strip().startswith("format"):
                fmt_line = line.strip()[6:].strip()
                break

        # Defaults
        fmt = {
            "decimal_mark": ".",
            "thousands_sep": ",",
            "currency_symbol": None,
            "currency_position": "right",
            "space": True,
        }

        if not fmt_line:
            return fmt

        # Match pattern like: 1.234,56 € or €1.234,56
        match = re.search(r'([^\d]*)([\d.,]+)\s*([^\d]*)', fmt_line)
        if match:
            left, number, right = match.groups()
            fmt["currency_symbol"] = (left or right or None).strip() or None
            fmt["currency_position"] = "left" if left else "right"

            if "," in number and "." in number:
                fmt["decimal_mark"] = ","
                fmt["thousands_sep"] = "."
            elif "," in number:
                fmt["decimal_mark"] = ","
                fmt["thousands_sep"] = ""
            else:
                fmt["decimal_mark"] = "."
                fmt["thousands_sep"] = ","

            fmt["space"] = bool(fmt["currency_symbol"])

        return fmt
