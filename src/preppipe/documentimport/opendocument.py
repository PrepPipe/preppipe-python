#!/usr/bin/env python3
import io, sys, os
import typing
from warnings import warn
import PIL.Image

import odf.opendocument

import preppipe.documentmodel as documentmodel
import preppipe.commontypes


def import_odf(fileData : io.BufferedReader, filePath: str) -> documentmodel.DocumentModel:
  """Import an ODF document and return a document model"""

  odfhandle = odf.opendocument.load(fileData)
  basedir = os.path.dirname(filePath)
  documentname = os.path.splitext(os.path.basename(filePath))[0]
  
  # common helper function
  def get_attribute(node: odf.element.Element, attr: str) -> str:
    for k in node.attributes.keys():
      if (k[1] == attr):
        return node.attributes[k];
    return ""
  
  # step 1: find style info to be able to tell bold, italic, etc. text
  
  styledict : typing.Dict[str, documentmodel.TextAttributeSet] = {}
  
  # insert this as value if one style is unimportant
  no_style = documentmodel.TextAttributeSet()
    
  def populate_styles(node: odf.element.Element):
    for child in node.childNodes:
      if child.qname[1] == "style":
        # we found a style entry
        name = get_attribute(child, "name")
        # should not happen, but just in case
        if len(name) == 0:
          continue;
        # if we have a parent-style-name, we need to modify from the parent style
        parent_style = get_attribute(child, "parent-style-name")
        base_style = no_style
        if len(parent_style) > 0:
          base_style = styledict[parent_style];
        # we should have child nodes of type text-properties
        # we don't care about paragraph-properties for now
        override_style = documentmodel.TextAttributeSet()
        for property_node in child.childNodes:
          if property_node.qname[1] == "text-properties":
            for k in property_node.attributes.keys():
              if k[1] == "font-weight" and property_node.attributes[k] == "bold":
                override_style.set_bold(True)
              elif k[1] == "font-style" and property_node.attributes[k] == "italic":
                override_style.set_italic(True)
              elif k[1] == "color":
                override_style.set_text_color(preppipe.commontypes.Color.get(property_node.attributes[k]))
              elif k[1] == "background-color":
                override_style.set_background_color(preppipe.commontypes.Color.get(property_node.attributes[k]))
        overall_style = documentmodel.get_merged_text_style(base_style, override_style)
        styledict[name] = overall_style
      else:
        # not a style node; just recurse
        if (len(child.childNodes) > 0):
          populate_styles(child)
  
  populate_styles(odfhandle.styles)
  populate_styles(odfhandle.automaticstyles)
  
  # step 2: handle text extraction
  result = documentmodel.DocumentModel()
  
  def get_style(node) -> str:
    """Extract the style-name attribute from the element node"""
    return get_attribute(node, "style-name")
  
  missing_style_list : typing.List[str] = []
  def create_node(text:str, style_name:str) -> documentmodel.TextElement:
    """Create the text element with the provided text and style name.
    The flags for the text element will be set from the style name
    """
    if style_name in styledict:
      style = styledict[style_name]
      node = documentmodel.TextElement(text, style)
      return node
    # style_name not found
    # add to notification
    if style_name not in missing_style_list:
      missing_style_list.append(style_name)
    # just create a text without format
    node = documentmodel.TextElement(text)
    return node
  
  image_dict : typing.Dict[str, object] = {}
  def getImageHandle(href : str) -> documentmodel.ImageData:
    """Convert image href to the registered image instance"""
    if href in image_dict:
      return image_dict[href]
    if href in odfhandle.Pictures:
      (FilenameOrImage, data, mediatype) = odfhandle.Pictures[href]
      if FilenameOrImage == odf.opendocument.IS_FILENAME:
        # not sure when will this happen...
        imagePath = os.path.join(basedir, documentname, data)
        image = PIL.Image.open(imagePath)
      elif FilenameOrImage == odf.opendocument.IS_IMAGE:
        # the image is embedded in the file
        image = PIL.Image.open(io.BytesIO(data))
    else:
      # the image is a link to outside file
      imagePath = os.path.join(basedir, documentname, href)
      image = PIL.Image.open(imagePath)
    handle = result.registerImage(image)
    image_dict[href] = handle
    return handle
  
  warned_UnexpectedAnchorType = False
  expectedAnchorTypes = ["as-char", "char", "paragraph"]
  def warn_UnexpectedAnchorType(ty : str) -> None:
    nonlocal warned_UnexpectedAnchorType
    if not warned_UnexpectedAnchorType:
      warned_UnexpectedAnchorType = True
      warn("Frame (image, textbox, etc) with unexpected anchor type " + ty + "found. Please inspect the output on possible mispositions of frame data. (Expecting: "+ str(expectedAnchorTypes) + ")")
  
  warned_MultipleChildPerFrame = False
  def warn_MultipleChildPerFrame() -> None:
    nonlocal warned_MultipleChildPerFrame
    if not warned_MultipleChildPerFrame:
      warned_MultipleChildPerFrame = True
      warn("Frame (image, textbox, etc) has more than one child element. Please inspect the output on possible data omission.")
  
  def populate_paragraph(p: documentmodel.Paragraph, node: odf.element.Element, default_style: str) -> None:
    for element in node.childNodes:
      if element.nodeType == 3:
        # this is a text node
        text = str(element)
        if len(text) > 0:
          element_node = create_node(text, default_style)
          p.addElement(element_node)
      elif element.nodeType == 1 and element.qname[1] == "span":
        # this is a node with attribute
        style = get_style(element)
        if (style == ""):
          style = default_style
        populate_paragraph(p, element, style)
      elif element.nodeType == 1 and element.qname[1] == "frame":
        # we do not support arbitrary frame nesting (there is no "frame" in document model)
        # just expand them here
        # if there is an image, add an image element
        # if there is a text box:
        #   - if the text box only have one paragraph: consider the text box content as part of current paragraph
        #   - if the text box has more than one paragraph: the first paragraph is considered as part of the paragraph and the rest are considered as new paragraphs
        
        if len(element.childNodes) == 0:
          continue
        
        # check whether the frame has the expected anchoring
        anchor = get_attribute(element, "anchor-type")
        if anchor not in expectedAnchorTypes:
          warn_UnexpectedAnchorType(anchor)
        
        # if we have more than one child in a frame, warn that we will ignore content
        if (len(element.childNodes) > 1):
          warn_MultipleChildPerFrame()
        
        firstChild = element.childNodes[0]
        
        if firstChild.nodeType == 1 and firstChild.qname[1] == "image":
          href = get_attribute(firstChild, "href")
          imgref = getImageHandle(href)
          imgelem = documentmodel.ImageReferenceElement(imgref)
          p.addElement(imgelem)
          
        elif firstChild.nodeType == 1 and firstChild.qname[1] == "text-box":
          # the default text style for textbox text is specified on the frame
          style = get_attribute(element, "text-style-name")
          if (style == ""):
            style = default_style
          
          isCurrentParagraphDone = False
          for textboxParagraph in firstChild.childNodes:
            if not isCurrentParagraphDone:
              populate_paragraph(p, textboxParagraph, style)
              isCurrentParagraphDone = True
            else:
              # we will create new paragraphs after the current one and handle those 
              curParagraph = documentmodel.Paragraph()
              result.addParagraph(curParagraph)
              populate_paragraph(curParagraph, textboxParagraph, style)
        else:
          print("Warning: unhandled node type in frame: " + str(element.qname) + ": " + str(element))
        
      else:
        print("Warning: unhandled node type " + str(element.qname) + ": " + str(element))
    # done!
  
  for paragraphnode in odfhandle.text.childNodes:
    
    # skip weird nodes like sequence-decls
    if paragraphnode.qname[1] != "p":
      continue
    
    p = documentmodel.Paragraph()
    result.addParagraph(p)
    default_style = get_style(paragraphnode)
    populate_paragraph(p, paragraphnode, default_style)
    
  
  # done
  if len(missing_style_list) > 0:
    print("Warning: styles not found: " + str(missing_style_list))
  return result

if __name__ == "__main__":
  if len(sys.argv) < 2 or len(sys.argv[1]) == 0:
    print("please specify the input file!")
    sys.exit(1)
  infile = sys.argv[1]
  fileData = open(infile, "rb")
  doc = import_odf(fileData, infile)
  print("Dump:")
  doc.dump()
  print("Print:")
  print(doc)
  
