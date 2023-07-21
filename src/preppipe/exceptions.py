# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 如果异常是可以因为用户的误操作而出现的，则应该创建翻译域和译段来支持多语言输出
# 如果异常只是因为程序内部错误，则可以使用这里定义的异常类型来减少麻烦

from .language import TR_preppipe

class PPInternalError(RuntimeError):
  '''没有翻译的需求时时，替代默认的 RuntimeError'''
  def __init__(self, msg : str = '') -> None:
    super().__init__(TR_preppipe.unreachable.get_with_msg(msg))

class PPNotImplementedError(NotImplementedError):
  '''没有翻译的需求时时，替代默认的 NotImplementedError'''
  def __init__(self, msg : str = '') -> None:
    super().__init__(TR_preppipe.not_implemented.get_with_msg(msg))

class PPAssertionError(AssertionError):
  def __init__(self, msg : str = '') -> None:
    super().__init__(TR_preppipe.assert_failure.get_with_msg(msg))
