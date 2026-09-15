from __future__ import absolute_import

import ast
import io
import os
import re
import unittest
import warnings


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_FILES = (
    "composition_guides.py",
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

    def test_controller_exposes_scene_and_render_entry_points(self):
        path = os.path.join(PROJECT_ROOT, "composition_guides.py")
        self.assertTrue(os.path.isfile(path), "missing composition_guides.py")
        module = ast.parse(_read_source("composition_guides.py"))
        functions = dict((node.name, node) for node in module.body
                         if isinstance(node, ast.FunctionDef))
        for name, arguments in (
                ("resolve_selected_camera", []), ("find_config", ["camera_shape"]),
                ("create_or_update", ["camera_shape", "settings"]),
                ("set_visible", ["camera_shape", "visible"]),
                ("remove", ["camera_shape"]), ("clean_cache", ["camera_shape"]),
                ("refresh_render_overlay", ["camera_shape", "force"]),
                ("install_render_hooks", []), ("remove_render_hooks", []),
                ("_before_render", []), ("_after_render", []), ("show", [])):
            self.assertIn(name, functions)
            self.assertEqual(arguments, [arg.arg for arg in functions[name].args.args])
        self.assertIn("GuideError", [node.name for node in module.body
                                    if isinstance(node, ast.ClassDef)])

    def test_controller_retains_overlay_integration_contract(self):
        source = _read_source("composition_guides.py")
        for token in ("OpenAI.CompositionGuides", "QImage.Format_ARGB32",
                      "QPainter.Antialiasing", "defaultRenderGlobals.currentRenderer",
                      "defaultRenderGlobals.preRenderMel", "defaultRenderGlobals.postRenderMel",
                      "mayaHardware2", "CGUIDES_BEGIN", "CGUIDES_END",
                      "MSceneMessage.kBeforeSave"):
            self.assertIn(token, source)

    def test_controller_chooses_qt_by_import_capability(self):
        source = _read_source("composition_guides.py")
        self.assertRegex(source, r"try:[\s\S]*?from PySide6[\s\S]*?except ImportError:[\s\S]*?from PySide2")
        self.assertNotRegex(source, r"cmds\.about\([^)]*(?:version|apiVersion)")

    def test_controller_does_not_delete_unvalidated_node_listings(self):
        source = _read_source("composition_guides.py")
        module = ast.parse(source)
        for node in ast.walk(module):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "delete"):
                self.assertEqual(1, len(node.args))
                self.assertIsInstance(node.args[0], ast.Name)
        self.assertNotRegex(source, r"cmds\.delete\(\s*cmds\.ls")

    def test_controller_sets_depth_factor_with_internal_mplug_value(self):
        source = _read_source("composition_guides.py")
        self.assertNotIn(
            'cmds.setAttr(multiplier + ".input2", 1.01)', source)
        self.assertRegex(
            source,
            r"MSelectionList[\s\S]{0,500}?\.input2[\s\S]{0,300}?getPlug\(0\)[\s\S]{0,300}?setDouble\(1\.01\)")

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

    def test_plugin_opts_into_python_api_2(self):
        source = _read_source("composition_guides_plugin.py")
        module = ast.parse(source, filename="composition_guides_plugin.py")
        markers = [
            statement for statement in module.body
            if isinstance(statement, ast.FunctionDef)
            and statement.name == "maya_useNewAPI"
        ]
        self.assertEqual(1, len(markers))
        self.assertEqual([], markers[0].args.args)

    def test_draw_override_supports_all_viewport_2_backends(self):
        source = _read_source("composition_guides_plugin.py")
        module = ast.parse(source, filename="composition_guides_plugin.py")
        draw_classes = [
            statement for statement in module.body
            if isinstance(statement, ast.ClassDef)
            and statement.name == "CompositionGuidesDrawOverride"
        ]
        self.assertEqual(1, len(draw_classes))
        methods = [
            statement for statement in draw_classes[0].body
            if isinstance(statement, ast.FunctionDef)
            and statement.name == "supportedDrawAPIs"
        ]
        self.assertEqual(1, len(methods))
        returns = [
            statement for statement in methods[0].body
            if isinstance(statement, ast.Return)
        ]
        self.assertEqual(1, len(returns))
        attributes = set(
            node.attr for node in ast.walk(returns[0].value)
            if isinstance(node, ast.Attribute) and node.attr.startswith("k")
        )
        self.assertEqual(set((
            "kOpenGL", "kOpenGLCoreProfile", "kDirectX11")), attributes)
        bitwise_ors = [
            node for node in ast.walk(returns[0].value)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)
        ]
        self.assertEqual(2, len(bitwise_ors))


if __name__ == "__main__":
    unittest.main()
