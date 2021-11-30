#!/usr/bin/env python3

import typing
import PIL.Image
import importlib
import hashlib
from enum import Enum

import preppipe.commontypes

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
    
  def empty(self) -> bool:
    return (len(self.element_list) == 0)

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
  
  def text_color(self) -> preppipe.commontypes.Color:
    if TextAttribute.TextColor in self.attributes:
      return self.attributes[TextAttribute.TextColor]
    return preppipe.commontypes.Color()
  
  def background_color(self) -> str:
    if TextAttribute.BackgroundColor in self.attributes:
      return self.attributes[TextAttribute.BackgroundColor]
    return preppipe.commontypes.Color()
  
  def has_text_color(self) -> bool:
    return TextAttribute.TextColor in self.attributes
  
  def has_background_color(self) -> bool:
    return TextAttribute.BackgroundColor in self.attributes
  
  def set_text_color(self, color: preppipe.commontypes.Color) -> None:
    if color.transparent():
      self.attributes.pop(TextAttribute.TextColor, None)
    else:
      self.attributes[TextAttribute.TextColor] = color
  
  def set_background_color(self, color: preppipe.commontypes.Color) -> None:
    if color.transparent():
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
    
  def getText(self) -> str:
    return self.text
  
  def getStyle(self) -> TextAttributeSet:
    return self.style

class ImageData:
  index : int
  image: typing.Any
  checksum_md5: str
  
  def __init__(self, index : int, img: typing.Any) -> None:
    self.index = index
    self.image = img
    self.checksum_md5 = hashlib.md5(self.image.tobytes()).hexdigest()
  
  def __str__(self) -> str:
    result = "<#" + str(self.index) + " " + str(self.image.format) + str(self.image.size) + " MD5: " + self.checksum_md5 + ">"
    return result
  
  def show(self) -> None:
    try:
      plt = importlib.import_module("matplotlib.pyplot") # do a testing first
    except:
      print("Image dump require matplotlib.pyplot package but the package import failed. Please ensure you have it installed.")
      return
    plt.imshow(self.image)
    plt.show()

  def __eq__(self, other: object) -> bool:
    if self.checksum_md5 != other.checksum_md5:
      return False
    return (self.image.tobytes() == other.image.tobytes())

class ImageReferenceElement(ParagraphElement):
  imageref : ImageData
  
  def __init__(self, img : ImageData) -> None:
    self.imageref = img
  
  def __str__(self) -> str:
    return self.imageref.__str__()
  
  def show(self) -> None:
    self.imageref.show()

class DocumentModel:
  paragraph_list : typing.List[Paragraph] = []
  image_dict : typing.Dict[int, ImageData] = {}
  image_md5_dict : typing.Dict[str, typing.List[int]] = {}

  def __init__(self) -> None:
    self.paragraph_list = []
  
  def registerImage(self, image) -> ImageData :
    id = len(self.image_dict)
    data = ImageData(id, image)
    md5 = data.checksum_md5
    if md5 in self.image_md5_dict:
      lst = self.image_md5_dict[md5]
      for otherID in lst:
        other = self.image_dict[otherID]
        if data == other:
          del data
          return other
      lst.append(id)
    else:
      self.image_md5_dict[md5] = id
    self.image_dict[id] = data
    return data
  
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
