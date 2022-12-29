# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# This is the latest (2022-11-30) version of command parser; commandast.py and commandastparser.py is obsolete
from __future__ import annotations
import typing
import collections
import dataclasses

import antlr4
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.ErrorListener import ConsoleErrorListener

from ._antlr_generated.CommandScanLexer      import CommandScanLexer
from ._antlr_generated.CommandScanParser     import CommandScanParser
from ._antlr_generated.CommandScanListener   import CommandScanListener
from ._antlr_generated.CommandParseLexer     import CommandParseLexer
from ._antlr_generated.CommandParseParser    import CommandParseParser
from ._antlr_generated.CommandParseListener  import CommandParseListener

from ..irbase import *
from ..inputmodel import *
from ..pipeline import TransformBase, MiddleEndDecl

# 命令扫描（语法分析阶段）
  
# ------------------------------------------------------------------------------
# Command AST definition
# ------------------------------------------------------------------------------

class CMDPositionalArgOp(Operation):
  # representing a positional argument
  # this is the only "value" without a name
  # everything else (keyword argument, the name of the command, etc) use CMDValueSymbol
  # operation location is the location of the name/value (start of the name for keyword args, start of the value for positional args)
  # we use a full op here to track the loc
  _value_operand : OpOperand
  
  def __init__(self, name: str, loc: Location, value : Value, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._value_operand = self._add_operand_with_value('value', value)

class CMDValueSymbol(Symbol):
  # representing a value in the command, or an argument value
  # name is the value / argument name
  # operation location is the location of the name/value (start of the name for keyword args, start of the value for positional args)
  _value_operand : OpOperand
  
  def __init__(self, name: str, loc: Location, value : Value, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._value_operand = self._add_operand_with_value('value', value)

class GeneralCommandOp(Operation):
  # 所有能被识别的命令（能找到命令名以及参数列表）
  _head_region : SymbolTableRegion # name + raw_args (raw args make life easier for commands with custom parsing)
  _positionalarg_region : Region # single block, list of values
  _positionalarg_block : Block
  _keywordarg_region : SymbolTableRegion
  
  def __init__(self, name: str, loc: Location, name_value : ConstantString, name_loc : Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._head_region = self._add_symbol_table('head')
    self._positionalarg_region = self._add_region('positional_arg')
    self._keywordarg_region = self._add_symbol_table('keyword_arg')
    # initialize the head region (name here)
    name_symbol = CMDValueSymbol('name', name_loc, name_value)
    self._head_region.add(name_symbol)
    # initialize the positional args region
    self._positionalarg_block = self._positionalarg_region.add_block('')
    # no initialization for keyword args region
  
  def add_positional_arg(self, value: Value, loc : Location):
    argop = CMDPositionalArgOp('', loc, value)
    self._positionalarg_block.push_back(argop)
  
  def add_keyword_arg(self, key: str, value : Value, keyloc : Location, _valueloc : Location):
    argop = CMDValueSymbol(name=key, loc=keyloc, value=value)
    self._keywordarg_region.add(argop)
  
  def set_raw_arg(self, rawarg_value : Value, rawarg_loc : Location):
    rawarg_symbol = CMDValueSymbol('rawarg', rawarg_loc, rawarg_value)
    self._head_region.add(rawarg_symbol)

# ------------------------------------------------------------------------------
# Top-level function call
# ------------------------------------------------------------------------------

def perform_command_parse_transform(op : Operation):
  def visit_block(b : Block):
    # 如果该块的开头是以'['或'【'开始的文本或其他数据,则将所有内容重整为单个字符串（所有非字符内容，像图片、声音素材等，都会转化为'\0'来做特判）
    # 否则遍历每个操作项，递归遍历每个块
    result_tuple = check_is_command_start(b, op.context)
    if result_tuple is None:
      # 该块不是命令
      # 递归遍历所有子项
      for child_op in b.body:
        if isinstance(child_op, MetadataOp):
          continue
        for r in child_op.regions:
          for b in r.blocks:
            visit_block(b)
      # 不是命令的情况处理完毕
      return
    # 如果是命令的话就调用下面的具体实现
    # 在第一个字符元素前添加命令操作项
    _visit_command_block_impl(b, op.context, result_tuple[0], result_tuple[1], result_tuple[2])
    # 然后把该块内y用于生成命令的所有内容清除
    consumed_ops = result_tuple[3]
    for deadop in consumed_ops:
      deadop.erase_from_parent()
    
  # 开始递归
  # 输入的 op 应该是像类似 IMDocumentOp 那样的顶层结构，虽然更小范围的也没有问题
  assert not isinstance(op, GeneralCommandOp)
  for r in op.regions:
    for b in r.blocks:
      visit_block(b)

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

def check_is_command_start(b : Block, ctx: Context) -> typing.Tuple[str, typing.List[AssetData], IMElementOp, typing.List[IMElementOp]] | None:
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
        error_op = IMErrorElementOp(name='', loc = first_op.location, content=ConstantString.get(command_str, ctx), error_code='cmd-noncontent-entry-in-command')
        error_op.insert_before(first_op)
      continue
    # 找到了一项内容
    # 尝试读取内容并组成命令文本
    assert isinstance(op, IMElementOp)
    content_operand : OpOperand = op.content
    for i in range(0, content_operand.get_num_operands()):
      v = content_operand.get(i)
      if isinstance(v, ConstantTextFragment):
        command_str += v.get_string()
      elif isinstance(v, ConstantText):
        command_str += v.get_string()
      else:
        raise NotImplementedError('TODO support other possible element types in IMElementOp')
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
  # 完成
  return (command_str, asset_list, first_op, consumed_ops)

# ------------------------------------------------------------------------------
# 具体实现
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# 命令扫描

def _strip_whitespaces(text: str) -> typing.Tuple[str, int, int]: # trimmed string, leading WS, terminating WS
  cur_text = text.lstrip()
  leadingWS = len(text) - len(cur_text)
  result = cur_text.rstrip()
  trailingWS = len(cur_text) - len(result)
  return (result, leadingWS, trailingWS)

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
    rawText = body.getText()
    result.body, contentStartTrim, contentEndTrim = _strip_whitespaces(rawText)
    result.body_range = (body.start.start + contentStartTrim, body.stop.stop - contentEndTrim)
    
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

def _splitTextAsCommands(text : str) -> typing.List[_InitParsedCommandInfo] | _CommandParseErrorRecord:
  istream = antlr4.InputStream(text)
  error_listener = _CommandScanErrorListener()
  lexer = CommandScanLexer(istream)
  #lexer.removeErrorListeners(); # remove ConsoleErrorListener
  lexer.addErrorListener(error_listener)
  lexer.addErrorListener(ConsoleErrorListener())
  tstream = antlr4.CommonTokenStream(lexer)
  parser = CommandScanParser(tstream)
  #parser.removeErrorListeners(); # remove ConsoleErrorListener
  parser.addErrorListener(error_listener)
  parser.addErrorListener(ConsoleErrorListener())
  tree = parser.line()
  
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

@dataclasses.dataclass
class ElementValueNode: # only contains fields of ASTNodeBase; nothing else
  start : int # index of first character of this AST node
  end : int # index +1 of last character of this AST node
  text: str # content of this node
  quoted : typing.Tuple[int, int] | None # number of characters to drop at beginning and at the end of the text string because the content is quoted
  
  def __str__(self) -> str:
    return self.to_string(0)
  
  def getContent(self) -> str:
    if self.quoted is None:
      return self.text
    return self.text[self.quoted[0] : -self.quoted[1]]
  
  def to_string(self, indent: int) -> str:
    if self.quoted is None:
      return '\"' + self.text + '\" ' + '[' + str(self.start) + ',' + str(self.end) + ']'
    return '\"' + self.getContent() + '\" ' + '[' + str(self.start) + '+' + self.quoted[0] + ',' + str(self.end) + '-' + self.quoted[1] + ')'

def _get_node_from_natural_text(global_offset : int, natural_text_node) -> ElementValueNode:
  natural_text_token = natural_text_node.getSymbol()
  start = natural_text_token.start
  end = natural_text_token.stop + 1
  text = natural_text_token.text
  return ElementValueNode(global_offset + start, global_offset + end, text, None)

def _get_node_from_quoted_str(global_offset : int, quoted_str_node) -> ElementValueNode:
  quoted_str_token = quoted_str_node.getSymbol()
  start = quoted_str_token.start
  end = quoted_str_token.stop + 1
  text = quoted_str_token.text
  return ElementValueNode(global_offset + start, global_offset + end, text, (1,1))

def _get_node_from_nontext_element(global_offset : int, element_node) -> ElementValueNode:
  element_token = element_node.getSymbol()
  start = element_token.start
  end = element_token.stop + 1
  text = element_token.text
  assert len(text) == 1 and text == '\0'
  return ElementValueNode(global_offset + start, global_offset + end, text, None)

def _parseValue(global_offset : int, node : CommandParseParser.ValueContext) -> ElementValueNode:
  assert isinstance(node, CommandParseParser.ValueContext)

  natural_text_node = node.NATURALTEXT()
  if natural_text_node is not None:
    return _get_node_from_natural_text(global_offset, natural_text_node)
  
  quoted_str_node = node.QUOTEDSTR()
  if quoted_str_node is not None:
    return _get_node_from_quoted_str(global_offset, quoted_str_node)
  
  element_node = node.ELEMENT()
  if element_node is not None:
    return _get_node_from_nontext_element(global_offset, element_node)
  
  raise RuntimeError("CommandAST value node parse failed")

def _parseName(global_offset : int, node : CommandParseParser.NameContext) -> ElementValueNode:
  assert isinstance(node, CommandParseParser.NameContext)

  natural_text_node = node.NATURALTEXT()
  if natural_text_node is not None:
    return _get_node_from_natural_text(global_offset, natural_text_node)
  
  quoted_str_node = node.QUOTEDSTR()
  if quoted_str_node is not None:
    return _get_node_from_quoted_str(global_offset, quoted_str_node)
  
  raise RuntimeError("CommandAST name node parse failed")

class _CommandParseListenerImpl(CommandParseListener):
  commandop : GeneralCommandOp
  startloc : Location
  fulltext : str # we need this to accurately collect the string; whitespaces are excluded in ctx.getText()
  global_offset : int
  is_in_positionals : bool
  kw_name : ElementValueNode | None
  kw_value : ElementValueNode | None
  rawarg_start : int
  rawarg_end : int

  def __init__(self, fulltext : str, global_offset : int, startloc : Location) -> None:
    super().__init__()
    self.commandop = None
    self.startloc = startloc
    self.fulltext = fulltext
    self.is_in_positionals = False
    self.global_offset = global_offset
    self.kw_name = None
    self.kw_value = None
    self.rawarg_start = -1
    self.rawarg_end = -1
  
  def _get_loc(self, offset : int) -> Location:
    loc = self.startloc
    if isinstance(loc, DILocation):
      offset_correction = loc.column - self.global_offset
      assert offset_correction == 1
      loc = loc.context.get_DILocation(loc.file, loc.page, loc.row, offset + offset_correction)
    return loc
  
  def _expand_value(self, node : ElementValueNode) -> typing.Tuple[Value, Location]:
    text = node.getContent()
    startpos = node.start
    if node.quoted is not None:
      startpos += node.quoted[0]
    loc = self._get_loc(startpos)
    value = ConstantString.get(text, self.startloc.context)
    return (value, loc)
  
  def enterPositionals(self, ctx: CommandParseParser.PositionalsContext):
    self.is_in_positionals = True
  
  def exitPositionals(self, ctx: CommandParseParser.PositionalsContext):
    self.is_in_positionals = False
  
  def enterValue(self, ctx: CommandParseParser.ValueContext):
    element = _parseValue(self.global_offset, ctx)
    if self.is_in_positionals:
      # we are handling positional arguments
      value, loc = self._expand_value(element)
      self.commandop.add_positional_arg(value, loc)
    else:
      # we are handling keyword arguments
      assert self.kw_value is None
      self.kw_value = element
    # update start and end
    #if self.rawarg_start == -1:
    #  self.rawarg_start = element.start
    #if self.rawarg_end == -1 or self.rawarg_end < element.end:
    #  self.rawarg_end = element.end

  def enterName(self, ctx: CommandParseParser.NameContext):
    name = _parseName(self.global_offset, ctx)
    if self.commandop is None:
      # 这是命令的名称
      nameval, nameloc = self._expand_value(name)
      self.commandop = GeneralCommandOp('', self.startloc, nameval, nameloc)
      # 同时更新这个位置
      self.rawarg_start = name.end
      self.rawarg_end = name.end
      return
    # 不是命令名的话那就是 kwarg 的名了
    assert not self.is_in_positionals
    assert self.kw_name is None
    self.kw_name = name
    # update start and end
    #if self.rawarg_start == -1:
    #  self.rawarg_start = name.start
    #if self.rawarg_end == -1 or self.rawarg_end < name.end:
    #  self.rawarg_end = name.end
  
  def enterArgumentlist(self, ctx: CommandParseParser.ArgumentlistContext):
    # 如果有参数列表的话，我们直接从这里提取 rawarg 的范围
    raw_start = ctx.start.start
    raw_end = ctx.stop.stop + 1
    self.rawarg_start = raw_start + self.global_offset
    self.rawarg_end = raw_end + self.global_offset
    
    # natural_text_token = natural_text_node.getSymbol()
    # start = natural_text_token.start
    # end = natural_text_token.stop + 1
  
  def exitKwvalue(self, ctx: CommandParseParser.KwvalueContext):
    assert self.kw_name is not None and self.kw_value is not None
    kv, kloc = self._expand_value(self.kw_name)
    vv, vloc = self._expand_value(self.kw_value)
    assert isinstance(kv, ConstantString)
    self.commandop.add_keyword_arg(kv.value, vv, kloc, vloc)
    self.kw_name = None
    self.kw_value = None
  
  def exitArgumentlist(self, ctx:CommandParseParser.ArgumentlistContext):
    rawarg_start = self.rawarg_start
    rawarg_end = self.rawarg_end
    rawarg_text = self.fulltext[rawarg_start:rawarg_end]
    self.commandop.set_raw_arg(ConstantString.get(rawarg_text, self.startloc.context), self._get_loc(rawarg_start))
    
# ------------------------------------------------------------------------------
# 组装起来

#class _InitParsedCommandInfo:
#  total_range : typing.Tuple[int, int] # position (from the text) of the '[' and ']' (or counterparts) token
#  is_comment : bool # whether this is a comment
#  body : str # content of the body (leading and terminating whitespace trimmed)
#  body_range : typing.Tuple[int, int] # start and end position of the body text

def _visit_command_block_impl(b : Block, ctx : Context, command_str : str, asset_list : typing.List[AssetData], insert_before_op : IMElementOp) -> None:
  
  # 帮助生成位置信息
  headloc = insert_before_op.location
  def get_loc_at_offset(offset : int):
    if isinstance(headloc, DILocation):
      return ctx.get_DILocation(headloc.file, headloc.page, headloc.row, headloc.column + offset)
    return headloc
  
  # 首先，把命令段分割成一系列命令，如果无法形成命令则添加一个错误
  infolist = _splitTextAsCommands(command_str)
  if isinstance(infolist, _CommandParseErrorRecord):
    errorloc = get_loc_at_offset(infolist.column)
    errop = ErrorOp('', errorloc, error_code='cmd-scan-error', error_msg=ConstantString.get(infolist.msg, ctx))
    errop.insert_before(insert_before_op)
    return
  
  # 开始处理
  # num_commands_created = 0 # 如果我们最后一个命令都没有生成，那就
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
      comment = CommentOp('', loc, ConstantString.get(body, ctx))
      comment.insert_before(insert_before_op)
      continue
    # 既然不是注释，那就是真正的命令了
    istream = antlr4.InputStream(body)
    error_listener = _CommandParseErrorListener()
    lexer = CommandParseLexer(istream)
    #lexer.removeErrorListeners(); # remove ConsoleErrorListener
    lexer.addErrorListener(error_listener)
    lexer.addErrorListener(ConsoleErrorListener())
    tstream = antlr4.CommonTokenStream(lexer)
    parser = CommandParseParser(tstream)
    #parser.removeErrorListeners(); # remove ConsoleErrorListener
    parser.addErrorListener(error_listener)
    parser.addErrorListener(ConsoleErrorListener())
    tree = parser.command()
    if error_listener.error_occurred:
      record = error_listener.get_error_record()
      errorloc = get_loc_at_offset(record.column)
      errop = ErrorOp('', errorloc, error_code='cmd-parse-error', error_msg=ConstantString.get(record.msg, ctx))
      errop.insert_before(insert_before_op)
      continue
    cmd_listener = _CommandParseListenerImpl(command_str, body_range_start, loc)
    walker = antlr4.ParseTreeWalker()
    walker.walk(cmd_listener, tree)
    cmd_listener.commandop.insert_before(insert_before_op)
    continue
    
