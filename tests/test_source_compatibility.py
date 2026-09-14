from __future__ import absolute_import

import ast
import io
import os
import re
import unittest
import warnings


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILES = (
    "composition_guides_core.py",
    "composition_guides_plugin.py",
)

FORBIDDEN_PATTERNS = [
    r"(^|[^A-Za-z0-9_])f['\"]",
    r"\bdataclass\b",
    r"\bpathlib\b",
    r"def\s+\w+\([^)]*\)\s*->",
    r"async\s+def\b",
]

REGISTRATION_TOKENS = (
    "compositionGuidesLocator",
    "0x00087001",
    "drawdb/geometry/compositionGuidesLocator",
    "CompositionGuidesPlugin",
    "initializePlugin",
    "uninitializePlugin",
    "MPxDrawOverride",
    "MUIDrawManager",
    "MRenderItem.sActiveWireDepthPriority",
)

ATTRIBUTE_NAMES = (
    "cameraMessage",
    "enabled",
    "outputMode",
    "thirds",
    "goldenSpiral",
    "spiralOrientation",
    "goldenTriangle",
    "triangleDirection",
    "diagonal",
    "diagonalDown",
    "diagonalUp",
    "center",
    "centerCross",
    "centerCircle",
    "centerBox",
    "centerDiamond",
    "lineColor",
    "lineAlpha",
    "lineWidth",
    "dataVersion",
    "ownerTag",
    "renderImagePath",
    "renderSignature",
    "renderInProgress",
)

DRAW_TOKENS = (
    "line2d",
    "beginDrawable",
    "endDrawable",
    "getViewportDimensions",
    "getViewingFrustum",
    "getRenderingFrustum",
)


def _read_source(filename):
    path = os.path.join(PROJECT_ROOT, filename)
    with io.open(path, "r", encoding="utf-8") as source_file:
        return source_file.read()


class SourceCompatibilityTests(unittest.TestCase):

    def test_sources_parse_and_avoid_unsupported_python_syntax(self):
        for filename in SOURCE_FILES:
            source = _read_source(filename)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                ast.parse(source, filename=filename)
            for pattern in FORBIDDEN_PATTERNS:
                self.assertIsNone(
                    re.search(pattern, source, re.MULTILINE),
                    "%s contains forbidden pattern %s" % (filename, pattern),
                )

    def test_plugin_declares_required_registration_contract(self):
        source = _read_source("composition_guides_plugin.py")
        for token in REGISTRATION_TOKENS:
            self.assertIn(token, source)

    def test_plugin_declares_every_required_attribute(self):
        source = _read_source("composition_guides_plugin.py")
        for attribute_name in ATTRIBUTE_NAMES:
            self.assertIn(attribute_name, source)

    def test_render_in_progress_is_non_storable(self):
        source = _read_source("composition_guides_plugin.py")
        pattern = r"renderInProgress[\s\S]{0,600}?storable\s*=\s*False"
        self.assertIsNotNone(re.search(pattern, source))

    def test_plugin_declares_required_screen_space_draw_calls(self):
        source = _read_source("composition_guides_plugin.py")
        for token in DRAW_TOKENS:
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
