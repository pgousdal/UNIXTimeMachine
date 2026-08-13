"""Preservation-safe preparation of stock 4.3BSD media for SIMH."""
from __future__ import annotations

import binascii
import gzip
import json
import os
import shutil
import struct
import tempfile
import zlib
from pathlib import Path

try:
    from utmlib import UTMError, sha256
except ModuleNotFoundError:
    from .utmlib import UTMError, sha256


# This is the 4.2/4.3BSD sequence published in the historical mkdisttap.pl
# transcription cited in systems/43bsd-vax/README.md.  In particular, srcsys
# precedes usr; the installation procedure's `mt fsf 3` depends on that.
TAPE_FILES = (
    ("stand.gz", "stand", 512),
    ("miniroot.gz", "miniroot", 10240),
    ("rootdump.gz", "rootdump", 10240),
    ("srcsys.tar.gz", "srcsys.tar", 10240),
    ("usr.tar.gz", "usr.tar", 10240),
    ("vfont.tar.gz", "vfont.tar", 10240),
    ("src.tar.gz", "src.tar", 10240),
    ("new.tar.gz", "new.tar", 10240),
    ("ingres.tar.gz", "ingres.tar", 10240),
)
BOOT_NAMES = ("boot42", "boot42.uue", "boot42.uu")
FORMAT_SOURCE = "https://gunkies.org/wiki/Mkdisttap.pl#4.2_&_4.3_BSD"
BOOT_SOURCE = "https://gunkies.org/wiki/Boot42"


def _artifact(path: Path, filename: str, provenance: dict) -> dict:
    return {"filename": filename, "sha256": sha256(path),
            "size": path.stat().st_size, "provenance": provenance}


def _gunzip(path: Path) -> bytes:
    try:
        # gzip.decompress validates headers, trailer CRC/size, concatenated
        # members, and rejects truncated or non-gzip input.
        return gzip.decompress(path.read_bytes())
    except (gzip.BadGzipFile, EOFError, zlib.error) as exc:
        raise UTMError(f"invalid gzip source {path.name}: {exc}") from exc


def write_simh_tape(output, files) -> None:
    """Write mkdisttap-compatible little-endian SIMH tape records."""
    for data, block_size in files:
        for offset in range(0, len(data), block_size):
            block = data[offset:offset + block_size]
            block += b"\0" * (block_size - len(block))
            marker = struct.pack("<I", block_size)
            output.write(marker)
            output.write(block)
            output.write(marker)
        output.write(b"\0\0\0\0")
    output.write(b"\0\0\0\0")


def decode_boot42(path: Path) -> tuple[bytes, str]:
    if path.name == "boot42":
        data = path.read_bytes()
        if not data:
            raise UTMError("decoded boot42 must not be empty")
        return data, "operator-supplied decoded 4.2BSD VAX bootstrap (byte-for-byte copy)"

    try:
        lines = path.read_bytes().splitlines()
        if not lines or lines[0] != b"begin 700 boot42":
            raise UTMError("boot42 uuencode header must be exactly 'begin 700 boot42'")
        if b"end" not in lines[1:]:
            raise UTMError("boot42 uuencoded source has no end line")
        end = lines.index(b"end", 1)
        if any(line.strip() for line in lines[end + 1:]):
            raise UTMError("boot42 uuencoded source has data after the end line")
        encoded = lines[1:end]
        if not encoded or encoded[-1] not in (b"`", b" "):
            raise UTMError("boot42 uuencoded source has no zero-length terminator")
        decoded = []
        for number, line in enumerate(encoded, 2):
            if not line or any(byte < 0x20 or byte > 0x60 for byte in line):
                raise UTMError(f"boot42 uuencode line {number} contains invalid characters")
            length = (line[0] - 0x20) & 0x3f
            expected = 1 + 4 * ((length + 2) // 3)
            if length > 45 or len(line) != expected:
                raise UTMError(f"boot42 uuencode line {number} has invalid encoded length")
            if length == 0 and number != end:
                raise UTMError("boot42 uuencode zero-length terminator must be last")
            part = binascii.a2b_uu(line)
            if len(part) != length:
                raise UTMError(f"boot42 uuencode line {number} decoded length mismatch")
            decoded.append(part)
        data = b"".join(decoded)
    except binascii.Error as exc:
        raise UTMError(f"invalid boot42 uuencoded data: {exc}") from exc
    if not data:
        raise UTMError("decoded boot42 must not be empty")
    return data, f"decoded original uuencode representation with Python binascii; route: {BOOT_SOURCE}"


def prepare_43bsd(source: Path, destination: Path) -> Path:
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise UTMError("4.3BSD media source must be a directory")
    destination = destination.resolve(strict=False)
    if destination.exists():
        raise UTMError(f"refusing to overwrite existing destination: {destination}")
    if source == destination or source in destination.parents:
        raise UTMError("destination must be outside the source directory")
    missing = [name for name, _, _ in TAPE_FILES if not (source / name).is_file()]
    if missing:
        raise UTMError("incomplete 4.3BSD source set; missing: " + ", ".join(missing))
    boots = [source / name for name in BOOT_NAMES if (source / name).is_file()]
    if len(boots) > 1:
        raise UTMError("multiple accepted boot42 source representations are present")

    destination.parent.mkdir(parents=True, exist_ok=True)
    transaction = Path(tempfile.mkdtemp(prefix=f".{destination.name}.prepare-",
                                        dir=destination.parent))
    try:
        inputs = []
        tape_parts = []
        decompressed = {}
        for compressed_name, tape_name, block_size in TAPE_FILES:
            path = source / compressed_name
            data = _gunzip(path)
            decompressed[compressed_name] = data
            tape_parts.append((data, block_size))
            inputs.append(_artifact(path, compressed_name, {
                "role": tape_name, "transformation": "gzip decompression"
            }))

        miniroot = transaction / "43bsd-miniroot.dsk"
        with miniroot.open("xb") as stream:
            stream.write(decompressed["miniroot.gz"])
        tape = transaction / "43bsd-dist.tap"
        with tape.open("xb") as stream:
            write_simh_tape(stream, tape_parts)

        outputs = [
            _artifact(miniroot, miniroot.name, {
                "source_filename": "miniroot.gz",
                "source_sha256": next(x["sha256"] for x in inputs if x["filename"] == "miniroot.gz"),
                "transformation": "validated gzip decompression; output bytes are the complete decompressed stream",
            }),
            _artifact(tape, tape.name, {
                "format_source": FORMAT_SOURCE,
                "record_format": "little-endian uint32 length, padded data block, repeated length; uint32 zero tape marks",
                "tape_files": [{"block_size": size, "source_filename": compressed,
                                "tape_name": name} for compressed, name, size in TAPE_FILES],
                "transformation": "gzip decompression followed by repository-owned SIMH tape writer",
            }),
        ]
        if boots:
            boot_data, transformation = decode_boot42(boots[0])
            inputs.append(_artifact(boots[0], boots[0].name,
                                    {"role": "boot42", "transformation": transformation}))
            boot = transaction / "boot42"
            with boot.open("xb") as stream:
                stream.write(boot_data)
            outputs.append(_artifact(boot, boot.name, {
                "source_filename": boots[0].name,
                "source_sha256": inputs[-1]["sha256"],
                "transformation": transformation,
            }))

        metadata = {
            "format": "unix-time-machine-43bsd-media-preparation-v1",
            "inputs": inputs,
            "outputs": outputs,
        }
        with (transaction / "metadata.json").open("x", encoding="utf-8") as stream:
            json.dump(metadata, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(transaction, destination)
    except Exception:
        shutil.rmtree(transaction, ignore_errors=True)
        raise
    return destination
