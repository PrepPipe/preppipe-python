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

@IROperationDataclass
@IRObjectJsonTypeName("placeholder_image_export_op_symbol")
class PlaceholderImageExportOpSymbol(CacheableOperationSymbol):
  export_path : OpOperand[StringLiteral]
  placeholder : OpOperand[PlaceholderImageLiteralExpr]

  def get_export_file_list(self) -> list[str]:
    return [self.export_path.get().value]

  @classmethod
  def cls_prepare_export(cls, tp : concurrent.futures.ThreadPoolExecutor) -> None:
    # 尝试载入一下字体
    AssetManager.get_font()

  def run_export(self, output_rootdir : str) -> None:
    # 执行这个操作的导出，output_rootdir 是输出根目录
    # 一般会在一个新的线程中执行这个操作
    v = self.placeholder.get()
    img = PlaceholderImageExportOpSymbol.get_image(v)
    relpath = self.export_path.get().value
    fullpath = os.path.join(output_rootdir, relpath)
    os.makedirs(os.path.dirname(fullpath), exist_ok=True)
    img.save(fullpath, format='PNG')

  @staticmethod
  def create(context : Context, v : PlaceholderImageLiteralExpr, path : StringLiteral):
    name = "PlaceholderImageExportOpSymbol" + "[" + path.get_string() + "]" + str(v)
    return PlaceholderImageExportOpSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, export_path=path, placeholder=v, name=name)

  @staticmethod
  def get_starting_font_point_size(width : int, height : int) -> int:
    return int(width*0.75)

  @staticmethod
  def get_font_for_text_image(fontsize : int) -> PIL.ImageFont.ImageFont | PIL.ImageFont.FreeTypeFont:
    return AssetManager.get_font(fontsize)

  @staticmethod
  def get_image(v : PlaceholderImageLiteralExpr) -> PIL.Image.Image:
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
    font = PlaceholderImageExportOpSymbol.get_font_for_text_image(curfontsize)
    center = ((left+right)/2, (top+bottom)/2)
    while True:
      bbox = draw.textbbox(center, text=text, font=font, align='center', anchor="mm", stroke_width=strokewidth)
      if bbox[0] > 0 and bbox[1] > 0 and bbox[2] < width and bbox[3] < height:
        break
      next_size = int(curfontsize * 0.9)
      if next_size == curfontsize or next_size == 0:
        break
      curfontsize = next_size
      font = PlaceholderImageExportOpSymbol.get_font_for_text_image(curfontsize)
    draw.text(center, text=text, font=font, fill=fg_color, align='center', anchor="mm", stroke_width=strokewidth, stroke_fill=stroke_color)
    return img
