# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import docx
import docx.document
import docx.parts
import docx.parts.image
import docx.text.run
import docx.text.paragraph
import docx.enum.text
import docx.styles.style
import lxml
import lxml.etree
import zipfile
import os
import sys
import typing
import dataclasses

from ..irbase import *
from ..inputmodel import *

class _DOCXParseContext:
  @dataclasses.dataclass
  class CharacterStyle:
    bgcolor : Color | None = None
    fgcolor : Color | None = None
    bold : bool = False
    italic : bool = False

  @dataclasses.dataclass
  class ParagraphStyle:
    bgcolor : Color | None = None
    align_mid : bool = False
    list_level : int | None = None

  context : Context
  filepath : str
  dochandle : docx.document.Document
  ziphandle : zipfile.ZipFile
  difile : DIFile
  documentname : str
  nsprefix : typing.Literal[r"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"]

  rels : dict[str, str]
  textstyles : dict[str, TextStyleLiteral | None]
  character_styles : dict[str, CharacterStyle]
  paragraph_styles : dict[str, ParagraphStyle]
  result : IMDocumentOp

  def __init__(self, ctx : Context, filepath : str) -> None:
    self.context = ctx
    self.filepath = filepath
    self.dochandle = docx.Document(filepath)
    self.ziphandle = zipfile.ZipFile(filepath, mode = "r")
    self.difile = ctx.get_DIFile(filepath)
    self.documentname = os.path.splitext(os.path.basename(filepath))[0]
    self.nsprefix=r"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    self.rels = {}
    self.textstyles = {}
    self.character_styles = {}
    self.paragraph_styles = {}
    self.result = IMDocumentOp.create(self.documentname, self.difile)

  def cleanup(self):
    self.ziphandle.close()

  def parse_rels(self):
    # https://stackoverflow.com/questions/27691678/finding-image-present-docx-file-using-python/61331396#61331396?newreg=ed63b33ba36847ccbdc19f5d20494cab
    for r in self.dochandle.part.rels.values():
      if isinstance(r._target, docx.parts.image.ImagePart):
        self.rels[r.rId] = os.path.basename(r._target.partname)

  def get_paragraph_bgcolor_impl(self, ps : docx.styles.style._ParagraphStyle | docx.text.paragraph.Paragraph) -> Color | None:
    element = ps.paragraph_format.element
    # 查找 <w:pPr> 下是否有 <w:shd> 项，有的话其中的 fill 属性就是背景颜色
    if pPr := element.find(self.nsprefix + "pPr"):
      if shd := pPr.find(self.nsprefix + "shd"):
        colorstr = shd.get(self.nsprefix + 'fill')
        if isinstance(colorstr, str):
          return Color.get('#' + colorstr)
    # 没有的话就没有了
    return None

  def get_paragraph_align_mid_impl(self, ps : docx.styles.style._ParagraphStyle | docx.text.paragraph.Paragraph) -> bool | None:
    if isinstance(ps, docx.styles.style._ParagraphStyle):
      alignment = ps.paragraph_format.alignment
    else:
      alignment = ps.alignment
    if alignment:
      return alignment == docx.enum.text.WD_PARAGRAPH_ALIGNMENT.CENTER
    return None

  def get_paragraph_listlevel_impl(self, ps: docx.styles.style._ParagraphStyle | docx.text.paragraph.Paragraph) -> int | None:
    if isinstance(ps, docx.styles.style._ParagraphStyle):
      return None
    # 查找 <w:pPr> 下是否有 <w:numPr>，有的话看里面是否有 <w:ilvl>
    if pPr := ps.paragraph_format.element.find(self.nsprefix + "pPr"):
      if numPr := pPr.find(self.nsprefix + "numPr"):
        if ilvl := numPr.find(self.nsprefix + "ilvl"):
          if lvlstr := ilvl.get(self.nsprefix+"val"):
            return int(lvlstr)
    return None

  def get_character_bold_impl(self, cs : docx.styles.style._CharacterStyle | docx.text.run.Run) -> bool | None:
    return cs.font.bold

  def get_character_italic_impl(self, cs : docx.styles.style._CharacterStyle | docx.text.run.Run) -> bool | None:
    return cs.font.italic

  def get_character_fg_color_impl(self, cs : docx.styles.style._CharacterStyle | docx.text.run.Run) -> Color | None:
    if color := cs.font.color:
      if rgbcolor := color.rgb:
        return Color(r=rgbcolor[0], g=rgbcolor[1], b=rgbcolor[2])
    return None

  def get_character_bg_color_impl(self, cs : docx.styles.style._CharacterStyle | docx.text.run.Run) -> Color | None:
    if color := cs.font.highlight_color:
      match color:
        case docx.enum.text.WD_COLOR_INDEX.AUTO:
          return None
        case docx.enum.text.WD_COLOR_INDEX.BLACK:
          return Color(0,0,0)
        case docx.enum.text.WD_COLOR_INDEX.BLUE:
          return Color(0,0,255)
        case docx.enum.text.WD_COLOR_INDEX.BRIGHT_GREEN:
          return Color(170, 255, 0)
        case docx.enum.text.WD_COLOR_INDEX.DARK_BLUE:
          return Color(0,0,139)
        case docx.enum.text.WD_COLOR_INDEX.DARK_RED:
          return Color(139,0,0)
        case docx.enum.text.WD_COLOR_INDEX.DARK_YELLOW:
          return Color(139, 128, 0)
        case docx.enum.text.WD_COLOR_INDEX.GRAY_25:
          return Color(64,64,64)
        case docx.enum.text.WD_COLOR_INDEX.GRAY_50:
          return Color(127,127,127)
        case docx.enum.text.WD_COLOR_INDEX.GREEN:
          return Color(0, 255, 0)
        case docx.enum.text.WD_COLOR_INDEX.PINK:
          return Color(255,192,203)
        case docx.enum.text.WD_COLOR_INDEX.RED:
          return Color(255,0,0)
        case docx.enum.text.WD_COLOR_INDEX.TEAL:
          return Color(0,128,128)
        case docx.enum.text.WD_COLOR_INDEX.TURQUOISE:
          return Color(64,224,208)
        case docx.enum.text.WD_COLOR_INDEX.VIOLET:
          return Color(128,0,128)
        case docx.enum.text.WD_COLOR_INDEX.WHITE:
          return Color(255,255,255)
        case docx.enum.text.WD_COLOR_INDEX.YELLOW:
          return Color(255,255,0)
        case _:
          return None

  def parse_styles(self):
    for s in self.dochandle.styles:
      if s.name is None:
        continue
      if isinstance(s, docx.styles.style._CharacterStyle):
        bgcolor = self.get_character_bg_color_impl(s)
        fgcolor = self.get_character_fg_color_impl(s)
        bold = self.get_character_bold_impl(s)
        italic = self.get_character_italic_impl(s)
        if bold is None:
          bold = False
        if italic is None:
          italic = False
        self.character_styles[s.name] = self.CharacterStyle(bgcolor=bgcolor, fgcolor=fgcolor, bold=bold, italic=italic)
      elif isinstance(s, docx.styles.style._ParagraphStyle):
        bgcolor = self.get_paragraph_bgcolor_impl(s)
        align_mid = self.get_paragraph_align_mid_impl(s)
        list_level = self.get_paragraph_listlevel_impl(s)
        if align_mid is None:
          align_mid = False
        self.paragraph_styles[s.name] = self.ParagraphStyle(bgcolor=bgcolor, align_mid=align_mid, list_level=list_level)

  def parse(self):
    self.parse_rels()
    self.parse_styles()
    self.parse_mainloop()
    self.cleanup()

  def get_path_from_rid(self, rid : str) -> str | None:
    if rid in self.rels:
      return "word/media/" + self.rels[rid]

  def get_full_path_from_epath(self, path : str) -> str:
    return os.path.normpath(os.path.join(self.filepath, path))

  def query_style(self, entity, cb : typing.Callable, stylecb : typing.Callable | None = None):
    if value := cb(entity):
      return value
    style = stylecb(entity) if stylecb is not None else entity.style
    value = cb(style)
    while value is None and style.base_style is not None:
      style = style.base_style
      value = cb(style)
    return value

  def get_paragraph_style(self, p : docx.text.paragraph.Paragraph) -> ParagraphStyle:
    src = self.paragraph_styles[p.style.name]
    bgcolor = src.bgcolor
    align_mid = src.align_mid
    list_level = src.list_level
    if bgcolor_override := self.get_paragraph_bgcolor_impl(p):
      bgcolor = bgcolor_override
    if align_mid_override := self.get_paragraph_align_mid_impl(p):
      align_mid = align_mid_override
    if list_level_override := self.get_paragraph_listlevel_impl(p):
      list_level = list_level_override
    return self.ParagraphStyle(bgcolor=bgcolor, align_mid=align_mid, list_level=list_level)

  def get_character_style(self, r : docx.text.run.Run) -> TextStyleLiteral | None:
    src = self.character_styles[r.style.name]
    styledict = {}
    if bgcolor := self.get_character_bg_color_impl(r):
      styledict[TextAttribute.BackgroundColor] = bgcolor
    elif src.bgcolor:
      styledict[TextAttribute.BackgroundColor] = src.bgcolor

    if fgcolor := self.get_character_fg_color_impl(r):
      styledict[TextAttribute.TextColor] = fgcolor
    elif src.fgcolor:
      styledict[TextAttribute.TextColor] = src.fgcolor

    bold = self.get_character_bold_impl(r)
    if bold is None:
      bold = src.bold
    if bold:
      styledict[TextAttribute.Bold] = True

    italic = self.get_character_italic_impl(r)
    if italic is None:
      italic = src.italic
    if italic:
      styledict[TextAttribute.Italic] = True

    if len(styledict) == 0:
      return None
    return TextStyleLiteral.get(styledict, self.context)

  def get_paragraph_alignment(self, p : docx.text.paragraph.Paragraph) -> docx.enum.text.WD_PARAGRAPH_ALIGNMENT | None:
    return self.query_style(p, lambda p : p.alignment)

  def parse_mainloop(self):
    # 目前暂不支持页码
    page = 0
    row = 0

    # 生成时直接合并相邻的特殊块和列表层级
    last_special_block : IMSpecialBlockOp | None = None
    current_ongoing_list : list[IMListOp] = []
    for p in self.dochandle.paragraphs:
      row += 1
      col = 1
      # 首先检查段落样式，是否是特殊块或者是列表
      pstyle = self.get_paragraph_style(p)
      special_block_reason : str | None = None
      list_level : int | None = pstyle.list_level
      if pstyle.align_mid:
        special_block_reason = IMSpecialBlockOp.ATTR_REASON_CENTERED
      elif pstyle.bgcolor is not None and pstyle.bgcolor.to_tuple() != (255, 255, 255):
        special_block_reason = IMSpecialBlockOp.ATTR_REASON_BG_HIGHLIGHT
      # 然后我们把内容弄出来
      # 即使是特殊块，我们也要按照正常的读取方式先读取一遍，这样可以不漏掉错误和内嵌的图片
      for r in p.runs:
        res = self.parse_run(r, page, row, col)
        # TODO 根据 res 分情况

  def parse_run(self, r : docx.text.run.Run, page : int, row : int, col : int) -> ErrorOp | AssetData | TextFragmentLiteral | StringLiteral | None:
    if len(r.text) > 0:
      # 文本内容
      s = StringLiteral.get(r.text, self.context)
      if style := self.get_character_style(r):
        return TextFragmentLiteral.get(self.context, s, style)
      return s
    else:
      # 内嵌内容
      # 参考 parse_rels() 中的链接
      if "Graphic" in r._r.xml:
        for rid in self.rels:
          if rid in r._r.xml:
            href = self.get_path_from_rid(rid)
            if href in self.ziphandle.namelist():
              data = self.ziphandle.read(href)
              mime, encoding = mimetypes.guess_type(href)
              loc = self.context.get_DILocation(self.difile, page, row, col)
              if mime is None:
                msg = "Unknown media type for media \"" + href + "\""
                MessageHandler.critical_warning(msg, self.filepath)
                textstr = StringLiteral.get(href, self.context)
                msgstr = StringLiteral.get(msg, self.context)
                return IMErrorElementOp.create(name = '', loc = loc, content = textstr, error_code='docx-bad-media-ref', error_msg = msgstr)
              fullpath = self.get_full_path_from_epath(href)
              if fmt := ImageAssetData.get_format_from_mime_type(mime):
                value = self.context.create_image_asset_data_embedded(fullpath, data, fmt)
              elif fmt := AudioAssetData.get_format_from_mime_type(mime):
                value = self.context.create_audio_asset_data_embedded(fullpath, data, fmt)
              else:
                textstr = StringLiteral.get(href, self.context)
                msgstr = StringLiteral.get(mime, self.context)
                return IMErrorElementOp.create(name = '', loc = loc, content = textstr, error_code='docx-bad-media-ref', error_msg = msgstr)
              if value is None:
                msg = "Cannot resolve reference to media \"" + href + "\" (please check file presence or security violation)"
                MessageHandler.critical_warning(msg, self.filepath)
                textstr = StringLiteral.get(href, self.context)
                msgstr = StringLiteral.get(msg, self.context)
                return IMErrorElementOp.create(name = '', loc = loc, content = textstr, error_code='docx-bad-media-ref', error_msg = msgstr)

              assert isinstance(value, AssetData)
              return value
    # 到这的话说明引用的内容暂不支持，直接跳过
    return None
