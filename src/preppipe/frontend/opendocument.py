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
  missing_style_list : typing.List[str]
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
    self.missing_style_list = []
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
        # we found a style entry
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
      error_op = IMErrorElementOp(name = '', loc = loc, content = content, error = ConstantString.get('Cannot find style name \"' + style_name + '"', self.ctx))
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
        return IMErrorElementOp(name = '', loc = loc, content = content, error = err)
    
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
      return IMErrorElementOp(name = '', loc = loc, content = textstr, error = msgstr)
    
    self.asset_reference_dict[href] = value
    return IMElementOp(name = '', loc = loc, content = value)
  
  def _get_unsupported_element_op(self, element : odf.element.Element) -> IMUnsupportedElementOp:
    loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
    return IMUnsupportedElementOp(name = str(element.qname), loc = loc, content = ConstantString.get(str(element), self.ctx))
  
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
                paragraph.push_back(IMErrorElementOp('', loc, ConstantString.get("text-box", self.ctx), ConstantString.get(warn_str, self.ctx)))
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
                self.odf_parse_frame(listop.add_list_item(), listnode, False, default_style)
          container_paragraph = Block('', self.ctx)
          container_paragraph.body.push_back(listop)
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
    def walk_region(region : Region):
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

        for op in b.body:
          if op.get_num_regions() > 0:
            assert not isinstance(op, IMElementOp)
            coalesce()
            for r in op.regions:
              walk_region(r)
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
      # end of the helper function
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
    pass
  
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

