import os
import logging
from unittest import TestCase
from unittest.mock import patch, MagicMock
from inference.prompt_builder import PromptBuilder
from tree.attached_file import AttachedFile

class TestPromptBuilder(TestCase):
    def setUp(self):
        self.prompt_builder = PromptBuilder()

    @patch("os.getenv")
    def test_is_prod_mode(self, mock_getenv):
        mock_getenv.return_value = "false"
        prompt_builder = PromptBuilder()
        self.assertFalse(prompt_builder.is_prod_mode)

        mock_getenv.return_value = "true"
        prompt_builder = PromptBuilder()
        self.assertTrue(prompt_builder.is_prod_mode)


    @patch("logging.Logger.info")
    def test_generate_system_prompt(self, mock_logger_info):
        result = self.prompt_builder._generate_system_prompt("")
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["type"], "text")
        self.assertIn("You are a strict Kubernetes manifests generator.", result[0]["text"])
        mock_logger_info.assert_called_once_with("Generating common prompt for microservices.")

    @patch("logging.Logger.info")
    def test_generate_prompt(self, mock_logger_info):
        microservice = {"name": "service1", "image": "service1-image", "replicas": 3}
        microservices = [{"name": "service2", "image": "service2-image"}]
        result = self.prompt_builder.generate_user_prompt("")

        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["role"], "user")
        self.assertIn("Now generate Kubernetes manifests in YAML format for the microservice 'service1'.", result[0]["content"])
        self.assertIn("  name: service1", result[0]["content"])
        self.assertIn("  image: service1-image", result[0]["content"])
        self.assertIn("  replicas: 3", result[0]["content"])
        mock_logger_info.assert_called_once_with(
            "Prompt generated for the service1 microservice:\nNow generate Kubernetes manifests in YAML format for the microservice 'service1'.\n\nMicroservice details:\n  name: service1\n  image: service1-image\n  replicas: 3\nOutput:\n"
        )