from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_a3_release import polygon_of
from verify_recut import compare_contours

class PrintedRecoveryRegression(unittest.TestCase):
    def test_recovery_rejects_a_shift_that_would_miss_the_print(self):
        source=polygon_of('M10 20L40 20L40 50L10 50Z')
        expected=[{'path':'M10 20L40 20L40 50L10 50Z','source_index':0,'is_hole':False}]
        self.assertEqual(compare_contours([source],expected,[source])['max_format_deviation_mm'],0)
        shifted=polygon_of('M10.1 20L40.1 20L40.1 50L10.1 50Z')
        with self.assertRaises(AssertionError):compare_contours([shifted],expected,[source])

    def test_reviewed_curve_cannot_enlarge_original_hole(self):
        source=polygon_of('M10 20L12 20L12 22L10 22Z')
        enlarged='M9.99 19.99L12.01 19.99L12.01 22.01L9.99 22.01Z'
        expected=[{'path':enlarged,'source_index':0,'is_hole':True}]
        with self.assertRaisesRegex(AssertionError,'hole dimensions'):
            compare_contours([polygon_of(enlarged)],expected,[source])

if __name__=='__main__':unittest.main()
