import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import laser_tester_generator as ltg


class ExportTests(unittest.TestCase):
    def test_sample_exports_are_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            ltg.export_samples(out_dir)

            svg_files = sorted(out_dir.glob("*.svg"))
            dxf_files = sorted(out_dir.glob("*.dxf"))
            self.assertEqual(len(svg_files), 2)
            self.assertEqual(len(dxf_files), 2)

            for svg in svg_files:
                ET.parse(svg)

            for dxf in dxf_files:
                text = dxf.read_text(encoding="utf-8")
                self.assertIn("$INSUNITS", text)
                self.assertIn("\nLINE\n", text)
                self.assertTrue(text.rstrip().endswith("EOF"))

            payload = json.loads((out_dir / "sample-parameters.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["units"], "mm")
            self.assertIn("kerf", payload)
            self.assertIn("fit", payload)

    def test_fit_slot_widths_equal_nominal_plus_allowance(self):
        params = ltg.FitParams(
            nominal_tab_width=20.0,
            allowance_start=-0.2,
            allowance_stop=0.2,
            allowance_step=0.2,
            include_labels=False,
        )
        drawing = ltg.generate_fit(params)
        slot_polylines = [entity for entity in drawing.entities if isinstance(entity, ltg.Polyline)][1:4]
        widths = [round(poly.points[1][0] - poly.points[0][0], 4) for poly in slot_polylines]
        self.assertEqual(widths, [19.8, 20.0, 20.2])

    def test_kerf_scale_tick_count_tracks_increment(self):
        params = ltg.KerfParams(
            gap_scale_range=1.0,
            gap_scale_increment=0.25,
            include_labels=False,
        )
        drawing = ltg.generate_kerf(params)
        mark_lines = [entity for entity in drawing.entities if isinstance(entity, ltg.Line) and entity.layer == "MARK"]
        self.assertEqual(len(mark_lines), 6)


if __name__ == "__main__":
    unittest.main()
