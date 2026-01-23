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

def format_number(
    value: float | Decimal,
    fmt: dict | None,
    include_symbol: bool = True,
    min_precision: int | None = None,
    precision: int | None = None,
    trim_trailing_to_min: bool = False,
) -> str:
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

    # Determine desired precision. If `precision` is provided, use it
    # exactly. Otherwise compute a precision that is the maximum of:
    # - the format's configured precision (fmt['precision'])
    # - the actual fractional digits present in the input value
    # - the optional `min_precision` requested by the caller
    # This preserves additional fractional digits while enforcing a
    # minimum number of decimals.
    s_raw = format(value.copy_abs(), "f")
    _, _, frac_raw = s_raw.partition(".")
    frac_len = len(frac_raw) if frac_raw else 0

    if precision is None:
        base_precision = fmt.get("precision", 2)
        if min_precision is not None:
            desired_precision = max(base_precision, min_precision, frac_len)
        else:
            desired_precision = max(base_precision, frac_len)
    else:
        desired_precision = precision

    # Quantize value to the desired precision using ROUND_HALF_UP, then
    # format as fixed-point.
    quant = Decimal(10) ** (-desired_precision)
    value = value.quantize(quant, rounding=ROUND_HALF_UP)
    # Check sign before taking absolute value
    neg = value < 0
    s = format(value.copy_abs(), "f")

    int_part, _, frac_part = s.partition(".")

    # If the caller did not request an exact `precision`, trim trailing
    # zeros from the fractional part while preserving at least the
    # minimum number of decimals (min_keep). This produces outputs like
    # `75.221,6953125000` -> `75.221,6953125` but keeps `77.869,00`.
    if precision is None and frac_part:
        base_precision = fmt.get("precision", 2)
        if trim_trailing_to_min:
            # Trim to the caller-requested minimum (but never less than 2)
            min_keep = max(2, min_precision or 0)
        else:
            min_keep = max(base_precision, min_precision or 0)

        # remove trailing zeros but keep at least min_keep digits
        while frac_part.endswith("0") and len(frac_part) > min_keep:
            frac_part = frac_part[:-1]

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
