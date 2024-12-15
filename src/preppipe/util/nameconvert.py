# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import pypinyin
import re
import enum

class NameConvertStyle(enum.Enum):
  NORMAL = 0
  ABBREVIATION = enum.auto()

def _fallback_handling(s : str) -> str:
  result_str = ''
  for ch in s:
    if ch.isascii():
      if ch.isalnum():
        result_str += ch
      else:
        if len(result_str) == 0 or result_str[-1] != '_':
          result_str += '_'
    else:
      result_str += hex(ord(ch))
  return result_str

def _str_conversion_impl(name : str, style : NameConvertStyle) -> str:
  if name.isascii():
    return _fallback_handling(name)
  else:
    match style:
      case NameConvertStyle.ABBREVIATION:
        result = pypinyin.lazy_pinyin(name, style=pypinyin.Style.FIRST_LETTER, errors=lambda c : _fallback_handling(c))
        return ''.join(result)
      case _:
        result = pypinyin.lazy_pinyin(name, style=pypinyin.Style.NORMAL, neutral_tone_with_five=True, tone_sandhi=True, errors=lambda c : _fallback_handling(c))
        return ''.join([s.title() for s in result])


def str2identifier(name : str, style : NameConvertStyle = NameConvertStyle.NORMAL) -> str:
  # 将一个字符串转换为可以用在各种代码里的标识符
  assert isinstance(name, str)
  if len(name) == 0:
    return ''
  if re.match(r'''^[a-zA-Z]+[0-0A-Za-z_]*$''', name) is not None:
    return name
  resultstr = _str_conversion_impl(name, style)
  if len(resultstr) > 0:
    if not (resultstr[0].isascii() and resultstr[0].isalpha()):
      resultstr = 'n_' + resultstr
  return resultstr

def str2pathcomponent(s : str, style : NameConvertStyle = NameConvertStyle.NORMAL) -> str:
  # 将字符串转换为可以用于文件路径的字符串
  # 可以返回空字符串，调用者需要自行忽略当前部分
  assert isinstance(s, str)
  if len(s) == 0:
    return ''
  if re.match(r'''^[a-zA-Z0-9_]+$''', s) is not None:
    return s
  resultstr = _str_conversion_impl(s, style)
  return resultstr
