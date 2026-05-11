# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
import os
import concurrent.futures
import PIL
import PIL.Image
import PIL.ImageDraw

from ..irbase import *
from ..exportcache import CacheableOperationSymbol
from ..imageexpr import *
from ..commontypes import *
from ..irdataop import *
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
    # 固定 PNG 编码参数，便于同一输入在各平台得到一致字节（便于校验与用户资源不应被无端改写的原则）
    img.save(fullpath, format="PNG", compress_level=9, optimize=False)

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
    pass

  @classmethod
  def get_image(cls, v : PlaceholderImageLiteralExpr) -> PIL.Image.Image:
    # 基础设置
    bg_color = (192, 192, 192, 255) # 灰色背景
    fg_color = (255, 255, 255, 255) # 白色前景
    stroke_color = (0, 0, 0, 255) # 黑色描边
    linewidth = 3

    width, height = v.size.value
    img = PIL.Image.new('RGBA', (width, height), (0, 0, 0, 0))

    # 在 bbox 区域画一个描边的叉
    left, top, right, bottom = v.bbox.value
    draw = PIL.ImageDraw.Draw(img)

    draw.rectangle((0, 0, width, height), fill=None, outline=stroke_color, width=linewidth)
    draw.rectangle((left, top, right, bottom), fill=bg_color, outline=fg_color, width=linewidth)
    draw.line((left, top, right, bottom), fill=fg_color, width=linewidth)
    draw.line((left, bottom, right, top), fill=fg_color, width=linewidth)

    # 不在位图中绘制描述文字：字体与 FreeType 版本会导致同一占位图在不同机器上 PNG 字节不一致。
    # 描述仍保留在 PlaceholderImageLiteralExpr / Ren'Py 脚本侧；导出像素仅由尺寸与 bbox 决定，跨平台稳定。
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
