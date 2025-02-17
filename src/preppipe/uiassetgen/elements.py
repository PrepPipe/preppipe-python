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
  # 文字元素，锚点在左上角（可能文字顶部离锚点还有段距离）
  # 具体锚点位置是 https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html#text-anchors 中的 la
  # 如果要对同一张图做不同语言的版本，应该有不同的 UIAssetTextElementOp
  fontpath : OpOperand[StringLiteral] # 如果为空就用默认字体
  fontindex : OpOperand[IntLiteral]
  fontsize : OpOperand[IntLiteral]
  fontcolor : OpOperand[ColorLiteral]
  text : OpOperand[StringLiteral]

  @staticmethod
  def create(context : Context, text : StringLiteral | str, fontsize : IntLiteral | int, fontcolor : ColorLiteral | Color, fontpath : StringLiteral | str | None = None, fontindex : IntLiteral | int | None = None):
    text_value = StringLiteral.get(text, context=context) if isinstance(text, str) else text
    fontsize_value = IntLiteral.get(fontsize, context=context) if isinstance(fontsize, int) else fontsize
    fontcolor_value = ColorLiteral.get(fontcolor, context=context) if isinstance(fontcolor, Color) else fontcolor
    fontpath_value = StringLiteral.get(fontpath, context=context) if isinstance(fontpath, str) else fontpath
    fontindex_value = IntLiteral.get(fontindex, context=context) if isinstance(fontindex, int) else fontindex
    return UIAssetTextElementOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, fontpath=fontpath_value, fontindex=fontindex_value, fontsize=fontsize_value, fontcolor=fontcolor_value, text=text_value)

  def get_font(self) -> PIL.ImageFont.FreeTypeFont | PIL.ImageFont.ImageFont:
    size = self.fontsize.get().value
    index = 0
    if index_l := self.fontindex.try_get_value():
      index = index_l.value
    if path := self.fontpath.try_get_value():
      return PIL.ImageFont.truetype(path.value, index=index, size=size)
    return AssetManager.get_font(fontsize=size)

  def get_bbox_impl(self, font : PIL.ImageFont.FreeTypeFont | PIL.ImageFont.ImageFont) -> tuple[int, int, int, int]:
    font = self.get_font()
    s = self.text.get().value
    if isinstance(font, PIL.ImageFont.FreeTypeFont):
      left, top, right, bottom = font.getbbox(s, anchor='la')
      return (math.floor(left), math.floor(top), math.ceil(right), math.ceil(bottom))
    elif isinstance(font, PIL.ImageFont.ImageFont):
      return font.getbbox(s)
    else:
      raise PPInternalError(f'Unexpected type of font: {type(font)}')

  def get_bbox(self) -> tuple[int, int, int, int]:
    return self.get_bbox_impl(self.get_font())

  def draw(self, drawctx : UIAssetDrawingContext) -> UIAssetElementDrawingData:
    font = self.get_font()
    s = self.text.get().value
    left, top, right, bottom = self.get_bbox_impl(font)
    width = right - left
    height = bottom - top
    color = self.fontcolor.get().value
    image = PIL.Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(image)
    draw.text((-left, -top), s, font=font, fill=color.to_tuple(), anchor='la')
    print(f"Original bbox: {left}, {top}, {right}, {bottom}; actual bbox: {str(image.getbbox())}")
    description = "<default_font>"
    if path := self.fontpath.try_get_value():
      description = path.value
    if index_l := self.fontindex.try_get_value():
      index = index_l.value
      if index != 0:
        description += f"#{index}"
    description += ", size=" + str(self.fontsize.get().value)
    return UIAssetElementDrawingData(image=image, description=description, anchor=(-left, -top))

@dataclasses.dataclass
class UIAssetLineLoopDrawingData(UIAssetElementDrawingData):
  # 除了基类的属性外，我们在这还存储描述边框的信息
  mask_interior : PIL.Image.Image | None = None # L （灰度）模式的图片，非零的部分表示内部（用于区域填充等），可作为 alpha 通道

  def sanity_check(self):
    sized_image_list = []
    if self.image is not None:
      sized_image_list.append(self.image)
    if self.mask_interior is not None:
      if not isinstance(self.mask_interior, PIL.Image.Image):
        raise PPInternalError(f'Unexpected type of mask_interior: {type(self.mask_interior)}')
      if self.mask_interior.mode != 'L':
        raise PPInternalError(f'Unexpected mode of mask_interior: {self.mask_interior.mode}')
    if len(sized_image_list) > 1:
      size = sized_image_list[0].size
      for image in sized_image_list[1:]:
        if image.size != size:
          raise PPInternalError(f'Inconsistent image size: {image.size} and {size}')


@IROperationDataclassWithValue(UIAssetElementType)
class UIAssetLineLoopOp(UIAssetElementNodeOp):
  # 用于描述一条或多条线段组成的闭合区域
  # 由于大部分情况下我们有更简单的表示（比如就一个矩形），该类只作为基类，不应该直接使用
  def draw(self, drawctx : UIAssetDrawingContext) -> UIAssetLineLoopDrawingData:
    return UIAssetLineLoopDrawingData()

@IROperationDataclassWithValue(UIAssetElementType)
class UIAssetRectangleOp(UIAssetLineLoopOp):
  width : OpOperand[IntLiteral]
  height : OpOperand[IntLiteral]

  def get_bbox(self) -> tuple[int, int, int, int]:
    return (0, 0, self.width.get().value, self.height.get().value)

  def draw(self, drawctx : UIAssetDrawingContext) -> UIAssetLineLoopDrawingData:
    result = UIAssetLineLoopDrawingData()
    result.mask_interior = PIL.Image.new('L', (self.width.get().value, self.height.get().value), 255)
    return result

  @staticmethod
  def create(context : Context, width : IntLiteral | int, height : IntLiteral | int):
    width_value = IntLiteral.get(width, context=context) if isinstance(width, int) else width
    height_value = IntLiteral.get(height, context=context) if isinstance(height, int) else height
    return UIAssetRectangleOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, width=width_value, height=height_value)

class UIAssetAreaFillMode(enum.Enum):
  COLOR_FILL = enum.auto() # 单色填充

@IROperationDataclassWithValue(UIAssetElementType)
class UIAssetAreaFillElementOp(UIAssetElementNodeOp):
  # 区域填充
  # TODO 添加渐变填充等功能

  boundary : OpOperand[UIAssetLineLoopOp]
  mode : OpOperand[EnumLiteral[UIAssetAreaFillMode]]
  color1 : OpOperand[ColorLiteral]
  color2 : OpOperand[ColorLiteral] # 目前不用

  @staticmethod
  def create(context : Context, boundary : UIAssetLineLoopOp, mode : UIAssetAreaFillMode, color1 : ColorLiteral | Color, color2 : ColorLiteral | Color | None = None):
    mode_value = EnumLiteral.get(value=mode, context=context)
    color1_value = ColorLiteral.get(color1, context=context) if isinstance(color1, Color) else color1
    color2_value = ColorLiteral.get(color2, context=context) if isinstance(color2, Color) else color2
    return UIAssetAreaFillElementOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, boundary=boundary, mode=mode_value, color1=color1_value, color2=color2_value)

  def get_bbox(self) -> tuple[int, int, int, int] | None:
    return self.boundary.get().get_bbox()

  def draw(self, drawctx : UIAssetDrawingContext) -> UIAssetElementDrawingData:
    boundary = self.boundary.get()
    boundary_data, _ = drawctx.get_drawing_data(boundary)
    if not isinstance(boundary_data, UIAssetLineLoopDrawingData):
      raise PPInternalError(f'Unexpected type of boundary_data: {type(boundary_data)}')
    if boundary_data.mask_interior is None:
      raise PPInternalError('Boundary mask_interior is None')
    match self.mode.get().value:
      case UIAssetAreaFillMode.COLOR_FILL:
        color = self.color1.get().value
        result = UIAssetLineLoopDrawingData()
        result.image = PIL.Image.new('RGBA', boundary_data.mask_interior.size, (0, 0, 0, 0))
        draw = PIL.ImageDraw.Draw(result.image)
        draw.bitmap((0, 0), boundary_data.mask_interior, fill=color.to_tuple())
        result.description = f'ColorFill({color.get_string()})'
        return result
      case _:
        raise PPNotImplementedError()