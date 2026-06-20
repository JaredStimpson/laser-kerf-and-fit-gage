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

    def test_preview_label_position_stays_inside_canvas(self):
        width = 120
        height = 80
        text_width = 90
        text_height = 22

        for x, y in [(-50, -50), (500, 500), (60, 40)]:
            safe_x, safe_y = ltg.clamped_label_position(x, y, text_width, text_height, width, height)
            self.assertGreaterEqual(safe_x - text_width / 2, 6)
            self.assertGreaterEqual(safe_y - text_height / 2, 6)
            self.assertLessEqual(safe_x + text_width / 2, width - 6)
            self.assertLessEqual(safe_y + text_height / 2, height - 6)

    def test_sample_exports_are_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            ltg.export_samples(out_dir)

            svg_files = sorted(out_dir.glob("*.svg"))
            dxf_files = sorted(out_dir.glob("*.dxf"))
            lbrn_files = sorted(out_dir.glob("*.lbrn2"))
            self.assertEqual(len(svg_files), 2)
            self.assertEqual(len(dxf_files), 2)
            self.assertEqual(len(lbrn_files), 1)

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

            self.assertEqual(ET.parse(lbrn_files[0]).getroot().tag, "LightBurnProject")

            payload = json.loads((out_dir / "sample-parameters.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["units"], "mm")
            self.assertIn("kerf", payload)
            self.assertIn("fit", payload)

    def test_fit_holes_use_independent_grid_values_and_on_part_labels(self):
        params = ltg.FitParams(
            fit_variable_center=20.0,
            fit_variable_count=3,
            fit_variable_min=19.8,
            fit_variable_max=20.2,
            material_thickness=3.0,
            material_count=2,
            material_min=2.9,
            material_max=3.1,
            spacing_margin=5.0,
        )
        layout = ltg.fit_layout(params)
        drawing = ltg.generate_fit(params)
        slot_polylines = [
            entity
            for entity in drawing.entities
            if isinstance(entity, ltg.Polyline) and entity.layer == "HOLES"
        ]
        hole_widths = sorted({round(poly.points[1][0] - poly.points[0][0], 4) for poly in slot_polylines})
        hole_heights = sorted({round(poly.points[2][1] - poly.points[1][1], 4) for poly in slot_polylines})
        label_text = [entity.text for entity in drawing.entities if isinstance(entity, ltg.Text)]

        self.assertEqual(len(slot_polylines), 6)
        self.assertEqual(hole_widths, [2.9, 3.1])
        self.assertEqual(hole_heights, [19.8, 20.0, 20.2])
        self.assertEqual([round(value, 2) for value in layout["fit_values"]], [19.8, 20.0, 20.2])
        self.assertEqual([round(value, 2) for value in layout["material_values"]], [2.9, 3.1])
        self.assertAlmostEqual(
            layout["coupon_length"],
            params.label_size * 3.2 + params.spacing_margin + 3 * (3.1 + params.spacing_margin),
        )
        self.assertIn("19.80", label_text)
        self.assertIn("20.20", label_text)
        self.assertIn("2.90", label_text)
        self.assertIn("3.10", label_text)
        self.assertIn("20 x 3 [mm]", label_text)
        self.assertEqual(round(layout["pin_width"], 4), 20.0)

    def test_fit_step_inputs_center_values_on_nominals(self):
        params = ltg.FitParams(
            fit_variable_center=20.0,
            fit_variable_count=5,
            fit_variable_step=0.05,
            material_thickness=3.0,
            material_count=3,
            material_step=0.1,
        )
        self.assertEqual(
            [round(value, 2) for value in ltg.fit_variable_values(params)],
            [19.9, 19.95, 20.0, 20.05, 20.1],
        )
        self.assertEqual(
            [round(value, 2) for value in ltg.material_values(params)],
            [2.9, 3.0, 3.1],
        )

    def test_lightburn_export_has_fit_layers_and_kerf_directions(self):
        params = ltg.FitParams(known_kerf=0.075)
        drawing = ltg.generate_fit(params)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fit.lbrn2"
            ltg.write_lightburn_fit(drawing, path, params.known_kerf)
            root = ET.parse(path).getroot()

        settings = {node.attrib["name"]: node.attrib for node in root.findall("CutSetting")}
        self.assertEqual(settings["OUTSIDE"]["type"], "Cut")
        self.assertEqual(settings["OUTSIDE"]["kerfDirection"], "out")
        self.assertEqual(settings["OUTSIDE"]["kerfOffset"], "0.075")
        self.assertEqual(settings["HOLES"]["type"], "Cut")
        self.assertEqual(settings["HOLES"]["kerfDirection"], "in")
        self.assertEqual(settings["HOLES"]["kerfOffset"], "0.075")
        self.assertEqual(settings["TEXT"]["type"], "Fill")
        self.assertEqual(settings["NUMBERS"]["mode"], "fill")
        self.assertTrue(root.findall("Shape[@Layer='HOLES']"))
        self.assertTrue(root.findall("Shape[@Layer='NUMBERS']"))

    def test_kerf_uses_vernier_offset_labels(self):
        params = ltg.KerfParams()
        drawing = ltg.generate_kerf(params)
        text_values = [entity.text for entity in drawing.entities if isinstance(entity, ltg.Text)]
        cut_lines = [entity for entity in drawing.entities if isinstance(entity, ltg.Line) and entity.layer == "CUT"]
        mark_lines = [entity for entity in drawing.entities if isinstance(entity, ltg.Line) and entity.layer == "MARK"]

        self.assertIn("Vernier Kerf Offset Test", text_values)
        self.assertIn("SLIDE ->", text_values)
        self.assertIn("DISCARD", text_values)
        self.assertNotIn("D", text_values)
        self.assertNotIn("E", text_values)
        self.assertIn("Kerf offset = D.E / 40", text_values)
        self.assertGreaterEqual(len(cut_lines), int(params.piece_count) + 5)
        self.assertGreaterEqual(len(mark_lines), int(params.scale_units) + int(params.vernier_divisions) + 2)

    def test_kerf_discard_and_slider_follow_reference_geometry(self):
        params = ltg.KerfParams()
        layout = ltg.kerf_layout(params)
        drawing = ltg.generate_kerf(params)
        cut_lines = [entity for entity in drawing.entities if isinstance(entity, ltg.Line) and entity.layer == "CUT"]

        def has_line(start, end):
            return any(
                abs(line.start[0] - start[0]) < 0.00001
                and abs(line.start[1] - start[1]) < 0.00001
                and abs(line.end[0] - end[0]) < 0.00001
                and abs(line.end[1] - end[1]) < 0.00001
                for line in cut_lines
            )

        self.assertTrue(has_line((layout["track_x"], layout["track_y"]), (layout["inner_right"], layout["track_y"])))
        self.assertTrue(has_line((layout["track_x"], layout["row_bottom"]), (layout["inner_right"], layout["row_bottom"])))
        self.assertTrue(has_line((layout["inner_right"], layout["track_bottom"]), (layout["track_x"], layout["track_bottom"])))
        self.assertTrue(has_line((layout["nose_x"], layout["row_bottom"]), (layout["discard_x"], layout["track_bottom"])))
        self.assertAlmostEqual(
            layout["discard_width"],
            layout["discard_piece_count"] * layout["cell_width"],
        )
        self.assertTrue(
            any(abs(line.start[0] - layout["discard_x"]) < 0.00001 for line in cut_lines),
            "Discard boundary should align with a top-row piece boundary.",
        )
        self.assertAlmostEqual(layout["top_scale_end"] - layout["track_x"], params.scale_units * params.scale_tick_spacing)
        self.assertAlmostEqual(layout["vernier_length"], layout["scale_length"])


if __name__ == "__main__":
    unittest.main()
