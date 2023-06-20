# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该文件存放一些帮助代码生成的函数
# 有些逻辑在解析与生成时都会用到，比如查找图片表达式等，我们把这些实现放在这

from ...irbase import *
from ...imageexpr import *
from .vnast import *

def emit_image_expr(context : Context, pathexpr : str) -> BaseImageLiteralExpr | None:
  # 如果提供了图片路径，则当场读取图片内容，创建 ImageAssetLiteralExpr
  # 如果是占位、声明这种，则根据情况特判
  raise NotImplementedError()
