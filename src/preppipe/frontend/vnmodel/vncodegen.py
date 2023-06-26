# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import dataclasses
import enum
import typing
from typing import Any

from preppipe.frontend.vnmodel.vnast import VNASTASMNode, VNASTChangeDefaultDeviceNode, VNASTCharacterTempSayAttrNode, VNASTNodeBase, VNASTSayModeChangeNode, VNASTTempAliasNode

from ...irbase import *
from ...vnmodel_v4 import *
from ..commandsyntaxparser import *
from .vnast import *
from ...renpy.ast import RenPyASMNode

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

  def get_default_state(self):
    curstate = ()
    if curstate in self._default_child_dict:
      curstate = self._default_child_dict[curstate]
    return curstate

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
  @dataclasses.dataclass
  class ParseContext:
    parent : typing.Any | None = None # ParseContext
    alias_dict : dict[str, str] = dataclasses.field(default_factory=dict)
    say_mode : VNASTSayMode = VNASTSayMode.MODE_DEFAULT
    say_mode_specified_sayers : list[tuple[str, VNCharacterSymbol]] = dataclasses.field(default_factory=list)
    temp_say_dict : dict[VNCharacterSymbol, dict[str, VNASTCharacterSayInfoSymbol]] = dataclasses.field(default_factory=dict) # 角色显示名（不是真实名称） --> 发言信息
    last_sayer : tuple[str, VNCharacterSymbol] | None = None
    interleaved_mode_last_sayer : tuple[str, VNCharacterSymbol] | None = None

    # 当前设备
    # 音频
    dev_voice : VNDeviceSymbol | None = None
    dev_bgm : VNDeviceSymbol | None = None
    dev_soundeffect : VNDeviceSymbol | None = None

    # 发言
    dev_say_name : VNDeviceSymbol | None = None
    dev_say_text : VNDeviceSymbol | None = None
    dev_say_sideimage : VNDeviceSymbol | None = None

    # 输入
    dev_menu : VNDeviceSymbol | None = None
    dev_lineinput : VNDeviceSymbol | None = None

    # 背景
    dev_foreground : VNDeviceSymbol | None = None
    dev_background : VNDeviceSymbol | None = None
    dev_overlay : VNDeviceSymbol | None = None

    @staticmethod
    def forkfrom(parent):
      assert isinstance(parent, VNCodeGen.ParseContext)
      return dataclasses.replace(parent, parent=parent, say_mode_specified_sayers=parent.say_mode_specified_sayers.copy(), alias_dict={}, temp_say_dict={})

    def handle_temp_alias(self, n : VNASTTempAliasNode):
      alias = n.alias.get().get_string()
      target = n.target.get().get_string()
      self.alias_dict[alias] = target

    def handle_temp_say_attr(self, n : VNASTCharacterTempSayAttrNode, ch : VNCharacterSymbol):
      # character : OpOperand[StringLiteral] # 角色的真实名字
      #sayinfo : SymbolTableRegion[VNASTCharacterSayInfoSymbol] # 大概只会有一个结点
      if ch in self.temp_say_dict:
        sayinfodict = self.temp_say_dict[ch]
      else:
        sayinfodict = {}
        self.temp_say_dict[ch] = sayinfodict
      for sayinfo in n.sayinfo:
        sayinfodict[sayinfo.name] = sayinfo

    def handle_say_mode_change(self, newmode : VNASTSayMode, specified_sayers : list[tuple[str, VNCharacterSymbol]]):
      # 检查是否符合要求
      match newmode:
        case VNASTSayMode.MODE_DEFAULT:
          assert len(specified_sayers) == 0
        case VNASTSayMode.MODE_LONG_SPEECH:
          assert len(specified_sayers) == 1
        case VNASTSayMode.MODE_INTERLEAVED:
          assert len(specified_sayers) >= 1
        case _:
          raise NotImplementedError()
      for t in specified_sayers:
        assert isinstance(t, tuple)
        assert isinstance(t[0], str) and isinstance(t[1], VNCharacterSymbol)
      self.say_mode = newmode
      self.say_mode_specified_sayers = specified_sayers
      self.interleaved_mode_last_sayer = None

    def get_last_sayer(self) -> tuple[str, VNCharacterSymbol] | None:
      return self.last_sayer

    def update_last_sayer(self, sayname : str, ch : VNCharacterSymbol):
      self.last_sayer = (sayname, ch)
      if self.say_mode == VNASTSayMode.MODE_INTERLEAVED:
        if self.last_sayer in self.say_mode_specified_sayers:
          self.interleaved_mode_last_sayer = self.last_sayer

    def get_narration_sayer(self) -> tuple[str, VNCharacterSymbol] | None:
      # 对于 <内容> 类发言的发言者
      # 只有长发言模式会给定发言者，其他模式都只有旁白
      if self.say_mode == VNASTSayMode.MODE_LONG_SPEECH:
        return self.say_mode_specified_sayers[0]
      return None

    def get_quotedsay_sayer(self) -> tuple[str, VNCharacterSymbol] | None:
      # 对于 "<内容>" 类发言的发言者
      match self.say_mode:
        case VNASTSayMode.MODE_DEFAULT:
          return self.last_sayer
        case VNASTSayMode.MODE_LONG_SPEECH:
          return self.say_mode_specified_sayers[0]
        case VNASTSayMode.MODE_INTERLEAVED:
          # 根据最后发言的角色，选择下一个
          prev_sayer = self.say_mode_specified_sayers[0]
          for cur_sayer in reversed(self.say_mode_specified_sayers):
            if cur_sayer == self.interleaved_mode_last_sayer:
              return prev_sayer
            else:
              prev_sayer = cur_sayer
          return self.say_mode_specified_sayers[0]
      raise NotImplementedError()

  ast : VNAST
  result : VNModel
  resolver : VNModelNameResolver
  _default_ns : tuple[str, ...]
  _func_map : dict[str, dict[tuple[str, ...], VNFunction]] # [名称] -> [命名空间] -> 函数体；现在仅用来在创建函数体时去重
  _all_functions : dict[VNFunction, VNASTFunction]
  _func_prebody_map : dict[VNFunction, Block]
  _func_postbody_map : dict[VNFunction, Block]
  #_char_sprite_map : dict[VNCharacterSymbol, dict[str, VNASTNamespaceSwitchableValueSymbol]]
  _char_say_parent_map : dict[VNASTCharacterSayInfoSymbol, tuple[VNASTCharacterSymbol, VNCharacterSymbol]] # 记录所有发言信息对应的角色记录
  _char_parent_map : dict[VNCharacterSymbol, VNASTCharacterSymbol]
  _char_state_matcher : dict[VNCharacterSymbol, _PartialStateMatcher]
  _global_asm_block : Block # 全局范围的ASM结点放这里；应该都是 VNBackendInstructionGroup 加 ASM 子节点
  _global_parsecontext : ParseContext
  _global_say_index : int
  _global_character_index : int

  def __init__(self, ast : VNAST) -> None:
    self.ast = ast
    self.result = VNModel.create(ast.context, ast.name, ast.location)
    self.resolver = VNModelNameResolver(self.result)
    self._default_ns = ()
    self._func_map = {}
    self._all_functions = {}
    self._func_prebody_map = {}
    self._func_postbody_map = {}
    #self._char_sprite_map = {}
    self._global_asm_block = Block.create('global', self.ast.context)
    self._global_parsecontext = VNCodeGen.ParseContext(parent=None)
    self._global_say_index = 0
    self._global_character_index = 0

    # 初始化根命名空间
    # 主要是把设备信息弄好
    rootns = self.get_or_create_ns(())
    VNDeviceSymbol.create_standard_device_tree(rootns)
    self._global_parsecontext.dev_voice = rootns.get_device(VNStandardDeviceKind.O_VOICE_AUDIO_DNAME.value)
    self._global_parsecontext.dev_bgm = rootns.get_device(VNStandardDeviceKind.O_BGM_AUDIO_DNAME.value)
    self._global_parsecontext.dev_soundeffect = rootns.get_device(VNStandardDeviceKind.O_SE_AUDIO_DNAME.value)
    self._global_parsecontext.dev_say_name = rootns.get_device(VNStandardDeviceKind.O_SAY_NAME_TEXT_DNAME.value + '_adv')
    self._global_parsecontext.dev_say_text = rootns.get_device(VNStandardDeviceKind.O_SAY_TEXT_TEXT_DNAME.value + '_adv')
    self._global_parsecontext.dev_say_sideimage = rootns.get_device(VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY_DNAME.value + '_adv')
    self._global_parsecontext.dev_menu = rootns.get_device(VNStandardDeviceKind.I_MENU_DNAME.value)
    self._global_parsecontext.dev_lineinput = rootns.get_device(VNStandardDeviceKind.I_LINE_INPUT_DNAME.value)
    self._global_parsecontext.dev_foreground = rootns.get_device(VNStandardDeviceKind.O_FOREGROUND_DISPLAY_DNAME.value)
    self._global_parsecontext.dev_background = rootns.get_device(VNStandardDeviceKind.O_BACKGROUND_DISPLAY_DNAME.value)
    self._global_parsecontext.dev_overlay = rootns.get_device(VNStandardDeviceKind.O_OVERLAY_DISPLAY_DNAME.value)

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

  def resolve_character(self, name : str, from_namespace : tuple[str, ...], parsecontext : ParseContext) -> tuple[str, VNCharacterSymbol] | None:
    # 尝试解析对角色名称的引用
    # 返回（1）实际发言名（考虑过别名之后的结果），（2）发言者身份

    # 首先检查名称是不是别名，是的话更新一下名称
    curpc = parsecontext
    while curpc is not None:
      if name in curpc.alias_dict:
        name = curpc.alias_dict[name]
        break
      curpc = curpc.parent
      assert isinstance(curpc, VNCodeGen.ParseContext)
    # 然后解析角色名
    character = self.resolver.unqualified_lookup(name, from_namespace, None)
    if character is None:
      return None
    assert isinstance(character, VNCharacterSymbol)
    return (name, character)

  def resolve_character_sayinfo(self, character : VNCharacterSymbol, sayname : str, parsecontext : ParseContext) -> VNASTCharacterSayInfoSymbol:
    # 根据实际发言名和发言者身份，找到发言所用的外观信息
    #temp_say_dict : dict[VNCharacterSymbol, dict[str, VNASTCharacterSayInfoSymbol]]
    # 如果没有提供发言名（比如是从默认发言者中来的），就从发言者身份中取
    if len(sayname) == 0:
      sayname = character.name

    # 如果当前环境指定了这个角色应该用什么发言信息，就用指定的值
    curpc = parsecontext
    while curpc is not None:
      if character in curpc.temp_say_dict:
        saydict = curpc.temp_say_dict[character]
        if sayname in saydict:
          return saydict[sayname]
      curpc = curpc.parent
      assert isinstance(curpc, VNCodeGen.ParseContext)

    # 如果环境中没有指定，就到上层去找
    astchar = self._char_parent_map[character]
    if info := astchar.sayinfo.get(sayname):
      return info
    # 不应该发生，但实在不行可以用这样
    return astchar.sayinfo.get(astchar.name)

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

  def emit_error(self, code : str, msg : str, loc : Location | None, dest : Block):
    err = ErrorOp.create(error_code=code, context=self.context, error_msg=StringLiteral.get(msg, self.context), loc=loc)
    dest.push_back(err)

  def emit_asm(self, src : VNASTASMNode) -> VNBackendInstructionGroup | None:
    node = VNBackendInstructionGroup.create(self.context, name=src.name, loc=src.location)
    code = src.body.get()
    backend = src.backend.try_get_value()
    if backend is None:
      return None
    match backend.get_string().lower():
      case 'renpy':
        asm = RenPyASMNode.create(context=self.context, asm=code, name=src.name, loc=src.location)
        node.body.push_back(asm)
      case _:
        # 不支持的后端，忽略
        return None
    return node

  def create_unknown_sayer(self, sayname : str, from_namespace : tuple[str,...]) -> VNCharacterSymbol:
    raise NotImplementedError()

  @dataclasses.dataclass
  class _NonlocalCodegenHelper(VNASTVisitor):
    codegen : VNCodeGen
    file : VNASTFileInfo
    parsecontext : VNCodeGen.ParseContext
    warningdest : Block

    # 如果可以处理命令则返回 True, 否则返回 False

    def visit_default_handler(self, node: VNASTNodeBase):
      return False

    def visitVNASTTempAliasNode(self, node: VNASTTempAliasNode):
      self.parsecontext.handle_temp_alias(node)
      return True

    def visitVNASTCharacterTempSayAttrNode(self, node: VNASTCharacterTempSayAttrNode):
      character = node.character.get().get_string()
      t = self.codegen.resolve_character(name=character, from_namespace=self.file.get_namespace_tuple(), parsecontext=self.parsecontext)
      if t is None:
        # 在这里我们只报错并忽略就行了
        self.codegen.emit_error(code='vncodegen-character-nameresolution-failed', msg=character, loc=node.location, dest=self.warningdest)
      else:
        cname, ch = t
        self.parsecontext.handle_temp_say_attr(node, ch)
      return True

    def visitVNASTSayModeChangeNode(self, node: VNASTSayModeChangeNode):
      target_mode : VNASTSayMode = node.target_mode.get().value
      specified_sayers : list[tuple[str, VNCharacterSymbol]] = []
      ns = self.file.get_namespace_tuple()
      for u in node.specified_sayers.operanduses():
        sayerstr = u.value.get_string()
        assert isinstance(sayerstr, str)
        t = self.codegen.resolve_character(name=sayerstr, from_namespace=ns, parsecontext=self.parsecontext)
        if t is None:
          # 在这里我们除了报错之外还需要生成一个默认的发言者，这样不至于令后续所有发言者错位
          self.codegen.emit_error(code='vncodegen-character-nameresolution-failed', msg=sayerstr, loc=node.location, dest=self.warningdest)
          t = (sayerstr, self.codegen.create_unknown_sayer(sayerstr, ns))
        specified_sayers.append(t)
      # 检查指定的发言者数量，如果不对的话作出调整
      is_check_passed = True
      match target_mode:
        case VNASTSayMode.MODE_DEFAULT:
          if len(specified_sayers) > 0:
            raise RuntimeError("Should not happen")
        case VNASTSayMode.MODE_LONG_SPEECH:
          if len(specified_sayers) > 1:
            raise RuntimeError("Should not happen")
          if len(specified_sayers) == 0:
            if prev_sayer := self.parsecontext.get_last_sayer():
              specified_sayers.append(prev_sayer)
            else:
              self.codegen.emit_error(code='vncodegen-saymode-insufficient-sayer', msg='Long speech mode without specified sayer', loc=node.location, dest=self.warningdest)
              is_check_passed = False
        case VNASTSayMode.MODE_INTERLEAVED:
          if len(specified_sayers) == 0:
            self.codegen.emit_error(code='vncodegen-saymode-insufficient-sayer', msg='Interleaving mode without specified sayer', loc=node.location, dest=self.warningdest)
            is_check_passed = False
        case _:
          raise NotImplementedError()
      if is_check_passed:
        self.parsecontext.handle_say_mode_change(target_mode, specified_sayers)
      return True

    def visitVNASTChangeDefaultDeviceNode(self, node: VNASTChangeDefaultDeviceNode):
      raise NotImplementedError("TODO")


  def handle_nonlocal_noasm_node(self, file : VNASTFileInfo, parsecontext : ParseContext, op : VNASTNodeBase, warningdest : Block) -> bool:
    # 有部分结点既可以在文件域出现也可以在函数域出现，并且对它们的处理也是一样的
    # 我们就用这一个函数来同时处理这两种情况
    # 如果结点可以处理就返回 True，结点没有处理（不是所列举的情况）就返回 False
    helper = VNCodeGen._NonlocalCodegenHelper(codegen=self, file=file, parsecontext=parsecontext, warningdest=warningdest)
    return helper.visit(op)

  def handle_filelocal_node(self, file : VNASTFileInfo, parsecontext : ParseContext, op : VNASTNodeBase, warningdest : Block):
    # 当我们在函数体外碰到非 MetadataOp 时，我们使用该函数来处理操作项
    # 报错信息写到 warningdest 中
    if type(op).TRAIT_FUNCTION_CONTEXT_ONLY:
      self.emit_error(code='vncodegen-functionlocal-command-in-globalscope', msg='Node ' + type(op).__name__ + ' cannot be in file scope', loc=op.location, dest=warningdest)
      return
    if isinstance(op, VNASTASMNode):
      if node := self.emit_asm(op):
        self._global_asm_block.push_back(node)
      return
    if self.handle_nonlocal_noasm_node(file, parsecontext, op, warningdest):
      return
    raise RuntimeError("Should not happen")

  @dataclasses.dataclass
  class SceneContext:
    # 记录当前场景的一切状态，包括：
    # * 现在是什么背景、什么状态
    # * 现在有哪些角色在场、各自的状态各是什么
    # * 当前有什么背景音乐

    # 对于在场的角色的搜索、管理，我们需要支持如下使用场景：
    # 1. 最简单的情况：单独的身份、不变的显示名，只有一个立绘
    # 2. 稍复杂的情况：单独的身份，显示名中途变换，一个角色立绘
    # 3. 以后可能出现的情况：角色是众人身份，不止一个形象在场，显示名中途变换
    # 为了支持以上场景并简化调试，我们使用 (身份+编号) 的方式进行跟踪：
    # 1. 每个场上的角色都以 VNCharacterSymbol 作身份、一个全局递增的计数器的值作编号
    # 2. 上场时建立 发言名 + 身份 --> 编号的映射，也可以从编号查到立绘句柄、发言名、身份等
    #    * 这样的话众人身份的角色可以由发言名区分立绘
    # 3. 每次改变角色发言名时，修改场上角色的这种映射关系
    #    * 这样的话角色更改发言名后我们仍然能够找到立绘
    # 由于除了在场上有立绘的角色需要跟踪状态外，
    # 为了确定所有发言角色（包括台下的或者以第一视角的人）的状态以选择正确的侧边头像，
    # 我们也跟踪记录没有立绘的角色的状态
    @dataclasses.dataclass
    class CharacterState:
      index : int
      sayname : str
      identity : VNCharacterSymbol
      state : tuple[str,...]
      sprite_handle : Value | None = None

    character_dict : dict[tuple[str, VNCharacterSymbol], int] = dataclasses.field(default_factory=dict) # (发言名, 身份) --> 状态索引
    character_states : dict[int, CharacterState] = dataclasses.field(default_factory=dict) # 状态索引 --> 状态
    character_sayname_inuse : dict[VNCharacterSymbol, list[str]] = dataclasses.field(default_factory=dict) # 身份 --> 发言名列表; 为了在改变发言名时找到现在记录里用的是什么发言名

    def update_character_sayname(self, ch : VNCharacterSymbol, oldname : str, newname : str):
      saynamelist = self.character_sayname_inuse[ch]
      assert len(saynamelist) == 1
      saynamelist[0] = newname
      index = self.character_dict[(oldname, ch)]
      del self.character_dict[(oldname, ch)]
      self.character_dict[(newname, ch)] = index
      info = self.character_states[index]
      info.sayname = newname

    def get_or_create_character_state(self, sayname : str, character : VNCharacterSymbol, codegen : VNCodeGen) -> VNCodeGen.SceneContext.CharacterState:
      searchtuple = (sayname, character)
      if searchtuple in self.character_dict:
        return self.character_states[self.character_dict[searchtuple]]
      index = codegen._global_character_index
      codegen._global_character_index += 1
      statetuple = codegen._char_state_matcher[character].get_default_state()
      newstate = VNCodeGen.SceneContext.CharacterState(index=index, sayname=sayname, identity=character, state=statetuple, sprite_handle=None)
      self.character_states[index] = newstate
      self.character_dict[searchtuple] = index
      return newstate

    def try_get_character_state(self, sayname : str, character : VNCharacterSymbol) -> VNCodeGen.SceneContext.CharacterState | None:
      searchtuple = (sayname, character)
      if searchtuple in self.character_dict:
        return self.character_states[self.character_dict[searchtuple]]
      return None

    @staticmethod
    def forkfrom(parent):
      assert isinstance(parent, VNCodeGen.SceneContext)
      return VNCodeGen.SceneContext()

  @dataclasses.dataclass
  class _FuntionCodegenHelper(_NonlocalCodegenHelper):
    parsecontext : VNCodeGen.ParseContext
    scenecontext : VNCodeGen.SceneContext
    destfunction : VNFunction
    destblock : Block
    starttime : Value

    # 除了 entry 之外所有的块都在里面
    # entry 块不接受按名查找
    _block_dict : dict[str, Block] = dataclasses.field(default_factory=dict)

    @property
    def context(self):
      return self.codegen.context

    def get_or_create_basic_block(self, labelname : str) -> Block:
      # 获取一个以 labelname 命名的基本块
      # 如果基本块已存在就直接使用存在的基本块
      # 如果不存在就先创建
      # 我们既使用该函数来解析对标签的引用，又用该函数来创建新的内部基本块
      # 这样对标签的引用就可以直接转化为对基本块的引用，不必再转
      # 如果基本块只被引用、没有被初始化，则我们在最后会给它们填错误处理的代码
      if labelname in self._block_dict:
        return self._block_dict[labelname]
      block = self.destfunction.create_block(name=labelname)
      self._block_dict[labelname] = block
      return block

    def visit_default_handler(self, node : VNASTNodeBase):
      raise NotImplementedError()

    def visitVNASTASMNode(self, node: VNASTASMNode):
      if result := self.codegen.emit_asm(node):
        self.destblock.push_back(result)

    # 这些可以直接继承父类的处理
    def visitVNASTTempAliasNode(self, node : VNASTTempAliasNode):
      return super().visitVNASTTempAliasNode(node)
    def visitVNASTSayModeChangeNode(self, node : VNASTSayModeChangeNode):
      return super().visitVNASTSayModeChangeNode(node)
    def visitVNASTChangeDefaultDeviceNode(self, node : VNASTChangeDefaultDeviceNode):
      return super().visitVNASTChangeDefaultDeviceNode(node)

    # 需要小改动的
    def visitVNASTCharacterTempSayAttrNode(self, node : VNASTCharacterTempSayAttrNode):
      character = node.character.get().get_string()
      t = self.codegen.resolve_character(name=character, from_namespace=self.file.get_namespace_tuple(), parsecontext=self.parsecontext)
      if t is None:
        # 在这里我们只报错并忽略就行了
        self.codegen.emit_error(code='vncodegen-character-nameresolution-failed', msg=character, loc=node.location, dest=self.warningdest)
        return

      cname, ch = t
      self.parsecontext.handle_temp_say_attr(node, ch)
      # 除了加到解析状态外，我们还得检查当前场景有没有该角色的状态，有的话把查找信息给改了
      # 现在我们只支持对单个角色
      if ch in self.scenecontext.character_sayname_inuse:
        saynamelist = self.scenecontext.character_sayname_inuse[ch]
        if len(saynamelist) == 1 and len(node.sayinfo) == 1:
          # 当前场上只有一个立绘使用该身份，且输入的结点只设定了一个名称
          oldname = saynamelist[0]
          newname = [info.name for info in node.sayinfo][0]
          if newname != oldname:
            # 开始更新信息
            self.scenecontext.update_character_sayname(ch, oldname, newname)

    # 这些应该不会出现
    def visitVNASTCodegenRegion(self, node : VNASTCodegenRegion):
      raise RuntimeError("Should not happen")
    def visitVNASTFileInfo(self, node : VNASTFileInfo):
      raise RuntimeError("Should not happen")

    # 辅助函数
    def emit_wait(self, loc : Location):
      node = VNWaitInstruction.create(context=self.context, start_time=self.starttime, name='', loc=loc)
      self.starttime = node.get_finish_time()
      self.destblock.push_back(node)

    def get_character_sprite(self, character : VNCharacterSymbol, state : tuple[str,...]) -> Value | None:
      srccharacter = self.codegen._char_parent_map[character]
      sprite = srccharacter.sprites.get(','.join(state))
      return sprite

    def handleCharacterStateChange(self, sayname : str, character : VNCharacterSymbol, statelist : list[str], loc : Location | None = None) -> tuple[str,...]:
      # 改变角色当前的状态，主要任务是当角色在场上时，改变角色的立绘
      # 不过除了场上角色外，没有显示立绘的角色也需要记住状态，这样可以把侧边头像的状态也定下来
      # （我们假设侧边头像与显示立绘所接受的状态一致）
      # 返回一个最终状态的字符串元组
      # (该函数也用于在角色上场前确定上场时的状态)
      charstate = self.scenecontext.get_or_create_character_state(sayname=sayname, character=character, codegen=self.codegen)
      curstate = list(charstate.state)
      matcher = self.codegen._char_state_matcher[character]
      if matchresult := matcher.find_match(curstate, statelist):
        if matchresult == charstate.state:
          # 状态不变的话什么也不做
          return charstate.state
        # 到这就是确实有状态改变
        # 首先，如果当前角色在场上，我们需要改变其立绘
        if charstate.sprite_handle:
          sprite = self.get_character_sprite(character, matchresult)
          # 如果在场上有立绘，那么这里我们应该能够找到立绘
          assert sprite is not None
          handleout = VNModifyInst.create(context=self.context, start_time=self.starttime, handlein=charstate.sprite_handle, content=sprite, loc=loc)
          self.starttime=handleout.get_finish_time()
          charstate.sprite_handle = handleout
          self.destblock.push_back(handleout)
        # 其次，改变记录中的状态
        charstate.state = matchresult
        return matchresult
      else:
        # 状态没有改变，生成一个警告
        self.codegen.emit_error(code='vncodegen-character-state-error', msg='Cannot apply state change ' + str(statelist) + ' to original state ' + str(charstate.state), loc=loc, dest=self.destblock)
        # 返回现在的状态
        return charstate.state

    # 开始处理只在函数体内有意义的结点
    def visitVNASTSayNode(self, node : VNASTSayNode):
      # 首先找到这句话是谁说的
      # 如果发言有附属的状态改变，则把状态改变先处理了
      # 最后再生成发言结点
      if sayer := node.sayer.try_get_value():
        sayname = sayer.get_string()
        sayertuple = self.codegen.resolve_character(name=sayname, from_namespace=self.file.get_namespace_tuple(), parsecontext=self.parsecontext)
        if sayertuple is None:
          # 如果没找到发言者，我们在当前命名空间创建一个新的发言者
          self.codegen.emit_error(code='vncodegen-sayer-implicit-decl', msg=sayname, loc=node.location, dest=self.warningdest)
          ch = self.codegen.create_unknown_sayer(sayname, self.file.get_namespace_tuple())
          sayertuple = (sayname, ch)
      else:
        match node.nodetype.get().value:
          case VNASTSayNodeType.TYPE_FULL:
            raise RuntimeError("Should not happen")
          case VNASTSayNodeType.TYPE_QUOTED:
            sayertuple = self.parsecontext.get_quotedsay_sayer()
          case VNASTSayNodeType.TYPE_NARRATE:
            sayertuple = self.parsecontext.get_narration_sayer()
          case _:
            raise NotImplementedError("TODO")
      # 至此，发言者身份应该已经确定；旁白的话 sayertuple 是 None, 其他情况下 sayertuple 都应该是 (sayname, character)
      # 如果涉及状态改变，则先处理这个
      sayerstatetuple = None
      if node.expression.get_num_operands() > 0:
        if sayertuple is not None:
          statelist : list[str] = [u.value.get_string() for u in node.expression.operanduses()]
          sayname, ch = sayertuple
          sayerstatetuple = self.handleCharacterStateChange(sayname=sayname, character=ch, statelist=statelist, loc=node.location)
        else:
          # 如果发言带状态但是这句话是旁白说的，我们生成一个错误
          # （旁白不应该有表情状态）
          self.codegen.emit_error(code='vncodegen-sayexpr-narrator-expression', msg='Cannot set expression state for the narrator', loc=node.location, dest=self.warningdest)

      # 然后生成发言
      character = None
      sayname = ''
      if sayertuple is not None:
        sayname, character = sayertuple
      sayid = self.codegen._global_say_index
      self.codegen._global_say_index += 1
      saynode = VNSayInstructionGroup.create(context=self.context, start_time=self.starttime, sayer=character, name=str(sayid), loc=node.location)
      # 首先，有配音的话放配音
      if voice := node.embed_voice.try_get_value():
        vnode = VNPutInst.create(context=self.context, start_time=self.starttime, content=voice, device=self.parsecontext.dev_voice, name='voice'+str(sayid), loc=node.location)
        saynode.body.push_back(vnode)
      # 其次，如果有侧边头像，就把侧边头像也加上
      # 我们从角色状态中取头像信息
      if character is not None:
        srcsayer = self.codegen._char_parent_map[character]
        if len(srcsayer.sideimages) > 0:
          if sayerstatetuple is None:
            sayerstatetuple = ()
          statestr = ','.join(sayerstatetuple)
          img = None
          while True:
            if sideimage := srcsayer.sideimages.get(statestr):
              img = sideimage.get_value(self.file.get_namespace_str())
              break
            if len(sayerstatetuple) == 0:
              break
            sayerstatetuple = sayerstatetuple[:-1]
          if img is not None:
            inode = VNPutInst.create(context=self.context, start_time=self.starttime, content=img, device=self.parsecontext.dev_say_sideimage, loc=node.location)
            saynode.body.push_back(inode)
      # 然后把发言者名字和内容放上去
      namestyle = None
      textstyle = None
      if character is not None:
        info = self.codegen.resolve_character_sayinfo(character=character, sayname=sayname, parsecontext=self.parsecontext)
        namestyle = info.namestyle.try_get_value()
        textstyle = info.saytextstyle.try_get_value()
      if len(sayname) > 0:
        namevalue = StringLiteral.get(sayname, self.context)
        if namestyle is not None:
          namevalue = TextFragmentLiteral.get(context=self.context, string=namevalue, styles=namestyle)
        nnode = VNPutInst.create(context=self.context, start_time=self.starttime, content=namevalue, device=self.parsecontext.dev_say_name,loc=node.location)
        saynode.body.push_back(nnode)
      if textstyle is None:
        textvalue = [u.value for u in node.content.operanduses()]
      else:
        textvalue = []
        for u in node.content.operanduses():
          v = u.value
          if isinstance(v, StringLiteral):
            v = TextFragmentLiteral.get(self.context, v, textstyle)
          textvalue.append(v)
      tnode = VNPutInst.create(context=self.context, start_time=self.starttime, content=textvalue, device=self.parsecontext.dev_say_text, loc=node.location)
      saynode.body.push_back(tnode)
      saynode.group_finish_time.set_operand(0, tnode.get_finish_time())
      self.starttime = saynode.get_finish_time()
      self.destblock.push_back(saynode)
      self.emit_wait(node.location)
      # 结束

    def visitVNASTCharacterStateChangeNode(self, node : VNASTCharacterStateChangeNode):
      sayname = node.character.get().get_string()
      statelist : list[str] = [u.value.get_string() for u in node.deststate.operanduses()]
      if sayertuple:= self.codegen.resolve_character(name=sayname, from_namespace=self.file.get_namespace_tuple(), parsecontext=self.parsecontext):
        cname, ch = sayertuple
        self.handleCharacterStateChange(sayname, ch, statelist, node.location)
      else:
        # 生成一个错误
        self.codegen.emit_error(code='vncodegen-character-notfound', msg=sayname, loc=node.location, dest=self.warningdest)

    def visitVNASTCharacterEntryNode(self, node : VNASTCharacterEntryNode):
      sayname = node.character.get().get_string()
      t = self.codegen.resolve_character(name=sayname, from_namespace=self.file.get_namespace_tuple(), parsecontext=self.parsecontext)
      if t is None:
        # 生成错误然后结束
        self.codegen.emit_error(code='vncodegen-character-notfound', msg=sayname, loc=node.location, dest=self.warningdest)
        return
      # 角色存在的话先设置角色状态
      states = [u.value.get_string() for u in node.states.operanduses()]
      cname, ch = t
      finalstate = self.handleCharacterStateChange(sayname=sayname, character=ch, statelist=states, loc=node.location)
      # 然后如果有立绘的话，让角色立绘上场
      info = self.scenecontext.try_get_character_state(sayname, ch)
      assert info is not None and info.sprite_handle is None
      if sprite := self.get_character_sprite(ch, finalstate):
        assert isinstance(sprite.valuetype, ImageType)
        cnode = VNCreateInst.create(context=self.context, start_time=self.starttime, content=sprite, ty=VNHandleType.get(sprite.valuetype), device=self.parsecontext.dev_foreground, loc=node.location)
        self.starttime = cnode.get_finish_time()
        info.sprite_handle = cnode
        self.destblock.push_back(cnode)
      # 完成

    def visitVNASTCharacterExitNode(self, node : VNASTCharacterExitNode):
      sayname = node.character.get().get_string()
      t = self.codegen.resolve_character(name=sayname, from_namespace=self.file.get_namespace_tuple(), parsecontext=self.parsecontext)
      if t is None:
        # 生成错误然后结束
        self.codegen.emit_error(code='vncodegen-character-notfound', msg=sayname, loc=node.location, dest=self.warningdest)
        return
      # 如果有角色的话就看看角色是否有在台上的立绘，有的话就撤下
      cname, ch = t
      if info := self.scenecontext.try_get_character_state(sayname, ch):
        if info.sprite_handle:
          rm = VNRemoveInst.create(self.context, start_time=self.starttime, handlein=info.sprite_handle, loc=node.location)
          self.starttime = rm.get_finish_time()
          self.destblock.push_back(rm)
          info.sprite_handle = None


    def visitVNASTAssetReference(self, node : VNASTAssetReference):
      return self.visit_default_handler(node)
    def visitVNASTSceneSwitchNode(self, node : VNASTSceneSwitchNode):
      return self.visit_default_handler(node)
    def visitVNASTConditionalExecutionNode(self, node : VNASTConditionalExecutionNode):
      return self.visit_default_handler(node)
    def visitVNASTMenuNode(self, node : VNASTMenuNode):
      return self.visit_default_handler(node)
    def visitVNASTBreakNode(self, node : VNASTBreakNode):
      return self.visit_default_handler(node)
    def visitVNASTLabelNode(self, node : VNASTLabelNode):
      return self.visit_default_handler(node)
    def visitVNASTJumpNode(self, node : VNASTJumpNode):
      return self.visit_default_handler(node)
    def visitVNASTCallNode(self, node : VNASTCallNode):
      return self.visit_default_handler(node)





  def run_codegen_for_block(self, srcfile : VNASTFileInfo, functioncontext : ParseContext, destfunction : VNFunction, baseparsecontext : VNCodeGen.ParseContext, basescenecontext : VNCodeGen.SceneContext, srcregion : VNASTCodegenRegion, dest : Block, deststarttime : Value, convergeblock : Block | None):
    # 如果
    parsecontext = VNCodeGen.ParseContext.forkfrom(baseparsecontext)
    scenecontext = VNCodeGen.SceneContext.forkfrom(basescenecontext)
    assert isinstance(deststarttime, VNTimeOrderType)
    helper = VNCodeGen._FuntionCodegenHelper(codegen=self, file=srcfile, parsecontext=parsecontext, warningdest=dest, destblock=dest, scenecontext=scenecontext, destfunction=destfunction, starttime=deststarttime)
    for op in srcregion.body.body:
      if isinstance(op, VNASTNodeBase):
        helper.visit(op)
      elif isinstance(op, MetadataOp):
        dest.push_back(op.clone())
        continue
      else:
        # 既不是 VNASTNodeBase 又不是 MetadataOp
        raise NotImplementedError()

    # 现在所有的内容都处理完了，开始收尾
    # 如果目标块有给定的状态，那么将当前场景状态与目标状态比对，场景不一样的话换场景，场景一样的话比较角色
    # 如果没有目标块，则这是函数本体结束，清除场上所有内容并生成一个返回指令
    raise NotImplementedError()

  def generate_function_body(self, srcfile : VNASTFileInfo, filecontext : ParseContext, src : VNASTFunction, dest : VNFunction):
    # 首先处理在函数体外的内容
    if len(src.prebody_md.body) > 0:
      prebody = self.get_function_prebody(dest)
      for op in src.prebody_md.body:
        if isinstance(op, MetadataOp):
          prebody.push_back(op.clone())
        else:
          assert isinstance(op, VNASTNodeBase)
          self.handle_filelocal_node(file=srcfile, parsecontext=filecontext, op=op, warningdest=prebody)
    # 然后处理函数体
    functioncontext = VNCodeGen.ParseContext.forkfrom(filecontext)



    # 在解析子 VNASTCodegenRegion 时，我们会复制(fork)解析状态和情景状态
    #



    # 需要在控制流保持的信息：
    #  当前场景（有句柄）
    #  当前角色、角色状态，（字符串的状态以及角色立绘句柄）
    #  循环入口
    raise NotImplementedError()

  def populate_assets(self):
    # 把角色、场景等信息写到输出里
    raise NotImplementedError()

  def run_pipeline(self):
    self.populate_assets()
    self.collect_functions()

  @staticmethod
  def run(ast : VNAST) -> VNModel:
    m = VNCodeGen(ast)
    m.run_pipeline()
    return m.result


