from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)


def _make_progress() -> Progress:
    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
    )


wire_progress = _make_progress()
pipe_progress = _make_progress()
btpipe_progress = _make_progress()
trigger_progress = _make_progress()
