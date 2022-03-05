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

# from tabnanny import check
# from tkinter.font import names
import typing
import PIL.Image
import importlib
import hashlib
import enum

from .commontypes import *

class IMAttribute:
  # support for using objects as key in dictionary / in set
  def __hash__(self) -> int:
    return hash(id(self))
  
  def __eq__(self, __o: object) -> bool:
    return __o is self
  
  # get the name of attributes
  def get_name() -> str:
    return ""
  
  def to_string(self, indent : int) -> str:
    return "<" + type(self).__name__ + ">"
  
  def __str__(self) -> str:
    return self.to_string(0)

class IMBase:
  # attributes
  _attributes : typing.List[IMAttribute]
  
  def __init__(self) -> None:
    self._attributes = []
    
  @property
  def attributes(self):
    return self._attributes
  
  def add_attribute(self, attr : IMAttribute):
    self._attributes.append(attr)
  
  def get_attribute(self, attribute_name : str) -> IMAttribute:
    for attr in self._attributes:
      if attr.get_name() == attribute_name:
        return attr
    return None
  
  def to_string(self, indent : int) -> str:
    result = "<" + type(self).__name__
    for attr in self.attributes:
      result += " " + attr.to_string(indent)
    result += ">"
    return result
  
  def get_attribute_list_string(self):
    return " ".join([attr.to_string(0) for attr in self.attributes])
  
  def __str__(self) -> str:
    return self.to_string(0)
  
  def __str__(self) -> str:
    return self.to_string(0)
  
  # support for using objects as key in dictionary / in set
  def __hash__(self) -> int:
    return hash(id(self))
  
  def __eq__(self, __o: object) -> bool:
    return __o is self

class IMElement(IMBase):
  def __init__(self) -> None:
    super().__init__()

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

  def to_string(self, indent : int) -> str:
    result = type(self).__name__
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    result += " -> " + self._symbol_entry.to_string(indent)
    return result

class IMAssetSymbolEntry(IMBase):
  # this belongs to InputModel's asset symbol table only
  asset : AssetBase
  relpath : str # path relative to the root of the namespace
  references : typing.List[IMAssetReference] # references to this entry
  
  def __init__(self, asset : AssetBase, relpath : str = ""):
    super().__init__()
    self.asset = asset
    self.relpath = relpath
    self.references = []
  
  def add_reference(self, ref : IMAssetReference) -> None:
    assert ref not in self.references
    self.references.append(ref)

  def to_string(self, indent : int) -> str:
    result = "IMAssetSymbolEntry "
    if self.asset is None:
      result += "<invalid>"
    else:
      result += str(id(self.asset))
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    if len(self.relpath) > 0:
      result += " at " + self.relpath
    return result

class IMTextElement(IMElement):
  styles: typing.Any
  text : str
  
  def __init__(self, text : str, styles : typing.Any = None) -> None:
    super().__init__()
    self.text = text
    self.styles = styles
  
  def to_string(self, indent : int) -> str:
    result = "Text(\"" + self.text + "\""
    if self.styles is not None:
      result += ", style: " + str(self.styles)
    result += ")"
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    return result

class IMImageElement(IMAssetReference):
  # TODO add additional metadata
  def __init__(self, symbol_entry : IMAssetSymbolEntry) -> None:
    super().__init__(symbol_entry)
    # TODO add metadata

class IMFrameDefinitionElement(IMElement):
  def __init__(self, frame) -> None:
    super().__init__()
    self.frame = frame
  
  def to_string(self, indent : int) -> str:
    result = "FrameDefinition"
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    result += " -> " + self.frame.to_string(indent)
    return result

class IMBlock(IMBase):
  """!
  @~english @brief Base class for all block level constructs
  @~chinese @brief 所有区块类的基类
  @~
  
  123
  """
  def __init__(self) -> None:
    super().__init__()

class IMFrame(IMBase):
  # one or more blocks; like a document but does not create (option, asset, ...) scope
  blocks: typing.List[IMBlock]
  
  def __init__(self) -> None:
    super().__init__()
    self.blocks = []
  
  def add_block(self, block : IMBlock):
    self.blocks.append(block)
  
  def to_string(self, indent : int) -> str:
    result = type(self).__name__
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    for b in self.blocks:
      result += "\n" + "  "*(indent+1) + b.to_string(indent+1)
    return result

class IMSpecialParagraphType(enum.Enum):
  Regular = 0
  Quote = enum.auto() # treated as assets
  Code = enum.auto() # treated as assets; probably lowered to a text displayable centered on the screen

class IMParagraphBlock(IMBlock):
  paragraph_type : IMSpecialParagraphType
  element_list : typing.List[IMElement]
  
  def __init__(self) -> None:
    super().__init__()
    self.paragraph_type = IMSpecialParagraphType.Regular
    self.element_list = []
  
  def add_element(self, element : IMElement):
    self.element_list.append(element)
    
  def to_string(self, indent : int) -> str:
    result = "Paragraph"
    if self.paragraph_type != IMSpecialParagraphType.Regular:
      result += "(" + str(self.paragraph_type) + ")"
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    for e in self.element_list:
      result += "\n" + "  "*(indent+1) + e.to_string(indent+1)
    return result

class IMCommandInput(IMBase):
  positional_args = typing.List[IMElement]
  keyword_args = typing.Dict[str, IMElement]

class IMCommandBlock(IMBlock):
  arguments : IMCommandInput
  attributes : typing.Dict[str, IMCommandInput]

class IMStructureItem(IMBase):
  # an item in a list or a cell in a table
  header : IMBlock # first line after the item mark / in the cell. we only use this part to create summary.
  children : IMFrame # additional stuff (probably paragraphs) that comes after the the list item.

class IMListBlock(IMBlock):
  # the content may be commands or normal text; context dependent
  is_item_numbered : bool
  list_level : int # from 0 (outermost) to +inf
  item_list : typing.List[IMStructureItem]

class IMTableBlock(IMBlock):
  table_cells: typing.List[typing.List[IMStructureItem]]

class IMDocument(IMFrame):
  local_options: typing.Dict[str, typing.Any]

class IMNamespace(IMBase):
  # namespace: stand-alone package; only the global namespace (namespace = []) and parent namespace (namespace list is a substring) is always present.
  # InputModel cannot assume other namespace-d assets are always available.
  namespace: typing.List[str]
  options: typing.Dict[str, typing.Any] # parsed from preppipe.json
  fileset: typing.Dict[str, IMDocument]
  asset_symbol_table : typing.List[IMAssetSymbolEntry]
  asset_path_dict : typing.Dict[str, IMAssetReference]
  asset_basepath_dict : typing.Dict[str, typing.List[str]]
  invalid_asset_entry : IMAssetSymbolEntry # used to keep track of invalid entries
  # in the input model, we have not yet resolved any "asset name"; assets are only referenced by path
  # asset_path_dict maps from asset path to the concrete asset symbol entry (for the ones with backing store only)
  # we ensure that all files can be referenced by <namespace> + <path>
  # no "out-of-tree" asset; they are either remapped to in-tree path or is a separate namespace
  # for each file like path/to/file1.xxx:
  # asset_path_dict['path/to/file1.xxx'] = <Asset>
  # asset_basepath_dict['path/to/file1'] = ['xxx']
  # if there is also path/to/file1.yyy, then
  # asset_path_dict['path/to/file1.xxx'] = <Asset>
  # asset_path_dict['path/to/file1.yyy'] = <Asset>
  # asset_basepath_dict['path/to/file1'] = ['xxx', 'yyy']
  # anonymous assets have empty path and does not have entries in asset_path_dict
  
  def __init__(self, namespace : typing.List[str]) -> None:
    self.namespace = namespace
    self.options = {}
    self.fileset = {}
    self.asset_symbol_table = []
    self.asset_path_dict = {}
    self.asset_basepath_dict = {}
    self.invalid_asset_entry = IMAssetSymbolEntry(None, "")
    
  def get_image_asset_entry_from_path(self, imagePath : str, mimetype : str) -> IMAssetSymbolEntry:
    # TODO
    return self.invalid_asset_entry
  
  def get_image_asset_entry_from_inlinedata(self, data : bytes, mimetype : str, localname : str) -> IMAssetSymbolEntry:
    # TODO
    return self.invalid_asset_entry

class InputModel(IMBase):
  global_options: typing.Dict[str, typing.Any]
  namespaces : typing.Dict[typing.List[str], IMNamespace]
  
  def __init__(self) -> None:
    self.global_options = {}
    self.namespaces = {}

class IMNamespaceBuilder:
  _hash_algorithm : typing.ClassVar[str] = "sha512"
  
  @staticmethod
  def set_hash_algorithm(algorithm : str):
    IMNamespaceBuilder._hash_algorithm = algorithm
  
  @staticmethod
  def get_hash(snapshot : bytes) -> bytes:
    hasher = hashlib.new(IMNamespaceBuilder._hash_algorithm)
    hasher.update(snapshot)
    return hasher.digest()
  
  # we use preppipe.json as configuration file format
  # we may even use this function outside building IMNamespace, e.g. parse the global options
  @staticmethod
  def parse_configuration_file(f) -> typing.Dict[str, typing.Any]:
    pass
  
  # ============================================================================
  class AssetInfo:
    # one for each asset
    asset : IMAssetSymbolEntry
    checksum: bytes
    name : str
    
    def __init__(self, asset : AssetBase, checksum : bytes, name : str = "") -> None:
      self.asset = asset
      self.checksum = checksum
      self.name = name
  
  _result: IMNamespace
  _assets_data : typing.List[AssetInfo]
  _anonymous_asset_uniquing_dict : typing.Dict[bytes, int] # key is a hash of asset; we may change the hash algorithm later on
  _stored_asset_uniquing_dict : typing.Dict[str, int] # backing store file absolute path -> index
  
  # when we build namespaces, we use (absolute) "path" for uniquing assets. We assume assets do not change during building.
  # after the input model is built, assets can be referenced by "name", which is a relative or absolute path at this moment
  
  def get_result(self) -> IMNamespace:
    pass
  
  def get_asset_entry_from_path(self, path : str) -> IMAssetSymbolEntry:
    assert path 
  
  def __init__(self) -> None:
    self._result = IMNamespace()
    self._assets_data = []
    self._anonymous_asset_uniquing_dict = {}
    self._stored_asset_uniquing_dict = {}
  
  def try_get_asset_info(self, *, store_path : str = "", checksum : bytes = None) -> AssetInfo:
    # TODO To be updated
    if len(store_path) > 0:
      # search for duplicates according to store path
      if store_path in self.stored_asset_uniquing_dict:
        return self.assets_data[self.stored_asset_uniquing_dict[store_path]]
      return None
    
    if checksum in self.anonymous_asset_uniquing_dict:
      return self.assets_data[self.anonymous_asset_uniquing_dict[checksum]]
    return None
    
  def add_asset(self, asset : AssetBase, name : str) -> None:
    # TODO To be updated
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
    