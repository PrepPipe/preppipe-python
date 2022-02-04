# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

"""Abstraction for input sources"""


##
# @namespace preppipe.inputmodel
# @~english @brief Abstraction for input sources
# @~chinese @brief 输入内容的抽象层
# @~
#
# **TESTBOLD**
#
# <details open>
# <summary>English</summary>
# Test detailed doc
# </details>
# 
# <details open>
# <summary>中文</summary>
# 测试中文
# </details>
# 
#

##
# @file preppipe/inputmodel.py
# @~english @brief See preppipe.inputmodel for documentation
# @~chinese @brief 请从 preppipe.inputmodel 查看文档
# @~

import typing
import PIL.Image
import importlib
import hashlib
from enum import Enum

from .commontypes import *

class IMBlock:
  """!
  @~english @brief Base class for all block level constructs
  @~chinese @brief 所有区块类的基类
  @~
  
  123
  """
  def __init__(self) -> None:
    pass
  

