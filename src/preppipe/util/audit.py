# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import typing
from ..language import TranslationDomain

class FileAccessAuditor:
  # 该类用于存储所有在读取阶段有关的设置，读取完毕后可扔

  # 审计相关的部分
  # 如果运行该程序的系统不属于输入文件的作者，我们用这类审计手段来限制可访问的文件的范围
  # 所有的字符串都是绝对路径
  _accessible_directories : set[str] # 绝对路径
  _global_searchroots : list[str]

  _tr : typing.ClassVar[TranslationDomain] = TranslationDomain("FileAccessAuditor")

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
    # basepath 是访问发起的文件路径，绝对路径(有可能是空字符串)
    # filecheckCB 是回调函数，接受一个绝对路径，若文件不符合要求则返回 None ，如果符合则返回任意非 None 的值，作为该 search() 的返回值
    if os.path.isabs(querypath):
      # 如果是绝对路径的话理应包含后缀名，就不考虑没有后缀名的情况了
      if not self.check_is_path_accessible(querypath):
        return None
      return filecheckCB(querypath)
    searchpaths = []
    if len(basepath) > 0:
      searchpaths.append(os.path.dirname(basepath))
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
            return result
    return None

  _tr_name = _tr.tr("name",
    en="File access auditor: ",
    zh_cn="文件访问控制信息：",
    zh_hk="文件訪問控製信息：",
  )
  _tr_searchpath = _tr.tr("search_path",
    en="Search path(s): ",
    zh_cn="搜索路径：",
    zh_hk="搜索路徑：",
  )
  _tr_accessiblepath = _tr.tr("accessible_path",
    en="Accessible path(s): ",
    zh_cn="允许访问的路径：",
    zh_hk="允許訪問的路徑：",
  )

  def dump(self):
    print(self._tr_name)
    print('  ' + self._tr_searchpath.get() + str(len(self._global_searchroots)))
    for p in self._global_searchroots:
      print('    ' + p)
    print('  ' + self._tr_accessiblepath.get() + str(len(self._accessible_directories)))
    for p in self._accessible_directories:
      print('    ' + p)

  _tr_asset_not_found_general = _tr.tr("asset_not_found_general",
    en="Please check if the asset name is spelled correctly and whether the directory containing the asset is included in the search paths. Current search paths: {searchpath}",
    zh_cn="请确认资源名称是否有拼写、输入错误，并检查存放资源的目录是否包含在搜索路径中。当前的搜索路径： {searchpath}",
    zh_hk="請確認資源名稱是否有拼寫、輸入錯誤，並檢查存放資源的目錄是否包含在搜索路徑中。當前的搜索路徑： {searchpath}",
  )
  def get_asset_not_found_errmsg(self):
    return self._tr_asset_not_found_general.format(searchpath=str(self._global_searchroots))

  def __init__(self) -> None:
    self._accessible_directories = set()
    self._global_searchroots = []
