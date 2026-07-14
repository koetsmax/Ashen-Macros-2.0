import threading
from collections.abc import Callable
from typing import Any


def run_background(fn: Callable[..., Any], *args, **kwargs) -> None:
    threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()
