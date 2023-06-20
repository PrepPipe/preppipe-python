# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import dataclasses
import enum
import typing
from typing import Any

from ...irbase import *
from ...vnmodel_v4 import *
from ..commandsyntaxparser import *
from .vnast import *

class _PartialStateMatcher:
  # 当切换角色、场景状态时，状态字符串很可能不全
  # 这个类被用于将这些状态字符串补全为预先设定的完整的状态
  # 比如角色可以有如下状态：
  #   * 站姿
  #       - 正常
  #       - 开心
  #   * 侧身
  #       - 正常
  #       - 愤怒
  # 那么完整状态有 (站姿, 正常), (站姿, 开心), (侧身, 正常), (侧身, 愤怒)
  # 并且有以下切换：(原状态) + (给出的状态) --> (完整的结果状态)
  # (站姿, 正常) + (开心) --> (站姿, 开心) (仅替换最后的表情)
  # (站姿, 正常) + (正常) --> (站姿, 正常) (正确识别无变化的情况)
  # (站姿, 正常) + (侧身) --> (侧身, 正常) (默认第一项为默认状态)
  # (站姿, 开心) + (侧身) --> (侧身, 正常)
  # (站姿, 正常) + (侧身, 愤怒) --> (侧身, 愤怒)
  # (站姿, 正常) + (侧身，开心) --> 报错
  # (站姿, 开心) + (愤怒) --> 报错

  # 以后如果需要加别的、不是基于树的状态（比如戴眼镜、不戴眼镜这样二分的）可以用额外的机制

  _parent_tree : dict[str, list[tuple[str,...]]] # 对每个状态而言，它们有哪些合理的前置状态
  _default_child_dict : dict[tuple[str,...], tuple[str,...]] # 如果当前状态不是子状态，这里存着它们接下来的默认状态

  def __init__(self) -> None:
    self._parent_tree = {}
    self._default_child_dict = {}

  def check_is_prefix(self, state : list[str], prefix : tuple[str, ...]) -> bool:
    if len(prefix) > len(state):
      return False
    for i in range(0, len(prefix)):
      if prefix[i] != state[i]:
        return False
    return True

  def check_is_same(self, state : list[str], prefix : tuple[str, ...]) -> bool:
    return len(state) == len(prefix) and self.check_is_prefix(state, prefix)

  def add_valid_state(self, state : tuple[str, ...]):
    for i in range(0, len(state)):
      # 首先添加子串
      substate = state[i]
      parent_prefix= state[:i]
      substate_parent = None
      if substate in self._parent_tree:
        substate_parent = self._parent_tree[substate]
      else:
        substate_parent = []
        self._parent_tree[substate] = substate_parent
      if parent_prefix not in substate_parent:
        substate_parent.append(parent_prefix)
      # 然后把默认子结点加上
      if parent_prefix not in self._default_child_dict:
        self._default_child_dict[parent_prefix] = state[i:]

  def finish_init(self):
    # 把 _parent_tree 中的所有项排序，长的在前短的在后
    for l in self._parent_tree.values():
      l.sort(key=lambda t : len(t), reverse=True)

  def find_match(self, existing_states : list[str], attached_states : list[str]) -> tuple[str] | None:
    pinned_length = -1
    cur_state = existing_states.copy()
    for newsubstate in attached_states:
      if newsubstate not in self._parent_tree:
        # 这是个没见过的状态，有可能是字打错了或是其他原因
        return None
      parent_list = self._parent_tree[newsubstate]
      is_prefix_found = False
      for candidate in parent_list:
        # 忽略长度小于确定项的备选前缀
        if len(candidate) < pinned_length:
          continue
        if self.check_is_prefix(cur_state, candidate):
          pinned_length = len(candidate)
          is_prefix_found = True
          break
      if not is_prefix_found:
        # 找不到合适的前缀
        return None
      # 重新检查 pinned_length 之后的所有项，如果前置条件已经不匹配了就去掉
      oldstates = cur_state[pinned_length:]
      cur_state = cur_state[:pinned_length]
      cur_state.append(newsubstate)
      pinned_length += 1
      for oldsubstate in oldstates:
        for candidate in self._parent_tree[oldsubstate]:
          if self.check_is_same(cur_state, candidate):
            cur_state.append(oldsubstate)
            break
      # 将当前状态补足到一个完整状态
      cur_state_tuple = tuple(cur_state)
      if cur_state_tuple in self._default_child_dict:
        substates = self._default_child_dict[cur_state_tuple]
        cur_state.append(*substates)
    return tuple(cur_state)

def _test_main_statematcher():
  matcher = _PartialStateMatcher()
  matcher.add_valid_state(('站姿', '正常'))
  matcher.add_valid_state(('站姿', '开心'))
  matcher.add_valid_state(('侧身', '正常'))
  matcher.add_valid_state(('侧身', '愤怒'))
  matcher.finish_init()
  curstate = ['站姿', '正常']
  curstate2 = ['站姿', '开心']
  assert (res := matcher.find_match(curstate, ['开心'])) == ('站姿', '开心')
  assert (res := matcher.find_match(curstate, ['正常'])) == ('站姿', '正常')
  assert (res := matcher.find_match(curstate, ['侧身'])) == ('侧身', '正常')
  assert (res := matcher.find_match(curstate2, ['侧身'])) == ('侧身', '正常')
  assert (res := matcher.find_match(curstate, ['侧身','愤怒'])) == ('侧身','愤怒')
  assert (res := matcher.find_match(curstate, ['侧身','开心'])) is None
  assert (res := matcher.find_match(curstate2, ['愤怒'])) is None

if __name__ == "__main__":
  _test_main_statematcher()

class VNCodeGen:
  ast : VNAST
  result : VNModel
  resolver : VNModelNameResolver
  _default_ns : tuple[str, ...]
  _func_map : dict[str, dict[tuple[str, ...], VNFunction]] # [名称] -> [命名空间] -> 函数体；现在仅用来在创建函数体时去重
  _all_functions : dict[VNFunction, VNASTFunction]
  _func_prebody_map : dict[VNFunction, Block]
  _func_postbody_map : dict[VNFunction, Block]
  _char_sprite_map : dict[VNCharacterSymbol, dict[str, VNASTNamespaceSwitchableValueSymbol]]

  def __init__(self, ast : VNAST) -> None:
    self.ast = ast
    self.result = VNModel.create(ast.context, ast.name, ast.location)
    self.resolver = VNModelNameResolver(self.result)
    self._default_ns = ()
    self._func_map = {}
    self._all_functions = {}
    self._func_prebody_map = {}
    self._func_postbody_map = {}
    self._char_sprite_map = {}

  @property
  def context(self):
    return self.ast.context

  def add_alias(self, alias_namespace : tuple[str, ...], alias : str, target : str, target_namespace : tuple[str, ...] | None = None, loc : Location | None = None) -> tuple[str, str] | None:
    # 尝试加入一个别名
    # 如果出错则返回一个 <code, msg> 的错误信息
    # 如果没出错就返回 None
    node = self.resolver.get_namespace_node(alias_namespace)
    if node is None:
      raise RuntimeError('should not happen')
    assert isinstance(node, VNNamespace)
    if existing := node.aliases.get(alias):
      # 已经有一个同样名称的别名了
      code = 'vncodegen-alias-already-exist'
      msg = '"' + alias + '"@' + VNNamespace.stringize_namespace_path(alias_namespace) + ' --> "' + existing.target_name.get().get_string() + '"@' + existing.target_namespace.get().get_string()
      msg += '; cannot add alias to "' + target + '"'
      if target_namespace is not None:
        msg += '@' + VNNamespace.stringize_namespace_path(target_namespace)
      return (code, msg)
    targetns = VNNamespace.stringize_namespace_path(alias_namespace  if target_namespace is None else target_namespace)
    symb = VNAliasSymbol.create(self.context, name=alias, target_name=target, target_namespace=targetns, loc=loc)
    node.add_alias(symb)
    return None

  def resolve_function(self, name : str, from_namespace : tuple[str, ...]) -> VNFunction | None:
    if func := self.resolver.unqualified_lookup(name, from_namespace, None):
      assert isinstance(func, VNFunction)
      return func
    return None

  def resolve_character(self, name : str, from_namespace : tuple[str, ...]) -> VNCharacterSymbol | None:
    if character := self.resolver.unqualified_lookup(name, from_namespace, None):
      assert isinstance(character, VNCharacterSymbol)
      return character
    return None

  def get_or_create_ns(self, namespace : tuple[str, ...]) -> VNNamespace:
    if node := self.resolver.get_namespace_node(namespace):
      assert isinstance(node, VNNamespace)
      return node
    node = VNNamespace.create(VNNamespace.stringize_namespace_path(namespace), self.context.null_location)
    self.result.add_namespace(node)
    return node

  def get_function_prebody(self, func : VNFunction) -> Block:
    if func in self._func_prebody_map:
      return self._func_prebody_map[func]
    b = Block.create('prebody', self.context)
    func.set_lost_block_prebody(b)
    self._func_prebody_map[func] = b
    return b

  def get_function_postbody(self, func : VNFunction) -> Block:
    if func in self._func_postbody_map:
      return self._func_postbody_map[func]
    b = Block.create('postbody', self.context)
    func.set_lost_block_postbody(b)
    self._func_postbody_map[func] = b
    return b

  def collect_functions(self):
    # 找到所有的函数，创建对应的命名空间，并把函数加到记录中
    # 做这步的目的是为了提前创建好所有 VNFunction, 这样其他函数可以直接生成对其的调用
    for file in self.ast.files.body:
      assert isinstance(file, VNASTFileInfo)
      if len(file.functions.body) == 0:
        continue
      namespace = self._default_ns
      if ns := file.namespace.try_get_value():
        namespace = VNNamespace.expand_namespace_str(ns.get_string())
      nsnode = self.get_or_create_ns(namespace)
      for func in file.functions.body:
        assert isinstance(func, VNASTFunction)
        if func.name not in self._func_map:
          self._func_map[func.name] = {}
        funcdict = self._func_map[func.name]
        if namespace in funcdict:
          # 我们已经有相同的函数了
          # 给现有的函数体开头加个错误提示
          existingfunc = funcdict[namespace]
          postbody = self.get_function_postbody(existingfunc)
          msg = 'Duplicated definition ignored: ' + file.name + ': ' + func.name
          err = ErrorOp.create(error_code='vncodegen-name-clash', context=self.context, error_msg=StringLiteral.get(msg, self.context), loc=func.location)
          postbody.push_back(err)
          continue
        function = VNFunction.create(self.context, func.name, func.location)
        nsnode.add_function(function)
        self._all_functions[function] = func
        funcdict[namespace] = func

  def generate_function_body(self, src : VNASTFunction, dest : VNFunction):
    # 需要在控制流保持的信息：
    #  当前场景（有句柄）
    #  当前角色、角色状态，（字符串的状态以及角色立绘句柄）
    #  循环入口
    raise NotImplementedError()

  def init_rootns(self):
    # 初始化根命名空间
    # 主要是把设备信息弄好
    rootns = self.get_or_create_ns(())
    VNDeviceSymbol.create_standard_device_tree(rootns)

  def populate_assets(self):
    # 把角色、场景等信息写到输出里
    raise NotImplementedError()

  def run_pipeline(self):
    self.init_rootns()
    self.populate_assets()
    self.collect_functions()

  @staticmethod
  def run(ast : VNAST) -> VNModel:
    m = VNCodeGen(ast)
    m.run_pipeline()
    return m.result


