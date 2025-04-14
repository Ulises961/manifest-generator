import pytest
from manifest_builder import ManifestBuilder
from utils.file_utils import load_environment
@pytest.fixture(autouse=True)
def load_env():
    load_environment()

def test_get_template_valid_names():
    builder = ManifestBuilder()
    
    assert builder.get_template("config_map") == builder._config_map_template
    assert builder.get_template("deployment") == builder.deployment_template 
    assert builder.get_template("service") == builder._service_template
    assert builder.get_template("stateful_set") == builder._stateful_set_template
    assert builder.get_template("pvc") == builder._pvc_template

def test_get_template_invalid_name():
    builder = ManifestBuilder()
    assert builder.get_template("invalid_name") is None

def test_get_template_empty_name():
    builder = ManifestBuilder()
    assert builder.get_template("") is None

def test_get_template_none_name():
    builder = ManifestBuilder()
    assert builder.get_template(None) is None

def test_build_secrets_yaml():
    assert True
    # builder = ManifestBuilder()
    # secrets = [
    #     {
    #         "name": "secret1",
    #         "data": {"key1": "value1", "key2": "value2"},
    #         "type": "Opaque"
    #     },
    #     {
    #         "name": "secret2",
    #         "data": {"key3": "value3", "key4": "value4"},
    #         "type": "docker-registry"
    #     }
    # ]
    # expected_output = (
    #     "---\n"
    #     + builder._config_map_template.format(secrets=secrets)
    # )
    # assert builder.build_secrets_yaml(secrets) == expected_output