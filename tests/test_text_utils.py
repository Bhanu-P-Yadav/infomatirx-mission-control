"""
Unit tests for infomatirx_tools.text_utils.
"""

import unittest
from infomatirx_tools.text_utils import (
    word_count,
    to_slug,
    to_camel_case,
    to_snake_case,
)


class TestTextUtils(unittest.TestCase):

    def test_word_count(self):
        self.assertEqual(word_count(""), 0)
        self.assertEqual(word_count("   "), 0)
        self.assertEqual(word_count("Hello World"), 2)
        self.assertEqual(word_count("The quick brown fox jumps over the lazy dog"), 9)

    def test_to_slug(self):
        self.assertEqual(to_slug(""), "")
        self.assertEqual(to_slug("Hello World!"), "hello-world")
        self.assertEqual(to_slug("Infomatirx AI Software 2026"), "infomatirx-ai-software-2026")

    def test_to_camel_case(self):
        self.assertEqual(to_camel_case(""), "")
        self.assertEqual(to_camel_case("hello_world"), "helloWorld")
        self.assertEqual(to_camel_case("infomatirx-task-manager"), "infomatirxTaskManager")

    def test_to_snake_case(self):
        self.assertEqual(to_snake_case(""), "")
        self.assertEqual(to_snake_case("helloWorld"), "hello_world")
        self.assertEqual(to_snake_case("InfomatirxMissionControl"), "infomatirx_mission_control")


if __name__ == "__main__":
    unittest.main()
