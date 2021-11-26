#!/usr/bin/env python3

import io, sys
import typing

import preppipe.documentmodel as documentmodel
import preppipe.visualnovelmodel as visualnovelmodel

def get_visual_novel_model_from_document(doc : documentmodel.DocumentModel) -> visualnovelmodel.VisualNovelModel:
  """Convert a DocumentModel into a VisualNovelModel
  This function makes best effort in converting all information, even if there are errors
  """
  result = visualnovelmodel.VisualNovelModel()
  # TODO import all images
  
  currentContext = result.getEmptyContext()
  currentBlock = None
  
  def getParentNode() -> visualnovelmodel.VNElementBlock:
    nonlocal currentBlock
    nonlocal currentContext
    nonlocal result
    if currentBlock is None:
      currentBlock = visualnovelmodel.VNElementBlock(currentContext)
      result.addBlock(currentBlock)
    return currentBlock
  
  for p in doc.paragraph_list:
    # ignore empty paragraphs
    if p.empty():
      continue
    # pattern detection
    
    # default case
    block = getParentNode();
    block.addElement(visualnovelmodel.VNClearElement())
    for e in p.element_list:
      if isinstance(e, documentmodel.TextElement):
        sayText = e.getText()
        attributeDict = {}
        sayStyle = e.getStyle()
        if sayStyle.bold():
          attributeDict[visualnovelmodel.VNTextAttribute.Bold] = True
        if sayStyle.italic():
          attributeDict[visualnovelmodel.VNTextAttribute.Italic] = True
        if sayStyle.has_nonzero_sizelevel():
          attributeDict[visualnovelmodel.VNTextAttribute.Size] = sayStyle.size_level()
        if sayStyle.has_text_color():
          attributeDict[visualnovelmodel.VNTextAttribute.TextColor] = sayStyle.text_color()
        if sayStyle.has_background_color():
          attributeDict[visualnovelmodel.VNTextAttribute.BackgroundColor] = sayStyle.background_color()
        
        textElement = visualnovelmodel.VNSayTextElement(sayText, attributeDict)
        block.addElement(textElement)
      else:
        raise RuntimeError("Unhandled element type")
  return result

    