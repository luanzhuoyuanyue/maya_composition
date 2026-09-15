# -*- coding: utf-8 -*-
from __future__ import absolute_import

import io
import os
import shutil
import sys
import tempfile
import types
import unittest
import warnings
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MayaBoundary(object):
    """Only Maya's external file/UI/plugin boundary is simulated."""
    def __init__(self, root):
        self.root = root
        self.loaded = False
        self.plugin_path = os.path.join(root, "app", "plug-ins", "composition_guides_plugin.py")
        self.plugin_name = "composition_guides_plugin"
        self.plugin_edits = []
        self.loads = []
        self.autoload = False
        self.live = []
        self.orphan_type = False
        self.new_scenes = []
        self.scene_writes = []
        self.controls = {"Shelf|Composition|user": {"annotation": "User camera"}}
        self.tabs = {"Shelf|Composition"}

    def internalVar(self, **kwargs):
        key = next(iter(kwargs))
        return os.path.join(self.root, {"userScriptDir": "scripts", "userAppDir": "app",
                                       "userTmpDir": "temp"}[key])

    def workspace(self, **kwargs):
        return os.path.join(self.root, "project")

    def allNodeTypes(self):
        return ["compositionGuidesLocator"] if self.loaded or self.orphan_type else []

    def getAttr(self, plug):
        assert plug == "defaultRenderGlobals.currentRenderer"
        return "previousRenderer"

    def setAttr(self, *args, **kwargs):
        self.scene_writes.append((args, kwargs))

    def file(self, **kwargs):
        self.new_scenes.append(kwargs)
        raise NewSceneBoundaryReached()

    def ls(self, **kwargs):
        return self.live

    def pluginInfo(self, plugin=None, **kwargs):
        if kwargs.get("listPlugins"):
            return [self.plugin_name] if self.loaded else []
        if kwargs.get("loaded"):
            return self.loaded
        if kwargs.get("path"):
            return self.plugin_path
        if kwargs.get("dependNode"):
            return ["compositionGuidesLocator"]
        if kwargs.get("edit"):
            self.plugin_edits.append((plugin, kwargs))
            self.autoload = kwargs["autoload"]

    def loadPlugin(self, path, **kwargs):
        assert kwargs == {"quiet": True}
        self.loads.append(path)
        self.loaded = True
        self.plugin_path = path
        return [self.plugin_name]

    def unloadPlugin(self, name, **kwargs):
        assert not kwargs.get("force")
        self.loaded = False

    def shelfLayout(self, name, **kwargs):
        if kwargs.get("exists"):
            return name in self.tabs
        if kwargs.get("query"):
            return list(self.controls)
        name = kwargs.get("parent", "Shelf") + "|" + name
        self.tabs.add(name)
        return name

    def shelfButton(self, name=None, **kwargs):
        if kwargs.get("exists"):
            return name in self.controls
        if kwargs.pop("query", False):
            if name not in self.controls:
                raise RuntimeError("not a shelf button")
            return self.controls[name]["annotation"]
        if kwargs.pop("edit", False):
            self.controls[name].update(kwargs)
            return None
        name = kwargs["parent"] + "|guide" + str(len(self.controls))
        self.controls[name] = kwargs
        return name

    def resourceManager(self, **kwargs):
        return []

    def deleteUI(self, name, **kwargs):
        del self.controls[name]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "install_composition_guides.py")),
                        "missing installer implementation")
        self.root = tempfile.mkdtemp(prefix="cg-installer-test-")
        self.addCleanup(shutil.rmtree, self.root)
        original_path = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), original_path))
        self.cmds = MayaBoundary(self.root)
        maya = types.ModuleType("maya")
        maya.cmds = self.cmds
        maya.mel = types.SimpleNamespace(eval=lambda expression: "Shelf")
        self.controller = types.ModuleType("composition_guides")
        self.controller.remove_render_hooks = mock.Mock()
        self.controller._remove_callbacks = mock.Mock()
        self.patch = mock.patch.dict(sys.modules, {"maya": maya, "maya.cmds": self.cmds,
                                                  "maya.mel": maya.mel, "composition_guides": self.controller})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.module = types.ModuleType("installer_under_test")
        self.module.__file__ = os.path.join(ROOT, "install_composition_guides.py")
        with open(self.module.__file__, "rb") as handle:
            exec(compile(handle.read(), self.module.__file__, "exec"), self.module.__dict__)

    def test_repeat_install_copies_only_runtime_files_and_reuses_owned_button(self):
        first = self.module.install()
        second = self.module.install()
        self.assertEqual(first, second)
        self.assertEqual(1, len(self.cmds.loads))
        self.assertTrue(self.cmds.autoload)
        self.assertEqual(["composition_guides.py", "composition_guides_core.py"],
                         sorted(os.listdir(os.path.join(self.root, "scripts"))))
        self.assertEqual(["composition_guides_plugin.py"],
                         os.listdir(os.path.join(self.root, "app", "plug-ins")))
        buttons = [v for v in self.cmds.controls.values() if v["annotation"] == "Maya Composition Guides"]
        self.assertEqual(1, len(buttons))
        self.assertEqual("import composition_guides; composition_guides.show()", buttons[0]["command"])
        self.assertEqual("python", buttons[0]["sourceType"])
        self.assertIn("Shelf|Composition|user", self.cmds.controls)

    def test_missing_source_stops_before_any_destination_mutation(self):
        self.module.__file__ = os.path.join(self.root, "missing", "install_composition_guides.py")
        with self.assertRaises(RuntimeError):
            self.module.install()
        self.assertEqual([], os.listdir(self.root))
        self.assertEqual([], self.cmds.loads)
        self.assertEqual(1, len(self.cmds.controls))

    def test_source_plugin_is_rejected_before_copy_load_autoload_or_shelf_mutation(self):
        self.cmds.loaded = True
        self.cmds.plugin_path = os.path.join(ROOT, "composition_guides_plugin.py")
        with self.assertRaises(RuntimeError):
            self.module.install()
        self.assertEqual([], os.listdir(self.root))
        self.assertEqual([], self.cmds.loads)
        self.assertEqual([], self.cmds.plugin_edits)
        self.assertEqual({"Shelf|Composition|user": {"annotation": "User camera"}}, self.cmds.controls)

    def test_renamed_plugin_owning_same_node_type_is_rejected_before_mutation(self):
        self.cmds.loaded = True
        self.cmds.plugin_name = "old_guides"
        self.cmds.plugin_path = os.path.join(self.root, "old_guides.py")
        with self.assertRaises(RuntimeError):
            self.module.install()
        self.assertEqual([], os.listdir(self.root))
        self.assertEqual([], self.cmds.loads)
        self.assertEqual([], self.cmds.plugin_edits)
        self.assertEqual(1, len(self.cmds.controls))

    def test_target_plugin_already_loaded_is_reused_without_second_load(self):
        self.cmds.loaded = True
        first = self.module.install()
        second = self.module.install()
        self.assertEqual(first, second)
        self.assertEqual([], self.cmds.loads)
        self.assertEqual(self.cmds.plugin_path, first["paths"]["composition_guides_plugin.py"])
        self.assertTrue(self.cmds.autoload)
        self.assertEqual(2, len(self.cmds.controls))

    def test_readme_install_command_runs_main_with_its_explicit_file_scope(self):
        with io.open(os.path.join(ROOT, "README_CN.md"), encoding="utf-8") as handle:
            snippet = handle.read().split("```python", 1)[1].split("```", 1)[0]
        snippet = snippet.replace('r"X:/path/install_composition_guides.py"', repr(self.module.__file__))
        scope = {}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            with mock.patch("builtins.print"):
                eval(compile(snippet, "README install example", "exec"), scope)
        self.assertEqual(self.module.__file__, scope["installer_scope"]["__file__"])
        self.assertEqual("__main__", scope["installer_scope"]["__name__"])
        self.assertTrue(os.path.isfile(os.path.join(self.root, "scripts", "composition_guides.py")))
        self.assertEqual(1, len(self.cmds.loads))
        self.assertEqual(2, len(self.cmds.controls))

    def test_live_nodes_block_uninstall_before_hooks_files_or_shelf_are_changed(self):
        self.module.install()
        self.cmds.live = ["liveGuide"]
        with self.assertRaises(RuntimeError):
            self.module.uninstall(remove_cache=True)
        self.assertTrue(self.cmds.loaded)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "scripts", "composition_guides.py")))
        self.assertEqual(2, len(self.cmds.controls))
        self.controller.remove_render_hooks.assert_not_called()

    def test_uninstall_is_repeatable_and_preserves_unrelated_files_controls_and_cache(self):
        self.module.install()
        other = os.path.join(self.root, "scripts", "personal.py")
        with open(other, "w") as handle:
            handle.write("personal")
        cache = os.path.join(self.root, "project", "sourceimages", "composition_guides")
        os.makedirs(cache)
        self.module.uninstall()
        self.module.uninstall()
        self.assertFalse(self.cmds.loaded)
        self.assertEqual(["personal.py"], os.listdir(os.path.join(self.root, "scripts")))
        self.assertEqual(["Shelf|Composition|user"], list(self.cmds.controls))
        self.assertTrue(os.path.isdir(cache))
        self.controller.remove_render_hooks.assert_called()
        self.controller._remove_callbacks.assert_called()

    def test_opt_in_cache_removal_deletes_only_two_dedicated_roots(self):
        for base in (os.path.join(self.root, "project", "sourceimages"), os.path.join(self.root, "temp")):
            os.makedirs(os.path.join(base, "composition_guides", "nested"))
            os.makedirs(os.path.join(base, "personal"))
        self.module.uninstall(remove_cache=True)
        for base in (os.path.join(self.root, "project", "sourceimages"), os.path.join(self.root, "temp")):
            self.assertEqual(["personal"], os.listdir(base))

    def test_redirected_cache_root_stops_before_any_uninstall_mutation(self):
        self.module.install()
        normalized = self.module._normalized
        def redirect(path):
            if path.endswith("composition_guides"):
                return os.path.join(self.root, "personal")
            return normalized(path)
        with mock.patch.object(self.module, "_normalized", side_effect=redirect):
            with self.assertRaises(RuntimeError):
                self.module.uninstall(remove_cache=True)
        self.assertTrue(self.cmds.loaded)
        self.assertEqual(2, len(self.cmds.controls))
        self.controller.remove_render_hooks.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows reparse-point boundary")
    def test_windows_junction_flag_blocks_cleanup_even_without_realpath_resolution(self):
        self.module.install()
        cache = os.path.join(self.root, "temp", "composition_guides")
        os.makedirs(cache)
        # Python 2 on Windows may not resolve junctions via realpath/islink.
        attributes = lambda path: 0x410 if path.endswith("composition_guides") else 0x10
        ctypes = types.ModuleType("ctypes")
        ctypes.windll = types.SimpleNamespace(
            kernel32=types.SimpleNamespace(GetFileAttributesW=attributes))
        with mock.patch.dict(sys.modules, {"ctypes": ctypes}):
            with self.assertRaises(RuntimeError):
                self.module.uninstall(remove_cache=True)
        self.assertTrue(os.path.isdir(cache))
        self.assertTrue(self.cmds.loaded)

    def test_smoke_default_rejects_before_importing_maya_or_mutating_scene(self):
        path = os.path.join(ROOT, "maya_smoke_test.py")
        self.assertTrue(os.path.isfile(path), "missing smoke implementation")
        module = types.ModuleType("smoke_under_test")
        module.__file__ = path
        with open(path, "rb") as handle:
            exec(compile(handle.read(), path, "exec"), module.__dict__)
        for value in (False, None, 1, "yes"):
            with self.assertRaises(RuntimeError):
                module.run_smoke_test(allow_new_scene=value)


class NewSceneBoundaryReached(Exception):
    """Stop valid preflight exactly at the external new-scene boundary."""


class SmokeIdentityTests(unittest.TestCase):
    setUp = InstallerTests.setUp

    def _smoke(self, installed=False):
        self.controller._after_render = mock.Mock()
        paths = self.module._paths() if installed else dict(
            (name, os.path.join(ROOT, name)) for name in
            ("composition_guides.py", "composition_guides_core.py", "composition_guides_plugin.py"))
        if installed:
            for name, path in paths.items():
                if not os.path.isdir(os.path.dirname(path)):
                    os.makedirs(os.path.dirname(path))
                shutil.copy2(os.path.join(ROOT, name), path)
        self.controller.__file__ = paths["composition_guides.py"]
        self.core = types.ModuleType("composition_guides_core")
        self.core.__file__ = paths["composition_guides_core.py"]
        self.plugin = types.ModuleType("composition_guides_plugin")
        self.plugin.__file__ = paths["composition_guides_plugin.py"]
        api = types.ModuleType("maya.api")
        api.OpenMaya = types.ModuleType("maya.api.OpenMaya")
        qt = types.ModuleType("PySide6")
        qt.QtGui = types.ModuleType("PySide6.QtGui")
        qt.QtGui.QImage = object
        modules = {"maya.api": api, "maya.api.OpenMaya": api.OpenMaya,
                   "PySide6": qt, "PySide6.QtGui": qt.QtGui,
                   "composition_guides_core": self.core,
                   "composition_guides_plugin": self.plugin}
        patch = mock.patch.dict(sys.modules, modules)
        patch.start()
        self.addCleanup(patch.stop)
        self.smoke = types.ModuleType("smoke_under_test")
        self.smoke.__file__ = os.path.join(ROOT, "maya_smoke_test.py")
        with open(self.smoke.__file__, "rb") as handle:
            eval(compile(handle.read(), self.smoke.__file__, "exec"), self.smoke.__dict__)
        self.cmds.plugin_path = paths["composition_guides_plugin.py"]
        return paths

    def _assert_rejected_before_scene_mutation(self):
        error = None
        try:
            self.smoke.run_smoke_test(allow_new_scene=True)
        except Exception as caught:
            error = caught
        self.assertIsInstance(error, RuntimeError)
        self.assertIn(u"干净", str(error))
        self.assertEqual([], self.cmds.new_scenes)
        self.assertEqual([], self.cmds.scene_writes)
        self.controller._after_render.assert_not_called()

    def test_old_controller_module_is_rejected_before_loading_or_new_scene(self):
        self._smoke()
        self.controller.__file__ = os.path.join(self.root, "old", "composition_guides.py")
        self._assert_rejected_before_scene_mutation()
        self.assertEqual([], self.cmds.loads)

    def test_old_plugin_module_is_rejected_before_new_scene(self):
        self._smoke()
        self.cmds.loaded = True
        self.plugin.__file__ = os.path.join(self.root, "old", "composition_guides_plugin.py")
        self._assert_rejected_before_scene_mutation()

    def test_unknown_loaded_plugin_path_is_rejected_before_new_scene(self):
        self._smoke()
        self.cmds.loaded = True
        self.cmds.plugin_path = os.path.join(self.root, "old", "composition_guides_plugin.py")
        self._assert_rejected_before_scene_mutation()

    def test_unknown_registered_node_type_is_rejected_before_plugin_load_or_new_scene(self):
        self._smoke()
        self.cmds.orphan_type = True
        self._assert_rejected_before_scene_mutation()
        self.assertEqual([], self.cmds.loads)

    def test_loaded_local_copy_reaches_new_scene_with_local_import_priority(self):
        self._smoke()
        self.cmds.loaded = True
        with self.assertRaises(NewSceneBoundaryReached):
            self.smoke.run_smoke_test(allow_new_scene=True)
        self.assertEqual([{"new": True, "force": True}], self.cmds.new_scenes)
        self.assertEqual(ROOT, sys.path[0])
        self.assertEqual([], self.cmds.loads)

    def test_loaded_installed_copy_reaches_new_scene_with_installed_import_priority(self):
        paths = self._smoke(installed=True)
        self.cmds.loaded = True
        with self.assertRaises(NewSceneBoundaryReached):
            self.smoke.run_smoke_test(allow_new_scene=True)
        self.assertEqual([{"new": True, "force": True}], self.cmds.new_scenes)
        self.assertEqual(os.path.dirname(paths["composition_guides.py"]), sys.path[0])
        self.assertEqual([], self.cmds.loads)

    def test_unloaded_complete_local_copy_loads_exact_plugin_before_new_scene(self):
        paths = self._smoke()
        with self.assertRaises(NewSceneBoundaryReached):
            self.smoke.run_smoke_test(allow_new_scene=True)
        self.assertEqual([paths["composition_guides_plugin.py"]], self.cmds.loads)
        self.assertEqual([{"new": True, "force": True}], self.cmds.new_scenes)

    def test_missing_local_package_falls_back_to_complete_installed_copy(self):
        paths = self._smoke(installed=True)
        self.smoke.__file__ = os.path.join(self.root, "smoke-only", "maya_smoke_test.py")
        with self.assertRaises(NewSceneBoundaryReached):
            self.smoke.run_smoke_test(allow_new_scene=True)
        self.assertEqual([paths["composition_guides_plugin.py"]], self.cmds.loads)
        self.assertEqual(os.path.dirname(paths["composition_guides.py"]), sys.path[0])

    def test_imported_controller_is_rechecked_before_new_scene(self):
        self._smoke()
        self.cmds.loaded = True
        self.controller.__file__ = os.path.join(self.root, "old", "composition_guides.py")
        del sys.modules["composition_guides"]
        original_import = __import__
        def redirected_import(name, *args, **kwargs):
            if name == "composition_guides":
                return self.controller
            return original_import(name, *args, **kwargs)
        with mock.patch("builtins.__import__", side_effect=redirected_import):
            self._assert_rejected_before_scene_mutation()


if __name__ == "__main__":
    unittest.main()
