# hledger_lots/types.py
from dataclasses import dataclass

@dataclass
class AdjustedTxn:
    date: str
    price: float
    base_cur: str
    qtty: float
    acct: str

@dataclass
class Txn(AdjustedTxn):
    type: str
