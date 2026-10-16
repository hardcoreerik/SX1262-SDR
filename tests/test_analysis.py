import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sx1262_sdr.analysis import analyze, parse_sxp


class SweepParsingTests(unittest.TestCase):
    def setUp(self):
        self.data = (Path(__file__).resolve().parents[1] /
                     "examples" / "synthetic_sxp.csv").read_text(encoding="utf-8")

    def test_parse_rows(self):
        rows = parse_sxp(self.data)
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0].frequency_khz, 915000)
        self.assertEqual(rows[0].status, "rssi_observed_unverified")

    def test_pll_vs_image_cal(self):
        rows = parse_sxp(self.data)
        self.assertTrue(rows[2].pll_error)
        self.assertTrue(rows[2].image_cal_error)
        self.assertFalse(rows[5].image_cal_error)
        self.assertTrue(rows[5].pll_error)
        self.assertTrue(rows[6].image_cal_error)
        self.assertFalse(rows[6].pll_error)
        self.assertEqual(rows[6].status, "rssi_observed_unverified")

    def test_summary_never_proves_reception(self):
        result = analyze(self.data, "fixture", "synthetic")
        self.assertFalse(result["rf_reception_proven"])
        self.assertTrue(all(not row["rf_reception_proven"]
                            for row in result["rows"]))
        self.assertEqual(result["status_counts"]["rx_pll_error"], 5)

    def test_repeated_header_and_non_sxp(self):
        rows = parse_sxp(self.data + "\nlog other text\n" + self.data)
        self.assertEqual(len(rows), 18)

    def test_reject_malformed(self):
        with self.assertRaises(ValueError):
            parse_sxp("sxp,123000,0040,0000,20,50,8,,,,1000\n")

    def test_reject_no_data(self):
        with self.assertRaises(ValueError):
            parse_sxp("sxp,khz,err_cal,err_rx,st_cal,st_rx,n,avg_dbm,max_dbm,min_dbm,us")


if __name__ == "__main__":
    unittest.main()
