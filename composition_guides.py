# -*- coding: utf-8 -*-
from __future__ import absolute_import, division

import atexit
import os
import tempfile

import maya.cmds as cmds
import maya.api.OpenMaya as om

try:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen
except ImportError:
    from PySide2.QtCore import QPointF, Qt
    from PySide2.QtGui import QColor, QImage, QPainter, QPen

import composition_guides_core as core

try:
    _ARGB32 = QImage.Format_ARGB32
except AttributeError:
    _ARGB32 = QImage.Format.Format_ARGB32
try:
    _ANTIALIASING = QPainter.Antialiasing
except AttributeError:
    _ANTIALIASING = QPainter.RenderHint.Antialiasing
try:
    _ROUND_CAP, _ROUND_JOIN = Qt.RoundCap, Qt.RoundJoin
except AttributeError:
    _ROUND_CAP, _ROUND_JOIN = Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin

OWNER_TAG = "OpenAI.CompositionGuides"
DATA_VERSION = 1
NODE_TYPE = "compositionGuidesLocator"
RENDERER = "mayaHardware2"
SETTING_NAMES = (
    "enabled", "outputMode", "thirds", "goldenSpiral", "spiralOrientation",
    "goldenTriangle", "triangleDirection", "diagonal", "diagonalDown",
    "diagonalUp", "center", "centerCross", "centerCircle", "centerBox",
    "centerDiamond", "lineColor", "lineAlpha", "lineWidth",
)
_HOOK_BEGIN = "\n// CGUIDES_BEGIN\n"
_HOOK_END = "// CGUIDES_END\n"
_HOOKS = (
    ("defaultRenderGlobals.preRenderMel", "_before_render"),
    ("defaultRenderGlobals.postRenderMel", "_after_render"),
)
# A reload must release the callbacks belonging to the previous module body.
if "_callback_ids" in globals():
    for _old_callback in _callback_ids:
        try:
            om.MMessage.removeCallback(_old_callback)
        except RuntimeError:
            pass
_callback_ids = []


class GuideError(RuntimeError):
    pass


def _setting_attribute(name):
    return "centerEnabled" if name == "center" else name


def _long(node):
    matches = cmds.ls(node, long=True) or []
    if len(matches) != 1:
        raise GuideError(u"对象不存在或名称不唯一。")
    return matches[0]


def _camera_shape(node):
    node = _long(node)
    kind = cmds.nodeType(node)
    if kind == "camera":
        return node
    if kind == "transform":
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True,
                                   type="camera") or []
        if len(shapes) == 1:
            return shapes[0]
        raise GuideError(u"所选变换必须只有一个相机形状。")
    raise GuideError(u"请选择相机或相机变换。")


def resolve_selected_camera():
    selected = cmds.ls(selection=True, long=True) or []
    if not selected:
        raise GuideError(u"请先选择一台相机。")
    if len(selected) != 1:
        raise GuideError(u"请只选择一台相机。")
    return _camera_shape(selected[0])


def _config_camera(config):
    try:
        if (cmds.nodeType(config) != NODE_TYPE or
                cmds.getAttr(config + ".ownerTag") != OWNER_TAG or
                cmds.getAttr(config + ".dataVersion") != DATA_VERSION):
            return None
        sources = cmds.listConnections(config + ".cameraMessage", source=True,
                                       destination=False, plugs=True) or []
        if len(sources) != 1:
            return None
        camera, attribute = sources[0].rsplit(".", 1)
        if attribute != "message" or cmds.nodeType(camera) != "camera":
            return None
        camera = _long(camera)
        if cmds.isConnected(camera + ".message", config + ".cameraMessage"):
            return camera
    except (RuntimeError, ValueError):
        pass
    return None


def find_config(camera_shape):
    camera_shape = _camera_shape(camera_shape)
    candidates = cmds.listConnections(camera_shape + ".message", source=False,
                                     destination=True, type=NODE_TYPE) or []
    valid = sorted(set(_long(node) for node in candidates
                       if _config_camera(node) == camera_shape))
    if len(valid) > 1:
        raise GuideError(u"该相机存在多个有效构图配置，请先处理重复配置。")
    return valid[0] if valid else None


def _configs():
    if NODE_TYPE not in (cmds.allNodeTypes() or []):
        return []
    return [node for node in (cmds.ls(type=NODE_TYPE, long=True) or [])
            if _config_camera(node) is not None]


def _owned(node, config, kind):
    try:
        return bool(
            _config_camera(config) and cmds.nodeType(node) == kind and
            cmds.getAttr(node + ".cgOwnerTag") == OWNER_TAG and
            cmds.isConnected(config + ".message", node + ".cgConfigMessage"))
    except (RuntimeError, ValueError):
        return False


def _dependency(config, kind):
    nodes = cmds.listConnections(config + ".message", source=False,
                                destination=True, type=kind) or []
    valid = sorted(set(_long(node) for node in nodes if _owned(node, config, kind)))
    if len(valid) > 1:
        raise GuideError(u"构图配置存在重复的渲染依赖，请先处理重复节点。")
    return valid[0] if valid else None


def _mark(node, config):
    cmds.addAttr(node, longName="cgOwnerTag", dataType="string")
    cmds.setAttr(node + ".cgOwnerTag", OWNER_TAG, type="string")
    cmds.addAttr(node, longName="cgConfigMessage", attributeType="message")
    cmds.connectAttr(config + ".message", node + ".cgConfigMessage")


def _connect(source, destination):
    if cmds.isConnected(source, destination):
        return
    if cmds.listConnections(destination, source=True, destination=False, plugs=True):
        raise GuideError(u"渲染依赖已连接到其他节点，无法安全覆盖。")
    cmds.connectAttr(source, destination)


def _set_multiplier_factor(multiplier):
    selection = om.MSelectionList()
    selection.add(multiplier + ".input2")
    selection.getPlug(0).setDouble(1.01)


def _ensure_plane(config):
    camera = _config_camera(config)
    if camera is None:
        raise GuideError(u"构图配置无效。")
    plane = _dependency(config, "imagePlane")
    if plane is None:
        transform, plane = cmds.imagePlane(camera=camera)
        plane = _long(plane)
        _mark(plane, config)
    cmds.setAttr(plane + ".visibility", False)
    cmds.setAttr(plane + ".displayMode", 4)
    cmds.setAttr(plane + ".fit", 4)
    if cmds.attributeQuery("fitToResolutionGate", node=plane, exists=True):
        cmds.setAttr(plane + ".fitToResolutionGate", True)
    cmds.setAttr(plane + ".displayOnlyIfCurrent", True)
    multiplier = _dependency(config, "multDoubleLinear")
    if multiplier is None:
        multiplier = cmds.createNode("multDoubleLinear", name="compositionGuidesDepth#")
        _mark(multiplier, config)
    _connect(camera + ".nearClipPlane", multiplier + ".input1")
    _set_multiplier_factor(multiplier)
    _connect(multiplier + ".output", plane + ".depth")
    return plane


def create_or_update(camera_shape, settings):
    camera_shape = _camera_shape(camera_shape)
    unknown = set(settings) - set(SETTING_NAMES)
    if unknown:
        raise GuideError(u"未知构图设置：%s" % ", ".join(sorted(unknown)))
    if NODE_TYPE not in (cmds.allNodeTypes() or []):
        plugin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "composition_guides_plugin.py")
        try:
            cmds.loadPlugin(plugin_path, quiet=True)
        except RuntimeError as error:
            raise GuideError(u"无法加载插件 %s：%s" % (plugin_path, error))
    cmds.undoInfo(openChunk=True, chunkName="Composition Guides")
    try:
        config = find_config(camera_shape)
        if config is None:
            config = _long(cmds.createNode(NODE_TYPE, name="compositionGuidesShape#"))
            cmds.connectAttr(camera_shape + ".message", config + ".cameraMessage")
            parent = cmds.listRelatives(config, parent=True, fullPath=True)[0]
            if cmds.attributeQuery("hiddenInOutliner", node=parent, exists=True):
                cmds.setAttr(parent + ".hiddenInOutliner", True)
        for key, value in settings.items():
            if key == "lineColor":
                cmds.setAttr(config + ".lineColor", *value, type="double3")
            else:
                cmds.setAttr(config + "." + _setting_attribute(key), value)
        if cmds.getAttr(config + ".outputMode") in (1, 2):
            refresh_render_overlay(camera_shape)
            install_render_hooks()
        _ordinary_state(config)
    finally:
        cmds.undoInfo(closeChunk=True)
    return config


def _ordinary_state(config):
    if not _config_camera(config):
        return
    try:
        plane = _dependency(config, "imagePlane")
        if plane:
            cmds.setAttr(plane + ".visibility", False)
    finally:
        cmds.setAttr(config + ".renderInProgress", False)


def _warn_config_failures(action, failures):
    for config, error in failures:
        cmds.warning(u"构图%s失败（%s）：%s" % (action, config, error))


def set_visible(camera_shape, visible):
    config = find_config(camera_shape)
    if config is None:
        raise GuideError(u"该相机尚未创建构图辅助线。")
    cmds.setAttr(config + ".enabled", bool(visible))
    _ordinary_state(config)


def _cache_roots():
    roots = []
    try:
        workspace = cmds.workspace(query=True, rootDirectory=True)
        if workspace and os.path.isdir(workspace):
            roots.append(os.path.join(workspace, "sourceimages", "composition_guides"))
    except RuntimeError:
        pass
    roots.append(os.path.join(cmds.internalVar(userTmpDir=True), "composition_guides"))
    return roots


def _cache_directory():
    for root in _cache_roots():
        try:
            if not os.path.isdir(root):
                os.makedirs(root)
            descriptor, probe = tempfile.mkstemp(prefix=".write-check-", dir=root)
            os.close(descriptor)
            os.remove(probe)
            return root
        except OSError:
            continue
    raise GuideError(u"无法写入构图 PNG 缓存目录。")


def _uuid(node):
    return cmds.ls(node, uuid=True)[0]


def _cache_filename(config, camera):
    scene = os.path.splitext(os.path.basename(cmds.file(query=True, sceneName=True)))[0]
    return "%s_%s_%s.png" % (
        core.safe_identifier(scene or "untitled"),
        core.safe_identifier(camera.rsplit("|", 1)[-1]),
        core.safe_identifier(_uuid(config)[:12]))


def _remove_cache_file(config):
    if not _config_camera(config):
        return
    path = cmds.getAttr(config + ".renderImagePath") or ""
    if not path:
        return
    resolved = os.path.normcase(os.path.realpath(path))
    allowed = [os.path.normcase(os.path.realpath(root)) for root in _cache_roots()]
    suffix = "_" + core.safe_identifier(_uuid(config)[:12]) + ".png"
    if (os.path.dirname(resolved) in allowed and
            os.path.basename(path).endswith(suffix) and os.path.isfile(resolved)):
        os.remove(resolved)


def clean_cache(camera_shape=None):
    configs = _configs() if camera_shape is None else [find_config(camera_shape)]
    for config in configs:
        if config is None:
            continue
        _remove_cache_file(config)
        plane = _dependency(config, "imagePlane")
        if plane:
            cmds.setAttr(plane + ".visibility", False)
            cmds.setAttr(plane + ".imageName", "", type="string")
        cmds.setAttr(config + ".renderImagePath", "", type="string")
        cmds.setAttr(config + ".renderSignature", "", type="string")


def _deletion_parent(shape):
    parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
    if len(parents) != 1:
        raise GuideError(u"构图节点层级已改变，无法安全删除。")
    children = cmds.listRelatives(parents[0], children=True, fullPath=True) or []
    if children != [_long(shape)]:
        raise GuideError(u"构图变换下存在其他对象，无法安全删除。")
    return parents[0]


def remove(camera_shape):
    config = find_config(camera_shape)
    if config is None:
        return
    plane = _dependency(config, "imagePlane")
    multiplier = _dependency(config, "multDoubleLinear")
    config_parent = _deletion_parent(config)
    plane_parent = _deletion_parent(plane) if plane else None
    _remove_cache_file(config)
    if plane and _owned(plane, config, "imagePlane"):
        cmds.delete(plane_parent)
    if multiplier and _owned(multiplier, config, "multDoubleLinear"):
        cmds.delete(multiplier)
    if _config_camera(config) == _camera_shape(camera_shape):
        cmds.delete(config_parent)


def _render_settings(config, camera):
    settings = dict((name, cmds.getAttr(config + "." + _setting_attribute(name)))
                    for name in SETTING_NAMES)
    settings["lineColor"] = list(settings["lineColor"][0])
    settings.update({
        "width": cmds.getAttr("defaultResolution.width"),
        "height": cmds.getAttr("defaultResolution.height"),
        "pixelAspect": cmds.getAttr("defaultResolution.pixelAspect"),
        "dataVersion": DATA_VERSION, "cameraUUID": _uuid(camera),
    })
    return settings


def _geometry_options(settings):
    return {
        "thirds": settings["thirds"],
        "golden_spiral": settings["goldenSpiral"],
        "spiral_orientation": ("top_left", "top_right", "bottom_left", "bottom_right")[settings["spiralOrientation"]],
        "golden_triangle": settings["goldenTriangle"],
        "triangle_direction": ("down", "up")[settings["triangleDirection"]],
        "downward": settings["diagonal"] and settings["diagonalDown"],
        "upward": settings["diagonal"] and settings["diagonalUp"],
        "center": ({"cross": settings["centerCross"], "circle": settings["centerCircle"],
                    "center_box": settings["centerBox"], "diamond": settings["centerDiamond"]}
                   if settings["center"] else False),
    }


def _write_png(path, settings):
    width, height = int(settings["width"]), int(settings["height"])
    if width <= 0 or height <= 0 or settings["pixelAspect"] <= 0:
        raise GuideError(u"渲染分辨率和像素比例必须大于零。")
    geometry = core.compose_geometry(_geometry_options(settings), width, height)
    image = QImage(width, height, _ARGB32)
    image.fill(0)
    rgba = list(settings["lineColor"]) + [settings["lineAlpha"]]
    color = QColor(*[int(round(max(0.0, min(1.0, value)) * 255)) for value in rgba])
    pen = QPen(color)
    pen.setWidthF(float(settings["lineWidth"]))
    pen.setCapStyle(_ROUND_CAP)
    pen.setJoinStyle(_ROUND_JOIN)
    painter = QPainter(image)
    try:
        if not painter.isActive():
            raise GuideError(u"无法创建构图图像。")
        painter.setRenderHint(_ANTIALIASING, True)
        painter.setPen(pen)
        segments = list(geometry["segments"])
        for polyline in geometry["polylines"]:
            segments.extend(zip(polyline[:-1], polyline[1:]))
        for start, end in segments:
            painter.drawLine(QPointF(start[0] * (width - 1), (1.0 - start[1]) * (height - 1)),
                             QPointF(end[0] * (width - 1), (1.0 - end[1]) * (height - 1)))
    finally:
        painter.end()
    if not image.save(path, "PNG") or not os.path.isfile(path) or os.path.getsize(path) <= 0:
        raise GuideError(u"构图 PNG 保存失败：%s" % path)


def refresh_render_overlay(camera_shape, force=False):
    camera_shape = _camera_shape(camera_shape)
    config = find_config(camera_shape)
    if config is None:
        raise GuideError(u"该相机尚未创建构图辅助线。")
    settings = _render_settings(config, camera_shape)
    signature = core.render_signature(settings)
    path = os.path.join(_cache_directory(), _cache_filename(config, camera_shape))
    if (force or signature != cmds.getAttr(config + ".renderSignature") or
            path != cmds.getAttr(config + ".renderImagePath") or
            not os.path.isfile(path) or os.path.getsize(path) <= 0):
        _write_png(path, settings)
    plane = _ensure_plane(config)
    cmds.setAttr(plane + ".imageName", path, type="string")
    cmds.setAttr(config + ".renderImagePath", path, type="string")
    cmds.setAttr(config + ".renderSignature", signature, type="string")
    return path


def _strip_hook(text):
    while _HOOK_BEGIN in text:
        start = text.index(_HOOK_BEGIN)
        end = text.find(_HOOK_END, start + len(_HOOK_BEGIN))
        if end < 0:
            raise GuideError(u"渲染钩子标记不完整，请检查渲染设置中的脚本。")
        text = text[:start] + text[end + len(_HOOK_END):]
    return text


def install_render_hooks():
    for plug, function in _HOOKS:
        user_text = _strip_hook(cmds.getAttr(plug) or "")
        block = (_HOOK_BEGIN + 'catchQuiet(`python("import composition_guides; '
                 'composition_guides.%s()")`);\n' % function + _HOOK_END)
        cmds.setAttr(plug, user_text + block, type="string")
    _install_callbacks()


def remove_render_hooks():
    for plug, function in _HOOKS:
        cmds.setAttr(plug, _strip_hook(cmds.getAttr(plug) or ""), type="string")
    _remove_callbacks()
    _after_render()


def _before_render():
    if cmds.getAttr("defaultRenderGlobals.currentRenderer") != RENDERER:
        return
    failures = []
    for config in _configs():
        try:
            _ordinary_state(config)
            if (cmds.getAttr(config + ".enabled") and
                    cmds.getAttr(config + ".outputMode") in (1, 2)):
                refresh_render_overlay(_config_camera(config))
                plane = _dependency(config, "imagePlane")
                cmds.setAttr(config + ".renderInProgress", True)
                cmds.setAttr(plane + ".visibility", True)
        except Exception as error:
            failures.append((config, error))
            try:
                _ordinary_state(config)
            except Exception as recovery_error:
                failures.append((config, recovery_error))
    _warn_config_failures(u"渲染准备", failures)


def _after_render():
    failures = []
    for config in _configs():
        try:
            _ordinary_state(config)
        except Exception as error:
            failures.append((config, error))
    _warn_config_failures(u"渲染状态恢复", failures)


def _before_save(*unused):
    for config in _configs():
        if cmds.getAttr(config + ".outputMode") in (1, 2):
            try:
                refresh_render_overlay(_config_camera(config))
            except (GuideError, RuntimeError, OSError) as error:
                cmds.warning(u"构图缓存刷新失败：%s" % error)


def _recover_scene(*unused):
    try:
        _after_render()
    except (GuideError, RuntimeError) as error:
        cmds.warning(u"构图状态恢复失败：%s" % error)


def _install_callbacks():
    if not _callback_ids:
        _callback_ids.append(om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeSave, _before_save))
        _callback_ids.append(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, _recover_scene))


def _remove_callbacks():
    while _callback_ids:
        try:
            om.MMessage.removeCallback(_callback_ids.pop())
        except RuntimeError:
            pass


class CompositionGuidesWindow(object):
    WINDOW_NAME = "compositionGuidesWindow"
    FAMILIES = ("thirds", "spiral", "triangle", "diagonal", "center")
    CHECKS = (
        ("thirds", "thirds", u"三分法", True),
        ("spiral", "goldenSpiral", u"黄金螺旋", False),
        ("triangle", "goldenTriangle", u"黄金三角", False),
        ("diagonal", "diagonal", u"对角线", False),
        ("diagonal_down", "diagonalDown", u"左上至右下", True),
        ("diagonal_up", "diagonalUp", u"右上至左下", True),
        ("center", "center", u"中心构图", False),
        ("center_cross", "centerCross", u"中心十字", True),
        ("center_circle", "centerCircle", u"中心圆", True),
        ("center_box", "centerBox", u"中心 25% 框", False),
        ("center_diamond", "centerDiamond", u"中心菱形", False),
    )
    MENUS = (
        ("output_mode", "outputMode", u"输出模式",
         (u"仅视口", u"仅硬件渲染", u"视口 + 硬件渲染"), 2),
        ("spiral_orientation", "spiralOrientation", u"螺旋方向",
         (u"左上", u"右上", u"左下", u"右下"), 0),
        ("triangle_direction", "triangleDirection", u"三角方向",
         (u"左上至右下", u"右上至左下"), 0),
    )

    def __init__(self):
        self.controls = {}
        self.camera = None
        self.enabled = True
        self._loading = False
        self._attributes = dict((row[0], row[1]) for row in self.CHECKS + self.MENUS)
        self._attributes.update({"color": "lineColor", "alpha": "lineAlpha",
                                 "line_width": "lineWidth"})
        self._build()

    def _callback(self, action, *arguments):
        def invoke(*unused):
            try:
                return action(*arguments)
            except GuideError as error:
                message = u"错误：%s" % error
                self._status(message)
                cmds.warning(message)
            except Exception as error:
                self._status(u"错误：%s" % error)
                raise
        return invoke

    def _frame(self, label):
        cmds.frameLayout(label=label, collapsable=False, marginWidth=8, marginHeight=4)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=3)

    def _end_frame(self):
        cmds.setParent("..")
        cmds.setParent("..")

    def _menu(self, row):
        key, attribute, label, choices, default = row
        self.controls[key] = cmds.optionMenuGrp(
            label=label, changeCommand=self._callback(self._changed, key))
        for choice in choices:
            cmds.menuItem(label=choice)
        cmds.optionMenuGrp(self.controls[key], edit=True, select=default + 1)

    def _build(self):
        if cmds.window(self.WINDOW_NAME, exists=True):
            cmds.deleteUI(self.WINDOW_NAME, window=True)
        self.window = cmds.window(self.WINDOW_NAME, title=u"构图辅助线",
                                  widthHeight=(440, 760), sizeable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        self._frame(u"相机")
        self.controls["camera"] = cmds.textFieldGrp(label=u"当前相机", text="", editable=False)
        cmds.button(label=u"从选择获取", command=self._callback(self._from_selection))
        self._end_frame()
        self._frame(u"输出")
        self._menu(self.MENUS[0])
        self._end_frame()
        self._frame(u"构图定义")
        self.controls["all"] = cmds.checkBoxGrp(
            numberOfCheckBoxes=1, label=u"全部", value1=False,
            changeCommand=self._callback(self._all_changed))
        for key, attribute, label, default in self.CHECKS:
            self.controls[key] = cmds.checkBoxGrp(
                numberOfCheckBoxes=1, label=label, value1=default,
                changeCommand=self._callback(self._changed, key))
            if key == "spiral":
                self._menu(self.MENUS[1])
            elif key == "triangle":
                self._menu(self.MENUS[2])
        self._end_frame()
        self._frame(u"样式")
        self.controls["color"] = cmds.colorSliderGrp(
            label=u"颜色", rgbValue=(1.0, 1.0, 0.0),
            changeCommand=self._callback(self._changed, "color"),
            dragCommand=self._callback(self._changed, "color"))
        for key, label, low, high, default in (
                ("alpha", u"不透明度", 0.0, 1.0, 0.8),
                ("line_width", u"线宽 (px)", 1.0, 10.0, 2.0)):
            self.controls[key] = cmds.floatSliderGrp(
                label=label, field=True, minValue=low, maxValue=high,
                fieldMinValue=low, fieldMaxValue=high, value=default,
                changeCommand=self._callback(self._changed, key),
                dragCommand=self._callback(self._changed, key))
        self._end_frame()
        self._frame(u"操作")
        for key, label, action in (
                ("create", u"创建 / 更新", self._create),
                ("visible", u"显示 / 隐藏", self._toggle_visible),
                ("delete", u"删除", self._delete),
                ("clean_cache", u"清理缓存", self._clean_cache)):
            self.controls[key] = cmds.button(label=label, command=self._callback(action))
        self.controls["status"] = cmds.text(label=u"请选择相机，然后创建辅助线。", align="left")
        self._end_frame()

    def _value(self, key):
        control = self.controls[key]
        if key in (row[0] for row in self.CHECKS):
            return bool(cmds.checkBoxGrp(control, query=True, value1=True))
        if key in (row[0] for row in self.MENUS):
            return cmds.optionMenuGrp(control, query=True, select=True) - 1
        if key == "color":
            return tuple(max(0.0, min(1.0, value)) for value in
                         cmds.colorSliderGrp(control, query=True, rgbValue=True))
        value = cmds.floatSliderGrp(control, query=True, value=True)
        low, high = (0.0, 1.0) if key == "alpha" else (1.0, 10.0)
        return max(low, min(high, value))

    def _settings(self):
        settings = dict((attribute, self._value(key))
                        for key, attribute in self._attributes.items())
        settings["enabled"] = self.enabled
        return settings

    def _sync_all(self):
        cmds.checkBoxGrp(self.controls["all"], edit=True,
                         value1=all(self._value(key) for key in self.FAMILIES))

    def _all_changed(self):
        if self._loading:
            return
        value = cmds.checkBoxGrp(self.controls["all"], query=True, value1=True)
        self._loading = True
        try:
            for key in self.FAMILIES:
                cmds.checkBoxGrp(self.controls[key], edit=True, value1=value)
        finally:
            self._loading = False
        self._changed(*self.FAMILIES)

    def _changed(self, *keys):
        if self._loading:
            return
        self._sync_all()
        if self.camera is None:
            return
        config = find_config(self.camera)
        if config is None:
            return
        for key in keys:
            plug = config + "." + _setting_attribute(self._attributes[key])
            value = self._value(key)
            if key == "color":
                cmds.setAttr(plug, *value, type="double3")
            else:
                cmds.setAttr(plug, value)
        cmds.refresh(force=True)
        self._status(u"视口已更新；硬件渲染图将在创建 / 更新或渲染时刷新。")

    def _bind(self, camera):
        camera = _camera_shape(camera)
        config = find_config(camera)
        self._loading = True
        try:
            for key, attribute, label, default in self.CHECKS:
                value = cmds.getAttr(config + "." + _setting_attribute(attribute)) if config else default
                cmds.checkBoxGrp(self.controls[key], edit=True, value1=value)
            for key, attribute, label, choices, default in self.MENUS:
                value = cmds.getAttr(config + "." + attribute) if config else default
                cmds.optionMenuGrp(self.controls[key], edit=True, select=value + 1)
            color = cmds.getAttr(config + ".lineColor")[0] if config else (1.0, 1.0, 0.0)
            cmds.colorSliderGrp(self.controls["color"], edit=True, rgbValue=color)
            for key, attribute, default in (("alpha", "lineAlpha", 0.8),
                                             ("line_width", "lineWidth", 2.0)):
                value = cmds.getAttr(config + "." + attribute) if config else default
                cmds.floatSliderGrp(self.controls[key], edit=True, value=value)
            self.enabled = bool(cmds.getAttr(config + ".enabled")) if config else True
            self.camera = camera
            cmds.textFieldGrp(self.controls["camera"], edit=True, text=camera)
            self._sync_all()
            self._visibility_label(config is not None)
        finally:
            self._loading = False

    def _status(self, message):
        cmds.text(self.controls["status"], edit=True, label=message)

    def _visibility_label(self, has_config):
        label = u"显示 / 隐藏"
        if has_config:
            label += u"（当前显示）" if self.enabled else u"（当前隐藏）"
        cmds.button(self.controls["visible"], edit=True, label=label)

    def _from_selection(self):
        self._bind(resolve_selected_camera())
        self._status(u"已绑定：%s" % self.camera)

    def _create(self):
        camera = None
        if self.camera is not None:
            try:
                camera = _camera_shape(self.camera)
            except GuideError:
                pass
        if camera is None:
            camera = resolve_selected_camera()
        settings = self._settings()
        create_or_update(camera, settings)
        if settings["outputMode"] in (1, 2):
            refresh_render_overlay(camera, force=True)
        self._bind(camera)
        cmds.refresh(force=True)
        self._status(u"已创建 / 更新构图辅助线。")

    def _require_config(self):
        if self.camera is None:
            raise GuideError(u"请先从选择获取一台相机。")
        config = find_config(self.camera)
        if config is None:
            raise GuideError(u"该相机尚未创建构图辅助线。")
        return config

    def _toggle_visible(self):
        config = self._require_config()
        visible = not cmds.getAttr(config + ".enabled")
        set_visible(self.camera, visible)
        self.enabled = visible
        cmds.refresh(force=True)
        self._visibility_label(True)
        self._status(u"辅助线已显示。" if visible else u"辅助线已隐藏。")

    def _delete(self):
        self._require_config()
        if cmds.confirmDialog(title=u"删除构图辅助线", message=u"删除此相机的辅助线？\n%s" % self.camera,
                              button=[u"是", u"否"], defaultButton=u"否",
                              cancelButton=u"否", dismissString=u"否") != u"是":
            return
        remove(self.camera)
        self._visibility_label(False)
        cmds.refresh(force=True)
        self._status(u"已删除当前相机的构图辅助线。")

    def _clean_cache(self):
        if cmds.confirmDialog(title=u"清理缓存", message=u"清理场景中所有有效构图配置的 PNG 缓存？",
                              button=[u"是", u"否"], defaultButton=u"否",
                              cancelButton=u"否", dismissString=u"否") != u"是":
            return
        clean_cache()
        self._status(u"已清理有效构图配置的缓存，场景节点保留。")


_window_instance = None


def show():
    global _window_instance
    if (_window_instance is None or
            not cmds.window(_window_instance.window, exists=True)):
        _window_instance = CompositionGuidesWindow()
    cmds.window(_window_instance.window, edit=True, iconify=False)
    cmds.showWindow(_window_instance.window)
    return _window_instance


atexit.register(_remove_callbacks)
_install_callbacks()
_recover_scene()
