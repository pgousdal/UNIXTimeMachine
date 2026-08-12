# Security Model

Historical systems are untrusted. Never bridge them directly to the public LAN, expose emulator monitors, grant host credentials, reuse operator secrets, or allow public sessions to mutate golden images. Default-deny outbound networking.

M1 is local-console only. The SIMH profile disables XQ/XU Ethernet and all
additional terminal multiplexers; it does not configure console Telnet or any
other listener. The SIMH control escape remains available only to the trusted
local operator. No guest networking, host shell escape for visitors, public
terminal handoff, or secrets are part of M1. Run the operator CLI as the
dedicated `unix-time-machine` account (or with equivalent group access), never
as an untrusted guest-facing service.

Host provisioning uses TLS plus a pinned SHA-256 for one immutable Open SIMH
source archive and Debian 13 packages from configured official host sources. It
does not add repositories or execute downloaded installer scripts. The PDP-11
target is compiled with `NONETWORK=1`; this supply-time host access does not
enable networking in the historical guest.
