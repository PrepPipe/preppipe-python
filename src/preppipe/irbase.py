# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
import enum
import dataclasses
import llist
import collections
import collections.abc

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
  def __init__(self) -> None:
    super().__init__()
  
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

  def __init__(self) -> None:
    super().__init__()
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
  def __repr__(self) -> str:
    return type(self).__name__
  
  def __str__(self) -> str:
    return type(self).__name__

class BlockReferenceType(ValueType):
  def __init__(self) -> None:
    super().__init__()
  
  @staticmethod
  def get(ctx : Context) -> BlockReferenceType:
    return ctx.get_stateless_type(BlockReferenceType)

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
  _loc : Location
  _uselist : IList[Use]

  def __init__(self, ty : ValueType, loc : Location) -> None:
    super().__init__()
    self._type = ty
    self._loc = loc
    self._uselist = IList(self)
  
  @property
  def uses(self) -> IList[Use]:
    return self._uselist
  
  def use_empty(self) -> bool:
    return self._uselist.empty
  
  @property
  def valuetype(self) -> ValueType:
    return self._type
  
  @property
  def location(self) -> Location:
    return self._loc
  
  def replace_all_uses_with(self, v : Value) -> None:
    assert self._type == v._type
    self._uselist.merge_into(v._uselist)
  
  def __str__(self) -> str:
    result = str(self._type) + ' ' + type(self).__name__
    if self._loc is not None:
      result += ' @ ' + str(self._loc)
    return result

class NameReferencedValue(Value, NameDictNode):
  def __init__(self, ty: ValueType, loc: Location) -> None:
    super().__init__(ty, loc)
  
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

  def __init__(self) -> None:
    super().__init__()
    self._uselist = []
  
  def get_operand(self, index : int) -> Value:
    return self._uselist[index].value
  
  def set_operand(self, index : int, value : Value) -> None:
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
  def __init__(self, ty: ValueType, loc : Location) -> None:
    super().__init__(ty, loc)
  
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
  def __init__(self, ty: ValueType, loc: Location) -> None:
    super().__init__(ty, loc)

# reference: https://mlir.llvm.org/doxygen/classmlir_1_1Operation.html
class Operation(IListNode):
  _name : str
  _loc : Location
  _operands : NameDict[OpOperand]
  _results : NameDict[OpResult]
  _attributes : NameDict[Attribute]
  _regions : NameDict[Region]
  _terminator_info : OpTerminatorInfo

  def __init__(self, name : str, loc : Location, is_terminator : bool) -> None:
    super().__init__()
    self._name = name
    self._loc = loc
    self._operands = NameDict(self)
    self._results = NameDict(self)
    self._attributes = NameDict(self)
    self._terminator_info = None
    if is_terminator:
      self._terminator_info = OpTerminatorInfo(self)
  
  def _add_result(self, name : str, ty : ValueType, loc : Location) -> OpResult:
    r = OpResult(ty, loc)
    self._results[name] = r
    return r
  
  def _add_operand(self, name : str) -> OpOperand:
    o = OpOperand()
    self._operands[name] = o
    return o
  
  def _add_operand_with_value(self, name : str, value : Value) -> OpOperand:
    o = self._add_operand(name)
    o.add_operand(value)
  
  def _add_operand_with_value_list(self, name : str, values : typing.Iterable[Value]) -> OpOperand:
    o = self._add_operand(name)
    for v in values:
      o.add_operand(v)
  
  def set_attr(self, name : str, value: typing.Any):
    a = Attribute(value)
    self._attributes[name] = a
  
  def get_attr(self, name : str) -> Attribute:
    return self._attributes[name]
  
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
  _loc : Location
  _name : str

  def __init__(self, name : str, loc : Location) -> None:
    ty = BlockReferenceType.get(loc.context)
    super().__init__(ty, loc)
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
  
  def add_argument(self, ty : ValueType, loc : Location):
    arg = BlockArgument(ty, loc)
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

  def get_stateless_type(self, ty : type) -> typing.Any:
    if ty in self._stateless_type_dict:
      return self._stateless_type_dict[ty]
    instance = ty()
    self._stateless_type_dict[ty] = instance
    return instance

