# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MayaBoundary(object):
    """Only Maya's external file/UI/plugin boundary is simulated."""
    def __init__(self, root):
        self.root = root
        self.loaded = False
        self.loads = []
        self.autoload = False
        self.live = []
        self.controls = {"Shelf|Composition|user": {"annotation": "User camera"}}
        self.tabs = {"Shelf|Composition"}

    def internalVar(self, **kwargs):
        key = next(iter(kwargs))
        return os.path.join(self.root, {"userScriptDir": "scripts", "userAppDir": "app",
                                       "userTmpDir": "temp"}[key])

    def workspace(self, **kwargs):
        return os.path.join(self.root, "project")

    def allNodeTypes(self):
        return ["compositionGuidesLocator"] if self.loaded else []

    def ls(self, **kwargs):
        return self.live

    def pluginInfo(self, plugin=None, **kwargs):
        if kwargs.get("listPlugins"):
            return ["composition_guides_plugin"] if self.loaded else []
        if kwargs.get("loaded"):
            return self.loaded
        if kwargs.get("path"):
            return os.path.join(self.root, "app", "plug-ins", "composition_guides_plugin.py")
        if kwargs.get("edit"):
            self.autoload = kwargs["autoload"]

    def loadPlugin(self, path, **kwargs):
        assert kwargs == {"quiet": True}
        self.loads.append(path)
        self.loaded = True
        return ["composition_guides_plugin"]

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


if __name__ == "__main__":
    unittest.main()
