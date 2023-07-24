# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# This is the latest (2022-11-30) version of command parser; commandast.py and commandastparser.py is obsolete
from __future__ import annotations
import typing
import collections
import dataclasses
import re

import antlr4
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.ErrorListener import ConsoleErrorListener

from ._antlr_generated.CommandScanLexer      import CommandScanLexer
from ._antlr_generated.CommandScanParser     import CommandScanParser
from ._antlr_generated.CommandScanListener   import CommandScanListener
from ._antlr_generated.CommandParseLexer     import CommandParseLexer
from ._antlr_generated.CommandParseParser    import CommandParseParser
from ._antlr_generated.CommandParseListener  import CommandParseListener
from ._antlr_generated.CommandParseVisitor   import CommandParseVisitor

from ..irbase import *
from ..inputmodel import *
from ..pipeline import TransformBase, MiddleEndDecl
from ..exceptions import *

# 命令扫描（语法分析阶段）

# ------------------------------------------------------------------------------
# Command AST definition
# ------------------------------------------------------------------------------

@IRObjectJsonTypeName("cmd_positional_arg_op")
class CMDPositionalArgOp(Operation):
  # representing a positional argument
  # this is the only "value" without a name
  # everything else (keyword argument, the name of the command, etc) use CMDValueSymbol
  # operation location is the location of the name/value (start of the name for keyword args, start of the value for positional args)
  # we use a full op here to track the loc
  _value_operand : OpOperand

  def construct_init(self, *, value : Value, name: str = '', loc: Location = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_operand_with_value('value', value)

  def post_init(self) -> None:
    super().post_init()
    self._value_operand = self.get_operand_inst('value')

  @property
  def value(self):
    return self._value_operand.get()

  @staticmethod
  def create(name: str, loc : Location, value : Value):
    return CMDPositionalArgOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, value=value, name=name, loc=loc)

@IRObjectJsonTypeName("cmd_value_symbol_op")
class CMDValueSymbol(Symbol):
  # representing a value in the command, or an argument value
  # name is the value / argument name
  # operation location is the location of the name/value (start of the name for keyword args, start of the value for positional args)
  _value_operand : OpOperand

  def construct_init(self, *, value : Value, name: str = '', loc: Location = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_operand_with_value('value', value)

  def post_init(self) -> None:
    super().post_init()
    self._value_operand = self.get_operand_inst('value')

  @property
  def value(self) -> Value:
    return self._value_operand.get()

  @staticmethod
  def create(name: str, loc: Location, value : Value):
    return CMDValueSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, value=value, name=name, loc=loc)

@IRObjectJsonTypeName("cmd_call_ref_t")
class CommandCallReferenceType(StatelessType):
  # type of GeneralCommandOp so that it can be a value
  pass

@IRObjectJsonTypeName("cmd_general_cmd_op")
class GeneralCommandOp(Operation):
  # 所有能被识别的命令（能找到命令名以及参数列表）
  _head_region : SymbolTableRegion # name + raw_args (raw args make life easier for commands with custom parsing)
  _positionalarg_region : Region # single block, list of values
  _positionalarg_block : Block
  _keywordarg_region : SymbolTableRegion
  _nested_callexpr_region : Region # single block, list of inner GeneralCommandOp
  _nested_callexpr_block : Block
  _extend_data_region : Region
  _extend_data_block : Block
  _valueref : OpResult

  def construct_init(self, *, name_value : StringLiteral, name_loc : Location, name: str = '', loc: Location = None, **kwargs) -> None:
    # 由于这里的初始化并不会在复制和JSON导入时执行，所以我们在 post_init() 里面要把对象属性全都重新取一遍
    assert isinstance(name_value, StringLiteral)
    assert isinstance(name_loc, Location)
    super().construct_init(name=name, loc=loc, **kwargs)
    self._head_region = self._add_symbol_table('head')
    self._positionalarg_region = self._add_region('positional_arg')
    self._keywordarg_region = self._add_symbol_table('keyword_arg')
    self._nested_callexpr_region = self._add_region('nested_calls')
    self._extend_data_region = self._add_region('extend_data')
    self._valueref = self._add_result('', CommandCallReferenceType.get(self.context))

    # initialize the head region (name here)
    name_symbol = CMDValueSymbol.create('name', name_loc, name_value)
    self._head_region.add(name_symbol)
    # initialize the positional args region
    self._positionalarg_block = self._positionalarg_region.create_block('')
    # no initialization for keyword args region
    # initialize the nested call region
    self._nested_callexpr_block = self._nested_callexpr_region.create_block('')
    # initialize the extend data region
    self._extend_data_block = self._extend_data_region.create_block('')

  def post_init(self) -> None:
    super().post_init()
    self._head_region = self.get_symbol_table('head')
    self._positionalarg_region = self.get_region('positional_arg')
    self._positionalarg_block = self._positionalarg_region.blocks.back
    self._keywordarg_region = self.get_symbol_table('keyword_arg')
    self._nested_callexpr_region = self.get_region('nested_calls')
    self._nested_callexpr_block = self._nested_callexpr_region.blocks.back
    self._extend_data_region = self.get_region('extend_data')
    self._extend_data_block = self._extend_data_region.blocks.back
    self._valueref = self.get_result('')

  @staticmethod
  def create(name: str, loc: Location, name_value : StringLiteral, name_loc : Location):
    return GeneralCommandOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name_value=name_value, name_loc=name_loc, name=name, loc=loc)

  def add_positional_arg(self, value: Value, loc : Location):
    argop = CMDPositionalArgOp.create('', loc, value)
    self._positionalarg_block.push_back(argop)

  def add_keyword_arg(self, key: str, value : Value, keyloc : Location, _valueloc : Location):
    argop = CMDValueSymbol.create(name=key, loc=keyloc, value=value)
    self._keywordarg_region.add(argop)

  def set_raw_arg(self, rawarg_value : Value, rawarg_loc : Location):
    rawarg_symbol = CMDValueSymbol.create('rawarg', rawarg_loc, rawarg_value)
    self._head_region.add(rawarg_symbol)

  def add_nested_call(self, call : GeneralCommandOp):
    self._nested_callexpr_block.push_back(call)

  def add_extend_data(self, data : Operation):
    assert self._extend_data_block.body.empty
    self._extend_data_block.push_back(data)

  def try_get_raw_arg(self) -> str | None:
    if rawarg := self._head_region.get('rawarg'):
      return rawarg.value.get_string()

  def get_short_str(self) -> str:
    namesymbol = self._head_region.get('name')
    result = '[' + namesymbol.value.get_string()
    if rawarg := self._head_region.get('rawarg'):
      result += ':' + rawarg.value.get_string()
      return result + ']'
    # 没有 rawarg 的话尝试自己组
    # 这个命令有可能没有参数（或是本来就没有，也可能是因为解析出错）
    is_arg_found = False
    for op in self._positionalarg_block.body:
      if is_arg_found == False:
        is_arg_found = True
        result += ': '
      else:
        result += ', '
      result += str(op)
    for op in self._keywordarg_region:
      if is_arg_found == False:
        is_arg_found = True
        result += ': '
      else:
        result += ', '
      result += op.name + '=' + str(op.value)
    return result + ']'

  @property
  def valueref(self):
    return self._valueref

# ------------------------------------------------------------------------------
# Top-level function call
# ------------------------------------------------------------------------------

def perform_command_parse_transform(op : Operation):
  # 开始递归
  # 输入的 op 应该是像类似 IMDocumentOp 那样的顶层结构，虽然更小范围的也没有问题
  blocks_to_remove : list[Block] = []
  assert not isinstance(op, GeneralCommandOp)
  for r in op.regions:
    prev_command = None
    for b in r.blocks:
      prev_command = _visit_block(b, prev_command, blocks_to_remove, op.context)
    if len(blocks_to_remove) > 0:
      for b in blocks_to_remove:
        b.erase_from_parent()
      blocks_to_remove.clear()

def try_parse_value_expr(body : str, loc : Location) -> GeneralCommandOp | str | None:
  # 尝试将一段内容解析为调用表达式或引用的字符串
  # 内容不合预期就返回 None
  istream = antlr4.InputStream(body)
  error_listener = _CommandParseErrorListener()
  lexer = CommandParseLexer(istream)
  lexer.removeErrorListeners()
  lexer.addErrorListener(error_listener)
  tstream = antlr4.CommonTokenStream(lexer)
  parser = CommandParseParser(tstream)
  parser.removeErrorListeners()
  parser.addErrorListener(error_listener)
  try:
    tree = parser.value()
  except:
    return None
  if error_listener.error_occurred:
    return None
  cmd_visitor = _CommandParseVisitorImpl(body, 0, {}, loc)
  vref, outloc = cmd_visitor.visitValue(tree)
  if isinstance(vref, OpResult):
    cmd = vref.parent
    assert isinstance(cmd, GeneralCommandOp)
    return cmd
  assert isinstance(vref, StringLiteral)
  return vref.get_string()

def _visit_block(hostblock : Block, prev_command : GeneralCommandOp, blocks_to_remove : list[Block], ctx : Context):
  # 如果该块的开头是以'['或'【'开始的文本或其他数据,则将所有内容重整为单个字符串（所有非字符内容，像图片、声音素材等，都会转化为'\0'来做特判）
  # 否则遍历每个操作项，递归遍历每个块
  result_tuple = check_is_command_start(hostblock, ctx)
  if result_tuple is None:
    # 该块不是命令
    # 递归遍历所有子项
    for child_op in hostblock.body:
      if isinstance(child_op, MetadataOp):
        continue
      for r in child_op.regions:
        prev = None
        for b in r.blocks:
          prev = _visit_block(b, prev, blocks_to_remove, ctx)
    # 然后看看该项是不是列表、表格、特殊块，并且前面有一个命令
    if prev_command is not None:
      first_child = None
      for child_op in hostblock.body:
        if isinstance(child_op, MetadataOp):
          continue
        first_child = child_op
        break
      if isinstance(first_child, (IMListOp, IMTableOp, IMSpecialBlockOp)):
        first_child.remove_from_parent()
        prev_command.add_extend_data(first_child)
        if hostblock.body.empty:
          blocks_to_remove.append(hostblock)
    # 不是命令的情况处理完毕
    return None
  # 如果是命令的话就调用下面的具体实现
  # 在第一个字符元素前添加命令操作项
  command_str, asset_list, first_op, consumed_ops, infolist = result_tuple
  last_command = _visit_command_block_impl(hostblock, ctx, command_str, asset_list, first_op, infolist)
  # 然后把该块内y用于生成命令的所有内容清除
  consumed_ops = result_tuple[3]
  for deadop in consumed_ops:
    deadop.erase_from_parent()
  return last_command

@MiddleEndDecl('cmdsyntax', input_decl=IMDocumentOp, output_decl=IMDocumentOp)
class CommandSyntaxAnalysisTransform(TransformBase):
  def run(self) -> IMDocumentOp | typing.List[IMDocumentOp] | None:
    if len(self.inputs) == 1:
      op = self.inputs[0]
      perform_command_parse_transform(op)
      return op
    result = []
    for op in self.inputs:
      perform_command_parse_transform(op)
      result.append(op)
    return result

def check_is_command_start(b : Block, ctx: Context) -> tuple[str, list[AssetData], IMElementOp, list[IMElementOp], list[_InitParsedCommandInfo]] | None:
  # 检查该段是否含有以 _command_start_text 中所标的字符开头并且是纯内容（不包含像是 IMFrameOp, IMListOp这种），是的话就返回:
  # (1) 一个纯文本的段落内容，所有资源都以'\0'替代；
  # (2) 一个资源列表（即那些被以'\0'替代的内容）
  # (3) 命令开头字符所在的操作项（来提供位置信息）
  # 如果该段不是命令的话，返回 None
  # 构建纯文本途中将忽略任何错误记录（像 IMErrorElementOp 那样的）

  # 可能的命令开始标记
  _command_start_text = ('[', '【')

  command_str = ''
  asset_list : typing.List[AssetData] = []
  first_op : Operation = None
  consumed_ops : typing.List[IMElementOp] = []
  for op in b.body:
    # 忽略所有非语义消息
    if isinstance(op, MetadataOp):
      continue
    if not isinstance(op, IMElementOp):
      # 碰到了一项非内容的
      # 如果我们已经找到了开始标记，就在开始标记前添加一个错误记录
      if first_op is not None:
        error_op = ErrorOp.create(error_code='cmd-noncontent-entry-in-command', context=ctx, error_msg=StringLiteral.get(command_str, ctx), name='', loc = first_op.location)
        error_op.insert_before(first_op)
      continue
    # 找到了一项内容
    # 尝试读取内容并组成命令文本
    assert isinstance(op, IMElementOp)
    content_operand : OpOperand = op.content
    for i in range(0, content_operand.get_num_operands()):
      v = content_operand.get(i)
      if isinstance(v, TextFragmentLiteral):
        command_str += v.get_string()
      elif isinstance(v, StringLiteral):
        command_str += v.get_string()
      elif isinstance(v, AssetData):
        command_str += '\0'
        asset_list.append(v)
      else:
        raise PPNotImplementedError('TODO support other possible element types in IMElementOp')
    if first_op is None:
      # 这是开头
      if command_str.startswith(_command_start_text):
        first_op = op
      else:
        # 该段不以 _command_start_text 所注字符开头，不是命令
        return None
    consumed_ops.append(op)
  # 如果没有找到开头的话那也不是命令段
  if first_op is None:
    return None
  # 如果无法顺利完成命令扫描的话也认为不是命令
  infolist = _split_text_as_commands(command_str)
  if isinstance(infolist, _CommandParseErrorRecord):
    #errorloc = get_loc_at_offset(infolist.column)
    #errop = ErrorOp.create(error_code='cmd-scan-error', context=ctx, error_msg=StringLiteral.get(infolist.msg, ctx), name='', loc=errorloc)
    #errop.insert_before(insert_before_op)
    return None
  return (command_str, asset_list, first_op, consumed_ops, infolist)

# ------------------------------------------------------------------------------
# 具体实现
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# 命令扫描

def _strip_whitespaces(text: str) -> typing.Tuple[str, int, int]: # trimmed string, leading WS, terminating WS
  cur_text = text.lstrip()
  leading_ws = len(text) - len(cur_text)
  result = cur_text.rstrip()
  trailing_ws = len(cur_text) - len(result)
  return (result, leading_ws, trailing_ws)

class _InitParsedCommandInfo:
  total_range : typing.Tuple[int, int] # position (from the text) of the '[' and ']' (or counterparts) token
  is_comment : bool # whether this is a comment
  body : str # content of the body (leading and terminating whitespace trimmed)
  body_range : typing.Tuple[int, int] # start and end position of the body text

class _CommandScanListener(CommandScanListener):
  commandinfo : typing.List[_InitParsedCommandInfo]

  def __init__(self):
    super().__init__()
    self.commandinfo = []

  def enterCommand(self, ctx : CommandScanParser.CommandContext):
    result = _InitParsedCommandInfo()

    commandstart = ctx.COMMANDSTART().getSymbol()
    commandend = ctx.COMMANDEND().getSymbol()
    # termal token's getSourceInterval() return Tuple[int, int] (start, end)
    # commandstart_start = commandstart.getSourceInterval()[0]
    # commandstart_end = commandstart.getSourceInterval()[1]
    result.total_range = (commandstart.start, commandend.stop) # inclusive; usually commandstart/end.start == ....stop

    commentstart = ctx.COMMENTSTART() # antlr4.tree.Tree.TerminalNodeImpl or None
    result.is_comment = (commentstart is not None)

    body = ctx.body()
    raw_text = body.getText()
    result.body, content_start_trim, content_end_trim = _strip_whitespaces(raw_text)
    result.body_range = (body.start.start + content_start_trim, body.stop.stop - content_end_trim)

    self.commandinfo.append(result)

    # if result.is_comment:
    #   print("Comment: \"" + result.body + "\" " + str(result.body_range) + " <- " + str(result.total_range))
    # else:
    #   print("Command: \"" + result.body + "\" " + str(result.body_range) + " <- " + str(result.total_range))

@dataclasses.dataclass
class _CommandParseErrorRecord:
  column : int
  msg : str

class _CommandCreationErrorListenerBase(ErrorListener):
  # since we run command scanning in every single paragraph in the input text,
  # we expect a lot of errors here and we don't want to report them
  # so we just record whether there is a failure or not and done
  _error_occurred : bool
  _error_column : int
  _error_msg : str
  def __init__(self):
    super().__init__()
    self._error_occurred = False
    self._error_column = 0
    self._error_msg = ''

  def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
    if not self._error_occurred:
      assert isinstance(column, int)
      assert isinstance(msg, str)
      self._error_occurred = True
      self._error_column = column
      self._error_msg = msg

  @property
  def error_occurred(self):
    return self._error_occurred

  def get_error_record(self) -> _CommandParseErrorRecord:
    return _CommandParseErrorRecord(column=self._error_column, msg=self._error_msg)

class _CommandScanErrorListener(_CommandCreationErrorListenerBase):
  pass

def _split_text_as_commands(text : str) -> typing.List[_InitParsedCommandInfo] | _CommandParseErrorRecord:
  istream = antlr4.InputStream(text)
  error_listener = _CommandScanErrorListener()
  lexer = CommandScanLexer(istream)
  lexer.removeErrorListeners(); # remove ConsoleErrorListener
  lexer.addErrorListener(error_listener)
  tstream = antlr4.CommonTokenStream(lexer)
  parser = CommandScanParser(tstream)
  parser.removeErrorListeners(); # remove ConsoleErrorListener
  parser.addErrorListener(error_listener)
  try:
    tree = parser.line()
  except:
    return error_listener.get_error_record()

  if error_listener.error_occurred:
    return error_listener.get_error_record()

  # print(tree.toStringTree(recog=parser))
  listener = _CommandScanListener()
  walker = antlr4.ParseTreeWalker()
  walker.walk(listener, tree)
  return listener.commandinfo

# ------------------------------------------------------------------------------
# 命令解析

class _CommandParseErrorListener(_CommandCreationErrorListenerBase):
  pass

class _CommandParseVisitorImpl(CommandParseVisitor):
  # 有两个使用场景：
  # 1. 在命令扫描后把完整的命令解析出来
  # 2. 在后续编译中需要把字符串理解为表达式时，会需要解析 "value", 有可能是调用表达式或带引号的字符串等
  startloc : Location
  fulltext : str # we need this to accurately collect the string; whitespaces are excluded in ctx.getText()
  global_offset : int
  asset_map : dict[int, AssetData]
  commandop : GeneralCommandOp
  command_op_stack : list[GeneralCommandOp]

  def __init__(self, fulltext : str, global_offset : int, asset_map : dict[int, AssetData], startloc : Location) -> None:
    super().__init__()
    self.startloc = startloc
    self.fulltext = fulltext
    self.global_offset = global_offset
    self.asset_map = asset_map
    self.commandop = None
    self.command_op_stack = []

  @property
  def context(self):
    return self.startloc.context

  def _get_loc(self, offset : int) -> Location:
    loc = self.startloc
    if isinstance(loc, DILocation):
      offset_correction = loc.column - self.global_offset
      assert offset_correction == 1
      loc = loc.context.get_DILocation(loc.file, loc.page, loc.row, offset + offset_correction)
    return loc

  def _handle_natural_text(self, natural_text_node) -> tuple[str, int, int]:
    natural_text_token = natural_text_node.getSymbol()
    start = natural_text_token.start
    end = natural_text_token.stop + 1
    text = natural_text_token.text
    return (text, self.global_offset + start, self.global_offset + end)

  def _handle_quoted_str(self, quoted_str_node) -> tuple[str, int, int]:
    quoted_str_token = quoted_str_node.getSymbol()
    start = quoted_str_token.start
    end = quoted_str_token.stop + 1
    text = quoted_str_token.text[1:-1]
    return (text, self.global_offset + start + 1, self.global_offset + end - 1)

  def _handle_nontext_element(self, element_node) -> tuple[AssetData, int, int]:
    element_token = element_node.getSymbol()
    start = element_token.start
    end = element_token.stop + 1
    text = element_token.text
    assert len(text) == 1 and text == '\0'
    global_start = self.global_offset + start
    data = self.asset_map[global_start]
    return (data, global_start, self.global_offset + end)

  def visitName(self, ctx: CommandParseParser.NameContext) -> tuple[StringLiteral, Location]:
    content_tuple = None

    if ctx.NATURALTEXT() is not None:
      content_tuple = self._handle_natural_text(ctx.NATURALTEXT())
    elif ctx.QUOTEDSTR() is not None:
      content_tuple = self._handle_quoted_str(ctx.QUOTEDSTR())
    else:
      raise PPInternalError('Name without valid child?')

    name_str, name_start, _name_end = content_tuple
    name_value = StringLiteral.get(name_str, self.context)
    name_loc = self._get_loc(name_start)
    return (name_value, name_loc)

  def visitCommand(self, ctx: CommandParseParser.CommandContext):
    assert ctx.name() is not None and isinstance(ctx.name(), CommandParseParser.NameContext)
    name_value, name_loc = self.visitName(ctx.name())
    self.commandop = GeneralCommandOp.create('', self.startloc, name_value, name_loc)
    if ctx.argumentlist() is not None:
      self.visitArgumentlist(ctx.argumentlist())

  def visitArgumentlist(self, ctx: CommandParseParser.ArgumentlistContext):
    # 本函数只会在 command 下触发，不会在内联的参数组中出现
    self.command_op_stack.append(self.commandop)
    assert ctx.arguments() is not None and isinstance(ctx.arguments(), CommandParseParser.ArgumentsContext)
    self.visitArguments(ctx.arguments())
    self.command_op_stack.pop(-1)

  def visitArguments(self, ctx: CommandParseParser.ArgumentsContext) -> None:
    # 这个函数会在两个情况下被调用：
    # 1. 我们在处理最外层的命令体
    # 2. 我们在处理某个值时，该值是个调用表达式
    current_command = self.command_op_stack[-1]
    # 把 rawargs 的范围设置好
    rawarg_start = self.global_offset + ctx.start.start
    rawarg_end = self.global_offset + ctx.stop.stop + 1
    rawarg_text = ''
    if rawarg_end > rawarg_start:
      rawarg_text = self.fulltext[rawarg_start:rawarg_end]
    current_command.set_raw_arg(StringLiteral.get(rawarg_text, self.context), self._get_loc(rawarg_start))
    # 具体的参数读取交给子项
    if ctx.positionals() is not None:
      self.visitPositionals(ctx.positionals())
    if ctx.kwargs() is not None:
      self.visitKwargs(ctx.kwargs())

  def visitPositionals(self, ctx: CommandParseParser.PositionalsContext):
    current_command = self.command_op_stack[-1]
    for v in ctx.value():
      assert isinstance(v, CommandParseParser.ValueContext)
      value, loc = self.visitValue(v)
      current_command.add_positional_arg(value, loc)

  def visitKwargs(self, ctx: CommandParseParser.KwargsContext):
    for v in ctx.kwvalue():
      assert isinstance(v, CommandParseParser.KwvalueContext)
      self.visitKwvalue(v)

  def visitKwvalue(self, ctx: CommandParseParser.KwvalueContext) -> None:
    current_command = self.command_op_stack[-1]
    name_value, name_loc = self.visitName(ctx.name())
    value, value_loc = self.visitValue(ctx.value())
    current_command.add_keyword_arg(name_value.value, value, name_loc, value_loc)

  def visitValue(self, ctx: CommandParseParser.ValueContext) -> tuple[Value, Location]:
    if ctx.callexpr() is not None:
      return self.visitCallexpr(ctx.callexpr())
    elif ctx.evalue() is not None:
      return self.visitEvalue(ctx.evalue())
    else:
      raise PPInternalError('Invalid value')

  def visitCallexpr(self, ctx: CommandParseParser.CallexprContext) -> tuple[Value, Location]:
    # 如果我们只是解析值的的话（不是解析一个完整的命令），
    # self.command_op_stack 有可能是空的
    name_value, name_loc = self.visitName(ctx.name())
    newop = GeneralCommandOp.create('', name_loc, name_value, name_loc)
    if len(self.command_op_stack) > 0:
      current_command = self.command_op_stack[-1]
      current_command.add_nested_call(newop)
    self.command_op_stack.append(newop)
    self.visitArguments(ctx.arguments())
    self.command_op_stack.pop(-1)
    return (newop.valueref, newop.location)

  def visitEvalue(self, ctx: CommandParseParser.EvalueContext) -> tuple[Value, Location]:
    content_tuple = None

    if ctx.NATURALTEXT() is not None:
      content_tuple = self._handle_natural_text(ctx.NATURALTEXT())
    elif ctx.QUOTEDSTR() is not None:
      content_tuple = self._handle_quoted_str(ctx.QUOTEDSTR())
    elif ctx.ELEMENT() is not None:
      data, start, _end = self._handle_nontext_element(ctx.ELEMENT())
      assert isinstance(data, AssetData)
      return (data, self._get_loc(start))
    else:
      raise PPInternalError('evalue without valid child?')

    content_str, startpos, _endpos = content_tuple
    value = StringLiteral.get(content_str, self.context)
    loc = self._get_loc(startpos)
    return (value, loc)

# ------------------------------------------------------------------------------
# 组装起来

#class _InitParsedCommandInfo:
#  total_range : typing.Tuple[int, int] # position (from the text) of the '[' and ']' (or counterparts) token
#  is_comment : bool # whether this is a comment
#  body : str # content of the body (leading and terminating whitespace trimmed)
#  body_range : typing.Tuple[int, int] # start and end position of the body text

def _visit_command_block_impl(b : Block, ctx : Context, command_str : str, asset_list : typing.List[AssetData], insert_before_op : IMElementOp, infolist : list[_InitParsedCommandInfo]) -> GeneralCommandOp | None:
  # 如果生成了命令的话，返回最后一个生成的命令
  # 帮助生成位置信息
  headloc = insert_before_op.location
  def get_loc_at_offset(offset : int):
    if isinstance(headloc, DILocation):
      return ctx.get_DILocation(headloc.file, headloc.page, headloc.row, headloc.column + offset)
    return headloc

  # 进行检查，把资源的位置何内容对应起来
  asset_loc_list = [i.start() for i in re.finditer('\0', command_str)]
  assert len(asset_loc_list) == len(asset_list)
  asset_map_dict = {}
  # pylint: disable=consider-using-enumerate
  for i in range(0, len(asset_loc_list)):
    asset_map_dict[asset_loc_list[i]] = asset_list[i]

  # 首先，把命令段分割成一系列命令，如果无法形成命令则添加一个错误
  # 更新：此段内容已移至判断命令段开始处
  #infolist = _split_text_as_commands(command_str)
  #if isinstance(infolist, _CommandParseErrorRecord):
  #  errorloc = get_loc_at_offset(infolist.column)
  #  errop = ErrorOp.create(error_code='cmd-scan-error', context=ctx, error_msg=StringLiteral.get(infolist.msg, ctx), name='', loc=errorloc)
  #  errop.insert_before(insert_before_op)
  #  return

  # 开始处理
  last_command = None
  assert isinstance(infolist, list)
  for info in infolist:
    # total_range = info.total_range
    is_comment = info.is_comment
    body = info.body
    body_range_start, body_range_end = info.body_range
    if body_range_start > body_range_end:
      # 跳过空项
      continue
    loc = get_loc_at_offset(body_range_start)
    # 如果是注释，则直接生成注释项
    if is_comment:
      comment = CommentOp.create(comment = StringLiteral.get(body, ctx), name = '', loc = loc)
      comment.insert_before(insert_before_op)
      continue
    # 既然不是注释，那就是真正的命令了
    istream = antlr4.InputStream(body)
    error_listener = _CommandParseErrorListener()
    lexer = CommandParseLexer(istream)
    lexer.removeErrorListeners(); # remove ConsoleErrorListener
    lexer.addErrorListener(error_listener)
    tstream = antlr4.CommonTokenStream(lexer)
    parser = CommandParseParser(tstream)
    parser.removeErrorListeners(); # remove ConsoleErrorListener
    parser.addErrorListener(error_listener)
    tree = parser.command()
    if error_listener.error_occurred:
      record = error_listener.get_error_record()
      errorloc = get_loc_at_offset(record.column)
      errop = ErrorOp.create(error_code='cmd-parse-error', context=ctx, error_msg=StringLiteral.get(record.msg, ctx), name='', loc=errorloc)
      errop.insert_before(insert_before_op)
      continue
    cmd_visitor = _CommandParseVisitorImpl(command_str, body_range_start, asset_map_dict, loc)
    cmd_visitor.visit(tree)
    result_command_op = cmd_visitor.commandop
    result_command_op.insert_before(insert_before_op)
    last_command = result_command_op
    continue
  return last_command
