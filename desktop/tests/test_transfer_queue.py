from threading import Event, Lock
from time import sleep

from plotdas_client.services import TransferQueue


def test_queue_deduplicates_and_prioritizes_foreground(qtbot):
    queue = TransferQueue(max_workers=1)
    blocker_started = Event()
    release_blocker = Event()
    order = []

    def blocker(progress, token):
        blocker_started.set()
        release_blocker.wait(2)
        return "blocker"

    def operation(name):
        def run(progress, token):
            order.append(name)
            return name

        return run

    queue.submit("blocker", "blocker", blocker, True)
    assert blocker_started.wait(1)
    low_id = queue.submit("low", "low", operation("low"), False)
    assert queue.submit("low", "low", operation("duplicate"), False) == low_id
    queue.submit("high", "high", operation("high"), True)
    release_blocker.set()
    qtbot.waitUntil(lambda: len(order) == 2, timeout=2000)
    assert order == ["high", "low"]
    queue.close()


def test_queue_never_exceeds_worker_limit(qtbot):
    queue = TransferQueue(max_workers=2)
    lock = Lock()
    active = 0
    maximum = 0
    completed = []
    queue.task_completed.connect(lambda event: completed.append(event.task_id))

    def operation(progress, token):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        sleep(0.08)
        with lock:
            active -= 1
        return True

    for index in range(5):
        queue.submit(str(index), str(index), operation, False)
    qtbot.waitUntil(lambda: len(completed) == 5, timeout=3000)
    assert maximum == 2
    queue.close()


def test_queued_prefetch_can_be_promoted(qtbot):
    queue = TransferQueue(max_workers=1)
    blocker_started = Event()
    release_blocker = Event()
    updates = []
    queue.task_updated.connect(updates.append)

    def blocker(progress, token):
        blocker_started.set()
        release_blocker.wait(2)

    queue.submit("blocker", "blocker", blocker, True)
    assert blocker_started.wait(1)
    task_id = queue.submit("image", "image", lambda progress, token: True, False)
    assert queue.promote(task_id)
    qtbot.waitUntil(
        lambda: any(event.task_id == task_id and event.foreground for event in updates), timeout=1000
    )
    release_blocker.set()
    queue.close()
