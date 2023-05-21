# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import pypinyin
import re

def _fallback_handling(c : str) -> str:
  if c.isalnum():
    return c
  return hex(ord(c))

def str2identifier(name : str) -> str:
  assert isinstance(name, str)
  if len(name) == 0:
    return ''
  if re.match(r'''^[a-zA-Z]+[0-0A-Za-z_]*$''', name) is not None:
    return name
  result = pypinyin.lazy_pinyin(name, style=pypinyin.Style.TONE3, neutral_tone_with_five=True, tone_sandhi=True, errors=lambda c : _fallback_handling(c))
  resultstr = ''.join(result)
  assert len(resultstr) > 0
  if not (resultstr[0].isascii() and resultstr[0].isalpha()):
    resultstr = 'n_' + resultstr
  return resultstr
