# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# Most of the code in this file is deprecated
# pylint: skip-file

from __future__ import annotations
import mimetypes
import os, io, gc
import pathlib
import typing
import functools
import tempfile
import enum

import bidict
import PIL.Image
import pydub

class Color:
  """!
  @~english @brief %Color tuple with <r,g,b,a> all in range [0, 255]
  @~chinese @brief <r, g, b, a> 格式的代表颜色的元组。所有项都在 [0, 255] 区间
  """
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

  ##
  # @~english @brief Map of predefined color names to values. %Color names can be passed to Color.get()
  # @~chinese @brief 预设颜色到对应值的表。可在调用 Color.get() 时提供颜色名。
  #
  PredefinedColorMap = {
    "transparent": (0,0,0,0),
    "red":   (255,  0,    0,    255),
    "green": (0,    255,  0,    255),
    "blue":  (0,    0,    255,  255),
    "white": (255,  255,  255,  255),
    "black": (0,    0,    0,    255)
  }
  PredefinedColorLanguageMap : typing.ClassVar[list[tuple[str, tuple[str, ...]]]] = [
    ("transparent", ("透明",)),
    ("red",         ("红色",)),
    ("green",       ("绿色",)),
    ("blue",        ("蓝色",)),
    ("white",       ("白色",)),
    ("black",       ("黑色",)),
  ]
  PredefinedColorAliasDict : typing.ClassVar[dict[str,str]] = {}
  for t in PredefinedColorLanguageMap:
    cname, aliastuple = t
    assert cname in PredefinedColorMap
    for alias in aliastuple:
      PredefinedColorAliasDict[alias] = cname

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

  def get_string(self) -> str:
    result = "#" + '{:02x}'.format(self.r) + '{:02x}'.format(self.g) + '{:02x}'.format(self.b)
    if self.a != 255:
      result += '{:02x}'.format(self.a)
    return result

  def __str__(self) -> str:
    return self.get_string()

  @staticmethod
  def get(src: typing.Any):
    """!
    @~english @brief Try to get a color from a value (a string or color tuple)
    @~chinese @brief 用参数(一个字符串或是元组)构造一个颜色值
    @~

    <details open><summary>English(en)</summary>
    Returns a Color from one of the following argument:
    <ul>
      <li>str: "#rrggbb", "#rrggbbaa", or any predefined color names from PredefinedColorMap</li>
      <li>tuple: (r,g,b) or (r,g,b,a)
    </ul>
    This function raises AttributeError exception if the argument is not in any of the form above.
    </details>

    <details open><summary>中文(zh)</summary>
    用来创建颜色的参数必须是以下任意一种形式:
    <ul>
      <li>str (字符串): "#rrggbb", "#rrggbbaa", 或者任意在 PredefinedColorMap 中的预设颜色名称</li>
      <li>tuple (元组): (r,g,b) or (r,g,b,a)
    </ul>
    如果参数不符合要求，则抛出 AttributeError 异常。
    </details>
    """
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
      elif src in Color.PredefinedColorAliasDict:
        cname = Color.PredefinedColorAliasDict[src]
        t = Color.PredefinedColorMap[cname]
        r = t[0]
        g = t[1]
        b = t[2]
        a = t[3]
    elif isinstance(src, tuple):
      if len(src) >= 3 and len(src) <= 4:
        r = src[0]
        g = src[1]
        b = src[2]
        if len(src) == 4:
          a = src[3]
      else:
        raise AttributeError("Not a color: " + str(src))
    else:
      raise AttributeError("Not a color: " + str(src))
    return Color(r, g, b, a)

  def to_tuple(self):
    if self.a == 255:
      return (self.r, self.g, self.b)
    return (self.r, self.g, self.b, self.a)

class TextAttribute(enum.Enum):
  # we only define TextAttribute without TextFragment because VNModel and InputModel permits different text fields
  # text attributes without associated data
  Bold = enum.auto()
  Italic = enum.auto()

  # text attributes with data
  Hierarchy = enum.auto() # data: int representing the "level" of text; 0: normal text; 1: title; 2: Header1; 3: Header2; ... UPDATE: this will be dropped
  Size = enum.auto() # data: int representing size change; 0 is no change, + means increase size, - means decrease size; see preppipe.util.FontSizeConverter for more details

  TextColor = enum.auto() # data: foreground color
  BackgroundColor = enum.auto() # data: background color (highlight color)
  FontConstraint = enum.auto() # RESERVED: we currently do not handle font families or font language tag. we will try to address this later on

  # 提供比较运算符，这样可以把它们和值一起放到元组里排序
  def __lt__(self, rhs : TextAttribute) -> bool:
    if self.__class__ is rhs.__class__:
      return self.value < rhs.value
    raise NotImplementedError("无法将文本属性与其他类型的值进行比较")

class MessageImportance(enum.Enum):
  Error = enum.auto()
  CriticalWarning = enum.auto()
  Warning = enum.auto()
  Info = enum.auto()

class MessageHandler:
  _instance = None

  @staticmethod
  def install_message_handler(handler):
    # subclass MessageHandler and call this function to install the handler
    assert isinstance(handler, MessageHandler)
    MessageHandler._instance = handler

  def message(self, importance : MessageImportance, msg : str, file : str = "", location: str = ""):
    # usually the location string contains the file path
    # use location if available
    locstring = ""
    if len(location) > 0:
      locstring = location
    elif len(file) > 0:
      locstring = file

    if len(locstring) > 0:
      locstring = ' ' + locstring + ': '

    print("[{imp}]{loc}{msg}".format(imp=str(importance), loc=locstring, msg=msg))

  @staticmethod
  def get():
    if MessageHandler._instance is None:
      MessageHandler._instance = MessageHandler()
    return MessageHandler._instance

  @staticmethod
  def info(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageImportance.Info, msg, file, location)

  @staticmethod
  def warning(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageImportance.Warning, msg, file, location)

  @staticmethod
  def critical_warning(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageImportance.CriticalWarning, msg, file, location)

  @staticmethod
  def error(msg : str, file : str = "", location: str = ""):
    MessageHandler.get().message(MessageImportance.Error, msg, file, location)
