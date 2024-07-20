# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该类用于一些我们不需要一个特别的类的、纯粹的文件素材

import os
import shutil
import typing
from .assetclassdecl import AssetClassDecl

@AssetClassDecl("file")
class FileAssetPack:
  path : str

  @staticmethod
  def create_from_asset_archive(path : str):
    return FileAssetPack(path)

  @staticmethod
  def build_asset_archive(name : str, destpath : str, copyfrom : str):
    if os.path.isdir(copyfrom):
      os.makedirs(destpath, exist_ok=True)
      shutil.copytree(copyfrom, destpath, dirs_exist_ok=True, ignore_dangling_symlinks=True)
    else:
      shutil.copy2(copyfrom, destpath)

  def __init__(self, path : str):
    self.path = path

  def dump_asset_info_json(self):
    result_dict : dict[str, typing.Any] = {
      "type": "file",
      "basepath": self.path
    }
    if os.path.isdir(self.path):
      filelist = []
      for root, _, files in os.walk(self.path):
        for file in files:
          filelist.append(os.path.relpath(os.path.join(root, file), self.path))
      if len(filelist) > 0:
        result_dict["files"] = filelist
    return result_dict
