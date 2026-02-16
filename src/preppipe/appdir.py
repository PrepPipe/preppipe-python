# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

"""可执行/基础目录的解析与覆盖，供设置文件、Ren'Py SDK 等路径统一使用。"""

import os
import sys


def _compute_executable_base_dir() -> str:
  """打包运行时为可执行文件所在目录，否则为 preppipe 包所在目录。"""
  if getattr(sys, 'frozen', False):
    return os.path.dirname(sys.executable)
  return os.path.dirname(os.path.abspath(__file__))


_executable_base_dir: str = _compute_executable_base_dir()


def get_executable_base_dir() -> str:
  """返回当前认定的「可执行/基础」目录。"""
  return _executable_base_dir


def set_executable_base_dir(path: str) -> None:
  """在未打包环境下覆盖基础目录（如 GUI 启动时指定设置目录）。打包后调用无效。"""
  global _executable_base_dir
  if getattr(sys, 'frozen', False):
    return
  _executable_base_dir = os.path.abspath(path)
  if not os.path.isdir(_executable_base_dir):
    raise FileNotFoundError(f"Path '{_executable_base_dir}' does not exist")
