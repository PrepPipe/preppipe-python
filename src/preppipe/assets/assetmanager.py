# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该类用于管理语涵编译器中内嵌的较大的素材。
# 这里的每个“素材”指一个路径，可以是目录也可以是文件。
# 每个素材同时也拥有一个对应的处理类，用于在程序中使用这个素材时进行处理。
# 主程序可以通过提供一个固定的路径来获取这个素材的处理类，然后使用这个处理类来处理素材。

# 由于这些素材需要通过额外的方式获取，我们必须假设(1)素材可能不存在，(2)素材内容可能是由攻击者恶意炮制的。
# 为了应对(1), 主程序所有需要用到素材的地方都应该支持在没有素材的情况下正常运行。
# 为了应对(2), 素材处理类应该对素材内容进行检查，确保素材只由预先设定的用途与方式读取和使用。
# 同时我们使用白名单机制，只有在内嵌的素材处理类中注册的素材才会被处理。我们不包含对素材的运行时注册机制。

# 由于素材处理类可能使用本类来获取内嵌的素材，为了避免循环依赖，我们不能在本类中直接引用任何素材处理类。
# （素材处理类可以有自己的 Tool 主程序入口来使用该类）

# 所有不需要读取已安装素材的操作都由本类的静态方法来完成，所有需要读取已安装素材的操作都由实例来完成。
# 可通过 get_instance() 获取本类的单例。

import os
import sys
import time
import typing
import json
import dataclasses
from ..language import *
from ..exceptions import *
from ..tooldecl import ToolClassDecl
from .assetclassdecl import _registered_asset_classes

@ToolClassDecl("assetmanager")
class AssetManager:
  _debug : typing.ClassVar[bool] = False
  _instance : typing.ClassVar["AssetManager | None"] = None

  # 所有的素材都在这里列举，键是素材的路径名，值是一个字典，包含了构建参数
  # 素材的路径名都应该以素材处理类的名字开头，然后是一个短横线，然后是素材的名字
  # 字符串类型的参数值在使用时会使用 str.format() 进行替换，目前可以用的变量有：
  # {srcpath}: 素材的源路径 (一般是<项目根目录>/assets)
  ASSET_MANIFEST : typing.ClassVar[dict] = {
    "imagepack-template-background-interior-private-Koala.zip" : {
      "yamlpath" : "{srcpath}/imagepack/background/A0-考拉Koala/T0-小型室内/config.yml",
    },
    "imagepack-template-background-interior-public-Koala.zip" : {
      "yamlpath" : "{srcpath}/imagepack/background/A0-考拉Koala/T1-大型室内/config.yml",
    },
    "imagepack-template-background-exterior-Koala.zip" : {
      "yamlpath" : "{srcpath}/imagepack/background/A0-考拉Koala/T2-室外/config.yml",
    },
  }

  @dataclasses.dataclass
  class AssetPackInfo:
    installpath : str # 在 _install 目录中的相对路径
    handle_class : type # 应该是一个由 AssetClassDecl 修饰的类
    handle : typing.Any | None # 应该是 handle_class 的一个实例

  _assets : dict[str, AssetPackInfo]

  def __init__(self) -> None:
    self._assets = {}
    installpath = AssetManager.get_asset_install_path()
    for relpath in AssetManager.ASSET_MANIFEST.keys():
      classid = relpath.split("-")[0]
      name = os.path.splitext(relpath)[0]
      handle_class = _registered_asset_classes.get(classid, None)
      if handle_class is None:
        raise PPInternalError(f"Asset class {classid} not found")
      handle = None
      asset_srcpath = os.path.join(installpath, relpath)
      if os.path.exists(asset_srcpath):
        handle = handle_class.create_from_asset_archive(asset_srcpath)
      self._assets[name] = AssetManager.AssetPackInfo(installpath=relpath, handle_class=handle_class, handle=handle)

  def get_assets_json(self) -> dict:
    result_dict = {}
    missing_assets_list : list[str] = []
    for name, info in self._assets.items():
      if info.handle is not None:
        result_dict[name] = info.handle.dump_asset_info_json()
      else:
        missing_assets_list.append(info.installpath)
    if len(missing_assets_list) > 0:
      result_dict["MISSING"] = missing_assets_list
    return result_dict

  @staticmethod
  def get_instance() -> "AssetManager":
    # 获取 AssetManager 的单例
    if AssetManager._instance is None:
      AssetManager._instance = AssetManager()
    return AssetManager._instance

  @staticmethod
  def get_asset_install_path():
    """Get the absolute path of "preppipe/assets/_install" directory"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "_install")

  @staticmethod
  def build_assets(srcpath : str):
    # 从 srcpath 构建所有素材包
    starttime = time.time()
    def print_progress(msg : str):
      curtime = time.time()
      timestr = "[{:.6f}] ".format(curtime - starttime)
      print(timestr + msg)
    install_base = AssetManager.get_asset_install_path()
    num_total_assets = len(AssetManager.ASSET_MANIFEST)
    asset_index = 0
    for relpath, buildargs in AssetManager.ASSET_MANIFEST.items():
      classid = relpath.split("-")[0]
      handle_class = _registered_asset_classes.get(classid, None)
      if handle_class is None:
        raise PPInternalError(f"Asset class {classid} not found")
      converted_args = {}
      for k, v in buildargs.items():
        if isinstance(v, str):
          converted_args[k] = v.format(srcpath=srcpath)
        else:
          converted_args[k] = v
      installpath = os.path.join(install_base, relpath)
      asset_index += 1
      print_progress(f"[{asset_index}/{num_total_assets}] Building asset {installpath}")
      handle_class.build_asset_archive(destpath=installpath, **converted_args)
    print_progress("All assets built")

  @staticmethod
  def tool_main(args : list[str] | None = None):
    # 创建一个有以下参数的 argument parser: [--debug] [--create <yml> | --load <zip>] [--save <zip>] [--fork [args]] [--export <dir>]
    Translatable._init_lang_list()
    parser = argparse.ArgumentParser(description="Asset Management Tool")
    Translatable._language_install_arguments(parser) # pylint: disable=protected-access
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--build", metavar="<dir>", help="Build the asset pack from a directory")
    parser.add_argument("--dump-json", action="store_true", help="Dump all asset info as a JSON string")
    if args is None:
      args = sys.argv[1:]
    parsed_args = parser.parse_args(args)

    if parsed_args.debug:
      AssetManager._debug = True
    Translatable._language_handle_arguments(parsed_args, AssetManager._debug) # pylint: disable=protected-access
    if parsed_args.build is not None:
      AssetManager.build_assets(parsed_args.build)
    if parsed_args.dump_json:
      inst = AssetManager.get_instance()
      print(json.dumps(inst.get_assets_json(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
  raise PPNotImplementedError('Please invoke assetmanager_cmd instead')