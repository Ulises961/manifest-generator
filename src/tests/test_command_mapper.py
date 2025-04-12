import unittest
from unittest.mock import patch, MagicMock
from tree.command_mapper import CommandMapper
from embeddings.label_classifier import LabelClassifier
from tree.node_types import NodeType
from tree.docker_instruction_node import DockerInstruction
import os
import json


class TestCommandMapper(unittest.TestCase):
    def setUp(self):
        self.label_classifier = LabelClassifier()
        self.command_mapper = CommandMapper(self.label_classifier)

    def test_parse_dockerfile(self):
        # Create temporary dockerfile content
        dockerfile_content = """
        CMD ["python", "app.py"]
        LABEL version="1.0"
        EXPOSE 80
        """
        with open("test_dockerfile", "w") as f:
            f.write(dockerfile_content)

        try:
            result = self.command_mapper.parse_dockerfile("test_dockerfile")
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0]["instruction"], "CMD")
            self.assertEqual(result[1]["instruction"], "LABEL")
            self.assertEqual(result[2]["instruction"], "EXPOSE")
        finally:
            # Cleanup
            os.remove("test_dockerfile")

    def test_generate_cmd_node(self):
        cmd = {"instruction": "CMD", "value": ["python", "app.py"]}
        node = self.command_mapper._generate_cmd_node(cmd)
        self.assertIsInstance(node, DockerInstruction)
        self.assertEqual(node.type, NodeType.CMD)
        self.assertEqual(node.command, ["python", "app.py"])

    @patch("tree.command_mapper.CommandMapper.decide_label")
    def test_generate_label_node(self, mock_decide_label):
        mock_decide_label.return_value = True
        label = {"instruction": "LABEL", "value": "version=1.0"}
        node = self.command_mapper._generate_label_node(label)
        self.assertIsInstance(node, DockerInstruction)
        self.assertEqual(node.type, NodeType.LABEL)
        self.assertEqual(node.command, "version=1.0")

    def test_generate_expose_node(self):
        expose = {"instruction": "EXPOSE", "value": "80"}
        node = self.command_mapper._generate_expose_node(expose)
        self.assertEqual(node["type"], "PORTS")
        self.assertEqual(node["command"], "80")

    def test_generate_volume_node(self):
        # Create temporary volumes.json
        volumes_content = '["test_volume"]'
        with open("volumes.json", "w") as f:
            f.write(volumes_content)

        try:
            os.environ["VOLUMES_PATH"] = "volumes.json"
            volume = {"instruction": "VOLUME", "value": "test_volume"}
            node = self.command_mapper._generate_volume_node(volume)
            self.assertIsInstance(node, DockerInstruction)
            self.assertEqual(node.type, NodeType.VOLUME)
            self.assertTrue(node.is_persistent)
        finally:
            # Cleanup
            os.remove("volumes.json")

    @patch("embeddings.label_classifier.LabelClassifier.classify_label")
    def test_decide_label(self, mock_classify_label):
        mock_classify_label.return_value = "label"
        self.assertTrue(self.command_mapper.decide_label("test_label"))

    def test_get_commands(self):
        parsed_dockerfile = [
            {"instruction": "CMD", "value": ["python", "app.py"]},
            {"instruction": "EXPOSE", "value": "80"},
        ]
        commands = self.command_mapper.get_commands(parsed_dockerfile)
        self.assertEqual(len(commands), 2)
        self.assertIsInstance(commands[0], DockerInstruction)
        self.assertIsInstance(commands[1], dict)

    def test_generate_entrypoint_node(self):
        entrypoint = {"instruction": "ENTRYPOINT", "value": ["python", "app.py"]}
        node = self.command_mapper._generate_entrypoint_node(entrypoint)
        self.assertIsInstance(node, DockerInstruction)
        self.assertEqual(node.type, NodeType.ENTRYPOINT)
        self.assertEqual(node.command, ["python", "app.py"])

    def test_generate_entrypoint_w_script(self):
        entrypoint = {"instruction": "ENTRYPOINT", "value": ["./start.sh"]}
        node = self.command_mapper._generate_entrypoint_node(entrypoint)
        self.assertIsInstance(node, DockerInstruction)
        self.assertEqual(node.type, NodeType.ENTRYPOINT)
        self.assertEqual(node.command, ["./start.sh"])

    def test_generate_entrypoint_w_script_and_args(self):
        entrypoint = {
            "instruction": "ENTRYPOINT",
            "value": ["./start.sh", "--arg1", "--arg2"],
        }
        node = self.command_mapper._generate_entrypoint_node(entrypoint)
        self.assertIsInstance(node, DockerInstruction)
        self.assertEqual(node.type, NodeType.ENTRYPOINT)
        self.assertEqual(node.command, ["./start.sh", "--arg1", "--arg2"])


if __name__ == "__main__":
    unittest.main()
