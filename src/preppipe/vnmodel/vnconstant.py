# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from ..commontypes import TextAttribute, Color
from .vntype import *



class VNConstantScreenCoordinate(Constant):
  # 屏幕坐标常量是一对整数型值<x,y>，坐标原点是屏幕左上角，x沿右边增加，y向下方增加，单位都是像素值
  # 根据使用场景，坐标常量有可能被当做大小、偏移量，或是其他值来使用
  def __init__(self, context : Context, value: tuple[int, int], **kwargs) -> None:
    assert isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], int)
    ty = VNScreenCoordinateType.get(context)
    super().__init__(ty, value, **kwargs)
  
  @staticmethod
  def get(context : Context, value : tuple[int, int]) -> VNConstantScreenCoordinate:
    return Constant._get_constant_impl(VNConstantScreenCoordinate, value, context)
