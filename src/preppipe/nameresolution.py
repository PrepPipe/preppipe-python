# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0


from __future__ import annotations

import typing
import enum
import dataclasses
import abc
from .exceptions import *

# ------------------------------------------------------------------------------
# 类似C++的命名解析在语涵编译器中至少有两处应用：
# 1.  命令名的解析（支持重载）
# 2.  视觉小说前端中对资源名的解析（不支持重载）
# 因此我们将这部分逻辑抽象出来，方便复用
# 我们支持C++命名解析的嵌套、别名
# 这里我们只提供解析，重载支持与否可以在被包裹的数据(T)中实现
# 当前的实现只支持对全局内容的名称搜索，如果是像查找局部变量等，则需要自行实现基于 scope 的栈
#
# 实现方式：
# 我们首先构建一棵命名空间的树，所有结点都是一个命名空间，内部包含该命名空间中定义的所有内容与别名
# 我们假设任意时刻都有一个“当前命名空间”，所有的 start_namespace_path 参数都应该是这个命名空间
# 当出现类似 using AAA = DDD::YYY 的声明时，我们先完成一次对 DDD::YYY 的解析，然后在当前命名空间下创建别名 AAA
# 当出现类似 using DDD::YYY 的声明时，解析完 DDD::YYY 后我们在当前命名空间下创建别名 YYY
# （以上两种在C++中叫 using declaration）
# 但出现类似 using namespace DDD::EEE 这样的命令时（C++里叫 using directive），这不是对命名空间的操作，前端应该记住这个声明
# 所有的 using_namespace_paths 都是一串代表了 using namespace DDD::EEE 这样的路径
# 在我们的编译器中，这样的 using directive 只能把命名空间并入全局命名空间(global namespace)，不能并入其他命名空间
# 因此，我们只在从当前命名空间开始查找完、没找到匹配项之后，再去搜索 using_namespace_paths 中的命名空间
# （呃。。我们早晚有一天要把这个功能加上，一个命名空间可以用类似 using namespace DDD 的方式把命名空间 DDD 中的内容并入当前（非全局）命名空间）
# ------------------------------------------------------------------------------

T = typing.TypeVar('T') # typevar for the node subclass

class NameResolver(typing.Generic[T]):

  # derived class may override the following methods (get root node and get node at specific path)
  def get_root_node(self) -> NamespaceNodeInterface[T]:
    raise PPNotImplementedError()

  def get_namespace_node(self, path : typing.Tuple[str]) -> NamespaceNodeInterface[T] | None:
    current_node = self.get_root_node()
    for step in path:
      assert isinstance(step, str)
      current_node = self._lookup_name(current_node, step)
      if not isinstance(current_node, NamespaceNodeInterface):
        return None
    return current_node

  # ----------------------------------------------------------------------------

  def _lookup_name(self, node : NamespaceNodeInterface[T], name : str) -> NamespaceNodeInterface[T] | T | None:
    # 解析该名
    # TODO 目前还不支持 node 的 get_using_namespace_paths()
    result = node.lookup_name(name)
    if isinstance(result, NamespaceNodeInterface.AliasEntry):
      tnode = self.get_namespace_node(result.ns_path)
      if result.name is None:
        return tnode
      return self._lookup_name(tnode, result.name)
    return result

  def unqualified_lookup(self, name : str, start_namespace_path : typing.Tuple[str], using_namespace_paths : typing.Iterable[typing.Tuple[str]] | None) -> NamespaceNodeInterface[T] | T | None:
    # 对类似 <name> 名字的查找
    # 从 start_namespace_path 开始查找，当前层没找到就往上一层查找，找到全局命名空间还是没有的话再在 using_namespace_paths 中一个个找
    def search_from_node(current_ns : NamespaceNodeInterface[T]) -> T | None:
      while current_ns is not None:
        result = self._lookup_name(current_ns, name)
        if result is not None:
          return result
        current_ns = current_ns.get_namespace_parent_node()
      return None

    current_ns = self.get_namespace_node(start_namespace_path)
    if initial_search_result := search_from_node(current_ns):
      return initial_search_result

    if using_namespace_paths is not None:
      for alternative in using_namespace_paths:
        current_ns = self.get_namespace_node(alternative)
        if result := self._lookup_name(current_ns, name):
          return result
    return None

  def fully_qualified_lookup(self, name : str, namespace_path : typing.Tuple[str]) -> NamespaceNodeInterface[T] | T | None:
    # 对类似 ::<namespace_path>::<name> 名字的查找
    node = self.get_namespace_node(namespace_path)
    if node is None:
      return None
    return self._lookup_name(node, name)

  def partially_qualified_lookup(self, name : str, prefix : typing.Tuple[str], start_namespace_path : typing.Tuple[str], using_namespace_paths : typing.Iterable[typing.Tuple[str]]) -> NamespaceNodeInterface[T] | T | None:
    # 对类似 <prefix>::<name> 名字的查找
    # 先递归查找 prefix 所在的命名空间，找到之后再在当前的命名空间中查找该名称
    assert prefix is not None and len(prefix) >= 1
    target_namespace = None
    if len(prefix) > 1:
      target_namespace = self.partially_qualified_lookup(prefix[-1], prefix[:-1], start_namespace_path, using_namespace_paths)
    else:
      target_namespace = self.unqualified_lookup(prefix[0], start_namespace_path, using_namespace_paths)
    if not isinstance(target_namespace, NamespaceNodeInterface):
      return None
    return self._lookup_name(target_namespace, name)

class NamespaceNodeInterface(typing.Generic[T], abc.ABC):
  @dataclasses.dataclass
  class AliasEntry:
    ns_path: tuple[str]
    name : str = None # None if referring to the node

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)

  @abc.abstractmethod
  def get_namespace_parent_node(self) -> NamespaceNodeInterface[T] | None:
    raise PPNotImplementedError()

  @abc.abstractmethod
  def get_namespace_path(self) -> tuple[str]:
    raise PPNotImplementedError()

  def get_using_namespace_paths(self) -> typing.Iterable[tuple[str]] | None:
    # 除了在该命名空间搜索之外，还应该在哪里搜索
    # (比如 using namespace DDD; --> 在此返回[('DDD')])
    return None

  @abc.abstractmethod
  def lookup_name(self, name : str) -> NamespaceNodeInterface[T] | T | AliasEntry | None:
    raise PPNotImplementedError()

class NamespaceNode(typing.Generic[T], NamespaceNodeInterface[T]):
  # 某个在该命名空间下的名称代表什么
  class _NameResolutionDataEntryKind(enum.Enum):
    CanonicalEntry = 0 # 代表一个数据项，值是数据项记录
    EntryAlias = 1 # 代表数据项的一个别名，值是该数据项的规范名(canonical name)
    CanonicalChild = 2 # 代表一个子结点，值是子结点的引用
    ChildAlias = 3 # 代表子结点的一个别名，值是子结点的规范名
    RemoteEntryAlias = 4 # 代表一个其他命名空间下的数据项，值是一个完整的命名空间路径+规范名
    RemoteChildAlias = 5 # 代表一个其他命名空间，值是完整的命名空间路径

  _namespace_path : typing.Tuple[str]
  _data_dict : typing.Dict[str, typing.Tuple[_NameResolutionDataEntryKind, typing.Any]] # 规范名(canonical name) -> 数据(data)、子结点，或者别名到其他东西
  _tree : NameResolver[T]
  _parent : NamespaceNode[T]

  @property
  def namespace_tree(self) -> NameResolver[T]:
    return self._tree

  def get_namespace_parent_node(self):
    return self._parent

  def get_namespace_path(self) -> tuple[str]:
    return self._namespace_path

  def lookup_name(self, name : str) -> NamespaceNode[T] | T | NamespaceNodeInterface.AliasEntry | None:
    assert isinstance(name, str)
    if name not in self._data_dict:
      return None
    kind, data = self._data_dict[name]
    match kind:
      case NamespaceNode._NameResolutionDataEntryKind.CanonicalEntry:
        return data # T
      case NamespaceNode._NameResolutionDataEntryKind.EntryAlias:
        target_kind, target_data = self._data_dict[data]
        assert target_kind == NamespaceNode._NameResolutionDataEntryKind.CanonicalEntry
        return target_data # T
      case NamespaceNode._NameResolutionDataEntryKind.CanonicalChild:
        return data # NamespaceNode[T]
      case NamespaceNode._NameResolutionDataEntryKind.ChildAlias:
        target_kind, target_data = self._data_dict[data]
        assert target_kind == NamespaceNode._NameResolutionDataEntryKind.CanonicalChild
        return target_data # NamespaceNode[T]
      case NamespaceNode._NameResolutionDataEntryKind.RemoteEntryAlias:
        nspath, cname = data
        return NamespaceNodeInterface.AliasEntry(ns_path=nspath, name=cname)
        # return self.namespace_tree.get_namespace_node(nspath).lookup_name(cname)
      case NamespaceNode._NameResolutionDataEntryKind.RemoteChildAlias:
        return NamespaceNodeInterface.AliasEntry(ns_path=data)
        # return self.namespace_tree.get_namespace_node(data)
      case _:
        raise PPNotImplementedError('Unexpected data entry kind')

  def unqualified_lookup(self, name : str, using_namespace_paths : typing.Iterable[typing.Tuple[str]]) -> NamespaceNode[T] | T | None:
    return self.namespace_tree.unqualified_lookup(name, self.get_namespace_path(), using_namespace_paths)

  def __init__(self,tree : NameResolver[T],  parent : NamespaceNode[T], cname : str | None) -> None:
    super().__init__()
    self._parent = parent
    self._tree = tree
    self._namespace_path = ()
    self._data_dict = {}
    if cname is None:
      assert parent is None
    else:
      assert parent is not None and isinstance(cname, str)
      self._namespace_path = (*parent.get_namespace_path(), cname)
      parent.add_child(cname, self)

  def add_data_entry(self, cname : str, data : T) -> None:
    assert data is not None
    if cname in self._data_dict:
      raise PPInternalError('given cname "' + cname + '" is already used:' + str(self._data_dict[cname]))
    self._data_dict[cname] = (NamespaceNode._NameResolutionDataEntryKind.CanonicalEntry, data)

  def add_child(self, cname : str, child : NamespaceNode[T]) -> None:
    assert child is not None
    if cname in self._data_dict:
      raise PPInternalError('given cname "' + cname + '" is already used:' + str(self._data_dict[cname]))
    self._data_dict[cname] = (NamespaceNode._NameResolutionDataEntryKind.CanonicalChild, child)

  def add_local_alias(self, name : str, alias : str) -> None:
    assert isinstance(name, str)
    assert isinstance(alias, str)
    if name == alias:
      return
    if alias in self._data_dict:
      raise PPInternalError('given alias "' + alias + '" is already used:' + str(self._data_dict[alias]))
    resolved_name = name
    while True:
      if resolved_name not in self._data_dict:
        raise PPInternalError('Cannot resolve name "' + name + '"')
      kind, data = self._data_dict[resolved_name]
      match kind:
        case NamespaceNode._NameResolutionDataEntryKind.CanonicalEntry:
          self._data_dict[alias] = (NamespaceNode._NameResolutionDataEntryKind.EntryAlias, resolved_name)
          return
        case NamespaceNode._NameResolutionDataEntryKind.EntryAlias:
          resolved_name = data
        case NamespaceNode._NameResolutionDataEntryKind.CanonicalChild:
          self._data_dict[alias] = (NamespaceNode._NameResolutionDataEntryKind.ChildAlias, resolved_name)
          return
        case NamespaceNode._NameResolutionDataEntryKind.ChildAlias:
          resolved_name = data
        case NamespaceNode._NameResolutionDataEntryKind.RemoteChildAlias:
          self._data_dict[alias] = (kind, data)
          return
        case NamespaceNode._NameResolutionDataEntryKind.RemoteEntryAlias:
          self._data_dict[alias] = (kind, data)
          return
        case _:
          raise PPNotImplementedError('Unhandled data entry kind')

  def _add_remote_alias_check(self, remote_path : typing.Tuple[str], alias : str) -> None:
    assert remote_path != self.get_namespace_path()
    assert isinstance(remote_path, tuple)
    for step in remote_path:
      assert isinstance(step, str)
    if alias in self._data_dict:
      raise PPInternalError('given alias "' + alias + '" is already used:' + str(self._data_dict[alias]))

  def add_remote_node_alias(self, remote_path : typing.Tuple[str], alias : str) -> None:
    self._add_remote_alias_check(remote_path, alias)
    self._data_dict[alias] = (NamespaceNode._NameResolutionDataEntryKind.RemoteChildAlias, remote_path)

  def add_remote_entry_alias(self, remote_path : typing.Tuple[str], remote_name : str, alias : str) -> None:
    self._add_remote_alias_check(remote_path, alias)
    assert isinstance(remote_name, str)
    self._data_dict[alias] = (NamespaceNode._NameResolutionDataEntryKind.RemoteEntryAlias, (remote_path, remote_name))

