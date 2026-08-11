import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN={".adf",".adz",".hdf",".iso",".img",".dsk",".tap",".rom"}
class PolicyTests(unittest.TestCase):
    def test_no_media(self):
        offenders=[str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and p.suffix.lower() in FORBIDDEN]
        self.assertEqual(offenders,[])
    def test_docs(self):
        for r in ["docs/LEGAL.md","docs/PRESERVATION.md","docs/SECURITY.md"]: self.assertTrue((ROOT/r).is_file())
if __name__=='__main__': unittest.main()
