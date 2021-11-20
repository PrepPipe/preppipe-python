#!/usr/bin/env python3

import typing
import PIL.Image
from enum import Enum

class ParagraphElement:
  def __init__(self) -> None:
    pass
  
  def __str__(self) -> str:
    return "<ParagraphElement>"
  
  def dump(self, indent: int = 0):
    raise NotImplementedError()

class Paragraph:
  element_list : typing.List[ParagraphElement] = []
  
  def __init__(self) -> None:
    self.element_list = []
  
  def addElement(self, element : ParagraphElement) -> None:
    self.element_list.append(element)
  
  def __str__(self) -> str:
    result = ""
    for e in self.element_list:
      result += e.__str__()
    return result
  
  def dump(self, indent: int = 0):
    if (len(self.element_list) == 0):
      print("[]", end="")
      return
    
    print("[", end="")
    isFirst: bool = True
    for element in self.element_list:
      if (isFirst):
        isFirst = False
      else:
        print(",", end="")
      print("\n" + "  "*(indent+1), end="")
      element.dump(indent+1)
    print("\n" + "  "*indent + "]", end="")

class TextAttribute(Enum):
  Bold = 0
  Italic = 1
  Size = 2
  TextColor = 3
  BackgroundColor = 4
 
class TextAttributeSet:
  attributes : typing.Dict = {}
  
  def __init__(self) -> None:
    self.attributes = {}
  
  def bold(self) -> bool:
    return TextAttribute.Bold in self.attributes
  
  def set_bold(self, value: bool = True) -> None:
    if (value):
      self.attributes[TextAttribute.Bold] = True
    else:
      self.attributes.pop(TextAttribute.Bold, None)
  
  def italic(self) -> bool:
    return TextAttribute.Italic in self.attributes
  
  def set_italic(self, value: bool = True) -> None:
    if value:
      self.attributes[TextAttribute.Italic] = True
    else:
      self.attributes.pop(TextAttribute.Italic, None)
  
  def size_level(self) -> int:
    if TextAttribute.Size in self.attributes:
      return self.attributes[TextAttribute.Size]
    return 0
  
  def has_nonzero_sizelevel(self) -> bool:
    return self.size_level() != 0
  
  def set_size(self, size: int) -> None:
    if (size == 0):
      self.attributes.pop(TextAttribute.Size, None)
    else:
      self.attributes[TextAttribute.Size] = size
  
  def text_color(self) -> str:
    if TextAttribute.TextColor in self.attributes:
      return self.attributes[TextAttribute.TextColor]
    return ""
  
  def background_color(self) -> str:
    if TextAttribute.BackgroundColor in self.attributes:
      return self.attributes[TextAttribute.BackgroundColor]
    return ""
  
  def has_text_color(self) -> bool:
    return TextAttribute.TextColor in self.attributes
  
  def has_background_color(self) -> bool:
    return TextAttribute.BackgroundColor in self.attributes
  
  def set_text_color(self, color: str) -> None:
    if len(color) == 0 or color == "transparent":
      self.attributes.pop(TextAttribute.TextColor, None)
    else:
      self.attributes[TextAttribute.TextColor] = color
  
  def set_background_color(self, color: str) -> None:
    if len(color) == 0 or color == "transparent":
      self.attributes.pop(TextAttribute.BackgroundColor, None)
    else:
      self.attributes[TextAttribute.BackgroundColor] = color
  
def get_merged_text_style(base: TextAttributeSet, patch: TextAttributeSet) -> TextAttributeSet:
  if len(patch.attributes) == 0:
    return base
  if len(base.attributes) == 0:
    return patch
  newset = {}
  for key, value in patch.attributes:
    if key in base.attributes and base.attributes[key] == value:
      continue
    newset[key] = value
  if len(newset) == 0:
    return base
  for k, v in base.attributes:
    if k not in newset:
      newset[k] = v
  result = TextAttributeSet()
  result.attributes = newset
  return result
 
class TextElement(ParagraphElement):
  text : str = ""
  style: TextAttributeSet
  
  def __init__(self) -> None:
    self.text = ""
    self.style = TextAttributeSet()
  
  def __init__(self, content: str) -> None:
    self.text = content
    self.style = TextAttributeSet()
  
  def __init__(self, content: str, style: TextAttributeSet) -> None:
    self.text = content
    self.style = style
    
  def __str__(self) -> str:
    result: str = self.text
    if self.style.italic():
      result = "_" + result + "_"
    if self.style.bold():
      result = "**" + result + "**"
    if self.style.has_nonzero_sizelevel() or self.style.has_text_color() or self.style.has_background_color():
      property_list = []
      if self.style.has_nonzero_sizelevel():
        property_list.append(str(self.style.size_level()))
      if self.style.has_text_color():
        property_list.append(str(self.style.text_color()))
      if self.style.has_background_color():
        property_list.append("B"+str(self.style.background_color()))
      property_str = ",".join(property_list)
      result = "<" + property_str + ">" + result + "</" + property_str + ">"
    return result
  
  def dump(self, indent: int = 0):
    print(self.__str__(), end="")

class ImageElement(ParagraphElement):
  image : PIL.Image
  
  def __init__(self) -> None:
    pass

class DocumentModel:
  paragraph_list : typing.List[Paragraph] = []

  def __init__(self) -> None:
    self.paragraph_list = []
  
  def addParagraph(self, p : Paragraph) -> None:
    self.paragraph_list.append(p)
  
  def __str__(self) -> str:
    result = ""
    for p in self.paragraph_list:
      result += p.__str__()
      result += "\n"
    return result
  
  def dump(self, indent: int = 0):
    if (len(self.paragraph_list) == 0):
      print("[]", end="")
      return
    
    print("[", end="")
    isFirst: bool = True
    for paragraph in self.paragraph_list:
      if (isFirst):
        isFirst = False
      else:
        print(",", end="")
      print("\n" + "  "*(indent+1), end="")
      paragraph.dump(indent+1)
    print("\n" + "  "*indent + "]", end="")
