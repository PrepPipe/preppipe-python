#!/usr/bin/env python3
import io, sys
import typing

import odf.opendocument

import preppipe.documentmodel as documentmodel
import preppipe.commontypes


def import_odf(fileData : io.BufferedReader, filename : str) -> documentmodel.DocumentModel:
  """Import an ODF document and return a document model"""

  odfhandle = odf.opendocument.load(fileData)
  
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
  
  def populate_paragraph(p: documentmodel.Paragraph, node: odf.element.Element, default_style: str) -> None:
    for element in node.childNodes:
      if element.nodeType == 3:
        # this is a text node
        text = str(element)
        element_node = create_node(text, default_style)
        p.addElement(element_node)
      elif element.nodeType == 1:
        # this is a node with attribute
        style = get_style(element)
        if (style == ""):
          style = default_style
        p = populate_paragraph(p, element, style)
      else:
        print("Warning: unhandled node type (" + str(element.nodeType) + "): " + str(element))
    return p
    # done!
  
  textroot = odfhandle.text
  # "rebase" to the real text root (i.e., skipping the empty parents)
  # textroot = textroot.childNodes[0].childNodes[0]

  result = documentmodel.DocumentModel()
  for paragraphnode in textroot.childNodes:
    
    # skip weird nodes like sequence-decls
    if paragraphnode.qname[1] != "p":
      continue
    
    p = documentmodel.Paragraph()
    default_style = get_style(paragraphnode)
    p = populate_paragraph(p, paragraphnode, default_style)
    result.addParagraph(p)
  
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
  
