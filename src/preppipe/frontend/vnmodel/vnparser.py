# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import copy

from preppipe.irbase import Location, StringLiteral

from ...irbase import *
from ..commandsyntaxparser import *
from ..commandsemantics import *
from ...vnmodel import *
from ...imageexpr import *
from .vnast import *
from .vncodegen import *
from .vnsayscan import *
from .vnutil import *

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

  input_file_path : str # 正在解析哪个文件的内容，用来辅助文件查找
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

  def emit_error(self, code : str, msg : str, loc : Location | None = None):
    err = ErrorOp.create(error_code=code, context=self.context, error_msg=StringLiteral.get(msg, self.context), loc=loc)
    self._emit_impl(err)

class VNParser(FrontendParserBase[VNASTParsingState]):
  ast : VNAST
  ctx : Context
  resolution : tuple[int, int]

  def __init__(self, ctx: Context, command_ns: FrontendCommandNamespace, screen_resolution : tuple[int, int], name : str = '') -> None:
    super().__init__(ctx, command_ns, VNASTParsingState)
    self.ast = VNAST.create(name=name, screen_resolution=IntTupleLiteral.get(screen_resolution, ctx), context=ctx)
    self.resolution = screen_resolution

  @staticmethod
  def create(ctx: Context, command_ns: FrontendCommandNamespace | None = None, screen_resolution : tuple[int, int] | None = None, name : str = ''):
    if command_ns is None:
      command_ns = vn_command_ns
    if screen_resolution is None:
      screen_resolution = (1920, 1080)
    return VNParser(ctx, command_ns, screen_resolution)

  def initialize_state_for_doc(self, doc : IMDocumentOp) -> VNASTParsingState | None:
    # 跳过空文件
    if doc.body.blocks.empty:
      return None
    state = VNASTParsingState(self.context, doc.location.get_file_path())
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
      expr : list[StringLiteral] | None = None
      if scanresult.sayer is not None:
        sayer = scanresult.sayer.text
      if scanresult.expression is not None:
        expr = [StringLiteral.get(v.text, self.context) for v in scanresult.expression]
      for piece in scanresult.content:
        finalcontent.extend(pu.extract_str_from_interval(piece.start, piece.end))
      nodetype = VNASTSayNodeType.TYPE_FULL
      if sayer is None:
        nodetype = VNASTSayNodeType.TYPE_QUOTED if scanresult.is_content_quoted else VNASTSayNodeType.TYPE_NARRATE
      for v in finalcontent:
        assert isinstance(v, (StringLiteral, TextFragmentLiteral))
      emit_content = VNASTSayNode.create(context=self.context, nodetype=nodetype, content=finalcontent, expression=expr, sayer=sayer, raw_content=content, name=leading_element.name, loc=leading_element.location)
    else:
      # 文本不符合预期内容，所有文本就当作没有指定发言者和状态、表情的内容
      emit_content = VNASTSayNode.create(context=self.context, nodetype=VNASTSayNodeType.TYPE_NARRATE, content=content, raw_content=content, name=leading_element.name, loc=leading_element.location)
    state.emit_node(emit_content)
    return emit_content

  def emit_asm_node(self, state : VNASTParsingState, backingop : Operation, code : list[StringLiteral], backend : StringLiteral | None = None):
    body = StringListLiteral.get(self.context, value=code)
    result = VNASTASMNode.create(self.context, body=body, backend=backend, name=backingop.name, loc=backingop.location)
    state.emit_node(result)

  def emit_transition_node(self, state : VNASTParsingState, backingop : Operation, transition : CallExprOperand | None) -> VNASTTransitionNode:
    if transition is None:
      result = VNASTTransitionNode.create(context=self.context, transition_name=None, name=backingop.name, loc=backingop.location)
      state.emit_node(result)
      return result
    assert isinstance(transition, CallExprOperand)
    result = VNASTTransitionNode.create(context=self.context, transition_name=transition.name, name=backingop.name, loc=backingop.location)
    for a in transition.args:
      if isinstance(a, Literal):
        result.add_arg(a)
      else:
        state.emit_error('vnparser-unexpected-argument-in-transition', transition.name + ': "' + str(a) + '"', loc=backingop.location)
    for k, v in transition.kwargs.items():
      if isinstance(v, Literal):
        name = StringLiteral.get(k, state.context)
        result.add_kwarg(name, v)
      else:
        state.emit_error('vnparser-unexpected-argument-in-transition', transition.name + ' arg "' + k +'": "' + str(v) + '"', loc=backingop.location)
    state.emit_node(result)
    return result

  def emit_pending_assetref(self, state : VNASTParsingState, backingop : Operation, ref : CallExprOperand) -> VNASTPendingAssetReference:
    refname = StringLiteral.get(ref.name, state.context)
    args : list[Literal] = []
    kwargs : dict[str, Literal] = {}
    for a in ref.args:
      if isinstance(a, Literal):
        args.append(a)
      else:
        state.emit_error('vnparser-unexpected-argument-in-assetref', ref.name + ': "' + str(a) + '"', loc=backingop.location)
    for k, v in ref.kwargs.items():
      if isinstance(v, Literal):
        kwargs[k] = v
      else:
        state.emit_error('vnparser-unexpected-argument-in-assetref', ref.name + ' arg "' + k +'": "' + str(v) + '"', loc=backingop.location)
    return VNASTPendingAssetReference.get(value=refname, args=args, kwargs=kwargs, context=state.context)

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
            result = VNASTAssetReference.create(context=self.context, name=op.name, loc=op.location, kind=VNASTAssetKind.KIND_AUDIO, operation=VNASTAssetIntendedOperation.OP_PUT, asset=firstvalue, transition=None)
            state.emit_node(result)
          last_say = None
        elif isinstance(firstvalue, ImageAssetData):
          # 内嵌图片
          try_emit_pending_content()
          last_say = None
          assert op.content.get_num_operands() == 1
          result = VNASTAssetReference.create(context=self.context, name=op.name, loc=op.location, kind=VNASTAssetKind.KIND_IMAGE, operation=VNASTAssetIntendedOperation.OP_CREATE, asset=firstvalue, transition=VNDefaultTransitionType.DT_IMAGE_SHOW.get_enum_literal(state.context))
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
    # 如果 IR 没有赋予名称，就用遇到的第一个文档的名字
    if len(doc.name) > 0:
      if len(self.ast.name) == 0:
        self.ast.name = doc.name
    # 开始解析
    while block := state.get_next_input_block():
      self.handle_block(state, block)
    # 以下操作需要对每个文件进行
    # 目前我们在这里只做默认函数创建
    self.run_create_default_function(state.output_current_file)

  def run_create_default_function(self, file : VNASTFileInfo):
    # 如果该文件满足以下条件:
    # 1. 该文件没有定义任何函数
    # 2. 该文件内存在只在函数内有意义的结点
    #     （比如发言，选单，等等命令）
    # 则我们创建一个与文件同名的函数，把所有的内容都放在这个函数里
    if len(file.functions.body) > 0:
      return
    is_functionlocal_node_found = False
    for op in file.pending_content.body:
      if isinstance(op, VNASTNodeBase):
        if type(op).TRAIT_FUNCTION_CONTEXT_ONLY:
          is_functionlocal_node_found = True
          break
    if not is_functionlocal_node_found:
      return
    # 确定执行这个转换
    func = VNASTFunction.create(context=self.context, name=file.name, loc=file.location)
    file.functions.push_back(func)
    func.body.take_body(file.pending_content)
    # 结束

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
    # print('Command ' + cmdinfo.cname + ': target_cb=' + str(target_cb) + ', args=' + str(target_args) + ', kwargs=' + str(target_kwargs) + ', warnings=' + str(target_warnings))
    target_cb(*target_args, **target_kwargs)
    return

# 把 VNParser 的定义包含进去，这样后面的类型标注可以顺利进行
_imports = globals()

# ------------------------------------------------------------------------------
# 内容声明命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, _imports, 'DeclImage', alias={
  '声明图片': {'name': '名称', 'path': '路径'}, # zh_CN
  "聲明圖片": {"name": "名稱", 'path': '路徑'}, # zh_HK
})
def cmd_image_decl_path(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str, path : str):
  warnings : list[tuple[str,str]] = []
  img = emit_image_expr_from_path(context=state.context, pathexpr=path, basepath=state.input_file_path, warnings=warnings)
  for code, msg in warnings:
    state.emit_error(code, msg, commandop.location)
  if img is None:
    # 找不到图片，生成一个错误
    state.emit_error('vnparse-image-notfound', path, loc=commandop.location)
    return
  if existing := state.output_current_file.assetdecls.get(name):
    state.emit_error('vnparse-nameclash-imagedecl', 'Image "' + name + '" already exist: ' + str(existing.asset.get()), loc=commandop.location)
  else:
    symb = VNASTAssetDeclSymbol.create(state.context, kind=VNASTAssetKind.KIND_IMAGE, asset=img, name=name, loc=commandop.location)
    state.output_current_file.assetdecls.add(symb)
  return


@CommandDecl(vn_command_ns, _imports, 'DeclImage', alias={
  '声明图片': {'name': '名称', 'source': '来源'}, # zh_CN
  "聲明圖片": {"name": "名稱", "source": "來源"}, # zh_HK
})
def cmd_image_decl_src(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str, source : CallExprOperand):
  wlist : list[tuple[str, str]] = []
  img = emit_image_expr_from_callexpr(context=state.context, call=source, placeholderdest=ImageExprPlaceholderDest.DEST_UNKNOWN, warnings=wlist, screen_resolution=parser.resolution)
  if img is None:
    state.emit_error('vnparse-imageexpr-invalid', str(source), loc=commandop.location)
    return
  if existing := state.output_current_file.assetdecls.get(name):
    state.emit_error('vnparse-nameclash-imagedecl', 'Image "' + name + '" already exist: ' + str(existing.asset.get()), loc=commandop.location)
  else:
    symb = VNASTAssetDeclSymbol.create(state.context, kind=VNASTAssetKind.KIND_IMAGE, asset=img, name=name, loc=commandop.location)
    state.output_current_file.assetdecls.add(symb)
  return

@CommandDecl(vn_command_ns, _imports, 'DeclVariable', alias={
  '声明变量' : {'name': '名称', 'type': '类型', 'initializer': '初始值'}, # zh_CN
  "聲明變量" : {"name": "名稱", "type": "類型", "initializer": "初始值"}, # zh_HK
})
# pylint: disable=redefined-builtin
def cmd_variable_decl(parser: VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str, type : str, initializer : str):
  if existing := state.output_current_file.variables.get(name):
    state.emit_error('vnparse-nameclash-variabledecl', 'Variable "' + name + '" already exist: type=' + existing.vtype.get().get_string() + ' initializer=' + existing.initializer.get().get_string(), commandop.location)
    return
  symb = VNASTVariableDeclSymbol.create(context=state.context, vtype=type, initializer=initializer, name=name, loc=commandop.location)
  state.output_current_file.variables.add(symb)

@CommandDecl(vn_command_ns, _imports, 'DeclCharacter', alias={
  '声明角色' : {'name': '姓名'}, # zh_CN
  "聲明角色" : {"name": "姓名"}, # zh_HK
})
def cmd_character_decl(parser: VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str, ext : ListExprOperand):
  # 声明角色仅用于提供角色的身份
  # 在前端命令上可以身份+显示方式（比如显示名称，名字颜色等）一并设置，也可以只用该指令设定身份，用后面的“设置角色发言属性”来提供其他信息
  if existing := state.output_current_file.characters.get(name):
    state.emit_error('vnparse-nameclash-characterdecl', 'Character "' + name + '" already exist', loc=commandop.location)
    return
  ch = VNASTCharacterSymbol.create(context=state.context, name=name, loc=commandop.location)
  state.output_current_file.characters.add(ch)
  if ext is not None:
    if isinstance(ext.data, collections.OrderedDict):
      # 有具体的发言信息
      defaultsay = VNASTCharacterSayInfoSymbol.create(state.context, name, commandop.location)
      ch.sayinfo.add(defaultsay)
      for k, v in ext.data.items():
        if k in ("Sprite", "立绘", "立繪"):
          # 这里开始是指定场景背景的信息
          _helper_parse_image_exprtree(parser, state, v, ch.sprites, ImageExprPlaceholderDest.DEST_CHARACTER_SPRITE, commandop.location)
          continue
        if k in ("SideImage", "头像", "頭像"):
          _helper_parse_image_exprtree(parser, state, v, ch.sideimages, ImageExprPlaceholderDest.DEST_CHARACTER_SIDEIMAGE, commandop.location)
          continue
        if k in ("Say", "发言", "發言"):
          _helper_parse_character_sayinfo(state=state, v=v, say=defaultsay, loc=commandop.location)
          continue
        if k in ("SayAlternativeName", "发言别名", "發言別名"):
          _helper_parse_character_alternativesay(state=state, v=v, sayinfo=ch.sayinfo, defaultsay=defaultsay, loc=commandop.location)
          continue
        # 到这就说明当前的键值没有匹配到认识的
        state.emit_error('vnparse-characterdecl-invalid-expr', 'Unexpected key "' + k + '"', loc=commandop.location)
    else:
      # ext.data 无效，记一下错误
      state.emit_error('vnparse-characterdecl-invalid-expr', 'Unexpected attached list format', loc=commandop.location)

def _helper_merge_textstyle(context : Context, srcoperand : OpOperand[TextStyleLiteral], attr : TextAttribute, v : typing.Any) -> TextStyleLiteral:
  srcdict = {}
  if src := srcoperand.try_get_value():
    for t in src.value:
      srcdict[t[0]] = t[1]
  srcdict[attr] = v
  return TextStyleLiteral.get(TextStyleLiteral.get_style_tuple(srcdict), context)

def _helper_parse_color(state : VNASTParsingState, v : str, loc : Location, contextstr : str = '') -> Color | None:
  try:
    color = Color.get(v)
    return color
  except AttributeError:
    msg = 'Invalid color string: "' + v + '"'
    if len(contextstr) > 0:
      msg = contextstr + ': ' + msg
    state.emit_error(code='vnparse-invalid-colorstr', msg=msg, loc=loc)
  return None

def _helper_parse_character_alternativesay(state : VNASTParsingState, v : typing.Any, sayinfo : SymbolTableRegion[VNASTCharacterSayInfoSymbol], defaultsay : VNASTCharacterSayInfoSymbol | None, loc : Location):
  if isinstance(v, list):
    for altname in v:
      if existing := sayinfo.get(altname):
        continue
      altnode = VNASTCharacterSayInfoSymbol.create(context=state.context, name=altname, loc=loc)
      if defaultsay is not None:
        altnode.copy_from(defaultsay)
      sayinfo.add(altnode)
  elif isinstance(v, collections.OrderedDict):
    for altname, alttree in v.items():
      if existing := sayinfo.get(altname):
        continue
      altnode = VNASTCharacterSayInfoSymbol.create(context=state.context, name=altname, loc=loc)
      if defaultsay is not None:
        altnode.copy_from(defaultsay)
      sayinfo.add(altnode)
      _helper_parse_character_sayinfo(state=state, v=alttree, say=altnode, loc=loc)
  else:
    raise RuntimeError("Should not happen")

def _helper_parse_character_sayinfo(state : VNASTParsingState, v : typing.Any, say : VNASTCharacterSayInfoSymbol, loc : Location):
  if isinstance(v, collections.OrderedDict):
    for attr, value in v.items():
      if attr in ("NameColor", "名字颜色", "名字顏色"):
        if c := _helper_parse_color(state, value, loc):
          newstyle = _helper_merge_textstyle(state.context, say.namestyle, TextAttribute.TextColor, c)
          say.namestyle.set_operand(0, newstyle)
        continue
      if attr in ("ContentColor", "内容颜色", "內容顏色"):
        if c := _helper_parse_color(state, value, loc):
          newstyle = _helper_merge_textstyle(state.context, say.saytextstyle, TextAttribute.TextColor, c)
          say.saytextstyle.set_operand(0, newstyle)
        continue
      state.emit_error('vnparse-characterdecl-invalid-expr', 'Say subtree: Unexpected attribute "' + attr + '"', loc=loc)
  else:
    # 发言应该是一个字典；这里报错
    state.emit_error('vnparse-characterdecl-invalid-expr', 'Unexpected data format for Say attribute (should be a dictionary)', loc=loc)

# 这个命令暂时不做
#@CommandDecl(vn_co mmand_ns, _imports, 'DeclCharacterSprite', alias={
#  '声明角色立绘' : {'character_state_expr': '角色与状态表达式', 'image': '图片'}, # zh_CN
#})
#def cmd_character_sprite_decl(parser : VNParser, commandop : GeneralCommandOp, character_state_expr : CallExprOperand | str, image : str):
  # 定义一个角色的外观状态（一般是立绘差分，比如站姿、衣着、等），使得角色变换状态时能够切换立绘
  # 这必须是一个独立于角色声明的操作，因为更多角色外观等可以通过DLC等形式进行补足，所以它们可能处于不同的命名空间中
  # 在实际的内容中，一个角色的状态标签会有很多（包含衣着、站姿、表情等），
  # 我们先把这里声明的角色标签给匹配掉，剩余的标签喂给图像参数（应该是带差分的多层图片）
  # 我们预计用本命令指定角色的基础外观（比如站姿、衣着，确定哪组立绘），剩下的用来在立绘中选表情匹配的差分
  # 虽然我们基本上只用一个“状态标签”参数来进行匹配，但对人物而言，我们要求最后一个标签代表表情，
  # 这样文中可以用<人名><表情><内容>的方式来表达说明，并且表情标签所替代的标签没有歧义
  # （我们也可以支持表情标签的层级，永远从最右侧替换）
#  pass

@CommandDecl(vn_command_ns, _imports, 'SetTemporarySayAttr', alias={
  '设置临时发言属性' : {'display_name': '显示名', 'actual_character': '实际角色',}, # zh_CN
  "設置臨時發言屬性" : {"display_name": "顯示名", "actual_character": "實際角色",}, # zh_HK
})
def cmd_temp_say_attr(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, *, display_name : str, actual_character : str, ext : ListExprOperand | None = None):
  # 定义一个角色说话时名称、发言内容的显示方式
  # 一般情况下在声明角色时就可以定义所有内容，不过我们偶尔要让同一个人的显示名或是其他属性变化一下
  # (比如刚出场时名字显示为 "???")
  # 在这种时候我们就要用此命令来让该角色可以用不同的名字显示发言
  # 注意，这里的发言属性会生效直到函数结束或者文件结束，取决于该结点在不在函数体里面
  # 如果有多个角色共用相同的特殊显示名，则需要在标注角色状态信息时把实际角色填上才能避免重名，比如: ???(苏语涵):你好！
  # 后置列表和声明角色时“发言”分支下的处理是一样的
  parent = VNASTCharacterTempSayAttrNode.create(context=state.context, character=actual_character, name=commandop.name, loc=commandop.location)
  state.emit_node(parent)
  info = VNASTCharacterSayInfoSymbol.create(state.context, name=display_name, loc=commandop.location)
  parent.sayinfo.add(info)
  if ext is not None:
    _helper_parse_character_sayinfo(state, ext.data, info, commandop.location)

@CommandDecl(vn_command_ns, _imports, 'DeclScene', alias={
  '声明场景' : {'name': '名称'}, # zh_CN
  "聲明場景" : {"name": "名稱"}, # zh_HK
})
def cmd_scene_decl(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str, ext : ListExprOperand | None = None):
  if existing := state.output_current_file.scenes.get(name):
    state.emit_error('vnparse-nameclash-scenedecl', 'Scene "' + name + '" already exist', loc=commandop.location)
    return
  scene = VNASTSceneSymbol.create(context=state.context, name=name, loc=commandop.location)
  state.output_current_file.scenes.add(scene)
  if ext is not None:
    if isinstance(ext.data, collections.OrderedDict):
      for k, v in ext.data.items():
        if k in ('Background', '背景'):
          # 这里开始是指定场景背景的信息
          _helper_parse_image_exprtree(parser, state, v, scene.backgrounds, ImageExprPlaceholderDest.DEST_SCENE_BACKGROUND, commandop.location)
          continue
        # 到这就说明当前的键值没有匹配到认识的
        state.emit_error('vnparse-scenedecl-invalid-expr', 'Unexpected key "' + k + '"', loc=commandop.location)
    else:
      # ext.data 无效，记一下错误
      state.emit_error('vnparse-scenedecl-invalid-expr', 'Unexpected attached list format', loc=commandop.location)

def _get_placeholder_desc_for_missing_img(context : Context, v : str):
  return StringLiteral.get("Image not found: "+ v, context)

def _helper_parse_image_exprtree(parser : VNParser, state : VNASTParsingState, v : collections.OrderedDict[str, typing.Any] | str, statetree : SymbolTableRegion[VNASTNamespaceSwitchableValueSymbol], placeholderdest : ImageExprPlaceholderDest, loc : Location):
  # 如果是一个词典，那么是个和角色立绘差不多的树状结构，每个子节点根一个图案表达式
  # 如果是一个值，那么只有一个图片
  # 首先把一个值的情况解决了
  warnings : list[tuple[str,str]] = []
  nstuple = None
  if ns :=state.output_current_file.namespace.try_get_value():
    nsstr = ns.get_string()
    nstuple = VNNamespace.expand_namespace_str(nsstr)
  nsstr = VNNamespace.stringize_namespace_path(nstuple) if nstuple is not None else '/'
  def submit_expr(statestr : str, expr : Value):
    nonlocal statetree
    node = statetree.get(statestr)
    if node is None:
      node = VNASTNamespaceSwitchableValueSymbol.create(state.context, name=statestr, defaultvalue=expr, loc=loc)
      statetree.add(node)
    node.set_value(nsstr, expr)

  if isinstance(v, str):
    expr = emit_image_expr_from_str(context=state.context, s=v, basepath=state.input_file_path, placeholderdest=placeholderdest, warnings=warnings, screen_resolution=parser.resolution)
    if expr is None:
      expr = emit_default_placeholder(context=state.context, dest=placeholderdest, screen_resolution=parser.resolution, description=_get_placeholder_desc_for_missing_img(state.context, v))
      state.emit_error(code='vnparse-invalid-imageexpr', msg=v, loc=loc)
    submit_expr('', expr)
  elif isinstance(v, collections.OrderedDict):
    state_stack = []
    def walk_dict(d : collections.OrderedDict):
      for k, v in d.items():
        if isinstance(v, str):
          expr = emit_image_expr_from_str(context=state.context, s=v, basepath=state.input_file_path, placeholderdest=placeholderdest, warnings=warnings, screen_resolution=parser.resolution)
          if expr is None:
            expr = emit_default_placeholder(context=state.context, dest=placeholderdest, screen_resolution=parser.resolution, description=_get_placeholder_desc_for_missing_img(state.context, v))
            state.emit_error(code='vnparse-invalid-imageexpr', msg=v, loc=loc)
          tmpstatelist = [*state_stack, k]
          submit_expr(','.join(tmpstatelist), expr)
        elif isinstance(v, collections.OrderedDict):
          state_stack.append(k)
          walk_dict(v)
          state_stack.pop()
        else:
          state.emit_error(code='vnparse-invalid-imageexpr', msg=str(v), loc=loc)
    walk_dict(v)
  else:
    state.emit_error(code='vnparse-invalid-imageexpr', msg=str(v), loc=loc)

  for t in warnings:
    code, msg = t
    state.emit_error(code=code, msg=msg, loc=loc)

# 相同的功能可以在声明场景中完成，暂时不做
#@CommandDecl(vn_command_ns, _imports, 'DeclSceneBackground', alias={
#  '声明场景背景' : {'scene': '场景', 'state_tags' : '状态标签', 'background_image' : '背景图片'}, # zh_CN
#})
#def cmd_scene_background_decl(parser : VNParser, commandop : GeneralCommandOp, scene : str, state_tags : str, background_image : str):
  # 给场景定义一个可显示状态，使得“切换场景”可以更改背景
#  pass

@CommandDecl(vn_command_ns, _imports, 'DeclAlias', alias={
  '声明别名' : {'alias_name': '别名名称', 'target':'目标'}, # zh_CN
  "聲明別名" : {"alias_name": "別名名稱", "target":"目標"}, # zh_HK
})
def cmd_alias_decl(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, alias_name : str, target : str):
  # (仅在解析时用到，不会在IR中)
  # 给目标添加别名（比如在剧本中用‘我’指代某个人）
  # 别名都是文件内有效，出文件就失效。（实在需要可以复制黏贴）
  node = VNASTTempAliasNode.create(context=state.context, alias=alias_name, target=target, name=commandop.name, loc=commandop.location)
  state.emit_node(node)

# ------------------------------------------------------------------------------
# 内容操作命令
# ------------------------------------------------------------------------------

@CommandDecl(vn_command_ns, _imports, 'ASM', alias={
  '内嵌汇编': {'content': '内容', 'backend': '后端'}, # zh_CN
  "內嵌匯編": {"content": "内容", "backend": "後端"}, # zh_HK
})
def cmd_asm_1(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, content : str, backend : str):
  # 单行内嵌后端命令
  if isinstance(backend, str):
    backend_l = StringLiteral.get(backend, state.context)
  else:
    assert isinstance(backend, StringLiteral)
    backend_l = backend
  parser.emit_asm_node(state, commandop, code=[StringLiteral.get(content, state.context)], backend=backend_l)

@CommandDecl(vn_command_ns, _imports, 'ASM', alias={
  '内嵌汇编': {'backend': '后端'}, # zh_CN
  "內嵌匯編": {"backend": "後端"}, # zh_HK
})
def cmd_asm_2(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, ext : SpecialBlockOperand, backend : str):
  # 使用特殊块的后端命令
  code = []
  block : IMSpecialBlockOp = ext.original_op
  assert isinstance(block, IMSpecialBlockOp)
  for u in block.content.operanduses():
    code.append(u.value)
  if isinstance(backend, str):
    backend_l = StringLiteral.get(backend, state.context)
  else:
    assert isinstance(backend, StringLiteral)
    backend_l = backend
  parser.emit_asm_node(state, commandop, code=code, backend=backend_l)

@CommandDecl(vn_command_ns, _imports, 'CharacterEnter', alias={
  '角色入场': {'characters': '角色', 'transition': '转场'}, # zh_CN
  "角色入場": {"characters": "角色", "transition": "轉場"}, # zh_HK
})
def cmd_character_entry(parser : VNParser, state: VNASTParsingState, commandop : GeneralCommandOp, characters : list[CallExprOperand], transition : CallExprOperand = None):
  transition = parser.emit_transition_node(state, commandop, transition)
  for chexpr in characters:
    charname = chexpr.name
    states = []
    for a in chexpr.args:
      if isinstance(a, str):
        states.append(StringLiteral.get(a, state.context))
      elif isinstance(a, StringLiteral):
        states.append(a)
      else:
        state.emit_error('vnparser-unexpected-argument', 'CharacterEnter ' + charname + ': argument "' + str(a) + '" ignored', loc=commandop.location)
    node = VNASTCharacterEntryNode.create(state.context, character=charname, states=states, name=commandop.name, loc=commandop.location)
    transition.push_back(node)

#def cmd_wait_finish(parser : VNParser, commandop : GeneralCommandOp):
#  pass

@CommandDecl(vn_command_ns, _imports, 'CharacterExit', alias={
  '角色退场': {'characters': '角色', 'transition': '转场'}, # zh_CN
  "角色退場": {"characters": "角色", "transition": "轉場"}, # zh_HK
})
def cmd_character_exit(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, characters : list[CallExprOperand], transition : CallExprOperand = None):
  # 如果退场时角色带有状态，我们先把角色的状态切换成目标状态，然后再创建一个 Transition 结点存放真正的退场
  characters_list : list[StringLiteral] = []
  for ch in characters:
    if len(ch.args) > 0 or len(ch.kwargs) > 0:
      cmd_switch_character_state(parser, state, commandop, ch)
    characters_list.append(StringLiteral.get(ch.name, state.context))
  transition = parser.emit_transition_node(state, commandop, transition)
  for chname in characters_list:
    node = VNASTCharacterExitNode.create(state.context, chname, name='', loc=commandop.location)
    transition.push_back(node)

@CommandDecl(vn_command_ns, _imports, 'SpecialEffect', alias={
  '特效': {'effect': '特效'} # zh_CN, zh_HK
})
def cmd_special_effect(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, effect : CallExprOperand):
  ref = parser.emit_pending_assetref(state, commandop, effect)
  result = VNASTAssetReference.create(context=state.context, kind=VNASTAssetKind.KIND_EFFECT, operation=VNASTAssetIntendedOperation.OP_PUT, asset=ref, transition=None, name=commandop.name, loc=commandop.location)
  state.emit_node(result)

def _helper_collect_character_expr(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, expr : CallExprOperand) -> list[StringLiteral]:
  # 将描述角色状态的 CallExprOperand 转化为字符串数组
  deststate : list[StringLiteral] = []
  for arg in expr.args:
    if isinstance(arg, StringLiteral):
      deststate.append(arg)
    else:
      state.emit_error('vnparser-unexpected-argument-in-character-expr', expr.name + ': "' + str(arg) + '"', loc=commandop.location)
  # 目前我们不支持提取 kwargs
  for k, v in expr.kwargs.items():
    state.emit_error('vnparser-unexpected-argument-in-character-expr', expr.name + ': "' + k + '"=' + str(v), loc=commandop.location)
  return deststate

def _helper_collect_scene_expr(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, expr : CallExprOperand) -> list[StringLiteral]:
  # 将描述场景状态的 CallExprOperand 转化为字符串数组
  # 这个和角色的一样，所以直接引用了
  return _helper_collect_character_expr(parser, state, commandop, expr)

@CommandDecl(vn_command_ns, _imports, 'SwitchCharacterState', alias={
  '切换角色状态': {'state_expr': '状态表达式'}, # zh_CN
  "切換角色狀態": {"state_expr": "狀態表達式"}, # zh_HK
})
def cmd_switch_character_state(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, state_expr : list[str] | CallExprOperand):
  # 如果是个调用表达式，则角色名是调用的名称
  # 如果是一串标签字符串，则更改默认发言者的状态
  # 优先匹配一串字符串
  # 一般来说切换角色状态都是立即发生的，不会有渐变的动画
  # 如果有立绘姿势、服装改变的话也是，顶多是下场+上场，所以这里我们不需要转场效果
  character = None
  if isinstance(state_expr, list):
    deststate = []
    for v in state_expr:
      assert isinstance(v, str)
      deststate.append(StringLiteral.get(v, state.context))
  elif isinstance(state_expr, CallExprOperand):
    character = state_expr.name
    deststate = _helper_collect_character_expr(parser, state, commandop, state_expr)
  else:
    raise RuntimeError("Should not happen")
  result = VNASTCharacterStateChangeNode.create(context=state.context, character=character, deststate=deststate, name=commandop.name, loc=commandop.location)
  state.emit_node(result)

@CommandDecl(vn_command_ns, _imports, 'SwitchScene', alias={
  '切换场景': {'scene': '场景', 'transition': '转场'}, # zh_CN
  "切換場景": {"scene": "場景", "transition": "轉場"}, # zh_HK
})
def cmd_switch_scene(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, scene: CallExprOperand, transition : CallExprOperand = None):
  transition = parser.emit_transition_node(state, commandop, transition)
  scenestates = _helper_collect_scene_expr(parser, state, commandop, scene)
  node = VNASTSceneSwitchNode.create(context=state.context, destscene=scene.name, states=scenestates)
  transition.push_back(node)

@CommandDecl(vn_command_ns, _imports, 'HideImage', alias={
  "收起图片": {"image_name": "图片名", "transition": "转场"}, # zh_CN
  "收起圖片": {"image_name": "圖片名", "transition": "轉場"}, # zh_HK
})
def cmd_hide_image(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, image_name : str, transition : CallExprOperand = None):
  transition = parser.emit_transition_node(state, commandop, transition)
  ref = VNASTPendingAssetReference.get(value=image_name, args=None, kwargs=None, context=state.context)
  node = VNASTAssetReference.create(context=state.context, kind=VNASTAssetKind.KIND_IMAGE, operation=VNASTAssetIntendedOperation.OP_REMOVE, asset=ref, transition=VNDefaultTransitionType.DT_IMAGE_HIDE.get_enum_literal(state.context), name=commandop.name, loc=commandop.location)
  transition.push_back(node)

@CommandDecl(vn_command_ns, _imports, 'SetBGM', alias={
  "设置背景音乐": {"bgm": "音乐"}, # zh_CN
  "設置背景音樂": {"bgm": "音樂"}, # zh_HK
})
def cmd_set_bgm(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, bgm : str | AudioAssetData):
  if isinstance(bgm, str):
    result_bgm = VNASTPendingAssetReference.get(value=bgm, args=None, kwargs=None, context=state.context)
  elif isinstance(bgm, AudioAssetData):
    result_bgm = bgm
  node = VNASTSetBackgroundMusicNode.create(context=state.context, bgm=result_bgm, transition=VNDefaultTransitionType.DT_BGM_CHANGE.get_enum_literal(state.context), name=commandop.name, loc=commandop.location)
  state.emit_node(node)

# ------------------------------------------------------------------------------
# 控制流相关的命令
# ------------------------------------------------------------------------------
@CommandDecl(vn_command_ns, _imports, 'Function', alias={
  ('Function', 'Section') : {}, # en
  ('函数', '章节') : {'name': '名称'}, # zh_CN
  ("函數", "章節") : {"name": "名稱"}, # zh_HK
})
def cmd_set_function(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str):
  # 如果我们在(1)该文件还没有函数或(2)现在正在一个函数体中时，我们创建一个新函数，从那里开始构建
  # 如果此时我们在一个函数的某个控制流分支里(比如选单的某个分支内)，我们除了上述操作外还得在当前位置添加一个调用
  func = VNASTFunction.create(context=state.context, name=name, loc=commandop.location)
  state.output_current_file.functions.push_back(func)
  if state.output_current_region is None:
    # 当前没有函数
    # 我们尝试把此命令之前的内容给转移进该函数
    if len(state.output_current_file.pending_content.body) > 0:
      func.prebody_md.take_body(state.output_current_file.pending_content)
  elif isinstance(state.output_current_region, VNASTFunction):
    # 我们现在正在一个函数的主体内
    # 什么都不做
    pass
  else:
    # 我们在一个分支里
    # 添加一个对该函数的调用
    callnode = VNASTCallNode.create(context=state.context, callee=name)
    state.emit_node(callnode)
  state.output_current_region = func

@CommandDecl(vn_command_ns, _imports, 'CallFunction', alias={
  '调用函数': {'name': '名称'}, # zh_CN
  "調用函數": {"name": "名稱"}, # zh_HK
})
def cmd_call_function(parser: VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str):
  # 如果当前在函数体内就生成一个调用结点，否则什么也不做
  if state.output_current_region is None:
    return
  callnode = VNASTCallNode.create(context=state.context, callee=name)
  state.emit_node(callnode)

@CommandDecl(vn_command_ns, _imports, 'TailCall', alias={
  ('转至函数', '转至章节'): {'name': '名称'}, # zh_CN
  ("轉至函數", "轉至章節"): {"name": "名稱"}, # zh_HK
})
def cmd_tailcall(parser: VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str):
  # 如果当前在函数体内就生成一个调用结点，否则什么也不做
  if state.output_current_region is None:
    return
  callnode = VNASTCallNode.create(context=state.context, callee=name)
  callnode.set_attr(VNASTCallNode.ATTR_TAILCALL, True)
  state.emit_node(callnode)

@CommandDecl(vn_command_ns, _imports, 'Jump', alias={
  '转至标签': {'name': '名称'}, # zh_CN
  "轉至標簽": {"name": "名稱"}, # zh_HK
})
def cmd_jump(parser: VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str):
  if len(name) == 0:
    state.emit_error(code='vnparse-expect-name', msg='Jump expects non-empty dest label', loc=commandop.location)
  node = VNASTJumpNode.create(context=state.context, target=name)
  state.emit_node(node)

@CommandDecl(vn_command_ns, _imports, 'Label', alias={
  '标签': {'name': '名称'}, # zh_CN
  "標簽": {"name": "名稱"}, # zh_HK
})
def cmd_label(parser: VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, name : str):
  if len(name) == 0:
    state.emit_error(code='vnparse-expect-name', msg='Label expects non-empty label name', loc=commandop.location)
  node = VNASTLabelNode.create(context=state.context, labelname=name)
  state.emit_node(node)

@FrontendParamEnum(alias={
  "CONTINUE": { "continue", "继续", "繼續"},
  "LOOP": {"loop", "循环", "循環"},
})
class _SelectFinishActionEnum(enum.Enum):
  CONTINUE = 0 # 默认继续执行分支后的内容（默认值）
  LOOP = 1 # 循环到选项开始（用于类似Q/A，可以反复选择不同选项。可由跳出命令结束）

@CommandDecl(vn_command_ns, _imports, 'Select', alias={
  "选项": {"name": "名称", "finish_action": "结束动作"}, # zh_CN
  "選項": {"name": "名稱", "finish_action": "結束動作"}, # zh_CN
})
def cmd_select(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, ext : ListExprOperand, name : str, finish_action : _SelectFinishActionEnum = _SelectFinishActionEnum.CONTINUE):
  # 该命令应该这样使用：
  # 【选项 名称=。。。】
  #     * <选项1文本>
  #       - <选项1段落1>
  #       - <选项1段落2>
  #       ...
  #     * <选项2文本>
  #       - <选项2段落1>
  #       - <选项2段落2>
  #       ...
  # 原来的 IMListOp 应该像是这样：
  # [IMListOp root]
  #    R: '1'
  #       B: '': [IMElementOp <选项1文本>]
  #       B: '': [IMListOp]
  #                 R: '1'
  #                   B: '': [IMElementOp <选项1段落1>]
  #                 R: '2'
  #                   B: '': [IMElementOp <选项1段落2>]
  #                 ...
  #    R: '2'
  #       B: '': [IMElementOp <选项2文本>]
  #       B: '': [IMListOp]
  #                 R: '1'
  #                   B: '': [IMElementOp <选项2段落1>]
  #                 R: '2'
  #                   B: '': [IMElementOp <选项2段落2>]
  #                 ...
  def extract_option_title_str(frontblock : Block, result : list[Value]) -> Location | None:
    # result 由调用的代码提供
    firstloc : Location | None = None
    for op in frontblock.body:
      if isinstance(op, IMElementOp):
        firstloc = op.location
        for u in op.content.operanduses():
          value = u.value
          if isinstance(value, (StringLiteral, TextFragmentLiteral)):
            result.append(value)
    return firstloc

  node = VNASTMenuNode.create(context=state.context, name=name, loc=commandop.location)
  state.emit_node(node)
  match finish_action:
    case _SelectFinishActionEnum.CONTINUE:
      pass
    case _SelectFinishActionEnum.LOOP:
      node.set_attr(VNASTMenuNode.ATTR_FINISH_ACTION, VNASTMenuNode.ATTR_FINISH_ACTION_LOOP)
    case _:
      raise RuntimeError('should not happen')
  listop : IMListOp = ext.original_op
  assert isinstance(listop, IMListOp)
  num_options = listop.get_num_regions()
  for i in range(0, num_options):
    regionname = str(i+1)
    r = listop.get_region(regionname)
    # 第一个块包含选项的文本内容
    front = r.blocks.front
    optiontitle = []
    loc = extract_option_title_str(front, optiontitle)
    codegen = node.add_option(optiontitle, loc)
    # 如果有第二个块的话，这个块应当包含另一个 IMListOp, 该选项选择之后的内容都在这个 IMListOp 里
    if bodyblock := front.get_next_node():
      childlist : IMListOp | None = None
      for op in bodyblock.body:
        if isinstance(op, IMListOp):
          childlist = op
          break
      if childlist is not None:
        childstate = dataclasses.replace(state, output_current_region=codegen)
        num_blocks = childlist.get_num_regions()
        for i in range(0, num_blocks):
          r = childlist.get_region(str(i+1))
          childstate.input_top_level_region = r
          childstate.input_current_block = r.blocks.front
          while block := childstate.get_next_input_block():
            parser.handle_block(childstate, block)

  # 结束

@CommandDecl(vn_command_ns, _imports, 'ExitLoop', alias={
  '跳出循环' : {}, # zh_CN
  "跳出循環" : {}, # zh_HK
})
def cmd_exit_loop(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp):
  # 用来在带循环的选项命令中跳出循环
  # 目前没有其他循环结构，只有这里用得到，以后可能会用在其他地方
  node = VNASTBreakNode.create(state.context, name=commandop.name, loc=commandop.location)
  state.emit_node(node)

@CommandDecl(vn_command_ns, _imports, 'Return', alias={
  ('FinishSection') : {},
  ("章节结束","函数返回") : {}, # zh_CN
  ("章節結束","函數返回") : {}, # zh_HK
})
def cmd_return(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp):
  node = VNASTReturnNode.create(state.context, name=commandop.name, loc=commandop.location)
  state.emit_node(node)

@CommandDecl(vn_command_ns, _imports, 'Switch', alias={
  "分支": {"condition": "条件"}, # zh_CN
  #"分支": {"condition": "條件"}, # zh_HK
})
def cmd_switch(parser : VNParser, commandop : GeneralCommandOp, ext : ListExprOperand, condition : str = None):
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
  "長發言": {"sayer": "發言者"}, # zh_HK
})
def cmd_long_speech_mode(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, sayer : CallExprOperand = None):
  sayerlist : list[StringLiteral] = []
  if sayer is not None:
    name = StringLiteral.get(sayer.name, state.context)
    sayerlist.append(name)
  node = VNASTSayModeChangeNode.create(context=state.context, target_mode=VNASTSayMode.MODE_LONG_SPEECH, specified_sayers=sayerlist)
  state.emit_node(node)
  # 如果长发言命令指定了状态改变，我们需要加状态改变的结点
  if sayer is not None:
    if len(sayer.args) > 0:
      statelist = []
      for a in sayer.args:
        if isinstance(a, StringLiteral):
          statelist.append(a)
        elif isinstance(a, TextFragmentLiteral):
          statelist.append(a.content)
      if len(statelist) > 0:
        statechange = VNASTCharacterStateChangeNode.create(context=state.context, character=sayer.name, deststate=sayer.args, loc=commandop.location)
        state.emit_node(statechange)

@CommandDecl(vn_command_ns, _imports, 'InterleaveSayer', alias={
  '交替发言': {'sayer': '发言者'}, # zh_CN
  "交替發言": {"sayer": "發言者"}, # zh_HK
})
def cmd_interleave_mode(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, sayer : list[CallExprOperand]):
  # 目前忽略额外状态，只记录名称
  # 如果提供了额外的角色状态，我们其实也可以先加一个角色状态切换
  sayerlist : list[StringLiteral] = []
  for s in sayer:
    name = StringLiteral.get(s.name, state.context)
    sayerlist.append(name)
  node = VNASTSayModeChangeNode.create(context=state.context, target_mode=VNASTSayMode.MODE_INTERLEAVED, specified_sayers=sayerlist)
  state.emit_node(node)

@CommandDecl(vn_command_ns, _imports, 'DefaultSayMode', alias={
  '默认发言模式': {}, # zh_CN
  "默認發言模式": {}, # zh_HK
})
def cmd_default_say_mode(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp):
  node = VNASTSayModeChangeNode.create(context=state.context, target_mode=VNASTSayMode.MODE_DEFAULT)
  state.emit_node(node)

# ------------------------------------------------------------------------------
# 其他命令
# ------------------------------------------------------------------------------

def _helper_collect_arguments(ctx : Context, operand : OpOperand) -> list[Value]:
  result : list[Value] = []
  # 如果有字符串内容，我们把它们并成 StringLiteral
  # 其他内容均保留
  prev_str = ''
  for u in operand.operanduses():
    v = u.value
    if isinstance(v, (StringLiteral, TextFragmentLiteral)):
      s = v.get_string()
      prev_str += s
    else:
      if len(prev_str) > 0:
        result.append(StringLiteral.get(prev_str, ctx))
        prev_str = ''
      result.append(v)
  if len(prev_str) > 0:
    result.append(StringLiteral.get(prev_str, ctx))
  return result

@CommandDecl(vn_command_ns, _imports, 'ExpandTable', alias={
  '表格展开': {'cmdname' : '命令名'}, # zh_CN
  "表格展開": {"cmdname" : "命令名"}, # zh_HK
})
def cmd_expand_table(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, cmdname : str, table : TableExprOperand):
  # 表格第一行是参数名
  # 如果第一列没有参数名，这列代表按位参数(positional argument)
  # 从第二行起，如果某一格是空白，则代表没有该参数
  tableop : IMTableOp = table.original_op
  assert isinstance(tableop, IMTableOp)
  rowcnt = tableop.rowcount.get().value
  colcnt = tableop.columncount.get().value
  if rowcnt < 2 or colcnt == 0:
    return # 忽略没有内容的表格
  has_positional_arg : bool = False
  kwarg_names : list[str] = []
  # 先读第一行，把命令参数信息读进来
  for col in range(0, colcnt):
    celloperand : OpOperand = tableop.get_cell_operand(0, col)
    curstr = ''
    for u in celloperand.operanduses():
      curstr += u.value.get_string()
    if len(curstr) == 0:
      # 这代表一个按位参数，只能是第一列
      if col == 0:
        has_positional_arg = True
      else:
        state.emit_error('vnparser-tableexpand-invalid-positionalarg', 'column ' + str(col+1), loc=commandop.location)
        return
    else:
      kwarg_names.append(curstr)
  # 然后读接下来的内容
  cmdnamel = StringLiteral.get(cmdname, state.context)
  for row in range(1, rowcnt):
    cmd = GeneralCommandOp.create(name='ExpandTable_' + str(row), loc=commandop.location, name_value=cmdnamel, name_loc=commandop.location)
    kwargindex = 0
    for col in range(0, colcnt):
      operand : OpOperand = tableop.get_cell_operand(row, col)
      values = _helper_collect_arguments(state.context, operand)
      if col == 0 and has_positional_arg:
        for v in values:
          cmd.add_positional_arg(v, commandop.location)
      else:
        argname = kwarg_names[kwargindex]
        kwargindex += 1
        # 如果没有值则直接忽视
        if len(values) > 0:
          if len(values) > 1:
            # 如果有多个值，只有第一个值保留，其他的都扔掉
            msg = 'row ' + str(row+1) + ', col ' + str(col+1) + ', discarded: ' + ', '.join(['"' + str(v) + '"' for v in values[1:]])
            state.emit_error('vnparser-tableexpand-excessive-args', msg, loc=commandop.location)
          cmd.add_keyword_arg(argname, values[0], commandop.location, commandop.location)
    parser.handle_command_op(state=state, op=cmd)

@CommandDecl(vn_command_ns, _imports, 'Comment', alias={
  '注释': {'comment' : '注释'}, # zh_CN
  "註釋": {"comment" : "註釋"}, # zh_HK
})
def cmd_comment(parser : VNParser, state : VNASTParsingState, commandop : GeneralCommandOp, comment : str):
  if rawstr := commandop.try_get_raw_arg():
    comment = rawstr
  node = CommentOp.create(comment=StringLiteral.get(comment, state.context), name=commandop.name, loc=commandop.location)
  state.emit_md(node)
