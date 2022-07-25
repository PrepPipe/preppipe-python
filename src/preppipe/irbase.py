# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
import enum
import dataclasses
import llist
import collections
import collections.abc
import tempfile
import os
import pathlib

import bidict
import PIL.Image
import pydub
import shutil

# ------------------------------------------------------------------------------
# ADT needed for IR
# ------------------------------------------------------------------------------

# we create our own list type here because of the following reasons:
# 1. IDE (e.g., VSCode) may not be able to get information from llist module for auto-completion, etc
# 2. Certain API is easy to misuse for our use case (we will subclass the nodes)
#    For example:
#       * llist.dllist.insert(), etc will create NEW nodes instead of directly using the node passed in, and this is not what we want
#       * iterating over a dllist is getting the VALUE on the nodes, instead of getting the nodes

T = typing.TypeVar('T') # typevar for the node subclass

class IList(typing.Generic[T]):
  _ilist : llist.dllist

  def __init__(self, parent : typing.Any) -> None:
    super().__init__()
    self._ilist = llist.dllist()
    setattr(self._ilist, "parent", parent)
    setattr(self._ilist, "ilistref", self)
  
  @property
  def size(self) -> int:
    return self._ilist.size
  
  @property
  def front(self) -> T:
    # return the first node if available, None if not
    return self._ilist.first
  
  @property
  def empty(self) -> bool:
    return self._ilist.first is None
  
  @property
  def back(self) -> T:
    # return the last node if available, None if not
    return self._ilist.last
  
  def insert(self, where : T, node : T):
    self._ilist.insertnodebefore(node, where)
  
  def push_back(self, node : T):
    self._ilist.appendnode(node)
  
  def push_front(self, node : T):
    self._ilist.insertnodebefore(node, self._ilist.first)
  
  def get_index_of(self, node : T) -> int:
    # -1 if node not found, node index if found
    cur_index = 0
    cur_node = self.front()
    while cur_node is not None:
      if cur_node is node:
        return cur_index
      cur_node = cur_node.next
    return -1
  
  def merge_into(self, dest : IList[T]):
    while self.front is not None:
      v = self.front
      self._ilist.remove(v)
      dest.push_back(v)
  
  def __iter__(self) -> IListIterator[T]:
    return IListIterator(self._ilist.first)

  def __len__(self) -> int:
    return self.size
  
  def __getitem__(self, index : int) -> T:
    return self._ilist[index]

class IListIterator(typing.Generic[T]):
  _node : T

  def __init__(self, n : T) -> None:
    super().__init__()
    self._node = n
  
  def __next__(self) -> T:
    if self._node is None:
      raise StopIteration
    curnode = self._node
    self._node = curnode.next
    return curnode

# if the list intends to be mutable, element node should inherit from this class
# otherwise, just inheriting from llist.dllistnode is fine
class IListNode(typing.Generic[T], llist.dllistnode):
  def __init__(self, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(**kwargs)
  
  def insert_before(self, ip : IListNode[T]) -> None:
    ip.owner.insert(ip, self)
  
  # erase_from_parent() includes self cleanup; it should be defined in derived classes
  def remove_from_parent(self):
    self.owner.remove(self)
  
  @property
  def prev(self) -> T:
    return super().prev
  
  @property
  def next(self) -> T:
    return super().next
  
  @property
  def parent(self):
    # return the parent of the list
    # to get a type hint, override this method in derived class to add it
    return self.owner.parent
  
  @property
  def ilistref(self) -> IList[T]:
    return self.owner.ilistref

  def get_index(self):
    return self.ilistref.get_index_of(self)

class NameDict(collections.abc.MutableMapping, typing.Generic[T]):
  _parent : typing.Any
  _dict : collections.OrderedDict[str, NameDictNode[T]]

  def __init__(self, parent : typing.Any) -> None:
    super().__init__()
    self._parent = parent
    self._dict = collections.OrderedDict()
  
  def __getitem__(self, key : str) -> T:
    return self._dict[key]
  
  def __setitem__(self, key : str, value : T) -> None:
    if value.dictref is not None:
      raise RuntimeError("Inserting one node into more than one NameDict")
    self._dict[key] = value
    value._update_parent_info(self, key)

  def __delitem__(self, key : str):
    value = self._dict[key]
    value._update_parent_info(None, "")
    del self._dict[key]
    
  def __iter__(self):
    return iter(self._dict)
  
  def __len__(self):
    return len(self._dict)
  
  @property
  def parent(self):
    return self._parent

class NameDictNode(typing.Generic[T]):
  _dictref : NameDict[T]
  _name : str

  def __init__(self, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(**kwargs)
    self._dictref = None
    self._name = ""

  @property
  def name(self) -> str:
    return self._name
  
  def _update_parent_info(self, parent: NameDict[T], name : str) -> None:
    self._dictref = parent
    self._name = name
  
  @property
  def dictref(self) -> NameDict[T]:
    return self._dictref
  
  @property
  def parent(self) -> typing.Any :
    if self._dictref is not None:
      return self._dictref.parent
    return None

# ------------------------------------------------------------------------------
# IR types
# ------------------------------------------------------------------------------

class Location:
  _context : Context

  def __init__(self, ctx : Context) -> None:
    self._context = ctx
  
  @property
  def context(self) -> Context:
    return self._context

  def __repr__(self) -> str:
    return type(self).__name__
  
  def __str__(self) -> str:
    return type(self).__name__

class ValueType:
  _context : Context

  def __init__(self, context: Context) -> None:
    self._context = context
  
  @property
  def context(self) -> Context:
    return self._context

  def __repr__(self) -> str:
    return type(self).__name__
  
  def __str__(self) -> str:
    return type(self).__name__

class BlockReferenceType(ValueType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  @staticmethod
  def get(ctx : Context) -> BlockReferenceType:
    return ctx.get_stateless_type(BlockReferenceType)

class _AssetDataReferenceType(ValueType):
  # this type is only for asset data internal reference (from Asset instance to AssetData instance)
  # we use this to implement copy-on-write
  # usually no user code need to work with it
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  @staticmethod
  def get(ctx : Context) -> _AssetDataReferenceType:
    return ctx.get_stateless_type(_AssetDataReferenceType)

class Attribute(NameDictNode):
  _data : typing.Any

  def __init__(self, data : typing.Any) -> None:
    super().__init__()
    self._data = data
  
  @property
  def data(self) -> typing.Any:
    return self._data
  
  @property
  def parent(self) -> Operation:
    return super().parent

class Value:
  # value is either a block argument or an operation result
  _type : ValueType
  _uselist : IList[Use]

  def __init__(self, ty : ValueType, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(**kwargs)
    self._type = ty
    self._uselist = IList(self)
  
  @property
  def uses(self) -> IList[Use]:
    return self._uselist
  
  def use_empty(self) -> bool:
    return self._uselist.empty
  
  @property
  def valuetype(self) -> ValueType:
    return self._type
  
  def replace_all_uses_with(self, v : Value) -> None:
    assert self._type == v._type
    self._uselist.merge_into(v._uselist)
  
  def __str__(self) -> str:
    return str(self._type) + ' ' + type(self).__name__

class NameReferencedValue(Value, NameDictNode):
  def __init__(self, ty: ValueType, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(ty, **kwargs)
  
  @property
  def parent(self) -> Block | Operation:
    return super().parent
  
class Use(IListNode):
  _user : User
  _argno : int
  def __init__(self, user : User, argno : int) -> None:
    super().__init__()
    self._user = user
    self._argno = argno
  
  @property
  def value(self) -> Value:
    return super().parent
  
  @property
  def user(self) -> User:
    return self._user
  
  @property
  def argno(self) -> int:
    return self._argno
  
  def set_value(self, v : Value):
    if super().parent is not None:
      super().remove_from_parent()
    if v is not None:
      v._uselist.push_back(self)

class User:
  _uselist : list[Use]

  def __init__(self, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(**kwargs)
    self._uselist = []
  
  def get_operand(self, index : int) -> Value:
    return self._uselist[index].value
  
  def set_operand(self, index : int, value : Value) -> None:
    if len(self._uselist) == index:
      return self.add_operand(value)
    self._uselist[index].set_value(value)
  
  def add_operand(self, value : Value) -> None:
    u = Use(self, len(self._uselist))
    self._uselist.append(u)
    u.set_value(value)
  
  def get_num_operands(self) -> int:
    return len(self._uselist)
  
  def drop_all_uses(self) -> None:
    for u in self._uselist:
      u.set_value(None)
    self._uselist.clear()

class OpOperand(User, NameDictNode):
  def __init__(self) -> None:
    super().__init__()
  
  @property
  def parent(self) -> Operation:
    return super().parent

  def get(self, index : typing.Optional[int] = None) -> Value:
    if index is not None:
      return super().get_operand(index)
    return super().get_operand(0)

class OpResult(NameReferencedValue):
  def __init__(self, ty: ValueType) -> None:
    super().__init__(ty)
  
  @property
  def result_number(self) -> int:
    return super().get_index()
  
  @property
  def parent(self) -> Operation:
    return super().parent

class OpTerminatorInfo(User):
  _parent : Operation

  def __init__(self, parent : Operation) -> None:
    super().__init__()
    self._parent = parent
  
  @property
  def parent(self) -> Operation:
    return self._parent
  
  def get_successor(self, index : int) -> Block:
    return super().get_operand(index).parent
  
  def set_successor(self, index : int, dest : Block) -> None:
    super().set_operand(index, dest.value)
  
  def add_successor(self, dest : Block) -> None:
    super().add_operand(dest.value)
  
  def get_num_successors(self) -> int:
    return super().get_num_operands()

class BlockArgument(NameReferencedValue):
  def __init__(self, ty: ValueType) -> None:
    super().__init__(ty)

# reference: https://mlir.llvm.org/doxygen/classmlir_1_1Operation.html
class Operation(IListNode):
  _name : str
  _loc : Location
  _operands : NameDict[OpOperand]
  _results : NameDict[OpResult]
  _attributes : NameDict[Attribute]
  _regions : NameDict[Region]
  _terminator_info : OpTerminatorInfo

  def __init__(self, name : str, loc : Location, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(**kwargs)
    self._name = name
    self._loc = loc
    self._operands = NameDict(self)
    self._results = NameDict(self)
    self._attributes = NameDict(self)
    self._terminator_info = None
  
  def _set_is_terminator(self):
    assert self._terminator_info is None
    self._terminator_info = OpTerminatorInfo(self)
  
  def _add_result(self, name : str, ty : ValueType) -> OpResult:
    r = OpResult(ty)
    self._results[name] = r
    return r
  
  def _add_operand(self, name : str) -> OpOperand:
    o = OpOperand()
    self._operands[name] = o
    return o
  
  def _add_operand_with_value(self, name : str, value : Value) -> OpOperand:
    o = self._add_operand(name)
    if value is not None:
      o.add_operand(value)
    return o
  
  def _add_operand_with_value_list(self, name : str, values : typing.Iterable[Value]) -> OpOperand:
    o = self._add_operand(name)
    for v in values:
      o.add_operand(v)
    return o
  
  def get_operand_inst(self, name : str) -> OpOperand:
    return self._operands.get(name)
  
  def get_operand(self, name : str) -> Value:
    o : OpOperand = self._operands.get(name)
    if o is not None:
      return o.get()
    return None
  
  def set_attr(self, name : str, value: typing.Any) -> Attribute:
    a = Attribute(value)
    self._attributes[name] = a
    return a
  
  def get_attr(self, name : str) -> Attribute:
    return self._attributes[name]
  
  def _add_region(self, name : str = '') -> Region:
    r = Region()
    self._regions[name] = r
    return r
  
  def get_region(self, name : str) -> Region:
    return self._regions.get(name)
  
  def drop_all_references(self) -> None:
    # drop all references to outside values; required before erasing
    for operand in self._operands.values():
      assert isinstance(operand, OpOperand)
      operand.drop_all_uses()
    if self._terminator_info is not None:
      self._terminator_info.drop_all_uses()
  
  @property
  def terminator_info(self) -> OpTerminatorInfo:
    return self._terminator_info

  def is_terminator(self) -> bool:
    return self._terminator_info is not None

  def get_successor(self, index : int) -> Block:
    if self._terminator_info is None:
      return None
    return self._terminator_info.get_successor(index)
  
  def set_successor(self, index : int, dest : Block) -> None:
    self._terminator_info.set_successor(index, dest)
  
  def add_successor(self, dest : Block) -> None:
    self._terminator_info.add_successor(dest)
  
  def get_num_successors(self) -> int:
    if self._terminator_info is None:
      return 0
    return self._terminator_info.get_num_successors()
  
  @property
  def name(self):
    return self._name
  
  @name.setter
  def name(self, n : str):
    self._name = n

  @property
  def parent(self) -> Block:
    return super().parent
  
  # TODO clone interface

  @property
  def block(self) -> Block:
    return self.parent
  
  @property
  def location(self) -> Location:
    return self._loc
  
  @location.setter
  def location(self, loc : Location):
    self._loc = loc
  
  @property
  def parent_region(self) -> Region:
    if self.parent is not None:
      return self.parent.parent
    return None
  
  @property
  def parent_op(self) -> Operation:
    parent_region = self.parent_region
    if parent_region is not None:
      return parent_region.parent
    return None

class Block(Value, IListNode):
  _ops : IList[Operation, Block]
  _args : IList[BlockArgument, Block]
  _name : str

  def __init__(self, name : str, context : Context) -> None:
    ty = BlockReferenceType.get(context)
    super().__init__(ty)
    self._ops = IList(self)
    self._args = IList(self)
    self._name = name
  
  @property
  def name(self) -> str:
    return self._name
  
  @name.setter
  def name(self, new_name : str) -> None:
    self._name = new_name

  @property
  def parent(self) -> Region:
    return super().parent
  
  @property
  def arguments(self) -> IList[BlockArgument, Block]:
    return self._args
  
  def add_argument(self, ty : ValueType):
    arg = BlockArgument(ty)
    self._args.push_back(arg)

  def drop_all_references(self) -> None:
    for op in self._ops:
      op.drop_all_references()

class Region(NameDictNode):
  _blocks : IList[Block, Region]

  def __init__(self) -> None:
    super().__init__()
    self._blocks = IList(self)
  
  def push_back(self, block : Block) -> None:
    self._blocks.push_back(block)
  
  def push_front(self, block : Block) -> None:
    self._blocks.push_front(block)
  
  @property
  def blocks(self) -> IList[Block, Region]:
    return self._blocks
  
  def drop_all_references(self) -> None:
    for b in self._blocks:
      b.drop_all_references()
  
  @property
  def entry_block(self) -> Block:
    return self._blocks.front

class Context:
  # the object that we use to keep track of unique constructs (types, constant expressions, file assets)
  _stateless_type_dict : dict[type, ValueType]
  _parameterized_type_dict : dict[type, dict[str, ValueType]] # for each parameterized type, the key for each instance is the string representation of the parameters
  _constant_dict : dict[type, dict[typing.Any, typing.Any]] # <ConstantType> -> <ConstantDataValue> -> ConstantDataObject
  _asset_data_list : IList[AssetData]
  _asset_temp_dir : tempfile.TemporaryDirectory # created on-demand
  _undef_location : Location # a dummy location value with only a reference to the context

  def __init__(self) -> None:
    self._stateless_type_dict = {}
    self._parameterized_type_dict = {}
    self._asset_data_list = IList(self)
    self._asset_temp_dir = None
    self._constant_dict = {}
    self._undef_location = Location(self)

  def get_stateless_type(self, ty : type) -> typing.Any:
    if ty in self._stateless_type_dict:
      return self._stateless_type_dict[ty]
    instance = ty(self)
    self._stateless_type_dict[ty] = instance
    return instance
  
  def get_parameterized_type_dict(self, ty : type) -> dict[str, ValueType]:
    if ty in self._parameterized_type_dict:
      return self._parameterized_type_dict[ty]
    result = {}
    self._parameterized_type_dict[ty] = result
    return result
  
  def get_backing_dir(self) -> tempfile.TemporaryDirectory:
    if self._asset_temp_dir is None:
      self._asset_temp_dir = tempfile.TemporaryDirectory(prefix="preppipe_asset")
    return self._asset_temp_dir
  
  def create_backing_path(self, suffix: str = "") -> str:
    backing_dir = self.get_backing_dir()
    fd, path = tempfile.mkstemp(dir=backing_dir.name,suffix=suffix)
    os.close(fd)
    return path
  
  def get_constant_uniquing_dict(self, ty : type) -> dict:
    if ty in self._constant_dict:
      return self._constant_dict[ty]
    result = {}
    self._constant_dict[ty] = result
    return result
  
  def _add_asset_data(self, asset : AssetData):
    # should only be called from the constructor of AssetData
    assert asset.owner is None
    self._asset_data_list.push_back(asset)
  
  @property
  def undef_location(self) -> Location:
    return self._undef_location
  
  #def add_asset_data(self, path : str, asset_type : type, **kwargs) -> AssetData:
  #  assert self._asset_temp_dir is not None
  #  assert issubclass(asset_type, AssetData)
  #  data = asset_type(context=self, backing_store_path=path, **kwargs)
  #  return data
    # if path.startswith(os.path.abspath(self._asset_temp_dir.name)+os.sep):

class AssetData(Value, IListNode):
  # an asset data represent a pure asset; no (IR-related) metadata
  # any asset data is immutable; they cannot be modified after creation
  # if we want to convert the type, a new asset data instance should be created

  # derived class can use their own judgement to decide storage policy
  # if the asset tends to be small (<16KB), we can store them in memory
  # otherwise we can store them on disk
  # however, in general if we want to make sure the hash of asset file is unchanged for copying and load/storing,
  # they shall be saved on disk

  # if analysis would like to have a big working set involving multiple assets, they can implement their own cache

  #_backing_store_path : str # if it is in the temporary directory, this asset data owns it; otherwise the source is read-only; empty string if no backing store

  def __init__(self, context : Context, **kwargs) -> None:
    ty = _AssetDataReferenceType.get(context)
    super().__init__(ty, **kwargs)
    context._add_asset_data(self)
  
  #@property
  #def backing_store_path(self) -> str:
  #  return self._backing_store_path
  
  def load(self) -> typing.Any:
    # load the asset data to memory
    # should be implemented in the derived classes
    pass

  def export(self, dest_path : str) -> None:
    # save the asset data to the specified path
    # we do not try to create another AssetData instance here
    # if the caller want one, they can always create one using the dest_path
    pass

  @staticmethod
  def secure_overwrite(exportpath: str, write_callback: typing.Callable, open_mode : str = 'wb'):
    tmpfilepath = exportpath + ".tmp"
    parent_path = pathlib.Path(tmpfilepath).parent
    os.makedirs(parent_path, exist_ok=True)
    isOldExist = os.path.isfile(exportpath)
    with open(tmpfilepath, open_mode) as f:
      write_callback(f)
    if isOldExist:
      old_name = exportpath + ".old"
      os.rename(exportpath, old_name)
      os.rename(tmpfilepath, exportpath)
      os.remove(old_name)
    else:
      os.rename(tmpfilepath, exportpath)

class BytesAssetData(AssetData):
  _backing_store_path : str
  _data : bytes
  def __init__(self, context: Context, *, backing_store_path : str = '', data : bytes = None,  **kwargs) -> None:
    super().__init__(context, **kwargs)
    self._backing_store_path = backing_store_path
    self._data = data
    # invariants check: either backing_store_path is provided, or data is provided
    assert (self._data is not None) == (len(self._backing_store_path) == 0)
  
  def load(self) -> bytes:
    if self._data is not None:
      return self._data
    with open(self._backing_store_path, 'rb') as f:
      return f.read()
  
  def export(self, dest_path: str) -> None:
    if self._data is not None:
      with open(dest_path, 'wb') as f:
        f.write(self._data)
    else:
      shutil.copy2(self._backing_store_path, dest_path, follow_symlinks=False)


class ImageAssetData(AssetData):
  _backing_store_path : str
  _data : PIL.Image.Image
  _format : str # format parameter used by PIL (e.g., 'png', 'bmp', ...)

  def __init__(self, context: Context, *, backing_store_path : str = '', data : PIL.Image.Image = None, **kwargs) -> None:
    super().__init__(context, **kwargs)
    self._backing_store_path = backing_store_path
    self._data = data
    self._format = None
    # invariants check: either backing_store_path or data is provided
    if len(self._backing_store_path) == 0:
      assert self._data is not None
      self._format = self._data.format # can be None
      # no other checks for now
    else:
      assert self._data is None
      # verify that the image file is valid
      with PIL.Image.open(self._backing_store_path) as image:
        self._format = image.format.lower()
        assert len(self._format) > 0
        image.verify()
  
  @property
  def format(self) -> str | None:
    # we can have no formats if the data is from a temporary PIL image
    return self._format
  
  def load(self) -> PIL.Image.Image:
    if self._data is not None:
      return self._data
    return PIL.Image.open(self._backing_store_path)

  def export(self, dest_path : str) -> None:
    if self._data is not None:
      self._data.save(dest_path)
      return
    # we do file copy iff the source and dest format matches
    # otherwise, we open the source file and save it in the destination
    srcname, srcext = os.path.splitext(self._backing_store_path)
    destname, destext = os.path.splitext(dest_path)
    if srcext == destext:
      shutil.copy2(self._backing_store_path, dest_path, follow_symlinks=False)
    else:
      image = PIL.Image.open(self._backing_store_path)
      image.save(dest_path)

class AudioAssetData(AssetData):
  _backing_store_path : str
  _data : pydub.AudioSegment
  _format : str

  _supported_formats : typing.ClassVar[list[str]] = ["wav", "aac", "ogg", "m4a", "aiff", "flac", "mp3"]

  def __init__(self, context: Context, *, backing_store_path : str, data : pydub.AudioSegment, **kwargs) -> None:
    super().__init__(context, **kwargs)
    self._backing_store_path = backing_store_path
    self._data = data
    self._format = None
    # invariants check: either backing_store_path or data is provided
    if len(self._backing_store_path) == 0:
      assert self._data is not None
      self._format = None
      # no other checks for now
    else:
      assert self._data is None
      # check that the file extension is what we recognize
      basepath, ext = os.path.splitext(self._backing_store_path)
      ext = ext.lower()
      if ext in self._supported_formats:
        self._format = ext
      else:
        raise RuntimeError("Unrecognized audio file format: " + ext)
  
  @property
  def format(self) -> str | None:
    return self._format

  def load(self) -> pydub.AudioSegment:
    if self._data is not None:
      return self._data
    return pydub.AudioSegment.from_file(self._backing_store_path, format = self._format)
  
  def export(self, dest_path: str) -> None:
    basepath, ext = os.path.splitext(dest_path)
    fmt = ext.lower()
    assert fmt in self._supported_formats
    if self._data is not None:
      self._data.export(dest_path, format=fmt)
      return
    if fmt == self._format:
      shutil.copy2(self._backing_store_path, dest_path, follow_symlinks=False)
    else:
      data : pydub.AudioSegment = pydub.AudioSegment.from_file(self._backing_store_path, format = self._format)
      data.export(dest_path, format=fmt)

class AssetBase(User):
  # base class of assets that other IR components can reference
  # depending on the use case, the asset may or may not reference an actual asset data
  # (e.g., if we are at backend, the asset can just export the asset and do not track it)
  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
  
  def load(self) -> typing.Any:
    data : AssetData = self.get_operand(0)
    if data is not None:
      return data.load()
    return None
  
  def set_data(self, data : typing.Any):
    # the correct way of modifying an asset data is:
    # 1. load the asset data to memory (call AssetBase.load())
    # 2. do modification on it
    # 3. call Context.create_backing_path() to get a destination for saving
    # 4. save the data to the file
    # 5. create the new AssetData with Context.add_asset_data()
    # 6. call AssetBase.set_operand(0, ...)
    # AssetBase.set_data() takes care of step 3-6 above
    # should be implemented in derived classes
    raise NotImplementedError("AssetBase.set_data() not overriden in " + type(self).__name__)

