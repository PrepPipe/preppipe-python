# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
from .irbase import *

# 此文件定义了一系列对于图片的操作以及能满足后端演出等实际需求的图片结点类型
# IRBase 中所有的素材(AssetData)都被要求不带除格式之外的元数据，在这里我们的类型将以 LiteralExpr/ConstExpr 的形式引用它们并添加元数据

# 图片有两类：
# 1.  单层图片：不带标签，只有一种外观。内容表示上等效于一个普通的图片文件。
# 2.  多层图片：由一组图层构成，每个图层有一个独特的名称（字符串）并且图层有顺序（从下到上）。若要转化成普通图片则需要使用转换的表达式，提供一个图层掩码来确定哪些图层需要显示。等效于一个PSD文件。

# 所有的图片、图层都满足以下条件：
# 1.  有一个像素值的大小
# 2.  有一个锚点(anchor)，在图片中的浮点坐标(0-1)
# 3.  所有的图片都假设有RGBA四通道。如果没有的话，语义上它们会被拓展为这样的图片。

# 在其他IR中，后续使用多层图片时可能还需要如下信息：
#     (1) 至少一组属性，每个属性有一个属性名(n_a, 字符串)和一串属性值(v_a, 字符串)，每个属性值有一串图层编码 m_l （字符串组）来决定哪些图层应该显示。每个属性都有个默认属性值。
#     (2) 零或多个预设值 preset，每个预设值映射到一组属性值
# 因为这些信息不影响图片的展示，并且名称可能影响到图片值的唯一性，以上这些信息应该在其他IR中另外提供

# TODO 目前只定义了基础的图片源类型，没有定义图像操作（如重叠、剪裁等），早晚得做

@IRObjectJsonTypeName('base_image_le')
class BaseImageLiteralExpr(LiteralExpr):
  # this is abstract
  def construct_init(self, *, context : Context, value_tuple: tuple[Literal, ...], **kwargs) -> None:
    # value 0 is specific to the image
    # value 1 is the size
    # value 2 is the anchor
    return super().construct_init(ty=ImageType.get(context), value_tuple=value_tuple, **kwargs)

  @property
  def size(self) -> IntTupleLiteral:
    return self.get_value_tuple()[1] # type: ignore

  @property
  def anchor(self) -> FloatTupleLiteral:
    return self.get_value_tuple()[2] # type: ignore

  @staticmethod
  def _validate_size_and_anchor(size : IntTupleLiteral, anchor : FloatTupleLiteral) -> None:
    assert isinstance(size, IntTupleLiteral)
    for v in size.value:
      assert v > 0
    assert isinstance(anchor, FloatTupleLiteral)
    for v in anchor.value:
      assert v >= 0 and v <= 1.0

@IRObjectJsonTypeName('image_asset_le')
class ImageAssetLiteralExpr(BaseImageLiteralExpr):
  # 该图片是由 ImageAssetData 而来的
  @property
  def image(self) -> ImageAssetData:
    return self.get_value_tuple()[0] # type: ignore

  @staticmethod
  def get(context : Context, image : ImageAssetData, size : IntTupleLiteral, anchor : FloatTupleLiteral) -> ImageAssetLiteralExpr:
    assert isinstance(image, ImageAssetData)
    BaseImageLiteralExpr._validate_size_and_anchor(size, anchor)
    return ImageAssetLiteralExpr._get_literalexpr_impl((image, size, anchor), context)

@IRObjectJsonTypeName('color_image_le')
class ColorImageLiteralExpr(BaseImageLiteralExpr):
  # 该图片是个纯色图片
  @property
  def color(self) -> ColorLiteral:
    return self.get_value_tuple()[0] # type: ignore

  @staticmethod
  def get(context : Context, color : ColorLiteral, size : IntTupleLiteral, anchor : FloatTupleLiteral) -> ColorImageLiteralExpr:
    assert isinstance(color, ColorLiteral)
    BaseImageLiteralExpr._validate_size_and_anchor(size, anchor)
    return ColorImageLiteralExpr._get_literalexpr_impl((color, size, anchor), context)

@IRObjectJsonTypeName('decl_image_le')
class DeclaredImageLiteralExpr(BaseImageLiteralExpr, AssetDeclarationTrait):
  # 该图片代表一个没有定义只有声明的图片
  # 该图片的定义已存在，不能生成定义
  @property
  def declaration(self) -> StringLiteral:
    return self.get_value_tuple()[0] # type: ignore

  @staticmethod
  def get(context : Context, decl : StringLiteral, size : IntTupleLiteral, anchor : FloatTupleLiteral) -> DeclaredImageLiteralExpr:
    assert isinstance(decl, StringLiteral)
    BaseImageLiteralExpr._validate_size_and_anchor(size, anchor)
    return DeclaredImageLiteralExpr._get_literalexpr_impl((decl, size, anchor), context)

@IRObjectJsonTypeName('placeholder_image_le')
class PlaceholderImageLiteralExpr(BaseImageLiteralExpr, AssetPlaceholderTrait):
  # 该图片代表一个没有定义、需要生成的图片
  @property
  def description(self) -> StringLiteral:
    return self.get_value_tuple()[0] # type: ignore

  @staticmethod
  def get(context : Context, desc : StringLiteral, size : IntTupleLiteral, anchor : FloatTupleLiteral) -> PlaceholderImageLiteralExpr:
    assert isinstance(desc, StringLiteral)
    BaseImageLiteralExpr._validate_size_and_anchor(size, anchor)
    return PlaceholderImageLiteralExpr._get_literalexpr_impl((desc, size, anchor), context)
