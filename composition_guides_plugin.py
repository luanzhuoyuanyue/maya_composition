from __future__ import absolute_import, division

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.api.OpenMayaRender as omr
import maya.cmds as cmds

import composition_guides_core as core


def maya_useNewAPI():
    pass


NODE_NAME = "compositionGuidesLocator"
NODE_TYPE_ID = om.MTypeId(0x00087001)
DRAW_CLASSIFICATION = "drawdb/geometry/compositionGuidesLocator"
DRAW_REGISTRANT_ID = "CompositionGuidesPlugin"


class CompositionGuidesLocator(omui.MPxLocatorNode):

    cameraMessage = om.MObject()
    enabled = om.MObject()
    outputMode = om.MObject()
    thirds = om.MObject()
    goldenSpiral = om.MObject()
    spiralOrientation = om.MObject()
    goldenTriangle = om.MObject()
    triangleDirection = om.MObject()
    diagonal = om.MObject()
    diagonalDown = om.MObject()
    diagonalUp = om.MObject()
    center = om.MObject()
    centerCross = om.MObject()
    centerCircle = om.MObject()
    centerBox = om.MObject()
    centerDiamond = om.MObject()
    lineColor = om.MObject()
    lineAlpha = om.MObject()
    lineWidth = om.MObject()
    dataVersion = om.MObject()
    ownerTag = om.MObject()
    renderImagePath = om.MObject()
    renderSignature = om.MObject()
    renderInProgress = om.MObject()

    @staticmethod
    def creator():
        return CompositionGuidesLocator()

    @staticmethod
    def initialize():
        message_attribute = om.MFnMessageAttribute()
        CompositionGuidesLocator.cameraMessage = message_attribute.create(
            "cameraMessage", "cm")
        message_attribute.storable = False
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.cameraMessage)

        numeric_attribute = om.MFnNumericAttribute()
        CompositionGuidesLocator.enabled = numeric_attribute.create(
            "enabled", "en", om.MFnNumericData.kBoolean, True)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(CompositionGuidesLocator.enabled)

        enum_attribute = om.MFnEnumAttribute()
        CompositionGuidesLocator.outputMode = enum_attribute.create(
            "outputMode", "omd", 2)
        enum_attribute.addField("Viewport", 0)
        enum_attribute.addField("Hardware", 1)
        enum_attribute.addField("Both", 2)
        enum_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.outputMode)

        CompositionGuidesLocator.thirds = numeric_attribute.create(
            "thirds", "th", om.MFnNumericData.kBoolean, True)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(CompositionGuidesLocator.thirds)

        CompositionGuidesLocator.goldenSpiral = numeric_attribute.create(
            "goldenSpiral", "gs", om.MFnNumericData.kBoolean, False)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.goldenSpiral)

        CompositionGuidesLocator.spiralOrientation = enum_attribute.create(
            "spiralOrientation", "so", 0)
        enum_attribute.addField("Top Left", 0)
        enum_attribute.addField("Top Right", 1)
        enum_attribute.addField("Bottom Left", 2)
        enum_attribute.addField("Bottom Right", 3)
        enum_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.spiralOrientation)

        CompositionGuidesLocator.goldenTriangle = numeric_attribute.create(
            "goldenTriangle", "gt", om.MFnNumericData.kBoolean, False)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.goldenTriangle)

        CompositionGuidesLocator.triangleDirection = enum_attribute.create(
            "triangleDirection", "td", 0)
        enum_attribute.addField("Down", 0)
        enum_attribute.addField("Up", 1)
        enum_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.triangleDirection)

        CompositionGuidesLocator.diagonal = numeric_attribute.create(
            "diagonal", "dg", om.MFnNumericData.kBoolean, False)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.diagonal)

        CompositionGuidesLocator.diagonalDown = numeric_attribute.create(
            "diagonalDown", "dd", om.MFnNumericData.kBoolean, True)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.diagonalDown)

        CompositionGuidesLocator.diagonalUp = numeric_attribute.create(
            "diagonalUp", "du", om.MFnNumericData.kBoolean, True)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.diagonalUp)

        CompositionGuidesLocator.center = numeric_attribute.create(
            "center", "ce", om.MFnNumericData.kBoolean, False)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(CompositionGuidesLocator.center)

        CompositionGuidesLocator.centerCross = numeric_attribute.create(
            "centerCross", "cc", om.MFnNumericData.kBoolean, True)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.centerCross)

        CompositionGuidesLocator.centerCircle = numeric_attribute.create(
            "centerCircle", "ci", om.MFnNumericData.kBoolean, True)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.centerCircle)

        CompositionGuidesLocator.centerBox = numeric_attribute.create(
            "centerBox", "cb", om.MFnNumericData.kBoolean, False)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.centerBox)

        CompositionGuidesLocator.centerDiamond = numeric_attribute.create(
            "centerDiamond", "cd", om.MFnNumericData.kBoolean, False)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.centerDiamond)

        CompositionGuidesLocator.lineColor = numeric_attribute.createColor(
            "lineColor", "lc")
        numeric_attribute.default = (1.0, 1.0, 0.0)
        numeric_attribute.usedAsColor = True
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.lineColor)

        CompositionGuidesLocator.lineAlpha = numeric_attribute.create(
            "lineAlpha", "la", om.MFnNumericData.kFloat, 0.8)
        numeric_attribute.setMin(0.0)
        numeric_attribute.setMax(1.0)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.lineAlpha)

        CompositionGuidesLocator.lineWidth = numeric_attribute.create(
            "lineWidth", "lw", om.MFnNumericData.kFloat, 2.0)
        numeric_attribute.setMin(1.0)
        numeric_attribute.setMax(10.0)
        numeric_attribute.keyable = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.lineWidth)

        CompositionGuidesLocator.dataVersion = numeric_attribute.create(
            "dataVersion", "dv", om.MFnNumericData.kInt, 1)
        numeric_attribute.hidden = True
        numeric_attribute.keyable = False
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.dataVersion)

        string_data = om.MFnStringData()
        typed_attribute = om.MFnTypedAttribute()
        CompositionGuidesLocator.ownerTag = typed_attribute.create(
            "ownerTag", "ot", om.MFnData.kString,
            string_data.create("OpenAI.CompositionGuides"))
        typed_attribute.hidden = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.ownerTag)

        CompositionGuidesLocator.renderImagePath = typed_attribute.create(
            "renderImagePath", "rip", om.MFnData.kString,
            string_data.create(""))
        typed_attribute.hidden = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.renderImagePath)

        CompositionGuidesLocator.renderSignature = typed_attribute.create(
            "renderSignature", "rs", om.MFnData.kString,
            string_data.create(""))
        typed_attribute.hidden = True
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.renderSignature)

        CompositionGuidesLocator.renderInProgress = numeric_attribute.create(
            "renderInProgress", "rpr", om.MFnNumericData.kBoolean, False)
        numeric_attribute.hidden = True
        numeric_attribute.keyable = False
        numeric_attribute.storable = False
        CompositionGuidesLocator.addAttribute(
            CompositionGuidesLocator.renderInProgress)


class GuideDrawData(om.MUserData):

    def __init__(self):
        om.MUserData.__init__(self, False)
        self.color = (1.0, 1.0, 0.0, 0.8)
        self.line_width = 2.0
        self.gate = (0.0, 0.0, 0.0, 0.0)
        self.segments = []
        self.polylines = []
        self.should_draw = False


def _normalize_camera_path(camera_path):
    path = om.MDagPath(camera_path)
    if path.node().hasFn(om.MFn.kCamera):
        return path
    if not path.node().hasFn(om.MFn.kTransform):
        raise ValueError("camera path does not name a camera")
    shape_count = path.numberOfShapesDirectlyBelow()
    for shape_index in range(shape_count):
        shape_path = om.MDagPath(path)
        shape_path.extendToShape(shape_index)
        if shape_path.node().hasFn(om.MFn.kCamera):
            return shape_path
    raise ValueError("camera transform has no camera shape")


def _connected_camera_path(node_function):
    camera_plug = node_function.findPlug("cameraMessage", False)
    source_plugs = camera_plug.connectedTo(True, False)
    if not source_plugs:
        return None
    source_object = source_plugs[0].node()
    source_path = om.MDagPath.getAPathTo(source_object)
    return _normalize_camera_path(source_path)


def _read_bool(node_function, attribute_name):
    return node_function.findPlug(attribute_name, False).asBool()


def _read_int(node_function, attribute_name):
    return node_function.findPlug(attribute_name, False).asInt()


def _read_float(node_function, attribute_name):
    return node_function.findPlug(attribute_name, False).asFloat()


def _read_color(node_function):
    color_plug = node_function.findPlug("lineColor", False)
    return (
        color_plug.child(0).asFloat(),
        color_plug.child(1).asFloat(),
        color_plug.child(2).asFloat(),
    )


class CompositionGuidesDrawOverride(omr.MPxDrawOverride):

    def __init__(self, obj):
        omr.MPxDrawOverride.__init__(self, obj, None, True)

    @staticmethod
    def creator(obj):
        return CompositionGuidesDrawOverride(obj)

    def isBounded(self, obj_path, camera_path):
        return False

    def hasUIDrawables(self):
        return True

    def supportedDrawAPIs(self):
        return (
            omr.MRenderer.kOpenGL |
            omr.MRenderer.kOpenGLCoreProfile |
            omr.MRenderer.kDirectX11
        )

    def prepareForDraw(self, obj_path, camera_path, frame_context, old_data):
        if isinstance(old_data, GuideDrawData):
            data = old_data
        else:
            data = GuideDrawData()

        data.color = (1.0, 1.0, 0.0, 0.8)
        data.line_width = 2.0
        data.gate = (0.0, 0.0, 0.0, 0.0)
        data.segments = []
        data.polylines = []
        data.should_draw = False

        try:
            self._prepare_draw_data(
                data, obj_path, camera_path, frame_context)
        except (RuntimeError, TypeError, ValueError) as error:
            om.MGlobal.displayWarning(
                "Composition Guides preparation failed: %s" % error)
            data.should_draw = False
        return data

    def _prepare_draw_data(self, data, obj_path, camera_path, frame_context):
        node_function = om.MFnDependencyNode(obj_path.node())
        connected_camera_path = _connected_camera_path(node_function)
        if connected_camera_path is None:
            return

        active_camera_path = _normalize_camera_path(camera_path)
        connected_camera_handle = om.MObjectHandle(
            connected_camera_path.node())
        active_camera_handle = om.MObjectHandle(active_camera_path.node())
        if connected_camera_handle.hashCode() != active_camera_handle.hashCode():
            return

        enabled = _read_bool(node_function, "enabled")
        output_mode = _read_int(node_function, "outputMode")
        render_in_progress = _read_bool(
            node_function, "renderInProgress")
        if not enabled or output_mode == 1 or render_in_progress:
            return

        thirds = _read_bool(node_function, "thirds")
        golden_spiral = _read_bool(node_function, "goldenSpiral")
        spiral_orientation = _read_int(
            node_function, "spiralOrientation")
        golden_triangle = _read_bool(node_function, "goldenTriangle")
        triangle_direction = _read_int(
            node_function, "triangleDirection")
        diagonal = _read_bool(node_function, "diagonal")
        diagonal_down = _read_bool(node_function, "diagonalDown")
        diagonal_up = _read_bool(node_function, "diagonalUp")
        center = _read_bool(node_function, "center")
        center_cross = _read_bool(node_function, "centerCross")
        center_circle = _read_bool(node_function, "centerCircle")
        center_box = _read_bool(node_function, "centerBox")
        center_diamond = _read_bool(node_function, "centerDiamond")
        line_color = _read_color(node_function)
        line_alpha = _read_float(node_function, "lineAlpha")
        line_width = _read_float(node_function, "lineWidth")

        viewport = frame_context.getViewportDimensions()
        origin_x, origin_y, viewport_width, viewport_height = viewport
        if viewport_width <= 0 or viewport_height <= 0:
            return

        render_width = cmds.getAttr("defaultResolution.width")
        render_height = cmds.getAttr("defaultResolution.height")
        pixel_aspect = cmds.getAttr("defaultResolution.pixelAspect")
        render_aspect = cmds.getAttr("defaultResolution.deviceAspectRatio")
        if render_width <= 0 or render_height <= 0 or pixel_aspect <= 0:
            raise ValueError("render dimensions and pixel aspect must be positive")
        if render_aspect <= 0:
            render_aspect = (
                float(render_width) * float(pixel_aspect) /
                float(render_height))

        viewport_aspect = float(viewport_width) / float(viewport_height)
        camera_function = om.MFnCamera(active_camera_path)
        viewing_frustum = camera_function.getViewingFrustum(
            viewport_aspect, True, True, True)
        rendering_frustum = camera_function.getRenderingFrustum(render_aspect)
        gate = core.map_render_gate(
            (origin_x, origin_y, viewport_width, viewport_height),
            viewing_frustum,
            rendering_frustum,
        )

        spiral_orientations = (
            "top_left", "top_right", "bottom_left", "bottom_right")
        triangle_directions = ("down", "up")
        options = {
            "thirds": thirds,
            "golden_spiral": (
                spiral_orientations[spiral_orientation]
                if golden_spiral else False),
            "golden_triangle": (
                triangle_directions[triangle_direction]
                if golden_triangle else False),
            "downward": diagonal and diagonal_down,
            "upward": diagonal and diagonal_up,
            "center": ({
                "cross": center_cross,
                "circle": center_circle,
                "center_box": center_box,
                "diamond": center_diamond,
            } if center else False),
        }
        geometry = core.compose_geometry(
            options, render_width, render_height)

        data.color = (
            line_color[0], line_color[1], line_color[2], line_alpha)
        data.line_width = line_width
        data.gate = gate
        data.segments = geometry["segments"]
        data.polylines = geometry["polylines"]
        data.should_draw = True

    def addUIDrawables(self, obj_path, draw_manager, frame_context, data):
        """Queue screen-space guide lines through MUIDrawManager."""
        if not isinstance(data, GuideDrawData) or not data.should_draw:
            return

        draw_manager.beginDrawable()
        try:
            draw_manager.setColor(om.MColor(data.color))
            draw_manager.setLineWidth(data.line_width)
            draw_manager.setDepthPriority(
                omr.MRenderItem.sActiveWireDepthPriority)

            for start, end in data.segments:
                start_x, start_y = core.map_point_to_gate(start, data.gate)
                end_x, end_y = core.map_point_to_gate(end, data.gate)
                draw_manager.line2d(
                    om.MPoint(start_x, start_y, 0.0),
                    om.MPoint(end_x, end_y, 0.0),
                )

            for polyline in data.polylines:
                for point_index in range(len(polyline) - 1):
                    start_x, start_y = core.map_point_to_gate(
                        polyline[point_index], data.gate)
                    end_x, end_y = core.map_point_to_gate(
                        polyline[point_index + 1], data.gate)
                    draw_manager.line2d(
                        om.MPoint(start_x, start_y, 0.0),
                        om.MPoint(end_x, end_y, 0.0),
                    )
        finally:
            draw_manager.endDrawable()


def initializePlugin(plugin_object):
    plugin = om.MFnPlugin(plugin_object, "OpenAI", "1.0.0", "Any")
    plugin.registerNode(
        NODE_NAME,
        NODE_TYPE_ID,
        CompositionGuidesLocator.creator,
        CompositionGuidesLocator.initialize,
        omui.MPxLocatorNode.kLocatorNode,
        DRAW_CLASSIFICATION,
    )
    omr.MDrawRegistry.registerDrawOverrideCreator(
        DRAW_CLASSIFICATION,
        DRAW_REGISTRANT_ID,
        CompositionGuidesDrawOverride.creator,
    )


def uninitializePlugin(plugin_object):
    omr.MDrawRegistry.deregisterDrawOverrideCreator(
        DRAW_CLASSIFICATION,
        DRAW_REGISTRANT_ID,
    )
    plugin = om.MFnPlugin(plugin_object)
    plugin.deregisterNode(NODE_TYPE_ID)
