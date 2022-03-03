#!/usr/bin/env python3

import os
import unittest

import preppipe.util
from . import util

class TestFontUtil(unittest.TestCase):
  def test_FontSizeConverter(self):
    converter = preppipe.util.FontSizeConverter()
    _default_font_size_dict = {
      -4: 5,  # \tiny
      -3: 7,  # \scriptsize
      -2: 8,  # \footnotesize
      -1: 9,  # \small
      0: 10, # \normalsize
      1: 12, # \large
      2: 14.4,  # \Large
      3: 17.28, # \LARGE
      4: 20.74, # \huge
      5: 24.88  # \Huge
    }
    for size, point in _default_font_size_dict.items():
      result_size = converter.getSizeFromPoints(point)
      result_point = converter.getPointsFromSize(size)
      self.assertEqual(result_size, size)
      self.assertLess(abs(result_point - point), 0.5)
    
if __name__ == '__main__':
  unittest.main()
    