from __future__ import division

import math
import unittest

import composition_guides_core as core


class CoreGeometryTests(unittest.TestCase):
    def test_thirds_has_four_expected_lines(self):
        geometry = core.thirds_geometry()
        self.assertEqual(geometry["polylines"], [])
        self.assertEqual(geometry["segments"], [
            ((1.0 / 3.0, 0.0), (1.0 / 3.0, 1.0)),
            ((2.0 / 3.0, 0.0), (2.0 / 3.0, 1.0)),
            ((0.0, 1.0 / 3.0), (1.0, 1.0 / 3.0)),
            ((0.0, 2.0 / 3.0), (1.0, 2.0 / 3.0)),
        ])

    def test_center_box_is_width_and_height_25_percent(self):
        geometry = core.center_geometry(False, False, True, False)
        self.assertEqual(geometry["segments"], [
            ((0.375, 0.375), (0.625, 0.375)),
            ((0.625, 0.375), (0.625, 0.625)),
            ((0.625, 0.625), (0.375, 0.625)),
            ((0.375, 0.625), (0.375, 0.375)),
        ])

    def test_center_diamond_connects_edge_midpoints(self):
        geometry = core.center_geometry(False, False, False, True)
        self.assertEqual(geometry["segments"], [
            ((0.5, 0.0), (1.0, 0.5)),
            ((1.0, 0.5), (0.5, 1.0)),
            ((0.5, 1.0), (0.0, 0.5)),
            ((0.0, 0.5), (0.5, 0.0)),
        ])

    def test_center_circle_has_ten_percent_short_side_diameter(self):
        width, height = 1920.0, 1080.0
        geometry = core.center_geometry(False, True, False, False,
                                       pixel_width=width, pixel_height=height,
                                       circle_steps=64)
        points = geometry["polylines"][0]
        self.assertEqual(len(points), 65)
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        self.assertAlmostEqual((max(xs) - min(xs)) * width, 108.0)
        self.assertAlmostEqual((max(ys) - min(ys)) * height, 108.0)

    def test_golden_triangle_helpers_are_perpendicular_in_pixel_space(self):
        for width, height in ((1920.0, 1080.0), (1080.0, 1920.0), (1000.0, 1000.0)):
            for direction in ("down", "up"):
                geometry = core.golden_triangle_geometry(direction, width, height)
                main = geometry["segments"][0]
                main_vector = ((main[1][0] - main[0][0]) * width,
                               (main[1][1] - main[0][1]) * height)
                for helper in geometry["segments"][1:]:
                    helper_vector = ((helper[1][0] - helper[0][0]) * width,
                                     (helper[1][1] - helper[0][1]) * height)
                    dot = (main_vector[0] * helper_vector[0] +
                           main_vector[1] * helper_vector[1])
                    self.assertAlmostEqual(dot, 0.0, delta=1e-6)

    def test_golden_spiral_orientations_are_mirrors(self):
        top_left = core.golden_spiral_geometry("top_left")["polylines"][0]
        top_right = core.golden_spiral_geometry("top_right")["polylines"][0]
        self.assertEqual(len(top_left), len(top_right))
        for left_point, right_point in zip(top_left, top_right):
            self.assertAlmostEqual(left_point[0], 1.0 - right_point[0])
            self.assertAlmostEqual(left_point[1], right_point[1])


if __name__ == "__main__":
    unittest.main()
