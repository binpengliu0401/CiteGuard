"""Shared Temporal serialization configuration for project contracts."""

import os

from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)

TEMPORAL_ADDRESS = os.getenv(
    "CITEGUARD_TEMPORAL_ADDRESS",
    "localhost:7233",
)
TEMPORAL_TASK_QUEUE = os.getenv(
    "CITEGUARD_TASK_QUEUE",
    "citeguard",
)
TEMPORAL_DATA_CONVERTER = pydantic_data_converter
"""Converter that reconstructs nested dataclasses and string-valued Enums."""
TEMPORAL_WORKFLOW_RUNNER = SandboxedWorkflowRunner(
    restrictions=SandboxRestrictions.default.with_passthrough_modules(
        "annotated_types"
    )
)
"""Sandbox runner sharing Pydantic's lazily imported annotation dependency."""
