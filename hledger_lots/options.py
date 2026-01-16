from dataclasses import dataclass


NAMESPACE = "hledger-lots"
REQUIRED_KEYS = {"avg_cost", "check", "no_desc"}
OPTIONAL_KEYS = {"decimal_mark", "thousands_sep"}


@dataclass
class Options:
    avg_cost: bool
    check: bool
    no_desc: str
    decimal_mark: str | None = None
    thousands_sep: str | None = None


class OptionError(BaseException):
    TEMPLATE = """Copy/Paste the text below to the journal, changing values according to the need

#+hledger-lots avg_cost:false, check:true
#+hledger-lots no_desc:
    """

    def __init__(self, message: str) -> None:
        self.message = f"\n\n{message}\n\n{self.TEMPLATE}"
        super().__init__(self.message)


class HledgerVars:
    NAMESPACE_START = "#+"

    def __init__(self, files: tuple[str, ...]):
        self.files = files
        self.vars: dict[str, str] = {}

    def get_var_tuple(self, var_str: str):
        var_key_value = var_str.split(":", 1)
        if len(var_key_value) == 0:
            return None

        key = var_key_value[0].strip(" \n")
        value = var_key_value[1].strip().strip('"')
        result = (key, value)
        return result

    def get_row_vars(self, row: str, namespace: str):
        start = self.NAMESPACE_START + namespace
        if not row.startswith(start):
            return

        vars_str = row[len(start) :]
        if len(vars_str) == 0:
            return

        import re
        vars_list = re.findall(r'(\w+):\s*([^,]*)', vars_str)
        vars_dict = {key: value.strip().strip('"') for key, value in vars_list}
        return vars_dict

    def get_file_vars(self, file: str, namespace: str):
        result: dict[str, str] = {}
        with open(file, "r") as f:
            for row in f:
                row_vars = self.get_row_vars(row, namespace)
                if row_vars:
                    result = {**result, **row_vars}

            return result

    def get_namespace_vars(self, namespace: str):
        result: dict[str, str] = {}
        for file in self.files:
            file_vars = self.get_file_vars(file, namespace)
            if file_vars:
                result = {**result, **file_vars}

        self.var = result
        return result

    def get(self, key: str, default: str | None = None):
        if not self.vars:
            return default

        try:
            value = self.vars[key]
        except KeyError:
            value = default

        return value


def get_options(files: tuple[str, ...]):
    hledger_vars = HledgerVars(files)
    vars = hledger_vars.get_namespace_vars(NAMESPACE)
    existing_keys = set(vars.keys())
    missing = REQUIRED_KEYS.difference(existing_keys)

    if len(missing) > 0:
        raise OptionError(f"Missing keys {missing}")

    errors = ""
    if vars["avg_cost"] not in ["true", "false"]:
        errors += 'avg_cost should be "true" or "false"\n'

    if vars["check"] not in ["true", "false"]:
        errors += 'check should be "true" or "false"\n'

    if errors != "":
        raise OptionError(errors)

    avg_cost = True if vars["avg_cost"] == "true" else False
    check = True if vars["check"] == "true" else False
    no_desc = vars["no_desc"]
    decimal_mark = vars.get("decimal_mark")
    thousands_sep = vars.get("thousands_sep")
    return Options(avg_cost, check, no_desc, decimal_mark, thousands_sep)
