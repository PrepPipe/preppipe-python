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
import pickle
import collections
import yaml
from ..language import *
from ..exceptions import *
from ..tooldecl import ToolClassDecl
from .assetclassdecl import _registered_asset_classes
from ..util.message import MessageHandler
from ..util.nameconvert import str2identifier
from .._version import __version__

@dataclasses.dataclass
class AssetManifestObject:
  program_version : str
  descriptors : dict[str, list[typing.Any]]
  items_by_class : dict[str, list[str]]

@ToolClassDecl("assetmanager")
class AssetManager:
  TR_assetmanager = TranslationDomain("assetmanager")
  _debug : typing.ClassVar[bool] = False
  _instance : typing.ClassVar["AssetManager | None"] = None

  # 指定额外的素材目录的环境变量
  # 每个素材目录都应该有个 preppipe_asset_manifest.yml 文件，用于描述该目录下所有的素材包
  # 对于每一个素材目录，我们都会在其上一层新建一个 __preppipe_build__/<原名称> 目录，用于存放构建好的素材包
  # （即 path/to/a 会有一个 path/to/__preppipe_build__/a 的构建目录）
  EXTRA_ASSETS_ENV : typing.ClassVar[str] = "PREPPIPE_EXTRA_ASSETS_SRCDIR"
  EXTRA_ASSETS_BUILD_DIR_PARENT : typing.ClassVar[str] = "__preppipe_build__"
  # 为了方便用户在不（经常）改环境变量的情况下使用额外的素材目录，我们使用以下环境变量来自动搜索额外的素材目录
  # 对于这个环境变量指向的每个目录，我们查看每个子目录，看看里面有没有 preppipe_asset_manifest.yml 文件，有的话这个子目录将会以和上面一样的方式被处理
  EXTRA_ASSETS_PARENT_DIRS_ENV : typing.ClassVar[str] = "PREPPIPE_EXTRA_ASSETS_SRCDIR_PARENTS"

  # 素材包的清单文件名，如果有什么信息需要在没有素材时也能获取（比如程序的另一个部分如何引用这些素材），则在这个文件中保存
  MANIFEST_NAME : typing.ClassVar[str] = "manifest.pickle"

  # 对于额外的素材目录，应该在每个目录下都有这么一个文件，包含类似 ASSET_MANIFEST 的内容
  MANIFEST_SRC_NAME : typing.ClassVar[str] = "preppipe_asset_manifest.yml"

  # 以下列举所有在其他地方可能用到的内嵌素材
  ASSETREF_DEFAULT_FONT = "thirdparty_Adobe_SourceHanSerif"

  # 有引用时可以把它们放在这里，构建时会检查是否存在
  ASSETREF_CHECKLIST : typing.ClassVar[tuple[str]] = (
    ASSETREF_DEFAULT_FONT,
  )

  @staticmethod
  def decompose_asset_relpath(relpath : str) -> tuple[str, str]:
    # 每个 ASSET_MANIFEST 的键都应该是一个符合该函数逻辑的相对路径
    basename = os.path.basename(relpath)
    classid = basename.split("-")[0] # 素材处理类的名字
    name = os.path.splitext(basename)[0] # 素材的名字
    return (classid, name)

  @dataclasses.dataclass
  class AssetPackInfo:
    installpath : str # 素材包的完整路径；内嵌素材的话应该在 _install 目录中
    handle_class : type # 应该是一个由 AssetClassDecl 修饰的类
    handle : typing.Any | None # 应该是 handle_class 的一个实例

  _assets : dict[str, AssetPackInfo]

  def __init__(self, load_manifest : bool = True) -> None:
    self._assets = {}
    if load_manifest:
      self.try_load_manifest()

  @staticmethod
  def is_builtin_manifest_exists() -> bool:
    manifest_filepath = os.path.join(AssetManager.get_embedded_asset_install_path(), AssetManager.MANIFEST_NAME)
    return os.path.exists(manifest_filepath)

  def try_load_manifest(self):
    # 先尝试加载内嵌的素材列表
    manifest_filepath = os.path.join(AssetManager.get_embedded_asset_install_path(), AssetManager.MANIFEST_NAME)
    if os.path.exists(manifest_filepath):
      with open(manifest_filepath, "rb") as f:
        manifest = pickle.load(f)
        res = self._handle_manifest(manifest, install_base=AssetManager.get_embedded_asset_install_path(), isbuiltin=True)
        if not res:
          raise PPInternalError("Failed to load builtin asset manifest")
    # 再尝试加载额外的素材列表
    # 我们需要保证稳定的顺序，所以使用 OrderedDict，值无所谓
    extra_assets_dirs_dict = collections.OrderedDict()
    if envval := os.getenv(AssetManager.EXTRA_ASSETS_PARENT_DIRS_ENV, None):
      for p in envval.split(os.pathsep):
        if os.path.isdir(p):
          for sub in os.listdir(p):
            subpath = os.path.realpath(os.path.join(p, sub))
            if os.path.isdir(subpath):
              manifestpath = os.path.join(subpath, AssetManager.MANIFEST_SRC_NAME)
              if os.path.exists(manifestpath):
                extra_assets_dirs_dict[subpath] = True
    if envval := os.getenv(AssetManager.EXTRA_ASSETS_ENV, None):
      for s in envval.split(os.pathsep):
        realpath = os.path.realpath(s)
        if os.path.isdir(realpath):
          extra_assets_dirs_dict[realpath] = True
    for d in extra_assets_dirs_dict.keys():
      self.try_load_extra_assets(d)

  def try_load_extra_assets(self, path : str):
    if not os.path.isdir(path):
      return
    manifest_yml_path = os.path.join(path, AssetManager.MANIFEST_SRC_NAME)
    if not os.path.exists(manifest_yml_path):
      return
    manifest_mtime = os.path.getmtime(manifest_yml_path)
    # 尝试读取现有的 manifest.pickle，一切顺利的话直接返回
    install_dir = AssetManager.get_extra_asset_install_path(path)
    if os.path.isdir(install_dir):
      manifest_pickle_path = os.path.join(install_dir, AssetManager.MANIFEST_NAME)
      if os.path.exists(manifest_pickle_path):
        if os.path.getmtime(manifest_pickle_path) >= manifest_mtime:
          with open(manifest_pickle_path, "rb") as f:
            manifest = pickle.load(f)
            res = self._handle_manifest(manifest, install_dir, isbuiltin=False)
            if res:
              return
    # 读取 preppipe_asset_manifest.yml 并构建素材包
    self.build_assets_extra(path)

  @staticmethod
  def lookup_asset_class(classid : str) -> type:
    if handle_class := _registered_asset_classes.get(classid, None):
      return handle_class
    raise PPInternalError(f"Asset class {classid} not found")

  @staticmethod
  def get_asset_name(relpath : str, install_base : str) -> str:
    # 由于我们有大量的文件名、内部ID名需要从素材名称中生成，我们在这里统一生成符合任意语言、环境的ID要求的名字
    if install_base == AssetManager.get_embedded_asset_install_path():
      rawname = os.path.splitext(relpath)[0]
    else:
      rawname = os.path.splitext(os.path.join(install_base, relpath))[0]
    return str2identifier(rawname)

  def _add_asset_info(self, name : str, installpath : str, handle_class : type, handle : typing.Any | None = None):
    if name in self._assets:
      raise PPInternalError(f"Asset {name} already exists (first path: {self._assets[name].installpath}, second path: {installpath})")
    self._assets[name] = AssetManager.AssetPackInfo(installpath=installpath, handle_class=handle_class, handle=handle)

  def _handle_manifest(self, manifest : AssetManifestObject, install_base : str, isbuiltin : bool = False) -> bool:
    if not isinstance(manifest, AssetManifestObject):
      if isbuiltin:
        raise PPInternalError("Builtin asset manifest is not an instance of AssetManifestObject")
      else:
        return False
    if manifest.program_version != __version__:
      if isbuiltin:
        raise PPInternalError(f"Asset manifest version mismatch: expected {__version__}, got {manifest.program_version}")
      else:
        return False
    for classid, path_list in manifest.items_by_class.items():
      handle_class = AssetManager.lookup_asset_class(classid)
      for relpath in path_list:
        name = AssetManager.get_asset_name(relpath, install_base)
        installpath = os.path.join(install_base, relpath)
        self._add_asset_info(name, installpath, handle_class)
    for classid, descriptor_list in manifest.descriptors.items():
      handle_class = AssetManager.lookup_asset_class(classid)
      handle_class.load_descriptors(descriptor_list)
    return True

  def _load_asset(self, info : AssetPackInfo):
    if info.handle is None:
      asset_srcpath = info.installpath
      if os.path.exists(asset_srcpath):
        info.handle = info.handle_class.create_from_asset_archive(asset_srcpath)

  def load_all_assets(self):
    for name, info in self._assets.items():
      if info.handle is None:
        self._load_asset(info)

  def get_assets_json(self) -> dict:
    result_dict = {}
    missing_assets_list : list[str] = []
    for name, info in self._assets.items():
      if info.handle is not None:
        result_dict[name] = info.handle.dump_asset_info_json(name=name)
      else:
        missing_assets_list.append(info.installpath)
    if len(missing_assets_list) > 0:
      result_dict["MISSING"] = missing_assets_list
    return result_dict

  def get_asset(self, name : str) -> typing.Any | None:
    if info := self._assets.get(name, None):
      if info.handle is None:
        self._load_asset(info)
      return info.handle
    return None

  def get_asset_noload(self, name : str) -> typing.Any | None:
    # 获取素材，但不加载；用于在多线程环境下获取素材的句柄
    if info := self._assets.get(name, None):
      return info.handle
    return None

  @staticmethod
  def get_instance() -> "AssetManager":
    # 获取 AssetManager 的单例
    if AssetManager._instance is None:
      AssetManager._instance = AssetManager()
    return AssetManager._instance

  @staticmethod
  def get_embedded_asset_install_path():
    """Get the absolute path of "preppipe/assets/_install" directory"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "_install")

  @staticmethod
  def get_extra_asset_install_path(path : str):
    d, b = os.path.split(path)
    return os.path.join(d, AssetManager.EXTRA_ASSETS_BUILD_DIR_PARENT, b)

  _tr_build_start = TR_assetmanager.tr("build_start",
    en="Start building assets from {srcpath} ({num} in total)",
    zh_cn="开始从 {srcpath} 构建素材包（共 {num} 个）",
    zh_hk="開始從 {srcpath} 構建素材包（共 {num} 個）",
  )
  _tr_build_item = TR_assetmanager.tr("build_item",
    en="({index}/{num}) Building asset {installpath}",
    zh_cn="({index}/{num})正在构建素材 {installpath}",
    zh_hk="({index}/{num})正在構建素材 {installpath}",
  )
  _tr_build_finish = TR_assetmanager.tr("build_finish",
    en="{srcpath}: asset build complete",
    zh_cn="{srcpath}: 素材包构建完成",
    zh_hk="{srcpath}: 素材包構建完成",
  )

  def build_assets_impl(self, srcpath : str, install_base : str, manifest : dict[str, dict[str, dict[str, typing.Any]]]):
    if not os.path.isdir(install_base):
      os.makedirs(install_base, exist_ok=True)
    num_total_assets = sum(len(v) for v in manifest.values())
    asset_index = 0
    descriptors : dict[str, list[typing.Any]] = {}
    items_by_class : dict[str, list[str]] = {}
    MessageHandler.info(AssetManager._tr_build_start.format(srcpath=srcpath, num=str(num_total_assets)))
    for classid, class_manifest in manifest.items():
      handle_class = _registered_asset_classes.get(classid, None)
      if handle_class is None:
        raise PPInternalError(f"Asset class {classid} not found")
      class_items = []
      items_by_class[classid] = class_items
      for relpath, buildargs in class_manifest.items():
        class_items.append(relpath)
        name = AssetManager.get_asset_name(relpath, install_base)
        converted_args = {}
        for k, v in buildargs.items():
          if isinstance(v, str):
            converted_args[k] = v.format(srcpath=srcpath)
          else:
            converted_args[k] = v
        installpath = os.path.join(install_base, relpath)
        install_parent = os.path.dirname(installpath)
        if not os.path.isdir(install_parent):
          os.makedirs(install_parent, exist_ok=True)
        asset_index += 1
        MessageHandler.info(AssetManager._tr_build_item.format(index=str(asset_index), num=str(num_total_assets), installpath=installpath))
        descriptor = handle_class.build_asset_archive(name=name, destpath=installpath, **converted_args)
        self._add_asset_info(name, installpath, handle_class, None)
        if descriptor is not None:
          if classid not in descriptors:
            descriptors[classid] = []
          descriptors[classid].append(descriptor)
          if not hasattr(handle_class, "load_descriptors"):
            raise PPInternalError(f"Asset class {classid} does not have a load_descriptors method while returning a manifest object")
    MessageHandler.info(AssetManager._tr_build_finish.format(srcpath=srcpath))
    manifestpath = os.path.join(install_base, AssetManager.MANIFEST_NAME)
    manifestobj = AssetManifestObject(program_version=__version__, descriptors=descriptors, items_by_class=items_by_class)
    with open(manifestpath, "wb") as f:
      pickle.dump(manifestobj, f, protocol=pickle.HIGHEST_PROTOCOL)

  _tr_asset_dir_not_found = TR_assetmanager.tr("asset_dir_not_found",
    en="Asset directory {path} not found",
    zh_cn="素材目录 {path} 不存在",
    zh_hk="素材目錄 {path} 不存在",
  )
  _tr_asset_dir_no_manifest = TR_assetmanager.tr("asset_dir_no_manifest",
    en="Asset directory {path} does not contain file {manifest_name}",
    zh_cn="素材目录 {path} 中没有找到文件 {manifest_name}",
    zh_hk="素材目錄 {path} 中沒有找到文件 {manifest_name}",
  )
  _tr_asset_dir_invalid_manifest = TR_assetmanager.tr("asset_dir_invalid_manifest",
    en="Asset directory {path} contains an invalid manifest file {manifest_name}",
    zh_cn="素材目录 {path} 中包含一个无效的清单文件 {manifest_name}",
    zh_hk="素材目錄 {path} 中包含一個無效的清單文件 {manifest_name}",
  )
  _tr_asset_duplicate = TR_assetmanager.tr("asset_duplicate",
    en="Asset directory {path} contains conflicting declarations of asset {name}",
    zh_cn="素材目录 {path} 中，素材 {name} 被声明不止一次且有冲突",
    zh_hk="素材目錄 {path} 中，素材 {name} 被聲明不止一次且有衝突",
  )

  @staticmethod
  def read_manifest_src(srcpath : str) -> dict[str, dict[str, dict[str, typing.Any]]]:
    # 我们从 srcpath 中读取 preppipe_asset_manifest.yml 文件，返回一个展开的字典： <资源包相对路径> -> <构建参数>
    # 这个 yaml 文件可以有以下内容：
    # 1. 用于描述素材包和构建所需的参数:
    # <classid>:
    #   <asset_name>:
    #     <param_name>: <param_value>
    #     ...
    # 2. 用于引用其他 yaml 文件:
    # subdirs:
    #   - <subdir1>/<subdir1_manifest.yml>
    #   ...
    # 这样的话，我们会递归地读取所有的子目录的 manifest 文件，并将它们合并到一个字典中
    # 子目录中的 manifest 使用的相对路径是基于 manifest 文件的，在合并结果时，我们需要调整这些相对路径
    if not os.path.isdir(srcpath):
      raise PPInvalidOperationError(AssetManager._tr_asset_dir_not_found.format(path=srcpath))
    manifest_src_path = os.path.join(srcpath, AssetManager.MANIFEST_SRC_NAME)
    if not os.path.exists(manifest_src_path):
      raise PPInvalidOperationError(AssetManager._tr_asset_dir_no_manifest.format(path=srcpath, manifest_name=AssetManager.MANIFEST_SRC_NAME))
    def handle_subdirs_recursive(result : dict[str, dict[str, dict[str, typing.Any]]], d : dict, curdir : str):
      # d 是当前目录中 manifest 文件的内容，我们需要将其合并到 result 中
      # 如果这是最顶层，则 curdir 为空字符串，否则这应该是从顶层的相对路径
      # curdir 非空的话，构建参数中的所有 {srcpath} 应该被替换为 {srcpath}/curdir
      for k, v in d.items():
        if k == "subdirs":
          continue
        if k in result:
          classdict = result[k]
        else:
          classdict = {}
          result[k] = classdict
        for filename, buildargs in v.items():
          if curdir == "":
            converted_filename = filename
            converted_buildargs = buildargs
          else:
            converted_filename = os.path.join(curdir, filename)
            converted_buildargs = {}
            newsrcpath = os.path.join("{srcpath}", curdir)
            for k2, v2 in buildargs.items():
              if isinstance(v2, str):
                converted_buildargs[k2] = v2.format(srcpath=newsrcpath)
              else:
                converted_buildargs[k2] = v2
          if converted_filename in classdict and classdict[converted_filename] != converted_buildargs:
            raise PPInvalidOperationError(AssetManager._tr_asset_duplicate.format(path=srcpath, name=converted_filename))
          classdict[converted_filename] = converted_buildargs
        result[k]
      subdirs = d.get("subdirs", [])
      if len(subdirs) == 0:
        return
      for subdir_manifest in subdirs:
        subdir, filename = os.path.split(subdir_manifest)
        fullsubdirpath = subdir if curdir == "" else os.path.join(curdir, subdir)
        manifest_fullpath = os.path.join(srcpath, fullsubdirpath, filename)
        with open(manifest_fullpath, "r", encoding="utf-8") as f:
          try:
            subdir_manifest_content = yaml.safe_load(f)
            if not isinstance(subdir_manifest_content, dict):
              raise RuntimeError("Top-level object is not a dictionary")
            handle_subdirs_recursive(result, subdir_manifest_content, fullsubdirpath)
          except Exception as e:
            raise PPInvalidOperationError(AssetManager._tr_asset_dir_invalid_manifest.format(path=srcpath, manifest_name=os.path.join(fullsubdirpath, filename)) + ": " + str(e)) from e
    with open(manifest_src_path, "r", encoding="utf-8") as f:
      try:
        manifest_src = yaml.safe_load(f)
        if not isinstance(manifest_src, dict):
          raise RuntimeError("Top-level object is not a dictionary")
      except Exception as e:
        raise PPInvalidOperationError(AssetManager._tr_asset_dir_invalid_manifest.format(path=srcpath, manifest_name=AssetManager.MANIFEST_SRC_NAME) + ": " + str(e)) from e
    result : dict[str, dict[str, dict[str, typing.Any]]] = {}
    handle_subdirs_recursive(result, manifest_src, "")
    return result

  def build_assets_embedded(self, srcpath : str):
    manifest_src = AssetManager.read_manifest_src(srcpath)
    install_base = AssetManager.get_embedded_asset_install_path()
    self.build_assets_impl(srcpath, install_base, manifest_src)
    for ref in AssetManager.ASSETREF_CHECKLIST:
      if ref not in self._assets:
        raise PPInternalError(f"Embedded asset {ref} not found in manifest")

  def build_assets_extra(self, srcpath : str):
    manifest_src = AssetManager.read_manifest_src(srcpath)
    install_base = AssetManager.get_extra_asset_install_path(srcpath)
    self.build_assets_impl(srcpath, install_base, manifest_src)

  @staticmethod
  def init():
    AssetManager.get_instance()

  @staticmethod
  def init_nomanifest():
    # 我们使用 AssetManager 的工具入口时，不能加载 manifest，
    # 万一要构建资源包的话 manifest 的构建过程可能会与已载入的产生冲突
    assert AssetManager._instance is None
    AssetManager._instance = AssetManager(load_manifest=False)

  @staticmethod
  def tool_main(args : list[str] | None = None):
    # 创建一个有以下参数的 argument parser: [--debug] [--create <yml> | --load <zip>] [--save <zip>] [--fork [args]] [--export <dir>]
    AssetManager.init_nomanifest()
    parser = argparse.ArgumentParser(description="Asset Management Tool")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--build-embedded", metavar="<dir>", help="Build the embedded asset pack from the specified directory")
    parser.add_argument("--build-extra", metavar="<dir>", nargs="*", help="Build the extra asset pack from the specified directory")
    parser.add_argument("--dump-json", action="store_true", help="Dump all asset info as a JSON string")
    if args is None:
      args = sys.argv[1:]
    parsed_args = parser.parse_args(args)

    if parsed_args.debug:
      AssetManager._debug = True
    if parsed_args.build_embedded is not None or parsed_args.build_extra is not None:
      if parsed_args.build_embedded is not None:
        AssetManager.get_instance().build_assets_embedded(parsed_args.build_embedded)
      if parsed_args.build_extra is not None:
        for p in parsed_args.build_extra:
          AssetManager.get_instance().build_assets_extra(p)
    else:
      AssetManager.get_instance().try_load_manifest()
    if parsed_args.dump_json:
      inst = AssetManager.get_instance()
      inst.load_all_assets()
      print(json.dumps(inst.get_assets_json(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
  raise PPNotImplementedError('Please invoke assetmanager_cmd instead')