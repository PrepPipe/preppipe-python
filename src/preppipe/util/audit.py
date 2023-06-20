# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import typing

class FileAccessAuditor:
  # 该类用于存储所有在读取阶段有关的设置，读取完毕后可扔

  # 审计相关的部分
  # 如果运行该程序的系统不属于输入文件的作者，我们用这类审计手段来限制可访问的文件的范围
  # 所有的字符串都是绝对路径
  _accessible_directories : set[str] # 绝对路径
  _global_searchroots : list[str]

  def add_permissible_path(self, v : str):
    realpath = os.path.realpath(v)
    if os.path.isdir(realpath):
      self._accessible_directories.add(realpath)

  def add_global_searchpath(self, v : str):
    realpath = os.path.realpath(v)
    if os.path.isdir(realpath):
      if realpath not in self._global_searchroots:
        self._global_searchroots.append(realpath)

  def check_is_path_accessible(self, realpath : str) -> bool:
    # 检查 abspath 是否为目录白名单中之一
    parent = os.path.dirname(realpath)
    for candidate in self._accessible_directories:
      if os.path.commonprefix([candidate, parent]) == candidate:
        return True
    return False

  def search(self, querypath : str, basepath : str, filecheckCB : typing.Callable) -> typing.Any:
    # querypath 是申请访问的文件名（来自文档内容，不可信），可能含后缀也可能不含，可能是绝对路径也可能是相对路径
    # basepath 是访问发起的文件路径，绝对路径
    # filecheckCB 是回调函数，接受一个绝对路径，若文件不符合要求则返回 None ，如果符合则返回任意非 None 的值，作为该 search() 的返回值
    if os.path.isabs(querypath):
      # 如果是绝对路径的话理应包含后缀名，就不考虑没有后缀名的情况了
      if not self.check_is_path_accessible(querypath):
        return None
      return filecheckCB(querypath)
    searchpaths = [os.path.dirname(basepath)]
    searchpaths.extend(self._global_searchroots)
    for base in searchpaths:
      candidate = os.path.join(base, querypath)
      if not self.check_is_path_accessible(candidate):
        continue
      # 先解决有后缀的情况
      if os.path.exists(candidate):
        if result := filecheckCB(candidate):
          return result
        continue
      # 再解决没有后缀、需要猜的情况
      parent = os.path.dirname(candidate)
      basename = os.path.basename(candidate)
      for file in os.listdir(parent):
        if not file.startswith(basename):
          continue
        root, ext = os.path.splitext(file)
        if root == basename and len(ext) > 0:
          candidatepath = os.path.join(parent, file)
          if result := filecheckCB(candidatepath):
            return candidatepath
    return None

  def dump(self):
    print('FileAccessAuditor:')
    print('  Search path(s): ' + str(len(self._global_searchroots)))
    for p in self._global_searchroots:
      print('    ' + p)
    print('  Accessible: ' + str(len(self._accessible_directories)))
    for p in self._accessible_directories:
      print('    ' + p)

  def __init__(self) -> None:
    self._accessible_directories = set()
    self._global_searchroots = []
