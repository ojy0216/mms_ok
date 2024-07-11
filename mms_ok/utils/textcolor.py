from dataclasses import dataclass


@dataclass(frozen=True)
class TextColor:
    red = "\u001b[31m"
    green = "\u001b[32m"
    yellow = "\u001b[33m"
    orange = "\u001b[38;5;208m"
    blue = "\u001b[34m"
    magenta = "\u001b[35m"
    cyan = "\u001b[36m"
    white = "\u001b[37m"
    reset = "\u001b[0m"
