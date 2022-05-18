#!/usr/bin/env python3

import os
import typing
import unittest
import preppipe
import preppipe.frontend.commandast
import preppipe.frontend.commandastparser

from .. import util

class TestCommandASTParser(unittest.TestCase):
  _test_cases : typing.List[typing.Tuple[str, str]] = [
    ("[command]", ""),
    ("[c1] [ c2] [c3 ]    【c4 value1】 [  命令 v1 v2, kv1=v2] # comment ", ""),
    ("[arithmetic hp+100,mp-200] ", "")
  ]
  def test_parse_command_ast(self):
    for testcase in self._test_cases:
      text = testcase[0]
      resultAST = preppipe.frontend.commandastparser.create_command_ast(text, None)
      resultStr = "<None>"
      if resultAST is not None:
        resultStr = resultAST.to_string(0)
      print("result for \"" + text + "\": \n" + resultStr)

