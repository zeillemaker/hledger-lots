# hledger_lots/file_utils.py
from pathlib import Path
from .types import AdjustedTxn
from decimal import Decimal, ROUND_HALF_UP

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

def format_number(value: float | Decimal, fmt: dict | None, include_symbol: bool = True) -> str:
    """
    Format a number according to a commodity's format (hledger semantics).

    Required fmt keys (will be defaulted if missing):
        decimal_mark, thousands_sep, currency_symbol, currency_position, space, precision
    """
    # Default format (used when no commodity format directive exists)
    if fmt is None:
        fmt = {
            "decimal_mark": ".",
            "thousands_sep": ",",
            "currency_symbol": None,
            "currency_position": "right",
            "space": True,
            "precision": 2,
        }

    # Convert to Decimal early to preserve exactness
    if not isinstance(value, Decimal):
        value = Decimal(str(value))

    # Use the full precision supplied by the Decimal (do not quantize)
    # Format as fixed-point to preserve all fractional digits from source
    s = format(value.copy_abs(), "f")
    neg = s.startswith("-")
    if neg:
        s = s[1:]

    int_part, _, frac_part = s.partition(".")

    # Add thousands separator if requested
    thousands = fmt.get("thousands_sep", "")
    if thousands:
        int_part_rev = int_part[::-1]
        grouped = [int_part_rev[i : i + 3] for i in range(0, len(int_part_rev), 3)]
        int_part = thousands.join(grouped)[::-1]

    # Recombine number with decimal mark (preserve all fractional digits)
    if frac_part:
        number = f"{int_part}{fmt.get('decimal_mark', '.')}{frac_part}"
    else:
        number = int_part


    # Apply currency symbol if present and requested
    sym = fmt.get("currency_symbol")
    if include_symbol and sym:
        if fmt.get("currency_position", "right") == "left":
            number = f"{sym}{' ' if fmt.get('space') else ''}{number}"
        else:
            number = f"{number}{' ' if fmt.get('space') else ''}{sym}"

    # Reapply negative sign
    if neg:
        number = f"-{number}"

    return number
