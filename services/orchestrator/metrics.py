from services.orchestrator.validation_wrapper import wrap_tool_call
from services.orchestrator.metrics import ORCH_TOOL_CALLS, ORCH_TOOL_LATENCY

from prometheus_client import Counter, Histogram

ORCH_TOOL_CALLS = Counter(
    "orch_tool_calls_total",
    "Tool calls by persona, tool and status",
    ["persona","tool","status"]
)

ORCH_TOOL_LATENCY = Histogram(
    "orch_tool_latency_seconds",
    "Latency per tool endpoint",
    ["tool"]
)
