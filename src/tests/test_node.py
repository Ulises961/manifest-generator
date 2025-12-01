import pytest
from tree.node import Node
from tree.node_types import NodeType

def test_value_property():
    # Test with string value
    node = Node("test", NodeType.ROOT, "test_value")
    assert node.value == "test_value"

    # Test with list value
    list_node = Node("test", NodeType.ROOT, ["value1", "value2"]) 
    assert list_node.value == ["value1", "value2"]

    # Test with None value
    none_node = Node("test", NodeType.ROOT, None)
    assert none_node.value is None

def test_add_child():
    parent = Node("parent", NodeType.ROOT, "parent_value")
    child = Node("child", NodeType.ENV, "child_value")
    
    parent.add_child(child)
    assert child in parent.children
    assert child.parent == parent
    assert len(parent.children) == 1

def test_add_children():
    parent = Node("parent", NodeType.ROOT, "parent_value")
    child1 = Node("child1", NodeType.ENV, "value1")
    child2 = Node("child2", NodeType.ENV, "value2")
    
    parent.add_children([child1, child2])
    assert child1 in parent.children
    assert child2 in parent.children
    assert child1.parent == parent
    assert child2.parent == parent
    assert len(parent.children) == 2

def test_node_equality():
    node1 = Node("test", NodeType.ROOT, "value")
    node2 = Node("test", NodeType.ROOT, "value")
    node3 = Node("different", NodeType.ENV, "value")
    
    assert node1 == node2
    assert node1 != node3
    assert node1 != "not_a_node"

def test_to_dict():
    node = Node("test", NodeType.ROOT, "value")
    node_dict = node.to_dict()
    
    assert node_dict["name"] == "test"
    assert node_dict["type"] == NodeType.ROOT
    assert node_dict["parent"] is None

def test_value_setter_with_string():
    """Test setting value with string"""
    node = Node("test", NodeType.ROOT)
    node.value = "new_value"
    assert node.value == "new_value"

def test_value_setter_with_list():
    """Test setting value with list"""
    node = Node("test", NodeType.ROOT)
    node.value = ["item1", "item2"]
    assert node.value == ["item1", "item2"]

def test_value_setter_with_none():
    """Test setting value with None"""
    node = Node("test", NodeType.ROOT, "initial")
    node.value = None
    assert node.value is None

def test_value_setter_with_invalid_type():
    """Test setting value with invalid type raises ValueError"""
    node = Node("test", NodeType.ROOT)
    with pytest.raises(ValueError, match="Value must be a string or a list"):
        node.value = 123

def test_metadata_property():
    """Test metadata property getter"""
    metadata = {"key": "value", "count": 42}
    node = Node("test", NodeType.ROOT, metadata=metadata)
    assert node.metadata == metadata

def test_metadata_setter_with_dict():
    """Test setting metadata with dict"""
    node = Node("test", NodeType.ROOT)
    new_metadata = {"new_key": "new_value"}
    node.metadata = new_metadata
    assert node.metadata == new_metadata

def test_metadata_setter_with_none():
    """Test setting metadata with None converts to empty dict"""
    node = Node("test", NodeType.ROOT, metadata={"initial": "data"})
    node.metadata = None
    assert node.metadata == {}

def test_metadata_setter_with_invalid_type():
    """Test setting metadata with invalid type raises ValueError"""
    node = Node("test", NodeType.ROOT)
    with pytest.raises(ValueError, match="Metadata must be a dictionary or None"):
        node.metadata = "invalid"

def test_node_with_is_persistent_flag():
    """Test node with is_persistent flag"""
    node = Node("test", NodeType.VOLUME, is_persistent=True)
    assert node.is_persistent is True

def test_node_with_is_directory_flag():
    """Test node with is_directory flag"""
    node = Node("test", NodeType.VOLUME, is_directory=True)
    assert node.is_directory is True

def test_node_with_is_file_flag():
    """Test node with is_file flag"""
    node = Node("test", NodeType.VOLUME, is_file=True)
    assert node.is_file is True

def test_repr():
    """Test __repr__ method"""
    parent = Node("parent", NodeType.ROOT)
    child = Node("child", NodeType.ENV, "value", parent=parent)
    repr_str = repr(child)
    assert "Node(" in repr_str
    assert "name=child" in repr_str
    assert "parent=parent" in repr_str

def test_str():
    """Test __str__ method"""
    parent = Node("parent", NodeType.ROOT)
    child = Node("child", NodeType.ENV, "value", parent=parent)
    str_repr = str(child)
    assert "Node(" in str_repr
    assert "name=child" in str_repr
    assert "parent=parent" in str_repr

def test_node_hierarchy():
    """Test complex node hierarchy"""
    root = Node("root", NodeType.ROOT)
    service = Node("service", NodeType.MICROSERVICE)
    env = Node("ENV_VAR", NodeType.ENV, "value")
    
    root.add_child(service)
    service.add_child(env)
    
    assert env.parent == service
    assert service.parent == root
    assert root.parent is None
    assert len(root.children) == 1
    assert len(service.children) == 1

def test_get_children_by_type():
    """Test getting children by type"""
    parent = Node("parent", NodeType.ROOT)
    env1 = Node("ENV1", NodeType.ENV, "val1")
    env2 = Node("ENV2", NodeType.ENV, "val2")
    port = Node("port", NodeType.CONTAINER_PORT, "8080")
    
    parent.add_children([env1, env2, port])
    
    env_children = parent.get_children_by_type(NodeType.ENV)
    assert len(env_children) == 2
    assert env1 in env_children
    assert env2 in env_children
    assert port not in env_children

