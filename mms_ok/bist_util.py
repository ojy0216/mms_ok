from bitslice import Bitslice
from rich.progress import Progress, MofNCompleteColumn, TimeRemainingColumn, TextColumn, BarColumn

wire_progress = Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeRemainingColumn(),
)

pipe_progress = Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeRemainingColumn(),
)

btpipe_progress = Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeRemainingColumn(),
)

trigger_progress = Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeRemainingColumn(),
)
