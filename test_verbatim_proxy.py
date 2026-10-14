#!/usr/bin/env python3
"""Tests for verbatim_proxy.mark / transform (python3 test_verbatim_proxy.py)."""
import unittest
from verbatim_proxy import mark, transform

class T(unittest.TestCase):
    def test_files_and_paths(self):
        self.assertEqual(mark("escribe errores.txt en /tmp/datos/salida"), "escribe `errores.txt` en `/tmp/datos/salida`")
        self.assertEqual(mark("mira config/colector.yaml"), "mira `config/colector.yaml`")
    def test_left_alone(self):
        for t in ["versión 2.5 y 3.14", "la IP 10.0.4.17", "ya `informe.md`", "```\ncat a.txt\n```", "/tmp sola", "e.g. esto"]:
            self.assertEqual(mark(t), t)
    def test_only_user_messages(self):
        b = {"messages": [{"role": "system", "content": "lee a.txt"}, {"role": "user", "content": "lee a.txt"},
                          {"role": "tool", "content": "a.txt"}, {"role": "user", "content": [{"type": "text", "text": "y b.csv"}]}]}
        transform(b)
        self.assertEqual(b["messages"][0]["content"], "lee a.txt")
        self.assertEqual(b["messages"][1]["content"], "lee `a.txt`")
        self.assertEqual(b["messages"][2]["content"], "a.txt")
        self.assertEqual(b["messages"][3]["content"][0]["text"], "y `b.csv`")

if __name__ == "__main__":
    unittest.main()
