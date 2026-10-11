"""Shipped Foundry generators (W0: five, DBMS + OS per SystemsDesign §12)."""
from __future__ import annotations

from .. import protocol  # noqa: F401
from .cpu_scheduling import CpuScheduling
from .page_replacement import PageReplacement
from .disk_scheduling import DiskScheduling
from .fd_closure import FdClosure
from .serializability import Serializability

__all__ = [
    "CpuScheduling",
    "PageReplacement",
    "DiskScheduling",
    "FdClosure",
    "Serializability",
]
