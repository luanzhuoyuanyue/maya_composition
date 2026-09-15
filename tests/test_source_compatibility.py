# -*- coding: utf-8 -*-
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
    "install_composition_guides.py",
    "maya_smoke_test.py",
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

    def test_final_package_has_exact_required_deliverables(self):
        for filename in SOURCE_FILES + ("README_CN.md",):
            self.assertTrue(os.path.isfile(os.path.join(PROJECT_ROOT, filename)),
                            "missing " + filename)

    def test_installer_exposes_safe_installation_contract(self):
        self.assertTrue(os.path.isfile(os.path.join(PROJECT_ROOT, "install_composition_guides.py")),
                        "missing install_composition_guides.py")
        source = _read_source("install_composition_guides.py")
        names = [node.name for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)]
        self.assertIn("install", names)
        self.assertIn("uninstall", names)
        for token in ("cmds.internalVar(userScriptDir=True)", "cmds.internalVar(userAppDir=True)",
                      "cmds.loadPlugin", "cmds.pluginInfo", "cmds.shelfButton",
                      "Maya Composition Guides", "import composition_guides; composition_guides.show()"):
            self.assertIn(token, source)
        self.assertNotRegex(source, r"(?:glob\s*\(|rmtree\([^\n]*[\"'][*?])")

    def test_smoke_test_is_explicit_and_has_named_lifecycle_checks(self):
        self.assertTrue(os.path.isfile(os.path.join(PROJECT_ROOT, "maya_smoke_test.py")),
                        "missing maya_smoke_test.py")
        source = _read_source("maya_smoke_test.py")
        self.assertIn("def run_smoke_test(allow_new_scene=False):", source)
        for name in ("camera_types", "idempotent_configs", "ownership_connections", "near_clip_depth",
                     "png_rgba_640x360", "output_mode_states", "scoped_removal"):
            self.assertIn(name, source)

    def test_readme_documents_installation_modes_and_limits(self):
        self.assertTrue(os.path.isfile(os.path.join(PROJECT_ROOT, "README_CN.md")),
                        "missing README_CN.md")
        source = _read_source("README_CN.md")
        for token in (u"Maya 2018–2026", "Maya Hardware 2.0", "Shelf", "Script Editor",
                      u"仅视口", u"仅硬件渲染", u"两者", u"中心 25%", u"中心菱形",
                      u"缓存", u"卸载", "run_smoke_test(allow_new_scene=True)"):
            self.assertIn(token, source)

    def test_gui_exposes_native_controls_and_stable_keys(self):
        source = _read_source("composition_guides.py")
        module = ast.parse(source)
        self.assertIn("CompositionGuidesWindow", [node.name for node in module.body
                                               if isinstance(node, ast.ClassDef)])
        for key in ("camera", "output_mode", "thirds", "spiral",
                    "spiral_orientation", "triangle", "triangle_direction",
                    "diagonal_down", "diagonal_up", "center_cross", "center_circle",
                    "center_box", "center_diamond", "color", "alpha", "line_width"):
            self.assertIn('"' + key + '"', source)
        for control in ("window", "columnLayout", "frameLayout", "optionMenuGrp",
                        "checkBoxGrp", "colorSliderGrp", "floatSliderGrp", "button"):
            self.assertIn("cmds." + control + "(", source)

    def test_gui_has_requested_actions_without_qt_widgets(self):
        source = _read_source("composition_guides.py")
        for label in (u"从选择获取", u"创建 / 更新", u"显示 / 隐藏", u"删除", u"清理缓存"):
            self.assertIn(label, source)
        self.assertNotRegex(source, r"\b(?:QWidget|QDialog|QMainWindow)\s*\(")

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
            self.assertTrue(os.path.isfile(os.path.join(PROJECT_ROOT, filename)),
                            "missing " + filename)
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
