# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy

from ...irbase import *
from ..commandsyntaxparser import *
from ..commandsemantics import *
from ...vnmodel_v4 import *

# ------------------------------------------------------------------------------
# 内容声明命令
# ------------------------------------------------------------------------------

vn_command_ns = FrontendCommandNamespace.create(None, 'vnmodel')

class UnrecognizedCommandOp(ErrorOp):
  # 基本是从 GeneralCommandOp 那里抄来的
  _head_region : SymbolTableRegion # name + raw_args
  _positionalarg_region : Region # single block, list of values
  _positionalarg_block : Block
  _keywordarg_region : SymbolTableRegion

  def __init__(self, src: GeneralCommandOp, **kwargs) -> None:
    super().__init__(src.name, src.location, 'vnparser-unrecognized-command', None, **kwargs)
    self._head_region = self._add_symbol_table('head')
    self._positionalarg_region = self._add_region('positional_arg')
    self._keywordarg_region = self._add_symbol_table('keyword_arg')
    self._positionalarg_block = self._positionalarg_region.add_block('')
    src_head = src.get_symbol_table('head')
    src_name_symbol = src_head.get('name')
    assert isinstance(src_name_symbol, CMDValueSymbol)
    name_symbol = CMDValueSymbol('name', src_name_symbol.location, src_name_symbol.value)
    self._head_region.add(name_symbol)
    src_rawarg_symbol = src_head.get('rawarg')
    if src_rawarg_symbol is not None:
      assert isinstance(src_rawarg_symbol, CMDValueSymbol)
      rawarg_symbol = CMDValueSymbol('rawarg', src_rawarg_symbol.location, src_rawarg_symbol.value)
      self._head_region.add(rawarg_symbol)
    src_positional_arg = src.get_region('positional_arg')
    assert src_positional_arg.get_num_blocks() == 1
    src_positional_arg_block = src_positional_arg.entry_block
    for op in src_positional_arg_block.body:
      assert isinstance(op, CMDPositionalArgOp)
      self._positionalarg_block.push_back(CMDPositionalArgOp(op.name, op.location, op.value))
    src_kwarg = src.get_symbol_table('keyword_arg')
    for op in src_kwarg:
      assert isinstance(op, CMDValueSymbol)
      self._keywordarg_region.add(CMDValueSymbol(op.name, op.location, op.value))

@dataclasses.dataclass
class VNParsingStateForSayer:
  sprite_handle : Value = None
  sayer_state : list[str] = None

  def __copy__(self) -> VNParsingStateForSayer:
    return copy.deepcopy(self)

  def __deepcopy__(self, memo) -> VNParsingStateForSayer:
    result = VNParsingStateForSayer(sprite_handle = self.sprite_handle)
    if self.sayer_state is not None:
      result.sayer_state = self.sayer_state.copy()
    return result

@dataclasses.dataclass
class VNParsingState:
  # 该类描述所有状态信息;所有的引用都不“拥有”所引用的对象
  # 部分不会在处理输入时改变的内容不会在这出现（比如当前的命名空间，当前命名空间的人物声明，等等）
  # 如果要添加成员，请记得更新 copy() 函数，以免出现复制出错

  # （不属于状态信息但是有用）
  context : Context

  # 输入输出位置
  # 所有的都是浅层复制
  # 读取时，我们以块（段落）为单位进行读取；输出是以操作项为单位
  input_top_level_region : Region = None # 应该永不为 None
  input_current_block : Block = None # 下一个需要读取的块（我们在处理操作项时先把这个转向它的下一项，就像先更新PC再执行指令那样）
  output_current_region : Region = None # 如果这是 None，那我们还没有开始构建 VNFunction 而只是在一个 stub 里填内容，否则这应该是 VNFunction 的内容区
  output_current_block : Block = None # 如果这是 None, 那我们还没有进入任何函数部分，有需要加内容就填一个 stub
  output_current_insertion_point : Operation = None # 新输出项的位置，如果是 None 则加到 output_current_block 结尾，不然的话就加在该操作项之前

  # 当前场景信息
  # state_sayer_states 和 state_scene_states 需要深层复制
  state_default_sayer : VNCharacterRecord = None # 默认发言者; None 为旁白
  state_current_scene : VNSceneRecord = None # 当前场景
  state_sayer_states : collections.OrderedDict[VNCharacterRecord, VNParsingStateForSayer] = None # 每个发言者当前的状态
  state_scene_states : list[str] = None # 场景的状态标签

  # 当前设备
  # 所有的都是浅层复制
  state_current_device_say_name : VNDeviceRecord = None
  state_current_device_say_text : VNDeviceRecord = None
  state_current_device_say_sideimage : VNDeviceRecord = None

  def __deepcopy__(self, memo):
    # deep copy of VNParserState would cause handles like VNCharacterRecord being copied as well
    # we only use shallow copy for VNParserState
    raise RuntimeError('VNParserState should not be deep-copied')

  def __copy__(self) -> VNParsingState:
    # 先把浅层复制的解决了
    result = dataclasses.replace(self)
    # 然后所有需要深层复制的再更新
    if self.state_scene_states is not None:
      result.state_scene_states = self.state_scene_states.copy()
    if self.state_sayer_states is not None:
      result.state_sayer_states = collections.OrderedDict()
      for sayer, state in self.state_sayer_states.items():
        result.state_sayer_states[sayer] = copy.copy(state)
    return result

  def fork(self) -> VNParsingState:
    return copy.copy(self)

  def write_op(self, op : Operation | typing.Iterable[Operation]):
    if self.output_current_block is None:
      assert self.output_current_region is None and self.output_current_insertion_point is None
      self.output_current_block = Block('', self.context)
    if isinstance(op, Operation):
      if self.output_current_insertion_point is None:
        self.output_current_block.push_back(op)
      else:
        if self.output_current_insertion_point is None:
          for cur in op:
            assert isinstance(cur, Operation)
            self.output_current_block.push_back(cur)
        else:
          for cur in op:
            assert isinstance(cur, Operation)
            cur.insert_before(self.output_current_insertion_point)

  def get_next_input_block(self) -> Block | None:
    if self.input_current_block is not None:
      cur = self.input_current_block
      self.input_current_block = cur.get_next_node()
      return cur
    return None

class VNParser(FrontendParserBase[VNParsingState]):
  _result_op : VNModel
  _resolver : VNModelNameResolver

  def __init__(self, ctx: Context, command_ns: FrontendCommandNamespace) -> None:
    super().__init__(ctx, command_ns, VNParsingState)
    self._result_op = VNModel.create(context=ctx, name = '', loc = ctx.null_location)
    self._resolver = VNModelNameResolver(self._result_op)

  @property
  def resolver(self):
    return self._resolver

  def initialize_state_for_doc(self, doc : IMDocumentOp) -> VNParsingState:
    state = VNParsingState(self._result_op.context)
    # 首先将输入状态搞好
    state.input_top_level_region = doc.body
    if state.input_top_level_region.blocks.empty:
      return None
    state.input_current_block = doc.body.blocks.front
    # 输出状态和当前场景状态不用管
    # TODO 初始化当前设备信息
    return state

  def populate_ops_from_block(self, state : VNParsingState, block : Block, oplist : list[Operation]) -> None:
    # 把一个块中的所有 op 读取出来
    # 专门建一个函数的原因是方便子类覆盖该函数，这样在我们开始处理该块之前可以搞一些特殊操作（比如添加命令，）
    for op in block.body:
      oplist.append(op)

  def handle_block(self, state : VNParsingState, block : Block):
    if block.body.empty:
      return
    # 我们在编译时跳过所有 MetadataOp 但是保留其与其他内容的相对位置
    # 虽然前端并不支持在文本中夹杂命令，这不妨碍我们在处理文本的过程中执行命令
    # 以后也有可能添加在文本中加入命令的语法
    # TODO 继续完成该函数
    text_sayer_ref : VNCharacterRecord = None
    pending_say_text_contents = []
    def try_emit_pending_content():
      pass

    for op in block.body:
      if isinstance(op, MetadataOp):
        try_emit_pending_content()
        # TODO 等待 clone() 完成后把这个加上
        # cloned = op.clone()
        # state.write_op(cloned)
        continue
      if isinstance(op, GeneralCommandOp):
        self.handle_command_op(state, op)
        continue
      if isinstance(op, IMElementOp):
        pending_say_text_contents.append(op.content.get())
        continue
      if isinstance(op, IMListOp):
        # TODO 递归解析所有内容
        continue
      raise NotImplementedError('Unhandled element type')

  def add_document(self, doc : IMDocumentOp):
    # 我们在 VNModel 中将该文档中的内容“转录”过去
    # 跳过所有空文件
    if (state := self.initialize_state_for_doc(doc)) is None:
      return
    while block := state.get_next_input_block():
      self.handle_block(state, block)

  def handle_command_unrecognized(self, state: VNParsingState, op: GeneralCommandOp, opname: str) -> None:
    # 在插入点创建一个 UnrecognizedCommandOp
    # TODO 在这加自动匹配
    newop = UnrecognizedCommandOp(op)
    #newop.insert_before(self._insert_point)
    print('Unrecognized command: ' + str(op))

  def handle_command_invocation(self, state: VNParsingState, commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo):
    return super().handle_command_invocation(state, commandop, cmdinfo)

  def handle_command_ambiguous(self, state: VNParsingState,
                               commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo,
                               matched_results: typing.List[FrontendParserBase.CommandInvocationInfo],
                               unmatched_results: typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    raise NotImplementedError()

  def handle_command_no_match(self, state: VNParsingState,
                              commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo,
                              unmatched_results: typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    raise NotImplementedError()

  def handle_command_unique_invocation(self, state: VNParsingState,
                                       commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo,
                                       matched_result: FrontendParserBase.CommandInvocationInfo,
                                       unmatched_results: typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    target_cb = matched_result.cb
    target_args = matched_result.args
    target_kwargs = matched_result.kwargs
    target_warnings = matched_result.warnings
    print('Command ' + cmdinfo.cname + ': target_cb=' + str(target_cb) + ', args=' + str(target_args) + ', kwargs=' + str(target_kwargs) + ', warnings=' + str(target_warnings))
    target_cb(*target_args, **target_kwargs)
    return

# 把 VNParser 的定义包含进去，这样后面的类型标注可以顺利进行
_imports = globals()

# ------------------------------------------------------------------------------
# 内容声明命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, _imports, 'DeclImage', alias={
  '声明图片': {'name': '名称', 'path': '路径'}, # zh_CN
})
def cmd_image_decl(parser : VNParser, commandop : GeneralCommandOp, name : str, path : str):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclVariable', alias={
  '声明变量' : {'name': '名称', 'type': '类型', 'initializer': '初始值'},
})
# pylint: disable=redefined-builtin
def cmd_variable_decl(parser: VNParser, commandop : GeneralCommandOp, name : str, type : str, initializer : str):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclCharacter', alias={
  '声明角色' : {'name': '姓名'}, # zh_CN
})
def cmd_character_decl(parser: VNParser, commandop : GeneralCommandOp, name : str, ext : ListExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclCharacterSprite', alias={
  '声明角色立绘' : {'character_state_expr': '角色与状态表达式', 'image': '图片'}, # zh_CN
})
def cmd_character_sprite_decl(parser : VNParser, commandop : GeneralCommandOp, character_state_expr : CallExprOperand | str, image : str):
  # 定义一个角色的外观状态（一般是立绘差分，比如站姿、衣着、等），使得角色变换状态时能够切换立绘
  # 这必须是一个独立于角色声明的操作，因为更多角色外观等可以通过DLC等形式进行补足，所以它们可能处于不同的命名空间中
  # 在实际的内容中，一个角色的状态标签会有很多（包含衣着、站姿、表情等），
  # 我们先把这里声明的角色标签给匹配掉，剩余的标签喂给图像参数（应该是带差分的多层图片）
  # 我们预计用本命令指定角色的基础外观（比如站姿、衣着，确定哪组立绘），剩下的用来在立绘中选表情匹配的差分
  # 虽然我们基本上只用一个“状态标签”参数来进行匹配，但对人物而言，我们要求最后一个标签代表表情，
  # 这样文中可以用<人名><表情><内容>的方式来表达说明，并且表情标签所替代的标签没有歧义
  # （我们也可以支持表情标签的层级，永远从最右侧替换）
  pass

@CommandDecl(vn_command_ns, _imports, 'SetCharacterSayAttr', alias={
  '设置角色发言属性' : {'character_name': '角色姓名', 'state_tags': '状态标签',
                       'name_color': '名字颜色',
                       'display_name': '显示名',
                       'display_name_expression': '显示名表达式',
                       'content_color': '内容颜色',
                       'content_prefix': '内容前缀',
                       'content_suffix': '内容后缀',
                      }, # zh_CN
})
def cmd_character_say_attr(parser : VNParser, commandop : GeneralCommandOp, character_name : str, *, state_tags : str = '',
                           name_color : str = None, # 名字的颜色，None 保留默认值
                           display_name : str = None, # 显示的名字的内容，如果名字不是字面值的话就用 expression, 这项留空
                           display_name_expression : str = None, # 如果名字要从变量中取或者其他方式，这项就是用于求解的表达式
                           content_color : str = None, # 文本的颜色
                           content_prefix : str = '', # 文本前缀（比如如果要把所有文本都用『』括起来的话，那么这两个符号就是前缀和后缀）
                           content_suffix : str = '',
                          ):
  # 定义一个角色说话时名称的显示
  # 如果
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclScene', alias={
  '声明场景' : {'name': '名称'}, # zh_CN
})
def cmd_scene_decl(parser : VNParser, commandop : GeneralCommandOp, name : str, ext : ListExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclSceneBackground', alias={
  '声明场景背景' : {'scene': '场景', 'state_tags' : '状态标签', 'background_image' : '背景图片'}, # zh_CN
})
def cmd_scene_background_decl(parser : VNParser, commandop : GeneralCommandOp, scene : str, state_tags : str, background_image : str):
  # 给场景定义一个可显示状态，使得“切换场景”可以更改背景
  pass

@CommandDecl(vn_command_ns, _imports, 'DeclAlias', alias={
  '声明别名' : {'alias_name': '别名名称', 'target':'目标'}, # zh_CN
})
def cmd_alias_decl(parser : VNParser, commandop : GeneralCommandOp, alias_name : str, target : CallExprOperand):
  # (仅在解析时用到，不会在IR中)
  # 给目标添加别名（比如在剧本中用‘我’指代某个人）
  pass

# ------------------------------------------------------------------------------
# 内容操作命令
# ------------------------------------------------------------------------------
@CommandDecl(vn_command_ns, _imports, 'CharacterEnter', alias={
  '角色入场': {'characters': '角色', 'transition': '转场'}
})
def cmd_character_entry(parser : VNParser, commandop : GeneralCommandOp, characters : list[CallExprOperand], transition : CallExprOperand = None):
  pass

def cmd_wait_finish(parser : VNParser, commandop : GeneralCommandOp):
  pass

@CommandDecl(vn_command_ns, _imports, 'CharacterExit', alias={
  '角色退场': {'characters': '角色', 'transition': '转场'}
})
def cmd_character_exit(parser : VNParser, commandop : GeneralCommandOp, characters : list[CallExprOperand], transition : CallExprOperand = None):
  pass

@CommandDecl(vn_command_ns, _imports, 'SpecialEffect', alias={
  '特效': {'effect': '特效'}
})
def cmd_special_effect(parser : VNParser, commandop : GeneralCommandOp, effect : CallExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'SwitchCharacterState', alias={
  '切换角色状态': {'state_expr': '状态表达式'}
})
def cmd_switch_character_state(parser : VNParser, commandop : GeneralCommandOp, state_expr : list[str] | CallExprOperand):
  # 如果是个调用表达式，则角色名是调用的名称
  # 如果是一串标签字符串，则更改默认发言者的状态
  # 优先匹配一串字符串
  pass

@CommandDecl(vn_command_ns, _imports, 'SwitchScene', alias={
  '切换场景': {'scene': '场景'}
})
def cmd_switch_scene(parser : VNParser, commandop : GeneralCommandOp, scene: CallExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'HideImage', alias={
  '收起图片': {'image_name': '图片名', 'transition': '转场'}
})
def cmd_hide_image(parser : VNParser, commandop : GeneralCommandOp, image_name : str, transition : CallExprOperand = None):
  pass


# ------------------------------------------------------------------------------
# 控制流相关的命令
# ------------------------------------------------------------------------------
@CommandDecl(vn_command_ns, _imports, 'Function', alias={
  ('Function', 'Section') : {}, # en
  ('函数', '章节') : {'name': '名称'}, # zh_CN
})
def cmd_set_function(parser : VNParser, commandop : GeneralCommandOp, name : str):
  pass

@FrontendParamEnum(alias={
  'CONTINUE': { 'continue', '继续'},
  'LOOP': {'loop', '循环'}
})
class ChoiceFinishActionEnum(enum.Enum):
  CONTINUE = 0 # 默认继续执行分支后的内容（默认值）
  LOOP = 1 # 循环到选项开始（用于类似Q/A，可以反复选择不同选项。可由跳出命令结束）

@CommandDecl(vn_command_ns, _imports, 'Choice', alias={
  '选项': {'name': '名称', 'finish_action': '结束动作'}
})
def cmd_choice(parser : VNParser, commandop : GeneralCommandOp, ext : ListExprOperand, name : str, finish_action : ChoiceFinishActionEnum = ChoiceFinishActionEnum.CONTINUE):
  pass

# ------------------------------------------------------------------------------
# 解析状态相关的命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, _imports, 'DefaultSayer', alias={
  '默认发言者': {'character_state_expr': '角色与状态表达式'}, # zh_CN
})
def cmd_set_default_sayer(parser : VNParser, commandop : GeneralCommandOp, character_expr : CallExprOperand):
  pass



@MiddleEndDecl('vn', input_decl=IMDocumentOp, output_decl=VNModel)
class VNParseTransform(TransformBase):
  _parser : VNParser
  def __init__(self, ctx: Context) -> None:
    super().__init__(ctx)
    self._parser = VNParser(ctx, vn_command_ns)

  def run(self) -> Operation | typing.List[Operation] | None:
    for doc in self.inputs:
      self._parser.add_document(doc)
    return VNModel('', self.context.null_location)
