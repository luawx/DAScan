from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import count
from queue import PriorityQueue
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from plotdas_client.transport import (
    CancellationToken,
    ProgressCallback,
    TransferCancelled,
    TransferProgress,
)


@dataclass(slots=True)
class TransferTask:
    task_id: str
    key: str
    label: str
    operation: Callable[[ProgressCallback, CancellationToken], Any]
    foreground: bool
    priority: int
    token: CancellationToken = field(default_factory=CancellationToken)
    state: str = "queued"
    progress: TransferProgress | None = None
    version: int = 0


@dataclass(frozen=True, slots=True)
class TransferEvent:
    task_id: str
    key: str
    label: str
    foreground: bool
    state: str
    progress: TransferProgress | None = None
    result: Any = None
    error: str = ""
    details: str = ""


class TransferQueue(QObject):
    task_updated = Signal(object)
    task_completed = Signal(object)
    task_failed = Signal(object)

    def __init__(self, max_workers: int = 2, parent=None):
        super().__init__(parent)
        self.max_workers = max(1, max_workers)
        self._queue: PriorityQueue[tuple[int, int, str | None, int]] = PriorityQueue()
        self._sequence = count()
        self._tasks: dict[str, TransferTask] = {}
        self._by_key: dict[str, str] = {}
        self._lock = Lock()
        self._closed = False
        self._workers = [
            Thread(target=self._worker_loop, name=f"plotdas-transfer-{index + 1}", daemon=True)
            for index in range(self.max_workers)
        ]
        for worker in self._workers:
            worker.start()

    @staticmethod
    def _event(task: TransferTask, **changes: Any) -> TransferEvent:
        values = {
            "task_id": task.task_id,
            "key": task.key,
            "label": task.label,
            "foreground": task.foreground,
            "state": task.state,
            "progress": task.progress,
        }
        values.update(changes)
        return TransferEvent(**values)

    def submit(
        self,
        key: str,
        label: str,
        operation: Callable[[ProgressCallback, CancellationToken], Any],
        foreground: bool,
    ) -> str:
        with self._lock:
            if self._closed:
                raise RuntimeError("传输队列已关闭")
            existing_id = self._by_key.get(key)
            if existing_id:
                task = self._tasks[existing_id]
                if foreground and not task.foreground:
                    task.foreground = True
                    if task.state == "queued":
                        task.priority = 0
                        task.version += 1
                        self._queue.put((0, next(self._sequence), task.task_id, task.version))
                event = self._event(task)
                task_id = task.task_id
            else:
                task_id = uuid4().hex
                priority = 0 if foreground else 10
                task = TransferTask(task_id, key, label, operation, foreground, priority)
                self._tasks[task_id] = task
                self._by_key[key] = task_id
                self._queue.put((priority, next(self._sequence), task_id, task.version))
                event = self._event(task)
        self.task_updated.emit(event)
        return task_id

    def cancel(self, task_id: str) -> None:
        event: TransferEvent | None = None
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.state in {"completed", "failed", "cancelled"}:
                return
            task.token.cancel()
            if task.state == "queued":
                task.state = "cancelled"
                self._by_key.pop(task.key, None)
                event = self._event(task)
                self._tasks.pop(task.task_id, None)
        if event:
            self.task_updated.emit(event)

    def promote(self, task_id: str) -> bool:
        event: TransferEvent | None = None
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.state not in {"queued", "transferring"}:
                return False
            if not task.foreground:
                task.foreground = True
                if task.state == "queued":
                    task.priority = 0
                    task.version += 1
                    self._queue.put((0, next(self._sequence), task.task_id, task.version))
                event = self._event(task)
        if event:
            self.task_updated.emit(event)
        return True

    def _worker_loop(self) -> None:
        while True:
            _, _, task_id, version = self._queue.get()
            try:
                if task_id is None:
                    return
                with self._lock:
                    task = self._tasks.get(task_id)
                    if task is None or task.version != version or task.state != "queued":
                        continue
                    if task.token.cancelled:
                        task.state = "cancelled"
                        self._by_key.pop(task.key, None)
                        event = self._event(task)
                        self.task_updated.emit(event)
                        continue
                    task.state = "transferring"
                    event = self._event(task)
                self.task_updated.emit(event)

                def on_progress(progress: TransferProgress, current_task: TransferTask = task) -> None:
                    with self._lock:
                        current_task.progress = progress
                        progress_event = self._event(current_task)
                    self.task_updated.emit(progress_event)

                try:
                    result = task.operation(on_progress, task.token)
                    task.token.raise_if_cancelled()
                except TransferCancelled as exc:
                    with self._lock:
                        task.state = "cancelled"
                        self._by_key.pop(task.key, None)
                        cancelled_event = self._event(task, error=str(exc))
                        self._tasks.pop(task.task_id, None)
                    self.task_updated.emit(cancelled_event)
                except Exception as exc:
                    with self._lock:
                        task.state = "failed"
                        self._by_key.pop(task.key, None)
                        failed_event = self._event(task, error=str(exc), details=traceback.format_exc())
                        self._tasks.pop(task.task_id, None)
                    self.task_failed.emit(failed_event)
                else:
                    with self._lock:
                        task.state = "completed"
                        self._by_key.pop(task.key, None)
                        completed_event = self._event(task, result=result)
                        self._tasks.pop(task.task_id, None)
                    self.task_completed.emit(completed_event)
            finally:
                self._queue.task_done()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for task in self._tasks.values():
                if task.state in {"queued", "transferring"}:
                    task.token.cancel()
        for _ in self._workers:
            self._queue.put((1000, next(self._sequence), None, 0))
        for worker in self._workers:
            worker.join(timeout=1.0)
