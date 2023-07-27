# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import dataclasses
import enum
import typing
from typing import Any

from preppipe.frontend.vnmodel.vnast import VNASTASMNode, VNASTChangeDefaultDeviceNode, VNASTCharacterTempSayAttrNode, VNASTNodeBase, VNASTSayModeChangeNode, VNASTTempAliasNode

from ...irbase import *
from ...vnmodel import *
from ...imageexpr import *
from ..commandsyntaxparser import *
from .vnast import *
from .vnutil import *
from ...renpy.ast import RenPyASMNode
from ...language import TranslationDomain
from ...exceptions import *

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
    issuccess, resultlist = self._find_match_impl(existing_states, attached_states)
    if issuccess:
      return tuple(resultlist)
    return None

  def find_match_besteffort(self, existing_states : list[str], attached_states : list[str]) -> tuple[bool, tuple[str,...]]:
    is_full_match, result = self._find_match_impl(existing_states, attached_states)
    return (is_full_match, tuple(result))

  def _find_match_impl(self, existing_states : list[str], attached_states : list[str]) -> tuple[bool, list[str]]:
    # 元组第一项是 attached_states 中的状态匹配是否全部成功，全部成功是 True, 中途有失败、结果是折中的就返回 False
    # 元组第二项是当前匹配的最好的状态
    pinned_length = -1
    cur_state = existing_states.copy()
    for newsubstate in attached_states:
      if newsubstate not in self._parent_tree:
        # 这是个没见过的状态，有可能是字打错了或是其他原因
        return (False, cur_state)
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
        return (False, cur_state)
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
    return (True, cur_state)

def _test_main_statematcher():
  matcher = _PartialStateMatcher()
  matcher.add_valid_state(('站姿', '正常'))
  matcher.add_valid_state(('站姿', '开心'))
  matcher.add_valid_state(('侧身', '正常'))
  matcher.add_valid_state(('侧身', '愤怒'))
  matcher.finish_init()
  curstate = ['站姿', '正常']
  curstate2 = ['站姿', '开心']
  if (res := matcher.find_match(curstate, ['开心'])) != ('站姿', '开心'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate, ['正常'])) != ('站姿', '正常'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate, ['侧身'])) != ('侧身', '正常'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate2, ['侧身'])) != ('侧身', '正常'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate, ['侧身','愤怒'])) != ('侧身','愤怒'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate, ['侧身','开心'])) is not None:
    raise PPAssertionError
  if (res := matcher.find_match(curstate2, ['愤怒'])) is not None:
    raise PPAssertionError

if __name__ == "__main__":
  _test_main_statematcher()

TR_vn_codegen = TranslationDomain("vn_codegen")

class VNCodeGen:
  @dataclasses.dataclass
  class ParseContext:
    parent : typing.Any # ParseContext
    narrator : VNCharacterSymbol # 当前的默认旁白

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
      if not isinstance(parent, VNCodeGen.ParseContext):
        raise PPAssertionError
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
          if not len(specified_sayers) == 0:
            raise PPAssertionError
        case VNASTSayMode.MODE_LONG_SPEECH:
          if not len(specified_sayers) == 1:
            raise PPAssertionError
        case VNASTSayMode.MODE_INTERLEAVED:
          if not len(specified_sayers) >= 1:
            raise PPAssertionError
        case _:
          raise PPNotImplementedError()
      for t in specified_sayers:
        if not isinstance(t, tuple):
          raise PPAssertionError
        if not (isinstance(t[0], str) and isinstance(t[1], VNCharacterSymbol)):
          raise PPAssertionError
      self.say_mode = newmode
      self.say_mode_specified_sayers = specified_sayers
      self.interleaved_mode_last_sayer = None
      # 如果发言模式改变，之后如果有取默认角色的情况，我们使用模式中指定的角色
      if len(specified_sayers) > 0:
        self.last_sayer = specified_sayers[0]

    def get_last_sayer_for_default_target(self) -> tuple[str, VNCharacterSymbol] | None:
      return self.last_sayer

    def update_last_sayer(self, sayname : str, ch : VNCharacterSymbol):
      sayertuple = (sayname, ch)
      if self.say_mode == VNASTSayMode.MODE_INTERLEAVED:
        if sayertuple in self.say_mode_specified_sayers:
          self.interleaved_mode_last_sayer = sayertuple
      if ch.kind.get().value == VNCharacterKind.NARRATOR:
        return
      self.last_sayer = sayertuple

    def get_narration_sayer(self) -> tuple[str, VNCharacterSymbol]:
      # 对于 <内容> 类发言的发言者
      # 只有长发言模式会给定发言者，其他模式都只有旁白
      if self.say_mode == VNASTSayMode.MODE_LONG_SPEECH:
        return self.say_mode_specified_sayers[0]
      return (self.narrator.name, self.narrator)

    def get_quotedsay_sayer(self) -> tuple[str, VNCharacterSymbol]:
      # 对于 "<内容>" 类发言的发言者
      match self.say_mode:
        case VNASTSayMode.MODE_DEFAULT:
          if self.last_sayer:
            return self.last_sayer
          return (self.narrator.name, self.narrator)
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
      raise PPNotImplementedError()

    def resolve_alias(self, name : str) -> str:
      curpc = self
      while curpc is not None:
        if not isinstance(curpc, VNCodeGen.ParseContext):
          raise PPAssertionError
        if name in curpc.alias_dict:
          return curpc.alias_dict[name]
        curpc = curpc.parent
      return name

  ast : VNAST
  result : VNModel
  resolver : VNModelNameResolver
  _default_ns : tuple[str, ...]
  _func_map : dict[str, dict[tuple[str, ...], VNFunction]] # [名称] -> [命名空间] -> 函数体；现在仅用来在创建函数体时去重
  _all_functions : dict[VNASTFunction, VNFunction]
  _func_prebody_map : dict[VNFunction, Block]
  _func_postbody_map : dict[VNFunction, Block]
  #_char_sprite_map : dict[VNCharacterSymbol, dict[str, VNASTNamespaceSwitchableValueSymbol]]
  _char_parent_map : dict[VNCharacterSymbol, VNASTCharacterSymbol]
  _char_state_matcher : dict[VNCharacterSymbol, _PartialStateMatcher]
  _scene_parent_map : dict[VNSceneSymbol, VNASTSceneSymbol]
  _scene_state_matcher : dict[VNSceneSymbol, _PartialStateMatcher]
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
    self._char_parent_map = {}
    self._char_state_matcher = {}
    self._scene_parent_map = {}
    self._scene_state_matcher = {}
    narrator = VNCharacterSymbol.create_narrator(self.ast.context)
    self._global_parsecontext = VNCodeGen.ParseContext(parent=None, narrator=narrator)
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
    rootns.add_character(narrator)
    for name in VNCharacterSymbol.NARRATOR_ALL_NAMES:
      if name != narrator.name:
        rootns.add_alias(VNAliasSymbol.create(self.context, name, narrator.name, rootns.get_namespace_string()))

  @property
  def context(self):
    return self.ast.context

  _tr_alias_exist = TR_vn_codegen.tr("alias_already_exist",
    en="There is already an alias: {curalias}, cannot add the same alias to {target}",
    zh_cn="已经有以下别名： {curalias}, 无法再为此目标添加相同的别名： {target}",
    zh_hk="已經有以下別名： {curalias}, 無法再為此目標添加相同的別名： {target}",
  )

  def add_alias(self, alias_namespace : tuple[str, ...], alias : str, target : str, target_namespace : tuple[str, ...] | None = None, loc : Location | None = None) -> tuple[str, str] | None:
    # 尝试加入一个别名
    # 如果出错则返回一个 <code, msg> 的错误信息
    # 如果没出错就返回 None
    node = self.resolver.get_namespace_node(alias_namespace)
    if node is None or not isinstance(node, VNNamespace):
      raise PPInternalError
    if existing := node.aliases.get(alias):
      # 已经有一个同样名称的别名了
      code = 'vncodegen-alias-already-exist'
      existing_alias_str = '"' + alias + '"@' + VNNamespace.stringize_namespace_path(alias_namespace) + ' --> "' + existing.target_name.get().get_string() + '"@' + existing.target_namespace.get().get_string()
      target_str = '"' + target + '"'
      if target_namespace is not None:
        target_str += '@' + VNNamespace.stringize_namespace_path(target_namespace)
      msg = self._tr_alias_exist.format(curalias=existing_alias_str, target=target_str)
      return (code, msg)
    targetns = VNNamespace.stringize_namespace_path(alias_namespace  if target_namespace is None else target_namespace)
    symb = VNAliasSymbol.create(self.context, name=alias, target_name=target, target_namespace=targetns, loc=loc)
    node.add_alias(symb)
    return None

  def resolve_function(self, name : str, from_namespace : tuple[str, ...]) -> VNFunction | None:
    if func := self.resolver.unqualified_lookup(name, from_namespace, None):
      if not isinstance(func, VNFunction):
        raise PPAssertionError
      return func
    return None

  def resolve_asset(self, name : str, from_namespace : tuple[str, ...], parsecontext : ParseContext) -> VNConstExprAsSymbol | None:
    asset = self.resolver.unqualified_lookup(name, from_namespace, None)
    if asset is None or not isinstance(asset, VNConstExprAsSymbol):
      return None
    return asset

  def resolve_character(self, sayname : str, from_namespace : tuple[str, ...], parsecontext : ParseContext) -> VNCharacterSymbol | None:
    # 尝试解析对角色名称的引用
    # 返回（1）实际发言名，（2）发言者身份

    # 首先检查名称是不是别名，是的话更新一下名称
    #curpc = parsecontext
    #while curpc is not None:
    #  assert isinstance(curpc, VNCodeGen.ParseContext)
    #  if name in curpc.alias_dict:
    #    name = curpc.alias_dict[name]
    #    break
    #  curpc = curpc.parent
    # 然后解析角色名
    character = self.resolver.unqualified_lookup(sayname, from_namespace, None)
    if character is None or not isinstance(character, VNCharacterSymbol):
      return None
    return character

  def resolve_character_sayinfo(self, character : VNCharacterSymbol, sayname : str, parsecontext : ParseContext) -> VNASTCharacterSayInfoSymbol | None:
    # 根据实际发言名和发言者身份，找到发言所用的外观信息
    # 如果没有提供发言名（比如是从默认发言者中来的），就从发言者身份中取
    # 该函数找不到后加的、没有声明的角色的发言信息
    if len(sayname) == 0:
      sayname = character.name

    # 如果当前环境指定了这个角色应该用什么发言信息，就用指定的值
    curpc = parsecontext
    while curpc is not None:
      if not isinstance(curpc, VNCodeGen.ParseContext):
        raise PPAssertionError
      if character in curpc.temp_say_dict:
        saydict = curpc.temp_say_dict[character]
        if sayname in saydict:
          return saydict[sayname]
      curpc = curpc.parent

    # 如果环境中没有指定，就到上层去找
    if character in self._char_parent_map:
      astchar = self._char_parent_map[character]
      if info := astchar.sayinfo.get(sayname):
        return info
      # 不应该发生，但实在不行可以用这样
      return astchar.sayinfo.get(astchar.name)

    # 如果角色是新加的、没声明的，我们会找不到原来的发言格式
    return None

  def resolve_scene(self, name : str, from_namespace : tuple[str, ...], parsecontext : ParseContext) -> VNSceneSymbol | None:
    # 首先检查名称是不是别名，是的话更新一下名称
    curpc = parsecontext
    while curpc is not None:
      if not isinstance(curpc, VNCodeGen.ParseContext):
        raise PPAssertionError
      if name in curpc.alias_dict:
        name = curpc.alias_dict[name]
        break
      curpc = curpc.parent
    # 然后解析角色名
    scene = self.resolver.unqualified_lookup(name, from_namespace, None)
    if scene is None or not isinstance(scene, VNSceneSymbol):
      return None
    return scene

  def get_or_create_ns(self, namespace : tuple[str, ...]) -> VNNamespace:
    if node := self.resolver.get_namespace_node(namespace):
      if not isinstance(node, VNNamespace):
        raise PPAssertionError
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

  def get_file_nstuple(self, file : VNASTFileInfo) -> tuple[str,...]:
    if ns := file.namespace.try_get_value():
      return VNNamespace.expand_namespace_str(ns.get_string())
    return self._default_ns

  _tr_duplicated_function_def = TR_vn_codegen.tr("duplicated_function_def",
    en="Duplicated function/section definition is ignored: {file}: {function} (first definition at: {existingloc})",
    zh_cn="重名的函数/章节定义将被忽略： {file}: {function} (第一个定义位于： {existingloc})",
    zh_hk="重名的函數/章節定義將被忽略： {file}: {function} (第一個定義位於： {existingloc})",
  )

  def collect_functions(self):
    # 找到所有的函数，创建对应的命名空间，并把函数加到记录中
    # 做这步的目的是为了提前创建好所有 VNFunction, 这样其他函数可以直接生成对其的调用
    for file in self.ast.files.body:
      if not isinstance(file, VNASTFileInfo):
        raise PPAssertionError
      if len(file.functions.body) == 0:
        continue
      namespace = self._default_ns
      if ns := file.namespace.try_get_value():
        namespace = VNNamespace.expand_namespace_str(ns.get_string())
      nsnode = self.get_or_create_ns(namespace)
      for func in file.functions.body:
        if not isinstance(func, VNASTFunction):
          raise PPAssertionError
        if func.name not in self._func_map:
          self._func_map[func.name] = {}
        funcdict = self._func_map[func.name]
        if namespace in funcdict:
          # 我们已经有相同的函数了
          # 给现有的函数体开头加个错误提示
          existingfunc = funcdict[namespace]
          postbody = self.get_function_postbody(existingfunc)
          msg = self._tr_duplicated_function_def.format(file=file.name, function=func.name, existingloc=str(existingfunc.location))
          err = ErrorOp.create(error_code='vncodegen-name-clash', context=self.context, error_msg=StringLiteral.get(msg, self.context), loc=func.location)
          postbody.push_back(err)
          continue
        function = VNFunction.create(self.context, func.name, func.location)
        nsnode.add_function(function)
        self._all_functions[func] = function
        funcdict[namespace] = func

  def run_codegen(self):
    for file in self.ast.files.body:
      filecontext = VNCodeGen.ParseContext.forkfrom(self._global_parsecontext)
      for func in file.functions.body:
        if not isinstance(func, VNASTFunction):
          raise PPAssertionError
        self.generate_function_body(file, filecontext, func, self._all_functions[func])

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

  def emit_assetnotfound(self, loc : Location | None, dest : Block):
    self.emit_error("vncodegen-asset-notfound-general", self.context.get_file_auditor().get_asset_not_found_errmsg(), loc=loc, dest=dest)

  def create_unknown_sayer(self, sayname : str, from_namespace : tuple[str,...]) -> VNCharacterSymbol:
    ch = VNCharacterSymbol.create(context=self.context, kind=VNCharacterKind.NORMAL, name=sayname)
    ns = self.get_or_create_ns(from_namespace)
    ns.add_character(ch)
    return ch

  def create_unknown_scene(self, scenename : str, from_namespace : tuple[str,...]) -> VNSceneSymbol:
    scene = VNSceneSymbol.create(context=self.context, name=scenename)
    ns = self.get_or_create_ns(from_namespace)
    ns.add_scene(scene)
    return scene

  @dataclasses.dataclass
  class _NonlocalCodegenHelper(VNASTVisitor):
    codegen : VNCodeGen
    namespace_tuple : tuple[str, ...]
    basepath : str
    parsecontext : VNCodeGen.ParseContext
    warningdest : Block

    # 如果可以处理命令则返回 True, 否则返回 False

    def visit_default_handler(self, node: VNASTNodeBase):
      return False

    def visitVNASTTempAliasNode(self, node: VNASTTempAliasNode):
      self.parsecontext.handle_temp_alias(node)
      return True

    _tr_temp_say_attr_skipped_char_not_found = TR_vn_codegen.tr("temp_say_attr_skipped_char_not_found",
      en="Setting character say attribute failed because character \"{character}\" not found.",
      zh_cn="未知发言者“{character}”，设置其临时发言属性失败。",
      zh_hk="未知發言者「{character}」，設置其臨時發言屬性失敗。",
    )
    def visitVNASTCharacterTempSayAttrNode(self, node: VNASTCharacterTempSayAttrNode):
      character = node.character.get().get_string()
      sayname = self.parsecontext.resolve_alias(character)
      ch = self.codegen.resolve_character(sayname=sayname, from_namespace=self.namespace_tuple, parsecontext=self.parsecontext)
      if ch is None:
        # 在这里我们只报错并忽略就行了
        msg = self._tr_temp_say_attr_skipped_char_not_found.format(character=character)
        self.codegen.emit_error(code='vncodegen-character-nameresolution-failed', msg=msg, loc=node.location, dest=self.warningdest)
      else:
        self.parsecontext.handle_temp_say_attr(node, ch)
      return True

    _tr_say_mode_change_char_not_found = TR_vn_codegen.tr("say_mode_change_char_not_found",
      en="When handling say mode change: character \"{character}\" not found and we will create the character with default settings.",
      zh_cn="处理发言模式改变命令时：未知发言者“{character}”，我们将使用默认设置创建该发言者。",
      zh_hk="處理發言模式改變命令時：未知發言者「{character}」，我們將使用默認設置創建該發言者。",
    )
    _tr_say_mode_change_long_speech_nosayer = TR_vn_codegen.tr("say_mode_change_long_speech_nosayer",
      en="Long speech mode without specifying the sayer; the say mode is unchanged.",
      zh_cn="长发言模式没指定发言者；发言模式不变。",
      zh_hk="長發言模式沒指定發言者；發言模式不變。",
    )
    _tr_say_mode_change_interleave_nosayer = TR_vn_codegen.tr("say_mode_change_interleave_nosayer",
      en="Interleaving mode without specifying the sayer; the say mode is unchanged.",
      zh_cn="交替发言模式没指定发言者；发言模式不变。",
      zh_hk="交替發言模式沒指定發言者；發言模式不變。",
    )

    def visitVNASTSayModeChangeNode(self, node: VNASTSayModeChangeNode):
      target_mode : VNASTSayMode = node.target_mode.get().value
      specified_sayers : list[tuple[str, VNCharacterSymbol]] = []
      ns = self.namespace_tuple
      for u in node.specified_sayers.operanduses():
        sayerstr = u.value.get_string()
        assert isinstance(sayerstr, str)
        sayname = self.parsecontext.resolve_alias(sayerstr)
        ch = self.codegen.resolve_character(sayname=sayname, from_namespace=ns, parsecontext=self.parsecontext)
        if ch is None:
          # 在这里我们除了报错之外还需要生成一个默认的发言者，这样不至于令后续所有发言者错位
          msg = self._tr_say_mode_change_char_not_found.format(character=sayerstr)
          self.codegen.emit_error(code='vncodegen-character-nameresolution-failed', msg=msg, loc=node.location, dest=self.warningdest)
          ch = self.codegen.create_unknown_sayer(sayname, ns)
        t = (sayname, ch)
        specified_sayers.append(t)
      # 检查指定的发言者数量，如果不对的话作出调整
      is_check_passed = True
      match target_mode:
        case VNASTSayMode.MODE_DEFAULT:
          if len(specified_sayers) > 0:
            raise PPInternalError
        case VNASTSayMode.MODE_LONG_SPEECH:
          if len(specified_sayers) > 1:
            raise PPInternalError
          if len(specified_sayers) == 0:
            if prev_sayer := self.parsecontext.get_last_sayer_for_default_target():
              specified_sayers.append(prev_sayer)
            else:
              self.codegen.emit_error(code='vncodegen-saymode-insufficient-sayer', msg=self._tr_say_mode_change_long_speech_nosayer.get(), loc=node.location, dest=self.warningdest)
              is_check_passed = False
        case VNASTSayMode.MODE_INTERLEAVED:
          if len(specified_sayers) == 0:
            self.codegen.emit_error(code='vncodegen-saymode-insufficient-sayer', msg=self._tr_say_mode_change_interleave_nosayer.get(), loc=node.location, dest=self.warningdest)
            is_check_passed = False
        case _:
          raise NotImplementedError()
      if is_check_passed:
        self.parsecontext.handle_say_mode_change(target_mode, specified_sayers)
      return True

    def visitVNASTChangeDefaultDeviceNode(self, node: VNASTChangeDefaultDeviceNode):
      raise PPNotImplementedError("TODO")


  def handle_nonlocal_noasm_node(self, file : VNASTFileInfo, parsecontext : ParseContext, op : VNASTNodeBase, warningdest : Block) -> bool:
    # 有部分结点既可以在文件域出现也可以在函数域出现，并且对它们的处理也是一样的
    # 我们就用这一个函数来同时处理这两种情况
    # 如果结点可以处理就返回 True，结点没有处理（不是所列举的情况）就返回 False
    helper = VNCodeGen._NonlocalCodegenHelper(codegen=self, namespace_tuple=self.get_file_nstuple(file), basepath=file.location.get_file_path(), parsecontext=parsecontext, warningdest=warningdest)
    return helper.visit(op)

  _tr_functionlocal_node_in_globalscope = TR_vn_codegen.tr("functionlocal_node_in_globalscope",
    en="Command node {node} is only meaningful inside a function (i.e., cannot be in file scope) and will be ignored.",
    zh_cn="命令结点 {node} 只在函数内有意义(也就是说不能在函数范围外、只在文件域内)，将被忽略。",
    zh_hk="命令結點 {node} 只在函數內有意義(也就是說不能在函數範圍外、只在文件域內)，將被忽略。",
  )

  def handle_filelocal_node(self, file : VNASTFileInfo, parsecontext : ParseContext, op : VNASTNodeBase, warningdest : Block, asmdest : Block):
    # 当我们在函数体外碰到非 MetadataOp 时，我们使用该函数来处理操作项
    # 报错信息写到 warningdest 中
    if type(op).TRAIT_FUNCTION_CONTEXT_ONLY:
      msg = self._tr_functionlocal_node_in_globalscope.format(node=type(op).__name__)
      self.emit_error(code='vncodegen-functionlocal-command-in-globalscope', msg=msg, loc=op.location, dest=warningdest)
      return
    if isinstance(op, VNASTASMNode):
      if node := self.emit_asm(op):
        asmdest.push_back(node)
      return
    if self.handle_nonlocal_noasm_node(file, parsecontext, op, warningdest):
      return
    raise PPInternalError

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
      # 对于每个（在场的和不在场的）角色，如果该角色有状态信息，我们用该结构体来记录
      index : int
      sayname : str
      identity : VNCharacterSymbol
      state : tuple[str,...]
      sprite_handle : Value | None = None

      def copy(self):
        return VNCodeGen.SceneContext.CharacterState(index=self.index, sayname=self.sayname, identity=self.identity, state=self.state, sprite_handle=self.sprite_handle)

    @dataclasses.dataclass
    class AssetState:
      # 对于每个在台上的资源（包括背景音乐、音效、图片等），我们用这个结构体来保存信息
      dev : VNDeviceSymbol
      search_names : list[str]
      data : Value # AssetData | AssetDecl | AssetPlaceholder
      output_handle : Value | None = None

      def copy(self):
        return VNCodeGen.SceneContext.AssetState(dev=self.dev, search_names=self.search_names.copy(), data=self.data, output_handle=self.output_handle)

    # SceneContext 下的角色信息
    character_dict : dict[tuple[str, VNCharacterSymbol], int] = dataclasses.field(default_factory=dict) # (发言名, 身份) --> 状态索引
    character_states : dict[int, CharacterState] = dataclasses.field(default_factory=dict) # 状态索引 --> 状态
    character_sayname_inuse : dict[VNCharacterSymbol, list[str]] = dataclasses.field(default_factory=dict) # 身份 --> 发言名列表; 为了在改变发言名时找到现在记录里用的是什么发言名

    # SceneContext 下的场上使用的资源信息
    # 虽然我们需要按照多种信息对资源进行搜索，但由于场上的资源一般不是很多，我们就使用一个数组，循环查找就应该够了
    asset_info : list[AssetState] = dataclasses.field(default_factory=list)
    scene_bg : AssetState | None = None # 场景背景的信息。不参与普通的使用中资源的查找，所以放在外面
    scene_symb : VNSceneSymbol | None = None # 当前场景
    scene_states : tuple[str,...] | None = None

    bgm : AudioAssetData | None = None

    def update_character_sayname(self, ch : VNCharacterSymbol, oldname : str, newname : str):
      saynamelist = self.character_sayname_inuse[ch]
      if not len(saynamelist) == 1:
        raise PPAssertionError("TODO")
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
      if character in codegen._char_state_matcher:
        statetuple = codegen._char_state_matcher[character].get_default_state()
      else:
        statetuple = ()
      newstate = VNCodeGen.SceneContext.CharacterState(index=index, sayname=sayname, identity=character, state=statetuple, sprite_handle=None)
      self.character_states[index] = newstate
      self.character_dict[searchtuple] = index
      return newstate

    def try_get_character_state(self, sayname : str, character : VNCharacterSymbol) -> VNCodeGen.SceneContext.CharacterState | None:
      searchtuple = (sayname, character)
      if searchtuple in self.character_dict:
        return self.character_states[self.character_dict[searchtuple]]
      return None

    def search_asset_inuse(self, *, dev : VNDeviceSymbol | None = None, searchname : str | None = None, data : Value | None = None) -> list[AssetState]:
      result : list[VNCodeGen.SceneContext.AssetState] = []
      for candidate in self.asset_info:
        if dev is not None and candidate.dev != dev:
          continue
        if data is not None and candidate.data != data:
          continue
        if searchname is not None:
          is_searchname_found = False
          for name in candidate.search_names:
            if searchname in name:
              is_searchname_found = True
              break
          if not is_searchname_found:
            continue
        # 到这就说明所有检查都通过了
        result.append(candidate)
      return result

    def get_handle_list_upon_call(self) -> list[Value]:
      # 当处理调用时，我们认为所有的句柄都会被清理掉
      # 在这里把所有的这些句柄都加到该列表里
      result : list[Value] = []
      for state in self.character_states.values():
        if state.sprite_handle:
          result.append(state.sprite_handle)
      for info in self.asset_info:
        if info.output_handle:
          result.append(info.output_handle)
      if self.scene_bg is not None and self.scene_bg.output_handle is not None:
        result.append(self.scene_bg.output_handle)
      return result

    def mark_after_call(self):
      # 当有还会返回的函数调用时会被调用
      # 理论上是应该把当前的所有句柄都清理掉
      # 现在先不做，试试看有没有这个需要
      pass

    @staticmethod
    def forkfrom(parent):
      if not isinstance(parent, VNCodeGen.SceneContext):
        raise PPAssertionError
      character_states = {}
      for index, state in parent.character_states.items():
        character_states[index] = state.copy()
      character_sayname_inuse = {}
      for symb, names in parent.character_sayname_inuse.items():
        character_sayname_inuse[symb] = names.copy()
      asset_info = [info.copy() for info in parent.asset_info]
      scene_bg = parent.scene_bg.copy() if  parent.scene_bg is not None else None
      return VNCodeGen.SceneContext(character_dict=parent.character_dict.copy(),character_states=character_states, character_sayname_inuse=character_sayname_inuse, asset_info=asset_info, scene_bg=scene_bg, scene_symb=parent.scene_symb, scene_states=parent.scene_states, bgm=parent.bgm)

  @dataclasses.dataclass
  class FunctionCodegenContext:
    # 除了 entry 之外所有的块都在 block_dict 里面
    # entry 块不接受按名查找
    destfunction : VNFunction
    block_dict : dict[str, Block] = dataclasses.field(default_factory=dict)
    states_dict : dict[Block, VNCodeGen.SceneContext] = dataclasses.field(default_factory=dict)
    anonymous_ctrlflow_entity_indexing_dict : dict[type, int] = dataclasses.field(default_factory=dict) # <像 VNASTMenuNode 这样的 type> --> index
    anon_block_index : int = 0
    empty_state_characters_warned : set[VNCharacterSymbol] = dataclasses.field(default_factory=set)

    def get_or_create_basic_block(self, labelname : str) -> Block:
      if labelname == 'entry':
        raise PPAssertionError("User should not be able to create or referring to the entry block")
      # 获取一个以 labelname 命名的基本块
      # 如果基本块已存在就直接使用存在的基本块
      # 如果不存在就先创建
      # 我们既使用该函数来解析对标签的引用，又用该函数来创建新的内部基本块
      # 这样对标签的引用就可以直接转化为对基本块的引用，不必再转
      # 如果基本块只被引用、没有被初始化，则我们在最后会给它们填错误处理的代码
      if labelname in self.block_dict:
        return self.block_dict[labelname]
      block = self.destfunction.create_block(name=labelname)
      self.block_dict[labelname] = block
      return block

    def register_new_block(self, helper : VNCodeGen._FunctionCodegenHelper, destblock : Block):
      if destblock in self.states_dict:
        raise PPAssertionError("destblock already registered")
      self.states_dict[destblock] = helper.scenecontext

    def try_get_destblock_entrystate(self, destblock : Block) -> VNCodeGen.SceneContext | None:
      return self.states_dict.get(destblock)

    def create_anon_block(self, labelname : str | None = None) -> Block:
      # 获取一个其名字不参与按名搜索的块，即可以随意调整名称
      # 如果这个标签名已经被用掉了，我们在后面加数字后缀，直到名字可用
      if labelname is None:
        labelname = 'anon_block_' + str(self.anon_block_index)
        self.anon_block_index += 1
      if labelname not in self.block_dict:
        block = self.destfunction.create_block(name=labelname)
        self.block_dict[labelname] = block
        return block
      basename = labelname + '_'
      loopindex = 0
      cur_name = basename + str(loopindex)
      while cur_name in self.block_dict:
        loopindex += 1
        cur_name = basename + str(loopindex)
      block = self.destfunction.create_block(name=cur_name)
      self.block_dict[cur_name] = block
      return block

    def get_anonymous_ctrlflow_entity_index(self, cls : type) -> int:
      if cls in self.anonymous_ctrlflow_entity_indexing_dict:
        cur = self.anonymous_ctrlflow_entity_indexing_dict[cls]
        self.anonymous_ctrlflow_entity_indexing_dict[cls] += 1
        return cur
      self.anonymous_ctrlflow_entity_indexing_dict[cls] = 1
      return 0

  @dataclasses.dataclass
  class _FunctionCodegenHelper(_NonlocalCodegenHelper):
    parsecontext : VNCodeGen.ParseContext
    scenecontext : VNCodeGen.SceneContext
    functioncontext : VNCodeGen.FunctionCodegenContext
    srcregion : VNASTCodegenRegion
    destblock : Block
    starttime : Value
    convergeblock : Block # 如果在函数内，这是 None; 如果这是在某个控制流结构下，这是输入块自然结束时的跳转目标
    loopexitblock : Block | None = None # 如果在循环内的话，这是最内侧循环的出口块
    # 如果现在正在解析 VNASTTransitionNode 下的内容的话，这里应该是解析好的转场效果
    is_in_transition : bool = False
    # 如果是 Value, 这是一个通用的转场
    # 如果是 tuple, 这是某个后端独有的转场
    # 如果是 None,  则父转场结点没有提供转场
    parent_transition : Value | tuple[StringLiteral, StringLiteral] | None = None
    transition_child_finishtimes : list[Value] = dataclasses.field(default_factory=list)

    # 当前是否已经有终指令
    cur_terminator : VNTerminatorInstBase | None = None

    @property
    def context(self):
      return self.codegen.context

    @property
    def destfunction(self):
      return self.functioncontext.destfunction

    def visit_default_handler(self, node : VNASTNodeBase):
      raise PPNotImplementedError()

    _tr_unhandled_node_in_terminated_block = TR_vn_codegen.tr("unhandled_node_in_terminated_block",
      en="The unexpected command node in a terminated block will be ignored: {node}. Please put contents before the instruction that would terminate the block (e.g., jump, select).",
      zh_cn="以下命令结点在一个已经结束的基本块中，内容不会被处理： {node}。请将内容移至可能结束该基本块的指令前（比如跳转、选项等）。",
      zh_hk="以下命令結點在一個已經結束的基本塊中，內容不會被處理： {node}。請將內容移至可能結束該基本塊的指令前（比如跳轉、選項等）。",
    )

    def check_blocklocal_cond(self, node : VNASTNodeBase) -> bool:
      # 检查该指令是否在正常的、未结束的块中
      # 是的话返回 False, 不在正常情况下时生成错误并返回 True
      if self.cur_terminator is None:
        return False
      msg = self._tr_unhandled_node_in_terminated_block.format(node=node.get_short_str(0))
      err = ErrorOp.create(error_code='vncodegen-unhandled-node-in-terminated-block', context=self.context, error_msg=StringLiteral.get(msg, self.context), loc=node.location)
      err.insert_before(self.cur_terminator)
      return True

    def check_block_or_function_local_cond(self, node : VNASTNodeBase) -> bool:
      # 检查该指令是否在未结束的块或是函数体中
      if self.cur_terminator is None:
        return False
      if self.convergeblock is None:
        return False
      msg = self._tr_unhandled_node_in_terminated_block.format(node=node.get_short_str(0))
      err = ErrorOp.create(error_code='vncodegen-unhandled-node-in-terminated-block', context=self.context, error_msg=StringLiteral.get(msg, self.context), loc=node.location)
      err.insert_before(self.cur_terminator)
      return True

    def visitVNASTASMNode(self, node: VNASTASMNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      if result := self.codegen.emit_asm(node):
        self.destblock.push_back(result)
        result.set_start_time(self.starttime)
        self.starttime = result.get_finish_time()
      return None

    # 这些可以直接继承父类的处理
    def visitVNASTTempAliasNode(self, node : VNASTTempAliasNode) -> VNTerminatorInstBase | None:
      if self.check_block_or_function_local_cond(node):
        return None
      super().visitVNASTTempAliasNode(node)
      return None
    def visitVNASTSayModeChangeNode(self, node : VNASTSayModeChangeNode) -> VNTerminatorInstBase | None:
      if self.check_block_or_function_local_cond(node):
        return None
      super().visitVNASTSayModeChangeNode(node)
      return None
    def visitVNASTChangeDefaultDeviceNode(self, node : VNASTChangeDefaultDeviceNode) -> VNTerminatorInstBase | None:
      if self.check_block_or_function_local_cond(node):
        return None
      super().visitVNASTChangeDefaultDeviceNode(node)
      return None

    # 需要小改动的
    def visitVNASTCharacterTempSayAttrNode(self, node : VNASTCharacterTempSayAttrNode) -> VNTerminatorInstBase | None:
      if self.check_block_or_function_local_cond(node):
        return None
      character = node.character.get().get_string()
      sayname = self.parsecontext.resolve_alias(character)
      ch = self.codegen.resolve_character(sayname=sayname, from_namespace=self.namespace_tuple, parsecontext=self.parsecontext)
      if ch is None:
        # 在这里我们只报错并忽略就行了
        msg = self._tr_temp_say_attr_skipped_char_not_found.format(character=character)
        self.codegen.emit_error(code='vncodegen-character-nameresolution-failed', msg=msg, loc=node.location, dest=self.warningdest)
        return None

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
      return None

    # 这些应该不会出现
    def visitVNASTCodegenRegion(self, node : VNASTCodegenRegion) -> VNTerminatorInstBase | None:
      raise PPInternalError
    def visitVNASTFileInfo(self, node : VNASTFileInfo) -> VNTerminatorInstBase | None:
      raise PPInternalError
    def visitVNASTFunction(self, node : VNASTFunction) -> VNTerminatorInstBase | None:
      raise PPInternalError

    # 辅助函数
    def emit_wait(self, loc : Location):
      node = VNWaitInstruction.create(context=self.context, start_time=self.starttime, name='', loc=loc)
      self.starttime = node.get_finish_time()
      self.destblock.push_back(node)

    def emit_jump_to_new_block(self, target : Block, loc : Location | None) -> VNBranchInst:
      node = VNBranchInst.create(context=self.context, start_time=self.starttime, defaultbranch=target, loc=loc)
      self.destblock.push_back(node)
      return node

    _tr_joinpath_character_missing = TR_vn_codegen.tr("joinpath_character_missing",
      en="Character {sayname} is shown from the main path but is not in joined path. Please check if the behavior is desirable.",
      zh_cn="角色 {sayname} 在首通路径上已入场但没在其他路径上入场。请确认目前的结果是否正确。",
      zh_hk="角色 {sayname} 在首通路徑上已入場但沒在其他路徑上入場。請確認目前的結果是否正確。",
    )
    _tr_joinpath_assetref_missing = TR_vn_codegen.tr("joinpath_assetref_missing",
      en="Asset {asset} is shown/used from the main path but is not in joined path. Please check if the behavior is desirable.",
      zh_cn="资源 {asset} 在首通路径上已启用但没在其他路径上启用。请确认目前的结果是否正确。",
      zh_hk="資源 {asset} 在首通路徑上已啟用但沒在其他路徑上啟用。請確認目前的結果是否正確。",
    )

    def emit_jump_to_block_mayexisting(self, target : Block, loc : Location | None) -> VNBranchInst:
      if prevstate := self.functioncontext.try_get_destblock_entrystate(target):
        # 检查所有资源
        # 如果有资源在之前进入该块时有的，现在没有了，那么报错
        # 如果有资源在之前进入该块时没有，现在多的，那么就把它去掉
        def find_root_creation(op : Value) -> VNCreateInst:
          # 根据一个句柄，找到创建该句柄的创建指令
          # 虽然句柄有可能直接就是 VNCreateInst, 但也可能是经过 VNModifyInst 的，所以这里需要查找
          if not isinstance(op.valuetype, VNHandleType):
            raise PPAssertionError
          while not isinstance(op, VNCreateInst):
            if isinstance(op, VNModifyInst):
              op = op.handlein.get()
            else:
              raise PPInternalError
          if not isinstance(op, VNCreateInst):
            raise PPAssertionError("TODO handle other scenarios")
          return op
        character_sprites : dict[VNCharacterSymbol, dict[VNCreateInst, Value]] = {}
        asset_usages : dict[VNDeviceSymbol, dict[Value, dict[VNCreateInst, Value]]] = {}
        def add_to_valuedict(handle : Value, creation : VNCreateInst, key : typing.Any, d : dict[typing.Any, dict[VNCreateInst, Value]]):
          if key not in d:
            d[key] = {creation : handle}
            return
          cur_dict = d[key]
          if creation in cur_dict:
            raise PPAssertionError("Handle already added?")
          cur_dict[creation] = handle
        # 首先总结当前状态
        # 角色状态
        for charstate in self.scenecontext.character_states.values():
          if sprite_handle := charstate.sprite_handle:
            creation = find_root_creation(sprite_handle)
            add_to_valuedict(sprite_handle, creation, charstate.identity, character_sprites)
        # 资源状态
        for assetstate in self.scenecontext.asset_info:
          if assetstate.dev in asset_usages:
            value_dict = asset_usages[assetstate.dev]
          else:
            value_dict = {}
            asset_usages[assetstate.dev] = value_dict
          assert assetstate.output_handle is not None
          creation = find_root_creation(assetstate.output_handle)
          add_to_valuedict(assetstate.output_handle, creation, assetstate.data, value_dict)
        # 开始检查目标块进入时的状态
        # 每碰到一个上场的角色、资源，我们尝试从记录中找到并删除
        # 如果没有找到，那么就生成一个错误
        # （暂时不生成致命错误，只报一下错）
        # 这样所有的都找完后，剩下的就是只有该块进入时才有的内容，我们把这些内容都撤下去
        checked_creations : set[VNCreateInst] = set()
        for charstate in prevstate.character_states.values():
          if sprite_handle := charstate.sprite_handle:
            is_found = False
            creation = find_root_creation(sprite_handle)
            if creation in checked_creations:
              is_found = True
            elif charstate.identity in character_sprites:
              cur_dict = character_sprites[charstate.identity]
              if creation in cur_dict:
                is_found = True
                del cur_dict[creation]
                checked_creations.add(creation)
            if not is_found:
              msg = self._tr_joinpath_character_missing.format(sayname=charstate.sayname)
              self.codegen.emit_error(code='vncodegen-joinpath-character-missing', msg=msg, loc=loc, dest=self.destblock)
        for assetstate in prevstate.asset_info:
          if handle := assetstate.output_handle:
            creation = find_root_creation(handle)
            if creation in checked_creations:
              continue
            is_found = False
            if assetstate.dev in asset_usages:
              cur_dict = asset_usages[assetstate.dev]
              if assetstate.data in cur_dict:
                value_dict = cur_dict[assetstate.data]
                if creation in value_dict:
                  is_found = True
                  del value_dict[creation]
                  checked_creations.add(creation)
            if not is_found:
              msg = self._tr_joinpath_assetref_missing.format(asset=str(assetstate.data))
              self.codegen.emit_error(code='vncodegen-joinpath-assetref-missing', msg=msg, loc=loc, dest=self.destblock)
        # 这样所有的都找完后，剩下的就是只有该块进入时才有的内容，我们把这些内容都撤下去
        rmindex = 0
        rmfinishtimes = []
        def remove_handle(handle : Value, transition : Value | None = None):
          nonlocal rmindex
          rm = VNRemoveInst.create(context=self.context, start_time=self.starttime, handlein=handle, name='pathjoin_remove_'+str(rmindex))
          rmindex += 1
          if transition is not None:
            rm.transition.set_operand(0, transition)
          self.destblock.push_back(rm)
          rmfinishtimes.append(rm.get_finish_time())

        chhide = VNDefaultTransitionType.DT_SPRITE_HIDE.get_enum_literal(self.context)
        for ch, d in character_sprites.items():
          for creation, handle in d.items():
            remove_handle(handle, chhide)
        for dev, d1 in asset_usages.items():
          for asset, d2 in d1.items():
            for creation, handle in d2.items():
              remove_handle(handle)

        # 最好能加一个同步，不过现在算了
        if len(rmfinishtimes) > 0:
          self.starttime = rmfinishtimes[-1]
        # 完成
      else:
        self.functioncontext.register_new_block(self, target)
      node = VNBranchInst.create(context=self.context, start_time=self.starttime, defaultbranch=target, loc=loc)
      self.destblock.push_back(node)
      return node

    def get_character_sprite(self, character : VNCharacterSymbol, state : tuple[str,...]) -> Value | None:
      if character in self.codegen._char_parent_map:
        srccharacter = self.codegen._char_parent_map[character]
        sprite = srccharacter.sprites.get(','.join(state))
        if isinstance(sprite, VNASTNamespaceSwitchableValueSymbol):
          sprite = sprite.get_value(self.namespace_tuple)
        return sprite
      return None

    def get_character_sideimage(self, character : VNCharacterSymbol, state : tuple[str,...] | None) -> Value | None:
      # state 如果有的话就是一个经过了状态匹配的完整状态
      # 由于我们认为立绘的状态是所有可能的状态的集合，而侧边头像状态是立绘状态的子集，
      # 我们这里会在找不到选项时尝试把状态串缩短来找到最佳的匹配项
      if character in self.codegen._char_parent_map:
        srcsayer = self.codegen._char_parent_map[character]
        if len(srcsayer.sideimages) > 0:
          if state is None:
            state = ()
          statestr = ','.join(state)
          while True:
            if sideimage := srcsayer.sideimages.get(statestr):
              return sideimage.get_value(self.namespace_tuple)
            if len(state) == 0:
              break
            state = state[:-1]
      return None

    def get_scene_background(self, scene : VNSceneSymbol, state : tuple[str, ...]) -> Value | None:
      if scene in self.codegen._scene_parent_map:
        srcscene = self.codegen._scene_parent_map[scene]
        background = srcscene.backgrounds.get(','.join(state))
        if isinstance(background, VNASTNamespaceSwitchableValueSymbol):
          background = background.get_value(self.namespace_tuple)
        return background
      return None

    _tr_character_state_empty = TR_vn_codegen.tr("character_state_empty",
      en="Character {character}: No sprite state declared, therefore all state changes will be ignored. If you want to introduce sprite change when the character state changes, please declare all sprite states when declaring the character.",
      zh_cn="角色 {character}: 没有找到立绘差分声明，所以所有的状态、表情改变都会被忽略。如果想在状态、表情改变时切换立绘，请在声明角色时声明所有的立绘差分。",
      zh_hk="角色 {character}: 沒有找到立繪差分聲明，所以所有的狀態、表情改變都會被忽略。如果想在狀態、表情改變時切換立繪，請在聲明角色時聲明所有的立繪差分。",
    )
    _tr_character_state_error = TR_vn_codegen.tr("character_state_error",
      en="Character {character}: Cannot apply state change {change} to original state {original} (i.e., no matching full state with sprite declared), so there is no sprite change here. Please either correct the state change or declare the missing sprites to have the sprite change here.",
      zh_cn="角色 {character}: 无法将状态改变 {change} 并入原状态 {original} (没有符合该状态改变、带立绘声明的完整状态), 所以这里立绘不会改变。如果要在这里启用立绘自动切换，请更正状态改变内容或者补充缺失的立绘声明。",
      zh_hk="角色 {character}: 無法將狀態改變 {change} 並入原狀態 {original} (沒有符合該狀態改變、帶立繪聲明的完整狀態), 所以這裏立繪不會改變。如果要在這裏啟用立繪自動切換，請更正狀態改變內容或者補充缺失的立繪聲明。",
    )

    def handleCharacterStateChange(self, sayname : str, character : VNCharacterSymbol, statelist : list[str], loc : Location | None = None) -> tuple[str,...]:
      # 改变角色当前的状态，主要任务是当角色在场上时，改变角色的立绘
      # 不过除了场上角色外，没有显示立绘的角色也需要记住状态，这样可以把侧边头像的状态也定下来
      # （我们假设侧边头像与显示立绘所接受的状态一致）
      # 返回一个最终状态的字符串元组
      # (该函数也用于在角色上场前确定上场时的状态)
      charstate = self.scenecontext.get_or_create_character_state(sayname=sayname, character=character, codegen=self.codegen)

      # 如果角色没有声明的话，我们无法检查状态是否有效，所以这种情况下直接使用空状态
      if character not in self.codegen._char_state_matcher:
        charstate.state = ()
        return ()

      curstate = list(charstate.state)
      matcher = self.codegen._char_state_matcher[character]
      is_full_match, matchresult = matcher.find_match_besteffort(curstate, statelist)
      if not is_full_match:
        if len(matcher.get_default_state()) == 0:
          # 该角色没有声明任何状态
          # 我们只在第一次生成一个错误
          if character in self.functioncontext.empty_state_characters_warned:
            pass
          else:
            self.functioncontext.empty_state_characters_warned.add(character)
            msg = self._tr_character_state_empty.format(character=character.name)
            self.codegen.emit_error(code='vncodegen-character-state-empty', msg=msg, loc=loc, dest=self.destblock)
        else:
          msg = self._tr_character_state_error.format(character=character.name, change=str(statelist), original=str(charstate.state))
          self.codegen.emit_error(code='vncodegen-character-state-error', msg=msg, loc=loc, dest=self.destblock)

      if matchresult == charstate.state:
        # 状态不变的话什么也不做
        return charstate.state
      # 到这就是确实有状态改变
      # 首先，如果当前角色在场上，我们需要改变其立绘
      # 改变状态的动作一般都没有渐变，直接切换
      if charstate.sprite_handle:
        sprite = self.get_character_sprite(character, matchresult)
        # 如果在场上有立绘，那么这里我们应该能够找到立绘
        if sprite is None:
          raise PPAssertionError("matched state should correspond to a sprite")
        handleout = VNModifyInst.create(context=self.context, start_time=self.starttime, handlein=charstate.sprite_handle, content=sprite, device=self.parsecontext.dev_foreground, loc=loc)
        # 改变状态导致的立绘变更应该不需要转场效果
        if not self.is_in_transition:
          self.starttime=handleout.get_finish_time()
        charstate.sprite_handle = handleout
        self.destblock.push_back(handleout)
      # 其次，改变记录中的状态
      charstate.state = matchresult
      return matchresult

    # 开始处理只在函数体内有意义的结点

    _tr_implicit_sayer = TR_vn_codegen.tr("implicit_sayer",
      en="Sayer {sayname} is not declared and will be implicitly created. Please check the spelling if you already have the declaration.",
      zh_cn="发言者 {sayname} 未被声明；我们会以默认设置创建该角色。如果您已经声明该角色，请检查拼写、输入错误。",
      zh_hk="發言者 {sayname} 未被聲明；我們會以默認設置創建該角色。如果您已經聲明該角色，請檢查拼寫、輸入錯誤。",
    )
    _tr_state_change_on_narrator = TR_vn_codegen.tr("state_change_on_narrator",
      en="The narrator cannot have expression states and we cannot set expression state {state} for the narrator.",
      zh_cn="旁白不能有状态、表情，我们无法将状态 {state} 赋予旁白。",
      zh_hk="旁白不能有狀態、表情，我們無法將狀態 {state} 賦予旁白。",
    )

    def visitVNASTSayNode(self, node : VNASTSayNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None

      # 特殊情况处理：如果长发言模式下遇到了有给出发言者或是发言状态的结点，我们很有可能是把发言内容误作了发言者或发言状态
      # 比如：
      #     今天我们来介绍一个新的项目：语涵编译器
      # 不是由一个叫“今天我们来介绍一个新的项目”说的一句“语涵编译器”
      # 这种时候我们要把原始内容当作发言内容
      raw_sayer = node.sayer.try_get_value()
      statelist : list[str] = [u.value.get_string() for u in node.expression.operanduses()]
      content_operand = node.content
      if self.parsecontext.say_mode == VNASTSayMode.MODE_LONG_SPEECH:
        if raw_sayer is not None or len(statelist) > 0:
          raw_sayer = None
          statelist = []
          content_operand = node.raw_content

      # 开始正常处理
      # 首先找到这句话是谁说的
      # 如果发言有附属的状态改变，则把状态改变先处理了
      # 最后再生成发言结点
      if raw_sayer is not None:
        rawname = raw_sayer.get_string()
        sayname = self.parsecontext.resolve_alias(rawname)
        ch = self.codegen.resolve_character(sayname=sayname, from_namespace=self.namespace_tuple, parsecontext=self.parsecontext)
        if ch is None:
          # 如果没找到发言者，我们在当前命名空间创建一个新的发言者
          msg = self._tr_implicit_sayer.format(sayname=sayname)
          self.codegen.emit_error(code='vncodegen-sayer-implicit-decl', msg=msg, loc=node.location, dest=self.warningdest)
          ch = self.codegen.create_unknown_sayer(sayname, self.namespace_tuple)
        sayertuple = (sayname, ch)
      else:
        if self.parsecontext.say_mode == VNASTSayMode.MODE_LONG_SPEECH:
          # 长发言模式下只有一种情况
          sayertuple = self.parsecontext.get_narration_sayer()
        else:
          match node.nodetype.get().value:
            case VNASTSayNodeType.TYPE_FULL:
              raise PPInternalError("The sayer should be provided in this case")
            case VNASTSayNodeType.TYPE_QUOTED:
              sayertuple = self.parsecontext.get_quotedsay_sayer()
            case VNASTSayNodeType.TYPE_NARRATE:
              sayertuple = self.parsecontext.get_narration_sayer()
            case _:
              raise PPNotImplementedError("TODO")
      # 至此，发言者身份应该已经确定；sayertuple 都应该是 (sayname, character)，即使是旁白应该也有
      # 如果涉及状态改变，则先处理这个
      sayname, character = sayertuple
      sayerstatetuple = None
      if len(statelist) > 0:
        match character.kind.get().value:
          case VNCharacterKind.NORMAL:
            sayerstatetuple = self.handleCharacterStateChange(sayname=sayname, character=character, statelist=statelist, loc=node.location)
          case VNCharacterKind.NARRATOR:
            # 如果发言带状态但是这句话是旁白说的，我们生成一个错误
            # （旁白不应该有表情状态）
            msg = self._tr_state_change_on_narrator.format(state=str(statelist))
            self.codegen.emit_error(code='vncodegen-sayexpr-narrator-expression', msg=msg, loc=node.location, dest=self.warningdest)
          case _:
            raise PPNotImplementedError("Unexpected character type: " + character.kind.get().value.name)

      self.parsecontext.update_last_sayer(sayname, character)

      # 然后生成发言
      sayid = self.codegen._global_say_index
      self.codegen._global_say_index += 1
      saynode = VNSayInstructionGroup.create(context=self.context, start_time=self.starttime, sayer=character, name=str(sayid), loc=node.location)
      # 首先，有配音的话放配音
      if voice := node.embed_voice.try_get_value():
        vnode = VNPutInst.create(context=self.context, start_time=self.starttime, content=voice, device=self.parsecontext.dev_voice, name='voice'+str(sayid), loc=node.location)
        saynode.body.push_back(vnode)
      # 其次，如果有侧边头像，就把侧边头像也加上
      # 我们从角色状态中取头像信息
      if character is not None and character in self.codegen._char_parent_map:
        if img := self.get_character_sideimage(character, sayerstatetuple):
          inode = VNPutInst.create(context=self.context, start_time=self.starttime, content=img, device=self.parsecontext.dev_say_sideimage, loc=node.location)
          saynode.body.push_back(inode)
      # 然后把发言者名字和内容放上去
      namestyle = None
      textstyle = None
      if character is not None:
        if info := self.codegen.resolve_character_sayinfo(character=character, sayname=sayname, parsecontext=self.parsecontext):
          namestyle = info.namestyle.try_get_value()
          textstyle = info.saytextstyle.try_get_value()
      if len(sayname) > 0 and character.kind.get().value != VNCharacterKind.NARRATOR:
        namevalue = StringLiteral.get(sayname, self.context)
        if namestyle is not None:
          namevalue = TextFragmentLiteral.get(context=self.context, string=namevalue, styles=namestyle)
        nnode = VNPutInst.create(context=self.context, start_time=self.starttime, content=namevalue, device=self.parsecontext.dev_say_name,loc=node.location)
        saynode.body.push_back(nnode)
      if textstyle is None:
        textvalue = [u.value for u in content_operand.operanduses()]
      else:
        textvalue = []
        for u in content_operand.operanduses():
          v = u.value
          if isinstance(v, StringLiteral):
            v = TextFragmentLiteral.get(self.context, v, textstyle)
          elif isinstance(v, TextFragmentLiteral):
            # 我们需要把两个格式合并起来，当前内容里的优先级更高
            mergedstyle = TextStyleLiteral.get_added(textstyle, v.style)
            v = TextFragmentLiteral.get(self.context, v.content, mergedstyle)
          textvalue.append(v)
      tnode = VNPutInst.create(context=self.context, start_time=self.starttime, content=textvalue, device=self.parsecontext.dev_say_text, loc=node.location)
      saynode.body.push_back(tnode)
      saynode.group_finish_time.set_operand(0, tnode.get_finish_time())
      self.starttime = saynode.get_finish_time()
      self.destblock.push_back(saynode)
      self.emit_wait(node.location)
      # 结束
      return None

    _tr_character_state_change_character_notfound = TR_vn_codegen.tr("character_state_change_character_notfound",
      en="Character {sayname} not found and the state change {change} is ignored. Please declare the character with sprite info if you want to enable sprite changes. Please check the spelling if you already have the declaration.",
      zh_cn="角色 {sayname} 未找到，状态改变 {change} 将被忽略。如果想启用立绘切换，请声明角色并提供立绘信息。如果您已经声明该角色，请检查拼写、输入错误。",
      zh_hk="角色 {sayname} 未找到，狀態改變 {change} 將被忽略。如果想啟用立繪切換，請聲明角色並提供立繪信息。如果您已經聲明該角色，請檢查拼寫、輸入錯誤。",
    )
    _tr_character_state_change_no_default_sayer = TR_vn_codegen.tr("character_state_change_no_default_sayer",
      en="No default sayer found and the state change {change} is ignored. To enable sprite change, please specify the sayer the state change should be applied to.",
      zh_cn="没找到默认发言者，状态改变 {change} 将被忽略。如果想启用立绘切换，请写明哪位发言者应该有此状态改变。",
      zh_hk="沒找到默認發言者，狀態改變 {change} 將被忽略。如果想啟用立繪切換，請寫明哪位發言者應該有此狀態改變。",
    )

    def visitVNASTCharacterStateChangeNode(self, node : VNASTCharacterStateChangeNode) -> VNTerminatorInstBase | None:
      if self.check_block_or_function_local_cond(node):
        return None
      statelist : list[str] = [u.value.get_string() for u in node.deststate.operanduses()]
      if rawnamel := node.character.try_get_value():
        rawname = rawnamel.get_string()
        sayname = self.parsecontext.resolve_alias(rawname)
        if ch := self.codegen.resolve_character(sayname=sayname, from_namespace=self.namespace_tuple, parsecontext=self.parsecontext):
          self.handleCharacterStateChange(sayname, ch, statelist, node.location)
        else:
          # 生成一个错误
          msg = self._tr_character_state_change_character_notfound.format(sayname=sayname, change=str(statelist))
          self.codegen.emit_error(code='vncodegen-character-notfound', msg=msg, loc=node.location, dest=self.warningdest)
      else:
        # 没有显式提供谁的状态应该改变
        if t := self.parsecontext.get_last_sayer_for_default_target():
          sayname, ch = t
          self.handleCharacterStateChange(sayname, ch, statelist, node.location)
        else:
          msg = self._tr_character_state_change_no_default_sayer.format(change=str(statelist))
          self.codegen.emit_error(code='vncodegen-character-notfound', msg=msg, loc=node.location, dest=self.warningdest)
      return None

    def handle_transition_and_finishtime(self, node : VNCreateInst | VNPutInst | VNModifyInst | VNRemoveInst):
      if not self.is_in_transition:
        self.starttime = node.get_finish_time()
      else:
        if self.parent_transition is not None:
          if isinstance(self.parent_transition, Value):
            node.transition.set_operand(0, self.parent_transition)
          elif isinstance(self.parent_transition, tuple):
            curfallback = node.transition.try_get_value()
            if isinstance(curfallback, EnumLiteral) and isinstance(curfallback.value, VNDefaultTransitionType):
              pass
            else:
              curfallback = VNDefaultTransitionType.DT_NO_TRANSITION.get_enum_literal(self.context)
            backend, expr = self.parent_transition
            final_transition = VNBackendDisplayableTransitionExpr.get(context=self.context, backend=backend, expression=expr, fallback=curfallback)
            node.transition.set_operand(0, final_transition)
          else:
            raise PPInternalError("Unexpected parent_transition type")
        self.transition_child_finishtimes.append(node.get_finish_time())

    _tr_character_entry_character_notfound = TR_vn_codegen.tr("character_entry_character_notfound",
      en="Character {sayname} not found and the entry with state {change} is ignored. Please declare the character with sprite info if you want to use sprites. Please check the spelling if you already have the declaration.",
      zh_cn="角色 {sayname} 未找到，以该状态 {change} 的入场操作将被忽略。如果想使用立绘，请声明角色并提供立绘信息。如果您已经声明该角色，请检查拼写、输入错误。",
      zh_hk="角色 {sayname} 未找到，以該狀態 {change} 的入場操作將被忽略。如果想使用立繪，請聲明角色並提供立繪信息。如果您已經聲明該角色，請檢查拼寫、輸入錯誤。",
    )
    _tr_character_entry_character_already_onstage = TR_vn_codegen.tr("character_entry_character_already_onstage",
      en="Character {sayname} is already on stage and cannot enter again.",
      zh_cn="角色 {sayname} 已经入场，不能再次上场。",
      zh_hk="角色 {sayname} 已經入場，不能再次上場。",
    )
    def visitVNASTCharacterEntryNode(self, node : VNASTCharacterEntryNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      rawname = node.character.get().get_string()
      sayname = self.parsecontext.resolve_alias(rawname)
      states = [u.value.get_string() for u in node.states.operanduses()]
      ch = self.codegen.resolve_character(sayname=sayname, from_namespace=self.namespace_tuple, parsecontext=self.parsecontext)
      if ch is None:
        # 生成错误然后结束
        msg = self._tr_character_entry_character_notfound.format(sayname=sayname, change=str(states))
        self.codegen.emit_error(code='vncodegen-character-notfound', msg=msg, loc=node.location, dest=self.warningdest)
        return None
      # 角色存在的话先设置角色状态
      finalstate = self.handleCharacterStateChange(sayname=sayname, character=ch, statelist=states, loc=node.location)
      # 然后如果有立绘的话，让角色立绘上场
      info = self.scenecontext.try_get_character_state(sayname, ch)
      if info is None:
        raise PPAssertionError
      if info.sprite_handle is not None:
        msg = self._tr_character_entry_character_already_onstage.format(sayname=sayname)
        self.codegen.emit_error(code='vncodegen-character-stateerror', msg=msg, loc=node.location, dest=self.destblock)
        return None
      if sprite := self.get_character_sprite(ch, finalstate):
        if not isinstance(sprite.valuetype, ImageType):
          raise PPAssertionError("We only support image types for now")
        cnode = VNCreateInst.create(context=self.context, start_time=self.starttime, content=sprite, ty=VNHandleType.get(sprite.valuetype), device=self.parsecontext.dev_foreground, loc=node.location)
        cnode.transition.set_operand(0, VNDefaultTransitionType.DT_SPRITE_SHOW.get_enum_literal(self.context))
        self.handle_transition_and_finishtime(cnode)
        info.sprite_handle = cnode
        self.destblock.push_back(cnode)
      # 完成
      return None

    _tr_character_exit_character_notfound = TR_vn_codegen.tr("character_exit_character_notfound",
      en="Character {sayname} not found and the exit operation is ignored. Please check the spelling if you already declared the character.",
      zh_cn="角色 {sayname} 未找到，退场操作将被忽略。如果您已经声明该角色，请检查拼写、输入错误。",
      zh_hk="角色 {sayname} 未找到，退場操作將被忽略。如果您已經聲明該角色，請檢查拼寫、輸入錯誤。",
    )
    _tr_character_exit_character_not_onstage = TR_vn_codegen.tr("character_exit_character_not_onstage",
      en="Character {sayname} is not on stage, so the exit operation is ignored.",
      zh_cn="角色 {sayname} 不在场上，退场操作将被忽略。",
      zh_hk="角色 {sayname} 不在場上，退場操作將被忽略。",
    )
    def visitVNASTCharacterExitNode(self, node : VNASTCharacterExitNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      rawname = node.character.get().get_string()
      sayname = self.parsecontext.resolve_alias(rawname)
      ch = self.codegen.resolve_character(sayname=sayname, from_namespace=self.namespace_tuple, parsecontext=self.parsecontext)
      if ch is None:
        # 生成错误然后结束
        msg = self._tr_character_exit_character_notfound.format(sayname=rawname)
        self.codegen.emit_error(code='vncodegen-character-notfound', msg=msg, loc=node.location, dest=self.warningdest)
        return None
      # 如果有角色的话就看看角色是否有在台上的立绘，有的话就撤下
      if info := self.scenecontext.try_get_character_state(sayname, ch):
        if info.sprite_handle:
          rm = VNRemoveInst.create(self.context, start_time=self.starttime, handlein=info.sprite_handle, loc=node.location)
          rm.transition.set_operand(0, VNDefaultTransitionType.DT_SPRITE_HIDE.get_enum_literal(self.context))
          self.handle_transition_and_finishtime(rm)
          self.destblock.push_back(rm)
          info.sprite_handle = None
        else:
          # 角色不在场上
          msg = self._tr_character_exit_character_not_onstage.format(sayname=sayname)
          self.codegen.emit_error(code='vncodegen-character-stateerror', msg=msg, loc=node.location, dest=self.destblock)
      return None

    _tr_assetref_asset_not_inuse = TR_vn_codegen.tr("assetref_asset_not_inuse",
      en="The asset is not in use and its removal is ignored: {asset}",
      zh_cn="该资源并不正在被使用，所以停用操作将被忽略: {asset}",
      zh_hk="該資源並不正在被使用，所以停用操作將被忽略: {asset}",
    )
    _tr_assetref_se_not_supported = TR_vn_codegen.tr("assetref_se_not_supporte",
      en="Special effect is not supported yet and the reference is ignored. Please contact the developer if you want this feature.",
      zh_cn="特效暂不支持，对特效的引用将被忽略。如果您需要该功能，请联系开发者。",
      zh_hk="特效暫不支持，對特效的引用將被忽略。如果您需要該功能，請聯系開發者。",
    )
    _tr_assetref_video_not_supported = TR_vn_codegen.tr("assetref_video_not_supported",
      en="Video playing is not supported yet and the reference is ignored. Please contact the developer if you want this feature.",
      zh_cn="视频播放暂不支持，对视频的引用将被忽略。如果您需要该功能，请联系开发者。",
      zh_hk="視頻播放暫不支持，對視頻的引用將被忽略。如果您需要該功能，請聯系開發者。",
    )
    def visitVNASTAssetReference(self, node : VNASTAssetReference) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      kind = node.kind.get().value
      operation = node.operation.get().value
      assetexpr = node.asset.get()

      # 目前而言，除了以下情况外：
      # 1. 引用特效：有一个完整的 VNASTPendingAssetReference, 可能会带参数
      # 2. 收起图片：有个只有名字的 VNASTPendingAssetReference, 不带参数
      # 其余情况下 node.asset 应该都是 AssetData
      # self.scenecontext.search_asset_inuse()
      assetdata = None
      assetexpr_name = None
      assetexpr_args = []
      assetexpr_kwargs = {}
      if isinstance(assetexpr, AssetData):
        assetdata = assetexpr
      elif isinstance(assetexpr, VNASTPendingAssetReference):
        assetexpr_name = assetexpr.populate_argdicts(assetexpr_args, assetexpr_kwargs)
      else:
        raise PPNotImplementedError('Unexpected asset expression type: ' + type(assetexpr).__name__)
      description = [u.value.get_string() for u in node.descriptions.operanduses()]
      match kind:
        case VNASTAssetKind.KIND_IMAGE:
          match operation:
            case VNASTAssetIntendedOperation.OP_CREATE:
              if not isinstance(assetdata, ImageAssetData):
                raise PPAssertionError
              cnode = VNCreateInst.create(context=self.context, start_time=self.starttime, content=assetdata, ty=VNHandleType.get(assetdata.valuetype), device=self.parsecontext.dev_foreground, name=node.name, loc=node.location)
              if transition := node.transition.try_get_value():
                cnode.transition.set_operand(0, transition)
              self.destblock.push_back(cnode)
              self.handle_transition_and_finishtime(cnode)
              info = VNCodeGen.SceneContext.AssetState(dev=self.parsecontext.dev_foreground, search_names=description, data=assetdata, output_handle=cnode)
              self.scenecontext.asset_info.append(info)
            case VNASTAssetIntendedOperation.OP_REMOVE:
              infolist = self.scenecontext.search_asset_inuse(dev=self.parsecontext.dev_foreground, searchname=assetexpr_name, data=assetdata)
              if len(infolist) == 0:
                assetstr = (assetexpr_name if assetexpr_name is not None and len(assetexpr_name) > 0 else str(assetdata))
                msg = self._tr_assetref_asset_not_inuse.format(asset=assetstr)
                self.codegen.emit_error(code='vncodegen-active-asset-not-found', msg=msg, loc=node.location, dest=self.destblock)
              else:
                # 应该只有一个资源
                # 把所有符合条件的都撤下来
                for info in infolist:
                  assert info.output_handle is not None
                  rnode = VNRemoveInst.create(context=self.context, start_time=self.starttime, handlein=info.output_handle, name=node.name, loc=node.location)
                  if transition := node.transition.try_get_value():
                    rnode.transition.set_operand(0, transition)
                  self.handle_transition_and_finishtime(rnode)
                  self.destblock.push_back(rnode)
                  self.scenecontext.asset_info.remove(info)
            case VNASTAssetIntendedOperation.OP_PUT:
              # 当前不应该出现这种情况
              raise NotImplementedError()
          return None
        case VNASTAssetKind.KIND_AUDIO:
          match operation:
            case VNASTAssetIntendedOperation.OP_PUT:
              assert isinstance(assetdata, AudioAssetData)
              pnode = VNPutInst.create(context=self.context, start_time=self.starttime, content=assetdata, device=self.parsecontext.dev_soundeffect, name=node.name, loc=node.location)
              if transition := node.transition.try_get_value():
                pnode.transition.set_operand(0, transition)
              # 这种情况下我们一般不更新开始时间，这个也不应该有渐变
              self.destblock.push_back(pnode)
            case _:
              # 当前不应该出现这种情况
              raise NotImplementedError()
          return None
        case VNASTAssetKind.KIND_EFFECT:
          msg = self._tr_assetref_se_not_supported.get()
          self.codegen.emit_error(code='vncodegen-not-implemented', msg=msg, loc=node.location, dest=self.destblock)
          return None
        case VNASTAssetKind.KIND_VIDEO:
          msg = self._tr_assetref_video_not_supported.get()
          self.codegen.emit_error(code='vncodegen-not-implemented', msg=msg, loc=node.location, dest=self.destblock)
          return None

      raise PPInternalError

    def visitVNASTTransitionNode(self, node : VNASTTransitionNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      transition_args = []
      transition_kwargs = {}
      transition_name = node.populate_argdicts(transition_args, transition_kwargs)
      warnings = []
      transition = parse_transition(self.context, transition_name=transition_name, transition_args=transition_args, transition_kwargs=transition_kwargs, warnings=warnings)
      for code, msg in warnings:
        self.codegen.emit_error(code, msg, node.location, dest=self.destblock)
      if self.is_in_transition:
        raise PPAssertionError("nested transition node should be impossible")
      self.parent_transition = transition
      self.is_in_transition = True
      for child in node.body.body:
        if isinstance(child, MetadataOp):
          self.destblock.push_back(child.clone())
        elif isinstance(child, VNASTNodeBase):
          self.visit(child)
      self.is_in_transition = False
      self.parent_transition = None
      # TODO 应该在这里加一个等待，如果有多个操作用相同的转场，我们应该先等它们全部结束再继续
      if len(self.transition_child_finishtimes) > 0:
        self.starttime = self.transition_child_finishtimes[-1]
      self.transition_child_finishtimes.clear()
      return None

    def _resolve_audio_reference(self, audio : VNASTPendingAssetReference, loc : Location | None) -> AudioAssetData | None:
      args = []
      kwargs = {}
      name = audio.populate_argdicts(args, kwargs)
      # 先找有没有声明的资源
      if asset := self.codegen.resolve_asset(name, self.namespace_tuple, self.parsecontext):
        v = asset.get_value()
        if isinstance(v, AudioAssetData):
          return v
      # 再找有没有文件符合要求
      warnings : list[tuple[str, str]] = []
      asset = emit_audio_from_path(context=self.context, pathexpr=name, basepath=self.basepath, warnings=warnings)
      for code, msg in warnings:
        self.codegen.emit_error(code, msg, loc=loc, dest=self.warningdest)
      if asset is not None:
        return asset
      return None

    _tr_bgm_audio_notfound = TR_vn_codegen.tr("bgm_audio_notfound",
      en="Cannot find audio {bgm}, set BGM operation ignored.",
      zh_cn="无法找到音频 {bgm}, 无法以此设置背景音乐。",
      zh_hk="無法找到音頻 {bgm}, 無法以此設置背景音樂。",
    )

    def visitVNASTSetBackgroundMusicNode(self, node : VNASTSetBackgroundMusicNode) -> VNTerminatorInstBase | None:
      bgm = node.bgm.get()
      if isinstance(bgm, AudioAssetData):
        bgmdata = bgm
      elif isinstance(bgm, VNASTPendingAssetReference):
        bgmdata = self._resolve_audio_reference(bgm, node.location)
        if bgmdata is None:
          msg = self._tr_bgm_audio_notfound.format(bgm=bgm.get_short_str_noheading())
          self.codegen.emit_error('vncodegen-audio-notfound', msg=msg, loc=node.location, dest=self.destblock)
          self.codegen.emit_assetnotfound(loc=node.location, dest=self.destblock)
          return None
      else:
        raise PPNotImplementedError
      bgmnode = VNCreateInst.create(context=self.context, start_time=self.starttime, content=bgmdata, device=self.parsecontext.dev_bgm, name=node.name, loc=node.location)
      if transition := node.transition.try_get_value():
        bgmnode.transition.set_operand(0, transition)
      self.destblock.push_back(bgmnode)
      self.scenecontext.bgm = bgm
      return None

    _tr_sceneswitch_scene_notfound = TR_vn_codegen.tr("sceneswitch_scene_notfound",
      en="Scene {scene} is not found and we will create this scene with no background. Please check the spelling if you already declared the scene.",
      zh_cn="场景 {scene} 未找到，我们将新建该场景且不设置其背景。如果您已经声明了该场景，请检查是否有拼写、输入错误。",
      zh_hk="場景 {scene} 未找到，我們將新建該場景且不設置其背景。如果您已經聲明了該場景，請檢查是否有拼寫、輸入錯誤。",
    )
    _tr_sceneswitch_scene_state_nomatch = TR_vn_codegen.tr("sceneswitch_scene_state_nomatch",
      en="Scene {scene} has no state {state} declared and we may set the correct background image. Please check the spelling and ensure the background image for this state is included in the scene declaration.",
      zh_cn="场景 {scene} 没有声明状态 {state}, 背景图片可能没有正确设置。请检查是否有拼写、输入错误，并确保该状态的背景图片已在场景声明中包含。",
      zh_hk="場景 {scene} 沒有聲明狀態 {state}, 背景圖片可能沒有正確設置。請檢查是否有拼寫、輸入錯誤，並確保該狀態的背景圖片已在場景聲明中包含。",
    )

    def visitVNASTSceneSwitchNode(self, node : VNASTSceneSwitchNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      #scene_bg : AssetState | None = None # 场景背景的信息。不参与普通的使用中资源的查找，所以放在外面
      #scene_symb : VNSceneSymbol | None = None # 当前场景
      #scene_states : tuple[str,...] | None = None
      destscene = node.destscene.get().get_string()
      states = [u.value.get_string() for u in node.states.operanduses()]
      # 不管场景解析成功与否，我们都会做场景切换
      # 这里先做好准备工作
      scene = self.codegen.resolve_scene(name=destscene, from_namespace=self.namespace_tuple, parsecontext=self.parsecontext)
      statetuple = ()
      scene_background = None
      if scene is None:
        msg = self._tr_sceneswitch_scene_notfound.format(scene=destscene)
        self.codegen.emit_error(code='vncodegen-scene-notfound', msg=msg, loc=node.location, dest=self.destblock)
        scene = self.codegen.create_unknown_scene(scenename=destscene, from_namespace=self.namespace_tuple)
      else:
        # 尝试匹配场景的状态
        if scene in self.codegen._scene_state_matcher:
          matcher = self.codegen._scene_state_matcher[scene]
          is_full_match, matchresult = matcher.find_match_besteffort(list(matcher.get_default_state()), states)
          if not is_full_match:
            msg = self._tr_sceneswitch_scene_state_nomatch.format(scene=destscene, state=str(states))
            self.codegen.emit_error(code='vncodegen-scene-state-nomatch', msg=msg, loc=node.location, dest=self.destblock)
          scene_background = self.get_scene_background(scene, matchresult)
          statetuple = matchresult

      switchnode = VNSceneSwitchInstructionGroup.create(context=self.context, start_time=self.starttime, dest_scene=scene, name=node.name, loc=node.location)
      rmtimes = []
      # 首先把当前场景下的所有东西先下了
      for info in self.scenecontext.asset_info:
        if info.output_handle is None:
          raise PPAssertionError
        rm = VNRemoveInst.create(context=self.context, start_time=self.starttime, handlein=info.output_handle, loc=node.location)
        if self.is_in_transition and self.parent_transition is not None:
          rm.transition.set_operand(0, self.parent_transition)
        switchnode.body.push_back(rm)
        rmtimes.append(rm.get_finish_time())
      self.scenecontext.asset_info.clear()
      # 再把当前场景下所有上场的角色给下了
      for characterinfo in self.scenecontext.character_states.values():
        if characterinfo.sprite_handle:
          rm = VNRemoveInst.create(context=self.context, start_time=self.starttime, handlein=characterinfo.sprite_handle, loc=node.location)
          if self.is_in_transition and self.parent_transition is not None:
            rm.transition.set_operand(0, self.parent_transition)
          else:
            rm.transition.set_operand(0, VNDefaultTransitionType.DT_SPRITE_HIDE.get_enum_literal(self.context))
          switchnode.body.push_back(rm)
          rmtimes.append(rm.get_finish_time())
          characterinfo.sprite_handle = None
      # 再把之前的场景的背景下了，换新的背景
      # 如果之前没背景、现在有背景，我们用 create
      # 如果之前有、现在没，我们用 remove
      # 如果都没有，什么也不干
      # 如果都有且背景不同，根据使用的转场效果决定，要么用 modify, 要么 create+remove
      # TODO 目前还不支持转场效果，所以所有转场都是 create + remove
      if self.scenecontext.scene_bg and self.scenecontext.scene_bg.output_handle:
        # 现在已有背景
        rm = VNRemoveInst.create(context=self.context, start_time=self.starttime, handlein=self.scenecontext.scene_bg.output_handle, loc=node.location)
        if self.is_in_transition and self.parent_transition is not None:
          rm.transition.set_operand(0, self.parent_transition)
        else:
          rm.transition.set_operand(0, VNDefaultTransitionType.DT_BACKGROUND_HIDE.get_enum_literal(self.context))
        switchnode.body.push_back(rm)
        rmtimes.append(rm.get_finish_time())
        self.scenecontext.scene_bg.output_handle = None

      self.scenecontext.scene_states = statetuple
      self.scenecontext.scene_symb = scene
      self.scenecontext.scene_bg = None
      best_finish_time = rmtimes[-1] if len(rmtimes) > 0 else self.starttime
      if scene_background is not None:
        cnode = VNCreateInst.create(context=self.context, start_time=best_finish_time, content=scene_background, ty=VNHandleType.get(scene_background.valuetype), device=self.parsecontext.dev_background, loc=node.location)
        if self.is_in_transition and self.parent_transition is not None:
          cnode.transition.set_operand(0, self.parent_transition)
        else:
          cnode.transition.set_operand(0, VNDefaultTransitionType.DT_BACKGROUND_SHOW.get_enum_literal(self.context))
        self.scenecontext.scene_bg = VNCodeGen.SceneContext.AssetState(dev=self.parsecontext.dev_background, search_names=[], data=scene_background, output_handle=cnode)
        best_finish_time = cnode.get_finish_time()
        switchnode.body.push_back(cnode)

      # 如果这次转场什么都没干就不添加结点了
      if len(switchnode.body.body) > 0:
        self.destblock.push_back(switchnode)
        switchnode.group_finish_time.set_operand(0, best_finish_time)
        self.starttime = switchnode.get_finish_time()
      # 结束
      return None

    def visitVNASTConditionalExecutionNode(self, node : VNASTConditionalExecutionNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      # 暂时不做
      raise PPNotImplementedError()
      return self.visit_default_handler(node)

    def visitVNASTMenuNode(self, node : VNASTMenuNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      namebase = node.name
      if len(namebase) == 0:
        namebase = 'anon_menu_' + str(self.functioncontext.get_anonymous_ctrlflow_entity_index(VNASTMenuNode))
      # 首先，如果我们需要循环的话，我们必须给该选单一个单独的块
      headerblock : Block | None = None
      if node.get_attr(VNASTMenuNode.ATTR_FINISH_ACTION) == VNASTMenuNode.ATTR_FINISH_ACTION_LOOP:
        headerblock = self.functioncontext.create_anon_block(namebase + '_header')
        self.emit_jump_to_new_block(headerblock, node.location)
        self.move_to_new_block(headerblock)
      # 在当前块中创建选单结点
      menu = VNMenuInst.create(context=self.context, start_time=self.starttime, name=namebase, loc=node.location)
      self.destblock.push_back(menu)
      # 然后创建个出口块
      exitblock = self.functioncontext.create_anon_block(namebase + '_exit')
      self.move_to_new_block(exitblock)
      # 最后再读取各个分支的内容，递归
      option_index = 0
      cond = BoolLiteral.get(True, self.context)
      convergeblock = headerblock if headerblock is not None else exitblock
      for op in node.body.body:
        if not isinstance(op, VNASTCodegenRegion):
          raise PPAssertionError
        operand = node.get_operand_inst(str(option_index))
        optionblock = self.functioncontext.create_anon_block(namebase + '_b' + str(option_index))
        self.functioncontext.register_new_block(self, optionblock)
        # 目前仅支持纯字符串字面值
        if operand.get_num_operands() == 1:
          optionstr = operand.get()
          if not isinstance(optionstr, StringLiteral):
            if not isinstance(optionstr, TextFragmentLiteral):
              raise PPAssertionError
            optionstr = optionstr.content
        else:
          cumulative_str = ''
          for u in operand.operanduses():
            v = u.value
            if isinstance(v, (StringLiteral, TextFragmentLiteral)):
              cumulative_str += v.get_string()
            else:
              cumulative_str += str(v)
          optionstr = StringLiteral.get(cumulative_str, self.context)
        menu.add_option(optionstr, optionblock, cond)
        self.run_codegen_for_region_helper(op, optionblock, convergeblock, exitblock)
        option_index += 1
      # 结束
      return None

    def run_codegen_for_region_helper(self, region : VNASTCodegenRegion, dest : Block, convergeblock : Block, loopexitblock : Block | None = None):
      # 如果我们要递归生成内部区域的内容，就用这个
      if loopexitblock is None:
        loopexitblock = self.loopexitblock
      VNCodeGen._FunctionCodegenHelper.run_codegen_for_region(
        codegen=self.codegen,
        namespace_tuple=self.namespace_tuple,
        basepath=self.basepath,
        functioncontext=self.functioncontext,
        baseparsecontext=self.parsecontext,
        basescenecontext=self.scenecontext,
        srcregion=region, dest=dest, deststarttime=dest.get_argument('start'),
        convergeblock=convergeblock, loopexitblock=loopexitblock)

    _tr_break_without_loop = TR_vn_codegen.tr("break_without_loop",
      en="Break command outside any loop and will be ignored.",
      zh_cn="“跳出循环”命令不在任何循环之中，命令将被忽略。",
      zh_hk="「跳出循環」命令不在任何循環之中，命令將被忽略。",
    )

    def visitVNASTBreakNode(self, node : VNASTBreakNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      if self.loopexitblock is not None:
        return self.emit_jump_to_block_mayexisting(self.loopexitblock, node.location)
      else:
        msg = self._tr_break_without_loop.get()
        self.codegen.emit_error(code='vncodegen-break-without-loop', msg=msg, loc=node.location, dest=self.destblock)
      return None

    def visitVNASTReturnNode(self, node : VNASTReturnNode) -> VNTerminatorInstBase | None:
      if self.check_block_or_function_local_cond(node):
        return None
      ret = VNReturnInst.create(context=self.context, start_time=self.starttime, name=node.name, loc=node.location)
      self.destblock.push_back(ret)
      return ret

    def visitVNASTLabelNode(self, node : VNASTLabelNode) -> VNTerminatorInstBase | None:
      if self.check_block_or_function_local_cond(node):
        return None
      labelname = node.labelname.get().get_string()
      destblock = self.functioncontext.get_or_create_basic_block(labelname)
      if self.cur_terminator is None:
        # 如果还没有终止当前基本块的话我们加一个跳转指令
        self.emit_jump_to_block_mayexisting(destblock, node.location)
        self.set_destblock(destblock)
      else:
        self.move_to_new_block(destblock)

    def visitVNASTJumpNode(self, node : VNASTJumpNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None
      targetlabel = node.target_label.get().get_string()
      destblock = self.functioncontext.get_or_create_basic_block(targetlabel)
      return self.emit_jump_to_block_mayexisting(destblock, node.location)

    _tr_callee_notfound = TR_vn_codegen.tr("callee_notfound",
      en="Callee {callee} is not found and no call will be generated. Please check if the names are spelled correctly.",
      zh_cn="被调用的函数/章节 {callee} 未找到，此处将不会生成调用。请检查是否有拼写、输入错误。",
      zh_hk="被調用的函數/章節 {callee} 未找到，此處將不會生成調用。請檢查是否有拼寫、輸入錯誤。",
    )

    def visitVNASTCallNode(self, node : VNASTCallNode) -> VNTerminatorInstBase | None:
      if self.check_blocklocal_cond(node):
        return None

      # 尝试找到调用对象
      callee = node.callee.get().get_string()
      func = self.codegen.resolve_function(callee, self.namespace_tuple)
      if func is None:
        msg = self._tr_callee_notfound.format(callee=callee)
        self.codegen.emit_error(code='vncodegen-callee-notfound', msg=msg, loc=node.location, dest=self.destblock)
        return None

      # 开始输出
      handle_list = self.scenecontext.get_handle_list_upon_call()
      if node.is_tail_call():
        call = VNTailCallInst.create(context=self.context, start_time=self.starttime, target=func, destroyed_handle_list=handle_list, name=node.name, loc=node.location)
        self.destblock.push_back(call)
        return call
      else:
        call = VNCallInst.create(context=self.context, start_time=self.starttime, target=func, destroyed_handle_list=handle_list, name=node.name, loc=node.location)
        self.destblock.push_back(call)
        self.scenecontext.mark_after_call()
        return None

    def move_to_new_block(self, destblock : Block):
      # 当我们处理一个控制流结构（比如选单等），可以继续用当前的场景、解析状态时，
      # 我们使用该函数来过渡到新块
      # 原来的输出块结束后，应该先调用该函数，使新块的初始状态被确认下来，再递归处理控制流结构中的内容
      # 调用这个函数时所选的目标块必须是新建的、没有注册过状态的
      self.functioncontext.register_new_block(self, destblock)
      self.set_destblock(destblock)

    def set_destblock(self, destblock : Block):
      self.cur_terminator = None
      self.destblock = destblock
      self.starttime = destblock.get_argument('start')
      self.warningdest = destblock
      assert isinstance(self.starttime.valuetype, VNTimeOrderType)

    def run_default_terminate(self):
      # 当输入块已经没有指令后，该函数会被调用
      # 该块中没有默认的结束目标
      # 如果 convergeblock 有提供的话，我们生成一个对该块的跳转
      # 如果 convergeblock 没有的话，我们生成一个返回指令
      if self.convergeblock is not None:
        self.emit_jump_to_block_mayexisting(self.convergeblock, None)
      else:
        ret = VNReturnInst.create(context=self.context, start_time=self.starttime)
        self.destblock.push_back(ret)

    def codegen_mainloop(self):
      if self.cur_terminator is not None:
        raise PPAssertionError
      for op in self.srcregion.body.body:
        if isinstance(op, VNASTNodeBase):
          #is_originally_inblock = False
          #if self.cur_terminator is None:
          #  is_originally_inblock = True
          if new_terminator := self.visit(op):
            self.cur_terminator = new_terminator
          #if self.cur_terminator is not None and is_originally_inblock:
          #  pass
        elif isinstance(op, MetadataOp):
          cloned = op.clone()
          if self.cur_terminator is None:
            self.destblock.push_back(cloned)
          else:
            cloned.insert_before(self.cur_terminator)
          continue
        else:
          # 既不是 VNASTNodeBase 又不是 MetadataOp
          raise PPNotImplementedError()
      if self.cur_terminator is None:
        self.run_default_terminate()

    @staticmethod
    def run_codegen_for_region(codegen : VNCodeGen, namespace_tuple : tuple[str,...], basepath : str, functioncontext : VNCodeGen.FunctionCodegenContext, baseparsecontext : VNCodeGen.ParseContext, basescenecontext : VNCodeGen.SceneContext | None, srcregion : VNASTCodegenRegion, dest : Block, deststarttime : Value, convergeblock : Block | None = None, loopexitblock : Block | None = None):
      parsecontext = VNCodeGen.ParseContext.forkfrom(baseparsecontext)
      scenecontext = VNCodeGen.SceneContext.forkfrom(basescenecontext) if basescenecontext is not None else VNCodeGen.SceneContext()
      if not isinstance(deststarttime.valuetype, VNTimeOrderType):
        raise PPAssertionError
      helper = VNCodeGen._FunctionCodegenHelper(codegen=codegen, namespace_tuple=namespace_tuple, basepath=basepath, parsecontext=parsecontext, srcregion=srcregion, warningdest=dest, destblock=dest, convergeblock=convergeblock, loopexitblock=loopexitblock, scenecontext=scenecontext, functioncontext=functioncontext, starttime=deststarttime)
      helper.codegen_mainloop()

  _tr_dangling_block = TR_vn_codegen.tr("dangling_block",
    en="Block/Label {block} is not reachable from any other blocks in the function/section (i.e., it will never be executed). Please check if you missed a jump to the block.",
    zh_cn="基本块/标签 {block} 无法从同函数/章节的其他基本块/标签抵达（也就是说它永远不会被执行）。请检查是否漏掉了到该块/标签的跳转。",
    zh_hk="基本塊/標簽 {block} 無法從同函數/章節的其他基本塊/標簽抵達（也就是說它永遠不會被執行）。請檢查是否漏掉了到該塊/標簽的跳轉。",
  )

  def generate_function_body(self, srcfile : VNASTFileInfo, filecontext : ParseContext, src : VNASTFunction, dest : VNFunction):
    # 首先处理在函数体外的内容
    if len(src.prebody_md.body) > 0:
      prebody = self.get_function_prebody(dest)
      for op in src.prebody_md.body:
        if isinstance(op, MetadataOp):
          prebody.push_back(op.clone())
        else:
          if not isinstance(op, VNASTNodeBase):
            raise PPAssertionError
          self.handle_filelocal_node(file=srcfile, parsecontext=filecontext, op=op, warningdest=prebody, asmdest=prebody)
    # 然后处理函数体
    entry = dest.create_block('Entry')
    starttime = entry.get_argument('start')
    functioncontext = VNCodeGen.FunctionCodegenContext(destfunction=dest)
    VNCodeGen._FunctionCodegenHelper.run_codegen_for_region(codegen=self, namespace_tuple=self.get_file_nstuple(srcfile), basepath=srcfile.location.get_file_path(), functioncontext=functioncontext, baseparsecontext=filecontext, basescenecontext=None, srcregion=src, dest=entry, deststarttime=starttime)
    # 最后检查所有创建的基本块，看看有没有基本块没有被用上
    # （有的话大概是跳转的时候目标点名字错了）
    # 所有没内容的基本块都塞上错误信息
    dangling_blocks : list[Block] = []
    for block in functioncontext.block_dict.values():
      if block.use_empty():
        dangling_blocks.append(block)
        # self.emit_error(code='vncodegen-dangling-block', msg='Block has no user', loc=None, dest=block)
      if block.body.empty:
        unreachable = VNUnreachableInst.create(context=self.context, start_time=block.get_argument('start'), name='empty')
        block.push_back(unreachable)
    for block in dangling_blocks:
      msg = self._tr_dangling_block.format(block=block.name)
      err = ErrorOp.create(error_code='vncodegen-dangling-block', context=self.context, error_msg=StringLiteral.get(msg, self.context))
      entry.push_front(err)

  def is_name_for_narrator(self, name : str):
    if name.lower() in VNCharacterSymbol.NARRATOR_ALL_NAMES:
      return True
    return False

  def populate_assets(self):
    # 把角色、场景等信息写到输出里

    # 这些需要填好：
    # _char_parent_map : dict[VNCharacterSymbol, VNASTCharacterSymbol]
    # _char_state_matcher : dict[VNCharacterSymbol, _PartialStateMatcher]
    # _scene_parent_map : dict[VNSceneSymbol, VNASTSceneSymbol]
    # _scene_state_matcher : dict[VNSceneSymbol, _PartialStateMatcher]

    # VNASTFileInfo 下有这些：
    # namespace : OpOperand[StringLiteral] # 无参数表示没有提供（取默认情况），'/'才是根命名空间
    # functions : Block # 全是 VNASTFunction
    # assetdecls : SymbolTableRegion[VNASTAssetDeclSymbol] # 可以按名查找的资源声明
    # characters : SymbolTableRegion[VNASTCharacterSymbol] # 在该文件中正式声明的角色
    # variables : SymbolTableRegion[VNASTVariableDeclSymbol] # 在该文件中声明的变量
    # scenes : SymbolTableRegion[VNASTSceneSymbol]
    # pending_content : Block # VNASTNodeBase | MetadataOp

    # 我们先把所有资源定义的部分解析了（指 VNASTFileInfo.assetdecls），再处理对资源的引用
    # （可能在声明角色、场景时引用这些资源）
    for file in self.ast.files.body:
      if not isinstance(file, VNASTFileInfo):
        raise PPAssertionError
      nstuple = self.get_file_nstuple(file)
      ns = self.get_or_create_ns(nstuple)
      for asset in file.assetdecls:
        if not isinstance(asset, VNASTAssetDeclSymbol):
          raise PPAssertionError
        name = asset.name
        value = asset.asset.get()
        kind = asset.kind.get().value
        symb = None
        match kind:
          case VNASTAssetKind.KIND_IMAGE:
            if not isinstance(value, BaseImageLiteralExpr):
              raise PPNotImplementedError
            symb = VNConstExprAsSymbol.create(context=self.context, value=value, name=name, loc=asset.location)
          case VNASTAssetKind.KIND_AUDIO:
            if not isinstance(value, AudioAssetData):
              raise PPNotImplementedError
            symb = VNConstExprAsSymbol.create(context=self.context, value=value, name=name, loc=asset.location)
          case _:
            # 其他资源暂不支持
            raise PPNotImplementedError("TODO")
        if symb:
          ns.add_asset(symb)
    # 然后处理角色、场景声明
    for file in self.ast.files.body:
      if not isinstance(file, VNASTFileInfo):
        raise PPAssertionError
      nstuple = self.get_file_nstuple(file)
      ns = self.get_or_create_ns(nstuple)
      for scene in file.scenes:
        if not isinstance(scene, VNASTSceneSymbol):
          raise PPAssertionError
        symb = VNSceneSymbol.create(context=self.context, name=scene.name, loc=scene.location)
        matcher = _PartialStateMatcher()
        self._scene_parent_map[symb] = scene
        self._scene_state_matcher[symb] = matcher
        ns.add_scene(symb)
        for u in scene.aliases.operanduses():
          aliasname = u.value.get_string()
          alias = VNAliasSymbol.create(context=self.context, name=aliasname, target_name=symb.name, target_namespace=ns.get_namespace_string(), loc=symb.location)
          ns.add_alias(alias)
        for bg in scene.backgrounds:
          state = bg.name.split(',')
          matcher.add_valid_state(tuple(state))
          # 尝试声明背景资源
          bg_img = bg.get_value(nstuple)
          if not isinstance(bg_img, BaseImageLiteralExpr):
            raise PPNotImplementedError
          bg_entry = VNConstExprAsSymbol.create(context=self.context, value=bg_img, name=bg.name, loc=scene.location)
          symb.backgrounds.add(bg_entry)
        matcher.finish_init()

      for character in file.characters:
        if not isinstance(character, VNASTCharacterSymbol):
          raise PPAssertionError
        # 如果用户尝试定义一个已存在的角色，那么我们忽略，除非这个角色是初始化时默认创建的旁白
        obsolete_old_narrator = None
        if ch := self.resolve_character(character.name, ns.get_namespace_path(), self._global_parsecontext):
          if ch.kind.get().value == VNCharacterKind.NARRATOR:
            parentns = ch.parent_op
            if not isinstance(parentns, VNNamespace):
              raise PPAssertionError
            if parentns is ns:
              # 确保后续可以顺利添加该角色
              obsolete_old_narrator = ch
              ch.remove_from_parent()
              # 也把别名给先撤了
              for aliasname in VNCharacterSymbol.NARRATOR_ALL_NAMES:
                if alias := parentns.aliases.get(aliasname):
                  if not isinstance(alias, VNAliasSymbol):
                    raise PPAssertionError
                  if alias.target_name == ch.name and alias.target_namespace.get().get_string() == parentns.get_namespace_string():
                    alias.erase_from_parent()
          else:
            # 如果不是覆盖旁白的话就是已有的，跳过
            return
        chkind = VNCharacterKind.NORMAL if obsolete_old_narrator is None else VNCharacterKind.NARRATOR
        symb = VNCharacterSymbol.create(self.context, kind=chkind, name=character.name, loc=character.location)
        matcher = _PartialStateMatcher()
        self._char_parent_map[symb] = character
        self._char_state_matcher[symb] = matcher
        ns.add_character(symb)
        for u in character.aliases.operanduses():
          aliasname = u.value.get_string()
          alias = VNAliasSymbol.create(context=self.context, name=aliasname, target_name=symb.name, target_namespace=ns.get_namespace_string(), loc=symb.location)
          ns.add_alias(alias)
        # 如果这个角色覆盖了默认的旁白，我们在此更正旁白信息
        if obsolete_old_narrator:
          if self._global_parsecontext.narrator is obsolete_old_narrator:
            self._global_parsecontext.narrator = symb
          for aliasname in VNCharacterSymbol.NARRATOR_ALL_NAMES:
            if ns.aliases.get(aliasname) is None:
              alias = VNAliasSymbol.create(context=self.context, name=aliasname, target_name=symb.name, target_namespace=ns.get_namespace_string(), loc=symb.location)
              ns.add_alias(alias)
        # 尝试总结通用的发言名称的样式和发言内容的样式
        sayname_styles = set()
        saytext_styles = set()
        for info in character.sayinfo:
          sayname_styles.add(info.namestyle.try_get_value())
          saytext_styles.add(info.saytextstyle.try_get_value())
        if None not in sayname_styles and len(sayname_styles) == 1:
          sayname_style = next(iter(sayname_styles))
          symb.sayname_style.set_operand(0, sayname_style)
        if None not in saytext_styles and len(saytext_styles) == 1:
          saytext_style = next(iter(saytext_styles))
          symb.saytext_style.set_operand(0, saytext_style)
        # 添加立绘信息
        for sprite in character.sprites:
          # 添加立绘状态
          if not isinstance(sprite, VNASTNamespaceSwitchableValueSymbol):
            raise PPAssertionError
          state = sprite.name.split(',')
          matcher.add_valid_state(tuple(state))
          # 尝试声明立绘资源
          sprite_img = sprite.get_value(nstuple)
          if not isinstance(sprite_img, BaseImageLiteralExpr):
            raise PPNotImplementedError
          sprite_entry = VNConstExprAsSymbol.create(context=self.context, value=sprite_img, name=sprite.name, loc=character.location)
          symb.sprites.add(sprite_entry)
        # 如果有侧边头像的话把它们也加进去
        for sideimage in character.sideimages:
          if not isinstance(sideimage, VNASTNamespaceSwitchableValueSymbol):
            raise PPAssertionError
          # 这里我们不加状态
          sideimage_img = sideimage.get_value(nstuple)
          if not isinstance(sideimage_img, BaseImageLiteralExpr):
            raise PPNotImplementedError
          sideimage_entry = VNConstExprAsSymbol.create(context=self.context, value=sideimage_img, name=sideimage.name, loc=character.location)
          symb.sideimages.add(sideimage_entry)
        matcher.finish_init()

      for variable in file.variables:
        if not isinstance(variable, VNASTVariableDeclSymbol):
          raise PPAssertionError
        raise PPNotImplementedError("TODO")
    # 结束

  def run_pipeline(self):
    self.populate_assets()
    self.collect_functions()
    self.run_codegen()

  @staticmethod
  def run(ast : VNAST) -> VNModel:
    m = VNCodeGen(ast)
    m.run_pipeline()
    return m.result


