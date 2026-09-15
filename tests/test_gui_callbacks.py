# -*- coding: utf-8 -*-
from __future__ import absolute_import

import unittest

from test_controller_recovery import _FakeCmds, _load_controller


class _NativeUI(_FakeCmds):
    """Maya controls need a GUI session; keep only their command boundary here."""

    def __init__(self):
        super(_NativeUI, self).__init__()
        self.controls = {}
        self.windows = set()
        self.confirmations = []
        self.answer = u"是"
        self.refreshes = 0

    def window(self, name, **kwargs):
        if kwargs.get("exists"):
            return name in self.windows
        if not kwargs.get("edit"):
            self.windows.add(name)
        return name

    def showWindow(self, name):
        self.shown = name

    def deleteUI(self, name, **kwargs):
        self.windows.remove(name)

    def setParent(self, *args, **kwargs):
        pass

    def refresh(self, **kwargs):
        assert kwargs == {"force": True}
        self.refreshes += 1

    def confirmDialog(self, **kwargs):
        self.confirmations.append(kwargs)
        return self.answer

    def setAttr(self, plug, *values, **kwargs):
        self.calls.append((plug, values, kwargs))
        self.values[plug] = [tuple(values)] if kwargs.get("type") == "double3" else values[0]

    def __getattr__(self, kind):
        if kind not in ("columnLayout", "frameLayout", "rowLayout", "text",
                        "textFieldGrp", "optionMenuGrp", "menuItem", "checkBoxGrp",
                        "colorSliderGrp", "floatSliderGrp", "button"):
            raise AttributeError(kind)

        def control(name=None, **kwargs):
            if kwargs.pop("query", False):
                return self.controls[name][next(iter(kwargs))]
            if kwargs.pop("edit", False):
                self.controls[name].update(kwargs)
                return name
            name = name or kind + str(len(self.controls))
            self.controls[name] = kwargs
            return name
        return control

    def change(self, window, key, value):
        control = self.controls[window.controls[key]]
        field = "value1" if "value1" in control else (
            "select" if "select" in control else "rgbValue" if "rgbValue" in control else "value")
        control[field] = value
        control["changeCommand"](value)

    def press(self, label):
        matches = [control for control in self.controls.values()
                   if control.get("label") == label and "command" in control]
        assert len(matches) == 1, (label, matches)
        matches[0]["command"]()


DEFAULTS = {
    "enabled": True, "outputMode": 2, "thirds": True,
    "goldenSpiral": False, "spiralOrientation": 0,
    "goldenTriangle": False, "triangleDirection": 0,
    "diagonal": False, "diagonalDown": True, "diagonalUp": True,
    "center": False, "centerCross": True, "centerCircle": True,
    "centerBox": False, "centerDiamond": False,
    "lineColor": (1.0, 1.0, 0.0), "lineAlpha": 0.8, "lineWidth": 2.0,
}
CAMERA = "|group|camera|cameraShape"


class GuiCallbackTests(unittest.TestCase):

    def setUp(self):
        self.cmds = _NativeUI()
        self.controller = _load_controller(self.cmds)
        self.config = None
        self.controller.resolve_selected_camera = lambda: CAMERA
        self.controller._camera_shape = lambda camera: camera
        self.controller.find_config = lambda camera: self.config
        self.created = []
        self.overlays = []
        self.controller.create_or_update = self._create
        self.controller.refresh_render_overlay = lambda camera, force=False: self.overlays.append((camera, force))
        self.assertTrue(hasattr(self.controller, "CompositionGuidesWindow"),
                        "missing native GUI implementation")
        self.window = self.controller.show()

    def _create(self, camera, settings):
        self.created.append((camera, settings))
        self.config = "config"
        self._scene_settings(settings)
        return self.config

    def _scene_settings(self, settings):
        for key, value in settings.items():
            attribute = "centerEnabled" if key == "center" else key
            self.cmds.values["config." + attribute] = [tuple(value)] if key == "lineColor" else value
        self.cmds.values["config.center"] = [(0.0, 0.0, 0.0)]

    def _bind_existing(self, settings=None):
        self.config = "config"
        self._scene_settings(settings or DEFAULTS)
        self.cmds.press(u"从选择获取")

    def test_creation_uses_exact_defaults_and_forces_both_overlay(self):
        self.cmds.press(u"创建 / 更新")
        self.assertEqual([(CAMERA, DEFAULTS)], self.created)
        self.assertEqual([(CAMERA, True)], self.overlays)

    def test_all_preserves_subguide_values_and_directions(self):
        for key, value in (("diagonal_down", False), ("center_circle", False),
                           ("center_box", True), ("spiral_orientation", 4),
                           ("triangle_direction", 2)):
            self.cmds.change(self.window, key, value)
        self.cmds.change(self.window, "all", True)
        self.cmds.press(u"创建 / 更新")
        expected = dict(DEFAULTS, goldenSpiral=True, goldenTriangle=True,
                        diagonal=True, center=True, diagonalDown=False,
                        centerCircle=False, centerBox=True,
                        spiralOrientation=3, triangleDirection=1)
        self.assertEqual(expected, self.created[0][1])

    def test_manual_family_convergence_updates_all_without_extra_writes(self):
        self._bind_existing()
        for key in ("spiral", "triangle", "diagonal", "center"):
            self.cmds.change(self.window, key, True)
        self.assertTrue(self.cmds.controls[self.window.controls["all"]]["value1"])
        self.assertEqual(["config.goldenSpiral", "config.goldenTriangle",
                          "config.diagonal", "config.centerEnabled"], [c[0] for c in self.cmds.calls])
        self.cmds.change(self.window, "thirds", False)
        self.assertFalse(self.cmds.controls[self.window.controls["all"]]["value1"])

    def test_loading_existing_settings_preserves_hidden_state_without_writes(self):
        settings = dict(DEFAULTS, enabled=False, outputMode=0, thirds=False,
                        goldenSpiral=True, spiralOrientation=2, goldenTriangle=True,
                        triangleDirection=1, diagonal=True, diagonalDown=False,
                        diagonalUp=False, center=True, centerCross=False,
                        centerCircle=False, centerBox=True, centerDiamond=True,
                        lineColor=(0.2, 0.3, 0.4), lineAlpha=0.3, lineWidth=7.0)
        self._bind_existing(settings)
        self.assertEqual([], self.cmds.calls)
        self.cmds.press(u"创建 / 更新")
        self.assertEqual(settings, self.created[0][1])
        self.assertEqual([], self.overlays)

    def test_live_change_writes_only_changed_attribute_and_never_png(self):
        self._bind_existing()
        self.cmds.change(self.window, "alpha", 0.25)
        self.assertEqual([("config.lineAlpha", (0.25,), {})], self.cmds.calls)
        self.assertEqual(1, self.cmds.refreshes)
        self.assertEqual([], self.created)
        self.assertEqual([], self.overlays)

    def test_loading_center_master_uses_boolean_setting_not_locator_center(self):
        self._bind_existing(dict(DEFAULTS, center=False))
        self.assertFalse(self.window._settings()["center"])
        self._bind_existing(dict(DEFAULTS, center=True))
        self.assertTrue(self.window._settings()["center"])

    def test_live_center_change_preserves_inherited_locator_center(self):
        self._bind_existing()
        self.cmds.change(self.window, "center", True)
        self.assertEqual([("config.centerEnabled", (True,), {})], self.cmds.calls)
        self.assertEqual([(0.0, 0.0, 0.0)], self.cmds.values["config.center"])

    def test_color_and_enum_changes_map_to_node_values(self):
        self._bind_existing()
        self.cmds.change(self.window, "color", (0.1, 0.6, 0.9))
        self.cmds.change(self.window, "output_mode", 2)
        self.cmds.change(self.window, "spiral_orientation", 3)
        self.cmds.change(self.window, "triangle_direction", 2)
        self.assertEqual([
            ("config.lineColor", (0.1, 0.6, 0.9), {"type": "double3"}),
            ("config.outputMode", (1,), {}),
            ("config.spiralOrientation", (2,), {}),
            ("config.triangleDirection", (1,), {})], self.cmds.calls)
        self.assertEqual([], self.overlays)

    def test_all_live_update_writes_only_five_family_masters(self):
        self._bind_existing()
        self.cmds.change(self.window, "all", False)
        self.assertEqual(set(("config.thirds", "config.goldenSpiral", "config.goldenTriangle",
                              "config.diagonal", "config.centerEnabled")), set(c[0] for c in self.cmds.calls))
        self.assertTrue(all(call[1] == (False,) for call in self.cmds.calls))
        self.assertEqual(1, self.cmds.refreshes)

    def test_binding_without_config_resets_defaults(self):
        self._bind_existing(dict(DEFAULTS, enabled=False, lineAlpha=0.1))
        self.config = None
        self.cmds.press(u"从选择获取")
        self.cmds.press(u"创建 / 更新")
        self.assertEqual(DEFAULTS, self.created[0][1])

    def test_deleted_camera_creation_uses_exact_selection(self):
        self.cmds.press(u"从选择获取")
        def missing(camera):
            if camera == CAMERA:
                raise self.controller.GuideError(u"相机已删除")
            return camera
        self.controller._camera_shape = missing
        self.controller.resolve_selected_camera = lambda: "|newCamera|newShape"
        self.cmds.press(u"创建 / 更新")
        self.assertEqual("|newCamera|newShape", self.created[0][0])
        self.assertEqual("|newCamera|newShape", self.window.camera)
        self.assertFalse(any(call[0] == "warning" for call in self.cmds.calls))

    def test_visibility_uses_current_node_state_and_controller(self):
        self._bind_existing()
        toggles = []
        self.controller.set_visible = lambda camera, value: toggles.append((camera, value))
        self.cmds.values["config.enabled"] = False
        self.cmds.press(u"显示 / 隐藏（当前显示）")
        self.assertEqual([(CAMERA, True)], toggles)
        self.assertEqual(1, self.cmds.refreshes)

    def test_delete_confirms_camera_once_and_preserves_binding_and_controls(self):
        self._bind_existing()
        removed = []
        def remove(camera):
            removed.append(camera)
            self.config = None
        self.controller.remove = remove
        self.cmds.change(self.window, "alpha", 0.4)
        self.cmds.answer = u"否"
        self.cmds.press(u"删除")
        self.assertEqual([], removed)
        self.cmds.answer = u"是"
        self.cmds.press(u"删除")
        self.assertEqual([CAMERA], removed)
        self.assertEqual(2, len(self.cmds.confirmations))
        self.assertIn(CAMERA, self.cmds.confirmations[-1]["message"])
        self.cmds.press(u"创建 / 更新")
        self.assertEqual(CAMERA, self.created[0][0])
        self.assertEqual(0.4, self.created[0][1]["lineAlpha"])

    def test_cache_cleanup_requires_confirmation_and_calls_scene_scope(self):
        cleaned = []
        self.controller.clean_cache = lambda: cleaned.append("scene")
        self.cmds.answer = u"否"
        self.cmds.press(u"清理缓存")
        self.assertEqual([], cleaned)
        self.cmds.answer = u"是"
        self.cmds.press(u"清理缓存")
        self.assertEqual(["scene"], cleaned)
        self.assertEqual(2, len(self.cmds.confirmations))

    def test_recoverable_error_warns_and_unexpected_error_reraises(self):
        def fail():
            raise self.controller.GuideError(u"请选择相机")
        self.controller.resolve_selected_camera = fail
        self.cmds.press(u"从选择获取")
        self.assertTrue(any(c[0] == "warning" for c in self.cmds.calls))
        self.assertTrue(self.cmds.controls[self.window.controls["status"]]["label"].startswith(u"错误："))
        def bug():
            raise ValueError("unexpected")
        self.controller.resolve_selected_camera = bug
        with self.assertRaises(ValueError):
            self.cmds.press(u"从选择获取")
        self.assertTrue(self.cmds.controls[self.window.controls["status"]]["label"].startswith(u"错误："))

    def test_show_reuses_live_instance_and_rebuilds_after_close(self):
        self.assertIs(self.window, self.controller.show())
        self.assertEqual(1, len(self.cmds.windows))
        self.cmds.deleteUI(self.window.window)
        reopened = self.controller.show()
        self.assertIn(reopened.window, self.cmds.windows)
        self.assertEqual(1, len(self.cmds.windows))
        self.assertEqual(2, len(self.controller._callback_ids))


class CenterStorageTests(unittest.TestCase):

    def test_create_and_update_write_public_center_to_center_enabled(self):
        for existing in (None, "config"):
            cmds = _NativeUI()
            controller = _load_controller(cmds)
            controller._camera_shape = lambda camera: camera
            controller.find_config = lambda camera: existing
            controller._long = lambda node: node
            controller._ordinary_state = lambda config: None
            cmds.allNodeTypes = lambda: ["compositionGuidesLocator"]
            cmds.undoInfo = lambda **kwargs: None
            cmds.createNode = lambda kind, **kwargs: "config"
            cmds.connectAttr = lambda source, destination: None
            cmds.listRelatives = lambda node, **kwargs: ["transform"]
            cmds.attributeQuery = lambda attribute, **kwargs: False
            cmds.values["config.outputMode"] = 0

            self.assertEqual("config", controller.create_or_update(
                CAMERA, {"center": True, "thirds": False}))

            self.assertIn(("config.centerEnabled", (True,), {}), cmds.calls)
            self.assertIn(("config.thirds", (False,), {}), cmds.calls)
            self.assertNotIn("config.center", [call[0] for call in cmds.calls])

    def test_render_settings_read_center_enabled_under_public_center_key(self):
        cmds = _NativeUI()
        controller = _load_controller(cmds)
        controller._uuid = lambda camera: "camera-uuid"
        for key, value in DEFAULTS.items():
            attribute = "centerEnabled" if key == "center" else key
            cmds.values["config." + attribute] = [value] if key == "lineColor" else value
        cmds.values.update({"config.center": [(0.0, 0.0, 0.0)],
                            "defaultResolution.width": 640,
                            "defaultResolution.height": 360,
                            "defaultResolution.pixelAspect": 1.0})
        for enabled in (False, True):
            cmds.values["config.centerEnabled"] = enabled
            settings = controller._render_settings("config", CAMERA)
            self.assertIs(enabled, settings["center"])
            self.assertNotIn("centerEnabled", settings)


if __name__ == "__main__":
    unittest.main()
