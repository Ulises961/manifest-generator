import pytest
from inference.prompt_builder import PromptBuilder

@pytest.fixture
def sample_microservices():
    return [
        {
            "name": "service1",
            "port": 8080,
            "image": "service1:latest"
        },
        {
            "name": "service2", 
            "port": 9090,
            "image": "service2:latest"
        }
    ]

@pytest.fixture
def prompt_builder(sample_microservices):
    return PromptBuilder(sample_microservices)

def test_init(prompt_builder):
    assert prompt_builder.prompt != ""
    assert isinstance(prompt_builder.attached_files, list)
    assert len(prompt_builder.attached_files) == 0

def test_add_instruction(prompt_builder):
    instruction = "Test instruction"
    prompt_builder.add_instruction(instruction)
    assert f"Instruction: {instruction}" in prompt_builder.get_prompt()

def test_add_output(prompt_builder):
    output = "Test output"
    prompt_builder.add_output(output)
    assert f"Output: {output}" in prompt_builder.get_prompt()

def test_clear_prompt(prompt_builder):
    prompt_builder.clear_prompt()
    assert prompt_builder.prompt == ""

def test_create_prompt(prompt_builder):
    instruction = "Test instruction"
    output = "Test output"
    prompt_builder.create_prompt(instruction, output)
    assert f"Instruction: {instruction}" in prompt_builder.prompt
    assert f"Output: {output}" in prompt_builder.prompt

def test_generate_prompt(prompt_builder, sample_microservices):
    result = prompt_builder.generate_prompt(sample_microservices[0])
    print(result)
    assert False
    assert "service1" in result
    assert "Guidelines:" in result
    assert "Output:" in result

def test_generate_second_pass_prompt(prompt_builder):
    prompt_builder.generate_second_pass_prompt()
    assert "DevOps engineer" in prompt_builder.prompt
    assert "Guidelines:" in prompt_builder.prompt