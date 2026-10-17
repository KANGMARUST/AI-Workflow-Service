"""Reported token totals for saved answers, not an external billing ledger."""
from sqlalchemy import select

from .database import ChatMessage

TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


def empty_totals():
    return {"assistant_messages": 0, "reported_messages": 0, "missing_usage_messages": 0,
            **{key: 0 for key in TOKEN_FIELDS}, "complete": True}


def add_usage(totals, usage):
    valid = {key: value for key, value in usage.items() if key in TOKEN_FIELDS and type(value) is int and value >= 0}
    totals["assistant_messages"] += 1
    if len(valid) == len(TOKEN_FIELDS):
        totals["reported_messages"] += 1
    else:
        totals["missing_usage_messages"] += 1
        totals["complete"] = False
    for key, value in valid.items():
        totals[key] += value


def usage_summary(session, chat_id=None):
    statement = select(ChatMessage.metadata_json).where(ChatMessage.role == "assistant")
    if chat_id is not None:
        statement = statement.where(ChatMessage.chat_id == chat_id)
    result = {"basis": "saved_answers", **empty_totals(), "by_model": []}
    models = {}
    for metadata in session.scalars(statement):
        metadata = metadata or {}
        usage = metadata.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        model = metadata.get("requested_model") or metadata.get("model") or "unknown"
        group = models.setdefault(model, {"model": model, **empty_totals()})
        add_usage(result, usage)
        add_usage(group, usage)
    result["by_model"] = [models[key] for key in sorted(models)]
    return result
