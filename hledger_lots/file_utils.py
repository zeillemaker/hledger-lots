# hledger_lots/file_utils.py
from pathlib import Path
from .types import AdjustedTxn

def find_all_included_files(filename, seen=None):
    if seen is None:
        seen = set()

    filename = Path(filename).resolve()
    if filename in seen:
        return []
    seen.add(filename)

    files = [filename]
    try:
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("include ") or line.startswith("!include "):
                    included = line.split(maxsplit=1)[1]
                    included_path = (filename.parent / included).resolve()
                    files.extend(find_all_included_files(included_path, seen))
    except FileNotFoundError:
        pass

    return files

def format_number(value: float, fmt: dict) -> str:
    """
    Format a number according to a commodity's format.
    fmt should include:
        - decimal_mark: ',' or '.'
        - thousands_sep: '.' or ',' or "'"
        - currency_symbol: str or None
        - currency_position: 'left' or 'right'
        - space: bool
    """
    int_part, _, frac_part = f"{abs(value):.20f}".rstrip("0").rstrip(".").partition(".")

    # Add thousands separator
    int_part = f"{int(int_part):,}".replace(",", fmt["thousands_sep"])

    # Combine with decimal mark
    if frac_part:
        number = f"{int_part}{fmt['decimal_mark']}{frac_part}"
    else:
        number = int_part

    # Attach currency symbol
    if fmt.get("currency_symbol"):
        if fmt["currency_position"] == "left":
            number = f"{fmt['currency_symbol']}{' ' if fmt['space'] else ''}{number}"
        else:
            number = f"{number}{' ' if fmt['space'] else ''}{fmt['currency_symbol']}"

    # Add negative sign
    if value < 0:
        number = f"-{number}"

    return number
