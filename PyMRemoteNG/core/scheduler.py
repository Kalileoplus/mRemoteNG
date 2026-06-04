"""
Scheduler: esegue script/comandi su connessioni in orari programmati.
"""
from __future__ import annotations
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

SCHEDULER_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "PyMRemoteNG", "scheduler.json"
)


@dataclass
class ScheduledTask:
    id:            str
    name:          str
    command:       str
    target_hosts:  List[str]   # hostname o connection ID
    protocol:      str = "SSH2"
    schedule_type: str = "once"   # once | daily | weekly
    run_at:        str = ""       # ISO datetime (time component usato per daily/weekly)
    last_run:      str = ""
    last_result:   str = ""
    enabled:       bool = True

    def is_due(self) -> bool:
        if not self.enabled or not self.run_at:
            return False
        try:
            run_dt = datetime.fromisoformat(self.run_at)
            now    = datetime.now()
            if self.schedule_type == "once":
                return not self.last_run and now >= run_dt
            target = now.replace(
                hour=run_dt.hour, minute=run_dt.minute, second=0, microsecond=0
            )
            if self.schedule_type == "daily":
                if self.last_run:
                    return datetime.fromisoformat(self.last_run).date() < now.date() \
                           and now >= target
                return now >= target
            if self.schedule_type == "weekly":
                if self.last_run:
                    diff = (now - datetime.fromisoformat(self.last_run)).days
                    return diff >= 7 and now >= target
                return now >= target
        except Exception:
            pass
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "command": self.command,
            "target_hosts": self.target_hosts, "protocol": self.protocol,
            "schedule_type": self.schedule_type, "run_at": self.run_at,
            "last_run": self.last_run, "last_result": self.last_result,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(d: dict) -> "ScheduledTask":
        return ScheduledTask(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name", ""),
            command=d.get("command", ""),
            target_hosts=d.get("target_hosts", []),
            protocol=d.get("protocol", "SSH2"),
            schedule_type=d.get("schedule_type", "once"),
            run_at=d.get("run_at", ""),
            last_run=d.get("last_run", ""),
            last_result=d.get("last_result", ""),
            enabled=d.get("enabled", True),
        )


class TaskScheduler:
    _instance: Optional["TaskScheduler"] = None

    def __init__(self):
        self._tasks: List[ScheduledTask] = []
        self._timer: Optional[threading.Timer] = None
        self._execute_cb: Optional[Callable[["ScheduledTask"], None]] = None
        self.load()

    @classmethod
    def get_instance(cls) -> "TaskScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_execute_callback(self, cb: Callable[["ScheduledTask"], None]):
        self._execute_cb = cb

    def load(self):
        if not os.path.exists(SCHEDULER_PATH):
            return
        try:
            with open(SCHEDULER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._tasks = [ScheduledTask.from_dict(d) for d in data.get("tasks", [])]
        except Exception:
            pass

    def save(self):
        os.makedirs(os.path.dirname(SCHEDULER_PATH), exist_ok=True)
        with open(SCHEDULER_PATH, "w", encoding="utf-8") as f:
            json.dump({"tasks": [t.to_dict() for t in self._tasks]}, f, indent=2)

    def all(self) -> List[ScheduledTask]:
        return list(self._tasks)

    def add(self, name: str, command: str, target_hosts: List[str],
            protocol: str, schedule_type: str, run_at: str) -> ScheduledTask:
        t = ScheduledTask(
            id=str(uuid.uuid4()), name=name, command=command,
            target_hosts=target_hosts, protocol=protocol,
            schedule_type=schedule_type, run_at=run_at,
        )
        self._tasks.append(t)
        self.save()
        return t

    def update(self, task_id: str, **kwargs):
        t = next((x for x in self._tasks if x.id == task_id), None)
        if t:
            for k, v in kwargs.items():
                if hasattr(t, k):
                    setattr(t, k, v)
            self.save()

    def delete(self, task_id: str):
        self._tasks = [t for t in self._tasks if t.id != task_id]
        self.save()

    def mark_ran(self, task_id: str, result: str):
        t = next((x for x in self._tasks if x.id == task_id), None)
        if t:
            t.last_run    = datetime.now().isoformat(timespec="seconds")
            t.last_result = result
            self.save()

    def start(self):
        self._tick()

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _tick(self):
        for task in list(self._tasks):
            if task.is_due() and self._execute_cb:
                try:
                    self._execute_cb(task)
                except Exception:
                    pass
        self._timer = threading.Timer(60.0, self._tick)
        self._timer.daemon = True
        self._timer.start()
