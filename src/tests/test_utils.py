from math import nan
from unittest import TestCase
import unittest
from utils import (
    remove_none_values,
)

class TestRemoveNoneValues(TestCase):
    def test_not_dict(self):
        self.assertEqual(remove_none_values("test"), "test")
        self.assertEqual(remove_none_values(123), 123)
        self.assertEqual(remove_none_values(None), None)

    def test_empty_dict(self):
        self.assertEqual(remove_none_values({}), None)

    def test_dict_with_none(self):
        input_dict = {
            "a": 1,
            "b": None,
            "c": "test"
        }
        expected = {
            "a": 1,
            "c": "test"
        }
        self.assertEqual(remove_none_values(input_dict), expected)

    def test_nested_dict_with_none(self):
        input_dict = {
            "a": {"x": None, "y": 2},
            "b": None,
            "c": {"z": None}
        }
        expected = {
            "a": {"y": 2},
        }
        self.assertEqual(remove_none_values(input_dict), expected)

    def test_deeply_nested_dict(self):
        input_dict = {
            "a": {"x": {"y": None, "z": 1}},
            "b": {"p": None, "q": {"r": None, "s": 2}}
        }
        expected = {
            "a": {"x": {"z": 1}},
            "b": {"q": {"s": 2}}
        }
        self.assertEqual(remove_none_values(input_dict), expected)

    def test_dict_with_empty_dict(self):
        input_dict = {
            "a": {},
            "b": {"x": 1},
            "c": None
        }
        expected = {
            "b": {"x": 1}
        }
        self.assertEqual(remove_none_values(input_dict), expected)


if __name__ == '__main__':
    unittest.main()
