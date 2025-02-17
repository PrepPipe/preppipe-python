# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from ..tooldecl import *
from .base import *
from .elements import *

@ToolClassDecl("uiassetgen-tester")
class UIAssetGenTester:
  @staticmethod
  def tool_main(args : list[str] | None):
    context = Context()
    text_color = Color.get((0, 0, 0)) # 黑色
    box1_color = Color.get((255, 255, 255))
    box2_color = Color.get((128, 128, 128))
    fontsize = 100
    text_color_value = ColorLiteral.get(text_color, context=context)
    box1_color_value = ColorLiteral.get(box1_color, context=context)
    box2_color_value = ColorLiteral.get(box2_color, context=context)
    text_value = StringLiteral.get("Test", context=context)
    text = UIAssetTextElementOp.create(context, fontcolor=text_color_value, fontsize=fontsize, text=text_value)
    text_bbox = text.get_bbox()
    print(text_bbox)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    box1 = UIAssetRectangleOp.create(context, width=text_width + 10, height=text_height + 10)
    box1_fill = UIAssetAreaFillElementOp.create(context, boundary=box1, mode=UIAssetAreaFillMode.COLOR_FILL, color1=box1_color_value)
    box2 = UIAssetRectangleOp.create(context, width=text_width + 20, height=text_height + 20)
    box2_fill = UIAssetAreaFillElementOp.create(context, boundary=box2, mode=UIAssetAreaFillMode.COLOR_FILL, color1=box2_color_value)
    box2.add_child(box2_fill, (0, 0), zorder=1)
    box2.add_child(box1, (5, 5), zorder=2)
    box1.add_child(box1_fill, (0, 0), zorder=1)
    box1.add_child(text, (5 - text_bbox[0], 5 - text_bbox[1]), zorder=2)
    group = UIAssetElementGroupOp.create(context)
    group.add_child(box2, (0, 0), zorder=1)
    group.add_child(box2, (text_width + 20, 0), zorder=2)
    group.add_child(box2, (0, text_height + 20), zorder=3)
    group.add_child(box2, (text_width + 20, text_height + 20), zorder=4)
    drawctx = UIAssetDrawingContext()
    stack = []
    image_layers = drawctx.draw_stack(group, 0, 0, stack)
    result_symb = UIAssetEntrySymbol.create(context, kind=UIAssetKind.GENERIC, name="test")
    result_symb.take_image_layers(image_layers)
    result_symb.save_png("testout.png")
    result_symb.dump()

