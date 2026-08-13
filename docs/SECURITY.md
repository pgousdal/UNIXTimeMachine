# Security Model

Historical systems are untrusted. Never bridge them directly to the public LAN, expose emulator monitors, grant host credentials, reuse operator secrets, or allow public sessions to mutate golden images. Default-deny outbound networking.

The M3 VAX profile disables XU/XUB, DZ, and all unused controllers and the
simulator is built with `NONETWORK=1`. It adds no listener, Telnet, SSH, remote
monitor, or guest network. Its external unpinned media must be treated as
untrusted input and is never executed by the host outside the pinned emulator.

M1 is local-console only. The SIMH profile disables XQ/XU Ethernet and all
additional terminal multiplexers; it does not configure console Telnet or any
other listener. The SIMH control escape remains available only to the trusted
local operator. No guest networking, host shell escape for visitors, public
terminal handoff, or secrets are part of M1. Run the operator CLI as the
dedicated `unix-time-machine` account (or with equivalent group access), never
as an untrusted guest-facing service.

Golden sets are owned by root and readable only by the `unix-time-machine`
group: directories use mode 0750 and disks/metadata use mode 0440. Operators
must be explicitly enrolled in that group. Session preparation copies golden
data without privilege escalation; neither operators nor guests receive golden
write permission.

Host provisioning uses TLS plus a pinned SHA-256 for one immutable Open SIMH
source archive and Debian 13 packages from configured official host sources. It
does not add repositories or execute downloaded installer scripts. The PDP-11
target is compiled with `NONETWORK=1`; this supply-time host access does not
enable networking in the historical guest.

M2 retains this boundary. Broker access is local and operator-controlled. Its
only handoff endpoint is a filesystem Unix-domain socket (mode 0660) beneath the
protected state directory; there is no public Telnet, SSH, TCP, web, BBS, guest
bridge or remote monitor. Ctrl-E remains available because an attached user is
a trusted operator, while Ctrl-] detaches locally. Only one operator may attach.

Session and PID input is validated, process identity includes `/proc` start
ticks, state mutation is locked and atomic, and audit entries contain lifecycle
metadata rather than terminal content. Backend launch descriptions must never
contain secrets. A failed or ambiguous shutdown is preserved for inspection;
the broker never escalates to SIGKILL. Operators must sync the historical guest
and explicitly attest that fact before requesting a normal stop. The
attestation is not represented as a complete guest OS shutdown. Automatic
deadline failures send no control input. An explicit SIMH stop enters the
monitor, confirms its prompt from bounded live PTY output, and only then sends
the monitor quit command; ambiguous outcomes preserve evidence.

Real-host qualification confirmed both safety branches: the attested normal
stop observed a fresh monitor prompt before sending `quit`, while idle timeout
and interrupted-supervisor reconciliation sent no shutdown input, performed no
forced kill, and preserved the emulator, workspace, and audit evidence.

M3 real-host qualification additionally confirmed the VAX-specific safe stop:
after 4.3BSD clean halt exposed a fresh live `sim>` prompt, the broker recognized
the already-active monitor, sent no redundant Ctrl-E, owned `quit`, observed
exit, and reset/released the disposable session. Its never-attached idle-timeout
case sent no control input or force kill and preserved the emulator and
workspace. Qualification-only short timeouts are not production defaults.
