# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy

from preppipe.irbase import Location, StringLiteral

from ...irbase import *
from ..commandsyntaxparser import *
from ..commandsemantics import *
from ...vnmodel_v4 import *
from .vnast import *
from .vncodegen import *
from .vnsayscan import *
from ...util.antlr4util import TextStringParsingUtil

# ------------------------------------------------------------------------------
# 内容声明命令
# ------------------------------------------------------------------------------

vn_command_ns = FrontendCommandNamespace.create(None, 'vnmodel')

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
class VNASTParsingState:
  # 该类描述所有状态信息;所有的引用都不“拥有”所引用的对象
  # 所有的都是浅层复制

  # （不属于状态信息但是有用）
  context : Context

  input_top_level_region : Region = None # 应该永不为 None
  input_current_block : Block = None # 下一个需要读取的块（我们在处理操作项时先把这个转向它的下一项，就像先更新PC再执行指令那样）
  output_current_file : VNASTFileInfo = None
  output_current_region : VNASTCodegenRegion = None

  def fork(self) -> VNASTParsingState:
    return copy.copy(self)

  def get_next_input_block(self) -> Block | None:
    if self.input_current_block is not None:
      cur = self.input_current_block
      self.input_current_block = cur.get_next_node()
      return cur
    return None

  def peek_next_block(self) -> Block | None:
    return self.input_current_block

  def _emit_impl(self, node : VNASTNodeBase | MetadataOp):
    if self.output_current_region is not None:
      self.output_current_region.body.push_back(node)
      return
    self.output_current_file.pending_content.push_back(node)

  def emit_node(self, node : VNASTNodeBase):
    self._emit_impl(node)

  def emit_md(self, md : MetadataOp):
    self._emit_impl(md)

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
  state_default_sayer : VNCharacterSymbol = None # 默认发言者; None 为旁白
  state_current_scene : VNSceneSymbol = None # 当前场景
  state_sayer_states : collections.OrderedDict[VNCharacterSymbol, VNParsingStateForSayer] = None # 每个发言者当前的状态
  state_scene_states : list[str] = None # 场景的状态标签

  # 当前设备
  # 所有的都是浅层复制
  state_current_device_say_name : VNDeviceSymbol = None
  state_current_device_say_text : VNDeviceSymbol = None
  state_current_device_say_sideimage : VNDeviceSymbol = None

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

class VNParser(FrontendParserBase[VNASTParsingState]):
  ast : VNAST
  ctx : Context

  def __init__(self, ctx: Context, command_ns: FrontendCommandNamespace) -> None:
    super().__init__(ctx, command_ns, VNASTParsingState)
    self.ast = VNAST.create('', ctx)

  @staticmethod
  def create(ctx: Context, command_ns: FrontendCommandNamespace | None = None):
    if command_ns is None:
      command_ns = vn_command_ns
    return VNParser(ctx, command_ns)

  def initialize_state_for_doc(self, doc : IMDocumentOp) -> VNASTParsingState:
    # 跳过空文件
    if doc.body.blocks.empty:
      return None
    state = VNASTParsingState(self.context)
    # 首先将输入状态搞好
    state.input_top_level_region = doc.body
    state.input_current_block = doc.body.blocks.front
    file = VNASTFileInfo.create(name=doc.name, loc = doc.location)
    self.ast.files.push_back(file)
    state.output_current_file = file
    state.output_current_region = None
    return state

  def populate_ops_from_block(self, state : VNASTParsingState, block : Block, oplist : list[Operation]) -> None:
    # 把一个块中的所有 op 读取出来
    # 专门建一个函数的原因是方便子类覆盖该函数，这样在我们开始处理该块之前可以搞一些特殊操作（比如添加命令，）
    for op in block.body:
      oplist.append(op)

  def _emit_text_content(self, state : VNASTParsingState, content : list[TextFragmentLiteral | StringLiteral], leading_element : Operation) -> VNASTSayNode | None:
    # 我们尝试把文本内容归类为以下三种情况：
    # 1. 显式指定发言角色的
    # 2. 所有内容都被引号引起来的，单独一句话
    # 3. 其他情况，默认所有内容都是发言
    # 具体实现在 vnsayscan.py 中
    pu = TextStringParsingUtil.create(content)
    emit_content = None
    if scanresult := analyze_say_expr(pu.get_full_str()):
      # 文本是预期的内容
      finalcontent : list[TextFragmentLiteral | StringLiteral] = []
      sayer : str | None = None
      expr : str | None = None
      if scanresult.sayer is not None:
        sayer = scanresult.sayer.text
      if scanresult.expression is not None:
        expr = scanresult.expression.text
      for piece in scanresult.content:
        finalcontent.extend(pu.extract_str_from_interval(piece.start, piece.end))
      nodetype = VNASTSayNodeType.TYPE_FULL
      if sayer is None:
        nodetype = VNASTSayNodeType.TYPE_QUOTED if scanresult.is_content_quoted else VNASTSayNodeType.TYPE_NARRATE
      for v in finalcontent:
        assert isinstance(v, (StringLiteral, TextFragmentLiteral))
      emit_content = VNASTSayNode.create(context=self.context, nodetype=nodetype, content=finalcontent, expression=expr, sayer=sayer, name=leading_element.name, loc=leading_element.location)
    else:
      # 文本不符合预期内容，所有文本就当作没有指定发言者和状态、表情的内容
      emit_content = VNASTSayNode.create(context=self.context, nodetype=VNASTSayNodeType.TYPE_NARRATE, content=content.copy(), name=leading_element.name, loc=leading_element.location)
    state.emit_node(emit_content)
    return emit_content

  def handle_block(self, state : VNASTParsingState, block : Block):
    # 检查一下假设
    if b := state.peek_next_block():
      assert block.get_next_node() is b
    if block.body.empty:
      return
    # 我们在编译时跳过所有 MetadataOp 但是保留其与其他内容的相对位置
    # 虽然前端并不支持在文本中夹杂命令，这不妨碍我们在处理文本的过程中执行命令
    # 以后也有可能添加在文本中加入命令的语法

    # 除了把所有命令翻译掉、文本段落转换为发言外，我们还需支持以下转换规则：
    # 1. 特殊块：
    #     有背景颜色：视为内嵌命令
    #     居中：视为特殊发言
    # 2. 单独的图片、声音：视为显示、播放资源
    # 3. 单独的列表、表格：忽视
    # 和以下特殊情况：
    # 1. 发言文本后同段落紧跟音频文件：将音频视为发言的语音而不是独立的音效
    # 2. 遇到段落内只有一张图片时，如果后面跟了一个特殊块，将特殊块视为该图片的标题，特殊处理
    pending_say_text_contents : list[TextFragmentLiteral | StringLiteral] = []
    leading_element : IMElementOp | None = None
    last_say : VNASTSayNode | None = None
    def try_emit_pending_content():
      nonlocal leading_element
      nonlocal pending_say_text_contents
      nonlocal last_say
      if leading_element is None:
        return
      last_say = self._emit_text_content(state, pending_say_text_contents, leading_element)
      pending_say_text_contents.clear()
      leading_element = None

    ignore_next_op = None
    for op in block.body:
      if ignore_next_op is not None:
        if ignore_next_op is op:
          ignore_next_op = None
          continue
        ignore_next_op = None

      if isinstance(op, MetadataOp):
        try_emit_pending_content()
        cloned = op.clone()
        state.emit_md(cloned)
        continue
      if isinstance(op, GeneralCommandOp):
        last_say = None
        try_emit_pending_content()
        self.handle_command_op(state, op)
        continue
      if isinstance(op, IMElementOp):
        # 首先判断这是文本内容还是音频或图片
        # 文本内容的话可能不止一个值，音频或者图片的话只会有一个值
        # 所以我们看第一个值就能判断种类
        firstvalue = op.content.get()
        if isinstance(firstvalue, (StringLiteral, TextFragmentLiteral)):
          # 这是文本内容
          last_say = None
          for u in op.content.operanduses():
            pending_say_text_contents.append(u.value)
          leading_element = op
        elif isinstance(firstvalue, AudioAssetData):
          # 内嵌音频
          try_emit_pending_content()
          assert op.content.get_num_operands() == 1
          if last_say is not None:
            last_say.embed_voice = firstvalue
          else:
            result = VNASTAssetReference.create(context=self.context, name=op.name, loc=op.location, kind=VNASTAssetKind.KIND_AUDIO, operation=VNASTAssetIntendedOperation.OP_PUT, asset=firstvalue)
            state.emit_node(result)
          last_say = None
        elif isinstance(firstvalue, ImageAssetData):
          # 内嵌图片
          try_emit_pending_content()
          last_say = None
          assert op.content.get_num_operands() == 1
          result = VNASTAssetReference.create(context=self.context, name=op.name, loc=op.location, kind=VNASTAssetKind.KIND_IMAGE, operation=VNASTAssetIntendedOperation.OP_CREATE, asset=firstvalue)
          state.emit_node(result)
          # 尝试在这个 IMElementOp 之后找到一个 IMSpecialBlockOp 来作为该图片的描述、标题
          # 我们假设有两种情况：
          # 1. 这个 IMElementOp 之后立即跟着 IMSpecialBlockOp （LibreOffice 实测下来是这种情况）
          # 2. 这段已经没有内容，下一段跟着个 IMSpecialBlockOp （臆想的情况，还没找到可以触发这种情况的源）
          def set_description_from_special_block(specialblock : IMSpecialBlockOp):
            nonlocal result
            # 如果内容不止一行的话我们取第一行
            firststr = specialblock.content.get_operand(0).get_string()
            assert isinstance(firststr, str)
            # 如果第一段有冒号':'或'：'，我们就把这段字符串分两截
            description : list[str] = []
            if r := re.match(r"^\s*((?P<T1>[^:：]+)\s*[:：])?\s*(?P<T2>.+)$", firststr):
              if t1 := r.group('T1'):
                description.append(t1)
              if t2 := r.group('T2'):
                description.append(t2)
            else:
              description.append(firststr)
            for s in description:
              result.descriptions.add_operand(StringLiteral.get(s, self.context))
          if op.get_next_node() is None:
            if nb := state.peek_next_block():
              is_other_element_found = False
              specialblock : IMSpecialBlockOp | None = None
              other_md : list[MetadataOp] = []
              for op in nb.body:
                if isinstance(op, IMSpecialBlockOp):
                  specialblock = op
                elif isinstance(op, MetadataOp):
                  other_md.append(op)
                else:
                  is_other_element_found = True
                  break
              if not is_other_element_found and specialblock is not None:
                set_description_from_special_block(specialblock)
                if len(other_md) > 0:
                  for md in other_md:
                    state.emit_md(md.clone())
                # 因为我们已经把下一段的特殊块吃掉了，所以这里必须跳过一个块
                state.get_next_input_block()
                return
          else:
            nextnode = op.get_next_node()
            if isinstance(nextnode, IMSpecialBlockOp):
              set_description_from_special_block(nextnode)
              ignore_next_op = nextnode
        else:
          raise RuntimeError('Unexpected content type in IMElementOp: ' + type(firstvalue).__name__)
        # IMElementOp 的情况处理完毕
        continue
      if isinstance(op, IMSpecialBlockOp):
        raise NotImplementedError('TODO 支持单独的 IMSpecialBlockOp')
      if isinstance(op, (IMListOp, IMTableOp)):
        last_say = None
        try_emit_pending_content()
        # 以后有可能能够解析，现在直接跳过
        continue
      raise NotImplementedError('Unhandled element type')
    try_emit_pending_content()
    return

  def add_document(self, doc : IMDocumentOp):
    # 我们在 VNModel 中将该文档中的内容“转录”过去
    # 跳过所有空文件
    if (state := self.initialize_state_for_doc(doc)) is None:
      return
    while block := state.get_next_input_block():
      self.handle_block(state, block)

  def create_command_match_error(self, commandop: GeneralCommandOp, unmatched_results: list[typing.Tuple[callable, typing.Tuple[str, str]]] | None = None, matched_results: list[FrontendParserBase.CommandInvocationInfo] | None = None) -> ErrorOp:
    errmsg = 'Cannot find unique match for command: ' + commandop.get_short_str()
    if matched_results is not None and len(matched_results) > 0:
      errmsg += '\nmatched candidates: ' + ', '.join([cmdinfo.cb.__name__ for cmdinfo in matched_results])
    if unmatched_results is not None and len(unmatched_results) > 0:
      errmsg += '\nunmatched candidates: '
      ulist = []
      for targetcb, errtuple in unmatched_results:
        errcode, msg = errtuple
        candidatemsg = targetcb.__name__ + ': ' + errcode + ': ' + msg
        ulist.append(candidatemsg)
      errmsg += ', '.join(ulist)
    error_msg_literal = StringLiteral.get(errmsg, self.context)
    return ErrorOp.create('vnparser-cmd-match-error', self.context, error_msg_literal)

  def handle_command_unrecognized(self, state: VNASTParsingState, op: GeneralCommandOp, opname: str) -> None:
    # 在插入点创建一个 UnrecognizedCommandOp
    newop = UnrecognizedCommandOp.create(op)
    state.emit_node(newop)

  def handle_command_invocation(self, state: VNASTParsingState, commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo):
    return super().handle_command_invocation(state, commandop, cmdinfo)

  def handle_command_ambiguous(self, state: VNASTParsingState,
                               commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo,
                               matched_results: typing.List[FrontendParserBase.CommandInvocationInfo],
                               unmatched_results: typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    newop = self.create_command_match_error(commandop, unmatched_results, matched_results)
    state.emit_md(newop)

  def handle_command_no_match(self, state: VNASTParsingState,
                              commandop: GeneralCommandOp, cmdinfo: FrontendCommandInfo,
                              unmatched_results: typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    newop = self.create_command_match_error(commandop, unmatched_results)
    state.emit_md(newop)

  def handle_command_unique_invocation(self, state: VNASTParsingState,
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
  # 声明角色仅用于提供角色的身份
  # 在前端命令上可以身份+显示方式（比如显示名称，名字颜色等）一并设置，也可以只用该指令设定身份，用后面的“设置角色发言属性”来提供其他信息
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
                       #'content_prefix': '内容前缀',
                       #'content_suffix': '内容后缀',
                      }, # zh_CN
})
def cmd_character_say_attr(parser : VNParser, commandop : GeneralCommandOp, character_name : str, *, state_tags : str = '',
                           name_color : str = None, # 名字的颜色，None 保留默认值
                           display_name : str = None, # 显示的名字的内容，如果名字不是字面值的话就用 expression, 这项留空
                           display_name_expression : str = None, # 如果名字要从变量中取或者其他方式，这项就是用于求解的表达式
                           content_color : str = None, # 文本的颜色
                           #前后缀暂不支持，后端这块要支持起来‘’还得改
                           #content_prefix : str = '', # 文本前缀（比如如果要把所有文本都用『』括起来的话，那么这两个符号就是前缀和后缀）
                           #content_suffix : str = '',
                          ):
  # 定义一个角色说话时名称的显示
  # 声明的发言信息会在这两种情况下使用：
  # 1. 剧本中发言者为角色本名，并且满足给定的状态标签时
  # 2. 剧本中发言者为这里定义的显示名称。
  # 第二种情况只在显示名称无歧义时可使用（比如没有多个角色同时为"???"），第一种情况一定可以用
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
  # 别名都是文件内有效，出文件就失效。（实在需要可以复制黏贴）
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
class _SelectFinishActionEnum(enum.Enum):
  CONTINUE = 0 # 默认继续执行分支后的内容（默认值）
  LOOP = 1 # 循环到选项开始（用于类似Q/A，可以反复选择不同选项。可由跳出命令结束）

@CommandDecl(vn_command_ns, _imports, 'Select', alias={
  '选项': {'name': '名称', 'finish_action': '结束动作'}
})
def cmd_select(parser : VNParser, commandop : GeneralCommandOp, ext : ListExprOperand, name : str, finish_action : _SelectFinishActionEnum = _SelectFinishActionEnum.CONTINUE):
  pass

@CommandDecl(vn_command_ns, _imports, 'ExitLoop', alias={
  '跳出循环': {}
})
def cmd_exit_loop(parser : VNParser, commandop : GeneralCommandOp):
  # 用来在带循环的选项命令中跳出循环
  # 目前没有其他循环结构，只有这里用得到，以后可能会用在其他地方
  pass

@CommandDecl(vn_command_ns, _imports, 'Choice', alias={
  '分支': {'condition': '条件'}
})
def cmd_branch(parser : VNParser, commandop : GeneralCommandOp, ext : ListExprOperand, condition : str = None):
  # 有两种方式使用该命令：
  # 1. 【分支】
  #       * <条件1>
  #         - <条件1的分支>
  #       * <条件2>
  # ....
  # 2.  【分支：条件="<条件1>"】
  #       * <条件1的分支>
  pass

# ------------------------------------------------------------------------------
# 解析状态相关的命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, _imports, 'LongSpeech', alias={
  '长发言': {'sayer': '发言者'}, # zh_CN
})
def cmd_long_speech_mode(parser : VNParser, commandop : GeneralCommandOp, sayer : CallExprOperand):
  pass

@CommandDecl(vn_command_ns, _imports, 'InterleaveSayer', alias={
  '交替发言': {'sayer': '发言者'}, # zh_CN
})
def cmd_interleave_mode(parser : VNParser, commandop : GeneralCommandOp, sayer : list[CallExprOperand]):
  print("交替发言：")
  for s in sayer:
    print(str(s))

