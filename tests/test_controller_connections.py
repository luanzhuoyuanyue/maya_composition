from __future__ import absolute_import

import unittest

from test_controller_recovery import _FakeCmds, _load_controller


CAMERA = "|camera|cameraShape"
CONFIG = "|guide|guideShape"
PLANE = "|plane|planeShape"


class _ConnectionCmds(_FakeCmds):
    """Model Maya's DAG parent return only for node-valued connections."""

    def __init__(self):
        super(_ConnectionCmds, self).__init__()
        self.types = {
            CAMERA: "camera", CONFIG: "compositionGuidesLocator",
            PLANE: "imagePlane", "multiplier": "multDoubleLinear",
            "|guide": "transform", "|plane": "transform",
        }
        self.values = {
            CONFIG + ".ownerTag": "OpenAI.CompositionGuides",
            CONFIG + ".dataVersion": 1,
            PLANE + ".cgOwnerTag": "OpenAI.CompositionGuides",
            "multiplier.cgOwnerTag": "OpenAI.CompositionGuides",
        }
        self.connections = [
            (CAMERA + ".message", CONFIG + ".cameraMessage"),
            (CONFIG + ".message", PLANE + ".cgConfigMessage"),
            (CONFIG + ".message", "multiplier.cgConfigMessage"),
        ]

    def ls(self, node, long=False):
        assert long
        return [name for name in self.types
                if name == node or name.rsplit("|", 1)[-1] == node]

    def nodeType(self, node):
        matches = self.ls(node, long=True)
        if len(matches) != 1:
            raise RuntimeError("node is missing or ambiguous")
        return self.types[matches[0]]

    def getAttr(self, plug):
        if plug not in self.values:
            raise RuntimeError("attribute is missing")
        return self.values[plug]

    def listConnections(self, plug, source, destination, plugs=False, type=None):
        assert source != destination
        result = []
        for start, end in self.connections:
            if (start if destination else end) != plug:
                continue
            connected = end if destination else start
            node = connected.split(".", 1)[0]
            if type is not None and self.nodeType(node) != type:
                continue
            if plugs:
                result.append(connected.rsplit("|", 1)[-1])
            elif node.startswith("|"):
                result.append(node.rsplit("|", 1)[0])
            else:
                result.append(node)
        return result

    def isConnected(self, source, destination):
        return (source, destination) in self.connections


class ControllerConnectionTests(unittest.TestCase):

    def setUp(self):
        self.cmds = _ConnectionCmds()
        self.controller = _load_controller(self.cmds)

    def test_camera_lookup_resolves_connected_shape_instead_of_parent(self):
        self.assertEqual(CONFIG, self.controller.find_config(CAMERA))

    def test_dependency_lookup_resolves_image_plane_shape_and_nondag_node(self):
        self.assertEqual(PLANE, self.controller._dependency(CONFIG, "imagePlane"))
        self.assertEqual("multiplier", self.controller._dependency(
            CONFIG, "multDoubleLinear"))

    def test_duplicate_valid_config_shapes_are_rejected(self):
        duplicate = "|otherGuide|otherGuideShape"
        self.cmds.types.update({duplicate: "compositionGuidesLocator",
                               "|otherGuide": "transform"})
        self.cmds.values.update({duplicate + ".ownerTag": "OpenAI.CompositionGuides",
                                 duplicate + ".dataVersion": 1})
        self.cmds.connections.append((CAMERA + ".message", duplicate + ".cameraMessage"))
        with self.assertRaises(self.controller.GuideError):
            self.controller.find_config(CAMERA)

    def test_duplicate_owned_dependencies_are_rejected(self):
        for kind, duplicate in (("imagePlane", "|otherPlane|otherPlaneShape"),
                                 ("multDoubleLinear", "otherMultiplier")):
            self.cmds.types.update({duplicate: kind, "|otherPlane": "transform"})
            self.cmds.values[duplicate + ".cgOwnerTag"] = "OpenAI.CompositionGuides"
            self.cmds.connections.append((CONFIG + ".message", duplicate + ".cgConfigMessage"))
            with self.assertRaises(self.controller.GuideError):
                self.controller._dependency(CONFIG, kind)

    def test_repeated_connection_results_do_not_count_as_duplicate_nodes(self):
        self.cmds.connections += self.cmds.connections[:]
        # Keep the upstream camera lookup singular, as Maya does.
        self.cmds.connections.pop(3)
        self.assertEqual(CONFIG, self.controller.find_config(CAMERA))
        self.assertEqual(PLANE, self.controller._dependency(CONFIG, "imagePlane"))

    def test_connected_nodes_require_exact_destination_attribute_and_type(self):
        self.assertTrue(hasattr(self.controller, "_connected_nodes"),
                        "missing destination-plug resolution")
        self.cmds.connections.extend([
            (CONFIG + ".message", "multiplier.otherMessage"),
            (CONFIG + ".message", PLANE + ".cgConfigMessage[0]"),
            (CONFIG + ".message", "|guide.cgConfigMessage"),
        ])
        self.assertEqual(["multiplier"], self.controller._connected_nodes(
            CONFIG + ".message", "multDoubleLinear", "cgConfigMessage"))
        self.assertEqual([PLANE], self.controller._connected_nodes(
            CONFIG + ".message", "imagePlane", "cgConfigMessage"))
        self.assertEqual([], self.controller._connected_nodes(
            CAMERA + ".message", "compositionGuidesLocator", "otherMessage"))

    def test_malformed_or_missing_destination_nodes_are_ignored(self):
        self.assertTrue(hasattr(self.controller, "_connected_nodes"),
                        "missing destination-plug resolution")
        self.cmds.connections.extend([
            (CONFIG + ".message", "missing.cgConfigMessage"),
            (CONFIG + ".message", "multiplier"),
            (CONFIG + ".message", ".cgConfigMessage"),
            (CONFIG + ".message", "multiplier.other.cgConfigMessage"),
        ])
        self.assertEqual(["multiplier"], self.controller._connected_nodes(
            CONFIG + ".message", "multDoubleLinear", "cgConfigMessage"))

    def test_config_lookup_retains_owner_and_version_validation(self):
        for attribute, invalid in (("ownerTag", "foreign"), ("dataVersion", 2)):
            original = self.cmds.values[CONFIG + "." + attribute]
            self.cmds.values[CONFIG + "." + attribute] = invalid
            self.assertIsNone(self.controller.find_config(CAMERA))
            self.cmds.values[CONFIG + "." + attribute] = original

    def test_dependency_lookup_retains_owner_and_exact_connection_validation(self):
        self.cmds.values["multiplier.cgOwnerTag"] = "foreign"
        self.assertIsNone(self.controller._dependency(CONFIG, "multDoubleLinear"))
        self.cmds.values["multiplier.cgOwnerTag"] = "OpenAI.CompositionGuides"
        self.cmds.connections[-1] = (CONFIG + ".message", "multiplier.otherMessage")
        self.assertIsNone(self.controller._dependency(CONFIG, "multDoubleLinear"))


if __name__ == "__main__":
    unittest.main()
