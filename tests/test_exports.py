import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import laser_tester_generator as ltg


class ExportTests(unittest.TestCase):
    def test_gui_field_groups_cover_all_parameters(self):
        kerf_grouped = ltg.KERF_GENERAL_FIELDS + ltg.KERF_ADVANCED_FIELDS
        fit_grouped = ltg.FIT_GENERAL_FIELDS + ltg.FIT_ADVANCED_FIELDS

        self.assertEqual(len(kerf_grouped), len(set(kerf_grouped)))
        self.assertEqual(len(fit_grouped), len(set(fit_grouped)))
        self.assertEqual({field.name for field in ltg.fields(ltg.KerfParams)}, set(kerf_grouped))
        self.assertEqual({field.name for field in ltg.fields(ltg.FitParams)}, set(fit_grouped))
        self.assertTrue(set(kerf_grouped).issubset(ltg.FIELD_HELP))
        self.assertTrue(set(fit_grouped).issubset(ltg.FIELD_HELP))

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
                svg_text = svg.read_text(encoding="utf-8")
                self.assertIn("#ff0000", svg_text)
                self.assertIn("#000000", svg_text)

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

    def test_kerf_uses_vernier_offset_labels(self):
        params = ltg.KerfParams()
        drawing = ltg.generate_kerf(params)
        text_values = [entity.text for entity in drawing.entities if isinstance(entity, ltg.Text)]
        cut_lines = [entity for entity in drawing.entities if isinstance(entity, ltg.Line) and entity.layer == "CUT"]
        mark_lines = [entity for entity in drawing.entities if isinstance(entity, ltg.Line) and entity.layer == "MARK"]

        self.assertIn("Vernier Kerf Offset Test", text_values)
        self.assertIn("SLIDE ->", text_values)
        self.assertIn("DISCARD", text_values)
        self.assertIn("D", text_values)
        self.assertIn("E", text_values)
        self.assertIn("Kerf offset = D.E / 40", text_values)
        self.assertEqual(len(cut_lines), int(params.piece_count) - 1)
        self.assertGreaterEqual(len(mark_lines), int(params.scale_units) + int(params.vernier_divisions) + 2)


if __name__ == "__main__":
    unittest.main()
