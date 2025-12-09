# Copilot instructions for hledger-lots

Quick context
- Purpose: a small CLI library to manage commodity lots (FIFO or AVERAGE COST) for hledger-style journals.
- Entrypoint: console script `hledger-lots` -> `hledger_lots.__main__:main` (see `pyproject.toml`).
- Python: requires >= 3.12 (see `pyproject.toml`).
- External runtime dependency: the `hledger` CLI is invoked via subprocess in `hledger_lots/hl.py` — available system `hledger` is required for `view`, `list` and other commands that query journal data.

What to know to be productive
- CLI wiring: `hledger_lots/cli.py` defines the Click commands. Use this file as the canonical layout for flags, defaults and help text (examples: `buy`, `sell`, `view`, `list`, `prices`).
- hledger integration: `hledger_lots/hl.py` shells out to `hledger -f <files> print --output-format=json` and then parses the JSON structure. Tests often construct small journal text and avoid invoking the real `hledger` by using monkeypatching — be careful when changing JSON parsing.
- Core utilities:
  - `hledger_lots/lib.py`: general helpers (precision/formatting helpers, command builders, default file resolution).
  - `hledger_lots/file_utils.py`: resolves `include` / `!include` directives and provides `format_number(value, fmt)` used to render commodity amounts. The `fmt` dict must include keys: `decimal_mark`, `thousands_sep`, `currency_symbol`, `currency_position`, `space`, `precision`.
  - `hledger_lots/avg.py`, `fifo.py`, `avg_info.py`, `fifo_info.py`: business logic for lot calculation and report generation.

Data and types
- Money and amounts: code uses `decimal.Decimal` semantics for money. Preserve exact arithmetic and use `ROUND_HALF_UP` where rounding occurs (see `file_utils.format_number`).
- Internal transaction types: structured dataclasses / typed tuples are used across modules (see `hledger_lots/types.py`). When producing or consuming these objects, follow the field names used in tests (for example `AdjustedTxn(date, price, base_cur, qtty, acct)`).

Tests and workflows
- Run tests: `pytest -q` at repository root. The project uses pytest and the tests live in `tests/`.
- Local CLI testing: install in editable mode and run CLI directly:

```bash
python -m pip install -e .
# or
pip install -e .

# then run the CLI (example)
python -m hledger_lots -f path/to/data.journal view AAPL
```

- When working on features that rely on `hledger` output, prefer creating unit tests that feed the expected JSON or text into the parsing functions rather than running the system `hledger` binary; `hl.py` expects a specific JSON shape — altering field names will break many tests.

Conventions and gotchas (project-specific)
- Module name mismatch: some older tests import `hledger_lots.files`. The project file is `file_utils.py`. A small shim `hledger_lots/files.py` is OK to add to preserve backwards compatibility.
- Formatting expectations: `format_number` expects `precision` in `fmt` and uses `decimal_mark` and `thousands_sep` semantics matching hledger's commodity directive. Tests and rendering rely on exact string output — changing formatting logic needs test updates.
- Default ledger file resolution: `lib.get_default_file()` will look at `$LEDGER_FILE` and `~/.hledger.journal`. Code paths that read from stdin use `lib.get_file_from_stdin()` which writes stdin to a temporary file.
- Command building: `lib.get_sell_comm(...)` creates a shell-ready `hledger-lots` invocation (via `shlex.join`). Use it when implementing programmatic workflows that need to spawn the CLI.

Editing and PR tips
- Keep changes small and verify tests: many modules are tightly coupled via the parsed hledger JSON shape. Update `tests/*` when modifying the parser.
- Preserve typing and dataclass shapes in `types.py` to avoid large cascaded test breakages.
- If changing rounding/formatting behavior, add golden-string tests around `file_utils.format_number` to lock the expected output.

Examples (concrete pointers)
- Where CLI flags are defined: `hledger_lots/cli.py` (see how `-f/--file`, `--avg-cost` and `--no-desc` are passed into `PromptBuy`/`PromptSell`).
- Where hledger JSON is parsed: `hledger_lots/hl.py` (functions: `hledger2txn`, `all_commodity_txns`, `prices_items2txn`).
- Number formatting: `hledger_lots/file_utils.py::format_number(value, fmt)` — ensure `fmt['precision']` exists and is an int.

If you break something
- Run `pytest -q` and inspect failing traces — many failures will clearly point to a mismatch in expected dataclass fields or JSON keys.
- For missing module errors like `hledger_lots.files`, add a one-line shim `hledger_lots/files.py` importing from `file_utils` rather than renaming tests.

When in doubt, ask:
- Which command are you trying to run? (CLI vs tests vs library import)
- Do you have a local `hledger` binary installed for full CLI testing?

---
Please review these instructions and tell me if you'd like me to:
- update tests to match `file_utils.py` instead of adding shims, or
- add the compatibility shim `hledger_lots/files.py` (I can add it now).
