from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str, str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, function: Callable[[], Any]):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function()
        except Exception as exc:  # error is deliberately transported to the UI boundary
            self.signals.failed.emit(str(exc), traceback.format_exc())
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
