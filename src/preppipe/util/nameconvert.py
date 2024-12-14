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

def str2identifier(name : str, style : NameConvertStyle = NameConvertStyle.NORMAL) -> str:
  assert isinstance(name, str)
  if len(name) == 0:
    return ''
  if re.match(r'''^[a-zA-Z]+[0-0A-Za-z_]*$''', name) is not None:
    return name
  if name.isascii():
    resultstr = _fallback_handling(name)
  else:
    match style:
      case NameConvertStyle.ABBREVIATION:
        result = pypinyin.lazy_pinyin(name, style=pypinyin.Style.FIRST_LETTER, errors=lambda c : _fallback_handling(c))
        resultstr = ''.join(result)
      case _:
        result = pypinyin.lazy_pinyin(name, style=pypinyin.Style.NORMAL, neutral_tone_with_five=True, tone_sandhi=True, errors=lambda c : _fallback_handling(c))
        resultstr = ''.join([s.title() for s in result])
  assert len(resultstr) > 0
  if not (resultstr[0].isascii() and resultstr[0].isalpha()):
    resultstr = 'n_' + resultstr
  return resultstr
