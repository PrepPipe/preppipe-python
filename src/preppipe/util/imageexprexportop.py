# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
import os
import concurrent.futures
import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from ..irbase import *
from ..exportcache import CacheableOperationSymbol
from ..imageexpr import *
from ..commontypes import *
from ..irdataop import *
from ..assets.assetmanager import AssetManager

ImageExprType = typing.TypeVar('ImageExprType', bound=BaseImageLiteralExpr)

@IROperationDataclass
class ImageExprExportOpSymbolBase(CacheableOperationSymbol, typing.Generic[ImageExprType]):
  export_path : OpOperand[StringLiteral]
  expr : OpOperand[ImageExprType]

  def get_export_file_list(self) -> list[str]:
    return [self.export_path.get().value]

  def run_export(self, output_rootdir : str) -> None:
    # 执行这个操作的导出，output_rootdir 是输出根目录
    # 一般会在一个新的线程中执行这个操作
    v = self.expr.get()
    img = self.get_image(v)
    relpath = self.export_path.get().value
    fullpath = os.path.join(output_rootdir, relpath)
    os.makedirs(os.path.dirname(fullpath), exist_ok=True)
    img.save(fullpath, format='PNG')

  @classmethod
  def get_image(cls, v : ImageExprType) -> PIL.Image.Image:
    raise PPNotImplementedError()

  @classmethod
  def create(cls, context : Context, v : ImageExprType, path : StringLiteral | str):
    if isinstance(path, str):
      path = StringLiteral.get(value=path, context=context)
    name = cls.__name__ + "[" + path.get_string() + "]" + str(v)
    return cls(init_mode=IRObjectInitMode.CONSTRUCT, context=context, export_path=path, expr=v, name=name)

@IROperationDataclass
@IRObjectJsonTypeName("placeholder_image_export_op_symbol")
class PlaceholderImageExportOpSymbol(ImageExprExportOpSymbolBase[PlaceholderImageLiteralExpr]):
  @classmethod
  def cls_prepare_export(cls, tp : concurrent.futures.ThreadPoolExecutor) -> None:
    # 尝试载入一下字体
    AssetManager.get_font()

  @staticmethod
  def get_starting_font_point_size(width : int, height : int) -> int:
    return int(width*0.75)

  @classmethod
  def get_image(cls, v : PlaceholderImageLiteralExpr) -> PIL.Image.Image:
    # 基础设置
    bg_color = (192, 192, 192, 255) # 灰色背景
    fg_color = (255, 255, 255, 255) # 白色前景
    stroke_color = (0, 0, 0, 255) # 黑色描边
    linewidth = 3
    strokewidth = 3

    width, height = v.size.value
    img = PIL.Image.new('RGBA', (width, height), (0, 0, 0, 0))

    # 在 bbox 区域画一个描边的叉
    left, top, right, bottom = v.bbox.value
    draw = PIL.ImageDraw.Draw(img)

    draw.rectangle((0, 0, width, height), fill=None, outline=stroke_color, width=linewidth)
    draw.rectangle((left, top, right, bottom), fill=bg_color, outline=fg_color, width=linewidth)
    draw.line((left, top, right, bottom), fill=fg_color, width=linewidth)
    draw.line((left, bottom, right, top), fill=fg_color, width=linewidth)

    # 准备把描述文本画上去
    text = v.description.get_string()
    curfontsize = PlaceholderImageExportOpSymbol.get_starting_font_point_size(width, height)
    font = AssetManager.get_font(curfontsize)
    center = ((left+right)/2, (top+bottom)/2)
    while True:
      bbox = draw.textbbox(center, text=text, font=font, align='center', anchor="mm", stroke_width=strokewidth)
      if bbox[0] > 0 and bbox[1] > 0 and bbox[2] < width and bbox[3] < height:
        break
      next_size = int(curfontsize * 0.9)
      if next_size == curfontsize or next_size == 0:
        break
      curfontsize = next_size
      font = AssetManager.get_font(curfontsize)
    draw.text(center, text=text, font=font, fill=fg_color, align='center', anchor="mm", stroke_width=strokewidth, stroke_fill=stroke_color)
    return img

@IROperationDataclass
@IRObjectJsonTypeName("color_image_export_op_symbol")
class ColorImageExportOpSymbol(ImageExprExportOpSymbolBase[ColorImageLiteralExpr]):
  @classmethod
  def get_image(cls, v : ColorImageLiteralExpr) -> PIL.Image.Image:
    width, height = v.size.value
    color_tuple = v.color.value.to_tuple()
    img = PIL.Image.new("RGB" if len(color_tuple) == 3 else "RGBA", (width, height), color_tuple)
    return img
