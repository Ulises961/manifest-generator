import pytest
from inference.inference_processor import InferenceProcessor

@pytest.fixture
def processor():
    return InferenceProcessor()

def test_process_response_with_valid_yaml(processor):
    response = [
        "kind: test\nname: example\n---\nkind: another_test\nname: example2"
    ]
    result = processor.process_response(response)
    assert len(result) == 2
    assert result[0]["name"] == "test"
    assert "kind: test" in result[0]["manifest"]
    assert result[1]["name"] == "another_test"
    assert "kind: another_test" in result[1]["manifest"]

def test_process_response_with_empty_response(processor):
    response = []
    result = processor.process_response(response)
    assert result == []

def test_process_response_with_invalid_content(processor):
    response = [None, "", "   "]
    result = processor.process_response(response)
    assert result == []

def test_process_response_with_mixed_content(processor):
    response = [
        "kind: valid\nname: example",
        None,
        "   ",
        "---\nkind: another_valid\nname: example2"
    ]
    result = processor.process_response(response)
    assert len(result) == 2
    assert result[0]["name"] == "valid"
    assert "kind: valid" in result[0]["manifest"]
    assert result[1]["name"] == "another_valid"
    assert "kind: another_valid" in result[1]["manifest"]

def test_process_response_with_no_kind_field(processor):
    response = [
        "name: example\n---\nname: example2"
    ]
    result = processor.process_response(response)
    assert len(result) == 2
    assert result[0]["name"] == "default-0"
    assert "name: example" in result[0]["manifest"]
    assert result[1]["name"] == "default-1"
    assert "name: example2" in result[1]["manifest"]