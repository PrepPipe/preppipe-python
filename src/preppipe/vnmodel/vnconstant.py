# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from ..commontypes import TextAttribute, Color
from .vntype import *

class VNConstant(Value):
  _value : typing.Any
  def __init__(self, ty: ValueType, value : typing.Any, **kwargs) -> None:
    super().__init__(ty, **kwargs)
    self._value = value
  
  @property
  def value(self) -> typing.Any:
    return self._value
  
  def get_context(self) -> Context:
    return self.valuetype.context
  
  @staticmethod
  def _get_constant_impl(cls : type, value : typing.Any, context : Context) -> typing.Any:
    d = context.get_constant_uniquing_dict(cls)
    if value in d:
      return d[value]
    result = cls(context, value)
    d[value] = result
    return result
  
  @staticmethod
  def get(value: typing.Any, context : Context) -> typing.Any:
    if isinstance(value, int):
      return VNConstantInt.get(value, context)
    if isinstance(value, bool):
      return VNConstantBool.get(value, context)
    raise RuntimeError("Unknown value type for constant creation")
  
class VNConstantInt(VNConstant):
  def __init__(self, context : Context, value : int, **kwargs) -> None:
    # should not be called by user code
    assert isinstance(value, int)
    ty = VNIntType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> int:
    return super().value
  
  @staticmethod
  def get(value : int, context : Context) -> VNConstantInt:
    return VNConstant._get_constant_impl(VNConstantInt, value, context)

class VNConstantBool(VNConstant):
  def __init__(self, context : Context, value: bool, **kwargs) -> None:
    assert isinstance(value, bool)
    ty = VNBoolType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> bool:
    return super().value
  
  @staticmethod
  def get(value : bool, context : Context) -> VNConstantBool:
    return VNConstant._get_constant_impl(VNConstantBool, value, context)

class VNConstantString(VNConstant):
  # 字符串常量的值不包含样式等信息，就是纯字符串
  def __init__(self, context : Context, value: str, **kwargs) -> None:
    assert isinstance(value, str)
    ty = VNStringType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @property
  def value(self) -> str:
    return super().value
  
  @staticmethod
  def get(value : str, context : Context) -> VNConstantString:
    return VNConstant._get_constant_impl(VNConstantString, value, context)

class VNConstantTextFragment(VNConstant):
  # 文本常量的值包含字符串以及样式信息（大小字体、字体颜色、背景色（高亮颜色），或是附注（Ruby text））
  # 单个文本片段常量内容所使用的样式需是一致的，如果不一致则可以把内容进一步切分，按照样式来进行分节
  # 文本片段常量的“值”（value）是【对字符串常量的引用】+【样式信息元组】的元组(tuple)
  # 样式信息元组内的每一项都是(样式，值)组成的元组，这些项将根据样式的枚举值进行排序

  def __init__(self, context : Context, value: tuple[VNConstantString, tuple[tuple[TextAttribute, typing.Any]]], **kwargs) -> None:
    # value 应为 VNConstantTextFragment.get_value_tuple() 的结果
    ty = VNTextType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @staticmethod
  def get_value_tuple(string : VNConstantString, styles : dict[TextAttribute, typing.Any]):
    stylelist = []
    for attr, v in styles:
      # 检查样式的值是否符合要求
      # 同时忽略部分VNModel不支持的属性
      isDiscard = False
      match attr:
        case TextAttribute.Bold:
          if v is not None:
            raise RuntimeError("文本属性“加粗”不应该带参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.Italic:
          if v is not None:
            raise RuntimeError("文本属性“斜体”不应该带参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.Hierarchy:
          # VNModel不支持该属性
          isDiscard = True
        case TextAttribute.Size:
          if not isinstance(v, int):
            raise RuntimeError("文本属性“大小”应该带一个整数型参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.TextColor:
          if not isinstance(v, Color):
            raise RuntimeError("文本属性“文本颜色”应该带一个颜色类型的参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case TextAttribute.BackgroundColor:
          if not isinstance(v, Color):
            raise RuntimeError("文本属性“背景颜色”应该带一个颜色类型的参数，但现有参数：" + str(v) + "<类型：" + str(type(v).__name__))
        case _:
          isDiscard = True
      if not isDiscard:
        entry_tuple = (attr, v)
        stylelist.append(entry_tuple)
    # 所有样式信息检查完毕后即可开始生成结果
    stylelist.sort()
    styletuple = tuple(stylelist)
    return (string, styletuple)
  
  @staticmethod
  def get(context : Context, string : VNConstantString, styles : dict[TextAttribute, typing.Any]) -> VNConstantTextFragment:
    if not isinstance(string, VNConstantString):
      raise RuntimeError("string 参数应为对字符串常量的引用")
    value_tuple = VNConstantTextFragment.get_value_tuple(string, styles)
    return VNConstant._get_constant_impl(VNConstantTextFragment, value_tuple, context)

class VNConstantText(VNConstant):
  # 文本常量是一个或多个文本片段常量组成的串

  def __init__(self, context : Context, value: tuple[VNConstantTextFragment], **kwargs) -> None:
    VNConstantText._check_value_tuple(value)
    ty = VNTextType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @staticmethod
  def _check_value_tuple(value: tuple[VNConstantTextFragment]) -> None:
    isCheckFailed = False
    if not isinstance(value, tuple):
      isCheckFailed = True
    else:
      for v in value:
        if not isinstance(v, VNConstantTextFragment):
          isCheckFailed = True
    if isCheckFailed:
      raise RuntimeError("文本常量的值应为仅由文本片段常量组成的元组")
  
  @staticmethod
  def get(context : Context, value : typing.Iterable[VNConstantTextFragment]) -> VNConstantText:
    value_tuple = tuple(value)
    return VNConstant._get_constant_impl(VNConstantText, value_tuple, context)