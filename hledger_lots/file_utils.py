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
