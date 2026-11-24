"""Production inventory recognizes only a complete registered large plate."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_repository import PAGE_FILES,output_inventory


class LargeFormatInventoryTests(unittest.TestCase):
    def test_large_plate_must_be_registered_and_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);a3=out/'a3_release';(a3/'05_len').mkdir(parents=True)
            for rel in ['README.md','05_len/assembly.png','05_len/assembly_dot.png']:
                (a3/rel).touch()
            folder='large_format/ascent_5T_800x500';plate=out/folder;plate.mkdir(parents=True)
            manifest={'groups':{},'package_archives':False,'retired_package_files':[],
                      'large_format_plates':[{'folder':folder,'canvas_mm':[800,500],
                          'pieces':30,'contours':70,'files':sorted(PAGE_FILES)}]}
            (a3/'manifest.json').write_text(json.dumps(manifest))
            for name in PAGE_FILES:(plate/name).touch()
            self.assertTrue(all(folder+'/'+name in output_inventory(out) for name in PAGE_FILES))
            (plate/'03_CUT_ONLY.svg').unlink()
            with self.assertRaisesRegex(ValueError,'Missing release artifacts'):output_inventory(out)
            (plate/'03_CUT_ONLY.svg').touch();(plate/'unknown.svg').touch()
            with self.assertRaisesRegex(ValueError,'Unregistered'):output_inventory(out)


if __name__=='__main__':unittest.main()
