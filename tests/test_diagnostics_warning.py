from __future__ import annotations

from loguru import logger

from mms_ok.diagnostics import log_warning


def test_log_warning_logs_message_and_origin():
    messages = []
    sink_id = logger.add(
        lambda message: messages.append(message.record["message"]),
        level="WARNING",
    )
    try:
        log_warning("compatibility warning")
    finally:
        logger.remove(sink_id)

    assert "compatibility warning" in messages
    assert any(
        message.startswith("Origin: ")
        and "test_diagnostics_warning.py" in message
        and "test_log_warning_logs_message_and_origin()" in message
        for message in messages
    )
