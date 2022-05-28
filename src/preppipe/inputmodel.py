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
  _debugloc : DebugLoc

  def __init__(self) -> None:
    self._attributes = []
    self._debugloc = None

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

  @property
  def debugloc(self):
    return self._debugloc

  @debugloc.setter
  def debugloc(self, loc : DebugLoc):
    self._debugloc = loc

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
  _asset : AssetBase
  
  # path relative to the root of the namespace (may be under remapped directory); participate in reference resolution later on
  _relative_path : str
  
  # absolute path (for debugging purpose)
  # if multiple files map to the same relative path (due to directory remapping), this field tells which one is selected
  _real_path : str
  
  # absolute path of anonymous asset
  # If an asset stays anonymous (only referenced inline and no file entry), this tells where (which doc, etc) does it come from
  _anonymous_path : str
  
  # hash of the asset; used for merging identical assets
  # algorithm depends on the parent namespace
  _checksum : bytes
  
  references : typing.List[IMAssetReference] # references to this entry
  
  def __init__(self, asset : AssetBase, checksum : bytes, relative_path : str = "", realpath : str = ""):
    super().__init__()
    self._asset = asset
    self._relative_path = relative_path
    self._real_path = realpath
    self._anonymous_path = ""
    self._checksum = checksum
    self.references = []
  
  @property
  def asset(self):
    return self._asset
  
  @property
  def relative_path(self):
    return self._relative_path
  
  @relative_path.setter
  def relative_path(self, relpath : str):
    # we should only initialize the relative path once
    assert self._relative_path == ""
    self._relative_path = relpath
  
  @property
  def real_path(self):
    return self._real_path
  
  @real_path.setter
  def real_path(self, realpath : str):
    # should only initialize once
    assert self._real_path == ""
    self._real_path = realpath
  
  @property
  def anonymous_path(self):
    return self._anonymous_path
  
  @anonymous_path.setter
  def anonymous_path(self, path : str):
    assert self._anonymous_path == ""
    self._anonymous_path = path
  
  @property
  def checksum(self):
    return self._checksum
  
  def add_reference(self, ref : IMAssetReference) -> None:
    assert ref not in self.references
    self.references.append(ref)
    
  def valid(self) -> bool:
    return self._asset is not None
  
  def get_mime_type(self) -> str:
    assert self.valid()
    return self._asset.get_mime_type()

  def to_string(self, indent : int) -> str:
    result = "IMAssetSymbolEntry "
    if self._asset is None:
      result += "<invalid>"
    else:
      result += hex(id(self._asset))
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    if len(self._relative_path) > 0:
      result += " at " + self._relative_path
      if len(self._real_path) > 0:
        # should only be non-empty when relative path is not empty
        result += " (" + self._real_path + ")"
    else:
      result += " from " + self._anonymous_path
    return result

class IMTextElement(IMElement):
  # element of a general text

  # declare styles as supporting typing.Any so that the code creating IMTextElement can use internal representation initially.
  # After parsing, all styles should be typing.Dict[TextAttribute, typing.Any]
  styles: typing.Dict[TextAttribute, typing.Any] | typing.Any
  text : str
  
  def __init__(self, text : str, styles : typing.Any = None) -> None:
    super().__init__()
    self.text = text
    self.styles = styles
  
  def to_string(self, indent : int) -> str:
    result = "Text(\"" + self.text + "\""
    if self.styles is not None:
      # should be typing.Dict[TextAttribute, typing.Any]
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
  _blocks: typing.List[IMBlock]
  
  def __init__(self) -> None:
    super().__init__()
    self._blocks = []
  
  @property
  def blocks(self):
    return self._blocks
  
  def add_block(self, block : IMBlock):
    self._blocks.append(block)
  
  def to_string(self, indent : int) -> str:
    result = type(self).__name__
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    for b in self._blocks:
      result += "\n" + "  "*(indent+1) + b.to_string(indent+1)
    return result

class IMSpecialParagraphType(enum.Enum):
  Regular = 0
  Quote = enum.auto() # treated as assets
  Code = enum.auto() # treated as assets; probably lowered to a text displayable centered on the screen

class IMParagraphBlock(IMBlock):
  _paragraph_type : IMSpecialParagraphType
  _element_list : typing.List[IMElement]

  @property
  def element_list(self):
    return self._element_list

  @property
  def paragraph_type(self):
    return self._paragraph_type
  
  def __init__(self) -> None:
    super().__init__()
    self._paragraph_type = IMSpecialParagraphType.Regular
    self._element_list = []
  
  def add_element(self, element : IMElement):
    self._element_list.append(element)
    
  def to_string(self, indent : int) -> str:
    result = "Paragraph"
    if self._paragraph_type != IMSpecialParagraphType.Regular:
      result += "(" + str(self._paragraph_type) + ")"
    attrs = self.get_attribute_list_string()
    if len(attrs) > 0:
      result += " [" + attrs + "]"
    for e in self._element_list:
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
  _local_options: typing.Dict[str, typing.Any]
  _relative_path : str # relative to namespace root; contains file extension
  _document_name : str # name of the document

  def __init__(self, document_name: str, relative_path : str) -> None:
    super().__init__()
    self._document_name = document_name
    self._relative_path = relative_path
  
  @property
  def relative_path(self):
    return self._relative_path
  
  @property
  def document_name(self):
    return self._document_name

class IMNamespace(IMBase):
  # namespace: stand-alone package; only the global namespace (namespace = []) and parent namespace (namespace list is a substring) is always present.
  # InputModel cannot assume other namespace-d assets are always available.
  _namespace: IRNamespaceIdentifier
  _root_real_path : str # real path of this namespace
  hash_algorithm : str # hash algorithm used for uniquing assets
  options: typing.Dict[str, typing.Any] # parsed from preppipe.json
  _fileset: typing.Dict[str, IMDocument]
  asset_symbol_table : typing.List[IMAssetSymbolEntry]
  asset_path_dict : typing.Dict[str, IMAssetSymbolEntry]
  asset_basepath_dict : typing.Dict[str, typing.List[str]]
  remap_dict : typing.Dict[str, str] # realpath for remapping --> relative path after remapping (no trailing '/')
  asset_checksum_dict : typing.Dict[bytes, typing.List[IMAssetSymbolEntry]] # checksum of asset --> list of entries with the same hash
  invalid_asset_entry : IMAssetSymbolEntry # used to keep track of invalid entries
  # in the input model, we have not yet resolved any "asset name"; assets are only referenced by path
  # we always use realpath (i.e., resolving symlinks) whenever a path is requested. this helps with security check.
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
  
  _default_hash_algorithm : typing.ClassVar[str] = "sha512"
  
  @staticmethod
  def set_default_hash_algorithm(algorithm : str):
    if algorithm in hashlib.algorithms_available:
      IMNamespace._default_hash_algorithm = algorithm
    else:
      MessageHandler.warning("IMNamespace.set_default_hash_algorithm(): specified algorithm \"" + algorithm + "\" not available; existing choice (" + IMNamespace._default_hash_algorithm + ") unchanged")
  
  def get_checksum(self, snapshot : bytes) -> bytes:
    hasher = hashlib.new(self.hash_algorithm)
    hasher.update(snapshot)
    return hasher.digest()
  
  @property
  def namespace(self):
    return self._namespace
  
  @property
  def root_real_path(self):
    return self._root_real_path

  @property
  def fileset(self):
    return self._fileset

  def __init__(self, namespace : IRNamespaceIdentifier, rootpath : str) -> None:
    self._namespace = namespace
    self._root_real_path = IMNamespace._canonicalize_path(rootpath)
    self.hash_algorithm = IMNamespace._default_hash_algorithm
    self.options = {}
    self._fileset = {}
    self.asset_symbol_table = []
    self.asset_path_dict = {}
    self.asset_basepath_dict = {}
    self.remap_dict = {}
    self.asset_checksum_dict = {}
    self.invalid_asset_entry = IMAssetSymbolEntry(None, bytes())
    
  @staticmethod
  def _canonicalize_path(path : str) -> str:
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.realpath(path)
    return path
  
  def resolve_to_relative_path(self, realpath: str) -> str:
    # return None if cannot resolve to a relative path inside the root directory
    if realpath == self.root_real_path:
      return ''
    if realpath.startswith(self.root_real_path + os.sep):
      return os.path.relpath(realpath, self.root_real_path)
    # the path may be inside one of the directories remapped to be inside the root directory
    for source_path, dest_path in self.remap_dict.items():
      if realpath == source_path:
        return dest_path
      if realpath.startswith(source_path + os.sep):
        return os.path.join(dest_path, os.path.relpath(realpath, source_path))
    # if the path does not fall in the rootpath, return something invalid
    return None
  
  def _canonialize_namespace_relative_path(self, path: str) -> str:
    # return none if path invalid (cannot resolve to a relative path under the root directory)
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.normpath(os.path.join(self.root_real_path, path))
    return self.resolve_to_relative_path(path)
  
  def _get_message_location_header(self):
    return "<IMNamespace at " + self.root_real_path + ">"
  
  def add_path_remapping_entry(self, source_path: str, dest_relative_path : str) -> bool:
    source_path = IMNamespace._canonicalize_path(source_path)
    old_dest_relative_path = dest_relative_path
    dest_relative_path = self._canonialize_namespace_relative_path(dest_relative_path)
    if dest_relative_path is None:
      MessageHandler.warning(self._get_message_location_header() + ".add_path_remapping_entry(): dest path \"" + old_dest_relative_path + "\" invalid (likely outside the root directory?")
      return False
    assert isinstance(dest_relative_path, str)
    self.remap_dict[source_path] = dest_relative_path
    return True
  
  def _register_asset_relpath(self, entry: IMAssetSymbolEntry, relative_path: str) -> None:
    # we cannot directly take relative_path from entry because an entry may corresponds to more than one paths
    # only the first one will have matching relative_path and all later ones will not have the same one
    
    # setup self.asset_path_dict
    assert relative_path not in self.asset_path_dict
    self.asset_path_dict[relative_path] = entry
    
    # setup self.asset_basepath_dict
    base, ext = os.path.splitext(relative_path)
    if len(ext) > 0 and ext[0] == '.':
      ext = ext[1:]
    if base not in self.asset_basepath_dict:
      self.asset_basepath_dict[base] = []
    self.asset_basepath_dict[base].append(ext)
  
  def _register_asset_checksum(self, entry: IMAssetSymbolEntry) -> None:
    checksum = entry.checksum
    if checksum not in self.asset_checksum_dict:
      self.asset_checksum_dict[checksum] = []
    self.asset_checksum_dict[checksum].append(entry)
    
  def get_asset_symbol_entry_from_path(self, realpath : str, mimetype: str, AssetClass : typing.Type[AssetBase]) -> IMAssetSymbolEntry:
    
    # helper for mime type check
    def check_mimetype(result: IMAssetSymbolEntry):
      if result.get_mime_type() != mimetype:
        MessageHandler.warning(self._get_message_location_header() + ".get_asset_symbol_entry_from_path(): existing asset entry has different mimetype (" + result.get_mime_type() + ") from the request (" + mimetype + ")")
    
    # real work
    relative_path = self.resolve_to_relative_path(realpath)
    if relative_path is None:
      # access violation; the warning should be emitted by the caller
      return self.invalid_asset_entry
    # check if we have already registered this asset
    if relative_path in self.asset_path_dict:
      existing_result = self.asset_path_dict.get(relative_path)
      # check if the mimetype matches; emit a warning if not
      check_mimetype(existing_result)
      return existing_result
    
    # we check whether the file exists at all here
    # if someday we want to move this check, make sure we "leak information" on whether the file exists or not only when we have permission to access the file
    if not os.path.exists(realpath):
      return self.invalid_asset_entry
    
    # this asset is not registered with explicit path yet
    # however, it is possible that it is currently an anonymous asset
    # check if we have a clash there
    asset = AssetClass(mimetype, backing_store_path=realpath)
    snapshot = asset.get_snapshot()
    checksum = self.get_checksum(snapshot)
    if checksum in self.asset_checksum_dict:
      for candidate_entry in self.asset_checksum_dict[checksum]:
        if candidate_entry.asset.get_snapshot() == snapshot:
          # we found a match
          if len(candidate_entry.relative_path) == 0:
            # this entry was previously anonymous and has no relative path set yet
            # we should also set the absolute path, since it is always initialized together with the relative path
            candidate_entry.relative_path = relative_path
            candidate_entry.real_path = realpath
            
          # it is possible that we found another entry with a different relative path set
          # no matter which case, we will always register the new path
          self._register_asset_relpath(candidate_entry, relative_path)
          
          # generate a warning if mime type does not match
          check_mimetype(candidate_entry)
          return candidate_entry
            
    # if no existing one found, create a new entry
    entry = IMAssetSymbolEntry(asset, checksum, relative_path, realpath)
    self._register_asset_relpath(entry, relative_path)
    self._register_asset_checksum(entry)
    return entry
  
  def get_asset_symbol_entry_from_inlinedata(self, data : bytes, mimetype : str, inlinedDocumentRealPath: str, localref : str, AssetClass : typing.Type[AssetBase]) -> IMAssetSymbolEntry:
    
    # helper for mime type check
    def check_mimetype(result: IMAssetSymbolEntry):
      if result.get_mime_type() != mimetype:
        MessageHandler.warning(self._get_message_location_header() + ".get_asset_symbol_entry_from_path(): existing asset entry has different mimetype (" + result.get_mime_type() + ") from the request (" + mimetype + ")")
    
    # real work
    checksum = self.get_checksum(data)
    if checksum in self.asset_checksum_dict:
      for candidate_entry in self.asset_checksum_dict[checksum]:
        if candidate_entry.asset.get_snapshot() == data:
          check_mimetype(candidate_entry)
          return candidate_entry
    
    # create a new one
    asset = AssetClass(mimetype, snapshot=data)
    entry = IMAssetSymbolEntry(asset, checksum)
    entry.anonymous_path = os.path.join(inlinedDocumentRealPath, localref)
    self._register_asset_checksum(entry)
    return entry
  
  def get_image_asset_entry_from_path(self, imageRealPath : str, mimetype : str) -> IMAssetSymbolEntry:
    return self.get_asset_symbol_entry_from_path(imageRealPath, mimetype, ImageAsset)
  
  def get_image_asset_entry_from_inlinedata(self, data : bytes, mimetype : str, inlinedDocumentRealPath: str, localref : str) -> IMAssetSymbolEntry:
    return self.get_asset_symbol_entry_from_inlinedata(data, mimetype, inlinedDocumentRealPath, localref, ImageAsset)

  def add_document(self, doc : IMDocument) -> None:
    assert doc.relative_path not in self._fileset
    self._fileset[doc.relative_path] = doc

class InputModel(IMBase):
  global_options: typing.Dict[str, typing.Any]
  _namespaces : typing.Dict[IRNamespaceIdentifier, IMNamespace]
  
  def __init__(self) -> None:
    super().__init__()
    self.global_options = {}
    self._namespaces = {}
  
  @property
  def namespaces(self):
    return self._namespaces
  
  def add_namespace(self, ns : IMNamespace):
    assert ns.namespace not in self._namespaces
    self._namespaces[ns.namespace] = ns
  
  def merge_with(self, other) -> None:
    assert isinstance(other, InputModel)
    raise NotImplementedError()

# UPDATE: now IMNamespaceBuilder is dead; please just create IMNamespace and add stuff on it
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
    