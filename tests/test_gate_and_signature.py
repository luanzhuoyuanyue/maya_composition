# -*- coding: utf-8 -*-
from __future__ import division

import unittest

import composition_guides_core as core


class GateAndSignatureTests(unittest.TestCase):
    def test_equal_frustums_fill_viewport(self):
        gate = core.map_render_gate(
            (10, 20, 800, 600),
            (-2.0, 2.0, -1.5, 1.5),
            (-2.0, 2.0, -1.5, 1.5),
        )
        for actual, expected in zip(gate, (10.0, 20.0, 800.0, 600.0)):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_narrow_render_frustum_is_centered_inside_viewport(self):
        gate = core.map_render_gate(
            (0, 0, 1000, 500),
            (-2.0, 2.0, -1.0, 1.0),
            (-1.0, 1.0, -1.0, 1.0),
        )
        for actual, expected in zip(gate, (250.0, 0.0, 500.0, 500.0)):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_point_mapping_uses_gate_origin_and_size(self):
        self.assertEqual(
            core.map_point_to_gate((0.25, 0.75), (100, 50, 800, 400)),
            (300.0, 350.0),
        )

    def test_signature_is_order_independent_but_value_sensitive(self):
        first = core.render_signature(
            {"width": 1920, "height": 1080, "color": [1, 0, 0, 1]})
        second = core.render_signature(
            {"color": [1, 0, 0, 1], "height": 1080, "width": 1920})
        changed = core.render_signature(
            {"width": 1920, "height": 1080, "color": [0, 1, 0, 1]})
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)
        self.assertEqual(len(first), 40)

    def test_safe_identifier_removes_path_characters_and_unicode(self):
        self.assertEqual(core.safe_identifier(u"shot:01/\u76f8\u673a A"), "shot_01_A")

    def test_map_render_gate_rejects_zero_or_negative_dimensions(self):
        view = (-2.0, 2.0, -1.0, 1.0)
        with self.assertRaises(ValueError):
            core.map_render_gate((0, 0, 0, 500), view, view)
        with self.assertRaises(ValueError):
            core.map_render_gate((0, 0, 1000, 0), view, view)
        with self.assertRaises(ValueError):
            core.map_render_gate((0, 0, -1, 500), view, view)
        with self.assertRaises(ValueError):
            core.map_render_gate((0, 0, 1000, -1), view, view)

    def test_map_render_gate_rejects_degenerate_viewing_frustum(self):
        with self.assertRaises(ValueError):
            core.map_render_gate((0, 0, 100, 100), (1, 1, -1, 1),
                                 (0, 2, -1, 1))
        with self.assertRaises(ValueError):
            core.map_render_gate((0, 0, 100, 100), (-1, 1, 2, 2),
                                 (-1, 1, 0, 1))

    def test_safe_identifier_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            core.safe_identifier(42)

    def test_safe_identifier_collapses_whitespace_and_forbidden_runs(self):
        self.assertEqual(core.safe_identifier(" shot 01:/\\  take? "),
                         "shot_01_take")

    def test_safe_identifier_collapses_control_and_forbidden_runs(self):
        self.assertEqual(core.safe_identifier(u"a\x01\x02:/\\\x1fb"),
                         "a_b")

    def test_safe_identifier_returns_unnamed_for_all_non_ascii_input(self):
        self.assertEqual(core.safe_identifier(u"\u76f8\u673a"), "unnamed")


if __name__ == "__main__":
    unittest.main()
