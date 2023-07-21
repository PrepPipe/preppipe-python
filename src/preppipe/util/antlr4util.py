# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import random
import antlr4
from ..irbase import *
from ..exceptions import *
from antlr4.error.ErrorListener import ErrorListener, ConsoleErrorListener

class ErrorListenerBase(ErrorListener):
  # since we run command scanning in every single paragraph in the input text,
  # we expect a lot of errors here and we don't want to report them
  # so we just record whether there is a failure or not and done
  _error_occurred : bool
  _error_column : int
  _error_msg : str

  def __init__(self):
    super().__init__()
    self._error_occurred = False
    self._error_column = 0
    self._error_msg = ''

  def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
    if not self._error_occurred:
      if not (isinstance(column, int) and isinstance(msg, str)):
        raise PPAssertionError
      self._error_occurred = True
      self._error_column = column
      self._error_msg = msg

  @property
  def error_occurred(self):
    return self._error_occurred

  def get_first_error_msg(self) -> str:
    return self._error_msg

  def get_first_error_column(self) -> int:
    return self._error_column

@dataclasses.dataclass
class TextStringParsingUtil:
  content : list[StringLiteral | TextFragmentLiteral]
  cumulative_lengths : list[int] # for each content, which is its starting index
  fullstr : str

  @staticmethod
  def create(content : list[StringLiteral | TextFragmentLiteral]):
    cumulative_lengths : list[int] = []
    merged_str = ''
    length = 0
    for v in content:
      if not isinstance(v, (StringLiteral, TextFragmentLiteral)):
        raise PPAssertionError
      curstr = v.get_string()
      merged_str += curstr
      cumulative_lengths.append(length)
      length += len(curstr)
    return TextStringParsingUtil(content=content, cumulative_lengths=cumulative_lengths, fullstr=merged_str)

  def get_full_str(self):
    return self.fullstr

  def extract_str_from_interval(self, start : int, end : int) -> list[StringLiteral | TextFragmentLiteral]:
    # 把 [start, end) 区间内的字符都提出来
    if start == end:
      return []
    if not (start >= 0 and end <= len(self.fullstr) and start < end):
      raise PPAssertionError
    curindex = 0
    while curindex < len(self.content) and self.cumulative_lengths[curindex] <= start:
      curindex += 1

    # 这是第一段文本应该开始的地方
    curindex -= 1
    result = []
    while True:
      curoffset = self.cumulative_lengths[curindex]
      if not curoffset <= start:
        raise PPAssertionError
      curvalue = self.content[curindex]
      curstr = curvalue.get_string()
      curstop = curoffset + len(curstr)
      if curstop >= end:
        # 这是最后一截
        startcut = start - curoffset
        endcut = curstop - end
        finalstr = curstr[startcut:] if endcut == 0 else curstr[startcut:-endcut]
        strliteral = StringLiteral.get(finalstr, curvalue.context)
        if isinstance(curvalue, StringLiteral):
          result.append(strliteral)
        elif isinstance(curvalue, TextFragmentLiteral):
          v = TextFragmentLiteral.get(curvalue.context, strliteral, curvalue.style)
          result.append(v)
        else:
          raise PPInternalError
        break
      # 我们需要继续
      if curoffset == start:
        # 不需要截掉开头
        result.append(curvalue)
      else:
        # 需要截开头
        startcut = start - curoffset
        finalstr = curstr[startcut:]
        strliteral = StringLiteral.get(finalstr, curvalue.context)
        if isinstance(curvalue, StringLiteral):
          result.append(strliteral)
        elif isinstance(curvalue, TextFragmentLiteral):
          v = TextFragmentLiteral.get(curvalue.context, strliteral, curvalue.style)
          result.append(v)
        else:
          raise PPInternalError
      curindex += 1
      start = curstop
    return result

def _testround():
  length = random.randint(0,50)
  randstr = ''
  for i in range(0, length):
    digit = random.randint(0,9)
    randstr += str(digit)
  testcases = []
  for i in range(0, 20):
    start = random.randint(0, length)
    end = random.randint(0, length)
    if start > end:
      tmp = end
      end = start
      start = tmp
    testtuple = (start, end, randstr[start:end])
    testcases.append(testtuple)
  numcuts = random.randint(0, length)
  cutlist = [random.randint(0, length) for i in range(0, numcuts)]
  cutlist.sort()
  cutlist.append(length)
  ctx = Context()
  content = []
  baseoffset = 0
  for cut in cutlist:
    if baseoffset == cut:
      continue
    curstr = randstr[baseoffset : cut]
    baseoffset = cut
    content.append(StringLiteral.get(curstr, ctx))
  pu = TextStringParsingUtil.create(content=content)
  if not pu.get_full_str() == randstr:
    raise PPAssertionError
  for start, end, expected in testcases:
    npu = TextStringParsingUtil.create(content=pu.extract_str_from_interval(start, end))
    if not npu.get_full_str() == expected:
      raise PPAssertionError

if __name__ == "__main__":
  for i in range(0, 100):
    _testround()