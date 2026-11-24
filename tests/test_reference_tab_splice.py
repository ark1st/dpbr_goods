"""Regression: copied reference tabs must not double back on their shoulders."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from svgpathtools import Line,Path as SVGPath,parse_path
import reference_cut_style as cut


class ReferenceTabSpliceTest(unittest.TestCase):
    def test_both_shoulders_trim_without_refitting_original_tab(self):
        reference=cut.read_reference(ROOT/'assets/incoming/fixed_page3.ai')
        splice=cut._splice_reference_tab
        for name in ('렘샤','적매화검'):
            with self.subTest(name=name), patch.object(cut,'_splice_reference_tab',wraps=splice) as called:
                result=cut.reference_stand(ROOT/'assets/chain_keyring/추가스탠드'/f'{name}_stand60_prepared.png',reference)
                outline,ref,dx,dy,shoulder=called.call_args.args
                unfitted=parse_path(outline)
                below=[i for i,s in enumerate(unfitted) if max(s.start.imag,s.end.imag)>shoulder+.05]
                a,b=min(below),max(below)
                insert=SVGPath(*parse_path(ref['original_stand_outer'])[20:27]).reversed().translated(complex(dx,dy))
                # The input actually has both problematic reverse connectors.
                self.assertGreater(unfitted[a].start.real,insert.start.real)
                self.assertLess(unfitted[b].end.real,insert.end.real)
                self.assertIsInstance(unfitted[a-1],Line)
                self.assertIsInstance(unfitted[b+1],Line)
                actual=parse_path(result['paths'][1]); matches=[i for i in range(len(actual)-6) if list(actual[i:i+7])==list(insert)]
                self.assertEqual(len(matches),1)
                i=matches[0];left,right=actual[i-1],actual[i+7]
                self.assertIsInstance(left,Line);self.assertIsInstance(right,Line)
                self.assertEqual(left.end,insert.start);self.assertEqual(right.start,insert.end)
                self.assertLess(left.start.real,left.end.real)
                self.assertLess(right.start.real,right.end.real)

if __name__=='__main__':unittest.main()
