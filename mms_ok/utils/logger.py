import inspect
import logging
import os

from .textcolor import TextColor


def get_caller_info() -> str:
    """
    Get information about the caller of the current function.

    Args:
        None

    Returns:
        str: A string containing the name of the current function, the name of the caller file, and the line number of the caller.
    """
    stack = inspect.stack()
    current_frame = stack[2]
    caller_frame = stack[3]

    current_function_name = current_frame.function
    caller_file_name = os.path.basename(caller_frame.filename)
    caller_lineno = caller_frame.lineno

    return f"{current_function_name} <= {caller_file_name}:{caller_lineno}"


def log(msg: str, logging_level: int) -> None:
    """
    Logs a message with the specified logging level.

    Args:
        msg (str): The message to be logged.
        logging_level (int): The logging level to use. Must be one of the following.

            - logging.DEBUG
            - logging.INFO
            - logging.WARNING
            - logging.ERROR
            - logging.CRITICAL

    Raises:
        ValueError: If an invalid logging level is provided.

    Returns:
        None
    """
    if logging_level not in {
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    }:
        raise ValueError("Invalid logging level provided!")

    if logging_level == logging.DEBUG:
        logging.debug(msg=msg, extra={"prefix": get_caller_info()})
        return
    if logging_level == logging.INFO:
        logging.info(msg=msg, extra={"prefix": get_caller_info()})
        return
    if logging_level == logging.WARNING:
        print(TextColor.yellow, end="", flush=True)
        logging.warning(msg=msg, extra={"prefix": get_caller_info()})
    elif logging_level == logging.ERROR:
        print(TextColor.orange, end="", flush=True)
        logging.error(msg=msg, extra={"prefix": get_caller_info()})
    elif logging_level == logging.CRITICAL:
        print(TextColor.red, end="", flush=True)
        logging.critical(msg=msg, extra={"prefix": get_caller_info()})
    print(TextColor.reset, end="", flush=True)
