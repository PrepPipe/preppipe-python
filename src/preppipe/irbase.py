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
import webbrowser
import io

from .commontypes import TextAttribute, Color

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

class IList(typing.Generic[T], llist.dllist):
  _parent : typing.Any
  def __init__(self, parent : typing.Any) -> None:
    super().__init__()
    self._parent = parent
  
  @property
  def parent(self) -> typing.Any:
    return self._parent
  
  @property
  def size(self) -> int:
    return super().size
  
  @property
  def front(self) -> T:
    # return the first node if available, None if not
    return super().first
  
  @property
  def empty(self) -> bool:
    return super().first is None
  
  @property
  def back(self) -> T:
    # return the last node if available, None if not
    return super().last
  
  def insert(self, where : T, node : T):
    super().insertnodebefore(node, where)
  
  def push_back(self, node : T):
    super().appendnode(node)
  
  def push_front(self, node : T):
    super().insertnodebefore(node, super().first)
  
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
      super().remove(v)
      dest.push_back(v)
  
  def __iter__(self) -> IListIterator[T]:
    return IListIterator(super().first)

  def __len__(self) -> int:
    return self.size
  
  def __getitem__(self, index : int) -> T:
    return super().__getitem__[index]

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
  
  def _try_get_owner(self):
    # first, weakref itself can be None if it never referenced another object
    # second, weakref may lose reference to the target
    # we use this function to dereference a weakref
    if self.owner is not None:
      return self.owner()
    return None
  
  def insert_before(self, ip : IListNode[T]) -> None:
    owner = self._try_get_owner()
    ipowner = ip._try_get_owner()
    assert ipowner is not None
    if owner is not None:
      self.node_removed(self.parent)
      owner.remove(self)
    self.node_inserted(self.parent)
    ipowner.insertnode(ip, self)
  
  # erase_from_parent() includes self cleanup; it should be defined in derived classes
  def remove_from_parent(self):
    owner = self._try_get_owner()
    if owner is not None:
      self.node_removed(self.parent)
      owner.remove(self)
  
  # if a derived class want to execute code before inserting or removing from list,
  # override these member functions

  def node_inserted(self, parent):
    # parent is the new parent after insertion
    pass

  def node_removed(self, parent):
    # parent is the one that is no longer the parent after the removal
    pass
  
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
    owner = self._try_get_owner()
    if owner is not None:
      return owner.parent
    return None

  def get_index(self):
    owner = self._try_get_owner()
    assert owner is not None
    return owner.get_index_of(self)

class NameDict(collections.abc.MutableMapping, typing.Generic[T]):
  _parent : typing.Any
  _dict : collections.OrderedDict[str, NameDictNode[T]]

  def __init__(self, parent : typing.Any) -> None:
    super().__init__()
    self._parent = parent
    self._dict = collections.OrderedDict()
  
  def __contains__(self, key : str) -> bool:
    return self._dict.__contains__(key)
  
  def __getitem__(self, key : str) -> T:
    return self._dict.__getitem__(key)
  
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
  def empty(self):
    return len(self._dict) == 0
  
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
# IR classes
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
  
  @staticmethod
  def getNullLocation(ctx: Context):
    return ctx.null_location

# ------------------------------------------------------------------------------
# Types
# ------------------------------------------------------------------------------

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

class ParameterizedType(ValueType):
  # parameterized types are considered different if the parameters (can be types or literal values) are different
  _parameters : typing.List[ValueType | int | str | bool | None] # None for separator

  def __init__(self, context: Context, parameters : typing.Iterable[ValueType | int | str | bool | None]) -> None:
    super().__init__(context)
    self._parameters = list(parameters)
  
  @staticmethod
  def _get_parameter_repr(parameters : typing.List[ValueType | int | str | bool | None]):
    result = ''
    isFirst = True
    for v in parameters:
      if isFirst:
        isFirst = False
      else:
        result += ', '
      if isinstance(v, ValueType):
        result += repr(v)
      elif isinstance(v, str):
        result += '"' + v + '"'
      elif v is None:
        # this is a separator
        result += '---'
      else: # int or bool
        result += str(v)
    return result

  def __repr__(self) -> str:
    return  type(self).__name__ + '<' + ParameterizedType._get_parameter_repr(self._parameters) + '>'

class OptionalType(ParameterizedType):
  # dependent type that is optional of the specified type (either have the data or None)
  # likely used for a PHI for handles
  _depend_type : ValueType

  def __init__(self, ty : ValueType) -> None:
    super().__init__(ty.context, [ty])
    self._depend_type = ty
  
  def __str__(self) -> str:
    return "可选<" + str(self._depend_type) + ">"
  
  @property
  def element_type(self) -> ValueType:
    return self._depend_type

  @staticmethod
  def get(ty : ValueType) -> OptionalType:
    # skip degenerate case
    if isinstance(ty, OptionalType):
      return ty
    return ty.context.get_parameterized_type_dict(OptionalType).get_or_create([ty], lambda : OptionalType(ty))

class ParameterizedTypeUniquingDict:
  # this class is used by Context to manage all parameterized type objects
  _pty : type # type object of the parameterized type
  _instance_dict : dict[str, ValueType]
  def __init__(self, pty : type) -> None:
    self._instance_dict = {}
    self._pty = pty
    assert isinstance(pty, type)
  
  def get_or_create(self, parameters : typing.List[ValueType | int | str | bool | None], ctor : callable):
    reprstr = ParameterizedType._get_parameter_repr(parameters)
    if reprstr in self._instance_dict:
      return self._instance_dict[reprstr]
    inst = None
    if callable(ctor):
      inst = ctor()
    else:
      inst = self._pty(parameters)
    self._instance_dict[reprstr] = inst
    return inst


# ------------------------------------------------------------------------------
# Actual value types
# ------------------------------------------------------------------------------

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

class IntType(ValueType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "整数类型"
  
  @staticmethod
  def get(ctx : Context) -> IntType:
    return ctx.get_stateless_type(IntType)

class FloatType(ValueType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "浮点数类型"
  
  @staticmethod
  def get(ctx : Context) -> FloatType:
    return ctx.get_stateless_type(FloatType)

class BoolType(ValueType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "逻辑类型"
  
  @staticmethod
  def get(ctx : Context) -> BoolType:
    return ctx.get_stateless_type(BoolType)

class StringType(ValueType):
  # any string
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "字符串类型"
  
  @staticmethod
  def get(ctx : Context) -> StringType:
    return ctx.get_stateless_type(StringType)

class TextStyleType(ValueType):
  # text styles
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "文本格式类型"
  
  @staticmethod
  def get(ctx : Context) -> TextStyleType:
    return ctx.get_stateless_type(TextStyleType)

class TextType(ValueType):
  # string + style (style can be empty)
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "文本类型"
  
  @staticmethod
  def get(ctx : Context) -> TextType:
    return ctx.get_stateless_type(TextType)

class ImageType(ValueType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "图片类型"
  
  @staticmethod
  def get(ctx : Context) -> ImageType:
    return ctx.get_stateless_type(ImageType)

class AudioType(ValueType):
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "声音类型"
  
  @staticmethod
  def get(ctx : Context) -> AudioType:
    return ctx.get_stateless_type(AudioType)

class AggregateTextType(ValueType):
  # 列表，表格，代码段等结构化的文本内容
  def __init__(self, context: Context) -> None:
    super().__init__(context)
  
  def __str__(self) -> str:
    return "结构文本类型"
  
  @staticmethod
  def get(ctx : Context) -> AggregateTextType:
    return ctx.get_stateless_type(AggregateTextType)

# ------------------------------------------------------------------------------
# Major classes
# ------------------------------------------------------------------------------

class Attribute(NameDictNode):
  _data : typing.Any

  def __init__(self, data : typing.Any) -> None:
    super().__init__()
    self._data = data
  
  @property
  def value(self) -> typing.Any:
    return self._data
  
  @value.setter
  def value(self, v : typing.Any) -> None:
    self._data = v
  
  @property
  def data(self) -> typing.Any:
    return self._data
  
  @data.setter
  def data(self, v : typing.Any) -> None:
    self._data = v
  
  @property
  def parent(self) -> Operation:
    return super().parent

class IntrinsicAttribute(Attribute):
  # use intrinsic attributes for class data members
  _attrname : str
  def __init__(self, attrname : str) -> None:
    super().__init__(data=None)
    self._attrname = attrname
  
  @property
  def value(self) -> typing.Any:
    return getattr(super().parent, self._attrname)
  
  @value.setter
  def value(self, v : typing.Any) -> None:
    setattr(super().parent, self._attrname, v)

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
  _operandlist : list[Use]

  def __init__(self, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(**kwargs)
    self._operandlist = []
  
  def get_operand(self, index : int) -> Value:
    return self._operandlist[index].value
  
  def set_operand(self, index : int, value : Value) -> None:
    if len(self._operandlist) == index:
      return self.add_operand(value)
    self._operandlist[index].set_value(value)
  
  def add_operand(self, value : Value) -> None:
    u = Use(self, len(self._operandlist))
    self._operandlist.append(u)
    u.set_value(value)
  
  def get_num_operands(self) -> int:
    return len(self._operandlist)
  
  def operanduses(self) -> typing.Iterable[Use]:
    return self._operandlist
  
  def drop_all_uses(self) -> None:
    for u in self._operandlist:
      u.set_value(None)
    self._operandlist.clear()

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
  
  # 可以调用 User.drop_all_uses() 来取消所有引用

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
  
  @property
  def parent(self) -> Block:
    return super().parent

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
    self._regions = NameDict(self)
    self._terminator_info = None
  
  def _set_is_terminator(self):
    assert self._terminator_info is None
    self._terminator_info = OpTerminatorInfo(self)
  
  def _add_result(self, name : str, ty : ValueType) -> OpResult:
    r = OpResult(ty)
    self._results[name] = r
    return r
  
  @property
  def operands(self):
    return self._operands
  
  @property
  def results(self):
    return self._results
  
  @property
  def attributes(self):
    return self._attributes
  
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
  
  def _add_intrinsic_attr(self, name : str, attrname : str) -> IntrinsicAttribute:
    assert name not in self._attributes
    a = IntrinsicAttribute(attrname)
    self._attributes[name] = a
    return a
  
  def set_attr(self, name : str, value: typing.Any) -> Attribute:
    a : Attribute = None
    if name in self._attributes:
      a = self._attributes[name]
      a.data = value
    else:
      a = Attribute(value)
      self._attributes[name] = a
    return a
  
  def get_attr(self, name : str) -> Attribute:
    return self._attributes[name]
  
  def _add_region(self, name : str = '') -> Region:
    r = Region()
    self._regions[name] = r
    return r
  
  def get_or_create_region(self, name : str = '') -> Region:
    if name in self._regions:
      return self._regions[name]
    return self._add_region(name)
  
  def _add_symbol_table(self, name : str = '') -> SymbolTableRegion:
    r = SymbolTableRegion(self._loc.context)
    self._regions[name] = r
    return r
  
  def get_region(self, name : str) -> Region:
    return self._regions.get(name)
  
  def get_num_regions(self) -> int:
    return len(self._regions)
  
  def get_region_names(self) -> typing.Iterable[str]:
    return self._regions.keys()
  
  @property
  def regions(self) -> typing.Iterable[Region]:
    return self._regions.values()
  
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
  def parent_block(self) -> Block:
    return self.parent
  
  @property
  def location(self) -> Location:
    return self._loc
  
  @location.setter
  def location(self, loc : Location):
    assert self._loc.context is loc.context
    self._loc = loc
  
  @property
  def context(self) -> Context:
    return self._loc.context

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
  
  def view(self) -> None:
    # for debugging
    _view_operation_impl(self)
  
  def dump(self) -> None:
    # for debugging
    _dump_operation_impl(self)

class Symbol(Operation):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
  
  @Operation.name.setter
  def name(self, n : str):
    if self.parent is not None:
      table : SymbolTableRegion = self.parent.parent
      assert isinstance(table, SymbolTableRegion)
      table._rename_symbol(self, n)
    self._name = n
  
  def node_inserted(self, parent : Block):
    table : SymbolTableRegion = parent.parent
    assert isinstance(table, SymbolTableRegion)
    table._add_symbol(self)
  
  def node_removed(self, parent : Block):
    table : SymbolTableRegion = parent.parent
    assert isinstance(table, SymbolTableRegion)
    table._drop_symbol(self.name)

class Block(Value, IListNode):
  _ops : IList[Operation, Block]
  _args : NameDict[BlockArgument]
  _name : str

  def __init__(self, name : str, context : Context) -> None:
    ty = BlockReferenceType.get(context)
    super().__init__(ty)
    self._ops = IList(self)
    self._args = NameDict(self)
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
  def args(self) -> NameDict[BlockArgument]:
    return self._args
  
  def arguments(self) -> typing.Iterable[BlockArgument]:
    return self._args.values()

  @property
  def body(self) -> IList[Operation, Block]:
    return self._ops
  
  def add_argument(self, name : str, ty : ValueType) -> BlockArgument:
    arg = BlockArgument(ty)
    self._args[name] = arg
    return arg
  
  def get_or_create_argument(self, name : str, ty : ValueType) -> BlockArgument:
    if name in self._args:
      return self._args[name]
    return self.add_argument(name, ty)

  def drop_all_references(self) -> None:
    for op in self._ops:
      op.drop_all_references()
  
  def push_back(self, op : Operation):
    self._ops.push_back(op)

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
  
  @property
  def parent(self) -> Operation:
    return super().parent
  
  def add_block(self, name : str = '') -> Block:
    block = Block(name, self.parent.context)
    self._blocks.push_back(block)
    return block

class SymbolTableRegion(Region, collections.abc.Sequence):
  # if a region is a symbol table, it will always have one block
  _lookup_dict : dict[str, Symbol]
  _block : Block
  _anonymous_count : int # we use numeric default names if a symbol without name is added
  
  def __init__(self, context : Context) -> None:
    super().__init__()
    self._block = Block("", context)
    self.push_back(self._block)
    self._anonymous_count = 0
  
  def _get_anonymous_name(self):
    result = str(self._anonymous_count)
    self._anonymous_count += 1
    return result
  
  def _drop_symbol(self, name : str):
    self._lookup_dict.pop(name, None)
  
  def _add_symbol(self, symbol : Symbol):
    # make sure _add_symbol is called BEFORE adding the symbol to list
    # to avoid infinite recursion
    if len(symbol.name) == 0:
      symbol.name = self._get_anonymous_name()
    assert symbol.name not in self._lookup_dict
    self._lookup_dict[symbol.name] = symbol
  
  def _rename_symbol(self, symbol : Symbol, newname : str):
    assert newname not in self._lookup_dict
    self._lookup_dict.pop(symbol.name, None)
    self._lookup_dict[newname] = symbol
  
  def __getitem__(self, key : str) -> Symbol:
    return self.get(key, None)
  
  def get(self, key : str) -> Symbol:
    return self._lookup_dict.get(key, None)
  
  def __iter__(self):
    return iter(self._lookup_dict.values())
  
  def __len__(self):
    return len(self._lookup_dict)
  
  def __contains__(self, value: Symbol) -> bool:
    return self._lookup_dict.get(value.name, None) == value
  
  def add(self, symbol : Symbol):
    self._block.push_back(symbol)

class Constant(Value):
  _value : typing.Any
  def __init__(self, ty: ValueType, value : typing.Any, **kwargs) -> None:
    super().__init__(ty, **kwargs)
    self._value = value
  
  @property
  def value(self) -> typing.Any:
    return self._value
  
  def get_context(self) -> Context:
    return self.valuetype.context
  
  @staticmethod
  def _get_constant_impl(cls : type, value : typing.Any, context : Context) -> typing.Any:
    return context.get_constant_uniquing_dict(cls).get_or_create(value, lambda : cls(context, value))
  
class ConstantUniquingDict:
  _ty : type
  _inst_dict : dict[typing.Any, typing.Any]
  
  def __init__(self, ty : type) -> None:
    self._ty = ty
    self._inst_dict = {}
  
  def get_or_create(self, data : typing.Any, ctor : callable) -> Value:
    if data in self._inst_dict:
      return self._inst_dict[data]
    inst = ctor()
    self._inst_dict[data] = inst
    return inst
  

class Context:
  # the object that we use to keep track of unique constructs (types, constant expressions, file assets)
  _stateless_type_dict : dict[type, ValueType]
  _parameterized_type_dict : dict[type, ParameterizedTypeUniquingDict]
  _constant_dict : dict[type, ConstantUniquingDict]
  _asset_data_list : IList[AssetData]
  _asset_temp_dir : tempfile.TemporaryDirectory # created on-demand
  _null_location : Location # a dummy location value with only a reference to the context
  _difile_dict : dict[str, DIFile] # from filepath string to the DIFile object
  _diloc_dict : dict[DIFile, dict[tuple[int, int, int], DILocation]] # <file> -> <page, row, column> -> DILocation

  def __init__(self) -> None:
    self._stateless_type_dict = {}
    self._parameterized_type_dict = {}
    self._asset_data_list = IList(self)
    self._asset_temp_dir = None
    self._constant_dict = {}
    self._null_location = Location(self)
    self._difile_dict = {}
    self._diloc_dict = {}

  def get_stateless_type(self, ty : type) -> typing.Any:
    if ty in self._stateless_type_dict:
      return self._stateless_type_dict[ty]
    instance = ty(self)
    self._stateless_type_dict[ty] = instance
    return instance
  
  def get_parameterized_type_dict(self, ty : type) -> ParameterizedTypeUniquingDict:
    if ty in self._parameterized_type_dict:
      return self._parameterized_type_dict[ty]
    result = ParameterizedTypeUniquingDict(ty)
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
  
  def get_constant_uniquing_dict(self, ty : type) -> ConstantUniquingDict:
    if ty in self._constant_dict:
      return self._constant_dict[ty]
    result = ConstantUniquingDict(ty)
    self._constant_dict[ty] = result
    return result
  
  def _add_asset_data(self, asset : AssetData):
    # should only be called from the constructor of AssetData
    asset.remove_from_parent()
    self._asset_data_list.push_back(asset)
  
  @property
  def null_location(self) -> Location:
    return self._null_location
  
  def get_DIFile(self, path : str) -> DIFile:
    if path in self._difile_dict:
      return self._difile_dict[path]
    result = DIFile(self, path)
    self._difile_dict[path] = result
    return result
  
  def get_DILocation(self, file : str | DIFile, page : int, row : int, column: int) -> DILocation:
    difile : DIFile = file
    if isinstance(file, str):
      difile = self.get_DIFile(file)
    assert isinstance(difile, DIFile)
    assert difile.context is self
    key = (page, row, column)
    if key in self._diloc_dict:
      return self._diloc_dict[key]
    result = DILocation(difile, page, row, column)
    self._diloc_dict[key] = result
    return result

# ------------------------------------------------------------------------------
# Assets
# ------------------------------------------------------------------------------

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

  # make AssetData usable for dict key
  def __eq__(self, __o: object) -> bool:
    return __o is self
  
  def __hash__(self) -> int:
    return hash(id(self))

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

# ------------------------------------------------------------------------------
# Debug info (DI)
# ------------------------------------------------------------------------------

class DIFile(Location):
  _path : str

  def __init__(self, ctx: Context, path : str) -> None:
    super().__init__(ctx)
    self._path = path
  
  @property
  def filepath(self) -> str:
    return self._path
  
  def __str__(self) -> str:
    return self._path

class DILocation(Location):
  # 描述一个文档位置
  # 对于文档而言，页数可以用 page breaks 来定 （ODF 有 <text:soft-page-break/>）
  # 对于表格而言，页数相当于 sheet 的序号
  # 所有信息如果有的话就从1开始，没有就用0
  # 目前我们的 DILocation 只用于给用户指出位置，暂时不会有源到源的转换，所以这里有信息损失不是大事
  _file : DIFile
  _page : int
  _row : int
  _col : int

  def __init__(self, file : DIFile, page : int, row : int, column : int) -> None:
    ctx = file.context
    super().__init__(ctx)
    self._file = file
    self._page = page
    self._row = row
    self._col = column
  
  @property
  def file(self) -> DIFile:
    return self._file
  
  @property
  def page(self) -> int:
    return self._page
  
  @property
  def row(self) -> int:
    return self._row
  
  @property
  def column(self) -> int:
    return self._col

  def __str__(self) -> str:
    return str(self.file) + '#P' + str(self.page) + ':' + str(self.row) + ':' + str(self.column)

# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------


  
  #@staticmethod
  #def get(value: typing.Any, context : Context) -> typing.Any:
  #  if isinstance(value, int):
  #    return VNConstantInt.get(value, context)
  #  if isinstance(value, bool):
  #    return VNConstantBool.get(value, context)
  #  raise RuntimeError("Unknown value type for constant creation")
  
class ConstantInt(Constant):
  def __init__(self, context : Context, value : int, **kwargs) -> None:
    # should not be called by user code
    assert isinstance(value, int)
    ty = IntType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> int:
    return super().value
  
  @staticmethod
  def get(value : int, context : Context) -> ConstantInt:
    return Constant._get_constant_impl(ConstantInt, value, context)

class ConstantBool(Constant):
  def __init__(self, context : Context, value: bool, **kwargs) -> None:
    assert isinstance(value, bool)
    ty = BoolType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> bool:
    return super().value
  
  @staticmethod
  def get(value : bool, context : Context) -> ConstantBool:
    return Constant._get_constant_impl(ConstantBool, value, context)

class ConstantFloat(Constant):
  def __init__(self, context : Context, value: float, **kwargs) -> None:
    ty = FloatType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> float:
    return super().value
  
  @staticmethod
  def get(value : float, context : Context) -> ConstantFloat:
    return Constant._get_constant_impl(ConstantFloat, value, context)

class ConstantString(Constant):
  # 字符串常量的值不包含样式等信息，就是纯字符串
  def __init__(self, context : Context, value: str, **kwargs) -> None:
    assert isinstance(value, str)
    ty = StringType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> str:
    return super().value
  
  @staticmethod
  def get(value : str, context : Context) -> ConstantString:
    return Constant._get_constant_impl(ConstantString, value, context)

class ConstantTextStyle(Constant):
  # 文字样式常量只包含文字样式信息
  def __init__(self, context : Context, value: tuple[tuple[TextAttribute, typing.Any]], **kwargs) -> None:
    ty = TextStyleType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> tuple[tuple[TextAttribute, typing.Any]]:
    return super().value
  
  @staticmethod
  def get(value : tuple[tuple[TextAttribute, typing.Any]] | dict[TextAttribute, typing.Any], context : Context) -> ConstantTextStyle:
    if isinstance(value, dict):
      value = ConstantTextStyle.get_style_tuple(value)
    assert isinstance(value, tuple)
    return Constant._get_constant_impl(ConstantTextStyle, value, context)
  
  @staticmethod
  def get_style_tuple(styles : dict[TextAttribute, typing.Any]):
    stylelist = []
    for attr, v in styles:
      # 检查样式的值是否符合要求
      # 同时忽略部分VNModel不支持的属性
      isDiscard = False
      match attr:
        case TextAttribute.Bold:
          if v is not None:
            raise RuntimeError("文本属性“加粗”不应该带参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.Italic:
          if v is not None:
            raise RuntimeError("文本属性“斜体”不应该带参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.Hierarchy:
          # VNModel不支持该属性
          isDiscard = True
        case TextAttribute.Size:
          if not isinstance(v, int):
            raise RuntimeError("文本属性“大小”应该带一个整数型参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.TextColor:
          if not isinstance(v, Color):
            raise RuntimeError("文本属性“文本颜色”应该带一个颜色类型的参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.BackgroundColor:
          if not isinstance(v, Color):
            raise RuntimeError("文本属性“背景颜色”应该带一个颜色类型的参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case _:
          isDiscard = True
      if not isDiscard:
        entry_tuple = (attr, v)
        stylelist.append(entry_tuple)
    # 所有样式信息检查完毕后即可开始生成结果
    stylelist.sort()
    styletuple = tuple(stylelist)
    return styletuple
  
  def __len__(self):
    return len(self.value)
  
  def __getitem__(self, attr : TextAttribute) -> typing.Any:
    for e in self.value:
      if e[0] == attr:
        if e[1] is None:
          return True
        return e[1]
    return None

class ConstantTextFragment(Constant, User):
  # 文本常量的值包含字符串以及样式信息（大小字体、字体颜色、背景色（高亮颜色），或是附注（Ruby text））
  # 单个文本片段常量内容所使用的样式需是一致的，如果不一致则可以把内容进一步切分，按照样式来进行分节
  # 文本片段常量的“值”（value）是【对字符串常量的引用】+【样式信息元组】的元组(tuple)
  # 样式信息元组内的每一项都是(样式，值)组成的元组，这些项将根据样式的枚举值进行排序

  def __init__(self, context : Context, string : ConstantString, styles : ConstantTextStyle, **kwargs) -> None:
    # value 应为 ConstantTextFragment.get_value_tuple() 的结果
    ty = TextType.get(context)
    super().__init__(ty = ty, value = (string, styles), **kwargs)
    self.add_operand(string)
    self.add_operand(styles)
  
  @property
  def value(self) -> tuple[ConstantString, ConstantTextStyle]:
    return super().value
  
  @property
  def content(self) -> ConstantString:
    return self.get_operand(0)
  
  @property
  def style(self) -> ConstantTextStyle:
    return self.get_operand(1)
  
  @staticmethod
  def get(context : Context, string : ConstantString, styles : ConstantTextStyle) -> ConstantTextFragment:
    if not isinstance(string, ConstantString):
      raise RuntimeError("string 参数应为对字符串常量的引用")
    if not isinstance(styles, ConstantTextStyle):
      raise RuntimeError("styles 参数应为对文本样式常量的引用")
    return context.get_constant_uniquing_dict(ConstantTextFragment).get_or_create((string, styles), lambda : ConstantTextFragment(context, string, styles))

class ConstantText(Constant, User):
  # 文本常量是一个或多个文本片段常量组成的串

  def __init__(self, context : Context, value: tuple[ConstantTextFragment], **kwargs) -> None:
    ConstantText._check_value_tuple(value)
    ty = TextType.get(context)
    super().__init__(ty, value, **kwargs)
    for frag in value:
      self.add_operand(frag)
  
  @staticmethod
  def _check_value_tuple(value: tuple[ConstantTextFragment]) -> None:
    isCheckFailed = False
    if not isinstance(value, tuple):
      isCheckFailed = True
    else:
      for v in value:
        if not isinstance(v, ConstantTextFragment):
          isCheckFailed = True
    if isCheckFailed:
      raise RuntimeError("文本常量的值应为仅由文本片段常量组成的元组")
  
  @staticmethod
  def get(context : Context, value : typing.Iterable[ConstantTextFragment]) -> ConstantText:
    value_tuple = tuple(value)
    return Constant._get_constant_impl(ConstantText, value_tuple, context)

class ConstantTextList(Constant, User):
  # 文本列表常量对应文档中列表的一层
  def __init__(self, context : Context, value: tuple[ConstantText | ConstantTextList], **kwargs) -> None:
    ty = AggregateTextType.get(context)
    super().__init__(ty, value, **kwargs)
    for element in value:
      self.add_operand(element)
  
  @property
  def value(self) -> tuple[ConstantText | ConstantTextList]:
    return super().value
  
  def __len__(self):
    return len(self.value)
  
  def __getitem__(self, index : int) -> ConstantText | ConstantTextList:
    return self.value.__getitem__(index)
  
  @staticmethod
  def get(context : Context, value : typing.Iterable[ConstantText | ConstantTextList]) -> ConstantTextList:
    value_tuple = tuple(value)
    return Constant._get_constant_impl(ConstantTextList, value_tuple, context)

class ConstantTable(Constant, User):
  def __init__(self, context : Context, nrows : int, ncols : int, value: tuple[tuple[ConstantText]], **kwargs) -> None:
    ty = AggregateTextType.get(context)
    super().__init__(ty = ty, value = (nrows, ncols, value), **kwargs)
    for rows in value:
      for cell in rows:
        self.add_operand(cell)
  
  @property
  def value(self) -> tuple(int, int, tuple[tuple[ConstantText]]):
    return super().value
  
  @property
  def rowcount(self) -> int:
    return self.value[0]
  
  @property
  def columncount(self) -> int:
    return self.value[1]
  
  @property
  def cells(self) -> tuple[tuple[ConstantText]]:
    return self.value[2]
  
  def get_cell(self, row : int, col : int) -> ConstantText:
    return self.value[2][row][col]

  @staticmethod
  def get(context : Context, nrows : int, ncols : int, value: tuple[tuple[ConstantText]]) -> ConstantTable:
    return context.get_constant_uniquing_dict(ConstantTable).get_or_create((nrows, ncols, value), lambda : ConstantTable(context, nrows, ncols, value))

# ------------------------------------------------------------------------------
# IR dumping
# ------------------------------------------------------------------------------

class IRWriter:
  _ctx : Context
  _asset_pin_dict : dict[AssetData, str]
  _asset_export_dict : dict[str, AssetData]
  _asset_export_cache : dict[AssetData, bytes] # exported HTML expression for the asset
  _asset_index_dict : dict[AssetData, int] # index of the asset in the context
  _output_body : io.BytesIO # the <body> part
  _output_asset : io.BytesIO # the <style> part
  _max_indent_level : int # maximum indent level; we need this to create styles for text with different indents
  
  def __init__(self, ctx : Context, asset_pin_dict : dict[AssetData, str], asset_export_dict : dict[str, AssetData] | None) -> None:
    # assets in asset_pin_dict are already exported and we can simply use the mapped value to reference the specified asset
    # if asset_export_dict is not None, the printer expect all remaining assets to be exported with path as key and content as value
    # if asset_export_dict is None, then the printer writes all remaining assets embedded in the export HTML
    # https://stackoverflow.com/questions/38014918/how-to-reuse-base64-image-repeatedly-in-html-file
    self._ctx = ctx
    self._output_body = io.BytesIO()
    self._output_asset = io.BytesIO()
    self._asset_pin_dict = asset_pin_dict
    self._asset_export_dict = asset_export_dict
    self._asset_export_cache = {}
    self._asset_index_dict = None
    self._max_indent_level = 0
    
  def escape(self, htmlstring):
    escapes = {'\"': '&quot;',
              '\'': '&#39;',
              '<': '&lt;',
              '>': '&gt;'}
    # This is done first to prevent escaping other escapes.
    htmlstring = htmlstring.replace('&', '&amp;')
    for seq, esc in escapes.items():
      htmlstring = htmlstring.replace(seq, esc)
    return htmlstring
  
  def _write_body(self, content : str):
    self._output_body.write(content.encode('utf-8'))
  
  def _index_assets(self) -> dict[AssetData, int]:
    if self._asset_index_dict is not None:
      return self._asset_index_dict
    # populate self._asset_index_dict
    self._asset_index_dict = {}
    num = 0
    for asset in self._ctx._asset_data_list:
      self._asset_index_dict[asset] = num
      num += 1
    return self._asset_index_dict
  
  def _emit_asset_reference_to_path(self, asset : AssetData, path : str) -> bytes:
    pass
  
  def _emit_asset(self, asset : AssetData) -> bytes:
    # TODO actually implement this function
    # for now we don't try to emit any asset; just print their ID as a text element and done
    id = self._index_assets()[asset]
    asset_name = type(asset).__name__
    s = "<span class=\"AssetPlaceholder\">#" + hex(id) + " " + asset_name + "</span>"
    return s.encode('utf-8')
    
    # check if we have already exported it
    if asset in self._asset_export_cache:
      return self._asset_export_cache[asset]
    
    # if the asset is already exported (i.e., it is in self._asset_pin_dict), just use the expression there
    if self._asset_pin_dict is not None and asset in self._asset_pin_dict:
      asset_path = self._asset_pin_dict[asset]
      result = self._emit_asset_reference_to_path(asset, asset_path)
      self._asset_export_cache[asset] = result
      return result
    
    # otherwise, if we export the asset as separate files (self._asset_export_dict not None), we do that
    if self._asset_export_dict is not None:
      pass
    # otherwise, we emit the expression in self._output_asset
    pass
  
  def _get_indent_stylename(self, level : int) -> str:
    return 'dump_indent_level_' + str(level)
  
  def _get_operation_short_name(self, op : Operation) -> str:
    return '[' + hex(id(op)) + ' ' + type(op).__name__ + ']\"' + op.name + '"'
  
  def _get_text_style_str(self, style : ConstantTextStyle) -> str:
    value : tuple[tuple[TextAttribute, typing.Any]] = style.value
    result = '('
    for t in value:
      attr = t[0]
      v = t[1]
      match attr:
        case TextAttribute.Bold if v == True:
          result += 'bold,'
        case TextAttribute.Italic if v == True:
          result += 'italic,'
        case TextAttribute.Size if isinstance(v, int):
          result += 'size=' + str(v) + ','
        case TextAttribute.TextColor if isinstance(v, Color):
          result += 'textcolor=' + str(v) + ','
        case TextAttribute.BackgroundColor  if isinstance(v, Color):
          result += 'backgroundcolor=' + str(v) + ','
        case _:
          result += 'UnknownAttribute[' + str(attr) + ':' + str(v) + '],'
    result += ')'
    return result
  
  def _walk_value(self, value : Value) -> bytes | None:
    # write the current value to body. if the content is too big (e.g., a table), a stub is written first and the return value is the full content
    # we must be in a <p> element
    if isinstance(value, OpResult):
      self._write_body(self.escape(self._get_operation_short_name(value.parent) + '.' + value.name))
      return None
    if isinstance(value, BlockArgument):
      raise NotImplementedError('TODO')
    if isinstance(value, Constant):
      if isinstance(value, ConstantBool):
        if value.value == True:
          self._write_body('true')
        else:
          self._write_body('false')
        return None
      elif isinstance(value, ConstantFloat):
        self._write_body(self.escape(str(value.value)))
        return None
      elif isinstance(value, ConstantInt):
        self._write_body(self.escape(str(value.value)))
        return None
      elif isinstance(value, ConstantString):
        self._write_body(self.escape('"' + value.value + '"'))
        return None
      elif isinstance(value, ConstantTextFragment):
        self._write_body(self.escape('TextFrag["' + value.content.value + '",' + self._get_text_style_str(value.style) + ']'))
        return None
      elif isinstance(value, ConstantTextStyle):
        self._write_body(self.escape(self._get_text_style_str(value)))
        return None
      elif isinstance(value, ConstantText):
        self._write_body(self.escape('Text{'))
        for u in value.operanduses():
          res = self._walk_value(u.value)
          assert res is None
          self._write_body(',')
        self._write_body(self.escape('}'))
        return None
      elif isinstance(value, ConstantTextList):
        raise NotImplementedError('TODO')
      elif isinstance(value, ConstantTable):
        raise NotImplementedError('TODO')
      else:
        raise NotImplementedError('Unexpected constant type for dumping')
    # unknown value types
    self._write_body(self.escape('[#' + str(id(value)) + ' ' + type(value).__name__ + ']'))
    return None
  
  def _walk_operation(self, op : Operation, level : int) -> None:
    # [#<id> ClassName]"Name"(operand=...) -> (result)[attr=...]<loc>
    #   <regions>
    self._write_body('<p class=\"' + self._get_indent_stylename(level) + '">')
    self._write_body(self.escape(self._get_operation_short_name(op))) # [#<id> ClassName]"Name"
    
    # operands
    self._write_body(self.escape('('))
    isFirst = True
    for operand_name in op.operands:
      operand = op.get_operand_inst(operand_name)
      if isFirst:
        isFirst = False
      else:
        self._write_body(',')
      self._write_body(self.escape(operand_name+'=['))
      numvalues = operand.get_num_operands()
      isFirstValue = True
      for i in range(0, numvalues):
        if isFirstValue:
          isFirstValue = False
        else:
          self._write_body(',')
        delayed_content = self._walk_value(operand.get_operand(i))
        if delayed_content is not None:
          raise NotImplementedError('TODO')
      self._write_body(self.escape(']'))
    self._write_body(self.escape(')'))
    
    # results
    if not op.results.empty:
      self._write_body(self.escape('->('))
      isFirst = True
      for result_name in op.results:
        if isFirst:
          isFirst = False
        else:
          self._write_body(',')
        rv = op.results[result_name]
        self._write_body(self.escape(str(rv.valuetype) + ' ' + result_name))
      self._write_body(self.escape(')'))
    
    # attributes
    if not op.attributes.empty:
      self._write_body(self.escape('['))
      isFirst = True
      for attribute_name in op.attributes:
        if isFirst:
          isFirst = False
        else:
          self._write_body(',')
        attr = op.get_attr(attribute_name)
        self._write_body(self.escape(attribute_name + '=' + str(attr.value)))
      self._write_body(self.escape(']'))
    
    # loc
    self._write_body(self.escape('<' + str(op.location) + '>'))
    self._write_body('</p>\n')
    
    # TODO write terminator info
    
    # regions
    body_level = level + 2
    if self._max_indent_level < body_level:
      self._max_indent_level = body_level
    
    for r in op.regions:
      self._write_body('<p class=\"' + self._get_indent_stylename(level) + '">')
      self._write_body(self.escape(r.name + ':') + '</p>\n')
      for b in r.blocks:
        self._write_body('<p class=\"' + self._get_indent_stylename(level+1) + '">')
        body_header = '<anon>'
        if len(b.name) > 0:
          body_header = '"' + b.name + '"'
        
        # now prepare body arguments
        arg_name_list = []
        for arg in b.arguments():
          if len(arg.name) == 0:
            arg_name_list.append('<anon>')
          else:
            arg_name_list.append(arg.name)
        body_header = hex(id(b)) + ' ' + body_header + '(' + ','.join(arg_name_list) + '):'
        self._write_body(self.escape(body_header))
        self._write_body('</p>\n')
        for o in b.body:
          self._walk_operation(o, body_level)
        
    # done!
    return None
  
  def print(self, op : Operation) -> bytes:
    # perform an HTML export with op as the top-level Operation. The return value is the HTML
    content = io.BytesIO()
    content.write(b'''<!DOCTYPE html>
<html>
<head>
''')
    title = 'Anonymous dump'
    if len(op.name) > 0:
      title = op.name
      assert isinstance(title, str)
    content.write(b'<title>' + title.encode('utf-8') + b'</title>')
    self._output_asset.write(b'<style>\n')
    self._output_asset.write(b'''.AssetPlaceholder {
  border-width: 1px;
  border-style: solid;
  border-color: black;
  text-align: center;
}
''')
    self._output_body.write(b'<body>\n')
    self._walk_operation(op, 0)
    self._output_body.write(b'</body>')
    
    # write styles for indent levels
    for curlevel in range(0, self._max_indent_level):
      stylestr = 'p.' + self._get_indent_stylename(curlevel) + '{ text-indent: ' + str(curlevel * 15) + 'px}\n'
      self._output_asset.write(stylestr.encode())
    self._output_asset.write(b'</style>')
    content.write(self._output_asset.getbuffer())
    content.write(self._output_body.getbuffer())
    content.write(b'</html>\n')
    return content.getvalue()

def _dump_operation_impl(op : Operation) -> None:
  raise NotImplementedError('Use view() instead')

def _view_operation_impl(op : Operation) -> None:
  writer = IRWriter(op.context, None, None)
  dump = writer.print(op)
  file = tempfile.NamedTemporaryFile('w+b', suffix='_viewdump.html', prefix='preppipe_', delete=False)
  file.write(dump)
  file.close()
  path = os.path.abspath(file.name)
  print('Opening HTML dump at ' + path)
  webbrowser.open_new_tab('file:///' + path)

# ------------------------------------------------------------------------------
# IR verification
# ------------------------------------------------------------------------------

class IRVerifier:
  _ostream : typing.Any # either a file-like object that we can write(), or None, in which case we just print
  _error_encountered : bool
  
  def __init__(self, ostream) -> None:
    self._ostream = ostream
    self._error_encountered = False
  
  def _report_error(self, msg : str):
    if self._ostream is not None:
      self._ostream.write(msg + '\n')
    else:
      print(msg)
    self._error_encountered = True
  
  def verify(self, op : Operation) -> bool:
    # verify the input operation; return True if error found, false otherwise
    # TODO
    return self._error_encountered
  
  @staticmethod
  def verifyOperation(op : Operation, ostream) -> bool:
    verifier = IRVerifier(ostream)
    return verifier.verify(op)