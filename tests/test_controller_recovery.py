from __future__ import absolute_import

import importlib
import os
import shutil
import sys
import tempfile
import types
import unittest


class _FakeCmds(object):

    def __init__(self):
        self.calls = []
        self.failure_for = None
        self.values = {}

    def allNodeTypes(self):
        return []

    def ls(self, *unused, **unused_keywords):
        return []

    def setAttr(self, plug, value, **unused_keywords):
        self.calls.append((plug, value))
        if self.failure_for is not None:
            message = self.failure_for(plug, value, self.calls)
            if message is not None:
                raise RuntimeError(message)

    def getAttr(self, plug):
        return self.values[plug]

    def warning(self, message):
        self.calls.append(("warning", message))


def _load_controller(fake_cmds):
    maya = types.ModuleType("maya")
    maya.__path__ = []
    api = types.ModuleType("maya.api")
    open_maya = types.ModuleType("maya.api.OpenMaya")
    internal_set_values = []

    class MMessage(object):

        @staticmethod
        def removeCallback(callback_id):
            return None

    class MSceneMessage(object):
        kBeforeSave = 1
        kAfterOpen = 2

        @staticmethod
        def addCallback(event, callback):
            return event

    class MSelectionList(object):

        def add(self, plug_name):
            self.plug_name = plug_name

        def getPlug(self, index):
            if index != 0:
                raise IndexError(index)

            class MPlug(object):

                def setDouble(self, value):
                    internal_set_values.append((self.plug_name, value))

            plug = MPlug()
            plug.plug_name = self.plug_name
            return plug

    open_maya.MMessage = MMessage
    open_maya.MSceneMessage = MSceneMessage
    open_maya.MSelectionList = MSelectionList
    open_maya.internal_set_values = internal_set_values

    qt_core = types.ModuleType("PySide2.QtCore")
    qt_gui = types.ModuleType("PySide2.QtGui")

    class Qt(object):
        RoundCap = 1
        RoundJoin = 2

    class QImage(object):
        Format_ARGB32 = 1

    class QPainter(object):
        Antialiasing = 1

    class QFileInfo(object):

        def __init__(self, path):
            self.path = path

        def exists(self):
            try:
                os.stat(self.path)
                return True
            except OSError:
                return False

        def size(self):
            try:
                return os.stat(self.path).st_size
            except OSError:
                return 0

    class QFile(object):

        @staticmethod
        def remove(path):
            try:
                os.remove(path)
                return True
            except OSError:
                return False

    qt_core.QFile = QFile
    qt_core.QFileInfo = QFileInfo
    qt_core.QPointF = object
    qt_core.Qt = Qt
    qt_gui.QColor = object
    qt_gui.QImage = QImage
    qt_gui.QPainter = QPainter
    qt_gui.QPen = object

    modules = {
        "maya": maya,
        "maya.cmds": fake_cmds,
        "maya.api": api,
        "maya.api.OpenMaya": open_maya,
        "PySide2": types.ModuleType("PySide2"),
        "PySide2.QtCore": qt_core,
        "PySide2.QtGui": qt_gui,
    }
    previous = dict((name, sys.modules.get(name)) for name in modules)
    previous_controller = sys.modules.pop("composition_guides", None)
    try:
        sys.modules.update(modules)
        return importlib.import_module("composition_guides")
    finally:
        sys.modules.pop("composition_guides", None)
        if previous_controller is not None:
            sys.modules["composition_guides"] = previous_controller
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class ControllerRecoveryTests(unittest.TestCase):

    @staticmethod
    def _last_value(calls, plug):
        return [value for candidate, value in calls if candidate == plug][-1]

    def test_multiplier_factor_uses_an_internal_mplug_value(self):
        fake_cmds = _FakeCmds()
        controller = _load_controller(fake_cmds)

        controller._set_multiplier_factor("multiplier")

        self.assertEqual(
            [("multiplier.input2", 1.01)],
            controller.om.internal_set_values)
        self.assertFalse(any(call[0] == "multiplier.input2"
                             for call in fake_cmds.calls))

    def test_owned_image_plane_uses_rgba_display_mode(self):
        fake_cmds = _FakeCmds()
        fake_cmds.attributeQuery = lambda *unused, **unused_keywords: False
        controller = _load_controller(fake_cmds)
        controller._config_camera = lambda config: "camera" if config == "config" else None
        controller._dependency = lambda config, kind: {
            "imagePlane": "ownedPlane", "multDoubleLinear": "multiplier",
        }[kind]
        controller._connect = lambda source, destination: None
        controller._set_multiplier_factor = lambda multiplier: None

        self.assertEqual("ownedPlane", controller._ensure_plane("config"))

        display_modes = [value for plug, value in fake_cmds.calls
                         if plug == "ownedPlane.displayMode"]
        self.assertEqual([3], display_modes)
        self.assertNotIn(4, display_modes)

    def test_after_render_continues_after_a_plane_hide_failure(self):
        fake_cmds = _FakeCmds()
        fake_cmds.failure_for = lambda plug, value, calls: (
            "bad plane cannot be hidden"
            if plug == "badPlane.visibility" and value is False else None)
        controller = _load_controller(fake_cmds)
        controller._configs = lambda: ["badConfig", "goodConfig"]
        controller._config_camera = lambda config: config
        controller._dependency = lambda config, kind: {
            "badConfig": "badPlane", "goodConfig": "goodPlane",
        }.get(config) if kind == "imagePlane" else None

        controller._after_render()

        self.assertIn(("badConfig.renderInProgress", False), fake_cmds.calls)
        self.assertIn(("goodPlane.visibility", False), fake_cmds.calls)
        self.assertIn(("goodConfig.renderInProgress", False), fake_cmds.calls)
        self.assertTrue(any(call[0] == "warning" for call in fake_cmds.calls))

    def test_before_render_recovers_display_failure_and_continues(self):
        fake_cmds = _FakeCmds()

        def failure_for(plug, value, calls):
            previous = calls[:-1]
            if plug == "badPlane.visibility" and value is True:
                return "plane display failed"
            if (plug == "badPlane.visibility" and value is False and
                    ("badPlane.visibility", True) in previous):
                return "plane recovery hide failed"
            return None

        fake_cmds.failure_for = failure_for
        fake_cmds.values = {
            "defaultRenderGlobals.currentRenderer": "mayaHardware2",
            "badConfig.enabled": True,
            "goodConfig.enabled": True,
            "badConfig.outputMode": 1,
            "goodConfig.outputMode": 1,
        }
        controller = _load_controller(fake_cmds)
        controller._configs = lambda: ["badConfig", "goodConfig"]
        controller._config_camera = lambda config: config
        controller._dependency = lambda config, kind: {
            "badConfig": "badPlane", "goodConfig": "goodPlane",
        }.get(config) if kind == "imagePlane" else None
        controller.refresh_render_overlay = lambda camera: camera

        controller._before_render()

        self.assertEqual(
            False, self._last_value(fake_cmds.calls,
                                    "badConfig.renderInProgress"))
        self.assertEqual(
            True, self._last_value(fake_cmds.calls,
                                   "goodConfig.renderInProgress"))
        self.assertEqual(
            True, self._last_value(fake_cmds.calls,
                                   "goodPlane.visibility"))
        warnings = [message for plug, message in fake_cmds.calls
                    if plug == "warning"]
        self.assertIn("badConfig", "\n".join(warnings))
        self.assertIn("plane display failed", "\n".join(warnings))
        self.assertIn("plane recovery hide failed", "\n".join(warnings))

    def test_before_render_warns_and_does_not_change_other_renderer(self):
        fake_cmds = _FakeCmds()
        fake_cmds.values = {
            "defaultRenderGlobals.currentRenderer": "arnold",
            "guideConfig.enabled": True,
            "guideConfig.outputMode": 1,
        }
        controller = _load_controller(fake_cmds)
        controller._configs = lambda: ["guideConfig"]

        controller._before_render()

        warnings = [message for plug, message in fake_cmds.calls
                    if plug == "warning"]
        self.assertIn("Maya Hardware 2.0", "\n".join(warnings))
        self.assertFalse(any(
            plug == "defaultRenderGlobals.currentRenderer"
            for plug, value in fake_cmds.calls if plug != "warning"))

    def test_before_render_stays_quiet_without_active_hardware_overlay(self):
        fake_cmds = _FakeCmds()
        fake_cmds.values = {
            "defaultRenderGlobals.currentRenderer": "arnold",
            "viewportConfig.enabled": True,
            "viewportConfig.outputMode": 0,
            "hiddenConfig.enabled": False,
            "hiddenConfig.outputMode": 2,
        }
        controller = _load_controller(fake_cmds)
        controller._configs = lambda: ["viewportConfig", "hiddenConfig"]

        controller._before_render()

        self.assertFalse(any(plug == "warning" for plug, value in fake_cmds.calls))


class _PngImage(object):
    save_result = True
    write_file = True
    file_content = b"png"
    reload_is_null = False
    reload_width = 8
    reload_height = 6
    reload_has_alpha = True

    def __init__(self, *arguments):
        self.arguments = arguments

    def fill(self, value):
        pass

    def save(self, path, format_name):
        if self.write_file:
            with open(path, "wb") as png_file:
                png_file.write(self.file_content)
        return self.save_result

    def isNull(self):
        return self.reload_is_null

    def width(self):
        return self.reload_width

    def height(self):
        return self.reload_height

    def hasAlphaChannel(self):
        return self.reload_has_alpha


class _PngPainter(object):
    def __init__(self, image):
        self.image = image

    def isActive(self):
        return True

    def setRenderHint(self, hint, enabled):
        pass

    def setPen(self, pen):
        pass

    def drawLine(self, start, end):
        pass

    def end(self):
        pass


class _PngPen(object):
    def __init__(self, color):
        self.color = color

    def setWidthF(self, width):
        pass

    def setCapStyle(self, cap):
        pass

    def setJoinStyle(self, join):
        pass


class PngWriteValidationTests(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="cg-png-test-")
        self.addCleanup(shutil.rmtree, self.directory)
        self.controller = _load_controller(_FakeCmds())
        self.controller.QImage = _PngImage
        self.controller.QPainter = _PngPainter
        self.controller.QColor = lambda *values: values
        self.controller.QPen = _PngPen
        self.controller.QPointF = lambda *values: values
        self.controller.core.compose_geometry = lambda options, width, height: {
            "segments": [], "polylines": []}
        self.settings = {
            "width": 8, "height": 6, "pixelAspect": 1.0,
            "thirds": False, "goldenSpiral": False, "spiralOrientation": 0,
            "goldenTriangle": False, "triangleDirection": 0,
            "diagonal": False, "diagonalDown": False, "diagonalUp": False,
            "center": False, "centerCross": False, "centerCircle": False,
            "centerBox": False, "centerDiamond": False,
            "lineColor": (1.0, 1.0, 1.0), "lineAlpha": 1.0, "lineWidth": 1.0,
        }

    def _write(self, **overrides):
        defaults = {
            "save_result": True, "write_file": True, "file_content": b"png",
            "reload_is_null": False, "reload_width": 8, "reload_height": 6,
            "reload_has_alpha": True,
        }
        for name, value in defaults.items():
            setattr(_PngImage, name, value)
        for name, value in overrides.items():
            setattr(_PngImage, name, value)
        path = os.path.join(self.directory, "guide.png")
        return self.controller._write_png(path, self.settings)

    def tearDown(self):
        _PngImage.save_result = True
        _PngImage.write_file = True
        _PngImage.file_content = b"png"
        _PngImage.reload_is_null = False
        _PngImage.reload_width = 8
        _PngImage.reload_height = 6
        _PngImage.reload_has_alpha = True

    def test_write_png_accepts_true_save_with_valid_reloaded_file(self):
        self._write(save_result=True)

    def test_maya_image_path_uses_forward_slashes(self):
        self.assertEqual(
            "C:/project/sourceimages/composition_guides/guide.png",
            self.controller._maya_image_path(
                r"C:\project/sourceimages\composition_guides/guide.png"))

    @unittest.skipUnless(os.name == "nt", "Windows path fallback")
    def test_cache_directory_skips_image_path_at_windows_limit(self):
        long_root = "C:/" + "/".join(["x" * 83] * 3)
        roots_used = []
        original_isdir = self.controller.os.path.isdir
        original_mkstemp = self.controller.tempfile.mkstemp
        original_close = self.controller.os.close
        original_remove = self.controller.os.remove
        self.controller._cache_roots = lambda: [long_root, self.directory]
        self.controller.os.path.isdir = lambda path: True
        self.controller.tempfile.mkstemp = lambda prefix, dir: (
            roots_used.append(dir) or (1, os.path.join(dir, prefix + "probe")))
        self.controller.os.close = lambda descriptor: None
        self.controller.os.remove = lambda path: None
        try:
            self.assertEqual(
                self.directory, self.controller._cache_directory("guide.png"))
            self.assertEqual([self.directory], roots_used)
        finally:
            self.controller.os.path.isdir = original_isdir
            self.controller.tempfile.mkstemp = original_mkstemp
            self.controller.os.close = original_close
            self.controller.os.remove = original_remove

    @unittest.skipUnless(os.name == "nt", "Windows path fallback")
    def test_cache_directory_keeps_project_root_below_windows_limit(self):
        project_root = "C:/project/sourceimages/composition_guides"
        roots_used = []
        original_isdir = self.controller.os.path.isdir
        original_mkstemp = self.controller.tempfile.mkstemp
        original_close = self.controller.os.close
        original_remove = self.controller.os.remove
        self.controller._cache_roots = lambda: [project_root, self.directory]
        self.controller.os.path.isdir = lambda path: True
        self.controller.tempfile.mkstemp = lambda prefix, dir: (
            roots_used.append(dir) or (1, os.path.join(dir, prefix + "probe")))
        self.controller.os.close = lambda descriptor: None
        self.controller.os.remove = lambda path: None
        try:
            self.assertEqual(
                project_root, self.controller._cache_directory("guide.png"))
            self.assertEqual([project_root], roots_used)
        finally:
            self.controller.os.path.isdir = original_isdir
            self.controller.tempfile.mkstemp = original_mkstemp
            self.controller.os.close = original_close
            self.controller.os.remove = original_remove

    def test_write_png_accepts_false_save_with_valid_reloaded_file(self):
        self._write(save_result=False)

    def test_write_png_rejects_stale_valid_file_after_failed_save(self):
        path = os.path.join(self.directory, "guide.png")
        with open(path, "wb") as png_file:
            png_file.write(b"old-valid-png")
        with self.assertRaises(self.controller.GuideError):
            self._write(save_result=False, write_file=False)

    def test_write_png_uses_qt_file_metadata_when_python_path_check_lags(self):
        original_isfile = self.controller.os.path.isfile
        self.controller.os.path.isfile = lambda path: False
        try:
            self._write(save_result=False)
        finally:
            self.controller.os.path.isfile = original_isfile

    def test_write_png_rejects_false_save_with_missing_empty_or_invalid_reload(self):
        invalid_cases = (
            {"write_file": False},
            {"file_content": b""},
            {"reload_is_null": True},
            {"reload_width": 7},
            {"reload_height": 5},
            {"reload_has_alpha": False},
        )
        for invalid in invalid_cases:
            with self.assertRaises(self.controller.GuideError):
                self._write(save_result=False, **invalid)

    def test_write_png_rejects_true_save_with_invalid_file(self):
        with self.assertRaises(self.controller.GuideError):
            self._write(save_result=True, reload_is_null=True)


if __name__ == "__main__":
    unittest.main()
