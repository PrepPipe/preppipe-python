# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import typing
import chardet
import marko
import marko.block
import marko.inline
import marko.ext.gfm.elements

from ..irbase import *
from ..inputmodel import *
from ..pipeline import *
from ..language import TranslationDomain

_TR_markdown = TranslationDomain("markdown")

# 已知问题：行号和列号基本都是错的。。marko库好像也不记录这个，暂时没有好的解决方案

class _MarkdownParser:
  context : Context
  filepath : str
  dochandle : marko.block.Document
  difile : DIFile
  documentname : str
  result : IMDocumentOp
  row : int

  def __init__(self, ctx : Context, filepath : str) -> None:
    self.context = ctx
    self.filepath = filepath

    with open(filepath, "rb") as f:
      data = f.read()
      det = chardet.detect(data, should_rename_legacy=True)
      strcontent = data.decode(encoding=det["encoding"], errors="ignore")
      md = marko.Markdown(extensions=["gfm"])
      self.dochandle = md.parse(strcontent)

    self.difile = ctx.get_DIFile(filepath)
    self.documentname = os.path.splitext(os.path.basename(filepath))[0]
    self.result = IMDocumentOp.create(self.documentname, self.difile)
    self.row = 0

  def get_full_path_from_href(self, href : str) -> str:
    return os.path.normpath(os.path.join(os.path.dirname(self.filepath), href))

  _tr_exturl_notsupported = _TR_markdown.tr("exturl_not_supported",
    en="External URL not supported: {url}",
    zh_cn="外部链接暂不支持：{url}",
    zh_hk="外部鏈接暫不支持：{url}",
  )
  _tr_file_notfound = _TR_markdown.tr("file_not_found_or_accessible",
    en="File not found or accessible: {path}",
    zh_cn="文件不存在或无法读取：{path}",
    zh_hk="文件不存在或無法讀取：{path}",
  )

  def parse_paragraph_like(self, p : marko.block.Paragraph | marko.block.Heading | marko.ext.gfm.elements.TableCell):
    col = 1
    coalescer = _MarkdownTextCoalescer(self.context)

    def handle_rawtext(c: marko.inline.RawText | marko.inline.CodeSpan, is_strike_through : bool = False, is_bold : bool = False, is_italic : bool = False):
      # 原本的 markdown 也不支持文字颜色或是背景色，所以这里我们不管
      nonlocal col
      nonlocal coalescer
      text = c.children
      if not isinstance(text, str):
        raise PPInternalError()
      if not is_strike_through:
        sl = StringLiteral.get(text, self.context)
        content = sl
        if is_bold or is_italic:
          styledict = {}
          if is_bold:
            styledict[TextAttribute.Bold] = True
          if is_italic:
            styledict[TextAttribute.Italic] = True
          style = TextStyleLiteral.get(styledict, self.context)
          content = TextFragmentLiteral.get(self.context, sl, style)
        coalescer.add_value(content, (self.row, col))
      col += len(text)

    def handle_textcommon(c: marko.inline.RawText | marko.inline.StrongEmphasis, is_strike_through : bool = False, is_bold : bool = False, is_italic : bool = False):
      if isinstance(c, (marko.inline.RawText, marko.inline.CodeSpan, marko.inline.Literal)):
        handle_rawtext(c, is_strike_through, is_bold, is_italic)
      elif isinstance(c, marko.inline.StrongEmphasis):
        is_bold = True
        handle_textcommon(c.children[0], is_strike_through, is_bold, is_italic)
      elif isinstance(c, marko.inline.Emphasis):
        is_italic = True
        handle_textcommon(c.children[0], is_strike_through, is_bold, is_italic)
      elif isinstance(c, marko.ext.gfm.elements.Strikethrough):
        is_strike_through = True
        handle_textcommon(c.children[0], is_strike_through, is_bold, is_italic)
      elif isinstance(c, (marko.inline.Link, marko.ext.gfm.elements.Url)):
        # 不尝试读取目的链接，仅当作普通文本
        handle_textcommon(c.children[0], is_strike_through, is_bold, is_italic)
      else:
        raise PPNotImplementedError()

    for c in p.children:
      if isinstance(c, marko.inline.Image):
        href = c.dest
        alttext = ""
        if len(c.children) > 0:
          alttext_elem = c.children[0]
          if not isinstance(alttext_elem, marko.inline.RawText):
            raise PPInternalError()
          alttext = alttext_elem.children
        alttextsl = StringLiteral.get(alttext,self.context)
        if href.startswith(("http://", "https://", "ftp://")):
          msg = self._tr_exturl_notsupported.format(url=href)
          content = IMErrorElementOp.create('', self.context.get_DILocation(self.difile, 0, self.row, col), alttextsl, "markdown-exturl-not-supported", StringLiteral.get(msg, self.context))
          coalescer.add_value (content, (self.row, col))
        elif self.context.get_file_auditor().check_is_path_accessible(href_full_path:= self.get_full_path_from_href(href)):
          content = self.context.get_or_create_image_asset_data_external(href_full_path)
          coalescer.add_value (content, (self.row, col))
        else:
          msg = self._tr_file_notfound.format(path=href_full_path)
          content = IMErrorElementOp.create('', self.context.get_DILocation(self.difile, 0, self.row, col), alttextsl, "markdown-file-not-supported", StringLiteral.get(msg, self.context))
          coalescer.add_value (content, (self.row, col))
      elif isinstance(c, marko.inline.LineBreak):
        self.row += 1
      else:
        handle_textcommon(c)
    coalescer.commit()
    return coalescer

  def parse_paragraph(self, p : marko.block.Paragraph, dest : Block):
    coalescer = self.parse_paragraph_like(p)
    pending_content = coalescer.contents
    locations = coalescer.locations
    del coalescer
    last_text_element : IMElementOp | None = None
    for c, loc in zip(pending_content, locations):
      if isinstance(c, (StringLiteral, TextFragmentLiteral)):
        if last_text_element is not None:
          last_text_element.content.add_operand(c)
        else:
          last_text_element = IMElementOp.create(c, '', self.context.get_DILocation(self.difile, 0, loc[0], loc[1]))
          dest.push_back(last_text_element)
      elif isinstance(c, AssetData):
        last_text_element = None
        element = IMElementOp.create(c, '', self.context.get_DILocation(self.difile, 0, loc[0], loc[1]))
        dest.push_back(element)
      elif isinstance(c, Operation):
        last_text_element = None
        dest.push_back(c)
      else:
        raise PPInternalError()

  def get_single_str_from_coalescer(self, coalescer, nontext_handler : typing.Callable | None = None) -> tuple[str, tuple[int, int]] | None:
    assert isinstance(coalescer, _MarkdownTextCoalescer)
    pending_content = coalescer.contents
    locations = coalescer.locations
    del coalescer
    comment_str = ""
    comment_loc = None
    for c, loc in zip(pending_content, locations):
      if isinstance(c, (StringLiteral, TextFragmentLiteral)):
        comment_str += c.get_string()
        if comment_loc is None:
          comment_loc = loc
      else:
        if nontext_handler:
          nontext_handler(c, loc)
        else:
          comment_str += str(c)
          if comment_loc is None:
            comment_loc = loc
    if len(comment_str) > 0:
      assert comment_loc is not None
      return (comment_str, comment_loc)
    return None

  def parse_heading(self, h : marko.block.Heading, dest : Block):
    # 我们把所有标题都当作注释
    # 图片单独拎出来，其他部分都作注释
    coalescer = self.parse_paragraph_like(h)
    def nontext_handler(c):
      if isinstance(c, AssetData):
        element = IMElementOp.create(c, '', self.context.get_DILocation(self.difile, 0, loc[0], loc[1]))
        dest.push_back(element)
      elif isinstance(c, Operation):
        dest.push_back(c)
      else:
        raise PPInternalError()
    if comment_result := self.get_single_str_from_coalescer(coalescer, nontext_handler):
      comment_str, comment_loc = comment_result
      comment = CommentOp.create(StringLiteral.get(comment_str, self.context), '', loc=self.context.get_DILocation(self.difile, 0, comment_loc[0], comment_loc[1]))
      dest.push_back(comment)

  def parse_list(self, l : marko.block.List):
    result = IMListOp.create('', self.context.get_DILocation(self.difile, 0, self.row, 0))
    for li in l.children:
      if not isinstance(li, marko.block.ListItem):
        raise PPInternalError()
      result_item = result.add_list_item()
      self.row += 1
      for be in li.children:
        destblock = result_item.create_block()
        if isinstance(be, marko.block.Paragraph):
          self.parse_paragraph(be, destblock)
        elif isinstance(be, marko.block.List):
          nested = self.parse_list(be)
          destblock.push_back(nested)
        else:
          raise PPNotImplementedError()
    return result

  def parse_quote(self, q : marko.block.Quote, dest : Block):
    # 所有的 BlockQuote 都作为注释
    comment_rows = []
    locations = []
    def parse_quote_impl(qe : marko.block.Quote):
      nonlocal comment_rows
      nonlocal locations
      for c in qe.children:
        if isinstance(c, marko.block.Paragraph):
          coalescer = self.parse_paragraph_like(c)
          if result := self.get_single_str_from_coalescer(coalescer):
            content, loc = result
            comment_rows.append(content)
            locations.append(loc)
          self.row += 1
        elif isinstance(c, marko.block.Quote):
          parse_quote_impl(c)
        elif isinstance(c, marko.block.BlankLine):
          comment_rows.append('')
          locations.append((self.row,0))
          self.row += 1
        else:
          raise PPNotImplementedError()
    parse_quote_impl(q)
    for c, loc in zip(comment_rows, locations):
      op = CommentOp.create(StringLiteral.get(c, self.context), '', self.context.get_DILocation(self.difile, 0, loc[0], loc[1]))
      dest.push_back(op)

  def parse_code_block_like(self, cb : marko.block.CodeBlock | marko.block.FencedCode, dest : Block):
    rawtext = cb.children[0]
    if not isinstance(rawtext, marko.inline.RawText):
      raise PPInternalError()
    code = rawtext.children
    lines = [ StringLiteral.get(s, self.context) for s in code.splitlines() ]
    content = StringListLiteral.get(self.context, lines)
    result = IMSpecialBlockOp.create(content, IMSpecialBlockOp.ATTR_REASON_BG_HIGHLIGHT, '', self.context.get_DILocation(self.difile, 0, self.row, 0))
    dest.push_back(result)
    self.row += len(lines)

  def parse_table(self, t : marko.ext.gfm.elements.Table, dest : Block):
    rows = []
    startrow = self.row
    ncols = 0
    def nontext_handler(c):
      pass
    for row in t.children:
      if not isinstance(row, marko.ext.gfm.elements.TableRow):
        raise PPInternalError()
      currow = []
      self.row += 1
      for cell in row.children:
        if not isinstance(cell, marko.ext.gfm.elements.TableCell):
          raise PPInternalError()
        coalescer = self.parse_paragraph_like(cell)
        if res := self.get_single_str_from_coalescer(coalescer, nontext_handler):
          text, loc = res
          currow.append(StringLiteral.get(text, self.context))
        else:
          currow.append(None)
      if len(currow) > ncols:
        ncols = len(currow)
    if len(rows) > 0:
      result = IMTableOp.create(len(rows), ncols, '', self.context.get_DILocation(self.difile, 0, startrow, 0))
      # pylint: disable=consider-using-enumerate
      for i in range(0, len(rows)):
        currow = rows[i]
        for j in range(0, len(currow)):
          cell = currow[j]
          if cell is not None:
            result.get_cell_operand(i, j).add_operand(cell)
      dest.push_back(result)

  def parse(self):
    for be in self.dochandle.children:
      assert isinstance(be, marko.block.BlockElement)
      destblock = self.result.body.create_block()
      if isinstance(be, marko.block.Paragraph):
        self.parse_paragraph(be, destblock)
        self.row += 1
      elif isinstance(be, marko.block.Heading):
        self.parse_heading(be, destblock)
        self.row += 1
      elif isinstance(be, marko.block.List):
        resultlist = self.parse_list(be)
        destblock.push_back(resultlist)
      elif isinstance(be, marko.block.BlankLine):
        self.row += 1
      elif isinstance(be, marko.block.Quote):
        self.parse_quote(be, destblock)
      elif isinstance(be, marko.block.ThematicBreak):
        self.row += 1
      elif isinstance(be, (marko.block.CodeBlock, marko.block.FencedCode)):
        self.parse_code_block_like(be, destblock)
      elif isinstance(be, marko.ext.gfm.elements.Table):
        self.parse_table(be, destblock)
      elif isinstance(be, marko.block.LinkRefDef):
        pass
      else:
        raise PPNotImplementedError()

  @staticmethod
  def parse_markdown(ctx : Context, filepath : str) -> IMDocumentOp:
    p = _MarkdownParser(ctx, filepath)
    p.parse()
    return p.result

  # 下面只是用于调试的代码

  @staticmethod
  def _dumpimpl(node, indent : int):
    print(type(node).__name__, end="")
    if isinstance(node, marko.block.BlockElement):
      print(" [B]")
      for c in node.children:
        print("  "*(indent+1),end="")
        _MarkdownParser._dumpimpl(c, indent+1)
    elif isinstance(node, marko.inline.InlineElement):
      if hasattr(node, "dest"):
        print(" [I]: " + str(getattr(node, "dest")))
      else:
        print(" [I]")
      if isinstance(node, marko.inline.LineBreak):
        # 只会多打空行出来，不理会
        pass
      elif isinstance(node.children, str):
        print("  "*(indent+1) + node.children)
      elif isinstance(node.children, list):
        print("  "*(indent+1) + "len(list)=" + str(len(node.children)))
        for c in node.children:
          print("  "*(indent+1), end="")
          if isinstance(c, marko.inline.InlineElement):
            _MarkdownParser._(c, indent+1)
          else:
            print(str(c))
      else:
        raise NotImplementedError("Unhandled child type: " + type(node.children).__name__)
    else:
      raise NotImplementedError("Unhandled node type: " + type(node).__name__)

  @staticmethod
  def dumptree(doc : marko.block.Document):
    for i in range(0, len(doc.children)):
      print("["+str(i)+"] ", end="")
      _MarkdownParser._dumpimpl(doc.children[i], 0)

  @staticmethod
  def dumpfile(path):
    with open(path, "r", encoding="utf-8") as f:
      md = marko.Markdown(extensions=["gfm"])
      doc = md.parse(f.read())
      _MarkdownParser.dumptree(doc)

class _MarkdownTextCoalescer:
  contents : list[Value | Operation]
  locations : list[tuple[int, int]]
  s : str
  style : TextStyleLiteral | None
  loc : tuple[int, int]
  context : Context

  def __init__(self, ctx : Context) -> None:
    self.contents = []
    self.locations = []
    self.s = ''
    self.style = None
    self.loc = -1
    self.context = ctx

  def commit(self):
    if len(self.s) > 0:
      v = StringLiteral.get(self.s, self.context)
      if self.style is not None:
        v = TextFragmentLiteral.get(self.context, v, self.style)
      self.contents.append(v)
      self.locations.append(self.loc)
    self.s = ''
    self.style = None
    self.loc = (-1, -1)

  def add_value(self, content : Value | Operation, location : tuple[int, int]):
    if isinstance(content, (StringLiteral, TextFragmentLiteral)):
      cur_s = content.get_string()
      cur_style = None
      if isinstance(content, TextFragmentLiteral):
        cur_style = content.style
      if self.loc == -1:
        # 开启新串
        self.s = cur_s
        self.style = cur_style
        self.loc = location
      elif self.style is cur_style:
        self.s += cur_s
      else:
        # 不同的串
        self.commit()
        self.s = cur_s
        self.style = cur_style
        self.loc = location
    else:
      self.commit()
      self.contents.append(content)
      self.locations.append(location)

@FrontendDecl('md', input_decl=IODecl('Markdown files', match_suffix=('md',), nargs='+'), output_decl=IMDocumentOp)
class ReadMarkdown(TransformBase):
  def run(self) -> IMDocumentOp | typing.List[IMDocumentOp]:
    if len(self.inputs) == 1:
      return _MarkdownParser.parse_markdown(self._ctx, self.inputs[0])
    results = []
    for f in self.inputs:
      results.append(_MarkdownParser.parse_markdown(self._ctx, f))
    return results

if __name__ == "__main__":
  _MarkdownParser.dumpfile(sys.argv[1])