"""Extension point for SAP, Sage and other accounting systems.

A future adapter must return the same canonical columns as JDEOracleAdapter.
The analytical pipeline and dashboard do not need to change.
"""

from src.adapters.base import AccountingSourceAdapter
