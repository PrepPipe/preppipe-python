# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
import enum
import math
import PIL
import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw
from .base import *
from ..assets.assetmanager import *

# 该文件定义了 UI 素材生成中所用到的元素类型（直接用于画图的底层）

@IROperationDataclassWithValue(UIAssetElementType)
class UIAssetTextElementOp(UIAssetElementNodeOp):
  # 文字元素
  # 如果要对同一张图做不同语言的版本，应该有不同的 UIAssetTextElementOp
  fontpath : OpOperand[StringLiteral] # 如果为空就用默认字体
  fontindex : OpOperand[IntLiteral]
  fontsize : OpOperand[IntLiteral]
  fontcolor : OpOperand[ColorLiteral]
  text : OpOperand[StringLiteral]

  def get_font(self) -> PIL.ImageFont.FreeTypeFont | PIL.ImageFont.ImageFont:
    size = self.fontsize.get().value
    index = 0
    if index_l := self.fontindex.get():
      index = index_l.value
    if path := self.fontpath.get().value:
      return PIL.ImageFont.truetype(path, index=index, size=size)
    return AssetManager.get_font(fontsize=size)

  def get_bbox(self) -> tuple[int, int, int, int]:
    font = self.get_font()
    s = self.text.get().value
    left, top, right, bottom = font.getbbox(s)
    return (math.floor(left), math.floor(top), math.ceil(right), math.ceil(bottom))

  def draw(self, drawctx : UIAssetDrawingContext) -> UIAssetElementDrawingData:
    font = self.get_font()
    s = self.text.get().value
    left, top, right, bottom = font.getbbox(s)
    left = math.floor(left)
    top = math.floor(top)
    right = math.ceil(right)
    bottom = math.ceil(bottom)
    width = right - left
    height = bottom - top
    color = self.fontcolor.get().value
    image = PIL.Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(image)
    draw.text((-left, -top), s, font=font, fill=color.to_tuple())
    description = "<default_font>"
    if path := self.fontpath.get().value:
      description = path
    if index_l := self.fontindex.get():
      index = index_l.value
      if index != 0:
        description += f"#{index}"
    description += ", size=" + str(self.fontsize.get().value)
    return UIAssetElementDrawingData(image=image, description=description, anchor=(left, top))

@IROperationDataclassWithValue(UIAssetElementType)
class UIAssetLineLoopOp(UIAssetElementNodeOp):
  pass

class UIAssetAreaFillMode(enum.Enum):
  COLOR_FILL = enum.auto() # 单色填充

@IROperationDataclassWithValue(UIAssetElementType)
class UIAssetAreaFillElementOp(UIAssetElementNodeOp):
  # 区域填充
  # TODO 添加渐变填充等功能

  mode : OpOperand[EnumLiteral[UIAssetAreaFillMode]]
  color1 : OpOperand[ColorLiteral]
  color2 : OpOperand[ColorLiteral] # 目前不用
