# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
import enum
import dataclasses
import collections
import collections.abc
import decimal
import tempfile
import os
import pathlib
import shutil
import webbrowser
import io
import abc
import json
import hashlib
import mimetypes
import base64

import PIL.Image
import pydub
import bidict
import llist

from .commontypes import TextAttribute, Color
from ._version import __version__
from .util.audit import *
from .exceptions import *

# ------------------------------------------------------------------------------
# ADT needed for IR
# ------------------------------------------------------------------------------

T = typing.TypeVar('T')

# we create our own list type here because of the following reasons:
# 1. IDE (e.g., VSCode) may not be able to get information from llist module for auto-completion, etc
# 2. Certain API is easy to misuse for our use case (we will subclass the nodes)
#    For example:
#       * llist.dllist.insert(), etc will create NEW nodes instead of directly using the node passed in, and this is not what we want
#       * iterating over a dllist is getting the VALUE on the nodes, instead of getting the nodes

_IListNodeTypeVar = typing.TypeVar('_IListNodeTypeVar', bound='IListNode')
class IList(typing.Generic[_IListNodeTypeVar, T], llist.dllist):
  # __slots__ = ('_parent')
  _parent : typing.Any
  def __init__(self, parent : T) -> None:
    super().__init__()
    self._parent = parent

  @property
  def parent(self) -> T:
    return self._parent

  @property
  def size(self) -> int:
    return super().size

  @property
  def front(self) -> _IListNodeTypeVar:
    # return the first node if available, None if not
    return super().first

  @property
  def empty(self) -> bool:
    return super().first is None

  @property
  def back(self) -> _IListNodeTypeVar:
    # return the last node if available, None if not
    return super().last

  def insert(self, where : _IListNodeTypeVar, node : _IListNodeTypeVar):
    assert isinstance(node, IListNode)
    super().insertnodebefore(node, where)
    node.node_inserted(self.parent)

  def push_back(self, node : _IListNodeTypeVar):
    assert isinstance(node, IListNode)
    super().appendnode(node)
    node.node_inserted(self.parent)

  def push_front(self, node : _IListNodeTypeVar):
    assert isinstance(node, IListNode)
    super().insertnodebefore(node, super().first)
    node.node_inserted(self.parent)

  def get_index_of(self, node : _IListNodeTypeVar) -> int:
    # -1 if node not found, node index if found
    assert isinstance(node, IListNode)
    cur_index = 0
    cur_node = self.front
    while cur_node is not None:
      assert isinstance(cur_node, IListNode)
      if cur_node is node:
        return cur_index
      # pylint: disable=no-member
      cur_node = cur_node.next
      cur_index += 1
    return -1

  def merge_into(self, dest : IList[_IListNodeTypeVar, T]):
    assert isinstance(dest, IList)
    while self.front is not None:
      v = self.front
      assert isinstance(v, IListNode)
      # pylint: disable=no-member
      v.node_removed(self.parent)
      super().remove(v)
      dest.push_back(v)

  def __iter__(self) -> IListIterator[_IListNodeTypeVar]:
    return IListIterator(super().first)

  # pylint: disable=invalid-length-returned
  def __len__(self) -> int:
    assert self.size >= 0
    return self.size

  def __getitem__(self, index : int) -> _IListNodeTypeVar:
    return super().__getitem__(index)

  def clear(self):
    while self.front is not None:
      v = self.front
      assert isinstance(v, IListNode)
      # pylint: disable=no-member
      v.node_removed(self.parent)
      super().remove(v)

class IListIterator(typing.Generic[_IListNodeTypeVar]):
  # __slots__ = ('_node')

  _node : _IListNodeTypeVar

  def __init__(self, n : _IListNodeTypeVar) -> None:
    super().__init__()
    self._node = n

  def __next__(self) -> _IListNodeTypeVar:
    if self._node is None:
      raise StopIteration
    curnode = self._node
    self._node = curnode.next
    assert isinstance(curnode, IListNode)
    # 大部分情况下我们使用结点本身作为列表的值
    # 不过某些场景（比如 util.graphtrait）我们使用额外的 IListNode 来使同一实例出现在多个列表中
    # 这时我们需要使用结点上挂的 value 来作为实际值
    # 但是有时我们的 IListNode 的子类也会用 value 属性
    # 所以我们这里特判，只有以下情况使用 value 值，其余情况用结点本身：
    # 1. 当前结点不是 IListNode 的子类
    # 2. 当前结点有 value
    if type(curnode) in (IListNode, llist.dllistnode):
      if v := curnode.value:
        return v
    return curnode

# if the list intends to be mutable, element node should inherit from this class
# otherwise, just inheriting from llist.dllistnode is fine
class IListNode(typing.Generic[_IListNodeTypeVar], llist.dllistnode):
  # __slots__ = ()

  def __init__(self, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(**kwargs)

  def _try_get_owner(self) -> IList | None:
    # first, weakref itself can be None if it never referenced another object
    # second, weakref may lose reference to the target
    # we use this function to dereference a weakref
    if self.owner is not None:
      return self.owner()
    return None

  # pylint: disable=protected-access
  def insert_before(self, ip : IListNode[_IListNodeTypeVar]) -> None:
    assert isinstance(ip, IListNode)
    owner = self._try_get_owner()
    ipowner = ip._try_get_owner()
    assert ipowner is not None
    if owner is not None:
      self.node_removed(self.parent)
      # pylint: disable=no-member
      owner.remove(self)
    self.node_inserted(self.parent)
    ipowner.insertnode(self, ip)

  # erase_from_parent() includes self cleanup; it should be defined in derived classes
  def remove_from_parent(self):
    owner = self._try_get_owner()
    if owner is not None:
      self.node_removed(self.parent)
      # pylint: disable=no-member
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
  def prev(self) -> _IListNodeTypeVar:
    return super().prev

  @property
  def next(self) -> _IListNodeTypeVar:
    return super().next

  @property
  def parent(self) -> IList[_IListNodeTypeVar, typing.Any] | None:
    # return the parent of the list
    # to get a type hint, override this method in derived class to add it
    owner = self._try_get_owner()
    if owner is not None:
      # pylint: disable=no-member
      return owner.parent
    return None

  def get_index(self):
    owner = self._try_get_owner()
    assert owner is not None
    # pylint: disable=no-member
    return owner.get_index_of(self)

_NameDictNodeTypeVar = typing.TypeVar('_NameDictNodeTypeVar', bound='NameDictNode')
class NameDict(collections.abc.MutableMapping[str, _NameDictNodeTypeVar], typing.Generic[_NameDictNodeTypeVar]):
  # __slots__ = ('_parent', '_dict')
  _parent : typing.Any
  _dict : collections.OrderedDict[str, _NameDictNodeTypeVar]

  def __init__(self, parent : typing.Any) -> None:
    super().__init__()
    self._parent = parent
    self._dict = collections.OrderedDict()

  def __contains__(self, key : str) -> bool:
    return self._dict.__contains__(key)

  def __getitem__(self, key : str) -> _NameDictNodeTypeVar:
    return self._dict.__getitem__(key)

  def __setitem__(self, key : str, value : _NameDictNodeTypeVar) -> None:
    if value.dictref is not None:
      raise PPInternalError("Inserting one node into more than one NameDict")
    self._dict[key] = value
    value._update_parent_info(self, key) # type: ignore

  def __delitem__(self, key : str):
    value = self._dict[key]
    value._update_parent_info(None, "")
    del self._dict[key]

  def __iter__(self):
    return iter(self._dict)

  def __reversed__(self):
    return reversed(self._dict)

  def __len__(self):
    return len(self._dict)

  @property
  def empty(self):
    return len(self._dict) == 0

  @property
  def parent(self):
    return self._parent

class NameDictNode(typing.Generic[_NameDictNodeTypeVar]):
  # 因为我们想要保证 Value 可以用 slots，但该类可能与 Value 同时被继承（比如 OpResult），所以这里不加 slots
  _dictref : NameDict[_NameDictNodeTypeVar] | None
  _name : str

  def __init__(self, **kwargs) -> None:
    # passthrough kwargs for cooperative multiple inheritance
    super().__init__(**kwargs)
    self._dictref = None
    self._name = ""

  @property
  def name(self) -> str:
    return self._name

  def _update_parent_info(self, parent: NameDict[_NameDictNodeTypeVar] | None, name : str) -> None:
    self._dictref = parent
    self._name = name

  def remove_from_parent(self):
    if self.dictref is not None:
      del self.dictref[self.name]
    #self.dictref.__delitem__(self.name)

  @property
  def dictref(self) -> NameDict[_NameDictNodeTypeVar] | None:
    return self._dictref

  @property
  def parent(self) -> typing.Any :
    if self._dictref is not None:
      return self._dictref.parent
    return None


# ------------------------------------------------------------------------------
# IR classes
# ------------------------------------------------------------------------------

class IRObjectInitMode(enum.Enum):
  CONSTRUCT = enum.auto() # 从零开始构造一个新对象
  COPY = enum.auto() # 复制一个现成的对象
  IMPORT_JSON = enum.auto() # 导入之前保存的 JSON

_IRObjectTypeVar = typing.TypeVar('_IRObjectTypeVar', bound='IRObject')
class IRObject:
  # （除了 Context 和基础类型之外的）IR 对象的基类
  # 提供此类的主要目的是将对象的创建过程统一

  # 帮助部分元数据、常量等去掉 __dict__
  # 使用 slots 之后我们仍然可以在类外给类做类似添加成员函数等操作，因为这些改的是类对象，而不是类实例
  # 。。现在先不用 slots，问题太多
  # __slots__ = ()

  # 从JSON字符串名字到类型的映射
  # 注意，这里不仅会有 IRObject 的子类，还会有外部的类型
  # 像 User 这种 IR 内部的类也会在这里
  # 我们要求如果类型不是 IRObject 的子类，则该类型必须无状态，要么不创建实例要么可以用cls()的方式创建实例
  json_name_dict : typing.ClassVar[dict[str, type]] = {}

  # 如果 IR 中的一个类型满足以下条件：
  # 1. 不会被用户代码继承
  # 2. 所有实例出现的地方一定不需要类型
  # 那么可以用 JSON_NAME_NOT_USED 作为 @IRObjectJsonTypeName 的类型标识
  # (现在只有 OpResult 使用)
  JSON_NAME_NOT_USED : typing.ClassVar[str] = '---'

  # 这是一个应该由 @IRObjectJsonTypeName 设置的值
  JSON_TYPE_NAME : typing.ClassVar[str]

  # 由于 Python 不像 C++ 那样支持多个构造函数，我们在这里提供我们所需要的 不同构造函数的接口
  # ****** 该函数不应该被覆盖 ******
  def __init__(self, *, init_mode : IRObjectInitMode, context : Context, **kwargs) -> None:
    self.base_init(init_mode=init_mode, context=context, **kwargs)
    match init_mode:
      case IRObjectInitMode.CONSTRUCT:
        self.construct_init(init_mode=init_mode, context=context, **kwargs)
      case IRObjectInitMode.COPY:
        self.copy_init(init_mode=init_mode, context=context, **kwargs)
      case IRObjectInitMode.IMPORT_JSON:
        self.json_import_init(init_mode=init_mode, context=context, **kwargs)
    self.post_init()

  def base_init(self, **kwargs) -> None:
    # 如果该对象继承了不属于 IRObject 的其他类型，那么这是调用它们构造函数的地方
    super().__init__()

  def construct_init(self, **kwargs) -> None:
    # 创建一个新的、空的对象
    pass

  def copy_init(self, *, init_src : IRObject, value_mapper : IRValueMapper, **kwargs) -> None:
    # 从一个相同类型的对象那里复制出一个新的
    # 该函数只应该由 IR 基础类实现，用户类不应该覆盖
    # value_mapper 用来保存被复制的值的映射关系（旧值到新值），如果我们复制一个有内部区块的操作项，内部的值有依赖关系，
    # 那么就需要用 value_mapper 使复制出来的操作项用上复制出来的值（而不是原来操作项里的值）
    pass

  def post_copy_value_remap(self, *, value_mapper : IRValueMapper, **kwargs) -> None:
    pass

  def json_import_init(self, *, importer : IRJsonImporter, init_src : dict, **kwargs) -> None:
    # 从保存的 JSON 那里恢复该对象
    # 该函数只应该由 IR 基础类实现，用户类不应该覆盖
    pass

  def post_init(self) -> None:
    # 主要是给用户定义的子类的，用于添加各种不进入存档的临时数据
    # 注意，在该函数被调用时，我们只知道该对象的基本属性、内容已完成初始化，
    # 我们不确定子对象或是其他引用的对象是否已经初始化
    pass

  def json_export_impl(self, *, exporter : IRJsonExporter, dest : dict, **kwargs) -> None:
    if 'JSON_TYPE_NAME' not in type(self).__dict__:
      raise PPInternalError('Type '+ type(self).__name__ + ' not registered with @IRObjectJsonTypeName("<name>") decorator')
    json_name = type(self).__dict__['JSON_TYPE_NAME']
    if json_name != IRObject.JSON_NAME_NOT_USED:
      dest[IRJsonRepr.ANY_TYPE.value] = json_name

  @classmethod
  def json_export_type_action(cls, exporter : IRJsonExporter, type_obj : dict):
    # 当我们在 IR JSON 输出中注册类型时，如果有什么额外的数据需要保存，我们可以在这做
    pass

  @property
  @abc.abstractmethod
  def context(self) -> Context:
    raise PPInternalError("context attribute not overriden by derived class")

  def clone(self : _IRObjectTypeVar, value_mapper : IRValueMapper | None = None) -> _IRObjectTypeVar:
    if value_mapper is None:
      value_mapper = IRValueMapper(self.context, option_ignore_values_with_no_use=True)
    result = self.__class__(init_mode = IRObjectInitMode.COPY, context=self.context, init_src=self, value_mapper=value_mapper)
    if value_mapper.is_require_value_remap():
      result.post_copy_value_remap(value_mapper=value_mapper)
    return result

  def json_export(self, exporter : IRJsonExporter | None = None) -> dict:
    if exporter is None:
      exporter = IRJsonExporter(self.context)
    toplevel = {}
    self.json_export_impl(exporter=exporter, dest=toplevel)
    return toplevel

def _register_json_type_name(cls : type, name : str):
  if name != IRObject.JSON_NAME_NOT_USED:
    assert name not in IRObject.json_name_dict
    IRObject.json_name_dict[name] = cls
  setattr(cls, 'JSON_TYPE_NAME', name)

def IRObjectJsonTypeName(name : str):
  '''使 IRObject 可以在 JSON 中表示。name 将是该类在 JSON 中的名称。'''
  assert isinstance(name, str) and len(name) > 0
  def inner_regr(cls : typing.Type[_IRObjectTypeVar]) -> typing.Type[_IRObjectTypeVar]:
    _register_json_type_name(cls, name)
    return cls
  return inner_regr

def _IRInnerConstructJsonTypeName(name : str):
  assert isinstance(name, str) and len(name) > 0
  def inner_regr(cls):
    _register_json_type_name(cls, name)
    return cls
  return inner_regr

def IRWrappedStatelessClassJsonName(name : str):
  '''使非 IRObject 的类型可以在 JSON 中表示。name 将是该类在 JSON 中的名称。
  用于 ClassLiteral 和 EnumLiteral 中的类会需要这个修饰符.

  被修饰的类型要么不会有实例（比如 ClassLiteral 中只需要取得类型对象即可），
  要么可以以已知的方式创建实例（比如 EnumLiteral）
  '''
  assert isinstance(name, str) and len(name) > 0
  def inner_regr(cls):
    assert not issubclass(cls, IRObject)
    _register_json_type_name(cls, name)
    return cls
  return inner_regr

class IRJsonRepr(enum.Enum):
  # 对象的一些值在 JSON 对象中所使用的键 (key)
  # 为了保证无歧义，即使对象类型不同，我们在这里也不会复用
  # 通用部分
  ANY_NAME  = 'name' # 所有的名称（包括操作项的，区的，或是其他）都使用这个
  ANY_TYPE  = 'type' # 类型标识
  ANY_BODY  = 'body'
  ANY_KIND  = 'kind'
  ANY_FLOAT = 'float' # 一个 decimal.Decimal 类型的值
  ANY_REF   = 'ref' # 一个对元数据 (Metadata) 或值类型 (ValueType)的引用值
  FLOAT_SIGN      = 'sign'
  FLOAT_DIGIT     = 'digit'
  FLOAT_EXPONENT  = 'exponent'

  # 专有部分
  LOCATION_FILE_PATH = 'file_path'
  TYPE_PARAMETERIZED_PARAM = 'type_param'
  VALUE_VALUETYPE = 'vty' # the type of the value
  VALUE_VALUEID   = 'vid' # an ID representing the value
  OP_LOCATION   = 'loc'
  OP_REGION     = 'region'
  OP_OPERAND    = 'operand'
  OP_RESULT     = 'result'
  OP_ATTRIBUTE  = 'attr'
  OP_METADATA   = 'md'
  USER_VALUELIST  = 'user_values'
  BLOCK_ARGUMENT = 'arg'
  MDLIKE_VALUEKIND_TYPE = 'm_type'
  MDLIKE_VALUEKIND_REF  = 'm_ref'
  VALUE_KIND_LITERALEXPR = 'literalexpr'
  VALUE_KIND_CONSTEXPR = 'constexpr'
  VALUE_KIND_MISC_LITERAL = 'literal' # 除整数、字符串、逻辑值、浮点数之外的字面值

  TEXTATTR_BOLD           = 'ts_bold'
  TEXTATTR_ITALIC         = 'ts_italic'
  TEXTATTR_SIZE           = 'ts_size'
  TEXTATTR_TEXTCOLOR      = 'ts_textcolor'
  TEXTATTR_HIGHLIGHTCOLOR = 'ts_highlightcolor'

class IRJsonExporter:
  # 每个实例对应一个 JSON 导出文件，管理其中需要去重或特殊处理的内容
  # 一个导出文件里可能包含不止一个顶层操作项
  context : Context
  base_types : set[type] # 包含所有（不需要额外注释的）基础类型
  type_dict : dict[type, str] # 从类型对象到 JSON 导出时所使用的的类型名；加在里面的都是加过类型注释的
  md_dict : dict[Metadata, int] # 从元数据对象到元数据结点 ID 的映射
  vty_dict : dict[ValueType, str] # 从值类型到表达值的映射
  vty_index_dict : dict[type, int] # 对于每个值类型，下一个下标应该是多少
  value_index_dict : dict[Value, int] # 每个（非字面值等的）值的索引
  protocol_ver : int # 协议版本
  output_type_dict : dict[str, typing.Any] # (要放到结果里的) Python 类型标注
  output_metadata_list : list # 元数据列表
  output_valuetype_dict : dict # 值类型（不是 Python 类型）（一般是类型名+数值后缀）

  def __init__(self, context : Context) -> None:
    self.context = context
    self.base_types = set()
    self.type_dict = {}
    self.md_dict = {}
    self.vty_dict = {}
    self.vty_index_dict = {}
    self.value_index_dict = {}
    self.protocol_ver = 0
    self.output_type_dict = {}
    self.output_metadata_list = []
    self.output_valuetype_dict = {}
    self.init_protocol_0()

  def add_base_type(self, ty : typing.Type[IRObject]):
    json_name = ty.JSON_TYPE_NAME
    assert isinstance(json_name, str)
    self.type_dict[ty] = json_name

  def get_type_str(self, ty : type) -> str:
    if ty in self.type_dict:
      return self.type_dict[ty]
    # 如果碰到一个没见过的类型，那么我们需要把他注册到 output_type_dict 里面
    assert issubclass(ty, IRObject)
    if 'JSON_TYPE_NAME' not in ty.__dict__:
      raise PPInternalError('Type not registered with @IRObjectJsonTypeName("<object_json_name>"): ' + ty.__name__)
    json_name = getattr(ty, 'JSON_TYPE_NAME')
    assert isinstance(json_name, str)
    # 把类型所有的直接父类列出来
    bases = []
    for parent in ty.__bases__:
      parent_ty_name = self.get_type_str(parent)
      bases.append(parent_ty_name)

    # 我们要求所有类型只能继承自 IRBase 中定义的基本类型
    # 如果有 IRBase 中的类型没有加到 JSON 基础类型中，我们想找到这些情况
    assert len(bases) > 0

    type_obj = {}
    type_obj["base"] = bases
    # 如果类型有其他东西需要加，就在这里加上
    ty.json_export_type_action(exporter=self, type_obj=type_obj)
    self.output_type_dict[json_name] = type_obj
    return json_name

  def emit_float(self, value : decimal.Decimal) -> dict:
    value_tuple = value.as_tuple() # (sign : 0/1, digits: tuple[int], exponent: int) --> json array
    out_value = {
      IRJsonRepr.ANY_KIND.value       : IRJsonRepr.ANY_FLOAT.value,
      IRJsonRepr.FLOAT_SIGN.value     : value_tuple.sign,
      IRJsonRepr.FLOAT_DIGIT.value    : value_tuple.digits,
      IRJsonRepr.FLOAT_EXPONENT.value : value_tuple.exponent
    }
    return out_value

  def _emit_metadata_like_value(self, value : typing.Any, toplevel_type : type) -> typing.Any:
    if isinstance(value, (int, bool, str)):
      return value
    if isinstance(value, decimal.Decimal):
      return self.emit_float(value)
    if isinstance(value, type):
      result = {}
      result[IRJsonRepr.ANY_KIND.value] = IRJsonRepr.MDLIKE_VALUEKIND_TYPE.value
      result[IRJsonRepr.ANY_TYPE.value] = self.get_type_str(value)
      return result
    if isinstance(value, toplevel_type):
      ref = None
      if toplevel_type is Metadata:
        ref = self.get_metadata_id(value)
      elif toplevel_type is ValueType:
        ref = self.get_value_type_repr(value)
      else:
        raise PPInternalError('Unexpected toplevel type for metadata value: ' + str(toplevel_type))
      result = {}
      result[IRJsonRepr.ANY_KIND.value] = IRJsonRepr.MDLIKE_VALUEKIND_REF.value
      result[IRJsonRepr.ANY_REF.value] = ref
      return result
    # 到这里的话就不是基础类型了
    # 检查是否是元组
    if isinstance(value, tuple):
      result = []
      for v in value:
        result.append(self._emit_metadata_like_value(v, toplevel_type))
      return result
    # 暂不支持其他类型
    raise PPInternalError('Unexpected value type')


  def export_metadata_like_object(self, obj : Metadata | ValueType) -> dict:
    assert dataclasses.is_dataclass(obj)
    toplevel_type = None
    if isinstance(obj, Metadata):
      toplevel_type = Metadata
    elif isinstance(obj, ValueType):
      toplevel_type = ValueType
    else:
      raise PPInternalError('Unexpected metadata-like type: ' + type(obj).__name__)
    data = {}
    for field in dataclasses.fields(obj):
      value = getattr(obj, field.name)
      # ignore context fields
      if isinstance(value, Context):
        assert value is self.context
        continue
      data[field.name] = self._emit_metadata_like_value(value, toplevel_type)
    type_str = self.get_type_str(type(obj))
    return {IRJsonRepr.ANY_TYPE.value : type_str, IRJsonRepr.ANY_BODY.value : data}

  def get_metadata_id(self, md : Metadata) -> int:
    if md in self.md_dict:
      return self.md_dict[md]
    # 需要把该元数据加到输出里
    dest_dict = self.export_metadata_like_object(md)
    index = len(self.output_metadata_list)
    self.output_metadata_list.append(dest_dict)
    self.md_dict[md] = index
    return index

  def emit_color(self, c : Color) -> str:
    return c.get_string()

  def get_value_repr(self, value : Value) -> dict | str | int | bool:
    # 该函数是在导出对值的引用（不是定义）时调用的

    if not isinstance(value, (Literal, ConstExpr)):
      # 如果不是这类常量的话我们生成一个对值的引用就完事了
      result_dict = {}
      result_dict[IRJsonRepr.ANY_KIND.value] = IRJsonRepr.ANY_REF.value
      result_dict[IRJsonRepr.ANY_REF.value] = self.get_value_id(value)
      return result_dict

    # 以下所有情况都需要使用类型标识
    if 'JSON_TYPE_NAME' not in type(value).__dict__:
      raise PPInternalError('Value type ' + type(value).__name__ + ' not decorated with @IRObjectJsonTypeName("<name>")')
    json_name = type(value).__dict__['JSON_TYPE_NAME']

    # 资源的话我们需要另起一个类似 Metadata-like 区域来存放，暂不支持
    if isinstance(value, AssetData):
      raise PPNotImplementedError()

    # 处理复合值的情况
    if isinstance(value, (LiteralExpr, ConstExpr)):
      result_dict = {}
      value_kind = None
      if isinstance(value, LiteralExpr):
        value_kind = IRJsonRepr.VALUE_KIND_LITERALEXPR
      else:
        value_kind = IRJsonRepr.VALUE_KIND_CONSTEXPR
      result_dict[IRJsonRepr.ANY_KIND.value] = value_kind.value
      result_dict[IRJsonRepr.ANY_TYPE.value] = json_name
      body_array = []
      for v in value.get_value_tuple():
        cur_repr = self.get_value_repr(v)
        body_array.append(cur_repr)
      result_dict[IRJsonRepr.ANY_BODY.value] = body_array
      return result_dict

    # 以下情况都是单值
    # 如果用到的是字符串字面值，就用 str
    # 如果用到的是整数字面值，就用 int
    # 如果用到的是逻辑类型的字面值，就用 bool
    # 如果用到的是其他值，就用 Object
    if isinstance(value, StringLiteral):
      assert isinstance(value.value, str)
      return value.value
    if isinstance(value, IntLiteral):
      assert isinstance(value.value, int)
      return value.value
    if isinstance(value, BoolLiteral):
      assert isinstance(value.value, bool)
      return value.value
    if isinstance(value, FloatLiteral):
      assert isinstance(value.value, decimal.Decimal)
      return self.emit_float(value.value)
    result_dict = {}
    result_dict[IRJsonRepr.ANY_KIND.value] = IRJsonRepr.VALUE_KIND_MISC_LITERAL.value
    result_dict[IRJsonRepr.ANY_TYPE.value] = json_name
    if isinstance(value, ClassLiteral):
      assert isinstance(value.value, type)
      result_dict[IRJsonRepr.ANY_BODY.value] = self.get_type_str(value.value)
    elif isinstance(value, TextStyleLiteral):
      body_dict = {}
      for attr, v in value.value:
        match attr:
          case TextAttribute.Bold:
            body_dict[IRJsonRepr.TEXTATTR_BOLD.value] = True
          case TextAttribute.Italic:
            body_dict[IRJsonRepr.TEXTATTR_ITALIC.value] = True
          case TextAttribute.Size:
            body_dict[IRJsonRepr.TEXTATTR_SIZE.value] = v
          case TextAttribute.TextColor:
            body_dict[IRJsonRepr.TEXTATTR_TEXTCOLOR.value] = self.emit_color(v)
          case TextAttribute.BackgroundColor:
            body_dict[IRJsonRepr.TEXTATTR_HIGHLIGHTCOLOR.value] = self.emit_color(v)
          case _:
            raise PPNotImplementedError('Unexpected text attribute')
      result_dict[IRJsonRepr.ANY_BODY.value] = body_dict
    elif isinstance(value, UndefLiteral):
      # 不需要额外值
      pass
    else:
      raise PPNotImplementedError()
    return result_dict

  def get_value_id(self, value: Value) -> int:
    # 该函数是在导出对值的定义（不是引用）时调用的
    # 如果是基础的字面值的话根本不会调用该函数（在应该引用处就内嵌其值了）
    if value in self.value_index_dict:
      return self.value_index_dict[value]
    # 到这的话我们需要新加值
    # 以下类型都是在导出时会特殊处理的，不应该有 ValueID
    assert not isinstance(value, (Literal, ConstExpr, AssetData))

    # 目前应该只有以下值会需要 ValueID
    assert isinstance(value, (BlockArgument, Block, OpResult, Operation))
    index = len(self.value_index_dict)
    self.value_index_dict[value] = index
    return index

  def get_value_type_repr(self, vty : ValueType) -> str:
    if 'JSON_TYPE_NAME' not in type(vty).__dict__:
      raise PPInternalError('ValueType ' + type(vty).__name__ + ' not registered with @IRObjectJsonTypeName("<name>") decorator')
    json_name = type(vty).__dict__['JSON_TYPE_NAME']
    if isinstance(vty, StatelessType):
      return json_name
    if isinstance(vty, ParameterizedType):
      # vty_dict : dict[ValueType, str] # 从值类型到表达值的映射
      # vty_index_dict : dict[type, int] # 对于每个值类型，下一个下标应该是多少
      if vty in self.vty_dict:
        return self.vty_dict[vty]
      next_index = 0
      cur_ty = type(vty)
      if cur_ty in self.vty_index_dict:
        next_index = self.vty_index_dict[cur_ty]
      self.vty_index_dict[cur_ty] = next_index + 1
      name_str = json_name + '_' + str(next_index)
      vty_dict = self.export_metadata_like_object(vty)
      self.output_valuetype_dict[name_str] = vty_dict
      self.vty_dict[vty] = name_str
      return name_str

    # 到这里的话就既不是 StatelessType 也不是 ParameterizedType
    raise PPInternalError("Value type is neither stateless nor parameterized: " + type(vty).__name__)

  def get_plain_value_repr(self, value : str | int | bool | decimal.Decimal) -> dict | str | int | bool:
    assert isinstance(value, (int, str, bool, decimal.Decimal))
    if isinstance(value, decimal.Decimal):
      return self.emit_float(value)
    return value

  def write_json(self, toplevel : dict | list) -> str:
    # 如果 toplevel 是 dict 的话，顶层操作项只有一个
    # 如果 toplevel 是 list 的话，顶层操作项可以不止一个，每一项都是列表成员
    assert isinstance(toplevel, (dict, list))
    json_obj = {}
    json_obj["version"] = {"protocol": self.protocol_ver, "preppipe": __version__}
    json_obj["type"] = self.output_type_dict
    json_obj["metadata"] = self.output_metadata_list
    json_obj["valuetype"] = self.output_valuetype_dict
    json_obj["toplevel"] = toplevel
    return json.dumps(json_obj, allow_nan=False, ensure_ascii=False)

  def init_protocol_0(self):
    base_types = [
      # core IR types
      ValueType,
      Value,
      User,
      Operation,
      Literal,
      LiteralExpr,
      ConstExpr,
      AssetData,
      Region,
      SymbolTableRegion,

      # types
      ParameterizedType,
      SingleElementParameterizedType,
      OptionalType,
      EnumType,
      ClassType,
      StatelessType,
      BlockReferenceType,
      AssetDataReferenceType,
      VoidType,
      IntType,
      FloatType,
      BoolType,
      StringType,
      ColorType,
      TextStyleType,
      TextType,
      ImageType,
      AudioType,

      # operations
      Symbol,
      MetadataOp,
      ErrorOp,
      CommentOp,

      # literal
      UndefLiteral,
      ClassLiteral,
      IntLiteral,
      IntTupleLiteral,
      BoolLiteral,
      FloatLiteral,
      FloatTupleLiteral,
      StringLiteral,
      ColorLiteral,
      TextStyleLiteral,
      TextFragmentLiteral,
      StringListLiteral,
      EnumLiteral,

      # metadata
      Location,
      DIFile,
      DILocation,

      # asset data
      BytesAssetData,
      ImageAssetData,
      AudioAssetData,
      AssetPlaceholderTrait,
      AssetDeclarationTrait,
    ]
    for ty in base_types:
      self.add_base_type(ty)


def _stub_copy_init(self, *, init_src : IRObject, value_mapper : IRValueMapper, **kwargs):
  raise PPInternalError("Class cannot be copy-constructed: " + type(self).__name__)

def _metadata_object_json_import_init(self, *, importer : IRJsonImporter, init_src : dict, **kwargs) -> None:
  raise PPNotImplementedError()

def IRObjectUniqueTrait(cls):
  '''该修饰符用于不可被复制的对象（比如他们需要在 Context 被去重，比如字面值）'''
  cls.copy_init = _stub_copy_init # type: ignore
  return cls

def IRObjectMetadataTrait(cls):
  '''该修饰符用于所有以元数据(Metadata)的方式进行 JSON 导入导出的对象：
1.  对象不可复制，将会在 Context 层面被去重
2.  对象是 dataclass 并且所有成员值只能包含(1)字面值（整数，字符串，等等），(2)Python 类型，(3)对其他元数据项的引用，(4) Context
    对象不可以包含对 Value 的引用，不能是 User
3.  对其他元数据的引用不可以包含环，必须最多是 DAG
4.  对象的每一个值都有 "json_repr" 的元数据，描述（除 Context 以外）所有参数的 JSON 形式

目前该修饰符只用于位置信息 (DIFile, DILocation)和值类型

（注意我们需要使用 object.__setattr__(obj, "field_name", value) 来进行初始化，不然我们不能动 frozen 的 dataclass）
'''
  cls.copy_init = _stub_copy_init # type: ignore
  cls.json_import_init = _metadata_object_json_import_init # type: ignore
  return cls

# 。。下面这些注释作废了
# IR 主要使用 JSON 进行导入导出
# JSON 大致结构如下：
# JSON 存档 ::= {类型列表, 顶层对象} ;
#   类型列表 ::= [类型 __qualname__] ; # 类型 必须是 IRObject 的子类
#   对象 ::= {"T": <TID>, 基础类型}
# TODO


class IRJsonImporter:
  _type_dict : dict[str, type]
  _value_dict : dict[int, Value]
  _valuetype_dict : dict[int, ValueType]
  _placeholder_value_dict : dict[int, Value]
  _placeholder_recycle_list : list[Value]
  _ctx : Context

  def __init__(self, ctx : Context) -> None:
    self._ctx = ctx
    self._type_dict = {}
    self._value_dict = {}
    self._valuetype_dict = {}
    self._placeholder_value_dict = {}
    self._placeholder_recycle_list = []

    for cls in IRObject.__subclasses__():
      self._type_dict[cls.__qualname__] = cls

  def json_import(self, json_fp : typing.TextIO) -> Operation:
    # 好像不应该用decoder或者json本身的load/dump。。还是用传统的递归比较好
    toplevel = json.load(json_fp)
    # TODO toplevel 应该有以下项：
    # 1.  协议版本号 (x.y)
    # 2.  类型列表 (Python 类型到 ID)
    # 3.  元数据节点，包括 DIFile/DILocation 和各种 ValueType
    # 4.  顶层操作项
    raise PPNotImplementedError()


  def get_value_type(self, value_type_id : int):
    return self._valuetype_dict[value_type_id]

  def claim_value_id(self, value_id : int, value : Value):
    # 当一个 IR 的值初始化好后，我们用这个函数来把对该值的引用加上
    assert value_id not in self._value_dict
    self._value_dict[value_id] = value
    if value_id in self._placeholder_value_dict:
      placeholder = self._placeholder_value_dict[value_id]
      placeholder.replace_all_uses_with(value)
      del self._placeholder_value_dict[value_id]
      self._placeholder_recycle_list.append(placeholder)

  def get_value(self, value_id : int) -> Value:
    # 获取指定 ID 的值（可能只是个占位的值）
    if value_id in self._value_dict:
      return self._value_dict[value_id]
    if value_id in self._placeholder_value_dict:
      return self._placeholder_value_dict[value_id]
    # 创建新的占位值
    placeholder = None
    if len(self._placeholder_recycle_list) > 0:
      placeholder = self._placeholder_recycle_list.pop()
    else:
      placeholder = PlaceholderValue(init_mode = IRObjectInitMode.CONSTRUCT, context = self._ctx, ty = VoidType.get(self._ctx))
    self._placeholder_value_dict[value_id] = placeholder
    return placeholder

  @property
  def context(self):
    return self._ctx

  def get_type(self, qualname : str):
    return self._type_dict[qualname]


@IRObjectJsonTypeName('metadata_md')
@IRObjectMetadataTrait
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class Metadata(IRObject):
  # 所有元数据的基类
  # 如果元数据有以下需求：
  # (1) 要包含对值的引用
  # (2) 要能作为值、有类型
  # (3) 要能表达复杂的、超越 DAG 的结构
  # 有以上之一的请继承 MetadataOp 而不是该类
  context : Context

  def construct_init(self, *, context : Context, **kwargs) -> None:
    super(Metadata, self).construct_init(context=context, **kwargs)
    object.__setattr__(self, 'context', context)

@IRObjectJsonTypeName('location_dl')
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class Location(Metadata):

  def __str__(self) -> str:
    return "NullLocation"

  def get_file_path(self) -> str:
    return ''

  @staticmethod
  def getNullLocation(ctx: Context):
    return ctx.null_location

# ------------------------------------------------------------------------------
# Types
# ------------------------------------------------------------------------------

@IRObjectJsonTypeName("value_t")
@IRObjectMetadataTrait
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class ValueType(IRObject):
  context : Context

  def construct_init(self, *, context : Context, **kwargs) -> None:
    super(ValueType, self).construct_init(context=context, **kwargs)
    object.__setattr__(self, 'context', context)

  def __str__(self) -> str:
    return type(self).__name__

  @staticmethod
  def get(*args, **kwargs):
    raise PPNotImplementedError

@IRObjectJsonTypeName("parameterized_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class ParameterizedType(ValueType):
  # parameterized types are considered different if the parameters (can be types or literal values) are different
  parameters : tuple[ValueType | type | int | str | bool | None] = dataclasses.field(metadata={'json_repr': IRJsonRepr.TYPE_PARAMETERIZED_PARAM}) # None for separator

  def construct_init(self, *, context : Context, parameters : typing.Iterable[ValueType | type | int | str | bool | None], **kwargs) -> None:
    super(ParameterizedType, self).construct_init(context=context,**kwargs)
    object.__setattr__(self, 'parameters', tuple(parameters))

  @staticmethod
  def _get_parameter_repr(parameters : typing.Iterable[ValueType | type | int | str | bool | None]):
    result = ''
    isFirst = True
    for v in parameters:
      if isFirst:
        isFirst = False
      else:
        result += ', '
      if isinstance(v, ValueType):
        result += repr(v)
      elif isinstance(v, type):
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
    return  type(self).__name__ + '<' + ParameterizedType._get_parameter_repr(self.parameters) + '>'

@IRObjectJsonTypeName("singleparam_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class SingleElementParameterizedType(ParameterizedType):
  def construct_init(self, *, element_type: ValueType, **kwargs) -> None:
    return super(SingleElementParameterizedType, self).construct_init(parameters=[element_type], **kwargs)

  @property
  def element_type(self) -> ValueType:
    return self.parameters[0] # type: ignore

  @classmethod
  def _get_typecheck(cls, element_type : ValueType) -> None:
    # 对所提供的类型进行检查，不符合要求就抛出异常
    pass

  @classmethod
  def get(cls, element_type : ValueType) -> SingleElementParameterizedType:
    cls._get_typecheck(element_type)
    return element_type.context.get_or_create_parameterized_type(
      cls,
      [element_type],
      lambda : cls(init_mode = IRObjectInitMode.CONSTRUCT,
                   context = element_type.context,
                   element_type=element_type)
    )

@IRObjectJsonTypeName("optional_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class OptionalType(SingleElementParameterizedType):
  # dependent type that is optional of the specified type (either have the data or None)
  def __str__(self) -> str:
    return "可选<" + str(self.element_type) + ">"

  @classmethod
  def _get_typecheck(cls, element_type : ValueType) -> None:
    assert not isinstance(element_type, OptionalType)

@IRObjectJsonTypeName("enum_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class EnumType(ParameterizedType):
  def construct_init(self, *, ty : type, context : Context, **kwargs) -> None:
    return super(EnumType, self).construct_init(context=context, parameters=[ty], **kwargs)

  @property
  def element_type(self) -> type:
    return super().parameters[0] # type: ignore

  def __str__(self) -> str:
    return "枚举类型<" + str(self.element_type) + ">"

  @staticmethod
  def get(ty : type, context : Context) -> EnumType:
    return context.get_or_create_parameterized_type(EnumType, [ty], lambda : EnumType(init_mode = IRObjectInitMode.CONSTRUCT, context = context, ty = ty))

@IRObjectJsonTypeName("class_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class ClassType(ParameterizedType):
  def construct_init(self, *, base_cls : type, context: Context, **kwargs) -> None:
    super().construct_init(context=context, parameters=[base_cls])

  def __str__(self) -> str:
    return "类类型<" + str(self.element_type) + ">"

  @property
  def element_type(self) -> type:
    return super().parameters[0] # type: ignore

  @staticmethod
  def get(base_cls : type, context : Context) -> ClassType:
    return context.get_or_create_parameterized_type(ClassType, [base_cls], lambda : ClassType(init_mode=IRObjectInitMode.CONSTRUCT, context=context, base_cls=base_cls))

class ParameterizedTypeUniquingDict:
  # this class is used by Context to manage all parameterized type objects
  _pty : type # type object of the parameterized type
  _instance_dict : collections.OrderedDict[str, ValueType]
  def __init__(self, pty : type) -> None:
    self._instance_dict = collections.OrderedDict()
    self._pty = pty
    assert isinstance(pty, type)

  def get_or_create(self, parameters : typing.List[ValueType | type | int | str | bool | None], ctor : typing.Callable):
    # pylint: disable=protected-access
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

@IRObjectJsonTypeName("stateless_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class StatelessType(ValueType):
  @classmethod
  def get(cls, ctx : Context):
    return ctx.get_stateless_type(cls)

@IRObjectJsonTypeName("block_ref_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class BlockReferenceType(StatelessType):
  pass

@IRObjectJsonTypeName("assetdata_ref_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class AssetDataReferenceType(StatelessType):
  # this type is only for asset data internal reference (from Asset instance to AssetData instance)
  # we use this to implement copy-on-write
  # usually no user code need to work with it
  pass

@IRObjectJsonTypeName("void_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class VoidType(StatelessType):
  def __str__(self) -> str:
    return "空类型"

@IRObjectJsonTypeName("int_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class IntType(StatelessType):
  def __str__(self) -> str:
    return "整数类型"

@IRObjectJsonTypeName("float_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class FloatType(StatelessType):
  def __str__(self) -> str:
    return "浮点数类型"

@IRObjectJsonTypeName("bool_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class BoolType(StatelessType):
  def __str__(self) -> str:
    return "逻辑类型"

@IRObjectJsonTypeName("str_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class StringType(StatelessType):
  def __str__(self) -> str:
    return "字符串类型"

@IRObjectJsonTypeName("color_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class ColorType(StatelessType):
  def __str__(self) -> str:
    return "颜色类型"

@IRObjectJsonTypeName("text_style_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class TextStyleType(StatelessType):
  def __str__(self) -> str:
    return "文本格式类型"

@IRObjectJsonTypeName("text_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class TextType(StatelessType):
  # string + style (style can be empty)
  def __str__(self) -> str:
    return "文本类型"

@IRObjectJsonTypeName("image_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class ImageType(StatelessType):
  def __str__(self) -> str:
    return "图片类型"

@IRObjectJsonTypeName("audio_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class AudioType(StatelessType):
  def __str__(self) -> str:
    return "声音类型"

@IRObjectJsonTypeName("aggr_text_t")
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class AggregateTextType(StatelessType):
  # 列表，表格，代码段等结构化的文本内容
  def __str__(self) -> str:
    return "结构文本类型"

# ------------------------------------------------------------------------------
# Major classes
# ------------------------------------------------------------------------------
_ValueTypeVar = typing.TypeVar('_ValueTypeVar', bound='Value')

@IRObjectJsonTypeName("value")
class Value(IRObject):
  # __slots__ = ('_type', '_uselist')
  # value is either a block argument or an operation result
  _type : ValueType
  _uselist : IList[Use, Value]

  # pylint: disable=arguments-differ
  def construct_init(self, *, ty : ValueType, **kwargs) -> None:
    super().construct_init(**kwargs)
    self._type = ty
    self._uselist = IList(self)

  def copy_init(self, *, init_src: Value, value_mapper : IRValueMapper, **kwargs) -> None:
    super().copy_init(init_src=init_src, value_mapper=value_mapper, **kwargs)
    self._type = init_src._type
    self._uselist = IList(self)
    value_mapper.add_value_map(init_src, self)

  def json_import_init(self, *, importer: IRJsonImporter, init_src: dict, **kwargs) -> None:
    # 因为有些值（比如同时继承了 Symbol 和 Value 的）不需要从存档里读取值类型，
    # 这些值的类型完全可以从子类决定，
    # 我们建一个新的函数 get_fixed_value_type(), 子类可以覆盖该函数来提供类型
    super().json_import_init(importer=importer, init_src=init_src, **kwargs)
    if ty := self.get_fixed_value_type():
      assert issubclass(ty, ValueType)
      self._type = ty.get(importer.context)
    else:
      self._type = importer.get_value_type(init_src[IRJsonRepr.VALUE_VALUETYPE.value])
    self._uselist = IList(self)
    importer.claim_value_id(init_src[IRJsonRepr.VALUE_VALUEID.value], self)

  def json_export_impl(self, *, exporter: IRJsonExporter, dest: dict, **kwargs) -> None:
    super().json_export_impl(exporter=exporter, dest=dest, **kwargs)
    dest[IRJsonRepr.VALUE_VALUEID.value] = exporter.get_value_id(self)
    if self.get_fixed_value_type() is None:
      # 我们需要把值类型也保存下来
      dest[IRJsonRepr.VALUE_VALUETYPE.value] = exporter.get_value_type_repr(self.valuetype)

  @staticmethod
  def get_fixed_value_type() -> type | None:
    # 如果某些子类只会使用一种值类型，那么在这里返回类型
    return None

  @classmethod
  def json_export_type_action(cls, exporter: IRJsonExporter, type_obj: dict):
    super().json_export_type_action(exporter, type_obj)
    if ty := cls.get_fixed_value_type():
      json_name = exporter.get_type_str(ty)
      type_obj["value"] = {"value_type": json_name}

  @property
  def uses(self) -> IList[Use, Value]:
    return self._uselist

  def use_empty(self) -> bool:
    return self._uselist.empty

  @property
  def valuetype(self) -> ValueType:
    return self._type

  @property
  def context(self) -> Context:
    return self._type.context

  # pylint: disable=protected-access
  def replace_all_uses_with(self, v : Value) -> None:
    assert self._type == v._type
    self._uselist.merge_into(v._uselist)

  def __str__(self) -> str:
    return str(self._type) + ' ' + type(self).__name__

  def destroy_value(self):
    # 首先走一遍 use list 看看有没有 constexpr 在用，如果有的话把它们去掉
    # constexpr 使用者都没了之后还有什么在用的话，就生成 Undef
    if not self.use_empty():
      const_users : list[ConstExpr] = []
      for use in self._uselist:
        user = use.user
        if isinstance(user, ConstExpr):
          const_users.append(user)
      if len(const_users) > 0:
        for cexpr in const_users:
          cexpr.destroy_constant()
    if not self.use_empty():
      undef = UndefLiteral.get(self.valuetype, str(self))
      self.replace_all_uses_with(undef)

class PlaceholderValue(Value):
  # __slots__ = ()
  # 只为了在导入或者是变换等时候临时使用一下的值，不应该出现在导出的 IR 里
  def replace_all_uses_with(self, v : Value) -> None:
    # 把对值类型的检查去掉的版本
    self._uselist.merge_into(v._uselist)


class NameReferencedValue(Value, NameDictNode):

  @property
  def parent(self) -> Block | Operation:
    return super().parent

  def json_export_impl(self, *, exporter: IRJsonExporter, dest: dict, **kwargs) -> None:
    super().json_export_impl(exporter=exporter, dest=dest, **kwargs)
    dest[IRJsonRepr.ANY_NAME.value] = self.name



class Use(IListNode, typing.Generic[_ValueTypeVar]):
  # __slots__ = ('_user', '_argno')
  _user : User[_ValueTypeVar]
  _argno : int
  def __init__(self, user : User[_ValueTypeVar], argno : int) -> None:
    super().__init__()
    self._user = user
    self._argno = argno

  @property
  def value(self) -> _ValueTypeVar:
    return super().parent # type: ignore

  @property
  def user(self) -> User[_ValueTypeVar]:
    # 这个可能是 OpOperand 或是 ConstExpr
    return self._user

  @property
  def user_op(self) -> Operation:
    assert isinstance(self._user, OpOperand)
    return self._user.parent

  @property
  def argno(self) -> int:
    return self._argno

  def set_value(self, v : _ValueTypeVar | None):
    if super().parent is not None:
      super().remove_from_parent()
    if v is not None:
      # pylint: disable=protected-access
      v._uselist.push_back(self) # type: ignore

@_IRInnerConstructJsonTypeName("user")
class User(typing.Generic[_ValueTypeVar]):
  _operandlist : list[Use[_ValueTypeVar]]

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self._operandlist = []

  def post_copy_value_remap(self, *, value_mapper : IRValueMapper, **kwargs):
    for u in self._operandlist:
      if newvalue := value_mapper.get_mapped_value(u.value):
        u.set_value(newvalue) # type: ignore

  def get_operand(self, index : int) -> _ValueTypeVar:
    return self._operandlist[index].value

  def set_operand(self, index : int, value : _ValueTypeVar) -> None:
    assert isinstance(value, Value)
    if len(self._operandlist) == index:
      return self.add_operand(value)
    self._operandlist[index].set_value(value)

  def add_operand(self, value : _ValueTypeVar) -> None:
    assert isinstance(value, Value)
    u = Use(self, len(self._operandlist))
    self._operandlist.append(u)
    u.set_value(value)

  def get_num_operands(self) -> int:
    return len(self._operandlist)

  def has_value(self) -> bool:
    return len(self._operandlist) > 0

  def try_get_value(self) -> _ValueTypeVar | None:
    if len(self._operandlist) > 0:
      return self._operandlist[0].value
    return None

  def operanduses(self) -> typing.Iterable[Use[_ValueTypeVar]]:
    return self._operandlist

  def drop_all_uses(self) -> None:
    for u in self._operandlist:
      u.set_value(None)
    self._operandlist.clear()

  def json_export_user_valuelist(self, *, exporter : IRJsonExporter, **kwargs):
    result = []
    for use in self._operandlist:
      result.append(exporter.get_value_repr(use.value))
    return result

class OpOperand(User[_ValueTypeVar], NameDictNode, typing.Generic[_ValueTypeVar]):
  def __init__(self) -> None:
    super().__init__()

  @property
  def parent(self) -> Operation:
    return super().parent

  def get(self, index : typing.Optional[int] = None) -> _ValueTypeVar:
    if index is not None:
      return super().get_operand(index)
    return super().get_operand(0)

  # 可以调用 User.drop_all_uses() 来取消所有引用

@_IRInnerConstructJsonTypeName(IRObject.JSON_NAME_NOT_USED)
class OpResult(NameReferencedValue):
  @property
  def parent(self) -> Operation:
    return super().parent

@_IRInnerConstructJsonTypeName(IRObject.JSON_NAME_NOT_USED)
class BlockArgument(NameReferencedValue):
  @property
  def parent(self) -> Block:
    return super().parent

# reference: https://mlir.llvm.org/doxygen/classmlir_1_1Operation.html
@IRObjectJsonTypeName("op")
class Operation(IRObject, IListNode):
  _name : str
  _loc : Location
  _operands : NameDict[OpOperand]
  _results : NameDict[OpResult]
  _attributes : collections.OrderedDict[str, int | str | bool | decimal.Decimal]
  _regions : NameDict[Region]
  #_terminator_info : OpTerminatorInfo

  def base_init(self, *, context : Context, **kwargs) -> None:
    super().base_init(context=context,**kwargs)
    self._name = ''
    self._loc = context.null_location
    self._operands = NameDict(self)
    self._results = NameDict(self)
    self._attributes = collections.OrderedDict()
    self._regions = NameDict(self)

  def construct_init(self, *, name : str = '', loc : Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc,**kwargs)
    self._name = name
    if loc is not None:
      self._loc = loc

  def copy_init(self, *, init_src: Operation, value_mapper: IRValueMapper, **kwargs) -> None:
    super().copy_init(init_src=init_src, value_mapper=value_mapper, **kwargs)
    self._name = init_src._name
    self._loc = init_src._loc
    for name in init_src._operands:
      cur_operand = self._add_operand(name)
      for op_use in init_src.get_operand_inst(name).operanduses():
        cur_operand.add_operand(op_use.value)
    for result in init_src._results.values():
      new_result = self._add_result(result.name, result.valuetype)
      value_mapper.add_value_map(result, new_result)
    self._attributes = init_src._attributes.copy()
    for name, r in init_src._regions.items():
      if isinstance(r, SymbolTableRegion):
        new_region = SymbolTableRegion(value_mapper.context)
        new_region.copy_init(init_src=r, value_mapper=value_mapper, **kwargs)
        self._regions[name] = new_region
      else:
        new_region = Region()
        new_region.copy_init(init_src=r, value_mapper=value_mapper, **kwargs)
        self._regions[name] = new_region

  def post_copy_value_remap(self, *, value_mapper: IRValueMapper, **kwargs) -> None:
    super().post_copy_value_remap(value_mapper=value_mapper, **kwargs)
    for name, operand in self._operands.items():
      operand.post_copy_value_remap(value_mapper=value_mapper, **kwargs)
    for r in self.regions:
      r.post_copy_value_remap(value_mapper=value_mapper, **kwargs)

  @staticmethod
  def _json_export_dump_region(r : Region, exporter : IRJsonExporter) -> dict :
    body = []
    if isinstance(r, SymbolTableRegion):
      for symb in r:
        # 为保证 symbol 的顺序能够在 JSON 中保存下来，我们在这一定使用 list 而不是 dict
        symb_dest = {}
        symb.json_export_impl(exporter=exporter, dest=symb_dest)
        body.append(symb_dest)
    else:
      # 如果冒出来不是 SymbolTableRegion 的其他 Region 的子类，我们想要报错，所以这里用等号做检查
      # pylint: disable=unidomatic-typecheck
      assert type(r) == Region
      for block in r.blocks:
        body.append(block.json_export_block(exporter=exporter))
    dest = {}
    dest[IRJsonRepr.ANY_BODY.value] = body
    dest[IRJsonRepr.ANY_KIND.value] = r.JSON_TYPE_NAME
    # 不保存区名，应该在上层就放进去了
    return dest

  def json_export_impl(self, *, exporter: IRJsonExporter, dest: dict, **kwargs) -> None:
    super().json_export_impl(exporter=exporter, dest=dest, **kwargs)
    if len(self.name) > 0:
      dest[IRJsonRepr.ANY_NAME.value] = self.name
    if self.location is not self.context.null_location:
      dest[IRJsonRepr.OP_LOCATION.value] = exporter.get_metadata_id(self.location)
    if len(self.operands) > 0:
      operands = {}
      for name, operand in self.operands.items():
        operands[name] = operand.json_export_user_valuelist(exporter=exporter)
      dest[IRJsonRepr.OP_OPERAND.value] = operands
    if len(self.results) > 0:
      opresults = []
      for name, opresult in self.results.items():
        dest_dict = {}
        opresult.json_export_impl(exporter=exporter, dest=dest_dict)
        opresults.append(dest_dict)
      dest[IRJsonRepr.OP_RESULT.value] = opresults
    if len(self.attributes) > 0:
      attrs = {}
      for key, value in self.attributes.items():
        assert isinstance(key, str) and isinstance(value, (int, str, decimal.Decimal, bool))
        attrs[key] = exporter.get_plain_value_repr(value)
      dest[IRJsonRepr.OP_ATTRIBUTE.value] = attrs
    if self.get_num_regions() > 0:
      regions_dict = {}
      for r in self.regions:
        regions_dict[r.name] = self._json_export_dump_region(r, exporter)
      dest[IRJsonRepr.OP_REGION.value] = regions_dict

  def _add_result(self, name : str, ty : ValueType) -> OpResult:
    r = OpResult(init_mode=IRObjectInitMode.CONSTRUCT, context=ty.context, ty=ty)
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

  def _add_operand_with_value(self, name : str, value : Value | typing.Iterable[Value] | None) -> OpOperand:
    o = self._add_operand(name)
    if value is not None:
      if isinstance(value, Value):
        o.add_operand(value)
      else:
        for v in value:
          o.add_operand(v)
    return o

  def get_result(self, name : str) -> OpResult:
    if v := self._results.get(name):
      return v
    raise PPInternalError('Result not found')

  def get_operand_inst(self, name : str) -> OpOperand:
    if v := self._operands.get(name):
      return v
    raise PPInternalError('Operand not found')

  def try_get_operand_inst(self, name: str) -> OpOperand | None:
    if name not in self._operands:
      return None
    return self._operands.get(name)

  def get_operand(self, name : str) -> Value | None:
    o = self._operands.get(name)
    if o is not None:
      return o.get()
    return None

  def set_attr(self, name : str, value: typing.Any) -> None:
    assert isinstance(value, (int, str, bool, decimal.Decimal))
    self._attributes[name] = value

  def get_attr(self, name : str) -> int | str | bool | decimal.Decimal | None:
    return self._attributes.get(name, None)

  def remove_attr(self, name : str):
    del self._attributes[name]

  def has_attr(self, name : str) -> bool:
    return name in self._attributes

  def _add_region(self, name : str = '') -> Region:
    assert name not in self._regions
    r = Region()
    self._regions[name] = r
    return r

  def _take_region(self, r : Region, name : str = ''):
    assert name not in self._regions
    assert r.parent is None
    self._regions[name] = r

  def get_or_create_region(self, name : str = '') -> Region:
    if name in self._regions:
      return self._regions[name]
    return self._add_region(name)

  def _add_symbol_table(self, name : str = '') -> SymbolTableRegion:
    r = SymbolTableRegion(self._loc.context)
    self._regions[name] = r
    return r

  def get_region(self, name : str) -> Region:
    r = self._regions.get(name)
    assert r is not None and type(r) == Region
    return r

  def get_symbol_table(self, name : str) -> SymbolTableRegion:
    r = self._regions.get(name)
    assert isinstance(r, SymbolTableRegion)
    return r

  def get_num_regions(self) -> int:
    return len(self._regions)

  def get_region_names(self) -> typing.Iterable[str]:
    return self._regions.keys()

  def get_next_node(self) -> Operation:
    return self.next

  def get_prev_node(self) -> Operation:
    return self.prev

  @property
  def regions(self) -> typing.Iterable[Region]:
    return self._regions.values()

  def get_first_region(self) -> Region | None:
    try:
      return next(iter(self._regions.values()))
    except StopIteration:
      return None

  def get_last_region(self) -> Region | None:
    try:
      return self._regions[next(reversed(self._regions))]
    except StopIteration:
      return None

  def drop_all_references(self) -> None:
    # drop all references to outside values; required before erasing
    for operand in self._operands.values():
      assert isinstance(operand, OpOperand)
      operand.drop_all_uses()
    for result in self._results.values():
      assert isinstance(result, OpResult)
      result.destroy_value()
    self._operands.clear()
    self._results.clear()
    for r in self.regions:
      r.drop_all_references()
    self._regions.clear()
    if isinstance(self, Value):
      self.destroy_value()
    if isinstance(self, User):
      self.drop_all_uses()

  def erase_from_parent(self) -> Operation:
    # return the next op
    retval = self.get_next_node()
    self.remove_from_parent()
    self.drop_all_references()
    return retval

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
  def parent_region(self) -> Region | None:
    if self.parent is not None:
      return self.parent.parent
    return None

  @property
  def parent_op(self) -> Operation | None:
    parent_region = self.parent_region
    if parent_region is not None:
      return parent_region.parent
    return None

  def __str__(self) -> str:
    writer = IRWriter(self.context, False, None, None)
    dump = writer.write_op(self)
    return dump.decode('utf-8')

  def __repr__(self) -> str:
    return '<' + type(self).__name__ + '>'

  def view(self) -> None:
    # for debugging
    writer = IRWriter(self.context, True, None, None)
    dump = writer.write_op(self)
    _view_content_helper(dump, self.name)

  def dump(self) -> None:
    # for debugging
    writer = IRWriter(self.context, False, None, None)
    dump = writer.write_op(self)
    print(dump.decode('utf-8'))

@IRObjectJsonTypeName("symbol_op")
class Symbol(Operation):

  @Operation.name.setter
  def name(self, n : str):
    if self.parent is not None:
      table = self.parent.parent
      # pylint: disable=protected-access
      assert isinstance(table, SymbolTableRegion)
      table._rename_symbol(self, n)
    self._name = n

  def node_inserted(self, parent : Block):
    assert isinstance(parent, Block)
    table = parent.parent
    assert isinstance(table, SymbolTableRegion)
    # pylint: disable=protected-access
    table._add_symbol(self)

  def node_removed(self, parent : Block):
    assert isinstance(parent, Block)
    table = parent.parent
    assert isinstance(table, SymbolTableRegion)
    # pylint: disable=protected-access
    table._drop_symbol(self.name)

@IRObjectJsonTypeName("metadata_op")
class MetadataOp(Operation):
  # 所有不带语义的操作项的基类（错误记录，注释，等等）
  pass

@IRObjectJsonTypeName("error_op")
class ErrorOp(MetadataOp):
  # 错误项用以记录编译中遇到的错误
  # 所有错误项需要(1)一个错误编号，(2)一个错误消息
  # 一般来说所有转换都需要忽视这些错误项，把它们留在IR里不去动它们
  _error_message_operand : OpOperand[StringLiteral]

  def construct_init(self, *, error_code : str, error_msg : StringLiteral, name: str = '', loc: Location | None = None,  **kwargs) -> None:
    assert isinstance(error_code, str)
    assert isinstance(error_msg, StringLiteral)
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_operand_with_value('message', error_msg)
    self.set_attr('Code', error_code)

  def post_init(self) -> None:
    self._error_message_operand = self.get_operand_inst('message')

  @property
  def error_code(self) -> str:
    return self.get_attr('Code') # type: ignore

  @property
  def error_message(self) -> StringLiteral:
    return self._error_message_operand.get()

  @staticmethod
  def create(error_code : str, context : Context, error_msg : StringLiteral | None = None, name: str = '', loc: Location | None = None) -> ErrorOp:
    if error_msg is None:
      error_msg = StringLiteral.get('', context)
    return ErrorOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, error_code = error_code, error_msg = error_msg, name = name, loc = loc)

@IRObjectJsonTypeName("comment_op")
class CommentOp(MetadataOp):
  # 注释项用以保留源中的用户输入的注释
  # 一般来说我们努力将其保留到输出源文件中
  _comment_operand : OpOperand

  def construct_init(self, *, comment : StringLiteral, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name = name, loc = loc, **kwargs)
    self._add_operand_with_value('comment', comment)

  def post_init(self) -> None:
    self._comment_operand = self.get_operand_inst('comment')

  @property
  def comment(self) -> StringLiteral:
    return self._comment_operand.get()

  @staticmethod
  def create(comment : StringLiteral, name: str = '', loc: Location | None = None) -> CommentOp:
    return CommentOp(init_mode=IRObjectInitMode.CONSTRUCT, context=comment.context, comment = comment, name = name, loc = loc)

class Block(Value, IListNode):
  _ops : IList[Operation, Block]
  _args : NameDict[BlockArgument]
  _name : str

  @staticmethod
  def create(name : str, context : Context):
    return Block(init_mode = IRObjectInitMode.CONSTRUCT, context = context, name = name)

  def base_init(self, **kwargs) -> None:
    super().base_init(**kwargs)
    self._ops = IList(self)
    self._args = NameDict(self)
    self._name = ''

  def construct_init(self, *, name : str, context : Context, **kwargs) -> None:
    ty = BlockReferenceType.get(context)
    super().construct_init(ty = ty, name = name, context = context, **kwargs)
    self._name = name

  def copy_init(self, *, init_src: Block, value_mapper: IRValueMapper, **kwargs) -> None:
    super().copy_init(init_src=init_src, value_mapper=value_mapper, **kwargs)
    self._name = init_src._name

    for arg in init_src._args.values():
      new_arg = self.add_argument(arg.name, arg.valuetype)
      value_mapper.add_value_map(arg, new_arg)
    for op in init_src._ops:
      clonedop = op.clone(value_mapper)
      self._ops.push_back(clonedop) # type: ignore

  def post_copy_value_remap(self, *, value_mapper : IRValueMapper, **kwargs):
    super().post_copy_value_remap(value_mapper=value_mapper, **kwargs)
    for op in self._ops:
      op.post_copy_value_remap(value_mapper=value_mapper, **kwargs)

  def json_export_block(self, *, exporter: IRJsonExporter, **kwargs) -> dict:
    # 该函数只有在正常区时会被调用，符号表区导出时会越过块级，直接输出子操作项
    dest = {}
    if len(self.name) > 0:
      dest[IRJsonRepr.ANY_NAME.value] = self.name
    if len(self.args) > 0:
      args = []
      for a in self.args.values():
        dest_dict = {}
        a.json_export_impl(exporter=exporter, dest=dest_dict)
        args.append(dest_dict)
      dest[IRJsonRepr.BLOCK_ARGUMENT.value] = args
    if len(self.body) > 0:
      body = []
      for op in self.body:
        cur_op = {}
        op.json_export_impl(exporter=exporter, dest=cur_op)
        body.append(cur_op)
      dest[IRJsonRepr.ANY_BODY.value] = body
    return dest

  @staticmethod
  def get_fixed_value_type():
    return BlockReferenceType

  @property
  def context(self) -> Context:
    return self.valuetype.context

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

  def take_body(self, src : Block):
    src._ops.merge_into(self._ops)

  def get_next_node(self) -> Block:
    return self.next

  def add_argument(self, name : str, ty : ValueType) -> BlockArgument:
    arg = BlockArgument(init_mode=IRObjectInitMode.CONSTRUCT, context=ty.context, ty=ty)
    self._args[name] = arg
    return arg

  def get_or_create_argument(self, name : str, ty : ValueType) -> BlockArgument:
    if name in self._args:
      return self._args[name]
    return self.add_argument(name, ty)

  def get_argument(self, name : str) -> BlockArgument:
    assert name in self._args
    return self._args[name]

  def drop_all_references(self) -> None:
    for op in self._ops:
      op.drop_all_references()
    self._ops.clear()
    self.destroy_value()

  def erase_from_parent(self) -> Block:
    retval = self.next
    self.remove_from_parent()
    self.drop_all_references()
    return retval

  def push_back(self, op : Operation):
    assert isinstance(op, Operation)
    if op.parent is not None:
      raise PPInternalError('Cannot add operation with parent')
    self._ops.push_back(op)

  def push_front(self, op : Operation):
    assert isinstance(op, Operation)
    if op.parent is not None:
      raise PPInternalError('Cannot add operation with parent')
    self._ops.push_front(op)

  def view(self) -> None:
    # for debugging
    writer = IRWriter(self.context, True, None, None)
    dump = writer.write_block(self)
    _view_content_helper(dump, self.name)

  def dump(self) -> None:
    writer = IRWriter(self.context, False, None, None)
    dump = writer.write_block(self)
    print(dump.decode('utf-8'))

@_IRInnerConstructJsonTypeName("region_r")
class Region(NameDictNode):
  _blocks : IList[Block, Region]

  JSON_TYPE_NAME: typing.ClassVar[str]

  def __init__(self) -> None:
    super().__init__()
    self._blocks = IList(self)

  def copy_init(self, *, init_src : Region, value_mapper : IRValueMapper, **kwargs):
    for b in init_src._blocks:
      new_block = b.clone(value_mapper)
      assert isinstance(new_block, Block)
      self._blocks.push_back(new_block)
      value_mapper.add_value_map(b, new_block)

  def post_copy_value_remap(self, *, value_mapper : IRValueMapper, **kwargs):
    for b in self._blocks:
      b.post_copy_value_remap(value_mapper=value_mapper, **kwargs)

  @property
  def context(self) -> Context | None:
    if not self._blocks.empty:
      # pylint: disable=no-member
      return self._blocks.front.context
    if self.parent is not None:
      return self.parent.context
    return None

  def push_back(self, block : Block) -> None:
    assert isinstance(block, Block)
    self._blocks.push_back(block)

  def push_front(self, block : Block) -> None:
    assert isinstance(block, Block)
    self._blocks.push_front(block)

  @property
  def blocks(self) -> IList[Block, Region]:
    return self._blocks

  def get_num_blocks(self) -> int:
    return self._blocks.size

  def drop_all_references(self) -> None:
    for b in self._blocks:
      b.drop_all_references()
    self._blocks.clear()

  def erase_from_parent(self) -> None:
    self.remove_from_parent()
    self.drop_all_references()

  @property
  def entry_block(self) -> Block:
    return self._blocks.front

  @property
  def parent(self) -> Operation:
    return super().parent

  def create_block(self, name : str = '') -> Block:
    ctx = self.context
    if ctx is None:
      raise PPInternalError('Cannot find context')
    block = Block.create(name, ctx)
    self._blocks.push_back(block)
    return block

  def view(self) -> None:
    # for debugging
    ctx = self.context
    if ctx is None:
      print('Region.view(): empty region, cannot get context')
      return
    writer = IRWriter(ctx, True, None, None)
    dump = writer.write_region(self)
    _view_content_helper(dump, self.name)

  def dump(self) -> None:
    # for debugging
    ctx = self.context
    if ctx is None:
      print('Region.view(): empty region, cannot get context')
      return
    writer = IRWriter(ctx, False, None, None)
    dump = writer.write_region(self)
    print(dump.decode('utf-8'))


_SymbolTypeVar = typing.TypeVar('_SymbolTypeVar', bound='Symbol')

@_IRInnerConstructJsonTypeName("symbol_r")
class SymbolTableRegion(Region, collections.abc.Sequence, typing.Generic[_SymbolTypeVar]):
  # if a region is a symbol table, it will always have one block
  _lookup_dict : collections.OrderedDict[str, _SymbolTypeVar]
  _block : Block
  _anonymous_count : int # we use numeric default names if a symbol without name is added

  def __init__(self, context : Context) -> None:
    super().__init__()
    self._block = Block.create("", context)
    self.push_back(self._block)
    self._anonymous_count = 0
    self._lookup_dict = collections.OrderedDict()

  def copy_init(self, *, init_src: SymbolTableRegion[_SymbolTypeVar], value_mapper: IRValueMapper, **kwargs):
    for symbol in init_src:
      new_symbol = symbol.clone(value_mapper)
      assert isinstance(new_symbol, Symbol)
      self.add(new_symbol)

  def _get_anonymous_name(self):
    result = str(self._anonymous_count)
    self._anonymous_count += 1
    return result

  def _drop_symbol(self, name : str):
    self._lookup_dict.pop(name, None)

  def _add_symbol(self, symbol : _SymbolTypeVar):
    # make sure _add_symbol is called BEFORE adding the symbol to list
    # to avoid infinite recursion
    assert isinstance(symbol, Symbol)
    #if len(symbol.name) == 0:
    #  symbol.name = self._get_anonymous_name()
    assert symbol.name not in self._lookup_dict
    self._lookup_dict[symbol.name] = symbol

  def _rename_symbol(self, symbol : _SymbolTypeVar, newname : str):
    assert isinstance(symbol, Symbol)
    assert newname not in self._lookup_dict
    self._lookup_dict.pop(symbol.name, None)
    self._lookup_dict[newname] = symbol

  def __getitem__(self, key : str) -> _SymbolTypeVar:
    return self._lookup_dict.get(key, None) # type: ignore

  def get(self, key : str) -> _SymbolTypeVar:
    return self._lookup_dict.get(key, None) # type: ignore

  def keys(self):
    return self._lookup_dict.keys()

  def __iter__(self):
    return iter(self._lookup_dict.values())

  def __len__(self):
    return len(self._lookup_dict)

  def __contains__(self, value: _SymbolTypeVar) -> bool:
    return self._lookup_dict.get(value.name, None) == value

  def add(self, symbol : _SymbolTypeVar):
    assert isinstance(symbol, Symbol)
    self._block.push_back(symbol)

@IRObjectJsonTypeName('literal_l')
@IRObjectUniqueTrait
class Literal(Value):
  # __slots__ = ('_value')
  _value : typing.Any

  def construct_init(self, *, ty: ValueType, value : typing.Any, **kwargs) -> None:
    super().construct_init(ty = ty, **kwargs)
    self._value = value

  def json_import_init(self, *, importer: IRJsonImporter, init_src: dict, **kwargs) -> None:
    raise PPNotImplementedError('Subclass should override this')

  @property
  def value(self) -> typing.Any:
    return self._value

  def get_context(self) -> Context:
    return super().valuetype.context

  @staticmethod
  def _get_literal_impl(literal_cls : type, value : typing.Any, context : Context) -> typing.Any:
    return context.get_literal_uniquing_dict(literal_cls).get_or_create(value, lambda : literal_cls(init_mode = IRObjectInitMode.CONSTRUCT, context = context, value = value))

@IRObjectJsonTypeName('undef_l')
class UndefLiteral(Literal):
  # 我们会使用 Undef 在特定条件下替换别的值
  # （比如如果一个Op要被删了，如果它还在被使用的话，所有的引用都会替换为这种值）

  @property
  def value(self) -> str:
    return super().value

  @staticmethod
  def get(ty : ValueType, msg : str):
    return ty.context.get_literal_uniquing_dict(UndefLiteral).get_or_create((ty, msg),
      lambda : UndefLiteral(init_mode = IRObjectInitMode.CONSTRUCT, context = ty.context, ty = ty, value = msg))

@IRObjectJsonTypeName('class_l')
class ClassLiteral(Literal):
  # 某些情况下我们需要用一个字面值来找到一个类
  # （比如 VNModel 中我们按名字查找转场效果）
  # 这就是使用该类型的时候了

  def construct_init(self, *, context : Context, baseclass : type,  value: type, **kwargs) -> None:
    ty = ClassType.get(baseclass, context)
    return super().construct_init(ty=ty, value=value, **kwargs)

  @property
  def value(self) -> type:
    return super().value

  @staticmethod
  def get(baseclass : type, value : type, context : Context) -> ClassLiteral:
    return context.get_literal_uniquing_dict(ClassLiteral).get_or_create((baseclass, value),
      lambda : ClassLiteral(init_mode = IRObjectInitMode.CONSTRUCT, context = context, baseclass = baseclass, value = value)) # type: ignore

@IRObjectJsonTypeName('constexpr_ce')
@IRObjectUniqueTrait
class ConstExpr(Value, User):
  # ConstExpr 是引用其他 Value 的 Value，自身像 Literal 那样也是保证无重复的。虽然大部分参数应该是 Literal 但也可以用别的
  # ConstExpr 与 Literal 的区别是， ConstExpr 可以引用从 Operation 来的值(包括 Operation的引用和 OpResult)
  # Literal 一定可以跨越顶层 Operation 的迭代（或者说从一种 IR 到另一种 IR）， ConstExpr 没有这种要求
  # 在有依赖关系的 Operation 被更换或者被删除时， ConstExpr 会被删掉， Literal 的值不可能有改变
  # 子 IR 类型可以定义新的 Literal 和 ConstExpr ，并以“是否可能依赖 Operation”为标准区分两者
  # 不过 ConstExpr 也可以不引用从 Operation 来的值
  # 一般而言推荐子类只继承自 ConstExpr ，不使用 LiteralExpr

  def construct_init(self, *, ty: ValueType, values : typing.Iterable[Value], **kwargs) -> None:
    super().construct_init(ty=ty, **kwargs)
    for v in values:
      self.add_operand(v)

  def destroy_constant(self):
    # 使用的值被删除，使得该表达式也该被删除时，本函数会被调用
    self.remove_dead_constant_users()
    if not self.use_empty():
      raise PPInternalError('Destroying ConstExpr in use')
    self_cls = type(self)
    key_tuple = (self_cls, *[v.value for v in self.operanduses()])
    self.valuetype.context.get_constexpr_uniquing_dict(self_cls).erase_constant(key_tuple)
    self.drop_all_uses()
    self.destroy_value()

  def remove_dead_constant_users(self):
    dead_cexpr : list[ConstExpr] = []
    for u in self.uses:
      user = u.user
      if isinstance(user, ConstExpr):
        user.remove_dead_constant_users()
        if user.use_empty():
          dead_cexpr.append(user)
    for user in dead_cexpr:
      user.destroy_constant()

  def get_value_tuple(self) -> tuple[Value]:
    return tuple(u.value for u in self.operanduses())


  @classmethod
  def _get_impl(cexpr_cls, ty : ValueType, values : typing.Iterable[Value]):
    key_tuple = (cexpr_cls, *values)
    return ty.context.get_constexpr_uniquing_dict(cexpr_cls).get_or_create(key_tuple,
      lambda: cexpr_cls(init_mode = IRObjectInitMode.CONSTRUCT, context = ty.context, values = values))

class LiteralUniquingDict:
  _ty : type
  _inst_dict : collections.OrderedDict[typing.Any, typing.Any]

  def __init__(self, ty : type) -> None:
    self._ty = ty
    self._inst_dict = collections.OrderedDict()

  def get_or_create(self, data : typing.Any, ctor : typing.Callable) -> Value:
    if data in self._inst_dict:
      return self._inst_dict[data]
    inst = ctor()
    self._inst_dict[data] = inst
    return inst

class ConstExprUniquingDict(LiteralUniquingDict):
  def __init__(self, ty: type) -> None:
    super().__init__(ty)

  def erase_constant(self, data : typing.Any):
    del self._inst_dict[data]

_AssetTV = typing.TypeVar('_AssetTV', bound='AssetData')

class Context:
  # the object that we use to keep track of unique constructs (types, constant expressions, file assets)
  _stateless_type_dict : collections.OrderedDict[type, ValueType]
  _parameterized_type_dict : collections.OrderedDict[type, ParameterizedTypeUniquingDict]
  _literal_dict : collections.OrderedDict[type, LiteralUniquingDict]
  _constexpr_dict : collections.OrderedDict[type, ConstExprUniquingDict]
  _asset_data_list : IList[AssetData, Context]
  _asset_temp_dir : tempfile.TemporaryDirectory | None # created on-demand
  _asset_import_cache : collections.OrderedDict[str, AssetData] # for avoiding importing external assets multiple times during import
  _null_location : Location # a dummy location value with only a reference to the context
  _difile_dict : collections.OrderedDict[str, DIFile] # from filepath string to the DIFile object
  _diloc_dict : collections.OrderedDict[DIFile, collections.OrderedDict[tuple[int, int, int], DILocation]] # <file> -> <page, row, column> -> DILocation
  _file_auditor : FileAccessAuditor

  def __init__(self, file_auditor : FileAccessAuditor | None = None) -> None:
    self._stateless_type_dict = collections.OrderedDict()
    self._parameterized_type_dict = collections.OrderedDict()
    self._asset_data_list = IList(self)
    self._asset_temp_dir = None
    self._asset_import_cache = collections.OrderedDict()
    self._literal_dict = collections.OrderedDict()
    self._constexpr_dict = collections.OrderedDict()
    self._null_location = Location(init_mode=IRObjectInitMode.CONSTRUCT, context=self)
    self._difile_dict = collections.OrderedDict()
    self._diloc_dict = collections.OrderedDict()
    self._file_auditor = file_auditor if file_auditor is not None else FileAccessAuditor()
    mimetypes.init()

  def __del__(self):
    if self._asset_temp_dir:
      del self._asset_temp_dir
      self._asset_temp_dir = None

  def get_stateless_type(self, ty : type) -> typing.Any:
    if ty in self._stateless_type_dict:
      return self._stateless_type_dict[ty]
    instance = ty(init_mode=IRObjectInitMode.CONSTRUCT, context=self)
    self._stateless_type_dict[ty] = instance
    return instance

  def get_or_create_parameterized_type(self, ty : typing.Type[T], parameters : typing.List[ValueType | type | int | str | bool | None], ctor : typing.Callable) -> T:
    return self.get_parameterized_type_dict(ty).get_or_create(parameters, ctor) # type: ignore

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

  def get_literal_uniquing_dict(self, ty : type) -> LiteralUniquingDict:
    if ty in self._literal_dict:
      return self._literal_dict[ty]
    result = LiteralUniquingDict(ty)
    self._literal_dict[ty] = result
    return result

  def get_constexpr_uniquing_dict(self, ty : type) -> ConstExprUniquingDict:
    if ty in self._constexpr_dict:
      return self._constexpr_dict[ty]
    result = ConstExprUniquingDict(ty)
    self._constexpr_dict[ty] = result
    return result

  def get_file_auditor(self) -> FileAccessAuditor:
    return self._file_auditor

  def create_name_for_asset(self, underdir : str, preferred_path : str, data : bytes) -> str:
    # 我们把所有素材文件都放一个目录下
    # 用该函数给素材命名，保证文件名不重复
    # 如果 preferred_path 有提供，则我们保证最终使用的文件名一定含有相同的后缀名
    # （这是为了保证使用后缀名确定格式的资源能够正常读取）
    if len(preferred_path) > 0:
      preferred_path = os.path.basename(preferred_path)
    basename = ''
    ext = '.bin'
    if len(preferred_path) > 0:
      basename, ext = os.path.splitext(preferred_path)
    if len(basename) == 0:
      m = hashlib.sha512()
      m.update(data)
      basename = m.digest().hex()
    index = 0
    cur_full_path = basename + ext
    while os.path.exists(os.path.join(underdir, cur_full_path)):
      index += 1
      cur_full_path = basename + '_' + str(index) + ext
    return cur_full_path

  def _create_asset_data_embedded(self, asset_cls : typing.Type[_AssetTV], full_embed_path : str, data : bytes, asset_format : typing.Any) -> _AssetTV:
    tmppath = self.get_backing_dir()
    filename = self.create_name_for_asset(tmppath.name, full_embed_path, data)
    backing_store_path = os.path.join(tmppath.name, filename)
    with open(backing_store_path, "wb") as f:
      f.write(data)
    loc = self.get_DIFile(full_embed_path)
    asset = asset_cls(init_mode=IRObjectInitMode.CONSTRUCT, context=self, backing_store_path=backing_store_path, format = asset_format, loc = loc)
    self._asset_data_list.push_back(asset)
    return asset

  def _get_or_create_asset_data_external(self, asset_cls : typing.Type[_AssetTV], ext_path : str, asset_format : typing.Any) -> _AssetTV:
    if ext_path in self._asset_import_cache:
      result = self._asset_import_cache[ext_path]
      assert isinstance(result, asset_cls)
      return result
    loc = self.get_DIFile(ext_path)
    asset = asset_cls(init_mode=IRObjectInitMode.CONSTRUCT, context=self, backing_store_path=ext_path, format=asset_format, loc=loc)
    self._asset_data_list.push_back(asset)
    self._asset_import_cache[ext_path] = asset
    return asset

  def get_or_create_unknown_asset_data_external(self, ext_path : str) -> AssetData | None:
    assert self._file_auditor.check_is_path_accessible(ext_path)
    mimety, encoding = mimetypes.guess_type(ext_path)
    if mimety is None:
      return None
    if not os.path.isfile(ext_path):
      return None
    if img_format := ImageAssetData.get_format_from_mime_type(mimety):
      return self.get_or_create_image_asset_data_external(ext_path, img_format)
    if audio_format := AudioAssetData.get_format_from_mime_type(mimety):
      return self.get_or_create_audio_asset_data_external(ext_path, audio_format)
    return None

  def create_image_asset_data_embedded(self, full_embed_path : str, data : bytes, img_format : str | None = None) -> ImageAssetData:
    return self._create_asset_data_embedded(ImageAssetData, full_embed_path, data, img_format)

  def get_or_create_image_asset_data_external(self, ext_path : str, img_format : str | None = None) -> ImageAssetData:
    assert self._file_auditor.check_is_path_accessible(ext_path)
    return self._get_or_create_asset_data_external(ImageAssetData, ext_path, img_format)

  def create_audio_asset_data_embedded(self, full_embed_path : str, data : bytes, audio_format : str | None = None) -> AudioAssetData:
    return self._create_asset_data_embedded(AudioAssetData, full_embed_path, data, audio_format)

  def get_or_create_audio_asset_data_external(self, ext_path : str, audio_format : str | None = None) -> AudioAssetData:
    assert self._file_auditor.check_is_path_accessible(ext_path)
    return self._get_or_create_asset_data_external(AudioAssetData, ext_path, audio_format)

  @property
  def null_location(self) -> Location:
    return self._null_location

  def get_DIFile(self, path : str) -> DIFile:
    if path in self._difile_dict:
      return self._difile_dict[path]
    result = DIFile(init_mode=IRObjectInitMode.CONSTRUCT, context = self, filepath=path)
    self._difile_dict[path] = result
    return result

  def get_DILocation(self, file : str | DIFile, page : int, row : int, column: int) -> DILocation:
    difile = file
    if isinstance(file, str):
      difile = self.get_DIFile(file)
    assert isinstance(difile, DIFile)
    assert difile.context is self
    if difile in self._diloc_dict:
      filedict = self._diloc_dict[difile]
    else:
      filedict = collections.OrderedDict()
      self._diloc_dict[difile] = filedict
    key = (page, row, column)
    if key in filedict:
      return filedict[key]
    # file : DIFile, page : int, row : int, column : int,
    result = DILocation(init_mode=IRObjectInitMode.CONSTRUCT, context=self, file=difile, page=page, row=row, column=column)
    filedict[key] = result
    return result

# ------------------------------------------------------------------------------
# Assets
# ------------------------------------------------------------------------------

_DataTV = typing.TypeVar('_DataTV')
_FmtTV = typing.TypeVar('_FmtTV')

@IRObjectJsonTypeName('assetdata_ad')
@IRObjectUniqueTrait
class AssetData(Value, IListNode, typing.Generic[_DataTV, _FmtTV]):
  # an asset data represent a pure asset; no (IR-related) metadata
  # any asset data is immutable; they cannot be modified after creation
  # if we want to convert the type, a new asset data instance should be created

  # derived class can use their own judgement to decide storage policy
  # if the asset tends to be small (<16KB), we can store them in memory
  # otherwise we can store them on disk
  # however, in general if we want to make sure the hash of asset file is unchanged for copying and load/storing,
  # they shall be saved on disk

  # if analysis would like to have a big working set involving multiple assets, they can implement their own cache

  _loc : DIFile | None # non-null if the asset is from external file (i.e., not created on the fly)
  _backing_store_path : str # if it is in the temporary directory, this asset data owns it; otherwise the source is read-only; empty string if no backing store
  _data : _DataTV | None
  _format : _FmtTV | None

  def construct_init(self, *, context : Context, backing_store_path : str = '', data : _DataTV | None = None, format : _FmtTV | None = None, loc : DIFile | None = None, **kwargs) -> None:
    ty = AssetDataReferenceType.get(context)
    super().construct_init(context=context, ty=ty, **kwargs)
    # context._add_asset_data(self)
    self._loc = loc
    self._backing_store_path = backing_store_path
    self._data = data
    # invariants check: either backing_store_path is provided, or data is provided
    assert (self._data is not None) == (len(self._backing_store_path) == 0)
    if format is not None:
      self._format = format
    else:
      self._format = self.get_format_in_construction(backing_store_path, data) # pylint: disable=assignment-from-none

  def get_format_in_construction(self, backing_store_path : str, data : _DataTV | None) -> _FmtTV | None:
    return None # type: ignore

  #@property
  #def backing_store_path(self) -> str:
  #  return self._backing_store_path

  @property
  def backing_store_path(self) -> str:
    return self._backing_store_path

  @property
  def data(self) -> _DataTV | None:
    return self._data

  @property
  def format(self) -> _FmtTV | None:
    return self._format

  @property
  def location(self) -> DIFile | None:
    return self._loc

  @classmethod
  def get_pretty_name(cls) -> str:
    return cls.__name__

  def __str__(self) -> str:
    result = self.__class__.get_pretty_name()
    if len(self._backing_store_path) > 0:
      result += ' ' + self._backing_store_path
    elif self._loc is not None:
      result += ' @' + str(self._loc)
    if self._format is not None:
      result += ' [' + str(self._format) + ']'
    return result

  def load(self) -> _DataTV:
    # load the asset data to memory
    # should be implemented in the derived classes
    if self._data is not None:
      return self._data
    return self.load_from_storage()

  def load_from_storage(self) -> _DataTV:
    # load the asset from the backing store path
    raise PPNotImplementedError()

  def export(self, dest_path : str) -> None:
    # save the asset data to the specified path
    # we do not try to create another AssetData instance here
    # if the caller want one, they can always create one using the dest_path
    raise PPNotImplementedError()

  @staticmethod
  def secure_overwrite(exportpath: str, write_callback: typing.Callable):
    tmpfilepath = exportpath + ".tmp"
    parent_path = pathlib.Path(tmpfilepath).parent
    os.makedirs(parent_path, exist_ok=True)
    isOldExist = os.path.isfile(exportpath)
    with open(tmpfilepath, 'wb') as f:
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

@IRObjectJsonTypeName('bytes_ad')
class BytesAssetData(AssetData[bytes, None]):
  def load_from_storage(self) -> bytes:
    with open(self.backing_store_path, 'rb') as f:
      return f.read()

  def export(self, dest_path: str) -> None:
    if data := self.data:
      with open(dest_path, 'wb') as f:
        f.write(data)
    else:
      shutil.copy2(self.backing_store_path, dest_path, follow_symlinks=False)

  _tr_bytesassetdata_name = TR_preppipe.tr("bytesassetdata_name",
    en="Binary Asset",
    zh_cn="二进制资源",
    zh_hk="二進製資源",
  )

  @classmethod
  def get_pretty_name(cls) -> str:
    return cls._tr_bytesassetdata_name.get()

@IRObjectJsonTypeName('image_ad')
class ImageAssetData(AssetData[PIL.Image.Image, str]):
  _SUPPORTED_FORMAT_BIDICT : typing.ClassVar[bidict.bidict[str, str]] | None = None
  @staticmethod
  def get_format_dict():
    if ImageAssetData._SUPPORTED_FORMAT_BIDICT is not None:
      return ImageAssetData._SUPPORTED_FORMAT_BIDICT
    ImageAssetData._SUPPORTED_FORMAT_BIDICT = bidict.bidict()
    mimetypes.init()
    # make sure basic types are in
    assert '.png' in mimetypes.types_map
    assert '.jpg' in mimetypes.types_map
    for ext, fmt in PIL.Image.registered_extensions().items():
      if ext not in mimetypes.types_map:
        continue
      mime = mimetypes.types_map[ext]
      # skip 1-to-N mappings
      if mime in ImageAssetData._SUPPORTED_FORMAT_BIDICT or fmt in ImageAssetData._SUPPORTED_FORMAT_BIDICT.inverse:
        continue
      ImageAssetData._SUPPORTED_FORMAT_BIDICT[mime] = fmt
    return ImageAssetData._SUPPORTED_FORMAT_BIDICT

  @staticmethod
  def get_format_from_mime_type(mime : str) -> str | None:
    d = ImageAssetData.get_format_dict()
    if mime in d:
      return d[mime]
    return None

  @staticmethod
  def get_mime_type_from_format(fmt : str) -> str | None:
    d =  ImageAssetData.get_format_dict().inverse
    if fmt in d:
      return d[fmt]
    return None

  def get_format_in_construction(self, backing_store_path: str, data: PIL.Image.Image | None) -> str | None:
    if len(backing_store_path) == 0:
      assert data is not None
      return data.format # can be None
    else:
      # verify that the image file is valid
      with PIL.Image.open(backing_store_path) as image:
        format = image.format
        assert format is not None and len(format) > 0 # should have a format if loaded from storage
        image.verify()
        return format.lower()

  def load_from_storage(self) -> PIL.Image.Image:
    return PIL.Image.open(self.backing_store_path)

  def export(self, dest_path : str) -> None:
    if data := self._data:
      data.save(dest_path)
      return
    # we do file copy iff the source and dest format matches
    # otherwise, we open the source file and save it in the destination
    _srcname, srcext = os.path.splitext(self.backing_store_path)
    _destname, destext = os.path.splitext(dest_path)
    if srcext.lower() == destext.lower():
      shutil.copy2(self.backing_store_path, dest_path, follow_symlinks=False)
    else:
      image = PIL.Image.open(self.backing_store_path)
      image.save(dest_path)

  _tr_imagesassetdata_name = TR_preppipe.tr("imagesassetdata_name",
    en="Image Asset",
    zh_cn="图片资源",
    zh_hk="圖片資源",
  )

  @classmethod
  def get_pretty_name(cls) -> str:
    return cls._tr_imagesassetdata_name.get()

@IRObjectJsonTypeName('audio_ad')
class AudioAssetData(AssetData[pydub.AudioSegment, str]):
  _SUPPORTED_FORMAT_BIDICT : typing.ClassVar[bidict.bidict[str, str]] | None = None

  # exclude formats that MAY contain video (e.g., webm)
  _SUPPORTED_FORMATS : typing.ClassVar[tuple[str, ...]] = ("wav", "aac", "ogg", "m4a", "aiff", "flac", "mp3")

  @staticmethod
  def get_format_dict():
    if AudioAssetData._SUPPORTED_FORMAT_BIDICT is not None:
      return AudioAssetData._SUPPORTED_FORMAT_BIDICT
    AudioAssetData._SUPPORTED_FORMAT_BIDICT = bidict.bidict()
    mimetypes.init()
    for fmt in AudioAssetData._SUPPORTED_FORMATS:
      mime = mimetypes.types_map['.' + fmt]
      AudioAssetData._SUPPORTED_FORMAT_BIDICT[mime] = fmt
    return AudioAssetData._SUPPORTED_FORMAT_BIDICT

  @staticmethod
  def get_format_from_mime_type(mime : str) -> str | None:
    d = AudioAssetData.get_format_dict()
    if mime in d:
      return d[mime]
    return None

  @staticmethod
  def get_mime_type_from_format(fmt : str) -> str | None:
    d =  AudioAssetData.get_format_dict().inverse
    if fmt in d:
      return d[fmt]
    return None

  def get_format_in_construction(self, backing_store_path: str, data: pydub.AudioSegment | None) -> str | None:
    if len(backing_store_path) == 0:
      return None
    else:
      _basepath, ext = os.path.splitext(backing_store_path)
      assert ext[0] == '.'
      ext = ext[1:].lower()
      if ext in self._SUPPORTED_FORMATS:
        return ext
      else:
        raise PPInternalError("Unrecognized audio file format: " + ext)

  @property
  def format(self) -> str | None:
    return self._format

  def load_from_storage(self) -> pydub.AudioSegment:
    return pydub.AudioSegment.from_file(self._backing_store_path, format = self._format)

  def export(self, dest_path: str) -> None:
    _basepath, ext = os.path.splitext(dest_path)
    assert ext[0] == '.'
    fmt = ext[1:].lower()
    assert fmt in self._SUPPORTED_FORMATS
    if self._data is not None:
      self._data.export(dest_path, format=fmt)
      return
    if fmt == self._format:
      shutil.copy2(self._backing_store_path, dest_path, follow_symlinks=False)
    else:
      data : pydub.AudioSegment = pydub.AudioSegment.from_file(self._backing_store_path, format = self._format)
      data.export(dest_path, format=fmt)

  _tr_audiosassetdata_name = TR_preppipe.tr("audiosassetdata_name",
    en="Audio Asset",
    zh_cn="音频资源",
    zh_hk="音頻資源",
  )

  @classmethod
  def get_pretty_name(cls) -> str:
    return cls._tr_audiosassetdata_name.get()

@IRWrappedStatelessClassJsonName('asset_placeholder_trait')
class AssetPlaceholderTrait:
  # 如果某个值表示占位资源，则应继承自该类来告诉其余代码
  pass

@IRWrappedStatelessClassJsonName('asset_decl_trait')
class AssetDeclarationTrait:
  # 如果某个值表示声明的资源（即内容暂缺的外部资源），则应继承自该类来告诉其余代码
  pass

# ------------------------------------------------------------------------------
# Debug info (DI)
# ------------------------------------------------------------------------------

@IRObjectJsonTypeName('difile_dl')
@IRObjectMetadataTrait
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class DIFile(Location):
  filepath : str

  def construct_init(self, *, filepath : str, **kwargs) -> None:
    super(DIFile, self).construct_init(**kwargs)
    object.__setattr__(self, 'filepath', filepath)

  @staticmethod
  def get_json_repr() -> dict[str, str]:
    return {'filepath': IRJsonRepr.LOCATION_FILE_PATH.value}

  def __str__(self) -> str:
    return self.filepath

  def get_file_path(self):
    return self.filepath

@IRObjectJsonTypeName('dilocation_dl')
@IRObjectMetadataTrait
@dataclasses.dataclass(init=False, slots=True, frozen=True)
class DILocation(Location):
  # 描述一个文档位置
  # 对于文档而言，页数可以用 page breaks 来定 （ODF 有 <text:soft-page-break/>）
  # 对于表格而言，页数相当于 sheet 的序号
  # 所有信息如果有的话就从1开始，没有就用0
  # 目前我们的 DILocation 只用于给用户指出位置，暂时不会有源到源的转换，所以这里有信息损失不是大事
  file : DIFile
  page : int
  row : int
  column : int

  def construct_init(self, *, file : DIFile, page : int, row : int, column : int, **kwargs) -> None:
    super(DILocation, self).construct_init(**kwargs)
    object.__setattr__(self, 'file', file)
    object.__setattr__(self, 'page', page)
    object.__setattr__(self, 'row', row)
    object.__setattr__(self, 'column', column)

  def get_file_path(self):
    return self.file.get_file_path()

  def __str__(self) -> str:
    return str(self.file) + '#P' + str(self.page) + ':' + str(self.row) + ':' + str(self.column)

# ------------------------------------------------------------------------------
# Literals
# ------------------------------------------------------------------------------

@IRObjectJsonTypeName('int_l')
class IntLiteral(Literal):
  def construct_init(self, *, context : Context, value : int, **kwargs) -> None:
    assert isinstance(value, int)
    ty = IntType.get(context)
    return super().construct_init(ty=ty, value=value, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return IntType

  @property
  def value(self) -> int:
    return super().value

  @staticmethod
  def get(value : int, context : Context) -> IntLiteral:
    return Literal._get_literal_impl(IntLiteral, value, context)

@IRObjectJsonTypeName('int_tuple_l')
class IntTupleLiteral(Literal):
  # 整数元组，一般用于像素坐标或大小
  def construct_init(self, *, context : Context, value: tuple[int, ...], **kwargs) -> None:
    return super().construct_init(ty=VoidType.get(context), value=value, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return VoidType

  @property
  def value(self) -> tuple[int, ...]:
    return super().value

  @staticmethod
  def get(value : tuple[int, ...], context : Context) -> IntTupleLiteral:
    return Literal._get_literal_impl(IntTupleLiteral, value, context)

@IRObjectJsonTypeName('bool_l')
class BoolLiteral(Literal):
  def construct_init(self, *, context : Context, value: bool, **kwargs) -> None:
    assert isinstance(value, bool)
    ty = BoolType.get(context)
    super().construct_init(ty=ty, value=value, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return BoolType

  @property
  def value(self) -> bool:
    return super().value

  @staticmethod
  def get(value : bool, context : Context) -> BoolLiteral:
    return Literal._get_literal_impl(BoolLiteral, value, context)

@IRObjectJsonTypeName('float_l')
class FloatLiteral(Literal):
  def construct_init(self, *, context : Context, value: decimal.Decimal, **kwargs) -> None:
    assert isinstance(value, decimal.Decimal)
    ty = FloatType.get(context)
    super().construct_init(ty=ty, value=value, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return FloatType

  @property
  def value(self) -> decimal.Decimal:
    return super().value

  @staticmethod
  def get(value : decimal.Decimal, context : Context) -> FloatLiteral:
    assert isinstance(value, decimal.Decimal)
    return Literal._get_literal_impl(FloatLiteral, value, context)

@IRObjectJsonTypeName('float_tuple_l')
class FloatTupleLiteral(Literal):
  # 浮点数元组，用于描述锚点位置等
  def construct_init(self, *, context : Context, value: tuple[decimal.Decimal, ...], **kwargs) -> None:
    return super().construct_init(ty=VoidType.get(context), value=value, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return VoidType

  @property
  def value(self) -> tuple[decimal.Decimal, ...]:
    return super().value

  @staticmethod
  def get(value : tuple[decimal.Decimal, ...], context : Context) -> FloatTupleLiteral:
    return Literal._get_literal_impl(FloatTupleLiteral, value, context)

@IRObjectJsonTypeName('str_l')
class StringLiteral(Literal):
  # 字符串常量的值不包含样式等信息，就是纯字符串

  def construct_init(self, *, context : Context, value: str, **kwargs) -> None:
    assert isinstance(value, str)
    ty = StringType.get(context)
    super().construct_init(ty=ty, value=value, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return StringType

  @property
  def value(self) -> str:
    return super().value

  def get_string(self) -> str:
    return self.value

  def __str__(self) -> str:
    return self.value

  @staticmethod
  def get(value : str, context : Context) -> StringLiteral:
    return Literal._get_literal_impl(StringLiteral, value, context)

@IRObjectJsonTypeName('color_l')
class ColorLiteral(Literal):
  def construct_init(self, *, context : Context, value: Color, **kwargs) -> None:
    assert isinstance(value, Color)
    super().construct_init(ty=ColorType.get(context), value=value, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return ColorType

  @property
  def value(self) -> Color:
    return super().value

  @staticmethod
  def get(value : Color, context : Context) -> ColorLiteral:
    return Literal._get_literal_impl(ColorLiteral, value, context)

@IRObjectJsonTypeName('text_style_l')
class TextStyleLiteral(Literal):
  # 文字样式常量只包含文字样式信息

  def construct_init(self, *, context : Context, value: tuple[tuple[TextAttribute, typing.Any]], **kwargs) -> None:
    ty = TextStyleType.get(context)
    super().construct_init(ty=ty, value=value, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return TextStyleType

  @property
  def value(self) -> tuple[tuple[TextAttribute, typing.Any]]:
    return super().value

  @staticmethod
  def get(value : tuple[tuple[TextAttribute, typing.Any]] | dict[TextAttribute, typing.Any], context : Context) -> TextStyleLiteral:
    if isinstance(value, dict):
      value = TextStyleLiteral.get_style_tuple(value)
    assert isinstance(value, tuple)
    return Literal._get_literal_impl(TextStyleLiteral, value, context)

  @staticmethod
  def get_added(base : TextStyleLiteral, override : TextStyleLiteral) -> TextStyleLiteral:
    if base == override:
      return base
    basedict = {}
    for k, v in base.value:
      basedict[k] = v
    for k, v in override.value:
      basedict[k] = v
    return TextStyleLiteral.get(basedict, base.context)

  @staticmethod
  def get_subtracted(base : TextStyleLiteral, result : TextStyleLiteral) -> TextStyleLiteral | None:
    if base is result:
      return None
    has_subtracted = False
    styledict = {}
    for k, v in result.value:
      styledict[k] = v
    for k, v in base.value:
      if k in styledict:
        if styledict[k] == v:
          # 现在的值在 base 中存在
          del styledict[k]
          has_subtracted = True
    if has_subtracted:
      return TextStyleLiteral.get(styledict, result.context)
    return result

  @staticmethod
  def get_style_tuple(styles : dict[TextAttribute, typing.Any]):
    stylelist = []
    for attr, v in styles.items():
      # 检查样式的值是否符合要求
      # 同时忽略部分VNModel不支持的属性
      isDiscard = False
      match attr:
        case TextAttribute.Bold:
          if v is not None and v is not True:
            raise PPInternalError("文本属性“加粗”不应该带参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
          if v is None:
            v = True
        case TextAttribute.Italic:
          if v is not None and v is not True:
            raise PPInternalError("文本属性“斜体”不应该带参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
          if v is None:
            v = True
        case TextAttribute.Hierarchy:
          # VNModel不支持该属性
          isDiscard = True
        case TextAttribute.Size:
          if not isinstance(v, int):
            raise PPInternalError("文本属性“大小”应该带一个整数型参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.TextColor:
          if not isinstance(v, Color):
            raise PPInternalError("文本属性“文本颜色”应该带一个颜色类型的参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.BackgroundColor:
          if not isinstance(v, Color):
            raise PPInternalError("文本属性“背景颜色”应该带一个颜色类型的参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
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

_LiteralExprTV = typing.TypeVar('_LiteralExprTV', bound = 'LiteralExpr')

@IRObjectJsonTypeName('literalexpr_le')
class LiteralExpr(Literal, User):
  # 字面值表达式是只引用其他字面值的表达式
  # 所有字面值表达式都只由：(1)表达式类型，(2)参数 这两项决定
  def construct_init(self, *, ty: ValueType, value_tuple: tuple[Literal | AssetData, ...], **kwargs) -> None:
    super().construct_init(ty=ty, value=value_tuple, **kwargs)
    for v in value_tuple:
      assert isinstance(v, (Literal, AssetData))
      self.add_operand(v)

  def get_value_tuple(self) -> tuple[Literal | AssetData, ...]:
    return self.value

  @classmethod
  def _get_literalexpr_impl(cls : typing.Type[_LiteralExprTV], value_tuple, context) -> _LiteralExprTV:
    return context.get_literal_uniquing_dict(cls).get_or_create(value_tuple,
      lambda : cls(init_mode=IRObjectInitMode.CONSTRUCT, context=context, value_tuple=value_tuple))

@IRObjectJsonTypeName('text_frag_le')
class TextFragmentLiteral(LiteralExpr):
  # 文本常量的值包含字符串以及样式信息（大小字体、字体颜色、背景色（高亮颜色），或是附注（Ruby text））
  # 单个文本片段常量内容所使用的样式需是一致的，如果不一致则可以把内容进一步切分，按照样式来进行分节
  # 文本片段常量的“值”（value）是【对字符串常量的引用】+【样式信息元组】的元组(tuple)
  # 样式信息元组内的每一项都是(样式，值)组成的元组，这些项将根据样式的枚举值进行排序
  # TODO 我们其实没有必要对文本内容提供去重。。。目前没有任何部分对

  def construct_init(self, *, context : Context, value_tuple : tuple[StringLiteral, TextStyleLiteral], **kwargs) -> None:
    assert len(value_tuple) == 2 and isinstance(value_tuple[0], StringLiteral) and isinstance(value_tuple[1], TextStyleLiteral)
    ty = TextType.get(context)
    super().construct_init(ty=ty, value_tuple=value_tuple, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return TextType

  @property
  def value(self) -> tuple[StringLiteral, TextStyleLiteral]:
    return super().value

  @property
  def content(self) -> StringLiteral:
    return self.get_operand(0)

  @property
  def style(self) -> TextStyleLiteral:
    return self.get_operand(1)

  def get_string(self) -> str:
    return self.content.value

  def __str__(self) -> str:
    return 'TextFragment[' + str(self.style) + ']"' + self.get_string() + '"'

  @staticmethod
  def get(context : Context, string : StringLiteral, styles : TextStyleLiteral) -> TextFragmentLiteral:
    if not isinstance(string, StringLiteral):
      raise PPInternalError("string 参数应为对字符串常量的引用")
    if not isinstance(styles, TextStyleLiteral):
      raise PPInternalError("styles 参数应为对文本样式常量的引用")
    return TextFragmentLiteral._get_literalexpr_impl((string, styles), context)

@IRObjectJsonTypeName('strlist_le')
class StringListLiteral(LiteralExpr):
  # 字符串列表字面值由零到N个字符串字面值组成
  # 一般用于像属性列表（每个属性一个字符串）或是内嵌汇编（每行一个字符串）等需要多个字符串的场景
  # 如果用在 OpOperand 上且字符串会经常变动，则应使用 OpOperand[StringLiteral] 而不是 OpOperand[StringListLiteral]
  def construct_init(self, *, context : Context, value_tuple: tuple[StringLiteral, ...], **kwargs) -> None:
    ty = StringType.get(context)
    return super().construct_init(ty=ty, value_tuple=value_tuple, **kwargs)

  @staticmethod
  def get_fixed_value_type():
    return StringType

  def __str__(self) -> str:
    return "StringListLiteral[" + ','.join(['"' + v.get_string() + '"' for v in self.value]) + ']'

  @staticmethod
  def _check_value_tuple(value: tuple[StringLiteral, ...]) -> None:
    assert isinstance(value, tuple) and all(isinstance(v, StringLiteral) for v in value)

  @staticmethod
  def get(context : Context, value : typing.Iterable[StringLiteral]) -> StringListLiteral:
    value_tuple = tuple(value)
    return StringListLiteral._get_literalexpr_impl(value_tuple, context)

  def has_single_value(self) -> bool:
    return len(self.value) == 1

@IRObjectJsonTypeName('enum_l')
class EnumLiteral(typing.Generic[T], Literal):
  # 用于将 Python Enum 打包成字面值
  # 用于 JSON 输入输出时，如果枚举类型不存在或字段值不存在，则使用 UnknownEnumLiteral 进行替代

  def construct_init(self, *, context : Context, value: T, **kwargs) -> None:
    assert isinstance(value, enum.Enum)
    ty = EnumType.get(type(value), context)
    super().construct_init(ty=ty, value=value, **kwargs)

  # 我们需要 value 的值来确定类型，所以不覆盖 get_fixed_value_type()

  @property
  def value(self) -> T:
    return super().value

  @staticmethod
  def get(context : Context, value : T) -> EnumLiteral[T]:
    return Literal._get_literal_impl(EnumLiteral, value, context)

class UnknownEnumLiteral(Literal):
  # 用于 JSON 输入输出 EnumLiteral 时，如果枚举类型或字段值不存在，则使用此值
  # （比如新版本加了一个值后使用旧代码读取新IR，或者删了一个值后用新代码读取旧IR）
  # value 应该是一个 (enum_type, enum_value) 的 tuple
  def construct_init(self, *, context : Context, value: tuple[type | str, str], **kwargs) -> None:
    enum_type : type | str = value[0]
    # enum_value : str = value[1]

    # 如果 enum_type 已知，则还是可以沿用 EnumType，否则使用空类型
    ty = None
    if isinstance(enum_type, type):
      ty = EnumType.get(enum_type, context)
    else:
      ty = VoidType.get(context)
    super().construct_init(ty=ty, value=value, **kwargs)

  @staticmethod
  def get(context : Context, enum_type : type | str, enum_value : str) -> UnknownEnumLiteral:
    return Literal._get_literal_impl(EnumLiteral, (enum_type, enum_value), context)

def convert_literal(value, ctx : Context | None, type_hint : type | None = None, type_hint_params : tuple[type,...] | None = None) -> Literal | None | bool:
  '''尝试把一个值转换为 Literal 类型的字面值(返回 Literal|None)。如果 ctx 没有提供，则只做类型检查(返回 bool)'''
  if isinstance(value, int):
    if type_hint is IntLiteral or type_hint is None:
      return IntLiteral.get(value, ctx) if ctx is not None else True
    elif type_hint is FloatLiteral:
      return FloatLiteral.get(decimal.Decimal(value), ctx) if ctx is not None else True
    else:
      return None  if ctx is not None else False
  elif isinstance(value, (float, decimal.Decimal)):
    if type_hint is FloatLiteral or type_hint is None:
      return FloatLiteral.get(decimal.Decimal(value), ctx) if ctx is not None else True
    else:
      return None if ctx is not None else False
  elif isinstance(value, str):
    if type_hint in (StringLiteral, Value) or type_hint is None:
      return StringLiteral.get(value, ctx) if ctx is not None else True
    elif type_hint is TextFragmentLiteral:
      return TextFragmentLiteral.get(ctx, StringLiteral.get(value, ctx), TextStyleLiteral.get({}, ctx)) if ctx is not None else True
    else:
      return None if ctx is not None else False
  elif isinstance(value, bool):
    if type_hint is BoolLiteral or type_hint is None:
      return BoolLiteral.get(value, ctx) if ctx is not None else True
    else:
      return None if ctx is not None else False
  elif isinstance(value, enum.Enum):
    if type_hint is EnumLiteral or type_hint is None:
      if type_hint is EnumLiteral and type_hint_params is not None:
        assert isinstance(value, type_hint_params[0])
      return EnumLiteral.get(ctx, value) if ctx is not None else True
    else:
      return None if ctx is not None else False
  else:
    return None if ctx is not None else False

# ------------------------------------------------------------------------------
# IR dumping
# ------------------------------------------------------------------------------

@dataclasses.dataclass
class IRValueMapper:
  context : Context
  option_ignore_values_with_no_use : bool = False
  value_map : dict[Value, Value] = dataclasses.field(default_factory=dict)

  def add_value_map(self, old_value : Value, new_value : Value):
    if self.option_ignore_values_with_no_use:
      if old_value.use_empty():
        return
    self.value_map[old_value] = new_value

  def get_mapped_value(self, key : Value) -> Value | None:
    if key in self.value_map:
      return self.value_map[key]
    return None

  def is_require_value_remap(self) -> bool:
    return len(self.value_map) > 0

# ------------------------------------------------------------------------------
# IR dumping
# ------------------------------------------------------------------------------

class IRWriter:
  _ctx : Context
  _asset_pin_dict : dict[AssetData, str]
  _asset_export_dict : dict[str, AssetData] | None
  _asset_export_cache : dict[AssetData, bytes] # exported HTML expression for the asset
  _output_body : io.BytesIO # the output buffer
  _output_asset_delayed : dict[str, bytes] # we use javascript to set the src attributes
  _max_indent_level : int # maximum indent level; we need this to create styles for text with different indents
  _html_dump : bool # True: output HTML; False: output text dump
  _element_id_map : dict[int, int] # id(obj) -> export_id(obj)

  def __init__(self, ctx : Context, html_dump : bool, asset_pin_dict : dict[AssetData, str] | None, asset_export_dict : dict[str, AssetData] | None) -> None:
    # assets in asset_pin_dict are already exported and we can simply use the mapped value to reference the specified asset
    # if asset_export_dict is not None, the printer expect all remaining assets to be exported with path as key and content as value
    # if asset_export_dict is None, then the printer writes all remaining assets embedded in the export HTML
    # https://stackoverflow.com/questions/38014918/how-to-reuse-base64-image-repeatedly-in-html-file
    self._ctx = ctx
    self._output_body = io.BytesIO()
    self._output_asset_delayed = {}
    if asset_pin_dict is None:
      asset_pin_dict = {}
    self._asset_pin_dict = asset_pin_dict
    self._asset_export_dict = asset_export_dict # TODO this is not used
    self._asset_export_cache = {}
    self._max_indent_level = 0
    self._html_dump = html_dump
    self._element_id_map = {}

  def get_export_id(self, obj : typing.Any) -> int:
    idvalue = id(obj)
    if idvalue in self._element_id_map:
      return self._element_id_map[idvalue]
    element_value = len(self._element_id_map)
    self._element_id_map[idvalue] = element_value
    return element_value

  def get_id_str(self, obj : typing.Any):
    elementid = self.get_export_id(obj)
    return "#" + str(elementid)

  def escape(self, htmlstring):
    if not self._html_dump:
      return htmlstring
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

  def _write_body_html(self, content : str):
    if self._html_dump:
      self._write_body(content)

  def _emit_asset_reference_to_path(self, asset : AssetData, path : str) -> bytes:
    s = "<span class=\"AssetPathReference\">" + self.escape(path) + "</span>"
    return s.encode('utf-8')

  def _write_asset_data_delayed(self, style_name_str : str, b64data : bytes, mimetype : str) -> None:
    fullstr = "data:" + mimetype + ";base64,"
    self._output_asset_delayed[style_name_str] = fullstr.encode("utf-8") + b64data

  def _write_image_asset(self, asset : ImageAssetData, style_name_str : str) -> bytes:
    b64data = None
    mimetype = None
    if asset.backing_store_path is not None:
      # 如果能猜 MIME 的话就不用读了
      if asset.format is not None:
        mimetype = ImageAssetData.get_mime_type_from_format(asset.format)
      else:
        guessed_ty, _guessed_encoding = mimetypes.guess_type(asset.backing_store_path)
        if guessed_ty is not None:
          mimetype = guessed_ty
      if mimetype is not None and mimetype in ('image/png', 'image/jpeg', 'image/gif'):
        # 不用读为 PIL.Image，直接转
        with open(asset.backing_store_path, 'rb') as f:
          image_as_bytes = f.read()
        b64data = base64.b64encode(image_as_bytes)
    if b64data is None:
      image_pil = asset.load()
      assert isinstance(image_pil, PIL.Image.Image)
      save_fmt = image_pil.format
      if save_fmt is None or save_fmt.upper() not in ('PNG', 'JPEG', 'GIF'):
        save_fmt = 'PNG'
        mimetype = 'image/png'
      else:
        mimetype = ImageAssetData.get_mime_type_from_format(save_fmt)
      buffer = io.BytesIO()
      image_pil.save(buffer, format=save_fmt)
      b64data = base64.b64encode(buffer.getvalue())
    assert mimetype is not None
    self._write_asset_data_delayed(style_name_str, b64data, mimetype)
    delayed_data_str = "<img class=\"" + style_name_str + "\"/>"
    return delayed_data_str.encode('utf-8')

  def _write_audio_asset(self, asset : AudioAssetData, style_name_str : str) -> bytes:
    b64data = None
    mimetype = None
    if asset.backing_store_path is not None:
      # 如果能猜 MIME 的话就不用读了
      if asset.format is not None:
        mimetype = AudioAssetData.get_mime_type_from_format(asset.format)
      else:
        guessed_ty, _guessed_encoding = mimetypes.guess_type(asset.backing_store_path)
        if guessed_ty is not None:
          mimetype = guessed_ty
      # https://en.wikipedia.org/wiki/HTML5_audio
      if mimetype is not None and mimetype in ('audio/wav', 'audio/mpeg', 'audio/ogg', 'audio/flac'):
        with open(asset.backing_store_path, 'rb') as f:
          data_as_bytes = f.read()
        b64data = base64.b64encode(data_as_bytes)
    if b64data is None:
      audio_seg = asset.load()
      assert isinstance(audio_seg, pydub.AudioSegment)
      mimetype = 'audio/mpeg'
      fhandle = audio_seg.export(format='mp3')
      assert isinstance(fhandle, io.BytesIO)
      b64data = base64.b64encode(fhandle.getvalue())
    assert mimetype is not None
    self._write_asset_data_delayed(style_name_str, b64data, mimetype)
    delayed_data_str = "<audio controls class=\"" + style_name_str + "\"/>"
    return delayed_data_str.encode('utf-8')

  def _write_asset(self, asset : AssetData) -> bytes | None:
    asset_id = self.get_export_id(asset)
    asset_name = type(asset).__name__
    body_str = "#" + str(asset_id) + " " + asset_name
    if loc := asset.location:
      body_str += ' <' + str(loc) + '>'
    if not self._html_dump:
      self._write_body(body_str)
    else:
      self._write_body("<span class=\"AssetPlaceholder\">" + self.escape(body_str) + "</span>")
    # do not write data if doing textual dump
    if not self._html_dump:
      return None

    # now try to write data
    # check if we have already exported it
    if asset in self._asset_export_cache:
      return self._asset_export_cache[asset]
    # if the asset is already exported (i.e., it is in self._asset_pin_dict), just use the expression there
    if self._asset_pin_dict is not None and asset in self._asset_pin_dict:
      asset_path = self._asset_pin_dict[asset]
      result = self._emit_asset_reference_to_path(asset, asset_path)
      self._asset_export_cache[asset] = result
      return result
    style_name_str = "assetdata_" + str(asset_id)
    delayed_data_bytes = None
    if isinstance(asset, ImageAssetData):
      delayed_data_bytes = self._write_image_asset(asset, style_name_str)
    elif isinstance(asset, AudioAssetData):
      delayed_data_bytes = self._write_audio_asset(asset, style_name_str)
    else:
      # unrecognized case
      return None

    assert delayed_data_bytes is not None
    self._asset_export_cache[asset] = delayed_data_bytes
    return delayed_data_bytes

  def _get_indent_stylename(self, level : int) -> str:
    return 'dump_indent_level_' + str(level)

  def _get_operation_short_name(self, op : Operation) -> str:
    return '[' + self.get_id_str(op) + ' ' + type(op).__name__ + ']\"' + op.name + '"'

  def _get_text_style_str(self, style : TextStyleLiteral) -> str:
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

  def _walk_value(self, value : Value) -> typing.OrderedDict[str, bytes] | None:
    # write the current value to body. if the content is too big (e.g., a table), a stub is written first and the return value is the full content
    # we must be in a <p> element
    assert isinstance(value, Value)
    delayed_content : typing.OrderedDict[str, bytes] | None = None
    if isinstance(value, OpResult):
      self._write_body(self.escape(self._get_operation_short_name(value.parent) + '.' + value.name))
      return delayed_content
    if isinstance(value, BlockArgument):
      block = value.parent
      blockstr = self.get_id_str(block)
      if len(block.name) > 0:
        blockstr += ':"' + block.name + '"'
      self._write_body(self.escape(blockstr + '.' + (value.name if len(value.name) > 0 else '<anon>')))
      return delayed_content
    if isinstance(value, Literal):
      if isinstance(value, BoolLiteral):
        if value.value == True:
          self._write_body('true')
        else:
          self._write_body('false')
        return delayed_content
      elif isinstance(value, FloatLiteral):
        self._write_body(self.escape(str(value.value)))
        return delayed_content
      elif isinstance(value, IntLiteral):
        self._write_body(self.escape(str(value.value)))
        return delayed_content
      elif isinstance(value, StringLiteral):
        self._write_body(self.escape('"' + value.value + '"'))
        return delayed_content
      elif isinstance(value, TextFragmentLiteral):
        self._write_body(self.escape('TextFrag["' + value.content.value + '",' + self._get_text_style_str(value.style) + ']'))
        return delayed_content
      elif isinstance(value, TextStyleLiteral):
        self._write_body(self.escape(self._get_text_style_str(value)))
        return delayed_content
      elif isinstance(value, EnumLiteral):
        ev = value.value
        self._write_body(self.escape(type(ev).__name__ + '.' + ev.name))
        return delayed_content
      else:
        self._write_body(self.escape(str(value)))
        return delayed_content
    if isinstance(value, AssetData):
      if res := self._write_asset(value):
        if delayed_content is None:
          delayed_content = typing.OrderedDict()
        delayed_content[self.get_id_str(value)] = res
      return delayed_content
    if isinstance(value, Operation):
      self._write_body(self.escape(self._get_operation_short_name(value)))
    # unknown value types
    self._write_body(self.escape('[' + self.get_id_str(value) + ' ' + type(value).__name__ + ']'))
    return delayed_content

  def _walk_operation(self, op : Operation, level : int) -> None:
    # [#<id> ClassName]"Name"(operand=...) -> (result)[attr=...]<loc>
    #   <regions>
    assert isinstance(op, Operation)
    isHasBody = op.get_num_regions() > 0
    optail = ''
    # step 1: write the operation header
    if self._html_dump:
      if level == 0:
        # this is the top-level op
        # we just use <p> to wrap it
        self._write_body('<p>')
        optail = '</p>'
      else:
        # this is an internal op
        # create a list item where itself is also a list
        if isHasBody:
          self._write_body('<li><details open><summary>')
          optail = '</summary>'
        else:
          self._write_body('<li>')
          optail = ''
    else:
      # text dump
      if level > 0:
        self._write_body('  '*level)
    # old version that do not use list
    # self._write_body('<p class=\"' + self._get_indent_stylename(level) + '">')
    self._write_body(self.escape(self._get_operation_short_name(op))) # [#<id> ClassName]"Name"

    # operands
    delayed_content = None
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
        # pylint: disable=assignment-from-none
        cur_delayed_content = self._walk_value(operand.get_operand(i))
        if cur_delayed_content is not None:
          if delayed_content is None:
            delayed_content = cur_delayed_content
          else:
            delayed_content.update(cur_delayed_content)
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
    if len(op.attributes) > 0:
      self._write_body(self.escape('['))
      isFirst = True
      for attribute_name in op.attributes:
        if isFirst:
          isFirst = False
        else:
          self._write_body(',')
        attr = op.get_attr(attribute_name)
        self._write_body(self.escape(attribute_name + '=' + str(attr)))
      self._write_body(self.escape(']'))

    # loc
    self._write_body(self.escape('<' + str(op.location) + '>'))
    self._write_body(optail + '\n')

    # delayed content (assets)
    if self._html_dump and delayed_content is not None:
      self._write_body('<ul class="tree">\n')
      for idstr, rep in delayed_content.items():
        self._write_body('<li><details open><summary>' + idstr + "</summary>\n")
        self._output_body.write(rep)
        self._write_body('</li>\n')
      self._write_body('</ul>\n')

    # regions
    if isHasBody:
      body_level = level + 2
      if self._max_indent_level < body_level:
        self._max_indent_level = body_level
      regions_end = ''
      if self._html_dump:
        if level == 0:
          # starting a top-level list
          self._write_body('<ul class="tree">')
          regions_end = '</ul>'
        else:
          # starting a nested list
          self._write_body('<ul>')
          regions_end = '</ul></details>'
      # no need for anything here in text dump

      for r in op.regions:
        # pylint: disable=assignment-from-none
        retval = self._walk_region(r, level+1)
        assert retval is None

      # done traversing all regions
      self._write_body(regions_end)
    # done writing regions
    if level == 0:
      # this is the top-level op
      # just do nothing here
      pass
    else:
      # this is a nested op
      # write the enclosing mark
      self._write_body_html('</li>\n')
    # done!
    return None

  def _walk_region(self, r : Region, level : int) -> None:
    assert isinstance(r, Region)
    # for HTML dump, this should be in a <ul> element
    region_title = self.get_id_str(r) + ' ' + type(r).__name__ + ' "' + r.name + '"'

    #self._write_body('<p class=\"' + self._get_indent_stylename(level) + '">')
    if self._html_dump:
      self._write_body('<li>')
    else:
      self._write_body('  '*level)
    if r.blocks.empty:
      # this is an empty region
      self._write_body(self.escape(region_title))
      self._write_body('\n')
    else:
      # this region have body
      # use nested list
      self._write_body_html('<details open><summary>')
      self._write_body(self.escape(region_title))
      self._write_body_html('</summary><ul>')
      self._write_body('\n')
      for b in r.blocks:
        self._walk_block(b, level+1)
      self._write_body_html('</ul></details>')
    #self._write_body(self.escape(r.name + ':'))
    #self._write_body('</p>\n')

    # finishing current region
    self._write_body_html('</li>')
    return None

  def _walk_block(self, b : Block, level : int) -> None:
    assert isinstance(b, Block)
    # for HTML dump, this should be in a <ul> element
    self._write_body_html('<li>')
    block_end = ''
    block_title_end = ''
    if self._html_dump:
      if b.body.empty:
        # no child for this block; just a normal list item
        block_end = '</li>'
      else:
        # there are children for this block; use nested list
        self._write_body('<details open><summary>')
        block_title_end = '</summary><ul>'
        block_end = '</ul></details></li>'
    else:
      self._write_body('  '*level)

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
    body_header = self.get_id_str(b) + ' ' + body_header + '(' + ','.join(arg_name_list) + ')'
    self._write_body(self.escape(body_header) + block_title_end + '\n')
    for o in b.body:
      self._walk_operation(o, level+1)
    self._write_body(block_end)
    return None

  def start_write_html(self, name : str) -> None:
    title = 'Anonymous dump'
    if len(name) > 0:
      assert isinstance(name, str)
      title = self.escape(name)
    self._output_body.write(b'''<!DOCTYPE html>
<html>
<head>
''')
    self._output_body.write(b'<title>' + title.encode('utf-8') + b'</title>')
    # https://iamkate.com/code/tree-views/
    self._output_body.write(b'''
<style>
.AssetPlaceholder {
  border-width: 1px;
  border-style: solid;
  border-color: black;
  text-align: center;
}
.AssetPathReference {
  border-width: 1px;
  border-style: solid;
  border-color: black;
  text-align: center;
}
.tree{
  --spacing : 1.5rem;
  --radius  : 10px;
}

.tree li{
  display      : block;
  position     : relative;
  padding-left : calc(2 * var(--spacing) - var(--radius) - 2px);
  margin-top: 10px;
}

.tree ul{
  margin-left  : calc(var(--radius) - var(--spacing));
  padding-left : 0;
}

.tree ul li{
  border-left : 2px solid #ddd;
}

.tree ul li:last-child{
  border-color : transparent;
}

.tree ul li::before{
  content      : '';
  display      : block;
  position     : absolute;
  top          : calc(var(--spacing) / -2);
  left         : -2px;
  width        : calc(var(--spacing) + 2px);
  height       : calc(var(--spacing) + 1px);
  border       : solid #ddd;
  border-width : 0 0 2px 2px;
}

.tree summary{
  display : block;
  cursor  : pointer;
}

.tree summary::marker,
.tree summary::-webkit-details-marker{
  display : none;
}

.tree summary:focus{
  outline : none;
}

.tree summary:focus-visible{
  outline : 1px dotted #000;
}

.tree li::after,
.tree summary::before{
  content       : '';
  display       : block;
  position      : absolute;
  top           : calc(var(--spacing) / 2 - var(--radius));
  left          : calc(var(--spacing) - var(--radius) - 1px);
  width         : calc(2 * var(--radius));
  height        : calc(2 * var(--radius));
  border-radius : 50%;
  background    : #ddd;
}

.tree summary::before{
  content     : '+';
  z-index     : 1;
  background  : #696;
  color       : #fff;
  line-height : calc(2 * var(--radius) - 2px);
  text-align  : center;
}

.tree details[open] > summary::before{
  content : '-';
}
</style>
<body>
''')

  def write_html_end(self):
    if len (self._output_asset_delayed) > 0:
      # write the assets to javascript dict
      self._output_body.write(b'''
<script>
var asset_dict = {
''')
      for k, v in self._output_asset_delayed.items():
        self._output_body.write(k.encode('utf-8') + b': "')
        self._output_body.write(v)
        self._output_body.write(b'",\n')
      self._output_body.write(b'''
};
for (asset_name in asset_dict) {
  var elementlist = document.getElementsByClassName(asset_name);
  for (var i = 0; i < elementlist.length; ++i) {
    elementlist.item(i).setAttribute('src', asset_dict[asset_name]);
  }
}
</script>
''')

    self._output_body.write(b'</body></html>\n')

  def write_op_html(self, op : Operation) -> bytes:
    # perform an HTML export with op as the top-level Operation. The return value is the HTML
    self.start_write_html(op.name)
    self._walk_operation(op, 0)
    self.write_html_end()
    return self._output_body.getvalue()

  def write_op(self, op : Operation) -> bytes:
    assert isinstance(op, Operation)
    if self._html_dump:
      return self.write_op_html(op)
    self._walk_operation(op, 0)
    return self._output_body.getvalue()

  def write_region(self, r : Region) -> bytes:
    assert isinstance(r, Region)
    if self._html_dump:
      self.start_write_html(r.name)
      self._write_body_html('<ul class="tree">')
      self._walk_region(r, 0)
      self._write_body_html('</ul>')
      self.write_html_end()
      return self._output_body.getvalue()
    # text dump
    self._walk_region(r, 0)
    return self._output_body.getvalue()

  def write_block(self, b : Block) -> bytes:
    assert isinstance(b, Block)
    if self._html_dump:
      self.start_write_html(b.name)
      self._write_body_html('<ul class="tree">')
      self._walk_block(b, 0)
      self._write_body_html('</ul>')
      self.write_html_end()
      return self._output_body.getvalue()
    # text dump
    self._walk_block(b, 0)
    return self._output_body.getvalue()

def _view_content_helper(dump : bytes, name : str):
  name_portion = 'anon'
  if len(name) > 0:
    sanitized_name = get_sanitized_filename(name)
    if len(sanitized_name) > 0:
      name_portion = sanitized_name
  file = tempfile.NamedTemporaryFile('w+b', suffix='_viewdump.html', prefix='preppipe_' + name_portion + '_', delete=False)
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

# ------------------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------------------

def get_sanitized_filename(s : str) -> str:
  illegal_chars = ['#', '%', '&', '{', '}', '\\', '/', ' ', '?', '*', '>', '<', '$', '!', "'", '"', ':', '@', '+', '`', '|', '=']
  return s.translate({ord(c) : None for c in illegal_chars})