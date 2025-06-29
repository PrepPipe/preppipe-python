# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import dataclasses
import shutil
import typing
from ..language import *
from ..exceptions import *

# 语涵编译器需要一些内嵌的素材，这些素材需要与程序本体一起分发。
# 但是部分素材的体积较大，在分发时不适合直接放在程序包中。
# 为了解决这个问题，我们使用了一种类似于工具的注册机制，将素材的处理方法注册到主程序中。
# 该文件定义支持自动注册素材处理类的修饰符
# 详细说明请见 AssetManager 类的文档

# 注册的类应该有以下成员：
# 1.  一个静态方法 create_from_asset_archive(path : str) -> AssetClass
#     该方法用于从素材包中创建一个素材处理类的实例
# 2.  一个静态方法 build_asset_archive(name : str, destpath : str, **kwargs) -> typing.Any
#     该方法用于构建一个素材包，kwargs 可以是任意的构建参数，这些参数会保存在 AssetManager 的 Manifest 中
#     如果该类需要类似 Manifest 的内容（比如用于在其他部分引用这些资源），则可返回一个任意可以 pickle 的对象
# 3.  一个成员函数 dump_asset_info_json(self, name : str) -> dict
#     该方法用于将素材的信息导出为一个 JSON 对象，将作为 AssetManager 的 dump 输出的一部分
# 4.  (可选) 一个静态方法 load_descriptors(descriptors : list[typing.Any]) -> None
#     该方法用于从 AssetManager 的 Manifest 中加载素材的信息，列表中的对象均为 build_asset_archive 的返回值
#     如果 build_asset_archive 只返回 None，则不需要提供该方法

_registered_asset_classes : dict[str, type] = {}

def AssetClassDecl(name : str): # pylint: disable=invalid-name
  def decorator(cls):
    assert name not in _registered_asset_classes, f"Duplicate asset class name {name}"
    # 确认该类有一个叫 create_from_asset_archive(path : str) 的静态方法，用于从素材包中创建一个素材处理类的实例
    assert hasattr(cls, "create_from_asset_archive"), f"Asset class {name} must have a static method create_from_asset_archive(path : str)"
    # 确认该类有一个叫 build_asset_archive(name : str, destpath : str, **kwargs) 的静态方法，用于创建素材包
    assert hasattr(cls, "build_asset_archive"), f"Asset class {name} must have a static method build_asset_archive(name : str, destpath : str, **kwargs)"
    # 确认该类有一个叫 dump_asset_info_json(self, name : str) 的成员方法，可以从素材处理类中获取详细信息
    assert hasattr(cls, "dump_asset_info_json"), f"Asset class {name} must have a member method dump_asset_info_json(self, name : str)"
    _registered_asset_classes[name] = cls
    return cls
  return decorator

# 如果注册的类符合以下条件，则可以继承自 NamedAssetClassBase:
# 1. 每个素材有一个可以引用的、可翻译（有 Translatable）的名称
# 2. 每个素材的使用方式（包括名称）都可由一个对象记录（姑且称之为描述对象），且这类对象足够小、可以始终和程序一起分发
# 3. 注册类的 build_asset_archive 方法返回的对象可以被用于创建描述对象
class NamedAssetClassBase:
  # 继承的类需要定义以下成员：
  DESCRIPTOR_TYPE : typing.ClassVar[type] # 描述对象(记录素材使用方式和名称等信息的对象)的实际类型
  MANIFEST : typing.ClassVar[dict[str, typing.Any]] # 用于保存描述对象 (ID -> 描述对象)
  DESCRIPTOR_DICT : typing.ClassVar[TranslatableDict[list[typing.Any]]] # 用于保存描述对象的字典，键为描述对象的名称
  DESCRIPTOR_DICT_STRONLY : typing.ClassVar[dict[str, list[typing.Any]]] # 如果一些资源只使用固定名称、没有 Translatable 作为名称，则使用这个字典

  @classmethod
  def get_candidate_name(cls, descriptor : typing.Any) -> Translatable | str:
    # 从描述对象中获取素材的候选名称
    raise PPNotImplementedError()

  @classmethod
  def get_candidate_id(cls, descriptor : typing.Any) -> str:
    # 从描述对象中获取素材的 ID, 此项不允许有重名
    raise PPNotImplementedError()

  @classmethod
  def add_descriptor(cls, descriptor : typing.Any) -> None:
    name = cls.get_candidate_name(descriptor)
    identifier = cls.get_candidate_id(descriptor)
    if identifier in cls.MANIFEST:
      raise PPInternalError(f"Duplicate descriptor ID {identifier}")
    cls.MANIFEST[identifier] = descriptor
    if isinstance(name, Translatable):
      cls.DESCRIPTOR_DICT.get_or_create(name, list).append(descriptor)
    elif isinstance(name, str):
      if name not in cls.DESCRIPTOR_DICT_STRONLY:
        cls.DESCRIPTOR_DICT_STRONLY[name] = [descriptor]
      else:
        cls.DESCRIPTOR_DICT_STRONLY[name].append(descriptor)
    else:
      raise PPInternalError(f"Invalid name type {type(name)}")

  @classmethod
  def get_descriptor_candidates(cls, name : str) -> list[typing.Any]:
    candidates = []
    if name in cls.DESCRIPTOR_DICT:
      candidates.extend(cls.DESCRIPTOR_DICT[name])
    if name in cls.DESCRIPTOR_DICT_STRONLY:
      candidates.extend(cls.DESCRIPTOR_DICT_STRONLY[name])
    return candidates

  @classmethod
  def get_descriptor(cls, name : str) -> typing.Any | None:
    # 返回唯一的结果，如果不止一个则也视为没找到
    candidates = cls.get_descriptor_candidates(name)
    if len(candidates) == 1:
      return candidates[0]
    return None

  @classmethod
  def get_descriptor_by_id(cls, identifier : str) -> typing.Any | None:
    return cls.MANIFEST.get(identifier, None)

  @classmethod
  def get_candidate_names(cls) -> list[str]:
    f = lambda x : x.get() if isinstance(x, Translatable) else x
    return [f(cls.get_candidate_name(d)) for d in cls.MANIFEST.values()]

  @classmethod
  def load_descriptors(cls, descriptors: list[typing.Any]) -> None:
    # 载入描述对象，可能被调用不止一次
    for descriptor in descriptors:
      if not isinstance(descriptor, cls.DESCRIPTOR_TYPE):
        raise ValueError(f"Invalid descriptor type {type(descriptor)}")
      cls.add_descriptor(descriptor)

  @classmethod
  def _descriptor(cls, descriptor_type : type):
    # 大部分时候，我们想把描述对象的代码放在注册类的定义后面，但是这样会导致描述对象的类型无法在注册类定义时确定
    # 为了解决这个问题，我们提供了这个函数，可以用作加到描述对象类型上面的修饰符
    cls.DESCRIPTOR_TYPE = descriptor_type
    cls.MANIFEST = {}
    cls.DESCRIPTOR_DICT = TranslatableDict()
    cls.DESCRIPTOR_DICT_STRONLY = {}
    return descriptor_type

  @staticmethod
  def clear_directory_recursive(path : str) -> None:
    # 构建素材时经常会需要清空已有的目录，这是给子类的辅助函数
    if not os.path.isdir(path):
      raise FileNotFoundError(f"Directory {path} not found")
    for root, dirs, files in os.walk(path):
      for f in files:
        os.unlink(os.path.join(root, f))
      for d in dirs:
        shutil.rmtree(os.path.join(root, d))

@dataclasses.dataclass
class AssetDocsDumpInfo:
  base_path : str # 以下所有相对路径的起始路径
  base_path_ref : str # 当生成对保存的内容的引用（比如到共通部分）时，使用的起始路径（即导出的文件中应该使用 base_path_ref 来替代 base_path）
  common_export_path : str # 共通部分、语言无关内容（比如图片本体）的导出路径
  language_specific_docs : dict[str, str] # 语言相关内容的导出路径

class AssetDocsDumperBase:
  # 用于输出面向用户的文档 (Markdown, mkdocs)
  dumpinfo : AssetDocsDumpInfo
  _classdict : typing.ClassVar[dict[int, type]] = {}
  _TARGET_CLASS : typing.ClassVar[typing.Type[NamedAssetClassBase]]

  def __init__(self, dumpinfo : AssetDocsDumpInfo):
    self.dumpinfo = dumpinfo

  @classmethod
  def get_targeting_asset_class(cls) -> typing.Type[NamedAssetClassBase]:
    return cls._TARGET_CLASS

  def try_claim_asset(self, name : str, asset : NamedAssetClassBase) -> int:
    # 返回一个表示顺序的整数，如果不处理则返回 -1
    # 该整数应该表示某种优先级，越小越优先，我们也会给每个值输出一个标题
    # 如果需要处理，那么这个函数应该完成所有需要的准备工作，比如导出共通的部分
    return -1

  @classmethod
  def get_heading_for_type(cls) -> str:
    # 应该是某个 Translatable 的 .get() 结果
    raise PPNotImplementedError()

  @classmethod
  def get_heading_for_sort_order(cls, sort_order : int) -> str:
    # 应该是某个 Translatable 的 .get() 结果
    raise PPNotImplementedError()

  def dump(self, dest : typing.TextIO, name : str, asset : NamedAssetClassBase, sort_order : int) -> None:
    # 将一个素材的文档输出到目标文件
    # 这个函数可能会执行不止一次，有多少种语言输出就会执行多少次
    pass

  # 给子类用的函数
  @classmethod
  def refpath(cls, path : str) -> str:
    '''Replace backslashes with slashes in a path.'''
    return path.replace('\\', '/')

def AssetDocsDumperDecl(target : typing.Type[NamedAssetClassBase], sort_order : int | None = None): # pylint: disable=invalid-name
  def decorator(cls : typing.Type[AssetDocsDumperBase]):
    # pylint: disable=protected-access
    if not issubclass(cls, AssetDocsDumperBase):
      raise ValueError("AssetDocsDumperDecl can only be used on subclasses of AssetDocsDumperBase")
    cls._TARGET_CLASS = target
    sort_order_value = sort_order if sort_order is not None else len(AssetDocsDumperBase._classdict)
    if sort_order_value in AssetDocsDumperBase._classdict:
      raise ValueError(f"Duplicate sort order {sort_order_value}")
    AssetDocsDumperBase._classdict[sort_order_value] = cls
    return cls
  return decorator
