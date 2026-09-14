from __future__ import division

import math

try:
    _STRING_TYPES = (basestring,)
except NameError:
    _STRING_TYPES = (str,)


def empty_geometry():
    return {"segments": [], "polylines": []}


def thirds_geometry():
    return {"segments": [
        ((1.0 / 3.0, 0.0), (1.0 / 3.0, 1.0)),
        ((2.0 / 3.0, 0.0), (2.0 / 3.0, 1.0)),
        ((0.0, 1.0 / 3.0), (1.0, 1.0 / 3.0)),
        ((0.0, 2.0 / 3.0), (1.0, 2.0 / 3.0)),
    ], "polylines": []}


def diagonal_geometry(downward, upward):
    geometry = empty_geometry()
    if downward:
        geometry["segments"].append(((0.0, 0.0), (1.0, 1.0)))
    if upward:
        geometry["segments"].append(((0.0, 1.0), (1.0, 0.0)))
    return geometry


def center_geometry(cross, circle, center_box, diamond, pixel_width=1.0,
                    pixel_height=1.0, circle_steps=64):
    if pixel_width <= 0 or pixel_height <= 0:
        raise ValueError("pixel dimensions must be positive")
    geometry = empty_geometry()
    if cross:
        geometry["segments"].extend([
            ((0.5, 0.0), (0.5, 1.0)),
            ((0.0, 0.5), (1.0, 0.5)),
        ])
    if center_box:
        geometry["segments"].extend([
            ((0.375, 0.375), (0.625, 0.375)),
            ((0.625, 0.375), (0.625, 0.625)),
            ((0.625, 0.625), (0.375, 0.625)),
            ((0.375, 0.625), (0.375, 0.375)),
        ])
    if diamond:
        geometry["segments"].extend([
            ((0.5, 0.0), (1.0, 0.5)),
            ((1.0, 0.5), (0.5, 1.0)),
            ((0.5, 1.0), (0.0, 0.5)),
            ((0.0, 0.5), (0.5, 0.0)),
        ])
    if circle:
        steps = int(circle_steps)
        if steps <= 0:
            raise ValueError("circle_steps must be positive")
        radius_px = 0.05 * min(pixel_width, pixel_height)
        radius_x = radius_px / pixel_width
        radius_y = radius_px / pixel_height
        points = []
        for index in range(steps + 1):
            angle = 2.0 * math.pi * index / steps
            points.append((0.5 + radius_x * math.cos(angle),
                          0.5 + radius_y * math.sin(angle)))
        geometry["polylines"].append(points)
    return geometry


def _clamp_edge(value):
    if abs(value) <= 1e-12:
        return 0.0
    if abs(value - 1.0) <= 1e-12:
        return 1.0
    return value


def golden_spiral_geometry(orientation, steps=96):
    if orientation not in ("top_left", "top_right", "bottom_left", "bottom_right"):
        raise ValueError("unknown spiral orientation")
    steps = int(steps)
    if steps <= 0:
        raise ValueError("steps must be positive")
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    canonical = []
    turns = 4.0
    for index in range(steps + 1):
        theta = 2.0 * math.pi * turns * index / steps
        radius = phi ** (theta / (math.pi / 2.0))
        canonical.append((radius * math.cos(theta), radius * math.sin(theta)))
    min_x = min(point[0] for point in canonical)
    max_x = max(point[0] for point in canonical)
    min_y = min(point[1] for point in canonical)
    max_y = max(point[1] for point in canonical)
    points = [((_clamp_edge((x - min_x) / (max_x - min_x))),
               _clamp_edge((y - min_y) / (max_y - min_y)))
              for x, y in canonical]
    if "right" in orientation:
        points = [(1.0 - x, y) for x, y in points]
    if "bottom" in orientation:
        points = [(x, 1.0 - y) for x, y in points]
    return {"segments": [], "polylines": [points]}


def _project_pixel_point_to_diagonal(point, start, end, pixel_width, pixel_height):
    ax, ay = start[0] * pixel_width, start[1] * pixel_height
    bx, by = end[0] * pixel_width, end[1] * pixel_height
    px, py = point[0] * pixel_width, point[1] * pixel_height
    dx, dy = bx - ax, by - ay
    t_value = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    return ((ax + t_value * dx) / pixel_width,
            (ay + t_value * dy) / pixel_height)


def golden_triangle_geometry(direction, pixel_width, pixel_height):
    if pixel_width <= 0 or pixel_height <= 0:
        raise ValueError("pixel dimensions must be positive")
    if direction == "down":
        start, end = (0.0, 1.0), (1.0, 0.0)
        corners = ((0.0, 0.0), (1.0, 1.0))
    elif direction == "up":
        start, end = (0.0, 0.0), (1.0, 1.0)
        corners = ((0.0, 1.0), (1.0, 0.0))
    else:
        raise ValueError("direction must be 'down' or 'up'")
    geometry = {"segments": [(start, end)], "polylines": []}
    for corner in corners:
        projection = _project_pixel_point_to_diagonal(
            corner, start, end, pixel_width, pixel_height)
        geometry["segments"].append((corner, projection))
    return geometry


def _append_geometry(target, source):
    target["segments"].extend(source["segments"])
    target["polylines"].extend(source["polylines"])


def compose_geometry(options, pixel_width, pixel_height):
    result = empty_geometry()
    if options.get("thirds"):
        _append_geometry(result, thirds_geometry())
    spiral = options.get("golden_spiral")
    if spiral:
        orientation = spiral if isinstance(spiral, _STRING_TYPES) else options.get("spiral_orientation", "top_left")
        _append_geometry(result, golden_spiral_geometry(orientation, options.get("spiral_steps", 96)))
    triangle = options.get("golden_triangle")
    if triangle:
        direction = triangle if isinstance(triangle, _STRING_TYPES) else options.get("triangle_direction", "down")
        _append_geometry(result, golden_triangle_geometry(direction, pixel_width, pixel_height))
    _append_geometry(result, diagonal_geometry(options.get("downward", options.get("diagonals_down", False)),
                                              options.get("upward", options.get("diagonals_up", False))))
    center = options.get("center")
    if isinstance(center, dict):
        _append_geometry(result, center_geometry(
            center.get("cross", False), center.get("circle", False),
            center.get("center_box", center.get("box", False)), center.get("diamond", False),
            pixel_width, pixel_height, center.get("circle_steps", 64)))
    return result
