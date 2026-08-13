from __future__ import annotations

from collections.abc import Callable


class SimhMonitorShutdownDriver:
    """Qualified SIMH monitor-entry/prompt/quit state owned by the adapter."""

    def __init__(self, spec: dict[str, object]):
        self.enter = bytes.fromhex(str(spec["monitor_enter_hex"]))
        self.prompt = bytes.fromhex(str(spec["monitor_prompt_hex"]))
        self.quit = bytes.fromhex(str(spec["monitor_quit_hex"]))
        self.may_already_be_active = bool(spec.get("monitor_may_already_be_active"))
        self.monitor_already_active = False
        self.live_tail = b""
        self.shutdown_tail = b""

    def begin(self, send: Callable[[bytes], None], log: Callable[[str], None]) -> str:
        if self.may_already_be_active and self.monitor_already_active:
            log("monitor already active; fresh prompt previously observed")
            send(self.quit)
            log("quit sent")
            return "exit"
        send(self.enter)
        log("Ctrl-E sent")
        self.shutdown_tail = b""
        return "monitor"

    def observe(self, data: bytes, ready: bool, phase: str | None,
                send: Callable[[bytes], None], log: Callable[[str], None]) -> str | None:
        if self.may_already_be_active and ready and phase is None:
            self.live_tail = (self.live_tail + data)[-4096:]
            if self.prompt in self.live_tail:
                self.monitor_already_active = True
                log("fresh live monitor prompt observed")
        if phase == "monitor":
            self.shutdown_tail = (self.shutdown_tail + data)[-4096:]
            if self.prompt in self.shutdown_tail:
                log("monitor prompt observed")
                send(self.quit)
                log("quit sent")
                return "exit"
        return phase

    def invalidate_on_input(self) -> None:
        if self.may_already_be_active:
            self.monitor_already_active = False
            self.live_tail = b""

    @staticmethod
    def timeout_reason(phase: str | None) -> str:
        if phase == "monitor":
            return "SIMH monitor entry unconfirmed; process left running for inspection"
        return "safe shutdown unconfirmed; process left running for inspection"


def shutdown_driver(spec: dict[str, object]) -> SimhMonitorShutdownDriver:
    kind = spec.get("driver", "simh-monitor")
    if kind == "simh-monitor":
        return SimhMonitorShutdownDriver(spec)
    raise RuntimeError(f"unsupported shutdown driver: {kind!r}")
