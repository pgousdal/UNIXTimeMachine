from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BrokerConfig:
    max_total_sessions: int = 4
    max_sessions_per_system: int = 2
    startup_timeout: float = 10.0
    readiness_timeout: float = 120.0
    idle_timeout: float = 1800.0
    absolute_timeout: float = 7200.0
    shutdown_timeout: float = 10.0
    system_limits: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> "BrokerConfig":
        path = root / "state" / "broker-config.json"
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = cls.__dataclass_fields__
        unknown = sorted(set(data) - set(allowed))
        if unknown:
            raise ValueError("unknown broker configuration keys: " + ", ".join(unknown))
        config = cls(**data)
        for name in ("max_total_sessions", "max_sessions_per_system"):
            if getattr(config, name) < 1:
                raise ValueError(f"{name} must be at least 1")
        for name in ("startup_timeout", "readiness_timeout", "idle_timeout",
                     "absolute_timeout", "shutdown_timeout"):
            if getattr(config, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if any(not isinstance(limit, int) or limit < 1 for limit in config.system_limits.values()):
            raise ValueError("all system_limits values must be positive integers")
        return config

    def as_dict(self):
        return asdict(self)

    def limit_for(self, system_id: str) -> int:
        return self.system_limits.get(system_id, self.max_sessions_per_system)
