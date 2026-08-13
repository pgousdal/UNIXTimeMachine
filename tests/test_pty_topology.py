import os
import pty
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker.supervisor import configure_controlling_terminal


SIMH_CONSOLE_MODEL = r"""
import os, signal, termios, time

command_tty = termios.tcgetattr(0)
run_tty = list(command_tty)
run_tty[3] &= ~(termios.ECHO | termios.ICANON)
run_tty[1] &= ~termios.OPOST
run_tty[0] &= ~termios.ICRNL
run_tty[6] = list(command_tty[6])
run_tty[6][termios.VINTR] = 5
run_tty[6][termios.VMIN] = 0
run_tty[6][termios.VTIME] = 0
signal.signal(signal.SIGINT, lambda *_: os.write(1, b'FRESH sim>'))
termios.tcsetattr(0, termios.TCSAFLUSH, run_tty)
try:
    foreground = os.tcgetpgrp(0)
except OSError:
    foreground = -1
os.write(1, ('READY tty=%s sid=%d pgrp=%d fg=%d isig=%d\n' %
    (os.ttyname(0), os.getsid(0), os.getpgrp(), foreground,
     bool(termios.tcgetattr(0)[3] & termios.ISIG))).encode())
while True:
    time.sleep(.05)
"""


def read_until(fd, marker, timeout=2):
    output = b""
    deadline = time.monotonic() + timeout
    while marker not in output and time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
        if ready:
            output += os.read(fd, 4096)
    return output


class PTYTopologyTests(unittest.TestCase):
    def launch(self, corrected):
        master, slave = pty.openpty()
        process = subprocess.Popen(
            [sys.executable, "-c", SIMH_CONSOLE_MODEL],
            stdin=slave, stdout=slave, stderr=slave, close_fds=True,
            start_new_session=True,
            preexec_fn=configure_controlling_terminal if corrected else None)
        os.close(slave)
        self.addCleanup(self.stop_process, process, master)
        return process, master

    @staticmethod
    def stop_process(process, master):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        os.close(master)

    def test_ctrl_e_requires_controlling_foreground_pty(self):
        """Match SIMH's ISIG/VINTR behavior; never append CR or LF."""
        old_process, old_master = self.launch(corrected=False)
        old_ready = read_until(old_master, b"READY")
        self.assertIn(b"fg=-1", old_ready)
        os.write(old_master, b"\x05")
        self.assertNotIn(b"sim>", read_until(old_master, b"sim>", timeout=.2))
        self.assertIsNone(old_process.poll())

        process, master = self.launch(corrected=True)
        ready = read_until(master, b"READY")
        fields = dict(item.split(b"=", 1) for item in ready.strip().split()[1:])
        self.assertEqual(fields[b"sid"], fields[b"pgrp"])
        self.assertEqual(fields[b"pgrp"], fields[b"fg"])
        self.assertEqual(fields[b"isig"], b"1")
        os.write(master, b"\x05")
        self.assertIn(b"FRESH sim>", read_until(master, b"FRESH sim>"))
        self.assertIsNone(process.poll())

    @unittest.skipUnless(
        os.access("/opt/unix-time-machine/simh/v3.12-3/pdp11", os.X_OK),
        "pinned Open SIMH v3.12-3 executable is unavailable")
    def test_pinned_simh_ctrl_e_enters_monitor_without_historical_media(self):
        executable = "/opt/unix-time-machine/simh/v3.12-3/pdp11"
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "loop.ini"
            config.write_text("deposit 0 777\nrun 0\n")
            master, slave = pty.openpty()
            process = subprocess.Popen(
                [executable, str(config)], stdin=slave, stdout=slave, stderr=slave,
                close_fds=True, start_new_session=True,
                preexec_fn=configure_controlling_terminal)
            os.close(slave)
            self.addCleanup(self.stop_process, process, master)
            startup = read_until(master, b"sim>", timeout=.5)
            self.assertNotIn(b"sim>", startup)
            os.write(master, b"\x05")
            self.assertIn(b"sim>", read_until(master, b"sim>", timeout=2))


if __name__ == "__main__":
    unittest.main()
