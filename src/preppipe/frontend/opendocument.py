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
                # TODO other attrs
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
  
  def create_text_element(self, text:str, style_name:str, loc : DILocation) -> IMElementOp:
    """Create the text element with the provided text and style name.
    The flags for the text element will be set from the style name
    """
    content = ConstantString.get(text, self.ctx)
    node = IMElementOp(name = '', loc = loc, content = content)
    node.set_attr('TextStyle', style_name)
    return node
    
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
            # TODO update the location info
            element_node = self.create_text_element(text, default_style, loc)
            paragraph.push_back(element_node)
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
                self.odf_parse_frame(frame, firstChild, True, style)
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
  
  def odf_parse_frame(self, result : IMFrameOp, rootnode : odf.element.Element, isInFrame : bool, default_style : str = ""):
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
      # skip sequence-decls
      #if nodetype == "sequence-decls":
      #  continue
      #if nodetype == "p":
        # paragraph
      #  paragraph = self.odf_parse_paragraph(node, isInFrame, default_style)
      #  result.body.push_back(paragraph)
      #  continue
      match nodetype:
        case "sequence-decls":
          # do nothing
          pass
        case "p":
          # paragraph
          paragraph = self.odf_parse_paragraph(node, isInFrame, default_style)
          result.body.push_back(paragraph)
        case 'list':
          # list is in parallel with paragraph in odf
          listop = IMListOp('', self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count))
          for listnode in node.childNodes:
            listnodetype = listnode.qname[1]
            match listnodetype:
              case 'list-header':
                # should appear before all the list item
                # treat it as a new paragraph
                # (this part is not tested)
                paragraph = self.odf_parse_paragraph(node, isInFrame, default_style)
                result.body.push_back(paragraph)
              case 'list-item':
                # basically each list item should be in parallel with a frame, but we expect most of them to only contain one paragraph
                # so we first create a dummy frame to parse the children, then extract the paragraphs and add to frame
                dummy_frame = IMFrameOp('', self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count))
                self.odf_parse_frame(dummy_frame, listnode, False, default_style)
                #if dummy_frame.body.blocks.size >= 2:
                #  MessageHandler.warning('List contains multiple blocks (len={0}, frame_id={1})'.format(str(dummy_frame.body.blocks.size), hex(id(listop))), location=str(dummy_frame.location))
                while not dummy_frame.body.blocks.empty:
                  frontblock =  dummy_frame.body.blocks.front
                  frontblock.remove_from_parent()
                  listop.body.push_back(frontblock)
          container_paragraph = Block('', self.ctx)
          container_paragraph.body.push_back(listop)
          result.body.push_back(container_paragraph)
        case _:
          # node type not recognized
          loc = self.get_DILocation(self.cur_page_count, self.cur_row_count, self.cur_column_count)
          MessageHandler.warning("Element unrecognized and ignored: " + nodetype, self.filePath, str(loc))
  
  def parse_odf(self) -> IMDocumentOp:
    self._populate_style_data(self.odfhandle.styles)
    self._populate_style_data(self.odfhandle.automaticstyles)
    
    assert self.cur_page_count == 1
    assert self.cur_row_count == 1
    assert self.cur_column_count == 1
    
    result : IMDocumentOp = IMDocumentOp(self.documentname, self.difile)
    self.odf_parse_frame(result, self.odfhandle.text, False)
    return result

def parse_odf(ctx : Context, settings : IMSettings, cache : IMParseCache, filePath : str):
  # ctx : Context, settings : IMSettings, cache : IMParseCache, filePath : str
  pc = _ODParseContext(ctx = ctx, settings = settings, cache = cache, filePath = filePath)
  return pc.parse_odf()

if __name__ == "__main__":
  if len(sys.argv) < 2 or len(sys.argv[1]) == 0:
    print("please specify the input file!")
    sys.exit(1)
  ctx = Context()
  settings = IMSettings()
  cache = IMParseCache(ctx)
  filePath = sys.argv[1]
  doc = parse_odf(ctx, settings, cache, filePath)
  doc.view()
  


