from unittest import TestCase
from unittest.mock import patch
from inference.prompt_builder import PromptBuilder

class TestPromptBuilder(TestCase):
    def setUp(self):
        self.prompt_builder = PromptBuilder()

    @patch("logging.Logger.info")
    def test_generate_system_prompt(self, mock_logger_info):
        test_prompt = "You are a strict Kubernetes manifests generator."
        result = self.prompt_builder._generate_system_prompt(test_prompt)
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["type"], "text")
        self.assertIn("You are a strict Kubernetes manifests generator.", result[0]["text"])
        mock_logger_info.assert_called_once_with("Generating common prompt for microservices.")

    def test_generate_prompt(self):
        test_prompt = "Now generate Kubernetes manifests in YAML format for the microservice 'service1'."
        result = self.prompt_builder.generate_user_prompt(test_prompt)

        self.assertIsInstance(result, list)
        self.assertEqual(result[0]["role"], "user")
        self.assertIn("Now generate Kubernetes manifests in YAML format for the microservice 'service1'.", result[0]["content"])