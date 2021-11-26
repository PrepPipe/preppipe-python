#!/usr/bin/env python3

import typing
import PIL.Image
from enum import Enum
import preppipe.commontypes

class VNContext:
  def __init__(self) -> None:
    self.background_music = None
    self.background_image = None

class VNElement:
  """VNElement
  Representing an actionable data element inside the VN model
  """
  
  def __init__(self) -> None:
    pass

class VNElementBlock:
  """VNElementBlock
  Basically a list of VNElements under the same VNContext
  All elements are guaranteed to execute from the first to last (similar to a basic block)
  """
  ctx : VNContext = None
  element_list : typing.List[VNElement] = []
  
  def __init__(self, context : VNContext) -> None:
    self.ctx = context
    self.element_list = []
  
  def addElement(self, element : VNElement) -> None:
    self.element_list.append(element)
  

class VisualNovelModel:
  context_list : typing.List[VNContext] = []
  block_list : typing.List[VNElementBlock] = []
  empty_context : VNContext = None
  
  def __init__(self) -> None:
    self.context_list = []
    self.block_list = []
    # create an empty context so that referencing code can query the object
    self.empty_context = VNContext()
  
  def addBlock(self, block : VNElementBlock):
    self.block_list.append(block)
  
  def addContext(self, ctx : VNContext):
    self.context_list.append(ctx)
  
  def getEmptyContext(self) -> VNContext:
    return self.empty_context
  
class VNClearElement(VNElement):
  """This Element clears all temporary data (similar to \\r)"""
  def __init__(self) -> None:
    pass

class VNTextAttribute(Enum):
  Bold = 0
  Italic = 1
  Size = 2
  TextColor = 3
  BackgroundColor = 4
  RubyText = 5
  HoverContent = 6 # unimplemented for now
  ClickAction = 7  # unimplemented for now

class VNSayTextElement(VNElement):
  """This element represents a piece of spoken text"""
  attributes : typing.Dict[VNTextAttribute, typing.Any] = {}
  text : str = ""
  
  def __init__(self, text : str = "", attributes : typing.Dict[VNTextAttribute, typing.Any] = {}) -> None:
    super().__init__()
    self.text = text
    self.attributes = attributes
  
  def bold(self) -> bool:
    return VNTextAttribute.Bold in self.attributes
  
  def italic(self) -> bool:
    return VNTextAttribute.Italic in self.attributes
  
  def has_nonzero_sizelevel(self) -> bool:
    return VNTextAttribute.Size in self.attributes
  
  def size_level(self) -> int:
    return self.attributes.get(VNTextAttribute.Size, 0)
  
  def has_text_color(self) -> bool:
    return VNTextAttribute.TextColor in self.attributes
  
  def text_color(self) -> preppipe.commontypes.Color:
    return self.attributes.get(VNTextAttribute.TextColor, preppipe.commontypes.Color())
  
  def has_background_color(self) -> bool:
    return VNTextAttribute.BackgroundColor in self.attributes
  
  def background_color(self) -> preppipe.commontypes.Color:
    return self.attributes.get(VNTextAttribute.BackgroundColor, preppipe.commontypes.Color())
  
  def has_ruby_text(self) -> bool:
    return VNTextAttribute.RubyText in self.attributes
  
  def ruby_text(self) -> str:
    return self.attributes.get(VNTextAttribute.RubyText, "")
  
  
  
  
  
  