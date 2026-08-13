# 4.3BSD on a VAX-11/780 (M3)

State: **IMPLEMENTED / AWAITING REAL-HOST QUALIFICATION**. Nothing below is a
claim of successful operation on the Debian 13 qualification host.

## Historical profile

The exhibit uses Open SIMH `vax780`, an 8 MiB VAX-11/780, a UDA50 with one
RA81, and a TS11 during installation. The simulator manual identifies these
devices and 8 MiB as its default VAX-11/780 memory. The installation sequence
is the stock-April-1986 4.3BSD procedure adapted to SIMH by the Computer
History Wiki. UDA50/RA81 is a repository/operator convention chosen because
that tested procedure and the distribution's `fstab.ra81` agree; it is not a
claim about a unique canonical Berkeley installation.

Networking is off: XU/XUB and DZ are disabled, no TCP console is configured,
and provisioning builds `vax780` with `NONETWORK=1` from the same pinned Open
SIMH v3.12-3 commit as PDP-11.

Sources:

- Berkeley, *Installing and Operating 4.3BSD on the VAX* (April 1986):
  https://bitsavers.org/pdf/usenix/Usenix_BSD_Manuals/4.3_1st_printing_198611/SMM_Unix_System_Managers_Manual_4.3BSD_198604.pdf
- Open SIMH VAX-11/780 simulator manual:
  https://simh.trailing-edge.com/pdf/vax780_doc.pdf
- Reproducible stock 4.3BSD/SIMH installation report:
  https://gunkies.org/wiki/Installing_4.3_BSD_on_SIMH
- Original 4.3BSD `shutdown(8)` manual:
  https://www.retro11.de/ouxr/43bsd/usr/man/cat8/shutdown.0.html
- pinned runtime source: https://github.com/open-simh/simh/tree/v3.12-3

## External media contract

Place exactly one accepted filename for each item in
`/srv/unix-time-machine/media/43bsd-vax/`:

| logical item | accepted filename(s) | status |
|---|---|---|
| SIMH distribution tape | `43bsd-dist.tap` or `43.tap` | required, UNPINNED |
| raw RA81 miniroot image | `43bsd-miniroot.dsk` or `miniroot` | required, UNPINNED |
| compatible standalone loader | `boot42` | required, UNPINNED |

No size or hash is asserted. `media verify` reports SHA-256 but **does not
authenticate** these files. The tape must be an operator-created SIMH tape with
stand, miniroot, rootdump, usr, srcsys, src, vfont, new, and ingres in the order
documented by the cited installation report. That ordering is a requirement of
this operator convention; retain the original archive objects, acquisition
source, license basis, conversion commands, and resulting hashes in the
qualification record. Nothing downloads or constructs copyrighted media.

## Human installation

After recording all provenance and hashes:

```sh
python3 scripts/utm.py media verify 43bsd-vax
python3 scripts/utm.py install prepare 43bsd-vax /srv/unix-time-machine/staging/43bsd-vax-QUAL --allow-unpinned
/opt/unix-time-machine/simh/v3.12-3/vax780 /srv/unix-time-machine/staging/43bsd-vax-QUAL/install-bootstrap.ini
```

At the miniroot `#` prompt perform the historically reported first phase:

```text
cd /dev
./MAKEDEV ra1
cd /
disk=ra1 type=ra81 tape=ts xtr
sync
sync
sync
```

Enter the monitor with Ctrl-E only after the syncs, confirm a fresh `sim>`
prompt, then `quit`. Run `install-runtime.ini`. At `#`:

```text
disk=ra
name=ra0h;type=ra81
cd /dev
sh ./MAKEDEV ts0;sync
cd /
newfs $name $type
mount /dev/$name /usr
cd /usr
mkdir sys
cd sys
mt rew
mt fsf 3
tar xpbf 20 /dev/rmt12
cd ..
mt fsf
tar xpbf 20 /dev/rmt12
cd /
chmod 755 / /usr /usr/sys
rm -rf sys
ln -s /usr/sys sys
umount /dev/$name
fsck /dev/r$name
cd /etc
cp fstab.ra81 fstab
newfs ra0g ra81
sync
reboot
```

These commands are historically sourced but still HUMAN_REQUIRED and
unqualified here. Boot the runtime configuration again to reach multi-user
`login:`. Confirm `real mem = 8388608`, `ra0`, `mount`, and `df`; disable guest
network daemons in the staged guest before publication even though no emulated
network device exists. Installation tapes and miniroot are never imported.

Publish only the complete `rq0.dsk`:

```sh
sudo python3 scripts/utm.py golden import 43bsd-vax /srv/unix-time-machine/staging/43bsd-vax-QUAL
```

The existing atomic, exclusive, root-owned 0440 golden publication path hashes
the disk and disposable sessions copy it.

## Runtime, readiness, and shutdown

The broker renders the manifest profile and retains the qualified controlling
PTY. Attach, type `run 2`, and accept `ra(0,0)vmunix` at `Boot`. Readiness is the
console `login:` prompt—not emulator start—and becomes armed on first attach.

For a multi-user guest, log in as root and run `/etc/shutdown -h now`. The
original manual says `-h` executes `halt`, while omitting `-n` retains normal
sync. Wait for console evidence that shutdown/halt has completed. Only then may
the operator attest with `broker stop SESSION --guest-synced`; that flag means
the documented 4.3BSD shutdown was observed, not merely that `sync` was typed.
The broker then uses Ctrl-E, requires a fresh `sim>` prompt, sends `quit`, and
requires emulator exit. Uncertainty preserves workspace, transcript, and audit.

## Debian 13 qualification gate

Record operator, UTC times, host release, repository commit, and every command.

1. `make provision` twice; record `vax780` version/provenance.
2. Run `utm.py doctor`, `catalog`, and `media verify 43bsd-vax`.
3. Record source provenance and SHA-256 for all three supplied artifacts.
4. Prepare a new staging directory with `--allow-unpinned`.
5. Perform both manual installation phases above.
6. Boot staging under `install-runtime.ini`; verify 8 MiB/VAX identity and RA81.
7. Reach console `login:` and verify expected `/`, `/usr`, and `/a`/home layout
   using `mount` and `df` (record actual distribution layout).
8. Run `/etc/shutdown -h now`, observe completion, then Ctrl-E/prompt/quit/exit.
9. Import the one-disk golden and record metadata plus independent hashes.
10. Request broker session #1; attach, `run 2`, reach readiness, log in, verify
    filesystems, detach (Ctrl-]), reattach, and detach again.
11. Perform `/etc/shutdown -h now`; after observed halt run broker stop with
    `--guest-synced`. Verify monitor handshake, exit, reset, and release.
12. Verify golden hash unchanged.
13. Request a completely fresh session #2 and repeat boot, readiness, login,
    filesystem checks, clean shutdown, monitor exit, reset/release, and hash check.
14. Exercise one safe failure (withhold shutdown attestation or use a bounded
    test where monitor confirmation is absent); verify evidence/workspace remains
    and no forced kill occurs. Recover only under the documented recovery path.
15. Archive console transcripts, supervisor diagnostics, broker audit JSONL,
    media report, golden metadata/hashes, and qualification notes outside Git.

Only after reviewing that evidence may ROADMAP state COMPLETE.

## Explicit unresolved assumptions

No canonical hashes/sizes for the archive-derived artifacts are claimed. The
exact provenance and correctness of an operator's `boot42`, miniroot conversion,
and SIMH tape construction remain qualification inputs. The documented commands
have not yet been executed with pinned v3.12-3 on the target Debian 13 host.
