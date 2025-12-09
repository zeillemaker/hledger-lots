"""Compatibility shim: historically tests and external code import `hledger_lots.files`.
This module re-exports the helpers implemented in `file_utils.py` to avoid breaking imports.
"""
from .file_utils import *

__all__ = [name for name in globals().keys() if not name.startswith("_")]
