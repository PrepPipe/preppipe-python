# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
from .irbase import *
from .language import TranslationDomain
from .util.imagepack import ImagePack, ImagePackDescriptor

# 此文件定义了一系列对于图片的操作以及能满足后端演出等实际需求的图片结点类型
# IRBase 中所有的素材(AssetData)都被要求不带除格式之外的元数据，在这里我们的类型将以 LiteralExpr/ConstExpr 的形式引用它们并添加元数据

# 图片有两类：
# 1.  单层图片：不带标签，只有一种外观。内容表示上等效于一个普通的图片文件。
# 2.  多层图片：由一组图层构成，每个图层有一个独特的名称（字符串）并且图层有顺序（从下到上）。若要转化成普通图片则需要使用转换的表达式，提供一个图层掩码来确定哪些图层需要显示。等效于一个PSD文件。

# 所有的图片、图层都满足以下条件：
# 1.  有一个像素值的大小
# 2.  所有的图片都假设有RGBA四通道。如果没有的话，语义上它们会被拓展为这样的图片。

# 在其他IR中，后续使用多层图片时可能还需要如下信息：
#     (1) 至少一组属性，每个属性有一个属性名(n_a, 字符串)和一串属性值(v_a, 字符串)，每个属性值有一串图层编码 m_l （字符串组）来决定哪些图层应该显示。每个属性都有个默认属性值。
#     (2) 零或多个预设值 preset，每个预设值映射到一组属性值
# 因为这些信息不影响图片的展示，并且名称可能影响到图片值的唯一性，以上这些信息应该在其他IR中另外提供

# TODO 目前只定义了基础的图片源类型，没有定义图像操作（如重叠、剪裁等），早晚得做

TR_imageexpr = TranslationDomain("imageexpr")

@IRObjectJsonTypeName('base_image_le')
class BaseImageLiteralExpr(LiteralExpr):
  # 图片表达式的抽象基类

  # 从此下标开始的数据属于派生类
  DERIVED_DATA_START = 2

  def construct_init(self, *, context : Context, value_tuple: tuple[Literal, ...], **kwargs) -> None:
    # 值 0 是大小，1 是 bbox，其余的值由子类决定意义
    # bbox 是图片非透明部分的 <左, 上, 右, 下> 边界
    # 如果图片完全透明，则为 <0, 0, 0, 0>
    # 如果图片完全不透明，则为 <0, 0, w, h>
    assert isinstance(value_tuple[0], IntTupleLiteral)
    assert isinstance(value_tuple[1], IntTupleLiteral)
    return super().construct_init(ty=ImageType.get(context), value_tuple=value_tuple, **kwargs)

  @property
  def size(self) -> IntTupleLiteral:
    return self.get_value_tuple()[0] # type: ignore

  @property
  def bbox(self) -> IntTupleLiteral:
    return self.get_value_tuple()[1] # type: ignore

  @staticmethod
  def _validate_size(size : IntTupleLiteral) -> None:
    assert isinstance(size, IntTupleLiteral)
    # 有两种情况是允许的：
    # 1. 两个都是0
    # 2. 两个都是正数
    num_zeros = 0
    num_positives = 0
    for v in size.value:
      if v == 0:
        num_zeros += 1
      elif v > 0:
        num_positives += 1
      else:
        raise ValueError("Image size must be non-negative")

  def get_bbox(self) -> tuple[int,int,int,int]:
    left, top, right, bottom = self.bbox.value
    return (left, top, right, bottom)

@IRObjectJsonTypeName('image_asset_le')
class ImageAssetLiteralExpr(BaseImageLiteralExpr):
  # 该图片是由 ImageAssetData 而来的
  @property
  def image(self) -> ImageAssetData:
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START] # type: ignore

  @staticmethod
  def get(context : Context, image : ImageAssetData, size : IntTupleLiteral, bbox : IntTupleLiteral) -> ImageAssetLiteralExpr:
    assert isinstance(image, ImageAssetData)
    BaseImageLiteralExpr._validate_size(size)
    return ImageAssetLiteralExpr._get_literalexpr_impl((size, bbox, image), context)

  @staticmethod
  def prepare_bbox(context : Context, imagedata : PIL.Image.Image) -> IntTupleLiteral:
    bbox = imagedata.getbbox()
    if bbox is None:
      return IntTupleLiteral.get((0, 0, 0, 0), context=context)
    return IntTupleLiteral.get(bbox, context=context)

  def __str__(self) -> str:
    width, height = self.size.value
    return '[' + str(width) + '*' + str(height) + ']' + str(self.image)

@IRObjectJsonTypeName('color_image_le')
class ColorImageLiteralExpr(BaseImageLiteralExpr):
  # 该图片是个纯色图片
  @property
  def color(self) -> ColorLiteral:
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START] # type: ignore

  def __str__(self) -> str:
    width, height = self.size.value
    return self.color.value.get_string() + '[' + str(width) + '*' + str(height) + ']'

  @staticmethod
  def get(context : Context, color : ColorLiteral, size : IntTupleLiteral) -> ColorImageLiteralExpr:
    assert isinstance(color, ColorLiteral)
    BaseImageLiteralExpr._validate_size(size)
    width, height = size.value
    bbox = IntTupleLiteral.get((0, 0, width, height), context=context)
    return ColorImageLiteralExpr._get_literalexpr_impl((size, bbox, color), context)

@IRObjectJsonTypeName('text_image_le')
class TextImageLiteralExpr(BaseImageLiteralExpr):
  # 该图片是一个文本图片，仅由文本内容和字体样式构成
  @property
  def font(self) -> StringLiteral | None:
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START]

  def get_string(self) -> str:
    strlist = []
    for i in range(BaseImageLiteralExpr.DERIVED_DATA_START + 1, len(self.get_value_tuple())):
      strlist.append(self.get_value_tuple()[i].get_string())
    return ''.join(strlist)

  @staticmethod
  def get(context : Context, font : StringLiteral | None, text : TextFragmentLiteral | StringLiteral | str | typing.Iterable[TextFragmentLiteral | StringLiteral | str], size : IntTupleLiteral) -> TextImageLiteralExpr:
    textlist = []
    if isinstance(text, (TextFragmentLiteral, StringLiteral, str)):
      if isinstance(text, str):
        text = StringLiteral.get(text, context=context)
      textlist.append(text)
    else:
      for t in text:
        if isinstance(t, str):
          textlist.append(StringLiteral.get(t, context=context))
        else:
          textlist.append(t)
    BaseImageLiteralExpr._validate_size(size)
    if font is not None:
      if not isinstance(font, StringLiteral):
        raise ValueError("Invalid font value")
    width, height = size.value
    bbox = IntTupleLiteral.get((0, 0, width, height), context=context)
    return TextImageLiteralExpr._get_literalexpr_impl((size, bbox, font, *textlist), context)

@IRObjectJsonTypeName('decl_image_le')
class DeclaredImageLiteralExpr(BaseImageLiteralExpr, AssetDeclarationTrait):
  # 该图片代表一个没有定义只有声明的图片
  # 该图片的定义已存在，不能生成定义
  @property
  def declaration(self) -> StringLiteral:
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START] # type: ignore

  def __str__(self) -> str:
    width, height = self.size.value
    return '[' + str(width) + '*' + str(height) + '] ' + self.declaration.get_string()

  @staticmethod
  def get(context : Context, decl : StringLiteral, size : IntTupleLiteral) -> DeclaredImageLiteralExpr:
    assert isinstance(decl, StringLiteral)
    BaseImageLiteralExpr._validate_size(size)
    width, height = size.value
    bbox = IntTupleLiteral.get((0, 0, width, height), context=context)
    return DeclaredImageLiteralExpr._get_literalexpr_impl((size, bbox, decl), context)

@IRWrappedStatelessClassJsonName("image_placeholder_dest_e")
class ImageExprPlaceholderDest(enum.Enum):
  # 当我们需要生成占位图时，用这个表示该占位图是要占什么位
  # 这样便于在后端选取对应的默认占位图，或者可以在转换中赋予默认的图
  DEST_UNKNOWN             = enum.auto() # 未知用途的占位图
  DEST_CHARACTER_SPRITE    = enum.auto() # 人物立绘
  DEST_CHARACTER_SIDEIMAGE = enum.auto() # 人物头像
  DEST_SCENE_BACKGROUND    = enum.auto() # 场景背景

@IRObjectJsonTypeName('placeholder_image_le')
class PlaceholderImageLiteralExpr(BaseImageLiteralExpr, AssetPlaceholderTrait):
  # 该图片代表一个没有定义、需要生成的图片
  @property
  def description(self) -> StringLiteral:
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START + 1] # type: ignore

  @property
  def dest(self) -> ImageExprPlaceholderDest:
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START].value

  _tr_placeholder_name = TR_imageexpr.tr("placeholder_name",
    en="Placeholder",
    zh_cn="占位图",
    zh_hk="占位圖",
  )

  def __str__(self) -> str:
    width, height = self.size.value
    return '[' + str(width) + '*' + str(height) + '] ' + self._tr_placeholder_name.get() +' ' + self.dest.name + (' ' + self.description.get_string() if len(self.description.get_string()) > 0 else '')

  @staticmethod
  def get(context : Context, dest : ImageExprPlaceholderDest, desc : StringLiteral, size : IntTupleLiteral) -> PlaceholderImageLiteralExpr:
    assert isinstance(dest, ImageExprPlaceholderDest)
    assert isinstance(desc, StringLiteral)
    BaseImageLiteralExpr._validate_size(size)
    destliteral = EnumLiteral.get(context=context, value=dest)
    width, height = size.value
    bbox = IntTupleLiteral.get((0, 0, width, height), context=context)
    return PlaceholderImageLiteralExpr._get_literalexpr_impl((size, bbox, destliteral, desc), context)

@IRObjectJsonTypeName('imagepack_image_le')
class ImagePackElementLiteralExpr(BaseImageLiteralExpr, AssetDeclarationTrait):
  # 该图片是一个图片包中的一个组合
  # 除了基础的图片信息外，还有以下参数：
  # 1. 图片包的名称(ID)
  # 2. 图片包中的组合名称
  # 3. 0-N 个选区参数（图片、颜色或是字符串文本）
  # 如果某个选区参数没有提供，则使用 NullLiteral 代替
  @property
  def pack_id(self) -> StringLiteral:
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START]

  @property
  def composite_name(self) -> StringLiteral:
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START + 1]

  def get_fork_operands(self) -> tuple[ImageAssetData | ColorLiteral | StringLiteral, ...] | None:
    num_operands = len(self.get_value_tuple()) - BaseImageLiteralExpr.DERIVED_DATA_START - 2
    if num_operands == 0:
      return None
    return self.get_value_tuple()[BaseImageLiteralExpr.DERIVED_DATA_START + 2:] # type: ignore

  @staticmethod
  def get(context : Context, pack : str, element : str, size : IntTupleLiteral | None = None, bbox : IntTupleLiteral | None = None, mask_operands : typing.Iterable[ImageAssetData | ColorLiteral | StringLiteral] | None = None):
    # 先检查图片包的基础信息
    descriptor = ImagePack.get_descriptor_by_id(pack)
    if descriptor is None:
      raise PPInternalError("Invalid Imagepack reference: " + pack)
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError("Invalid Imagepack descriptor: " + pack + " (type: " + str(type(descriptor)) + ")")
    if not descriptor.is_valid_composite(element):
      raise PPInternalError("Invalid Imagepack element: " + element)
    # 再处理选区参数
    # 选区参数可以少（用 None 填充）但是不能多
    cur_operands = []
    masks = descriptor.get_masks()
    has_nonnull_operand = False
    if mask_operands is not None:
      for operand in mask_operands:
        index = len(cur_operands)
        if index >= len(masks):
          raise PPInternalError("Too many mask operands")
        cur_operands.append(operand)
        if operand is None:
          # 我们应该使用 NullLiteral 代替 None
          cur_operands[-1] = NullLiteral.get(context=context)
          continue
        # 检查参数类型
        has_nonnull_operand = True
        match masks[index].get_param_type():
          case ImagePackDescriptor.MaskParamType.IMAGE:
            if not isinstance(operand, (ImageAssetData, ColorLiteral, StringLiteral)):
              raise PPInternalError("Invalid mask operand type: " + str(type(operand)))
          case ImagePackDescriptor.MaskParamType.COLOR:
            if not isinstance(operand, ColorLiteral):
              raise PPInternalError("Invalid mask operand type: " + str(type(operand)))
          case _:
            raise PPInternalError("Invalid mask param type")
    if has_nonnull_operand:
      while len(cur_operands) < len(masks):
        cur_operands.append(None)
    else:
      cur_operands = []
    # 最后处理大小和 bbox
    # 描述对象中会有基础的大小和 bbox 信息，但是这里可以覆盖
    # 当用户指定了一个不一样的大小时，我们认为用户是想缩放图片，最后导出时要按指定尺寸导出
    # 当用户指定 bbox 时，我们认为用户并不是想对图片做什么，只是调整其在屏幕上的位置。
    std_size : tuple[int, int] = descriptor.get_size()
    std_bbox = descriptor.get_bbox()
    if size is not None:
      BaseImageLiteralExpr._validate_size(size)
    else:
      size = IntTupleLiteral.get(std_size, context=context)
    if bbox is not None:
      if not isinstance(bbox, IntTupleLiteral) or len(bbox.value) != 4:
        raise ValueError("Invalid bbox value")
    else:
      # 我们需要自行计算 bbox
      # 如果图片被缩放，那么我们也要根据原来的 bbox 把缩放后的 bbox 计算出来
      if size.value == std_size:
        bbox = IntTupleLiteral.get(std_bbox, context=context)
      else:
        if std_bbox == (0, 0, 0, 0):
          bbox = IntTupleLiteral.get((0, 0, 0, 0), context=context)
        elif std_bbox == (0, 0, std_size[0], std_size[1]):
          bbox = IntTupleLiteral.get((0, 0, size.value[0], size.value[1]), context=context)
        else:
          x_scale = size.value[0] / std_size[0]
          y_scale = size.value[1] / std_size[1]
          left, top, right, bottom = std_bbox
          bbox = IntTupleLiteral.get((int(left * x_scale), int(top * y_scale), int(right * x_scale), int(bottom * y_scale)), context=context)
    pack_str = StringLiteral.get(pack, context=context)
    element_str = StringLiteral.get(element, context=context)
    return ImagePackElementLiteralExpr._get_literalexpr_impl((size, bbox, pack_str, element_str, *cur_operands), context)

