from pathlib import Path
import sys,json,hashlib,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from source_cache import cached_input
from verify_repository import output_inventory,PAGE_FILES

class RepositoryRegression(unittest.TestCase):
    def test_nesting_does_not_extend_protection_to_nearby_owned_paths(self):
        from verify_laser_paths import protected_contour
        from shapely.geometry import Polygon,box
        protected=Polygon([(0,0),(20,0),(20,5),(5,5),(5,20),(0,20)])
        self.assertFalse(protected_contour('M8 8 L12 8 L12 12 L8 12 Z',[protected]))
        self.assertFalse(protected_contour('M0 0 L20 0 L20 20 L0 20 Z',[protected]))
        self.assertTrue(protected_contour('M0 0 L20 0 L20 5 L5 5 L5 20 L0 20 Z',[protected]))

    def test_archived_input_stays_in_cache_and_rejects_modified_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            cache=Path(d)/'cache';data=b'original source'
            spec={'file':'output/old/plate.ai','commit':'1'*40,'sha256':hashlib.sha256(data).hexdigest()}
            with patch('source_cache.subprocess.check_output',return_value=data) as run:
                p=cached_input(spec,cache);self.assertTrue(p.is_relative_to(cache));self.assertEqual(p.read_bytes(),data)
                self.assertEqual(cached_input(spec,cache),p);self.assertEqual(run.call_count,1)
                p.write_bytes(b'altered')
                with self.assertRaisesRegex(ValueError,'Changed source'):cached_input(spec,cache)
            with self.assertRaises(ValueError):cached_input({**spec,'file':'../../escape'},cache)

    def test_unregistered_and_missing_release_files_block_publication(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);base=out/'a3_release';page=base/'05_len/3T/sheet_01';page.mkdir(parents=True)
            (base/'manifest.json').write_text(json.dumps({'groups':{'05_len/3T':[{'folder':'a3_release/05_len/3T/sheet_01'}]}}))
            for p in [base/'README.md',base/'05_len/README.md',base/'05_len/assembly.png',base/'05_len/assembly_dot.png',base/'05_len_3T_A3.zip',*(page/n for n in PAGE_FILES)]:p.touch()
            output_inventory(out)
            rogue=page/'04_FIT_TEST.svg';rogue.touch()
            with self.assertRaisesRegex(ValueError,'Unregistered'):output_inventory(out)
            rogue.unlink();(page/'03_CUT_ONLY.pdf').unlink()
            with self.assertRaisesRegex(ValueError,'Missing'):output_inventory(out)

if __name__=='__main__':unittest.main()
