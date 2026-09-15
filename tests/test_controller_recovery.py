from __future__ import absolute_import

import importlib
import sys
import types
import unittest


class _FakeCmds(object):

    def __init__(self):
        self.calls = []

    def allNodeTypes(self):
        return []

    def ls(self, *unused, **unused_keywords):
        return []

    def setAttr(self, plug, value, **unused_keywords):
        self.calls.append((plug, value))
        if plug == "badPlane.visibility":
            raise RuntimeError("bad plane cannot be hidden")

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

    def test_multiplier_factor_uses_an_internal_mplug_value(self):
        fake_cmds = _FakeCmds()
        controller = _load_controller(fake_cmds)

        controller._set_multiplier_factor("multiplier")

        self.assertEqual(
            [("multiplier.input2", 1.01)],
            controller.om.internal_set_values)
        self.assertFalse(any(call[0] == "multiplier.input2"
                             for call in fake_cmds.calls))

    def test_after_render_continues_after_a_plane_hide_failure(self):
        fake_cmds = _FakeCmds()
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


if __name__ == "__main__":
    unittest.main()
