# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import io, sys, os
import typing
from warnings import warn
import PIL.Image

import odf.opendocument

from ..inputmodel import *

class _TextStyleInfo:
  # temporary structure for text style
  # we don't have a relative font sizing metric (used in InputModel) until we parsed all the text
  # this structure temporarily holds the style info during the parsing
  style : typing.Dict[TextAttribute, typing.Any]
  is_strike_through : bool # if the font has strikethrough (and we will drop it after generation)
  
  def __init__(self, src = None):
    self.style = {}
    self.is_strike_through = False
    if src is not None:
      assert isinstance(src, _TextStyleInfo)
      self.style = src.style.copy()
      self.is_strike_through = src.is_strike_through
  
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
    self.style[TextAttribute.TextColor] = color
  
  def set_background_color(self, color: Color):
    self.style[TextAttribute.BackgroundColor] = color
  
  def set_strike_through(self, v : bool):
    self.is_strike_through = v

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
  settings : IMSettings
  cache : IMParseCache
  filePath : str
  odfhandle: odf.opendocument.OpenDocument
  difile : DIFile
  documentname : str
  
  style_data : typing.Dict[str, _TextStyleInfo]
  list_style_data : typing.Dict[str, _ListStyleInfo]
  asset_reference_dict : typing.Dict[str, AssetData | typing.Tuple[ConstantString, ConstantString]] # cache asset request results; either the asset or the error tuple
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
  
  def __init__(self, ctx : Context, settings : IMSettings, cache : IMParseCache, filePath : str) -> None:
    filePath = os.path.realpath(filePath, strict=True)
    self.ctx = ctx
    self.settings = settings
    self.cache = cache
    self.filePath = filePath
    self.odfhandle = odf.opendocument.load(filePath)
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
        current_style = _TextStyleInfo()
        if len(parent_style) > 0:
          current_style = _TextStyleInfo(self.style_data[parent_style])
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
  
  def create_text_element(self, text:str, style_name:str, loc : DILocation) -> IMElementOp | typing.Tuple[IMElementOp, IMErrorElementOp]:
    """Create the text element with the provided text and style name.
    The flags for the text element will be set from the style name
    """
    # 如果文本被划掉（有strikethrough），则我们在此添加一个StrikeThrough的属性，这个 IMElementOp 会在之后的 transform_pass_fix_text_elements() 中消耗掉
    content = ConstantString.get(text, self.ctx)
    error_op = None
    cstyle = None
    is_strike_through = False
    if style_name in self.style_data:
      style = self.style_data[style_name]
      if style.is_strike_through:
        is_strike_through = True
      cstyle = ConstantTextStyle.get(style.style, self.ctx)
    else:
      cstyle = ConstantTextStyle.get(style.style, self.ctx)
      error_op = IMErrorElementOp(name = '', loc = loc, content = content, error_code='odf-bad-style-name', error_msg = ConstantString.get('Cannot find style name \"' + style_name + '"', self.ctx))
    content = ConstantTextFragment.get(self.ctx, content, cstyle)
    node = IMElementOp(name = '', loc = loc, content = content)
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
  
  def create_image_reference(self, href : str, loc : DILocation) -> IMElementOp:
    if href in self.asset_reference_dict:
      value = self.asset_reference_dict[href]
      if isinstance(value, AssetData):
        return IMElementOp(name = '', loc = loc, content = value)
      else:
        content = value[0]
        err = value[1]
        return IMErrorElementOp(name = '', loc = loc, content = content, error_code='odf-bad-image-ref', error_msg = err)
    
    value : Value = None
    if href in self.odfhandle.Pictures:
      (FilenameOrImage, data, mediatype) = self.odfhandle.Pictures[href]
      if FilenameOrImage == odf.opendocument.IS_FILENAME:
        # not sure when will this happen...
        raise NotImplementedError('odf.opendocument.IS_FILENAME for image reference not supported yet')
        #imagePath = os.path.join(self.basedir, self.documentname, data)
        #entry = self.parent.get_image_asset_entry_from_path(imagePath, mediatype)
      elif FilenameOrImage == odf.opendocument.IS_IMAGE:
        # the image is embedded in the file
        raise NotImplementedError()
        # entry = self.parent.get_image_asset_entry_from_inlinedata(data, mediatype, self.filePath, href)
    else:
      # the image is a link to outside file
      imagePath = os.path.join(self.filePath, href)
      def fileCheckCB(path) -> ImageAssetData:
        if os.path.isfile(path):
          return self.cache.query_image_asset(path)
        return None
      value = self.settings.search(imagePath, self.filePath, fileCheckCB)
    
    if not isinstance(value, ImageAssetData):
      msg = "Cannot resolve reference to image \"" + href + "\" (please check file presence or security violation)"
      MessageHandler.critical_warning(msg, self.filePath)
      textstr = ConstantString.get(href, self.ctx)
      msgstr = ConstantString.get(msg, self.ctx)
      self.asset_reference_dict[href] = (textstr, msgstr)
      return IMErrorElementOp(name = '', loc = loc, content = textstr, error_code='odf-bad-image-ref', error_msg = msgstr)
    
    self.asset_reference_dict[href] = value
    return IMElementOp(name = '', loc = loc, content = value)
  
  def _get_unsupported_element_op(self, element : odf.element.Element) -> IMErrorElementOp:
    loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
    return IMErrorElementOp(name = str(element.qname), loc = loc, content = ConstantString.get(str(element), self.ctx), error_code='unsupported-element')
  
  def odf_parse_paragraph(self, rootnode : odf.element.Element, isInFrame : bool, default_style: str = "") -> Block:
    def populate_paragraph(paragraph: Block, rootnode : odf.element.Element, default_style: str, isInFrame : bool) -> None:
      for element in rootnode.childNodes:
        loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
        if element.nodeType == 3:
          # this is a text node
          text = str(element)
          if len(text) > 0:
            element_node_or_pair = self.create_text_element(text, default_style, loc)
            if isinstance(element_node_or_pair, tuple):
              # an IMElementOp and an IMErrorElementOp
              for e in element_node_or_pair:
                paragraph.push_back(e)
            else:
              assert isinstance(element_node_or_pair, IMElementOp)
              paragraph.push_back(element_node_or_pair)
            self.cur_column_count += len(text)
        elif element.nodeType == 1:
          if element.qname[1] == "span":
            # this is a node with attribute
            style = self.get_style(element)
            if (style == ""):
              style = default_style
            populate_paragraph(paragraph, element, style, isInFrame)
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
              
            elif firstChild.nodeType == 1 and first_child_name == "text-box":
              # we do not support nested textbox. If we are already in frame, we skip this text box
              loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
              if isInFrame:
                warn_str = "Frame (" + first_child_name +") is inside a framed environment, and is therefore ignored"
                MessageHandler.warning(warn_str, self.filePath, str(loc))
                paragraph.push_back(IMErrorElementOp('', loc, content= ConstantString.get("text-box", self.ctx), error_code='odf-nested-frame', error_msg= ConstantString.get(warn_str, self.ctx)))
              else:
                # let's deal with this text box
                # the default text style for textbox text is specified on the frame, instead of the text-box element
                style = self._get_element_attribute(element, "text-style-name")
                if (style == ""):
                  style = default_style
                frame = IMFrameOp('', loc)
                self.odf_parse_frame(frame.body, firstChild, True, style)
                paragraph.push_back(frame)
            else:
              paragraph.push_back(self._get_unsupported_element_op(element))
              # print("Warning: unhandled node type in frame: " + str(element.qname) + ": " + str(element))
            # end of elements in frame
          elif element.qname[1] == "soft-page-break":
            # entering a new page
            self.cur_page_count += 1
            self.cur_row_count = 1
            self.cur_column_count = 1
          else:
            paragraph.push_back(self._get_unsupported_element_op(element))
            # MessageHandler.warning("Warning: unhandled node type in frame: " + str(element.qname) + ": " + str(element), self.filePath, str(loc))
        else:
          MessageHandler.warning("Warning: unhandled node type " + str(element.qname) + ": " + str(element), self.filePath, str(loc))
      # done!
    paragraph = Block('', self.ctx)
    default_style_read = self.get_style(rootnode)
    if len(default_style_read) > 0:
      default_style = default_style_read
    populate_paragraph(paragraph, rootnode, default_style, isInFrame)
    # exiting the current paragraph; reset column
    self.cur_row_count += 1
    self.cur_column_count = 1
    return paragraph
  
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
        case "p":
          # paragraph
          paragraph = self.odf_parse_paragraph(node, isInFrame, default_style)
          result.push_back(paragraph)
        case 'list':
          # list is in parallel with paragraph in odf
          listop = IMListOp('', self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count))
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
                    startvalue = parent_op.get_attr('StartValue').data
                    assert isinstance(startvalue, int)
                    listop.set_attr('StartValue', startvalue)
                else:
                  listop.is_numbered = False
            if is_emit_error:
              list_error_op = IMErrorElementOp('', listop.location, content = ConstantString.get(list_style, self.ctx), error_code='odf-bad-list-style', error_msg = ConstantString.get('Cannot get list style', self.ctx))
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
          container_paragraph = Block('', self.ctx)
          container_paragraph.body.push_back(listop)
          if list_error_op is not None:
            container_paragraph.body.push_back(list_error_op)
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
          while cur_op is not end_op:
            assert type(cur_op) == IMElementOp
            # 加上这条检查，这样万一以后在首次生成 IMElementOp 时沾上属性后，我们可以在这里添加对属性的合并
            assert cur_op.attributes.empty
            cur_content = cur_op.content.get()
            assert isinstance(cur_content, ConstantTextFragment)
            if cur_style is None:
              # this is the first time we visit an element
              cur_text = cur_content.content.value
              assert len(cur_text) > 0
              cur_style = cur_content.style
            elif cur_content.style is cur_style:
              # we get an fragment with the same style
              cur_text += cur_content.content.value
            else:
              # we get an fragment with a different style
              # first, end the last fragment
              new_frag = ConstantTextFragment.get(self.ctx, ConstantString.get(cur_text, self.ctx), cur_style)
              fragment_list.append(new_frag)
              # now start the new one
              cur_text = cur_content.content.value
              assert len(cur_text) > 0
              cur_style = cur_content.style
            # finished handling current op
            cur_op = cur_op.get_next_node()
          # finished the first iteration
          # end the last fragment
          assert len(cur_text) > 0
          new_frag = ConstantTextFragment.get(self.ctx, ConstantString.get(cur_text, self.ctx), cur_style)
          # create the new element
          new_content = None
          if len(fragment_list) == 0:
            new_content = new_frag
          else:
            fragment_list.append(new_frag)
            new_content = ConstantText.get(self.ctx, fragment_list)
          newop  = IMElementOp(first_text_op.name, first_text_op.location, new_content)
          # now replace the current ops
          newop.insert_before(first_text_op)
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
            if isinstance(content, ConstantTextFragment) and not op.has_attr('StrikeThrough'):
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
        # 如果一个段落里全是被删除的文本，则我们在此也将把该段落去掉
        if not b.body.empty:
          is_all_strikethrough = True
          for op in b.body:
            if type(op) == IMElementOp and op.get_attr('StrikeThrough') is not None:
              pass
            else:
              is_all_strikethrough = False
              break
          if is_all_strikethrough:
            blocks_to_delete.append(b)
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
  
  def parse_odf(self) -> IMDocumentOp:
    self._populate_style_data(self.odfhandle.styles)
    self._populate_style_data(self.odfhandle.automaticstyles)
    
    assert self.cur_page_count == 1
    assert self.cur_row_count == 1
    assert self.cur_column_count == 1
    
    result : IMDocumentOp = IMDocumentOp(self.documentname, self.difile)
    self.odf_parse_frame(result.body, self.odfhandle.text, False)
    self.transform_pass_fix_text_elements(result)
    self.transform_pass_reassociate_lists(result)
    return result

def parse_odf(ctx : Context, settings : IMSettings, cache : IMParseCache, filePath : str):
  # ctx : Context, settings : IMSettings, cache : IMParseCache, filePath : str
  pc = _ODParseContext(ctx = ctx, settings = settings, cache = cache, filePath = filePath)
  return pc.parse_odf()

def _main():
  if len(sys.argv) < 2 or len(sys.argv[1]) == 0:
    print("please specify the input file!")
    sys.exit(1)
  ctx = Context()
  settings = IMSettings()
  cache = IMParseCache(ctx)
  filePath = sys.argv[1]
  doc = parse_odf(ctx, settings, cache, filePath)
  doc.view()
  
if __name__ == "__main__":
  _main()

