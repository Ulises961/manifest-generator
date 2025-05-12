import pytest
from inference.inference_engine import InferenceEngine
from unittest.mock import Mock, patch
import logging

@pytest.fixture
def inference_engine():
    model = Mock()
    tokenizer = Mock()
    return InferenceEngine(model, tokenizer)

def test_process_response_empty(inference_engine):
   
    result = inference_engine.process_response("")
    assert result == []

def test_process_response_single_manifest(inference_engine):
    response = """kind: TestManifest
content: test"""
    result = inference_engine.process_response(response)
    assert len(result) == 1
    assert result[0]["name"] == "TestManifest"
    assert result[0]["manifest"] == response

def test_process_response_multiple_manifests(inference_engine):
    response = """kind: First
content: one
---
kind: Second 
content: two"""
    result = inference_engine.process_response(response)
    assert len(result) == 2
    assert result[0]["name"] == "First"
    assert result[1]["name"] == "Second"

def test_process_response_no_kind(inference_engine):
    response = "content: test"
    result = inference_engine.process_response(response)
    assert len(result) == 1
    assert result[0]["name"] == "default"
    assert result[0]["manifest"] == response

def test_process_response_with_whitespace(inference_engine):
    response = """
    kind: Test
    content: test
    """
    result = inference_engine.process_response(response)
    assert len(result) == 1
    assert result[0]["name"] == "Test"