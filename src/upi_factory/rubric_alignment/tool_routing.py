from __future__ import annotations

from upi_factory.rubric_alignment.models import ToolRoute


def route_tool(trace_id: str, task: str) -> ToolRoute:
    considered = ["deterministic_assertions", "fake_llm_provider", "openai_live_provider", "retrieval_index", "human_review"]
    lower = task.lower()
    if "live" in lower:
        selected = "openai_live_provider"
        reason = "Selected only for explicitly approved live evaluation with environment key gate."
    elif "retrieve" in lower or "rag" in lower:
        selected = "retrieval_index"
        reason = "Selected because the task needs approved corpus citations."
    elif "unsafe" in lower or "ambiguous" in lower:
        selected = "human_review"
        reason = "Selected because the request needs escalation state."
    else:
        selected = "deterministic_assertions"
        reason = "Selected because deterministic checks cover the offline rubric evidence."
    rejected = {tool: "Not the narrowest fit for this task." for tool in considered if tool != selected}
    return ToolRoute(trace_id=trace_id, considered=considered, selected=selected, rejected=rejected, reason=reason)
