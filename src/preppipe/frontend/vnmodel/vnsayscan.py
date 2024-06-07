# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

#from .vncodegen import *

import dataclasses
from typing import Any
import antlr4
from antlr4.error.ErrorListener import ConsoleErrorListener

from preppipe.frontend.vnmodel._antlr_generated.SayScanParser import SayScanParser
from ...util.antlr4util import ErrorListenerBase
from ._antlr_generated.SayScanLexer import SayScanLexer
from ._antlr_generated.SayScanParser import SayScanParser
from ._antlr_generated.SayScanVisitor import SayScanVisitor

#def emit_say_expr(text : list[Value]) -> VNASTSayNodeBase:
  #    苏语涵：这是我说的话
  #    苏语涵：“这是我说的话”
  #    苏语涵（平静）：这是我说的话
  #    【苏语涵】这是我说的话
  #    【苏语涵】（平静）这是我说的话
#  pass

from ._antlr_generated.SayScanVisitor import *

@dataclasses.dataclass
class SayScanFieldPosition:
  # 描述(发言者|状态|内容)中某一项的结构体
  # 如果内容有被括号引起来的话，两项都不应包含括号内容
  start : int
  end : int
  text : str
  # 英语中我们可能在引号内不加空格、在引号外加空格，所以像这样的语句：
  # Yuhan: "Sentence 3", ignored, "continued."
  # 说话内容就会成为 "Sentence 3continued."
  # 当发现这类情况是，我们看原文中在引号后的字符（除了标点符号外）是否是空格，如果是的话我们就在这里加上一个空格
  flag_append_space : bool = False

  def __str__(self) -> str:
    return '[' + str(self.start) + ',' + str(self.end) + ')"' + self.text + '"'

@dataclasses.dataclass
class SayScanResult:
  sayer : SayScanFieldPosition | None = None
  expression : list[SayScanFieldPosition] | None = None

  # 如果发言内容带引号的话我们有可能会有不止一段内容，所以这里用个 list
  content : list[SayScanFieldPosition] = dataclasses.field(default_factory=list)
  is_content_quoted : bool = False

  def __str__(self) -> str:
    result = ''
    if self.sayer is not None:
      result += str(self.sayer)
    if self.expression is not None:
      result += '(' + ','.join([str(v) for v in self.expression]) + ')'
    if len(result) > 0:
      result += ': '
    for c in self.content:
      result += str(c)
    return result

class SayScanner(SayScanVisitor):
  result : SayScanResult
  rawtext : str

  def __init__(self, rawtext : str) -> None:
    super().__init__()
    self.result = SayScanResult()
    self.rawtext = rawtext

  def handle_quoted_str(self, node : antlr4.TerminalNode) -> SayScanFieldPosition:
    quoted_str_token = node.getSymbol()
    # 需要把引号去掉
    start = quoted_str_token.start + 1
    end = quoted_str_token.stop
    text = quoted_str_token.text[1:-1]
    return SayScanFieldPosition(start, end, text)

  def handle_normal_str(self, node : antlr4.TerminalNode) -> SayScanFieldPosition:
    natural_text_token = node.getSymbol()
    start = natural_text_token.start
    end = natural_text_token.stop + 1
    text = natural_text_token.text
    return SayScanFieldPosition(start, end, text)

  def collect_all_child(self, node : antlr4.ParserRuleContext) -> SayScanFieldPosition:
    firstsymbol = node.getChild(0)
    while not isinstance(firstsymbol, antlr4.TerminalNode):
      firstsymbol = firstsymbol.getChild(0)
    start = firstsymbol.getSymbol().start

    numchildren = node.getChildCount()
    lastsymbol = node.getChild(numchildren-1)
    while not isinstance(lastsymbol, antlr4.TerminalNode):
      numchildren = lastsymbol.getChildCount()
      lastsymbol = lastsymbol.getChild(numchildren-1)
    end = lastsymbol.getSymbol().stop + 1

    text = node.getText()
    return SayScanFieldPosition(start, end, text)

  def trim_text(self, field : SayScanFieldPosition, trim_start : bool = True, trim_end : bool = True) -> SayScanFieldPosition:
    # 原地调整 field 的 start 和 end 以去掉前后的空白
    is_changed = False
    if trim_start:
      while field.start < field.end and self.rawtext[field.start].isspace():
        field.start += 1
        is_changed = True
    if trim_end:
      while field.start < field.end and self.rawtext[field.end-1].isspace():
        field.end -= 1
        is_changed = True
    if is_changed:
      field.text = self.rawtext[field.start:field.end]
    return field

  def should_add_whitespace_after_quoted_str(self, stop : int) -> bool:
    # 目前我们只考虑英语的情况，所以只检查 ASCII 字符
    curpos : int = stop + 1 # 跳过引号
    while curpos < len(self.rawtext):
      nextchar = self.rawtext[curpos]
      if nextchar == ' ':
        return True
      elif nextchar == ',':
        curpos += 1
        continue
      else:
        return False
    return False

  def visitNameexpr(self, ctx: SayScanParser.NameexprContext):
    if node := ctx.QUOTEDSTR():
      self.result.sayer = self.handle_quoted_str(node)
      return
    if node := ctx.NORMALTEXT():
      self.result.sayer = self.trim_text(self.handle_normal_str(node))
      return
    raise RuntimeError("should not happen")

  def visitNameexpr_strong(self, ctx:SayScanParser.Nameexpr_strongContext):
    if node := ctx.QUOTEDSTR():
      self.result.sayer = self.handle_quoted_str(node)
      return
    raise RuntimeError("should not happen")

  def visitStatusexpr(self, ctx:SayScanParser.StatusexprContext):
    if node := ctx.NORMALTEXT():
      if isinstance(node, list):
        self.result.expression = [self.trim_text(self.handle_normal_str(v)) for v in node]
      else:
        self.result.expression = [self.trim_text(self.handle_normal_str(node))]

  def visitContentexpr(self, ctx:SayScanParser.ContentexprContext):
    # 如果第一个终结符是 QUOTEDSTR, 那么我们只处理所有 QUOTEDSTR
    # 如果第一个终结符是 NORMALTEXT 或是 SENTENCESPLITTER, 那么我们把所有内容都算进来
    firstchild = ctx.getChild(0)
    match firstchild.getSymbol().type:
      case SayScanParser.QUOTEDSTR:
        for c in ctx.QUOTEDSTR():
          curresult = self.handle_quoted_str(c)
          # 检查该内容是否需要在后面加空格
          if (self.should_add_whitespace_after_quoted_str(curresult.end)):
            curresult.flag_append_space = True
          self.result.content.append(curresult)
        # 内容的最后一项后面肯定不加空格
        if len(self.result.content) > 0:
          self.result.content[-1].flag_append_space = False
        self.result.is_content_quoted = True
      case SayScanParser.NORMALTEXT | SayScanParser.SENTENCESPLITTER:
        curresult = self.collect_all_child(ctx)
        self.result.content.append(curresult)
      case _:
        raise RuntimeError("should not happen")

  def visitContentexpr_strong(self, ctx:SayScanParser.Contentexpr_strongContext):
    if node := ctx.QUOTEDSTR():
      curresult = self.handle_quoted_str(node)
      self.result.content.append(curresult)
      self.result.is_content_quoted = True

def analyze_say_expr(text : str, *, debug : bool = False) -> SayScanResult | None:
  error_listener = ErrorListenerBase()
  istream = antlr4.InputStream(text)
  lexer = SayScanLexer(istream)
  lexer.removeErrorListeners()
  lexer.addErrorListener(error_listener)
  #lexer.addErrorListener(ConsoleErrorListener())
  tstream = antlr4.CommonTokenStream(lexer)
  parser = SayScanParser(tstream)
  parser.removeErrorListeners(); # remove ConsoleErrorListener
  parser.addErrorListener(error_listener)
  #parser.addErrorListener(ConsoleErrorListener())
  tree = parser.sayexpr()
  if error_listener.error_occurred:
    if debug:
      print(str(error_listener.get_first_error_column()) + ': ' + error_listener.get_first_error_msg())
      print(tree.toStringTree())
    return None
  if debug:
    print(tree.toStringTree())
  scanner = SayScanner(text)
  scanner.visit(tree)
  return scanner.result

def _test_main():
  def test(text : str):
    print('Testing: ' + text)
    if result := analyze_say_expr(text, debug=True):
      print(str(result))
  test('这是我说的话')
  test('"这是我说的话"')
  test('（平静）"这是我说的话"')
  test('（平静）"这是我说的话"。这是该忽略的内容。“这又是另一句话。”')
  test('苏语涵：这是我说的话')
  test('苏语涵：这是我说的话(这是注释不是表情)')
  test('苏语涵：“这是我说的话”')
  test('苏语涵：“这是我说的话”(这是注释不是表情)')
  test('苏语涵（平静）：这是我说的话')
  test('【苏语涵】这是我说的话')
  test('【苏语涵】（平静）这是我说的话')
  test('【苏语涵】（平静）这是我说的话(这是注释不是表情)')

if __name__ == "__main__":
  _test_main()
