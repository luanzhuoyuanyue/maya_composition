# -*- coding: utf-8 -*-
"""Explicit disposable-scene checks; does not validate GPU-rendered pixels."""
from __future__ import absolute_import, division

import os
import sys


def _normalized(path):
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _identity_error(detail):
    return RuntimeError(u"测试副本不一致：%s。请重启干净 Maya 会话后运行测试。" % detail)


def _registered_plugin(cmds):
    matches = []
    for name in cmds.pluginInfo(query=True, listPlugins=True) or []:
        path = cmds.pluginInfo(name, query=True, path=True)
        if (os.path.normcase(os.path.basename(path)) == os.path.normcase("composition_guides_plugin.py") or
                "compositionGuidesLocator" in (cmds.pluginInfo(name, query=True, dependNode=True) or [])):
            matches.append((name, path))
    if len(matches) > 1:
        raise _identity_error(u"存在多个构图插件")
    if not matches and "compositionGuidesLocator" in (cmds.allNodeTypes() or []):
        raise _identity_error(u"构图节点类型的插件来源不明")
    return matches[0] if matches else None


def _validate_module(name, module, expected):
    actual = getattr(module, "__file__", None)
    if not actual or _normalized(actual) != _normalized(expected):
        raise _identity_error(u"%s 不在预期文件 %s" % (name, expected))


def _test_modules(cmds):
    names = ("composition_guides", "composition_guides_core", "composition_guides_plugin")
    directory = os.path.dirname(os.path.abspath(__file__))
    local = dict((name, os.path.join(directory, name + ".py")) for name in names)
    scripts = os.path.abspath(cmds.internalVar(userScriptDir=True))
    installed = dict((name, os.path.join(scripts, name + ".py")) for name in names)
    installed["composition_guides_plugin"] = os.path.join(
        os.path.abspath(cmds.internalVar(userAppDir=True)), "plug-ins", "composition_guides_plugin.py")
    loaded = _registered_plugin(cmds)
    if loaded:
        path = _normalized(loaded[1])
        if path == _normalized(installed["composition_guides_plugin"]):
            expected = installed
        elif path == _normalized(local["composition_guides_plugin"]):
            expected = local
        else:
            raise _identity_error(u"已加载其他目录的构图插件 %s" % loaded[1])
    else:
        expected = local if all(os.path.isfile(path) for path in local.values()) else installed
    for name, path in expected.items():
        if not os.path.isfile(path):
            raise _identity_error(u"所选测试副本缺少 %s" % path)
        if name in sys.modules:
            _validate_module(name, sys.modules[name], path)
    directories = [os.path.dirname(expected["composition_guides"])]
    plugin_directory = os.path.dirname(expected["composition_guides_plugin"])
    if plugin_directory not in directories:
        directories.append(plugin_directory)
    for path in reversed(directories):
        while path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)
    if loaded is None:
        cmds.loadPlugin(expected["composition_guides_plugin"], quiet=True)
    verified_plugin = _registered_plugin(cmds)
    if (verified_plugin is None or
            _normalized(verified_plugin[1]) != _normalized(expected["composition_guides_plugin"])):
        raise _identity_error(u"加载后的插件路径与所选测试副本不一致")
    # The plugin loader may import modules; check those before the controller's
    # import-time recovery can modify scene state.
    for name, path in expected.items():
        if name in sys.modules:
            _validate_module(name, sys.modules[name], path)
    modules = {}
    for name in ("composition_guides_core", "composition_guides_plugin", "composition_guides"):
        module = __import__(name)
        _validate_module(name, module, expected[name])
        modules[name] = module
    return modules["composition_guides"], modules["composition_guides_plugin"], expected


def run_smoke_test(allow_new_scene=False):
    if allow_new_scene is not True:
        raise RuntimeError(u"测试会强制新建场景；请保存工作并在可丢弃的 Maya 会话中显式传入 allow_new_scene=True。")
    import maya.cmds as cmds
    guides, plugin, expected_paths = _test_modules(cmds)
    import maya.api.OpenMaya as om
    try:
        from PySide6.QtGui import QImage
    except ImportError:
        from PySide2.QtGui import QImage

    def check(name, condition):
        if not condition:
            raise AssertionError(u"冒烟检查失败：%s" % name)
        results[name] = True

    def dag_path(node):
        selection = om.MSelectionList()
        selection.add(node)
        return selection.getDagPath(0)

    class FrameContext(object):
        def getViewportDimensions(self):
            return (0, 0, 640, 360)

    def draw_state(config, camera):
        # Exercise the real draw preparation; this does not submit pixels to a GPU.
        path = dag_path(config)
        override = plugin.CompositionGuidesDrawOverride(path.node())
        return override.prepareForDraw(path, dag_path(camera), FrameContext(), None).should_draw

    results = {"tested_paths": expected_paths}
    previous_renderer = cmds.getAttr("defaultRenderGlobals.currentRenderer")
    try:
        cmds.file(new=True, force=True)
        cmds.currentUnit(linear="cm")
        perspective = cmds.ls(cmds.camera(name="cgSmokePerspective")[1], long=True)[0]
        orthographic = cmds.ls(cmds.camera(name="cgSmokeOrthographic", orthographic=True)[1], long=True)[0]
        check("camera_types", not cmds.getAttr(perspective + ".orthographic") and
              bool(cmds.getAttr(orthographic + ".orthographic")))
        cmds.setAttr("defaultResolution.width", 640)
        cmds.setAttr("defaultResolution.height", 360)
        cmds.setAttr("defaultResolution.pixelAspect", 1.0)
        configs = []
        for camera in (perspective, orthographic):
            config = guides.create_or_update(camera, {"outputMode": 2, "enabled": True})
            repeated = guides.create_or_update(camera, {"outputMode": 2, "enabled": True})
            check("idempotent_" + camera.rsplit("|", 1)[-1], config == repeated and
                  len([node for node in guides._configs() if guides._config_camera(node) == camera]) == 1)
            configs.append(config)
        check("idempotent_configs", len(guides._configs()) == 2 and len(set(configs)) == 2)
        check("ownership_connections", all(
            cmds.getAttr(config + ".ownerTag") == "OpenAI.CompositionGuides" and
            cmds.getAttr(config + ".dataVersion") == 1 and
            cmds.isConnected(camera + ".message", config + ".cameraMessage")
            for camera, config in zip((perspective, orthographic), configs)))
        plane = guides._dependency(configs[0], "imagePlane")
        multiplier = guides._dependency(configs[0], "multDoubleLinear")
        for near, expected in ((0.1, 0.101), (10.0, 10.1)):
            cmds.setAttr(perspective + ".nearClipPlane", near)
            check("near_clip_" + str(near),
                  abs(cmds.getAttr(multiplier + ".output") - expected) < 1e-6 and
                  abs(cmds.getAttr(plane + ".depth") - expected) < 1e-6)
        check("near_clip_depth", cmds.isConnected(perspective + ".nearClipPlane", multiplier + ".input1") and
              cmds.isConnected(multiplier + ".output", plane + ".depth"))
        png = guides.refresh_render_overlay(perspective, force=True)
        image = QImage(png)
        check("png_rgba_640x360", os.path.isfile(png) and os.path.getsize(png) > 0 and
              not image.isNull() and image.width() == 640 and image.height() == 360 and image.hasAlphaChannel())
        cmds.setAttr("defaultRenderGlobals.currentRenderer", "mayaHardware2", type="string")
        for mode, label, ordinary_draw, rendering_draw, rendering_plane in (
                (0, "viewport", True, True, False),
                (1, "hardware", False, False, True),
                (2, "both", True, False, True)):
            guides.create_or_update(perspective, {"outputMode": mode, "enabled": True})
            check(label + "_ordinary", draw_state(configs[0], perspective) == ordinary_draw and
                  not cmds.getAttr(plane + ".visibility") and not cmds.getAttr(configs[0] + ".renderInProgress"))
            guides._before_render()
            check(label + "_rendering", draw_state(configs[0], perspective) == rendering_draw and
                  bool(cmds.getAttr(plane + ".visibility")) == rendering_plane and
                  bool(cmds.getAttr(configs[0] + ".renderInProgress")) == rendering_plane)
            guides._after_render()
            check(label + "_restored", draw_state(configs[0], perspective) == ordinary_draw and
                  not cmds.getAttr(plane + ".visibility") and not cmds.getAttr(configs[0] + ".renderInProgress"))
        check("output_mode_states", True)
        unmarked = cmds.imagePlane(camera=perspective)[1]
        guides.remove(perspective)
        check("scoped_removal", guides.find_config(perspective) is None and
              guides.find_config(orthographic) == configs[1] and cmds.objExists(unmarked))
        return results
    finally:
        try:
            guides._after_render()
        finally:
            cmds.setAttr("defaultRenderGlobals.currentRenderer", previous_renderer, type="string")
