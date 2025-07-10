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

