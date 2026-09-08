"""Public threat catalog for OSS/local mode.

Uses `threats/schema.py` (the shared contract) to give the basic engine
something concrete to validate. Scoped to what `BasicSupplyChainAgent` can
actually attempt — a full STRIDE catalog would leave most entries
permanently "untested" in local mode. Cloud's threat planner covers the
full technique set.
"""
from crucible.threats.schema import Threat

BASIC_THREATS = [
    Threat(
        id="basic-1",
        title="Unpinned third-party GitHub Action",
        technique="Tampering",
        description="A workflow step references an action by tag/branch instead of a commit SHA.",
        attack_plan=["supply_chain_basic"],
    ),
]
