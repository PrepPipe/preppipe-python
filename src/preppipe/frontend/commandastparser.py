# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing

from .commandast import *

# this is the function to call for users
def create_command_ast(text : str, debugloc : typing.Any) -> CommandAST:
  return _create_command_ast_impl(text, debugloc)

# ------------------------------------------------------------------------------
# Implementation detail
# ------------------------------------------------------------------------------

import collections

import antlr4
from antlr4.error.ErrorListener import ErrorListener
from antlr4.error.ErrorListener import ConsoleErrorListener

from ._antlr_generated.CommandScanLexer      import CommandScanLexer
from ._antlr_generated.CommandScanParser     import CommandScanParser
from ._antlr_generated.CommandScanListener   import CommandScanListener
from ._antlr_generated.CommandParseLexer     import CommandParseLexer
from ._antlr_generated.CommandParseParser    import CommandParseParser
from ._antlr_generated.CommandParseListener  import CommandParseListener

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

    if result.is_comment:
      print("Comment: \"" + result.body + "\" " + str(result.body_range) + " <- " + str(result.total_range))
    else:
      print("Command: \"" + result.body + "\" " + str(result.body_range) + " <- " + str(result.total_range))

class _CommandScanErrorListener(ErrorListener):
  # since we run command scanning in every single paragraph in the input text,
  # we expect a lot of errors here and we don't want to report them
  # so we just record whether there is a failure or not and done
  _error_occurred : bool
  def __init__(self):
    super().__init__()
    self._error_occurred = False
  
  def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
    self._error_occurred = True
  
  @property
  def error_occurred(self):
    return self._error_occurred

def _splitTextAsCommands(text : str) -> typing.List[_InitParsedCommandInfo] | None:
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
    return None
  
  # print(tree.toStringTree(recog=parser))
  listener = _CommandScanListener()
  walker = antlr4.ParseTreeWalker()
  walker.walk(listener, tree)
  return listener.commandinfo

class _CommandParseErrorListener(ErrorListener):
  # since we only run command parsing on chosen command blocks, we want to report useful error messages
  # for now we still just save whether problems are encountered and don't do anything else
  # we shall go back to this later on
  _error_occurred : bool
  def __init__(self) -> None:
    super().__init__()
    self._error_occurred = False
  
  def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
    self._error_occurred = True
  
  @property
  def error_occurred(self):
    return self._error_occurred

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

class _CommandArgListener(CommandParseListener):
  positionals : typing.List[ElementValueNode]
  keywordargs : typing.List[KeywordArgumentInfoNode]
  fulltext : str # we need this to accurately collect the string; whitespaces are excluded in ctx.getText()
  global_offset : int
  is_in_positionals : bool
  kw_name : ElementValueNode | None
  kw_value : ElementValueNode | None
  start : int
  end : int
  result : ArgumentInfoNode

  def __init__(self, fulltext : str, global_offset : int) -> None:
    super().__init__()
    self.positionals = []
    self.keywordargs = []
    self.fulltext = fulltext
    self.is_in_positionals = False
    self.global_offset = global_offset
    self.kw_name = None
    self.kw_value = None
    self.start = -1
    self.end = -1
    self.result = None
  
  def enterPositionals(self, ctx: CommandParseParser.PositionalsContext):
    self.is_in_positionals = True
  
  def exitPositionals(self, ctx: CommandParseParser.PositionalsContext):
    self.is_in_positionals = False
  
  def enterValue(self, ctx: CommandParseParser.ValueContext):
    element = _parseValue(self.global_offset, ctx)
    if self.is_in_positionals:
      # we are handling positional arguments
      self.positionals.append(element)
    else:
      # we are handling keyword arguments
      assert self.kw_value is None
      self.kw_value = element
    # update start and end
    if self.start == -1:
      self.start = element.start
    if self.end == -1 or self.end < element.end:
      self.end = element.end

  def enterName(self, ctx: CommandParseParser.NameContext):
    name = _parseName(self.global_offset, ctx)
    assert not self.is_in_positionals
    assert self.kw_name is None
    self.kw_name = name
    # update start and end
    if self.start == -1:
      self.start = name.start
    if self.end == -1 or self.end < name.end:
      self.end = name.end
  
  def exitKwvalue(self, ctx: CommandParseParser.KwvalueContext):
    assert self.kw_name is not None and self.kw_value is not None
    kwnode = KeywordArgumentInfoNode(self.kw_name.start, self.kw_value.end, self.fulltext[self.kw_name.start: self.kw_value.end], self.kw_name, self.kw_value)
    self.keywordargs.append(kwnode)
    self.kw_name = None
    self.kw_value = None
  
  def exitArgumentlist(self, ctx: CommandParseParser.ArgumentlistContext):
    self.result = ArgumentInfoNode(self.start, self.end, self.fulltext[self.start: self.end], self.positionals, self.keywordargs)
  
  def getResult(self) -> ArgumentInfoNode:
    assert self.result is not None
    return self.result

def _handleScanResult(text : str, info : _InitParsedCommandInfo) -> ASTNodeBase | None:
  # the position info from the last stage is using closed interval, i.e. body is in range [command_start, command_end]
  # so if the body is empty, we would have command_start == command_end+1
  command_body_start, command_body_end = info.body_range

  # skip empty body
  if command_body_start > command_body_end:
    return None
  
  # change the convention to the one python use, i.e. [command_start, command_end] -> [command_start, command_end)
  command_body_end += 1
  command_body_text = text[command_body_start:command_body_end]
  command_total_start, command_total_end = info.total_range
  command_total_end += 1
  
  # if this is a comment block, we don't need to run the next stage parser
  if info.is_comment:
    return CommentNode(start=command_total_start, end=command_total_end, text=text[command_total_start:command_total_end])
  
  istream = antlr4.InputStream(command_body_text)
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
  name_node = tree.name()
  if name_node is None:
    # cannot identify the name field
    return UnrecognizedPartNode(start=command_total_start, end=command_total_end, text=text[command_total_start:command_total_end])
  
  # this will become the name member in the AST root node
  name = _parseName(command_body_start, name_node)

  # if there are parsing errors, we do not consider arguments as correctly parsed
  argumentlist_node = None
  if not error_listener.error_occurred:
    argumentlist_node = tree.argumentlist()
  
  parsed_args = None
  if argumentlist_node is not None:
    assert isinstance(argumentlist_node, CommandParseParser.ArgumentlistContext)
    argumentlist_listener = _CommandArgListener(text, command_body_start)
    walker = antlr4.ParseTreeWalker()
    walker.walk(argumentlist_listener, argumentlist_node)
    parsed_args = argumentlist_listener.getResult()

  # now determine the range of arguments
  raw_args_start = 0
  raw_args_end = 0
  raw_args_text = ""
  if parsed_args is not None:
    # if we have the parsed arguments, we just get the range from there
    raw_args_start = parsed_args.start
    raw_args_end = parsed_args.end
    raw_args_text = parsed_args.text
  else:
    # we need to compute that by ourselves
    # if we have the separator (':') symbol, we use this to determine the start position of arguments
    # otherwise we assume arguments begin immediately after the command name
    # in any case we will trim whitespace before and after the text
    raw_args_start = name.end
    separator_node = tree.COMMANDSEP()
    if separator_node is not None:
      separator_token = separator_node.getSymbol()
      new_start = command_body_start + separator_token.end + 1
      assert raw_args_start < new_start
      raw_args_start = new_start
    raw_args_end = command_body_end
    raw_args_text, lead_ws, trailing_ws = _strip_whitespaces(text[raw_args_start:raw_args_end])
    raw_args_start += lead_ws
    raw_args_end -= trailing_ws
  raw_args = ASTNodeBase(raw_args_start, raw_args_end, raw_args_text)
  return CommandNode(command_total_start, command_total_end, text[command_total_start:command_total_end], name, raw_args, parsed_args)

def _create_command_ast_impl(text : str, debugloc : typing.Any) -> CommandAST:
  scan_result = _splitTextAsCommands(text)
  if scan_result is None:
    # this text does not include command
    return None
  bodylist = []
  for info in scan_result:
    cur_result = _handleScanResult(text, info)
    if cur_result is None:
      continue
    assert isinstance(cur_result, UnrecognizedPartNode) or isinstance(cur_result, CommentNode) or isinstance(cur_result, CommandNode)
    bodylist.append(cur_result)
  return CommandAST(debugloc=debugloc, bodylist=bodylist)
