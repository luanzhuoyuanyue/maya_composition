# -*- coding: utf-8 -*-
"""Explicit disposable-scene checks; does not validate GPU-rendered pixels."""
from __future__ import absolute_import, division

import os
import sys


def run_smoke_test(allow_new_scene=False):
    if allow_new_scene is not True:
        raise RuntimeError(u"测试会强制新建场景；请保存工作并在可丢弃的 Maya 会话中显式传入 allow_new_scene=True。")
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    try:
        from PySide6.QtGui import QImage
    except ImportError:
        from PySide2.QtGui import QImage
    directory = os.path.dirname(os.path.abspath(__file__))
    if directory not in sys.path:
        sys.path.append(directory)
    import composition_guides as guides
    if "compositionGuidesLocator" not in (cmds.allNodeTypes() or []):
        local = os.path.join(directory, "composition_guides_plugin.py")
        installed = os.path.join(cmds.internalVar(userAppDir=True), "plug-ins", "composition_guides_plugin.py")
        cmds.loadPlugin(local if os.path.isfile(local) else installed, quiet=True)
    import composition_guides_plugin as plugin

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

    results = {}
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
