"""A thin wrapper around the ollama.chat function that logs requests and responses
to the `forbot` logger. The backend configures the log file via `backend/server.py`.
"""
from ollama import chat as _orig_chat
import logging

logger = logging.getLogger("forbot")


def _shorten(obj, max_chars=1000):
    try:
        s = str(obj)
    except Exception:
        return "<unserializable>"
    if len(s) > max_chars:
        return s[:max_chars] + "...[truncated]"
    return s


def chat(*args, **kwargs):
    # Log the request messages if present
    messages = kwargs.get("messages")
    if messages is not None:
        try:
            logger.info("LLM request messages: %s", _shorten(messages))
        except Exception:
            logger.info("LLM request messages: <failed to stringify>")

    # Call the real chat function
    result = _orig_chat(*args, **kwargs)

    # Try to extract the most likely response text
    resp_text = None
    try:
        # many clients expose .message.content
        resp_text = getattr(getattr(result, "message", None), "content", None)
    except Exception:
        resp_text = None

    if resp_text is None:
        # fallback to str(result)
        try:
            resp_text = str(result)
        except Exception:
            resp_text = "<unserializable>"

    logger.info("LLM response: %s", _shorten(resp_text))

    return result
