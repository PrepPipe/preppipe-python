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
#

##
# @file preppipe/inputmodel.py
# @~english @brief See preppipe.inputmodel for documentation
# @~chinese @brief 请从 preppipe.inputmodel 查看文档
# @~

from tabnanny import check
import typing
import PIL.Image
import importlib
import hashlib
import enum

from .commontypes import *

class IMBase:
  # support for using objects as key in dictionary / in set
  def __hash__(self) -> int:
    return hash(id(self))
  
  def __eq__(self, __o: object) -> bool:
    return __o is self

class IMElement(IMBase):
  pass

class IMAssetReference(IMElement):
  _symbol_entry : object # IMAssetSymbolEntry declared below
  
  def __init__(self, symbol_entry : object):
    # should only be created by calling IMAssetSymbolEntry.get_reference()
    super().__init__()
    assert isinstance(symbol_entry, IMAssetSymbolEntry)
    self._symbol_entry = symbol_entry
    symbol_entry.add_reference(self)
  
  def get_symbol_entry(self):
    return self._symbol_entry


class IMAssetSymbolEntry(IMBase):
  # this belongs to InputModel's asset symbol table only
  asset : AssetBase
  relpath : str
  references : typing.List[IMAssetReference]
  
  def __init__(self, asset : AssetBase, relpath : str = ""):
    self.asset = asset
    self.relpath = relpath
    self.references = []
  
  def add_reference(self, ref : IMAssetReference) -> None:
    assert ref not in self.references
    self.references.append(ref)


class IMTextElement(IMElement):
  styles: TextAttribute
  text : str

class IMImageElement(IMAssetReference):
  # TODO add additional metadata
  def __init__(self, symbol_entry : IMAssetSymbolEntry) -> None:
    super().__init__(symbol_entry)
    # TODO add metadata

class IMBlock(IMBase):
  """!
  @~english @brief Base class for all block level constructs
  @~chinese @brief 所有区块类的基类
  @~
  
  123
  """
  def __init__(self) -> None:
    pass

class IMBlockList:
  # one or more blocks; like a document but does not create scope
  blocks: typing.List[IMBlock]

class IMSpecialParagraphType(enum.Enum):
  Regular = 0
  Quote = enum.auto() # treated as assets
  Code = enum.auto() # treated as assets; probably lowered to a text displayable centered on the screen

class IMParagraphBlock(IMBlock):
  paragraph_type : IMSpecialParagraphType
  element_list : typing.List[IMElement]

class IMCommandInput:
  positional_args = typing.List[IMElement]
  keyword_args = typing.Dict[str, IMElement]

class IMCommandBlock(IMBlock):
  arguments : IMCommandInput
  attributes : typing.Dict[str, IMCommandInput]

class IMStructureItem:
  # an item in a list or a cell in a table
  header : IMBlock # first line after the item mark / in the cell. we only use this part to create summary.
  children : IMBlockList # additional stuff (probably paragraphs) that comes after the the list item.

class IMListBlock(IMBlock):
  # the content may be commands or normal text; context dependent
  is_item_numbered : bool
  list_level : int # from 0 (outermost) to +inf
  item_list : typing.List[IMStructureItem]

class IMTableBlock(IMBlock):
  table_cells: typing.List[typing.List[IMStructureItem]]

class IMDocument(IMBlockList):
  local_options: typing.Dict[str, typing.Any]


class InputModel(IMBase):
  global_options: typing.Dict[str, typing.Any]
  fileset: typing.Dict[str, IMDocument]
  asset_symbol_table : typing.List[IMAssetSymbolEntry]
  asset_path_dict : typing.Dict[str, IMAssetReference]
  
  # in the input model, we have not yet resolved any "asset name"; assets are only referenced by path
  # asset_path_dict maps from asset path to the concrete asset symbol entry (for the ones with backing store only)
  # we ensure that all files can be referenced starting from a common base path, specified by the config / command line
  # (which means no need to remap out-of-tree asset directories to in-tree ones; out-of-tree assets are imported as if they are in-tree. users use in-tree path only)
  # if we have path/to/file1.xxx, if there is no other file with the same basename in that directory, then we will have two entries in the asset_path_dict:
  # path/to/file1.xxx -> ref
  # path/to/file1     -> ref
  # however, if we have path/to/file1.yyy as well, then we only
  
  
  def __init__(self) -> None:
    self.global_options = {}
    self.fileset = {}
    self.asset_symbol_table = []
    self.asset_path_dict = {}

class InputModelBuilder:
  result : InputModel
  hash_algorithm : str
  asset_uniquing_dict_hash = typing.Dict[bytes, IMAssetReference]
  asset_uniquing_dict_storepath = typing.Dict[str, IMAssetReference]
  
  # when we build the input model, we use (absolute) "path" for uniquing assets. We assume assets do not change during building.
  # after the input model is built, assets can be referenced by "name", which is a relative or absolute path at this moment

  def __init__(self, hash_algorithm : str = "sha512") -> None:
    self.result = InputModel()
    self.hash_algorithm = hash_algorithm
    self.asset_uniquing_dict_hash = {}
    self.asset_uniquing_dict_storepath = {}
  
  def get_asset_entry_from_path(self, path : str) -> IMAssetSymbolEntry:
    assert path 

  
  class AssetInfo:
    # one for each asset
    asset : IMAssetSymbolEntry
    checksum: bytes
    name : str
    
    def __init__(self, asset : AssetBase, checksum : bytes, name : str = "") -> None:
      self.asset = asset
      self.checksum = checksum
      self.name = name
      
  result : InputModel
  assets_data : typing.List[AssetInfo]
  anonymous_asset_uniquing_dict : typing.Dict[bytes, int] # key is a hash of asset; we may change the hash algorithm later on
  stored_asset_uniquing_dict : typing.Dict[str, int] # backing store file absolute path -> index
  hash_algorithm : str
  
  def __init__(self, hash_algorithm : str = "sha512") -> None:
    self.result = InputModel()
    self.assets_data = []
    self.anonymous_asset_uniquing_dict = {}
    self.hash_algorithm = hash_algorithm
  
  def get_hash(self, snapshot : bytes) -> bytes:
    hasher = hashlib.new(self.hash_algorithm)
    hasher.update(snapshot)
    return hasher.digest()
  
  def try_get_asset_info(self, *, store_path : str = "", checksum : bytes = None) -> AssetInfo:
    if len(store_path) > 0:
      # search for duplicates according to store path
      if store_path in self.stored_asset_uniquing_dict:
        return self.assets_data[self.stored_asset_uniquing_dict[store_path]]
      return None
    
    if checksum in self.anonymous_asset_uniquing_dict:
      return self.assets_data[self.anonymous_asset_uniquing_dict[checksum]]
    return None
    
  def add_asset(self, asset : AssetBase, name : str) -> None:
    # the caller must ensure the asset is not duplicated
    # step 1: try to prove no duplicates
    
    store_path = asset.get_backing_store_path()
    snapshot = asset.get_snapshot()
    checksum = self.get_hash(snapshot)
    asset_info = self.try_get_asset_info(store_path = store_path, checksum = checksum)
    if asset_info is None:
      # simplest case, no possible duplication
      # just register and done
      asset_index = len(self.assets_data)
      # asset_info = AssetInfo(asset, checksum, name)
      
      
    pass
    