"""Foundry — verified, infinite practice (SystemsDesign §6, architecture §18).

The LLM writes *generator code*, never questions. A generator is trusted only when
two independently written solvers agree across thousands of seeds, plus property
tests and hand-verified golden cases. This module is the deterministic core that
makes "free, unlimited, and provably correct" possible.
"""

from edgen.foundry.generator import (
    Answer,
    Distractor,
    Generator,
    Instance,
    ParamSpec,
)
from edgen.foundry.pool import InstancePool, PoolConfig
from edgen.foundry.registry import Foundry, generator
from edgen.foundry.verify import (
    GeneratorVerifier,
    VerificationReport,
    require_verified,
)

__all__ = [
    "Answer",
    "Distractor",
    "Generator",
    "Instance",
    "ParamSpec",
    "Foundry",
    "generator",
    "InstancePool",
    "PoolConfig",
    "GeneratorVerifier",
    "VerificationReport",
    "require_verified",
]
