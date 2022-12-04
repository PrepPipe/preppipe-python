# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
import dataclasses

# ------------------------------------------------------------------------------
# Command AST definition
# ------------------------------------------------------------------------------
# We only specify AST for "commands" (similar to function calls) and comments here

@dataclasses.dataclass
class ASTNodeBase:
  start : int # index of first character of this AST node
  end : int # index +1 of last character of this AST node
  text: str # content of this node

  def to_string(self, _indent : int) -> str:
    return '\"' + self.text + '\" ' + '[' + str(self.start) + ',' + str(self.end) + ']'
  
  def __str__(self) -> str:
    return self.to_string(0)

@dataclasses.dataclass
class ElementValueNode(ASTNodeBase): # only contains fields of ASTNodeBase; nothing else
  quoted : typing.Tuple[int, int] | None # number of characters to drop at beginning and at the end of the text string because the content is quoted
  
  def getContent(self) -> str:
    if self.quoted is None:
      return self.text
    return self.text[self.quoted[0] : -self.quoted[1]]
  
  def to_string(self, indent: int) -> str:
    if self.quoted is None:
      return super().to_string(indent)
    return '\"' + self.getContent() + '\" ' + '[' + str(self.start) + '+' + self.quoted[0] + ',' + str(self.end) + '-' + self.quoted[1] + ')'

@dataclasses.dataclass
class UnrecognizedPartNode(ASTNodeBase): # command blocks that we cannot retrieve command name
  def to_string(self, indent: int) -> str:
    return "Unrecognized " + super().to_string(indent)

@dataclasses.dataclass
class CommentNode(ASTNodeBase): # command blocks that are explicitly comments
  def to_string(self, indent: int) -> str:
    return "Comment " + super().to_string(indent)

@dataclasses.dataclass
class KeywordArgumentInfoNode(ASTNodeBase):
  keyword : ElementValueNode # name of the argument
  value : ElementValueNode # value of the node

  def to_string(self, indent: int) -> str:
    return 'KWArg ' + super().to_string(indent) + '\n' + '  '*(indent+1) + 'K: ' + self.keyword.to_string(indent+1) + '\n' + '  '*(indent+1) + 'V: ' + self.value.to_string(indent+1)

@dataclasses.dataclass
class ArgumentInfoNode(ASTNodeBase): # for commands that we can parse the arguments
  positionals : typing.List[ElementValueNode] # info of positional arguments
  keywordargs : typing.List[KeywordArgumentInfoNode] # info of keyword arguments

  def to_string(self, indent: int) -> str:
    result = 'ArgInfo ' + super().to_string(indent)
    if len(self.positionals) > 0:
      result += '\n' + '  '*indent + 'Positional: #' + str(len(self.positionals)) + ':'
      for v in self.positionals:
        result += '\n' + '  '*(indent+1) + v.to_string(indent+1)
    if len(self.keywordargs) > 0:
      result += '\n' + '  '*indent + 'Keyword Arg: #' + str(len(self.keywordargs)) + ':'
      for kv in self.keywordargs:
        result += '\n' + '  '*(indent+1) + kv.to_string(indent+1)
    return result

@dataclasses.dataclass
class CommandNode(ASTNodeBase): # any command that we are able to get the name
  name : ElementValueNode # name of the command
  raw_args : ASTNodeBase # raw info of arguments (useful for commands with custom parsing)
  parsed_args : ArgumentInfoNode | None # if we can parse the arguments, the info will be here

  def to_string(self, indent: int) -> str:
    result = 'Command ' + super().to_string(indent) + '\n'
    result += '  '*(indent+1) + 'Name ' + self.name.to_string(indent+1) + '\n'
    result += '  '*(indent+1) + 'RawArgs ' + self.raw_args.to_string(indent+1)
    if self.parsed_args is not None:
      result += '\n' + '  '*(indent+1) + self.parsed_args.to_string(indent+1)
    return result

@dataclasses.dataclass
class CommandAST:
  debugloc: typing.Any # debug location of this AST
  bodylist: typing.List[ASTNodeBase] # list of parsed command info

  def to_string(self, _indent: int) -> str:
    result = "CommandAST DebugLoc=" + str(self.debugloc)
    for body in self.bodylist:
      result += '\n' + '  ' + body.to_string(1)
    return result
