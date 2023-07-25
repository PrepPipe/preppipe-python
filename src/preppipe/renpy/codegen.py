# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import re
import dataclasses
import typing

from .ast import *
from ..vnmodel import *
from ..imageexpr import *
from ..util import nameconvert

@dataclasses.dataclass
class _FunctionCodeGenHelper:
  codename : StringLiteral = dataclasses.field(init=True, kw_only=True)
  numeric_blocks : int = 0
  local_labels : dict[str, RenPyLabelNode] = dataclasses.field(default_factory=dict)
  block_dict : dict[Block, RenPyLabelNode] = dataclasses.field(default_factory=dict)
  used_names : set[str] = dataclasses.field(default_factory=set)
  # block_order_dict : dict[Block, dict[VNInstruction, int]] = dataclasses.field(default_factory=dict) # block -> inst -> #order

  def reserve_block_name(self, block : Block) -> None:
    self.used_names.add(block.name)

  def generate_anonymous_local_label(self) -> str:
    codename = '.anon_' + str(self.numeric_blocks)
    self.numeric_blocks += 1
    while codename in self.used_names or codename in self.local_labels:
      codename = '.anon_' + str(self.numeric_blocks)
      self.numeric_blocks += 1
    return codename

  def sanitize_local_label(self, n : str) -> str:
    # 如果标签名有
    codename = nameconvert.str2identifier(n)
    if not codename.startswith('.'):
      codename = '.' + codename
    return codename

  def _create_label(self, block : Block, codename : str) -> RenPyLabelNode:
    label = RenPyLabelNode.create(block.context, codename)
    self.local_labels[codename] = label
    self.block_dict[block] = label
    return label

  def create_entry_block_label(self, block : Block, codename : str) -> RenPyLabelNode:
    return self._create_label(block, codename)

  def create_block_local_label(self, block : Block) -> RenPyLabelNode:
    # 给新遇到的这个块生成函数内的局部标签
    if len(block.name) == 0:
      # 块没有提供名字，按照数值生成它们
      codename = self.generate_anonymous_local_label()
    else:
      codename = self.sanitize_local_label(block.name)
      assert codename not in self.local_labels
    return self._create_label(block, codename)

  #def compute_inst_order(self, block : Block) -> dict[VNInstruction, int]:
    # 给块中的指令赋予一个整数表示他们的顺序（即顺序号）
    # 如果碰到指令组，则指令组内的所有 VNInstruction (去掉后端指令)也要有顺序号
  #  raise NotImplementedError()

@dataclasses.dataclass(eq=True, frozen=True)
class _RenPyCharacterInfo:
  sayername : str
  mode : str = 'adv'
  sayerstyle : TextStyleLiteral | None = None
  textstyle : TextStyleLiteral | None = None

class _RenPyCodeGenHelper:
  model : VNModel
  cur_namespace : VNNamespace
  cur_path_prefix : str
  cur_mainscript : RenPyScriptFileOp | None
  cur_toplevel_insertionpoint : RenPyNode | None
  result : RenPyModel

  # 所有的全局状态（不论命名空间）
  char_dict : collections.OrderedDict[VNCharacterSymbol, collections.OrderedDict[_RenPyCharacterInfo, RenPyDefineNode]]
  canonical_char_dict : collections.OrderedDict[VNCharacterSymbol, RenPyDefineNode]
  func_dict : collections.OrderedDict[VNFunction, _FunctionCodeGenHelper]
  global_name_dict : collections.OrderedDict # 避免命名冲突的全局名称字典
  imspec_dict : collections.OrderedDict[Value, tuple[StringLiteral, ...]]
  audiospec_dict : collections.OrderedDict[Value, StringLiteral]
  anon_asset_index_dict : collections.OrderedDict[str, int] # parent dir -> anon index
  numeric_image_index : int

  # 辅助信息
  CODEGEN_MATCH_TREE : typing.ClassVar[dict] = {}

  def __init__(self, model : VNModel) -> None:
    self.model = model
    self.cur_namespace = None # type: ignore
    self.cur_path_prefix = None # type: ignore
    self.cur_mainscript = None
    self.cur_toplevel_insertionpoint = None
    self.result = None # type: ignore
    self.char_dict = collections.OrderedDict()
    self.func_dict = collections.OrderedDict()
    self.canonical_char_dict = collections.OrderedDict()
    self.global_name_dict = collections.OrderedDict()
    self.imspec_dict = collections.OrderedDict()
    self.audiospec_dict = collections.OrderedDict()
    self.anon_asset_index_dict = collections.OrderedDict()
    self.numeric_image_index = 0

    if len(_RenPyCodeGenHelper.CODEGEN_MATCH_TREE) == 0:
      _RenPyCodeGenHelper.init_matchtable()

  @property
  def context(self) -> Context:
    return self.model.context

  def get_codegen_path(self, n: VNNamespace) -> str:
    return n.name

  def get_unique_global_name(self, displayname : str) -> str:
    codename = nameconvert.str2identifier(displayname)
    if codename in self.global_name_dict:
      # 加一个后缀来避免命名冲突
      codename_base = codename + '_'
      num = 1
      codename = codename_base + str(num)
      while codename in self.global_name_dict:
        num += 1
        codename = codename_base + str(num)
    return codename

  #def handle_device(self, dev : VNDeviceSymbol):
    # 目前什么都不干
    #pass

  def handle_all_devices(self):
    # 目前什么都不干
    pass

  def handle_all_values(self):
    # 目前什么都不干
    pass

  def label_all_functions(self):
    # 确定每个函数的入口标签，便于在其他函数体中生成对该函数的调用
    for func in self.cur_namespace.functions:
      displayname = func.name
      assert len(displayname) > 0
      codename_l = func.codename.try_get_value()
      if codename_l is None:
        codename = self.get_unique_global_name(displayname)
        codename_l = StringLiteral.get(codename, self.context)
      else:
        codename = codename_l.get_string()
        if codename_l in self.global_name_dict:
          raise RuntimeError("Global name conflict: \"" + codename + '"')
      self.global_name_dict[codename] = func
      self.func_dict[func] = _FunctionCodeGenHelper(codename = codename_l)

  def handle_asset(self, asset : VNConstExprAsSymbol):
    raise NotImplementedError("TODO")

  def _populate_imspec_from_assetdecl(self, basename : str, symbolname : str, prefix : str | None = None):
    imspec_list = [nameconvert.str2identifier(v) for v in symbolname.split(',') if len(v) > 0]
    imspec_list.insert(0, basename)
    if prefix:
      imspec_list.insert(0, prefix)
    return tuple(imspec_list)

  def handle_character(self, character : VNCharacterSymbol):
    # 为角色生成 character 对象
    ms = self.get_mainscript()
    displayname = character.name
    if len(displayname) == 0:
      raise RuntimeError("Empty display name for character")
    codename = ''
    if v := character.codename.try_get_value():
      codename = v.get_string()
      if not self.check_identifier(codename):
        raise RuntimeError('Invalid codename specified: "' + codename + '"')
      if codename in self.global_name_dict:
        raise RuntimeError('Duplicated codename: "' + codename + '"')
    else:
      codename = self.get_unique_global_name(displayname)
    # 如果是旁白的话，displayname 必须是 None
    if character.kind.get().value == VNCharacterKind.NARRATOR:
      displayname = None
    definenode, charexpr = RenPyDefineNode.create_character(self.context, varname=codename, displayname=displayname)
    ms.body.push_back(definenode)

    # charexpr.image.set_operand(0, StringLiteral.get(codename, self.context))
    # 如果这是旁白且我们并没有覆盖任何设置，就把这个结点去掉
    is_change_made = False
    match character.kind.get().value:
      case VNCharacterKind.NORMAL | VNCharacterKind.CROWD:
        pass
      case VNCharacterKind.NARRATOR:
        # 如果是 narrator，那我们在这里覆盖掉默认的 narrator 定义
        codename = 'narrator'
        if codename in self.global_name_dict:
          raise RuntimeError('Duplicated narrator definition')
      case VNCharacterKind.SYSTEM:
        # 默认用红字体
        charexpr.who_color.set_operand(0, StringLiteral.get('#800000', self.context))
        charexpr.what_color.set_operand(0, StringLiteral.get('#600000', self.context))
    sayerstyle = None
    if sayerstyle := character.sayname_style.try_get_value():
      self._populate_renpy_characterexpr_from_sayerstyle(charexpr, sayerstyle)
      is_change_made = True
    textstyle = None
    if textstyle := character.saytext_style.try_get_value():
      self._populate_renpy_characterexpr_from_textstyle(charexpr, textstyle)
      is_change_made = True
    for img in character.sprites:
      self.try_set_imspec_for_asset(img.get_value(), self._populate_imspec_from_assetdecl(codename, img.name))
      is_change_made = True
    for img in character.sideimages:
      self.try_set_imspec_for_asset(img.get_value(), self._populate_imspec_from_assetdecl(codename + '_side', img.name))
      is_change_made = True
    # 暂时不支持其他项
    if character.kind.get().value == VNCharacterKind.NARRATOR:
      if not is_change_made:
        definenode.erase_from_parent()
        return
    self.global_name_dict[codename] = definenode
    self.canonical_char_dict[character] = definenode
    if character.kind.get().value != VNCharacterKind.NARRATOR:
      assert displayname is not None
      char_dict = collections.OrderedDict()
      std_char_info = _RenPyCharacterInfo(sayername=displayname, sayerstyle=sayerstyle, textstyle=textstyle)
      char_dict[std_char_info] = definenode
      self.char_dict[character] = char_dict

  def handle_scene(self, scene : VNSceneSymbol):
    scenename = nameconvert.str2identifier(scene.name)
    for bg in scene.backgrounds:
      self.try_set_imspec_for_asset(bg.get_value(), self._populate_imspec_from_assetdecl(scenename, bg.name, 'bg'))
    # 目前不需要其他操作
    return

  def get_terminator(self, block : Block) -> VNTerminatorInstBase:
    terminator = block.body.back
    assert isinstance(terminator, VNTerminatorInstBase)
    return terminator

  def emit_expr(self, v : Value, helper : _FunctionCodeGenHelper) -> RenPyASMExpr:
    if isinstance(v, BoolLiteral):
      if v.value:
        return RenPyASMExpr.create(self.context, asm='True')
      else:
        return RenPyASMExpr.create(self.context, asm='False')
    raise NotImplementedError("Unhandled expr type " + type(v).__name__)

  def gen_branch(self, terminator : VNBranchInst, helper : _FunctionCodeGenHelper, label : RenPyLabelNode):
    if terminator.get_num_conditional_branch() == 0:
      target = terminator.get_default_branch_target()
      dest_label = helper.block_dict[target]
      label.body.push_back(RenPyJumpNode.create(self.context, dest_label.codename.get()))
    else:
      ifchain = RenPyIfNode.create(self.context)
      label.body.push_back(ifchain)
      for i in range(0, terminator.get_num_conditional_branch()):
        target, cond = terminator.get_conditional_branch_tuple(i)
        dest_label = helper.block_dict[target]
        assert isinstance(cond.valuetype, BoolType)
        condexpr = self.emit_expr(cond, helper)
        new_block = ifchain.add_branch(condexpr)
        new_block.push_back(RenPyJumpNode.create(self.context, dest_label.codename.get()))
      target = terminator.get_default_branch_target()
      dest_label = helper.block_dict[target]
      new_block = ifchain.add_branch(None)
      new_block.push_back(RenPyJumpNode.create(self.context, dest_label.codename.get()))

  def gen_menu(self, terminator : VNMenuInst, helper : _FunctionCodeGenHelper, label : RenPyLabelNode):
    menu = RenPyMenuNode.create(self.context)
    label.body.push_back(menu)
    num_options = terminator.text_list.get_num_operands()
    for i in range(0, num_options):
      text = terminator.text_list.get_operand(i)
      cond = terminator.condition_list.get_operand(i)
      target = terminator.target_list.get_operand(i)
      if isinstance(cond, BoolLiteral) and cond.value:
        cond = None
      else:
        cond = self.emit_expr(cond, helper)
      dest_label = helper.block_dict[target]
      item = RenPyMenuItemNode.create(self.context, label = text, condition = cond)
      menu.items.push_back(item)
      item.body.push_back(RenPyJumpNode.create(self.context, dest_label.codename.get()))

  def gen_terminator(self, terminator : VNTerminatorInstBase, helper : _FunctionCodeGenHelper, label : RenPyLabelNode):
    assert label.body.body.empty
    if isinstance(terminator, VNBranchInst):
      self.gen_branch(terminator, helper, label)
    elif isinstance(terminator, VNMenuInst):
      self.gen_menu(terminator, helper, label)
    elif isinstance(terminator, VNReturnInst):
      label.body.push_back(RenPyReturnNode.create(self.context))
    elif isinstance(terminator, VNTailCallInst):
      target_func = terminator.target.get()
      target_codename = self.func_dict[target_func].codename
      label.body.push_back(RenPyJumpNode.create(self.context, target_codename))
    elif isinstance(terminator, VNEndingInst):
      label.body.push_back(RenPyCallNode.create(self.context, label='__preppipe_ending__', arguments='ending_name="' + terminator.ending.get() + '"'))
    else:
      raise NotImplementedError("Unimplemented terminator type " + type(terminator).__name__)

  # 在这里初始化指令转换表
  # 每个生成函数都应该是 def gen_XXX(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode
  # instrs 是匹配到的 VNInstruction, insertbefore 是应该插入的位置，返回值是生成的第一个指令，给出后续指令的生成位置（插在前面）
  # 进行匹配时，如果有含多个指令的模板（比如Say+Wait），我们只会在中间的指令所产出的时间没有使用者的情况下才会匹配
  # （比如如果有 Say --> Show 和 Say --> Wait 并存，那么 Wait 会单独匹配而不会被并入 Say+Wait ，因为有另一个 Show 在使用 Say 的结束时间）
  # 如果一个指令有多个
  # 键值都是类型；可以按需要添加 RenPy 辅助生成的类（比如可以定义一个新的 InstructionGroup, 先用一个转换找到特定指令（比如可以共用 With 从句的 Show）并把它们替换为新的类型，然后在这里定义细则）
  @staticmethod
  def init_matchtable():
    _RenPyCodeGenHelper.CODEGEN_MATCH_TREE = {
      VNWaitInstruction : {
        VNSayInstructionGroup: _RenPyCodeGenHelper.gen_say_wait,
        None: _RenPyCodeGenHelper.gen_wait,
      },
      VNSayInstructionGroup: _RenPyCodeGenHelper.gen_say_nowait,
      VNSceneSwitchInstructionGroup : _RenPyCodeGenHelper.gen_sceneswitch,
      VNCreateInst : _RenPyCodeGenHelper.gen_create_put,
      VNPutInst : _RenPyCodeGenHelper.gen_create_put,
      VNModifyInst : _RenPyCodeGenHelper.gen_modify,
      VNRemoveInst : _RenPyCodeGenHelper.gen_remove,
      VNCallInst : _RenPyCodeGenHelper.gen_call,
      VNBackendInstructionGroup : _RenPyCodeGenHelper.gen_renpy_asm,
    }

  def collect_say_text(self, src : OpOperand) -> list[Value]:
    result = []
    for u in src.operanduses():
      v = u.value
      if isinstance(v, (StringLiteral, TextFragmentLiteral)):
        result.append(v)
        continue
      if isinstance(v, VNValueSymbol):
        raise NotImplementedError("Currently not supporting VNValueSymbol codegen")
      raise NotImplementedError("Unexpected value type for text: " + type(v).__name__)
    return result

  def _gen_say_impl(self, say : VNSayInstructionGroup, wait : VNWaitInstruction | None, insert_before : RenPyNode) -> RenPyNode:
    sayer = say.sayer.try_get_value()
    who = self.canonical_char_dict[sayer] if sayer is not None and sayer in self.canonical_char_dict else None
    what = []
    mode = 'adv'
    embed_voice = None
    # 由于我们需要尝试在读取发言内容之后再找最合适的 RenPyCharacterExpr，
    # 这里我们先声明用来找发言者信息的变量
    sayername_str = ''
    sayerstyle = None
    is_sayername_specified = False
    for op in say.body.body:
      assert isinstance(op, VNInstruction)
      if isinstance(op, VNPutInst):
        # 首先根据设备类型决定
        # 我们暂不支持侧边头像
        dev = op.device.get()
        assert isinstance(dev, VNDeviceSymbol)
        match dev.get_std_device_kind():
          case VNStandardDeviceKind.O_SAY_NAME_TEXT:
            # 我们以后再支持在名称上用变量等内容
            # 现在就假设只有一个 StringLiteral
            # 暂时不支持给旁白加发言名
            assert sayer is not None
            name_data = self.collect_say_text(op.content)
            assert len(name_data) == 1
            sayername = name_data[0]
            sayerstyle = None
            if isinstance(sayername, StringLiteral):
              sayername_str = sayername.get_string()
            elif isinstance(sayername, TextFragmentLiteral):
              sayerstyle = sayername.style
              sayername_str = sayername.get_string()
            else:
              raise RuntimeError("Unexpected sayername type: " + str(type(sayername)))
            is_sayername_specified = True
          case VNStandardDeviceKind.O_SAY_TEXT_TEXT:
            what = self.collect_say_text(op.content)
            if parent_dev := dev.get_parent_device():
              match parent_dev.get_std_device_kind():
                case VNStandardDeviceKind.N_SCREEN_SAY_ADV:
                  mode='adv'
                case VNStandardDeviceKind.N_SCREEN_SAY_NVL:
                  mode='nvl'
                case _:
                  pass
          case VNStandardDeviceKind.O_VOICE_AUDIO:
            embed_voice = op.content.get()
          # 忽略其他不支持的设备
          case _:
            continue
    # 扫完所有的发言内容，确定一个最合适的基础样式
    single_text_style = None # 最常见的应该是只有单个样式
    is_multiple_styles = False
    is_raw_string_found = False # 只要有一个原始字符串，我们就认为没有样式
    conflicting_attrs : set[TextAttribute] = set()
    consistent_attrs : dict[TextAttribute, typing.Any] = {}
    for v in what:
      if isinstance(v, StringLiteral):
        is_raw_string_found = True
        break
      if isinstance(v, TextFragmentLiteral):
        curstyle = v.style
        if single_text_style is None:
          if not is_multiple_styles:
            single_text_style = curstyle
        else:
          if single_text_style is not curstyle:
            is_multiple_styles = True
            single_text_style = None
        for k, v in curstyle.value:
          if k in conflicting_attrs:
            continue
          if k in consistent_attrs:
            if consistent_attrs[k] != v:
              conflicting_attrs.add(k)
              del consistent_attrs[k]
          else:
            consistent_attrs[k] = v
        # 当前文本片段处理完毕
        continue
      # 暂时假设其他内容不管格式
    # 所有内容处理完毕
    fallback_text_style = sayer.saytext_style.try_get_value() if sayer is not None else None
    if is_raw_string_found:
      final_text_style = None
    elif single_text_style is not None:
      final_text_style = single_text_style
    elif len(consistent_attrs) == 0:
      final_text_style = fallback_text_style
    else:
      # 目前只支持颜色
      if TextAttribute.TextColor in consistent_attrs:
        final_text_style = TextStyleLiteral.get({TextAttribute.TextColor : consistent_attrs[TextAttribute.TextColor]}, self.context)
      else:
        final_text_style = fallback_text_style
    if is_sayername_specified:
      who = self.get_renpy_character(sayer, sayername=sayername_str, mode=mode, sayerstyle=sayerstyle, textstyle=final_text_style)
    # 根据最终的效果去调整现在 what 中的内容
    final_what = what
    if final_text_style is not None:
      final_what = []
      for v in what:
        if isinstance(v, TextFragmentLiteral):
          curstyle = v.style
          if diff := TextStyleLiteral.get_subtracted(final_text_style, curstyle):
            newvalue = TextFragmentLiteral.get(self.context, v.content, diff)
          else:
            # 这种情况下时整个文本的样式与基础样式相符，只用字符串就够了
            newvalue = v.content
          final_what.append(newvalue)
        else:
          final_what.append(v)
    result = RenPySayNode.create(self.context, who=who, what=final_what)
    if wait is None:
      result.interact.set_operand(0, BoolLiteral.get(False, self.context))
    if sayid := say.sayid.try_get_value():
      result.identifier.set_operand(0, sayid)
    result.insert_before(insert_before)
    if embed_voice is not None:
      voicenode = RenPyVoiceNode.create(self.context, self.get_audiospec(embed_voice, VNStandardDeviceKind.O_VOICE_AUDIO))
      voicenode.insert_before(result)
    return result

  def gen_say_wait(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    assert len(instrs) == 2
    say = instrs[1]
    wait = instrs[0]
    assert isinstance(say, VNSayInstructionGroup)
    assert isinstance(wait, VNWaitInstruction)
    return self._gen_say_impl(say, wait, insert_before)

  def gen_say_nowait(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    assert len(instrs) == 1
    say = instrs[0]
    assert isinstance(say, VNSayInstructionGroup)
    return self._gen_say_impl(say, None, insert_before)

  def gen_wait(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    assert len(instrs) == 1
    result = RenPyASMNode.create(self.context, asm=StringLiteral.get('pause', self.context))
    result.insert_before(insert_before)
    return result

  def _get_handle_value_and_device(self, handlein : Value) -> tuple[Value, VNDeviceSymbol]:
    assert isinstance(handlein, (VNCreateInst, VNModifyInst, BlockArgument))
    if isinstance(handlein, BlockArgument):
      raise RuntimeError('Handles from block arguments not supported yet')
    if isinstance(handlein, VNCreateInst):
      value = handlein.content.get()
    elif isinstance(handlein, VNModifyInst):
      value = handlein.content.get()
    else:
      raise RuntimeError('Should not happen')
    rootdev = None
    curhandle = handlein
    while not isinstance(curhandle, VNCreateInst):
      assert isinstance(curhandle, VNModifyInst)
      curhandle = curhandle.handlein.get()
    rootdev = curhandle.device.get()
    return (value, rootdev)

  def gen_sceneswitch(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    assert len(instrs) == 1
    sceneswitch = instrs[0]
    assert isinstance(sceneswitch, VNSceneSwitchInstructionGroup)
    imspec = ''
    transition = None
    # 我们需要做这些：
    # 1. 找到向背景设备写入的create/put，生成背景的 impsec
    # 2. 对所有剩下的创建类的指令，对它们单独做生成
    top_insert_place = None
    for op in sceneswitch.body.body:
      assert isinstance(op, VNInstruction)
      is_handled = False
      if isinstance(op, VNPlacementInstBase):
        assert isinstance(op, (VNCreateInst, VNPutInst))
        dev = op.device.get()
        if dev.get_std_device_kind() == VNStandardDeviceKind.O_BACKGROUND_DISPLAY:
          is_handled = True
          imspec = self.get_impsec(op.content.get(), user_hint=VNStandardDeviceKind.O_BACKGROUND_DISPLAY)
          transition = op.transition.try_get_value()
      elif isinstance(op, VNRemoveInst):
        # 如果是前景、背景内容的话就不需要额外操作了，包含在 scene 命令里了
        removevalue, rootdev = self._get_handle_value_and_device(op.handlein.get())
        match rootdev.get_std_device_kind():
          case VNStandardDeviceKind.O_BACKGROUND_DISPLAY | VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
            is_handled = True
          case _:
            pass

      if not is_handled:
        # 在这里就地生成
        match_result = self.CODEGEN_MATCH_TREE[type(op)]
        if isinstance(match_result, dict):
          match_result = match_result[None]
        genresult = match_result(self, [op], insert_before)
        if top_insert_place is None:
          top_insert_place = genresult
    result = RenPySceneNode.create(self.context, imspec=imspec)
    if transition is not None:
      if img_transition := self.resolve_displayable_transition(transition):
        withnode = RenPyWithNode.create(self.context, expr=img_transition)
        result.with_.set_operand(0, withnode)
        result.body.push_back(withnode)
    if top_insert_place is None:
      top_insert_place = insert_before
    result.insert_before(top_insert_place)
    return result

  def _resolve_transition(self, transition : Value) -> tuple[str|None, tuple[decimal.Decimal, decimal.Decimal] | None]:
    renpy_displayable_transition = None
    renpy_audio_transition = None # tuple[Decimal, Decimal] : <fadein, fadeout>
    if transition is not None:
      if defaulttransition := VNDefaultTransitionType.get_default_transition_type(transition):
        match defaulttransition:
          case VNDefaultTransitionType.DT_NO_TRANSITION:
            # 保持 None 的状态
            pass
          case VNDefaultTransitionType.DT_IMAGE_SHOW | VNDefaultTransitionType.DT_IMAGE_HIDE | VNDefaultTransitionType.DT_IMAGE_MODIFY:
            renpy_displayable_transition = "dissolve"
          case VNDefaultTransitionType.DT_IMAGE_MOVE:
            renpy_displayable_transition = "move"
          case VNDefaultTransitionType.DT_BACKGROUND_SHOW | VNDefaultTransitionType.DT_BACKGROUND_HIDE | VNDefaultTransitionType.DT_BACKGROUND_CHANGE:
            renpy_displayable_transition = "fade"
          case VNDefaultTransitionType.DT_SPRITE_SHOW | VNDefaultTransitionType.DT_SPRITE_HIDE:
            renpy_displayable_transition = "dissolve"
          case VNDefaultTransitionType.DT_SPRITE_MOVE:
            renpy_displayable_transition = "move"
          case VNDefaultTransitionType.DT_BGM_CHANGE:
            renpy_audio_transition = (VNAudioFadeTransitionExpr.DEFAULT_FADEIN, VNAudioFadeTransitionExpr.DEFAULT_FADEOUT)
          case _:
            raise NotImplementedError("Unhandled default transition kind")
      elif isinstance(transition, VNBackendDisplayableTransitionExpr):
        if transition.backend.get_string().lower() == 'renpy':
          renpy_displayable_transition = transition.expression.get_string()
        else:
          return self._resolve_transition(transition.fallback)
      elif isinstance(transition, VNAudioFadeTransitionExpr):
        renpy_audio_transition = (transition.fadein.value, transition.fadeout.value)
      else:
        # TODO
        pass
    return (renpy_displayable_transition, renpy_audio_transition)

  def resolve_displayable_transition(self, transition : Value) -> str | None:
    renpy_displayable_transition, renpy_audio_transition = self._resolve_transition(transition)
    return renpy_displayable_transition

  def resolve_audio_transition(self, transition : Value) -> tuple[decimal.Decimal, decimal.Decimal] | None:
    renpy_displayable_transition, renpy_audio_transition = self._resolve_transition(transition)
    return renpy_audio_transition

  def _add_audio_transition(self, transition : Value, play : RenPyPlayNode):
    if audio_transition := self.resolve_audio_transition(transition):
      fadein, fadeout = audio_transition
      play.fadein.set_operand(0, FloatLiteral.get(fadein, self.context))
      play.fadeout.set_operand(0, FloatLiteral.get(fadeout, self.context))

  def _add_image_transition(self, transition : Value, node : RenPyShowNode | RenPyHideNode):
    if img_transition := self.resolve_displayable_transition(transition):
      withnode = RenPyWithNode.create(self.context, img_transition)
      node.with_.set_operand(0, withnode)
      node.body.push_back(withnode)

  def gen_create_put(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    # VNCreateInst/VNPutInst
    assert len(instrs) == 1
    instr = instrs[0]
    assert isinstance(instr, VNPlacementInstBase)
    content = instr.content.get()
    device : VNDeviceSymbol = instr.device.get()
    # placeat : SymbolTableRegion
    devkind = device.get_std_device_kind()
    if devkind is None:
      # 暂不支持
      return insert_before
    match devkind:
      case VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
        # 放置在前景，用 show
        imspec = self.get_impsec(content, user_hint=devkind)
        show = RenPyShowNode.create(context=self.context, imspec=imspec)
        if transition := instr.transition.try_get_value():
          self._add_image_transition(transition, show)
        show.insert_before(insert_before)
        return show
      case VNStandardDeviceKind.O_SE_AUDIO:
        # 音效，用 play
        audiospec = self.get_audiospec(content, devkind)
        play = RenPyPlayNode.create(context=self.context, channel=RenPyPlayNode.CHANNEL_SOUND, audiospec=audiospec)
        if transition := instr.transition.try_get_value():
          self._add_audio_transition(transition, play)
        play.insert_before(insert_before)
        return play
      case VNStandardDeviceKind.O_BGM_AUDIO:
        # 背景音乐，用 play
        audiospec = self.get_audiospec(content, devkind)
        play = RenPyPlayNode.create(context=self.context, channel=RenPyPlayNode.CHANNEL_MUSIC, audiospec=audiospec)
        if transition := instr.transition.try_get_value():
          self._add_audio_transition(transition, play)
        play.insert_before(insert_before)
        return play
      case VNStandardDeviceKind.O_SAY_NAME_TEXT | VNStandardDeviceKind.O_SAY_TEXT_TEXT | VNStandardDeviceKind.O_BACKGROUND_DISPLAY | VNStandardDeviceKind.O_VOICE_AUDIO:
        # 这些都应该在特定的指令组中特殊处理，不应该在这里处理
        raise RuntimeError('Should not happen')
      case _:
        # 暂不支持
        return insert_before

  def gen_modify(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    assert len(instrs) == 1
    instr = instrs[0]
    assert isinstance(instr, VNModifyInst)
    modifyvalue, rootdev = self._get_handle_value_and_device(instr.handlein.get())
    devkind = rootdev.get_std_device_kind()
    match devkind:
      case VNStandardDeviceKind.O_BACKGROUND_DISPLAY | VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
        assert isinstance(modifyvalue.valuetype, ImageType)
        remove_imspec = self.get_impsec(modifyvalue, devkind)
        newvalue = instr.content.get()
        new_imspec = self.get_impsec(newvalue, devkind)
        show = RenPyShowNode.create(context=self.context, imspec=new_imspec)
        show.insert_before(insert_before)
        if transition := instr.transition.try_get_value():
          self._add_image_transition(transition, show)
        new_insert_point = show
        if remove_imspec[0] != new_imspec[0]:
          # 只有第一项不一样时才要 hide
          hide = RenPyHideNode.create(context=self.context, imspec=remove_imspec)
          hide.insert_before(show)
          new_insert_point = hide
        return new_insert_point
      case _:
        raise NotImplementedError("TODO")
    return insert_before

  def gen_remove(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    # VNRemoveInst
    assert len(instrs) == 1
    instr = instrs[0]
    assert isinstance(instr, VNRemoveInst)
    removevalue, rootdev = self._get_handle_value_and_device(instr.handlein.get())
    if kind := rootdev.get_std_device_kind():
      match kind:
        case VNStandardDeviceKind.O_BACKGROUND_DISPLAY | VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
          imspec = self.get_impsec(removevalue, kind)
          hide = RenPyHideNode.create(context=self.context, imspec=imspec)
          hide.insert_before(insert_before)
          if transition := instr.transition.try_get_value():
            self._add_image_transition(transition, hide)
          return hide
        case VNStandardDeviceKind.O_BGM_AUDIO:
          stop = RenPyStopNode.create(context=self.context,channel=RenPyPlayNode.CHANNEL_MUSIC)
          stop.insert_before(insert_before)
          return stop
        case VNStandardDeviceKind.O_SE_AUDIO:
          stop = RenPyStopNode.create(context=self.context,channel=RenPyPlayNode.CHANNEL_SOUND)
          stop.insert_before(insert_before)
          return stop
        case _:
          pass
    # 如果不是标准设备的话暂不支持，直接忽略
    return insert_before

  def gen_call(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    callee = instrs[0].target.get()
    calleelabel = self.func_dict[callee].codename
    result = RenPyCallNode.create(self.context, label = calleelabel)
    result.insert_before(insert_before)
    return result

  def gen_renpy_asm(self, instrs : list[VNInstruction], insert_before : RenPyNode) -> RenPyNode:
    group = instrs[0]
    assert isinstance(group, VNBackendInstructionGroup)
    firstinstr = None
    for op in group.body.body:
      if isinstance(op, (MetadataOp, RenPyNode)):
        cloned = op.clone()
        cloned.insert_before(insert_before)
        if firstinstr is None and isinstance(op, RenPyNode):
          firstinstr = cloned
    return firstinstr if firstinstr is not None else insert_before

  def match_instr_patterns(self, finishtime : Value, blocktime : Value) -> tuple[list[VNInstruction], typing.Callable[[typing.Any, list[VNInstruction], RenPyNode], RenPyNode]]:
    assert isinstance(finishtime, OpResult) and isinstance(finishtime.valuetype, VNTimeOrderType)
    cur_match_dict = _RenPyCodeGenHelper.CODEGEN_MATCH_TREE
    instrs = []
    while True:
      end_instr = finishtime.parent
      assert isinstance(end_instr, VNInstruction)
      instrs.append(end_instr)
      match_type = type(end_instr)
      if match_type not in cur_match_dict:
        if None not in cur_match_dict:
          raise RuntimeError('Codegen for instr type not supported yet: ' + match_type.__name__)
        match_result = cur_match_dict[None]
      else:
        match_result = cur_match_dict[match_type]
      if isinstance(match_result, dict):
        cur_match_dict = match_result
        finishtime = end_instr.get_start_time()
        # 遇到以下三种情况时我们停止匹配：
        # 1. 已经到块的开头
        # 2. 前一个指令是上一步的类似等待的指令
        # 3. 除了当前匹配到的指令外，前一个指令的输出时间有其他使用者（我们不能把这个输出时间抢走）
        if finishtime is blocktime or self.is_waitlike_instr(finishtime.parent):
          return (instrs, match_result[None])
        for u in finishtime.uses:
          user_instr = u.user.parent
          if user_instr is not end_instr and user_instr.try_get_parent_group() is not end_instr:
            # 情况三
            return (instrs, match_result[None])
        # 否则我们继续匹配
        continue
      return (instrs, match_result)

  def is_waitlike_instr(self, instr : VNInstruction) -> bool:
    if isinstance(instr, VNWaitInstruction):
      return True
    return False

  def codegen_block(self, b : Block, helper : _FunctionCodeGenHelper):
    # 从末指令开始从后往前，用查表的方式找到对应的函数进行指令生成
    terminator = self.get_terminator(b)
    label = helper.block_dict[b]
    self.gen_terminator(terminator, helper, label)
    if terminator is b.body.front:
      return

    cur_srcpos = terminator # Block @ VNModel
    cur_insertpos = label.body.body.front # RenPyNode @ RenPyLabelNode
    #pos_dict = {orders[terminator] : cur_insertpos}
    block_start = b.get_argument('start')
    # 下面这个是处理该块的主循环
    visited_instrs = set()

    while True:
      if cur_srcpos is b.body.front:
        return
      cur_srcpos = cur_srcpos.get_prev_node()
      if isinstance(cur_srcpos, VNInstruction):
        if cur_srcpos in visited_instrs:
          continue
        instrs, gen = self.match_instr_patterns(cur_srcpos.get_finish_time(), block_start)
        cur_insertpos = gen(self, instrs, cur_insertpos)
        visited_instrs.update(instrs)
      else:
        if isinstance(cur_srcpos, MetadataOp):
          cloned = cur_srcpos.clone()
          cloned.insert_before(cur_insertpos)
          cur_insertpos = cloned
        else:
          raise RuntimeError('Unexpected instruction kind: ' + type(cur_srcpos).__name__)

  def handle_function(self, func : VNFunction):
    # 在这里，函数内的基本块应当已按照拓扑排序顺序排列
    # 第一步：遍历所有块，生成局部标签
    #     <TODO> 如果有跳转指令取句柄值传给另一个块的话，给这些句柄值一个唯一的标签
    # 第二步：在每个标签（块）中进行生成
    # 第三步：使用模式匹配来还原 if, while 这种控制流命令
    # 指令生成期间，我们需要跟踪每个（命名）资源的生存区间，如果当前已经有使用者了
    # （比如某物件的图片在屏幕上出现两次，第二个显示命令处会发现该图片已有一个使用中的句柄）
    # 则我们需要安排一个不一样的句柄（show 命令中的 as 参数）

    # 呃。。首先把函数前的错误信息给加上
    prebody : Block | None = None
    postbody : Block | None = None
    for b in func.lost.blocks:
      if b.name == VNFunction.NAME_PREBODY:
        prebody = b
      elif b.name == VNFunction.NAME_POSTBODY:
        postbody = b
      else:
        raise PPNotImplementedError("Unexpected lost block name")
    def write_md_block(block : Block):
      # 在这里将元数据块中的所有内容搬到输出
      # 唯一要变动的是 ErrorOp, 如果此时不变的话，它们在之后导出时会变为发言，这在标签外会出错
      # 我们把这些 ErrorOp 转为注释
      # 如果是全局的 ASM 则按照要求输出
      # 虽然我们可以保留 MetadataOp 直到输出时，不过他们的输出会有所不同
      destblock = self.get_mainscript().body
      def copy_and_add(op : Operation):
        if isinstance(op, ErrorOp):
          code = op.error_code
          msg = op.error_message.get_string()
          content = msg + ' (' + code + ')'
          content_rows = content.split('\n')
          asm_rows = [StringLiteral.get('# ' + v, self.context) for v in content_rows]
          asm = StringListLiteral.get(self.context, asm_rows)
          node = RenPyASMNode.create(context=self.context, asm=asm, name=op.name, loc=op.location)
          destblock.push_back(node)
          return
        destblock.push_back(op.clone())
      for op in block.body:
        # 先对类似 ASM 这样的内容特判
        if isinstance(op, VNBackendInstructionGroup):
          for childop in op.body.body:
            if isinstance(childop, (MetadataOp, RenPyNode)):
              copy_and_add(childop)
          continue
        if not isinstance(op, MetadataOp):
          raise PPAssertionError
        copy_and_add(op)
    if prebody is not None:
      write_md_block(prebody)

    if func.body.blocks.size == 0:
      if postbody is not None:
        write_md_block(postbody)
      return

    helper = self.func_dict[func]

    # 第一步
    # 由于某些块已经有名称，我们把所有的块走两遍：
    # 1. 第一遍把已经有名称的块加进去（所有的局部名冲突是错误），
    # 2. 第二遍把还没有名称的块放进去（局部名冲突会使得名称重新生成）
    for b in func.body.blocks:
      terminator = self.get_terminator(b)
      #if len(terminator.get_passed_handles()) > 0:
      #  raise RuntimeError('Terminator passing handles are not supported yet (report to the programmer)')
      if len(b.name) > 0:
        helper.reserve_block_name(b)

    entry_block = func.get_entry_block()
    entry_label = helper.create_entry_block_label(entry_block, helper.codename.get_string())
    self.get_mainscript().body.push_back(entry_label)
    if self.cur_toplevel_insertionpoint is None:
      self.cur_toplevel_insertionpoint = entry_label

    for b in func.body.blocks:
      if b is entry_block:
        continue
      label = helper.create_block_local_label(b)
      self.get_mainscript().body.push_back(label)

    # 第二步
    for b in func.body.blocks:
      self.codegen_block(b, helper)

    if entry := func.get_entry_point():
      if entry != 'main':
        raise RuntimeError('Unrecognized entry point')
      if self.func_dict[func].codename.get_string() != 'start':
        start = RenPyLabelNode.create(self.context, codename='start')
        self.insert_at_top(start)
        start.body.push_back(RenPyJumpNode.create(self.context, target=self.func_dict[func].codename))

    # 第三步暂时不做
    if postbody is not None:
      write_md_block(postbody)

  def check_identifier(self, idstr : str, is_label : bool = False):
    if not is_label:
      return re.match(r'''^[a-zA-Z]+[0-9A-Za-z_]*$''', idstr) is not None
    return re.match(r'''^([a-zA-Z]+[0-9A-Za-z_]*)?.?[a-zA-Z]+[0-9A-Za-z_]*$''', idstr) is not None

  def generate_varname(self, parentvar : str) -> str:
    suffix = 1
    curname = parentvar + '_' + str(suffix)
    while curname in self.global_name_dict:
      suffix += 1
      curname = parentvar + '_' + str(suffix)
    return curname

  def _populate_renpy_characterexpr_from_sayerstyle(self, charexpr : RenPyCharacterExpr, sayerstyle : TextStyleLiteral):
    for style, v in sayerstyle.value:
      match style:
        case TextAttribute.TextColor:
          assert isinstance(v, Color)
          charexpr.who_color.set_operand(0, StringLiteral.get(v.get_string(), self.context))
        case _:
          # TODO
          pass
  def _populate_renpy_characterexpr_from_textstyle(self, charexpr : RenPyCharacterExpr, textstyle : TextStyleLiteral):
    for style, v in textstyle.value:
      match style:
        case TextAttribute.TextColor:
          assert isinstance(v, Color)
          charexpr.what_color.set_operand(0, StringLiteral.get(v.get_string(), self.context))
        case _:
          # TODO
          pass

  def get_renpy_character(self, vncharacter : VNCharacterSymbol, sayername : str, mode : str = 'adv', sayerstyle : TextStyleLiteral | None = None, textstyle : TextStyleLiteral | None = None) -> RenPyDefineNode | None:
    # 暂不支持 side image
    if vncharacter not in self.char_dict:
      assert vncharacter.kind.get().value == VNCharacterKind.NARRATOR
      return None
    display_dict = self.char_dict[vncharacter]
    info = _RenPyCharacterInfo(sayername=sayername, mode=mode, sayerstyle=sayerstyle, textstyle=textstyle)
    if info in display_dict:
      return display_dict[info]
    # 我们需要为了这个显示名称新建一个 Character
    # 首先，生成一个 varname
    canonical = self.canonical_char_dict[vncharacter]
    canonicalvarname = canonical.varname.get().get_string()
    definenode, charexpr = RenPyDefineNode.create_character(self.context, varname=self.generate_varname(canonicalvarname), displayname=sayername)
    self.insert_at_top(definenode)
    charexpr.kind.set_operand(0, StringLiteral.get(canonicalvarname, self.context))
    if mode != 'adv':
      charexpr.kind.set_operand(0, StringLiteral.get(mode, self.context))
    if sayerstyle is not None:
      self._populate_renpy_characterexpr_from_sayerstyle(charexpr, sayerstyle)
    if textstyle is not None:
      self._populate_renpy_characterexpr_from_textstyle(charexpr, textstyle)
    display_dict[info] = definenode
    self.global_name_dict[definenode.varname.get().get_string()] = definenode
    return definenode

  def get_asset_export_path(self, v : AssetData, parentdir : str, export_format_ext : str | None) -> str:
    # 给指定的资源生成一个在 parentdir 下的导出路径
    # 如果 export_format_ext 提供的话，应该是一个小写的后缀名，不带 '.'
    # 这里我们也要处理去重等情况
    NAME_ANON = 'anon'
    basename = NAME_ANON
    baseext = str(v.format)
    if len(baseext) == 0:
      baseext = 'bin'
    if loc := v.location:
      fileloc = loc.get_file_path()
      assert len(fileloc) > 0
      basepath, oldext = os.path.splitext(fileloc)
      basename = os.path.basename(basepath)
      assert oldext[0] == '.'
      baseext = oldext[1:]
    if export_format_ext is not None:
      baseext = export_format_ext
    # 找到一个没被用上的名字
    cur_path = parentdir + '/' + basename + '.' + baseext
    if existing := self.result.get_asset(cur_path):
      # 如果内容一样就直接报错（不应该尝试生成导出路径）
      # 不然的话加后缀直到不重名
      if existing.get_asset_value() is v:
        raise RuntimeError('Should not happen')
      suffix = 0
      if basename == NAME_ANON and parentdir in self.anon_asset_index_dict:
        suffix = self.anon_asset_index_dict[parentdir]
      cur_path = parentdir + '/' + basename + '_' + str(suffix) + '.' + baseext
      while existing := self.result.get_asset(cur_path):
        if existing.get_asset_value() is v:
          raise RuntimeError('Should not happen')
        suffix += 1
        cur_path = parentdir + '/' + basename + '_' + str(suffix) + '.' + baseext
      if basename == NAME_ANON:
        self.anon_asset_index_dict[parentdir] = suffix + 1
    return cur_path

  def _handle_assetdata(self, v : AssetData, user_hint : VNStandardDeviceKind | None = None) -> str:
    rootdir = ''
    if isinstance(v, AudioAssetData):
      match user_hint:
        case VNStandardDeviceKind.O_VOICE_AUDIO:
          rootdir = 'audio/voice'
        case VNStandardDeviceKind.O_SE_AUDIO:
          rootdir = 'audio/se'
        case VNStandardDeviceKind.O_BGM_AUDIO:
          rootdir = 'audio/bgm'
        case _:
          rootdir = 'audio/misc'
    elif isinstance(v, ImageAssetData):
      rootdir = 'images'
    else:
      rootdir = 'misc'

    # 看看是否需要转换格式，需要的话把值和后缀都改了
    export_format = None
    if isinstance(v, ImageAssetData):
      cur_format = v.format
      if cur_format is None:
        # 现在应该没有这种情况
        raise RuntimeError('Should not happen')
      if cur_format not in ['webp', 'png', 'jpeg', 'jpg']:
        # 创建一个 png 格式的新资源
        export_format = 'png'
    elif isinstance(v, AudioAssetData):
      cur_format = v.format
      if cur_format is None:
        # 现在应该没有这种情况
        raise RuntimeError('Should not happen')
      if cur_format not in ['ogg', 'mp3', 'wav']:
        export_format = 'ogg'
    else:
      raise RuntimeError('Unknown asset type')
    path = self.get_asset_export_path(v, rootdir, export_format)
    file = RenPyFileAssetOp.create(context=self.context, assetref=v, export_format=export_format, path=path)
    self.result.add_asset(file)
    return path

  def _gen_asmexpr(self, v : Value, user_hint : VNStandardDeviceKind | None = None) -> str:
    if isinstance(v, AssetData):
      return '"' + self._handle_assetdata(v, user_hint) + '"'
    if isinstance(v, PlaceholderImageLiteralExpr):
      match v.dest:
        case ImageExprPlaceholderDest.DEST_SCENE_BACKGROUND:
          kind = "'bg'"
        case ImageExprPlaceholderDest.DEST_CHARACTER_SPRITE | ImageExprPlaceholderDest.DEST_CHARACTER_SIDEIMAGE:
          kind = "'girl'"
        case _:
          kind = "None"
      return 'Placeholder(base=' + kind + ', text="' + v.description.get_string() + '")'
    if isinstance(v, ImageAssetLiteralExpr):
      return '"' + self._handle_assetdata(v.image, user_hint) + '"'
    raise NotImplementedError('Unsupported value type for asmexpr generation: ' + str(type(v)))

  def get_impsec(self, v : Value, user_hint : VNStandardDeviceKind | None = None) -> tuple[StringLiteral]:
    if result := self.imspec_dict.get(v, None):
      return result

    # 如果是有图片直接支撑的，那就可以直接取图片名
    if isinstance(v, ImageAssetLiteralExpr):
      path = self._handle_assetdata(v.image, user_hint)
      basename = os.path.basename(path)
      base = os.path.splitext(basename)[0]
      spec = tuple([StringLiteral.get(v, self.context) for v in base.split()])
      self.imspec_dict[v] = spec
      return spec

    # 需要创建一个 image 结点
    # 先定名称
    if isinstance(v, VNSymbol):
      codename = self.get_unique_global_name(v.name)
    else:
      codename = 'anonimg_' + str(self.numeric_image_index)
      self.numeric_image_index += 1
      while codename in self.global_name_dict:
        codename = 'anonimg_' + str(self.numeric_image_index)
        self.numeric_image_index += 1
    # 再取值
    expr = self._gen_asmexpr(v, user_hint=user_hint)

    resultnode = RenPyImageNode.create(self.context, codename=codename, displayable=expr)
    self.insert_at_top(resultnode)
    self.global_name_dict[codename] = resultnode
    resultimspec = (StringLiteral.get(codename, self.context),)
    self.imspec_dict[v] = resultimspec
    return resultimspec

  def try_set_imspec_for_asset(self, v : Value, imspec : tuple[str, ...]):
    if v in self.imspec_dict:
      return

    stringtized = ' '.join(imspec)
    if stringtized in self.global_name_dict:
      return

    # 可以建
    expr = self._gen_asmexpr(v, None)

    resultnode = RenPyImageNode.create(self.context, codename=stringtized, displayable=expr)
    self.insert_at_top(resultnode)
    self.global_name_dict[stringtized] = resultnode
    resultimspec = tuple([StringLiteral.get(v, self.context) for v in imspec])
    self.imspec_dict[v] = resultimspec

  def get_audiospec(self, v : Value, src_dev : VNStandardDeviceKind | None) -> StringLiteral:
    if result := self.audiospec_dict.get(v, None):
      return result
    expr = self._gen_asmexpr(v, user_hint=src_dev)
    expr = StringLiteral.get(expr, self.context)
    self.audiospec_dict[v] = expr
    return expr

  def move_to_ns(self, n : VNNamespace):
    self.cur_namespace = n
    self.cur_path_prefix = self.get_codegen_path(n)
    self.cur_mainscript = None
    self.cur_toplevel_insertionpoint = None
    # 以下状态不应该清空
    # self.char_dict.clear()
    # self.func_dict.clear()
    # self.canonical_char_dict.clear()
    # self.global_name_dict.clear()

  def insert_at_top(self, node : RenPyNode):
    ms = self.get_mainscript()
    if self.cur_toplevel_insertionpoint is None:
      ms.body.push_back(node)
    else:
      node.insert_before(self.cur_toplevel_insertionpoint)

  def get_mainscript(self):
    if self.cur_mainscript is not None:
      return self.cur_mainscript
    self.cur_mainscript = RenPyScriptFileOp.create(self.model.context, 'script')
    self.result.add_script(self.cur_mainscript)
    return self.cur_mainscript

  def run(self) -> RenPyModel:
    # 所有在 / 命名空间下的资源都会组织在根目录下，其他命名空间的资源会在 dlc/<命名空间路径> 下
    # 我们需要按排好序的名称进行生成，这样可以保证子命名空间在父命名空间之后生成
    assert self.result is None
    self.result = RenPyModel.create(self.model.context)
    for k in sorted(self.model.namespace.keys()):
      n = self.model.namespace.get(k)
      assert isinstance(n, VNNamespace)
      self.move_to_ns(n)
      self.handle_all_devices()
      self.label_all_functions()
      self.handle_all_values()

      for a in n.assets:
        self.handle_asset(a)
      for c in n.characters:
        self.handle_character(c)
      for s in n.scenes:
        self.handle_scene(s)
      for f in n.functions:
        self.handle_function(f)
    return self.result

def codegen_renpy(m : VNModel) -> RenPyModel:
  helper = _RenPyCodeGenHelper(m)
  return helper.run()
