#!/usr/bin/env python3

import typing
from enum import Enum

class Color:
  """Uniformed representation; r,g,b,a all in range [0, 255]"""
  r : int = 0
  g : int = 0
  b : int = 0
  a : int = 255
  
  def __init__(self, r : int = 0, g: int = 0, b: int = 0, a: int = 255) -> None:
    self.r = r
    self.g = g
    self.b = b
    self.a = a
    self.validate()
  
  PredefinedColorMap = {
    "transparent": (0,0,0,0),
    "red":   (255,  0,    0,    255),
    "green": (0,    255,  0,    255),
    "blue":  (0,    0,    255,  255),
    "white": (255,  255,  255,  255),
    "black": (0,    0,    0,    255)
  }
  
  def red(self) -> int:
    return self.r
  
  def green(self) -> int:
    return self.g
  
  def blue(self) -> int:
    return self.b
  
  def alpha(self) -> int:
    return self.a
  
  def transparent(self) -> bool:
    return self.a == 0
  
  def validate(self) -> None:
    if self.r < 0 or self.r > 255:
      raise AttributeError("Color.r (" + str(self.r) + ") out of range [0, 255]")
    if self.g < 0 or self.g > 255:
      raise AttributeError("Color.g (" + str(self.g) + ") out of range [0, 255]")
    if self.b < 0 or self.b > 255:
      raise AttributeError("Color.b (" + str(self.b) + ") out of range [0, 255]")
    if self.a < 0 or self.a > 255:
      raise AttributeError("Color.a (" + str(self.a) + ") out of range [0, 255]")
  
  def getString(self) -> str:
    result = "#" + '{:02x}'.format(self.r) + '{:02x}'.format(self.g) + '{:02x}'.format(self.b)
    if self.a != 255:
      result += '{:02x}'.format(self.a)
    return result

  def __str__(self) -> str:
    return self.getString()
  
  def get(src: typing.Any):
    r = 0
    g = 0
    b = 0
    a = 255
    if isinstance(src, str):
      if src.startswith("#"):
        if len(src) >= 7:
          r = int(src[1:3], 16)
          g = int(src[3:5], 16)
          b = int(src[5:7], 16)
        if len(src) == 9:
          a = int(src[7:9], 16)
        elif len(src) != 7:
          raise AttributeError("Not a color: " + src)
      elif src in Color.PredefinedColorMap:
        t = Color.PredefinedColorMap[src]
        r = t[0]
        g = t[1]
        b = t[2]
        a = t[3]
    else:
      raise AttributeError("Not a color: " + src)
    return Color(r, g, b, a)
  
  def to_tuple(self):
    if self.a == 255:
      return (self.r, self.g, self.b)
    return (self.r, self.g, self.b, self.a)
  

class FileType(Enum):
  Text = 0  # both plain text and markdown / rich text
  HTML = 1
  Image = 2
  Document = 3
  Presentation = 4
  Spreadsheet = 5
