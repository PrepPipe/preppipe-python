# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import io, sys, os
import typing
from warnings import warn
import PIL.Image
import dataclasses
import re

import odf.opendocument
import zipfile
import urllib

from ..inputmodel import *
import argparse
from ..pipeline import TransformBase, FrontendDecl, IODecl

@dataclasses.dataclass
class _TextStyleInfo:
  # 用来存储文本样式的结构
  # 源文档中文本样式既包含“文本样式”又包含“段落样式”，所以这里我们也都存储
  # 生成 IMElementOp 时会只取文本样式的内容，段落样式则会影响内容的组织方式
  # 注意，有些地方的文本的段落样式包含在段落中而不是文本自身，比如段落
  # <p style="P1"><span style="T1">ABC</span></p>
  # 可能 P1 的段落样式使得该段需要特殊处理而 T1 不包含段落样式
  # 这些情况都需要特判
  style : dict[TextAttribute, typing.Any] = dataclasses.field(default_factory=dict)
  is_strike_through : bool = False # if the font has strikethrough (and we will drop it after generation)
  is_special_block_style : bool = False # if the text style satisfy requirement for special block
  special_block_reason : str | None = None
  # 有些编辑器导出的 odf 文档会把列表“压平”，列表项内没有层级，只用文字属性来标明列表项的缩进
  # 我们需要在文字属性这里记录其缩进距离，这样之后可以将列表项的层级结构还原出来
  base_list_style : str | None = None # 只有文本属性包含 "style:list-style-name" 时，我们才考虑它是否是列表项中的文本
  paragraph_margin_left : str | None = None # e.g., <style:paragraph-properties ... fo:margin-left="0.635cm" ></style:paragraph-properties>

  @staticmethod
  def forkfrom(src):
    assert isinstance(src, _TextStyleInfo)
    return dataclasses.replace(src, style=src.style.copy())

  def set_bold(self, bold : bool):
    if bold:
      self.style[TextAttribute.Bold] = True
    else:
      self.style.pop(TextAttribute.Bold, None)

  def set_italic(self, italic : bool):
    if italic:
      self.style[TextAttribute.Italic] = True
    else:
      self.style.pop(TextAttribute.Italic, None)

  def set_color(self, color: Color):
    # 前景色默认为黑色
    if color.red() == 0 and color.green() == 0 and color.blue() == 0 and color.alpha() == 255:
      if TextAttribute.TextColor in self.style:
        del self.style[TextAttribute.TextColor]
      return
    self.style[TextAttribute.TextColor] = color

  def set_background_color(self, color: Color):
    # 背景色默认为白色
    # 将背景色设为白色或透明都被认为是去掉当前背景
    if (color.red(), color.green(), color.blue()) == (255, 255, 255) or color.alpha() == 0:
      if TextAttribute.BackgroundColor in self.style:
        del self.style[TextAttribute.BackgroundColor]
      return
    self.style[TextAttribute.BackgroundColor] = color

  def set_strike_through(self, v : bool):
    self.is_strike_through = v

  def set_is_pecial_block(self, v : bool, reason : str | None = None):
    if v:
      self.is_special_block_style = True
      self.special_block_reason = reason
    else:
      if self.special_block_reason is not None and self.special_block_reason == reason:
        self.is_special_block_style = False
        self.special_block_reason = None

  def set_in_list_style(self, list_style : str):
    self.base_list_style = list_style

  def set_margin_left(self, margin_left : str):
    self.paragraph_margin_left = margin_left

  def empty(self) -> bool:
    return len(self.style) == 0 and not self.is_strike_through and not self.is_special_block_style

class _ListStyleInfo:
  is_numbered : bool # true if the list use numbers instead of bullet points
  start_value : int # usually 1

  def __init__(self, src = None) -> None:
    self.is_numbered = False
    self.start_value = 1
    if src is not None:
      assert isinstance(src, _ListStyleInfo)
      self.is_numbered = src.is_numbered
      self.start_value = src.start_value

  def set_numbered(self, v : bool):
    self.is_numbered = v

  def set_start_value(self, v : int):
    self.start_value = v

class _ODParseContext:
  # how many characters in a paragraph makes the paragraph considered long enough (for debugging purpose)
  _NUM_CHARS_LONG_PARAGRAPH : typing.ClassVar[int] = 10

  # the list of anchor types we support for frames
  # we do not support anchoring from page; it would be too difficult to determine
  _FRAME_EXPECTED_ANCHORTYPES : typing.List[str] = ["as-char", "char", "paragraph"]

  ctx : Context
  filePath : str
  odfhandle: odf.opendocument.OpenDocument
  ziphandle : zipfile.ZipFile
  difile : DIFile
  documentname : str

  style_data : typing.Dict[str, _TextStyleInfo]
  list_style_data : typing.Dict[str, _ListStyleInfo]
  asset_reference_dict : typing.Dict[str, AssetData | typing.Tuple[StringLiteral, StringLiteral]] # cache asset request results; either the asset or the error tuple
  cur_page_count : int
  cur_row_count : int
  cur_column_count : int

  # ------------------------------------------------------------------
  # ODF states
  # it is generally hard to locate a point in the source document
  # we use the text from the "last" paragraph to help user to locate a point
  # whenever we see a paragraph with > _NUM_CHARS_LONG_PARAGRAPH characters, we consider it as a long paragraph
  # ... just use the traditiona <line, col> for now
  #num_total_paragraph : int # the absolute paragraph count
  #last_paragraph_text : str # the content of the "last long paragraph"
  #num_paragraph_past_last_text : int # how many paragraphs has passed from the last long paragraph; should be starting from 1

  # ------------------------------------------------------------------

  def __init__(self, ctx : Context, filePath : str) -> None:
    filePath = os.path.realpath(filePath, strict=True)
    self.ctx = ctx
    self.filePath = filePath
    self.ctx.get_file_auditor().add_permissible_path(os.path.dirname(filePath))
    self.odfhandle = odf.opendocument.load(filePath)
    self.ziphandle = zipfile.ZipFile(filePath, mode = "r")
    self.difile = ctx.get_DIFile(filePath)

    self.style_data = {}
    self.list_style_data = {}
    self.asset_reference_dict = {}
    self.documentname = os.path.splitext(os.path.basename(filePath))[0]

    self.cur_page_count = 1
    self.cur_row_count = 1
    self.cur_column_count = 1

    #self.num_total_paragraph = 0
    #self.last_paragraph_text = ""
    #self.num_paragraph_past_last_text = 0

  def cleanup(self):
    self.ziphandle.close()

  @staticmethod
  def _get_element_attribute(node: odf.element.Element, attr: str) -> str:
    for k in node.attributes.keys():
      if (k[1] == attr):
        return node.attributes[k]
    return ""

  def _populate_style_data(self, node: odf.element.Element):
    for child in node.childNodes:
      if child.qname[1] == "style":
        # we found a text style entry
        name = self._get_element_attribute(child, "name")
        # should not happen, but just in case
        if len(name) == 0:
          continue
        # if we have a parent-style-name, we need to modify from the parent style
        parent_style = self._get_element_attribute(child, "parent-style-name")
        if len(parent_style) > 0:
          current_style = _TextStyleInfo.forkfrom(self.style_data[parent_style])
        else:
          current_style = _TextStyleInfo()
        # check if is in some list
        parent_list_style = self._get_element_attribute(child, 'list-style-name')
        if len(parent_list_style) > 0:
          current_style.set_in_list_style(parent_list_style)
        # we should have child nodes of type text-properties
        # we don't care about paragraph-properties for now
        for property_node in child.childNodes:
          if property_node.qname[1] == "text-properties":
            for k in property_node.attributes.keys():
              if k[1] == "font-weight" and property_node.attributes[k] in ["bold"]:
                current_style.set_bold(True)
              elif k[1] == "font-style" and property_node.attributes[k] in ["italic"]:
                current_style.set_italic(True)
              elif k[1] == "color":
                current_style.set_color(Color.get(property_node.attributes[k]))
              elif k[1] == "background-color":
                current_style.set_background_color(Color.get(property_node.attributes[k]))
              elif k[1] == "text-line-through-style":
                current_style.set_strike_through(property_node.attributes[k] != 'none')
                # add other attrs here if needed
          elif property_node.qname[1] == "paragraph-properties":
            for k in property_node.attributes.keys():
              match k[1]:
                case "background-color":
                  bgcolor = Color.get(property_node.attributes[k])
                  is_special_block = bgcolor.alpha() > 0 and (bgcolor.red(), bgcolor.green(), bgcolor.blue()) != (255, 255, 255)
                  current_style.set_is_pecial_block(is_special_block, IMSpecialBlockOp.ATTR_REASON_BG_HIGHLIGHT)
                case "text-align":
                  current_style.set_is_pecial_block(property_node.attributes[k] == 'center', IMSpecialBlockOp.ATTR_REASON_CENTERED)
                case "margin-left":
                  current_style.set_margin_left(property_node.attributes[k])
                case _:
                  pass

        self.style_data[name] = current_style
      elif child.qname[1] == "list-style":
        # we found a list style entry
        name = self._get_element_attribute(child, "name")
        # should not happen, but just in case
        if len(name) == 0:
          continue
        is_numbered = False
        start_value = 1
        first_child = child.childNodes[0]
        if first_child.qname[1] == 'list-level-style-bullet':
          is_numbered = False
        elif first_child.qname[1] == 'list-level-style-number':
          is_numbered = True
          start_value_attr = self._get_element_attribute(first_child, "start-value")
          if len(start_value_attr) > 0:
            start_value = int(start_value_attr)
        else:
          raise RuntimeError('Unexpected child ' + first_child.qname[1] + ' in list-style node')
        current_style = _ListStyleInfo()
        if is_numbered:
          current_style.set_numbered(True)
          current_style.set_start_value(start_value)
        else:
          current_style.set_numbered(False)
        self.list_style_data[name] = current_style
      else:
        # not a style node; just recurse
        if (len(child.childNodes) > 0):
          self._populate_style_data(child)

  @staticmethod
  def get_style(node) -> str:
    """Extract the style-name attribute from the element node"""
    return _ODParseContext._get_element_attribute(node, "style-name")

  def get_DILocation(self, page : int, row : int, column : int) -> DILocation:
    return self.ctx.get_DILocation(self.difile, page, row, column)

  def create_text_element(self, text:str, style_name:str, paragraph_style_src : str, loc : DILocation) -> IMElementOp | IMSpecialBlockOp | typing.Tuple[IMElementOp, IMErrorElementOp]:
    """Create the text element with the provided text and style name.
    The flags for the text element will be set from the style name
    """
    # 如果文本被划掉（有strikethrough），则我们在此添加一个StrikeThrough的属性，这个 IMElementOp 会在之后的 transform_pass_fix_text_elements() 中消耗掉
    content = StringLiteral.get(text, self.ctx)
    error_op = None
    cstyle = None
    is_strike_through = False
    special_block_reason : str | None = None
    left_margin_in_list : str | None = None
    if style_name in self.style_data:
      style = self.style_data[style_name]
      if style.is_strike_through:
        is_strike_through = True
      if style.is_special_block_style:
        special_block_reason = style.special_block_reason
      if style.base_list_style is not None:
        left_margin_in_list = style.paragraph_margin_left
      # 如果当前设置没有段落设置的话，尝试从段落样式中读取
      if paragraph_style_src in self.style_data:
        paragraph_style = self.style_data[paragraph_style_src]
        if special_block_reason is None and paragraph_style.is_special_block_style:
          special_block_reason = paragraph_style.special_block_reason
        if left_margin_in_list is None and paragraph_style.base_list_style is not None:
          left_margin_in_list = paragraph_style.paragraph_margin_left
      # 开始实际创建样式
      if not style.empty() and special_block_reason is None:
        cstyle = TextStyleLiteral.get(style.style, self.ctx)
    else:
      error_op = IMErrorElementOp.create(name = '', loc = loc, content = content, error_code='odf-bad-style-name', error_msg = StringLiteral.get('Cannot find style name \"' + style_name + '"', self.ctx))
    if cstyle is not None:
      content = TextFragmentLiteral.get(self.ctx, content, cstyle)
    if special_block_reason is not None:
      node = IMSpecialBlockOp.create(name = '', reason=special_block_reason, loc = loc, content = content)
    else:
      node = IMElementOp.create(name = '', loc = loc, content = content)
      # 如果这个内容结点在列表中，我们在这记录一下左边距来辅助重构列表层级
      if left_margin_in_list is not None and len(left_margin_in_list) > 0:
        node.set_attr("LeftMarginInList", left_margin_in_list)
    if is_strike_through:
      node.set_attr('StrikeThrough', True)
    if error_op is None:
      return node
    return (node, error_op)

    #if style_name in self.style_data:
    #  style = self.style_data[style_name]
    #  node = IMTextElement(text, style)
    #  return node

    # style_name not found
    # add to notification
    #if style_name not in self.missing_style_list:
    #  self.missing_style_list.append(style_name)
    # just create a text without format
    #node = IMTextElement(text)
    #return node

  def get_full_path_from_href(self, href : str) -> str:
    return os.path.normpath(os.path.join(self.filePath, urllib.parse.unquote(href)))

  def create_image_reference(self, href : str, loc : DILocation) -> IMElementOp:
    if href in self.asset_reference_dict:
      value = self.asset_reference_dict[href]
      if isinstance(value, AssetData):
        return IMElementOp.create(name = '', loc = loc, content = value)
      else:
        content = value[0]
        err = value[1]
        return IMErrorElementOp.create(name = '', loc = loc, content = content, error_code='odf-bad-image-ref', error_msg = err)

    value = None
    href_full_path = self.get_full_path_from_href(href)
    if href in self.odfhandle.Pictures:
      (FilenameOrImage, data, mediatype) = self.odfhandle.Pictures[href]
      fmt = ImageAssetData.get_format_from_mime_type(mediatype)
      if fmt is None:
        # 图片类型不支持
        # 输出一个错误
        textstr = StringLiteral.get(href, self.ctx)
        msgstr = StringLiteral.get(mediatype, self.ctx)
        self.asset_reference_dict[href] = (textstr, msgstr)
        return IMErrorElementOp.create(name = '', loc = loc, content = textstr, error_code='odf-unrecognized-image-mime', error_msg = msgstr)

      if FilenameOrImage == odf.opendocument.IS_FILENAME:
        # not sure when will this happen...
        raise NotImplementedError('odf.opendocument.IS_FILENAME for image reference not supported yet')
        #imagePath = os.path.join(self.basedir, self.documentname, data)
        #entry = self.parent.get_image_asset_entry_from_path(imagePath, mediatype)
      elif FilenameOrImage == odf.opendocument.IS_IMAGE:
        # the image is embedded in the file
        value = self.ctx.create_image_asset_data_embedded(href_full_path, data, fmt)
        # entry = self.parent.get_image_asset_entry_from_inlinedata(data, mediatype, self.filePath, href)
    else:
      # the image is a link to outside file
      if self.ctx.get_file_auditor().check_is_path_accessible(href_full_path):
        value = self.ctx.get_or_create_image_asset_data_external(href_full_path)

    if not isinstance(value, ImageAssetData):
      msg = "Cannot resolve reference to image \"" + href + "\" (please check file presence or security violation)"
      MessageHandler.critical_warning(msg, self.filePath)
      textstr = StringLiteral.get(href, self.ctx)
      msgstr = StringLiteral.get(msg, self.ctx)
      self.asset_reference_dict[href] = (textstr, msgstr)
      return IMErrorElementOp.create(name = '', loc = loc, content = textstr, error_code='odf-bad-image-ref', error_msg = msgstr)

    self.asset_reference_dict[href] = value
    return IMElementOp.create(name = '', loc = loc, content = value)

  def create_media_reference(self, href : str, loc : Location) -> IMElementOp:
    if href in self.asset_reference_dict:
      value = self.asset_reference_dict[href]
      if isinstance(value, AssetData):
        return IMElementOp.create(name = '', loc = loc, content = value)
      else:
        content = value[0]
        err = value[1]
        return IMErrorElementOp.create(name = '', loc = loc, content = content, error_code='odf-bad-media-ref', error_msg = err)
    value = None
    href_full_path = self.get_full_path_from_href(href)
    if href in self.ziphandle.namelist():
      assert href.startswith('Media/')
      data = self.ziphandle.read(href)

      mime, encoding = mimetypes.guess_type(href)
      if mime is None:
        msg = "Unknown media type for media \"" + href + "\""
        MessageHandler.critical_warning(msg, self.filePath)
        textstr = StringLiteral.get(href, self.ctx)
        msgstr = StringLiteral.get(msg, self.ctx)
        self.asset_reference_dict[href] = (textstr, msgstr)
        return IMErrorElementOp.create(name = '', loc = loc, content = textstr, error_code='odf-bad-media-ref', error_msg = msgstr)
      if fmt := ImageAssetData.get_format_from_mime_type(mime):
        value = self.ctx.create_image_asset_data_embedded(href_full_path, data, fmt)
      elif fmt := AudioAssetData.get_format_from_mime_type(mime):
        value = self.ctx.create_audio_asset_data_embedded(href_full_path, data, fmt)
      else:
        textstr = StringLiteral.get(href, self.ctx)
        msgstr = StringLiteral.get(mime, self.ctx)
        self.asset_reference_dict[href] = (textstr, msgstr)
        return IMErrorElementOp.create(name = '', loc = loc, content = textstr, error_code='odf-bad-media-ref', error_msg = msgstr)
    else:
      # the href is a link to outside file
      if self.ctx.get_file_auditor().check_is_path_accessible(href_full_path):
        value = self.ctx.get_or_create_unknown_asset_data_external(href_full_path)

    if value is None:
      msg = "Cannot resolve reference to media \"" + href + "\" (please check file presence or security violation)"
      MessageHandler.critical_warning(msg, self.filePath)
      textstr = StringLiteral.get(href, self.ctx)
      msgstr = StringLiteral.get(msg, self.ctx)
      self.asset_reference_dict[href] = (textstr, msgstr)
      return IMErrorElementOp.create(name = '', loc = loc, content = textstr, error_code='odf-bad-media-ref', error_msg = msgstr)

    assert isinstance(value, AssetData)
    self.asset_reference_dict[href] = value
    return IMElementOp.create(name = '', loc = loc, content = value)


  def _get_unsupported_element_op(self, element : odf.element.Element) -> IMErrorElementOp:
    loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
    elementname = str(element.qname)
    return IMErrorElementOp.create(name = elementname, loc = loc, content = StringLiteral.get(str(element), self.ctx), error_code='unsupported-element', error_msg=StringLiteral.get(elementname, self.ctx))

  def _populate_paragraph_impl(self, paragraph: Block, rootnode : odf.element.Element, default_style: str, paragraph_style_src : str, isInFrame : bool) -> None:
    # default_style 是没有额外样式标注时的内容样式
    # 纯文本内容的话，有时段落样式只在段落开始时指定，内容都用 span 包裹且该样式只有文本样式没有段落样式，所以需要一个额外的 paragraph_style_src
    for element in rootnode.childNodes:
      loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
      if element.nodeType == 3:
        # this is a text node
        text = str(element)
        if len(text) > 0:
          element_node_or_pair = self.create_text_element(text, default_style, paragraph_style_src, loc)
          if isinstance(element_node_or_pair, tuple):
            # an IMElementOp and an IMErrorElementOp
            for e in element_node_or_pair:
              paragraph.push_back(e)
          else:
            assert isinstance(element_node_or_pair, (IMElementOp, IMSpecialBlockOp))
            paragraph.push_back(element_node_or_pair)
          self.cur_column_count += len(text)
      elif element.nodeType == 1:
        if element.qname[1] == "span":
          # this is a node with attribute
          style = self.get_style(element)
          if (style == ""):
            style = default_style
          self._populate_paragraph_impl(paragraph, element, style, paragraph_style_src, isInFrame)
        elif element.qname[1] == "frame":
          if len(element.childNodes) == 0:
            continue

          # inside a frame, we usually only have one single child
          # however, we may have substitutes that appear after the first child
          # (e.g., if we have a chart in the doc, we will have (1) the chart object and (2) a replacement image)
          # the qname is not always good enough for debugging (e.g., the chart is just an "object"), but is better than nothing
          firstChild = element.childNodes[0]
          first_child_name = firstChild.qname[1]

          if len(element.childNodes) > 1:
            remaining_qnames = []
            for i in range(1, len(element.childNodes)):
              remaining_qnames.append(element.childNodes[i].qname[1])
            info_str = "Frame (" + first_child_name +") has more than one child ("+ str(remaining_qnames)+"); only the first is read."
            MessageHandler.info(info_str, self.filePath, str(loc))

          # check whether the frame has the expected anchoring
          anchor = self._get_element_attribute(element, "anchor-type")
          if anchor not in self._FRAME_EXPECTED_ANCHORTYPES:
            warn_str = "Frame (" + first_child_name + ") with unexpected anchor type " + anchor + "found. Please inspect the output on possible mispositions of frame data. (Expecting: "+ str(self._FRAME_EXPECTED_ANCHORTYPES) + ")"
            MessageHandler.warning(warn_str, self.filePath, str(loc))


          if firstChild.nodeType == 1 and first_child_name == "image":
            href = self._get_element_attribute(firstChild, "href")
            loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
            image_element = self.create_image_reference(href, loc)
            paragraph.push_back(image_element)

          elif firstChild.nodeType == 1 and first_child_name == "plugin" and self._get_element_attribute(firstChild, 'mime-type') == 'application/vnd.sun.star.media':
            # audio / video
            href = self._get_element_attribute(firstChild, "href")
            loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
            media_element = self.create_media_reference(href, loc)
            paragraph.push_back(media_element)

          elif firstChild.nodeType == 1 and first_child_name == "text-box":
            # we do not support nested textbox. If we are already in frame, we skip this text box
            loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
            if isInFrame:
              warn_str = "Frame (" + first_child_name +") is inside a framed environment, and is therefore ignored"
              MessageHandler.warning(warn_str, self.filePath, str(loc))
              paragraph.push_back(IMErrorElementOp.create(name='', loc=loc, content= StringLiteral.get("text-box", self.ctx), error_code='odf-nested-frame', error_msg= StringLiteral.get(warn_str, self.ctx)))
            else:
              # let's deal with this text box
              # the default text style for textbox text is specified on the frame, instead of the text-box element
              style = self._get_element_attribute(element, "text-style-name")
              if (style == ""):
                style = default_style
              frame = IMFrameOp.create('', loc)
              self.odf_parse_frame(frame.body, firstChild, True, style)
              paragraph.push_back(frame)
          else:
            paragraph.push_back(self._get_unsupported_element_op(element))
            # print("Warning: unhandled node type in frame: " + str(element.qname) + ": " + str(element))
          # end of elements in frame
        elif element.qname[1] == "soft-page-break":
          # entering a new page
          self.odf_encountering_pagebreak()
        elif element.qname[1] in ("bookmark", "s"):
          # ignore
          pass
        else:
          paragraph.push_back(self._get_unsupported_element_op(element))
          # MessageHandler.warning("Warning: unhandled node type in frame: " + str(element.qname) + ": " + str(element), self.filePath, str(loc))
      else:
        MessageHandler.warning("Warning: unhandled node type " + str(element.qname) + ": " + str(element), self.filePath, str(loc))
    # done!

  def odf_parse_paragraph(self, rootnode : odf.element.Element, isInFrame : bool, default_style: str = "") -> Block:
    paragraph = Block.create('', self.ctx)
    default_style_read = self.get_style(rootnode)
    if len(default_style_read) > 0:
      default_style = default_style_read
    self._populate_paragraph_impl(paragraph, rootnode, default_style, default_style, isInFrame)
    # exiting the current paragraph; reset column
    self.cur_row_count += 1
    self.cur_column_count = 1
    return paragraph

  def odf_encountering_pagebreak(self):
    self.cur_page_count += 1
    self.cur_row_count = 1
    self.cur_column_count = 1

  def odf_parse_tablecell(self, rootnode : odf.element.Element, errlist : list[Operation], default_style: str = "") -> list[Value]:
    result : list[Value] = []
    tmpregion = Region()
    self.odf_parse_frame(tmpregion, rootnode, isInFrame=True, default_style=default_style)
    # 然后拆开这个区，看看里面有什么
    pending_text : str = ''
    pending_text_style : TextStyleLiteral | None = None
    pending_mds : list[Operation] = []
    def commit_cur_text():
      nonlocal result
      nonlocal pending_text
      nonlocal pending_text_style
      if len(pending_text) == 0:
        return
      if pending_text_style is None:
        v = StringLiteral.get(pending_text, self.ctx)
      else:
        v = TextFragmentLiteral.get(self.ctx, StringLiteral.get(pending_text, self.ctx), pending_text_style)
      result.append(v)
      pending_text = ''
      pending_text_style = None

    def put_value(v : Value):
      nonlocal result
      nonlocal pending_text
      nonlocal pending_text_style
      if isinstance(v, StringLiteral):
        if len(pending_text) == 0:
          pending_text = v.get_string()
          pending_text_style = None
        elif pending_text_style is None:
          pending_text += v.get_string()
        else:
          commit_cur_text()
          pending_text = v.get_string()
          pending_text_style = None
      elif isinstance(v, TextFragmentLiteral):
        if len(pending_text) == 0:
          pending_text = v.get_string()
          pending_text_style = v.style
        elif pending_text_style is v.style:
          pending_text += v.get_string()
        else:
          commit_cur_text()
          pending_text = v.get_string()
          pending_text_style = v.style
      else:
        commit_cur_text()
        result.append(v)
    for b in tmpregion.blocks:
      for op in b.body:
        if isinstance(op, MetadataOp):
          pending_mds.append(op)
          continue
        if isinstance(op, IMElementOp):
          for u in op.content.operanduses():
            put_value(u.value)
          continue
        MessageHandler.warning("Content nested in table cell ignored: " + str(op), self.filePath)
    commit_cur_text()
    for op in pending_mds:
      op.remove_from_parent()
      errlist.append(op)
    tmpregion.drop_all_references()
    return result

  def odf_parse_frame(self, result : Region, rootnode : odf.element.Element, isInFrame : bool, default_style : str = ""):
    # isInFrame is false if this part is inside the flow of the document,
    # and is true if this is outside the document flow.
    # if it is inside the flow:
    #  - The "last long paragraph" should be updated during parsing
    #  - if a frame is encountered, we create a new frame
    # if it is outside the flow:
    #  - The "last long paragraph" should not be updated during parsing
    #  - we maintain a local "last long paragraph" for better locating
    #  - if a frame is encountered, we inline the frame content without creating IMFrameDefinitionElement
    # We only consider text boxes or other multi-paragraph contents as frames
    # We don't consider images, etc as frame even if they have a frame in the source doc
    for node in rootnode.childNodes:
      nodetype = node.qname[1]
      match nodetype:
        case "sequence-decls":
          # skip sequence-decls
          # do nothing
          pass
        case "section":
          new_default_style = default_style
          default_style_read = self.get_style(node)
          if len(default_style_read) > 0:
            new_default_style = default_style_read
          self.odf_parse_frame(result, node, isInFrame, new_default_style)
        case "p":
          # paragraph
          paragraph = self.odf_parse_paragraph(node, isInFrame, default_style)
          result.push_back(paragraph)
        case 'list':
          # list is in parallel with paragraph in odf
          listname = self._get_element_attribute(node, 'id')
          listop = IMListOp.create(listname, self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count))
          start_base = 1
          list_style = self._get_element_attribute(node, 'style-name')
          list_error_op = None
          if list_style in self.list_style_data:
            list_style_entry = self.list_style_data[list_style]
            listop.is_numbered = list_style_entry.is_numbered
            if list_style_entry.is_numbered and list_style_entry.start_value != 1:
              listop.set_attr('StartValue', list_style_entry.start_value)
              start_base = list_style_entry.start_value
          else:
            is_emit_error = True
            if len(list_style) == 0:
              # this usually happens in a nested list
              # we need to get the style info from the parent list op
              parent_op = result.parent
              while parent_op is not None and not isinstance(parent_op, IMListOp):
                parent_op = parent_op.parent_op
              if isinstance(parent_op, IMListOp):
                is_emit_error = False
                if parent_op.is_numbered:
                  listop.is_numbered = True
                  if parent_op.has_attr('StartValue'):
                    startvalue = parent_op.get_attr('StartValue')
                    assert isinstance(startvalue, int)
                    listop.set_attr('StartValue', startvalue)
                else:
                  listop.is_numbered = False
            if is_emit_error:
              list_error_op = IMErrorElementOp.create(name='', loc=listop.location, content = StringLiteral.get(list_style, self.ctx), error_code='odf-bad-list-style', error_msg = StringLiteral.get('Cannot get list style', self.ctx))
          for listnode in node.childNodes:
            listnodetype = listnode.qname[1]
            match listnodetype:
              case 'list-header':
                # should appear before all the list item
                # treat it as a new paragraph
                # (this part is not tested; I don't even know how to create a list-header..)
                paragraph = self.odf_parse_paragraph(node, isInFrame, default_style)
                result.push_back(paragraph)
              case 'list-item':
                self.odf_parse_frame(listop.add_list_item(start_base), listnode, False, default_style)
          container_paragraph = Block.create('', self.ctx)
          container_paragraph.body.push_back(listop)
          if list_error_op is not None:
            container_paragraph.body.push_back(list_error_op)
          result.push_back(container_paragraph)
        case "table":
          rowlist : list[list[list[Value]]] = [] # [row][col] -> [list of value]
          covered_table_cells : dict[tuple[int,int], tuple[int,int]] = {} # covered <row, col> --> src <row, col>
          tablename = self._get_element_attribute(node, 'name')
          errlist : list[Operation] = []
          rowindex = -1
          colcount = 0
          # 一定要在处理内容前保存当前位置
          tableloc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
          for childnode in node.childNodes:
            childnodetype = childnode.qname[1]
            match childnodetype:
              case 'table-column':
                pass
              case "soft-page-break":
                self.odf_encountering_pagebreak()
              case 'table-row':
                cur_row_list : list[list[Value]] = []
                rowindex += 1
                colindex = -1
                for cell in childnode.childNodes:
                  colindex += 1
                  match cell.qname[1]:
                    case 'table-cell':
                      colspan = 1
                      rowspan = 1
                      colspanstr = self._get_element_attribute(cell, 'number-columns-spanned')
                      if len(colspanstr) > 0:
                        colspan = int(colspanstr)
                      rowspanstr = self._get_element_attribute(cell, 'number-rows-spanned')
                      if len(rowspanstr) > 0:
                        rowspan = int(rowspanstr)
                      if colspan > 1 or rowspan > 1:
                        for col in range(colindex, colindex + colspan):
                          for row in range(rowindex, rowindex + rowspan):
                            if col == colindex and row == rowindex:
                              continue
                            covered_table_cells[(row, col)] = (rowindex, colindex)
                      cur_row_list.append(self.odf_parse_tablecell(cell, errlist))
                    case 'covered-table-cell':
                      cur_row_list.append([])
                    case _:
                      raise RuntimeError("should not happen")
                if len(cur_row_list) > colcount:
                  assert colcount == 0
                  colcount = len(cur_row_list)
                rowlist.append(cur_row_list)
          tableop = IMTableOp.create(rowcount = len(rowlist), columncount=colcount, name=tablename, loc=tableloc)
          for row in range(0, len(rowlist)):
            for col in range(0, colcount):
              if (row, col) in covered_table_cells:
                rrow, rcol = covered_table_cells[(row, col)]
                vlist = rowlist[rrow][rcol]
              else:
                vlist = rowlist[row][col]
              celloperand = tableop.get_cell_operand(row, col)
              for v in vlist:
                celloperand.add_operand(v)
          container_paragraph = Block.create('', self.ctx)
          container_paragraph.body.push_back(tableop)
          for md in errlist:
            container_paragraph.body.push_back(md)
          result.push_back(container_paragraph)
        case _:
          # node type not recognized
          loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
          MessageHandler.warning("Element unrecognized and ignored: " + nodetype, self.filePath, str(loc))

  def transform_pass_fix_text_elements(self, doc : IMDocumentOp):
    # 把所有文本的字体转换为符合IR的形式：
    # （误）1. 将 ODF 的 styles 转换为IR的格式，确定所有字体大小
    # （误）2. 将对 ConstantString 的引用转换为 ConstantText
    # 3. 合并相邻的、文本格式相同的纯文本单元
    # 原本打算统计各个字体的最大众的大小，然后以此为基准大小来计算其他字符的标准大小，但是这样有如下问题无法解决：
    # 1. 对"每个字体"的定义可能不尽相同，以什么为边界来确定字体大小很难决定。
    #    如果有人在文本内包含引用等，并使用与本文相同的字体，我们很可能希望即使它们实际大小不一，导出时大小也一致
    #    （此时理想的边界是引用的范围，但是一般而言引用只会有缩进等“提示”，这些提示同样会被用到非引用的内容中）
    # 2. 字体的大小成为了非局部的属性，容易产生意外结果
    # 因此，即使IR支持字体大小，我们也在此将丢弃所有大小信息，只将不会引起误判的内容（颜色，加粗，斜体等）加进去
    # 更新：放弃使用字体大小后，我们现在在生成阶段就直接在 IMElementOp 中生成符合要求的内容，因此在此处我们目前只合并相邻的、样式相同的文本

    def walk_region(region : Region) -> bool:
      # 如果该区内所有的内容都被去除，则返回 True,否则返回 False
      blocks_to_delete = []
      for b in region.blocks:
        # 我们首先把所有划掉的 IMElementOp 删掉
        strikethrough_elements : list[IMElementOp] = []
        for op in b.body:
          if isinstance(op, IMElementOp):
            if op.has_attr('StrikeThrough'):
              strikethrough_elements.append(op)
        if len(strikethrough_elements) > 0:
          for op in strikethrough_elements:
            op.erase_from_parent()
          # 如果这个块空了，直接跳过
          if b.body.empty:
            blocks_to_delete.append(b)
            continue
        # 然后开始常规的合并
        first_text_op : IMElementOp = None
        last_text_op : IMElementOp = None
        # 尝试合并从 first_text_op 到 last_text_op 间的所有文本内容
        # 相同字体的内容合并为同一个 ConstantTextFragment
        # 不同字体的内容合并为一个 ConstantText，内容为多个 ConstantTextFragment
        def coalesce():
          nonlocal first_text_op
          nonlocal last_text_op
          # skip degenerate cases
          if first_text_op is None or last_text_op is None or first_text_op is last_text_op:
            first_text_op = None
            last_text_op = None
            return
          cur_text = ''
          cur_style = None
          fragment_list = []
          end_op = last_text_op.get_next_node()
          cur_op = first_text_op
          merged_attribute_dict = {}
          while cur_op is not end_op:
            assert type(cur_op) == IMElementOp
            # 加上这条检查，这样万一以后在首次生成 IMElementOp 时沾上属性后，我们可以在这里添加对属性的合并
            if len(cur_op.attributes) > 0:
              for k, v in cur_op.attributes.items():
                match k:
                  case "LeftMarginInList":
                    if k not in merged_attribute_dict:
                      merged_attribute_dict[k] = v
                  case _:
                    raise RuntimeError("Unexpected IMElementOp attribute on merge: " + k)
            for u in cur_op.content.operanduses():
              cur_content = u.value
              if isinstance(cur_content, TextFragmentLiteral):
                cur_new_text = cur_content.get_string()
                cur_new_style = cur_content.style
              else:
                assert isinstance(cur_content, StringLiteral)
                cur_new_text = cur_content.get_string()
                cur_new_style = None

              if cur_style is None and len(cur_text) == 0:
                # this is the first time we visit an element
                cur_text = cur_new_text
                cur_style = cur_new_style
              elif (cur_style is None and cur_new_style is None) or (cur_style == cur_new_style):
                # this is the first time we visit an element
                cur_text += cur_new_text
              else:
                # we get an fragment with a different style
                newfrag = StringLiteral.get(cur_text, self.ctx)
                if cur_style is not None:
                  newfrag = TextFragmentLiteral.get(self.ctx, newfrag, cur_style)
                fragment_list.append(newfrag)
                cur_text = cur_new_text
                cur_style = cur_new_style
            # finished handling current op
            cur_op = cur_op.get_next_node()
          # finished the first iteration
          # end the last fragment
          if len(cur_text) > 0:
            newfrag = StringLiteral.get(cur_text, self.ctx)
            if cur_style is not None:
              newfrag = TextFragmentLiteral.get(self.ctx, newfrag, cur_style)
            # create the new element
            new_content = None
            if len(fragment_list) == 0:
              new_content = newfrag
            else:
              fragment_list.append(newfrag)
              new_content = fragment_list
            newop  = IMElementOp.create(content = new_content, name = first_text_op.name, loc = first_text_op.location)
            # now replace the current ops
            newop.insert_before(first_text_op)
            for k, v in merged_attribute_dict.items():
              newop.set_attr(k, v)
          cur_op = first_text_op
          while cur_op is not end_op:
            cur_op = cur_op.erase_from_parent()
          # done for this helper

        op_to_delete = []
        for op in b.body:
          if op.get_num_regions() > 0:
            assert not isinstance(op, IMElementOp)
            coalesce()
            emptied_regions : typing.List[Region] = []
            for r in op.regions:
              ret = walk_region(r)
              if ret:
                emptied_regions.append(r)
            if len(emptied_regions) > 0:
              # 查看我们是否允许在该操作符内删掉区，甚至删除整个操作符
              delete_op_if_empty = False
              if isinstance(op, IMListOp):
                # 列表下任意区都可以删
                # 如果所有区都没了，列表也可以删
                delete_op_if_empty = True
              else:
                # 默认什么区都不能删
                # 如果以后有其他操作符可以删区，则在此处更新
                emptied_regions.clear()
              if len(emptied_regions) > 0:
                for r in emptied_regions:
                  r.erase_from_parent()
                if op.get_num_regions() == 0 and delete_op_if_empty:
                  op_to_delete.append(op)
          elif type(op) == IMElementOp:
            content = op.content.get()
            if isinstance(content, (StringLiteral, TextFragmentLiteral)) and not op.has_attr('StrikeThrough'):
              # we do found a fragment
              if first_text_op is None:
                first_text_op = op
                last_text_op = op
              else:
                last_text_op = op
            else:
              # it is some other content (cannot merge)
              coalesce()
          else:
            # this is not an IMElementOp
            coalesce()
        # we walked through all the ops of the body
        coalesce()
        for op in op_to_delete:
          op.erase_from_parent()
        # finished this block
      if len(blocks_to_delete) > 0:
        for b in blocks_to_delete:
          b.erase_from_parent()
        if region.blocks.empty:
          return True
      return False
      # end of the helper function
    walk_region(doc.body)
    # 我们不会删除文档的 body 区，所以此处不检查返回值

  def transform_pass_merge_special_blocks(self, doc : IMDocumentOp):
    # 把相邻的 IMSpecialBlockOp 合并起来，后续内容合入第一个
    #raise NotImplementedError("TODO")
    def walk_region(region : Region) -> bool:
      # 如果该区内所有的内容都被去除，则返回 True,否则返回 False
      blocks_to_delete : list[Block] = []
      special_block_textlist : list[StringLiteral] = []
      leader_block : Block | None = None
      leader_op : IMSpecialBlockOp | None = None
      member_blocks : list[Block] = []
      def commit_blocks():
        nonlocal blocks_to_delete
        nonlocal special_block_textlist
        nonlocal leader_block
        nonlocal leader_op
        nonlocal member_blocks
        if len(member_blocks) > 0:
          if len(special_block_textlist) > 0:
            leader_op.content.drop_all_uses()
            for v in special_block_textlist:
              leader_op.content.add_operand(v)
          for b in member_blocks:
            blocks_to_delete.append(b)
            ops_to_move = []
            for op in b.body:
              if isinstance(op, MetadataOp):
                ops_to_move.append(op)
                continue
              if isinstance(op, IMSpecialBlockOp):
                continue
              raise RuntimeError("Unexpected op kind: " + type(op).__name__)
            for op in ops_to_move:
              op.remove_from_parent()
              leader_block.push_back(op)
        else:
          # 这种情况下我们应该不需要 StringListLiteral
          assert len(special_block_textlist) < 2
        special_block_textlist.clear()
        leader_block = None
        leader_op = None
        member_blocks.clear()

      for b in region.blocks:
        # 一般而言这个块内应该只有一个 IMSpecialBlockOp, 其他只可能有 MetadataOp
        # 不过如果段内有不止一个文本样式的话可能会被拆分成多个 IMSpecialBlockOp
        # 这里我们第一遍进行段内合并，第二遍再做段间合并
        is_other_elements_found = False
        cur_leader_op : IMSpecialBlockOp | None = None
        subsequent_specialblocks = []
        cur_specialblock_text = []
        for op in b.body:
          if isinstance(op, MetadataOp):
            continue
          if isinstance(op, IMSpecialBlockOp):
            for u in op.content.operanduses():
              cur_specialblock_text.append(u.value)
            if cur_leader_op is None:
              cur_leader_op = op
            else:
              subsequent_specialblocks.append(op)
            continue
          is_other_elements_found = True
          break
        # 如有需要，尝试段内合并
        if len(subsequent_specialblocks) > 0:
          cur_leader_op.content.drop_all_uses()
          cumulative_str = ''.join([v.get_string() for v in cur_specialblock_text])
          cumulative_str_l = StringLiteral.get(cumulative_str, self.ctx)
          cur_specialblock_text = [cumulative_str_l]
          cur_leader_op.content.add_operand(cumulative_str_l)
          for op in subsequent_specialblocks:
            op.erase_from_parent()
          subsequent_specialblocks.clear()
        # 开始判断
        if leader_block is None:
          # 现在还没有块可以合并
          if cur_leader_op is not None and not is_other_elements_found:
            # 遇到一个新块
            leader_block = b
            leader_op = cur_leader_op
            special_block_textlist = cur_specialblock_text
          else:
            # 这个块不能合并
            pass
        else:
          # 当前已经有块
          if cur_leader_op is not None and not is_other_elements_found:
            # 可以合并
            special_block_textlist.extend(cur_specialblock_text)
            member_blocks.append(b)
          else:
            # 结束一个块
            commit_blocks()
      if len(member_blocks) > 0:
        commit_blocks()
      for b in blocks_to_delete:
        b.erase_from_parent()
      return False

    walk_region(doc.body)

  def transform_pass_reassociate_lists(self, doc : IMDocumentOp):
    # 对所有的 IMListOp 进行重组，以解决以下问题：
    # 1.  目前当不同种类的列表相互嵌套（比如有数字的和没数字的）时，如果有以下列表：
    #     <L1> * A
    #          * B
    #        <L2> 1. x
    #             2. y
    #        </L2>
    #     </L1>
    #     则实际在文件中会以如下形式表达：
    #     <L1> * A
    #          * B
    #     </L1>
    #     <L2><L'>  1. x
    #               2. y
    #     </L'></L2>
    #     我们需要重组列表来把 L2 放到 L1 的B项下。
    #
    # 2.  当列表内容含有其他内容（比如文字、图片等）时，列表也会被中断，比如如果我们有如下内容：
    #     <L1> * A
    #            关于A的描述
    #          * B
    #     </L1>
    #     则内容很有可能表述为如下形式：
    #     <L1> * A
    #     </L1>
    #     <p> 关于A的描述 </p>
    #     <L2> * B
    #     </L2>
    #     如下情况发生时，我们需要把L2合并到L1中。
    #     由于在“吸收”列表内最后一项的额外内容时有可能将不属于该项的内容包含进来，我们使用如下偏保守的启发式算法：
    #     我们仅在最后一项有内容时吸收新内容，若最后一项没有文字内容则不进行重整
    #     (有这样的空项的话我们也把空项去掉)
    #     项内有内容时，我们吸收“一自然段”的内容（图片等占满整“行”的也视为属于上一段），直到以下情况发生：
    #     (a) 有一个空段落
    #     (b) 内容后开始了一个新列表，该新列表与目前的列表不匹配所以无法合并
    #         （不匹配指该新列表的样式（有无数字，有数字的话也包含数字的值）与其缩进等级对应的现列表的样式不同）
    #     在列表层级高于一层时，我们不使用文本的缩进来确定其属于哪个列表项，固定认为它们属于嵌套最深层的部分。原因如下：
    #     (a) 使用文本编辑器的缩进层级时，除非是嵌套最深层的，否则有时很难让其对准自己想要的列表层级，不稳定
    #     (b) 从文本样式中（我认为）比较难找到对应的列表层级，并且如果文本缩进不对应任何列表层级时的处理比较难选择最好的策略
    #     (c) 暂时没有任何需要使用这种表述形式的场景，如果真的需要大列表嵌套小列表然后再后接内容的话，完全可以把后接的内容也变成列表项
    #     更新：我们现在不再做这一项，如果有“关于A的描述”需要合并，用户可以给它们新建一层列表（即给A加一个列表，每段内容都作为列表项）
    #     有这个转换的话容易把一些意外的内容并入
    def _should_absorb_content(list : IMListOp):
      # 检查一个列表是否应该“吸收”其他内容
      # 一般来说，如果列表每一项都只有一行内容，我们不应该把后面一段的内容并入该列表最后一项中
      # 如果列表最后一项是空的，则我们也不应该将之后的内容并入
      # 只有当列表某一项有其他内容时（这种时候一般每一项都会有点内容），我们才做这种合并
      # （如果目前该列表只有一项且该项不为空，则我们也认为可以吸收内容，不然所有的列表都会无法吸收内容，因为连第一项也没法收。。）

      # 不应该发生这种情况，仅作检查
      if list.get_num_regions() == 0:
        return False
      # 如果最后一项为空，则不合并内容
      last_region = list.get_last_region()
      if last_region.blocks.empty or last_region.blocks.back.body.empty:
        return False
      # 在之前的检查后，如果只有一项内容，则可以合并
      if list.get_num_regions() == 1:
        return True
      # 检查每一项是否有除一个内容段落、一个列表操作项之外的其他内容，如果有的话就可以吸收
      for r in list.regions:
        is_first_content_block_found = False
        is_first_list_block_found = False
        for b in r.blocks:
          if b.body.empty:
            continue
          if isinstance(b.body.front, IMListOp):
            if is_first_list_block_found is True:
              return True
            is_first_list_block_found = True
          else:
            if is_first_content_block_found is True:
              return True
            is_first_content_block_found = True
      return False

    def walk_frame(frame : IMFrameOp):
      # cur_listop_stack 维护一个当前 IMListOp 嵌套层级的栈
      # 当我们不能再继续合并列表内容时，该栈清空
      # 当我们需要合并一个段落到当前访问的列表时，我们把该段划分给栈顶的列表
      # 但我们需要合并一个新的列表时，我们根据该列表的嵌套层级来进行合并
      cur_listop_stack : typing.List[IMListOp] = []
      cur_block = frame.body.blocks.front
      while cur_block is not None:
        if cur_block.body.empty:
          # 遇到一个空段落
          # 如果此时我们正在尝试合并，则立即停止
          cur_listop_stack = []
          cur_block = cur_block.get_next_node()
          continue
        # 该段落有内容
        # 如果我们有 IMListOp，则该操作项一般独占一段（除非有错误）
        # 如果这段是一个列表操作项，则我们首先尝试将其合并入当前的列表栈
        # 如果可以的话就合并，不行的话就在合适的地方“断开”
        # 如果这段不是一个列表操作项，则如果栈非空，就把该段内容“嫁接”到当前栈顶的列表操作项中
        # 如果空栈，则继续寻找第一个列表项
        if cur_block.body.size == 1 and isinstance(cur_block.body.front, IMListOp):
          # 这段是一个列表操作项
          if len(cur_listop_stack) > 0:
            cur_list : IMListOp = cur_block.body.front
            num_nest = 0
            # 展开所有嵌套
            # 如果该列表只有一个区，并且其内容也是一个列表，则我们视其为一重嵌套
            while cur_list.get_num_regions() == 1:
              first_region = cur_list.get_first_region()
              if first_region.blocks.size == 1:
                first_block = first_region.blocks.front
                if first_block.body.size == 1 and isinstance(first_block.body.front, IMListOp):
                  cur_list : IMListOp = first_block.body.front
                  num_nest += 1
                  continue
              break
            if num_nest > len(cur_listop_stack):
              # 正常情况下不应该出现这样的情况（也许用户是故意的？）
              # 放弃挣扎，跳过这个列表
              # something weird is happening (maybe the user is intentionally doing the wrong thing?)
              # just stop and skip this list
              cur_listop_stack = []
              cur_block = cur_block.get_next_node()
              continue
            if num_nest == len(cur_listop_stack):
              # 开启一个新的层叠层级
              # 将当前列表添加到栈顶列表最后一项的区中
              # we are opening a new nest level
              # move the current list to the stack top
              cur_parent_block = cur_list.parent_block
              assert cur_parent_block is not cur_block
              cur_parent_block.remove_from_parent()
              last_list = cur_listop_stack[-1]
              last_listitem = last_list.get_last_region()
              last_listitem.push_back(cur_parent_block)
              cur_listop_stack.append(cur_list)
              # 把 cur_block 删了然后继续
              cur_block = cur_block.erase_from_parent()
              continue
            # 当前列表的层级与已有的列表相同，需要进行合并
            # 首先检查两列表是否兼容：
            # 如果列表使用点(Bullet point)，则必定兼容
            # 如果列表使用数字，则所有区的名字不应重复
            # 若列表不兼容，则重新开始
            # 不管怎样，我们不会再需要层级更高的项
            if len(cur_listop_stack) > num_nest+1:
              cur_listop_stack = cur_listop_stack[0:num_nest+1]
            is_compatible = False
            existing_list = cur_listop_stack[num_nest]
            if existing_list.is_numbered == cur_list.is_numbered:
              is_compatible = True
              if existing_list.is_numbered:
                for r in cur_list.regions:
                  if existing_list.get_region(r.name) is not None:
                    is_compatible = False
                    break
              # 如果使用的是点，那么一定兼容，不需要额外检查
              if is_compatible:
                # 进行合并，这里我们只需将所有区搬迁到目标列表即可
                region_to_move = cur_list.get_first_region()
                while region_to_move is not None:
                  existing_list.take_list_item(region_to_move)
                  region_to_move = cur_list.get_first_region()
                # 删除当前列表
                cur_list.erase_from_parent()
                # 把 cur_block 删了然后继续
                cur_block = cur_block.erase_from_parent()
                continue
            # 这是列表不兼容的情况
            cur_listop_stack = []
            if num_nest == 0:
              cur_listop_stack.append(cur_list)
          else:
            cur_listop_stack.append(cur_block.body.front)
          cur_block = cur_block.get_next_node()
          continue
        # 该段有内容且不是op
        # 清空当前栈
        # 把内容整合进栈顶列表的最后一项
        #while len(cur_listop_stack) > 0 and not should_absorb_content(cur_listop_stack[-1]):
        #  cur_listop_stack.pop()
        cur_listop_stack.clear()
        #if len(cur_listop_stack) > 0:
        #  block_to_move = cur_block
        #  cur_block = cur_block.get_next_node()
        #  block_to_move.remove_from_parent()
        #  cur_listop_stack[-1].get_last_region().push_back(block_to_move)
        #  continue

        # 有内容且不是列表项、目前栈为空，则继续寻找第一个列表
        cur_block = cur_block.get_next_node()
        continue

    # end of the helper
    walk_frame(doc)

  def _try_recover_flattened_list(self, rootlist : IMListOp):
    # 首先检查是否只有一个层级，如果已经有多层级了就可以结束了
    # 同时收集每项的缩进距离
    # 如果有某层没有，那也没法做

    # 简单的情况先排除
    if rootlist.get_num_items() < 2:
      return

    dist_list : list[str] = []
    content_list : list[list[Operation]] = []
    for i in range(0, rootlist.get_num_items()):
      r = rootlist.get_item(i+1)
      cur_lmargin = None
      cur_contents = []
      has_content = False
      for b in r.blocks:
        for op in b.body:
          if isinstance(op, IMListOp):
            # 有内嵌列表，我们不需要修改这个的父列表
            return
          if isinstance(op, IMElementOp):
            if lmargin := op.get_attr("LeftMarginInList"):
              if isinstance(lmargin, str) and len(lmargin) > 0 and cur_lmargin is None:
                cur_lmargin = lmargin
            cur_contents.append(op)
            has_content = True
          elif isinstance(op, MetadataOp):
            cur_contents.append(op)
      if cur_lmargin is None:
        # 没这个信息也没法做转换
        return
      if not has_content:
        # 有项为空，不应该
        raise RuntimeError("Empty list item")
      dist_list.append(cur_lmargin)
      content_list.append(cur_contents)
    # 到这，所有项的距离都有了
    # 我们检查是否是同一单位（应该是同一单位），如果不是的话目前也放弃
    # (可能是百分比值也可能是绝对值+单位)
    dist_stripped_list : list[str] = []
    dist_set : set[str] = set()
    cur_tail = None
    for diststr in dist_list:
      if res := re.match(r"^(?P<dist>\d+(\.\d+)?).*$", diststr):
        dist = res.group("dist")
        tail = diststr[len(dist):]
        if cur_tail is None:
          cur_tail = tail
        else:
          if cur_tail != tail:
            # 单位不一致，没法转换
            return
        dist_stripped_list.append(dist)
        dist_set.add(dist)
      else:
        # 该参数不符合正则表达式，大概是bug...
        raise RuntimeError("Unexpected left margin repr: " + diststr)
    if len(dist_set) < 2:
      # 如果左边距都一样那也区分不了层级
      return
    dist_sorted : list[str] = []
    for dist in dist_set:
      dist_sorted.append(dist)
    dist_sorted.sort(key=lambda s : float(s))
    assert len(dist_stripped_list) == len(content_list)
    # 开始创建新列表
    # 如果某层级存着的是一个 IMListOp，那么我们已经为该层级创建了子列表，直接在其下加区即可
    # 如果某层级存着的是 Region，那么当前这一层级还是叶子结点，我们需要新建一个块、一个 IMListOp，然后再在其中加区
    # 先把旧列表清空，然后原地创造
    old_regions = [r for r in rootlist.regions]
    # 这里先只 remove，我们需要保留列表内容
    for r in old_regions:
      r.remove_from_parent()
    layerstack : list[IMListOp | Region] = [rootlist]
    for i in range(0, len(dist_stripped_list)):
      contents = content_list[i]
      for c in contents:
        c.remove_from_parent()
      level = dist_sorted.index(dist_stripped_list[i])
      if level >= len(layerstack):
        # 大概出了点 bug...
        level = len(layerstack) -1
      while len(layerstack) > level + 1:
        layerstack.pop()
      parent = layerstack[-1]
      if isinstance(parent, IMListOp):
        pass
      elif isinstance(parent, Region):
        pb = Block.create('', self.ctx)
        parent.push_back(pb)
        parent = IMListOp.create('', contents[0].location)
        layerstack[-1] = parent
        pb.push_back(parent)
      r = parent.add_list_item()
      b = Block.create('', self.ctx)
      r.push_back(b)
      for c in contents:
        b.push_back(c)
      layerstack.append(r)
    # 完成
    for r in old_regions:
      r.erase_from_parent()

  def transform_pass_recover_flattened_list(self, doc : IMDocumentOp):
    # 有些文档编辑器 (TextMaker) 生成的列表项没有嵌套的 list 结构，不管树状结构如何，所有的列表项都是平级
    # 不同层级之间用段落样式中的 margin-left 来表示缩进
    # 所以在此我们需要还原列表项结构
    for r in doc.regions:
      for b in r.blocks:
        for op in b.body:
          if isinstance(op, IMListOp):
            self._try_recover_flattened_list(op)
    # 完成

  def parse_odf(self) -> IMDocumentOp:
    self._populate_style_data(self.odfhandle.styles)
    self._populate_style_data(self.odfhandle.automaticstyles)

    assert self.cur_page_count == 1
    assert self.cur_row_count == 1
    assert self.cur_column_count == 1

    result : IMDocumentOp = IMDocumentOp.create(self.documentname, self.difile)
    self.odf_parse_frame(result.body, self.odfhandle.text, False)
    self.transform_pass_fix_text_elements(result)
    self.transform_pass_merge_special_blocks(result)
    self.transform_pass_reassociate_lists(result)
    self.transform_pass_recover_flattened_list(result)
    return result

def parse_odf(ctx : Context, filePath : str):
  pc = _ODParseContext(ctx = ctx, filePath = filePath)
  result = pc.parse_odf()
  pc.cleanup()
  return result

@FrontendDecl('odf', input_decl=IODecl('OpenDocument files', match_suffix=('.odf',), nargs='+'), output_decl=IMDocumentOp)
class ReadOpenDocument(TransformBase):
  _ctx : Context

  def __init__(self, _ctx: Context) -> None:
    super().__init__(_ctx)
    self._ctx = _ctx

  def run(self) -> IMDocumentOp | typing.List[IMDocumentOp]:
    if len(self.inputs) == 1:
      return parse_odf(self._ctx, self.inputs[0])
    results = []
    for f in self.inputs:
      results.append(parse_odf(self._ctx, f))
    return results

def _main():
  if len(sys.argv) < 2 or len(sys.argv[1]) == 0:
    print("please specify the input file!")
    sys.exit(1)
  ctx = Context()
  filePath = sys.argv[1]
  doc = parse_odf(ctx, filePath)
  doc.view()

if __name__ == "__main__":
  _main()

