import binascii
import gzip
import json
import struct
import tempfile
import unittest
from pathlib import Path

from scripts.media43bsd import TAPE_FILES, decode_boot42, prepare_43bsd
from scripts.utmlib import UTMError, sha256


class Media43BSDTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.payloads = {}
        for index, (filename, _name, _size) in enumerate(TAPE_FILES, 1):
            payload = bytes([index]) * (index + 2)
            self.payloads[filename] = payload
            (self.source / filename).write_bytes(gzip.compress(payload, mtime=0))

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def uuencode(data):
        lines = [b"begin 700 boot42"]
        lines.extend(binascii.b2a_uu(data[offset:offset + 45]).rstrip(b"\n")
                     for offset in range(0, len(data), 45))
        lines.extend((b"`", b"end"))
        return b"\n".join(lines) + b"\n"

    @staticmethod
    def tape_files(path):
        result, current = [], []
        data = path.read_bytes()
        offset = 0
        while offset < len(data):
            length = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            if length == 0:
                result.append(current)
                current = []
                continue
            block = data[offset:offset + length]
            offset += length
            trailer = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            if trailer != length:
                raise AssertionError("bad trailing record length")
            current.append(block)
        return result

    def test_required_set_and_lossless_gzip_decompression(self):
        destination = prepare_43bsd(self.source, self.base / "output")
        self.assertEqual((destination / "43bsd-miniroot.dsk").read_bytes(),
                         self.payloads["miniroot.gz"])
        (self.source / "miniroot.gz").write_bytes(b"not gzip")
        with self.assertRaisesRegex(UTMError, "invalid gzip"):
            prepare_43bsd(self.source, self.base / "bad-output")

    def test_tape_records_padding_order_and_double_final_mark(self):
        destination = prepare_43bsd(self.source, self.base / "output")
        files = self.tape_files(destination / "43bsd-dist.tap")
        self.assertEqual(len(files), len(TAPE_FILES) + 1)
        for index, ((filename, _name, block_size), records) in enumerate(zip(TAPE_FILES, files)):
            self.assertEqual(len(records), 1)
            self.assertEqual(len(records[0]), block_size)
            self.assertEqual(records[0][:len(self.payloads[filename])], self.payloads[filename])
            self.assertEqual(records[0][len(self.payloads[filename]):],
                             b"\0" * (block_size - len(self.payloads[filename])))
            self.assertEqual(records[0][0], index + 1)
        self.assertEqual(files[-1], [])

    def test_deterministic_outputs_and_metadata(self):
        first = prepare_43bsd(self.source, self.base / "one")
        second = prepare_43bsd(self.source, self.base / "two")
        for filename in ("43bsd-miniroot.dsk", "43bsd-dist.tap", "metadata.json"):
            self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
        metadata = json.loads((first / "metadata.json").read_text())
        self.assertEqual(metadata["format"], "unix-time-machine-43bsd-media-preparation-v1")
        self.assertEqual([item["filename"] for item in metadata["inputs"]],
                         [item[0] for item in TAPE_FILES])
        for item in metadata["inputs"] + metadata["outputs"]:
            self.assertEqual(len(item["sha256"]), 64)
            self.assertIsInstance(item["size"], int)
            self.assertTrue(item["provenance"])
        mini = next(x for x in metadata["outputs"] if x["filename"] == "43bsd-miniroot.dsk")
        self.assertEqual(mini["sha256"], sha256(first / "43bsd-miniroot.dsk"))
        self.assertEqual(mini["provenance"]["source_filename"], "miniroot.gz")

    def test_refuses_overwrite_and_incomplete_source(self):
        destination = self.base / "output"
        prepare_43bsd(self.source, destination)
        with self.assertRaisesRegex(UTMError, "overwrite"):
            prepare_43bsd(self.source, destination)
        (self.source / "new.tar.gz").unlink()
        with self.assertRaisesRegex(UTMError, "incomplete.*new.tar.gz"):
            prepare_43bsd(self.source, self.base / "incomplete")

    def test_boot42_decoded_and_uuencoded_routes(self):
        raw = b"historical bootstrap bytes\0"
        (self.source / "boot42.uue").write_bytes(self.uuencode(raw))
        destination = prepare_43bsd(self.source, self.base / "encoded")
        self.assertEqual((destination / "boot42").read_bytes(), raw)
        metadata = json.loads((destination / "metadata.json").read_text())
        boot = next(x for x in metadata["outputs"] if x["filename"] == "boot42")
        self.assertEqual(boot["provenance"]["source_filename"], "boot42.uue")

        (self.source / "boot42.uue").unlink()
        (self.source / "boot42").write_bytes(raw)
        copied = prepare_43bsd(self.source, self.base / "decoded")
        self.assertEqual((copied / "boot42").read_bytes(), raw)

    def test_boot42_input_validation_and_ambiguous_representation(self):
        invalid = self.source / "boot42.uue"
        invalid.write_bytes(b"begin 644 malware\n`\nend\n")
        with self.assertRaisesRegex(UTMError, "header"):
            prepare_43bsd(self.source, self.base / "invalid")
        invalid.write_bytes(self.uuencode(b"boot"))
        (self.source / "boot42").write_bytes(b"boot")
        with self.assertRaisesRegex(UTMError, "multiple"):
            prepare_43bsd(self.source, self.base / "ambiguous")

    def test_source_files_are_not_mutated(self):
        before = {path.name: (sha256(path), path.stat().st_mtime_ns)
                  for path in self.source.iterdir()}
        prepare_43bsd(self.source, self.base / "output")
        after = {path.name: (sha256(path), path.stat().st_mtime_ns)
                 for path in self.source.iterdir()}
        self.assertEqual(before, after)

    def test_destination_inside_source_is_refused(self):
        with self.assertRaisesRegex(UTMError, "outside"):
            prepare_43bsd(self.source, self.source / "output")


if __name__ == "__main__":
    unittest.main()
