# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import dataclasses
import PIL
import PIL.Image
import enum

from ..irbase import *
from ..irdataop import *


@dataclasses.dataclass(init=False, slots=True, frozen=True)
class UIAssetElementType(StatelessType):
  @classmethod
  def get(cls, ctx : Context):
    return ctx.get_stateless_type(cls)

@dataclasses.dataclass
class UIAssetElementDrawingData:
  # 作图过程中的数据。这是基类，各种节点可以继承该类后添加数据。
  # 这里不包含该图片会在最终结果中的位置
  image : PIL.Image.Image | None = None # 该图仅为当前元素的图层。如果该元素有子元素，子元素的图不应该直接嵌在这里。
  description : Translatable | str | None = None # 该图的描述，用于调试；应该描述画的算法（比如渐变填充）而不是该图是什么（比如按钮背景）
  anchor : tuple[int, int] = (0, 0) # 锚点在当前结果中的位置（像素距离）

  def sanity_check(self):
    # 有异常就报错
    pass

@IROperationDataclassWithValue(UIAssetElementType)
class UIAssetElementNodeOp(Operation, Value):
  # 该类用于表述任意 UI 素材的元素，包括点、线、面等
  # 所有的坐标、大小都以像素为单位
  # 除非特殊情况，否则所有元素的锚点都应该是左上角顶点（不管留白或是延伸的特效（如星星延伸出的光效等））

  # 子节点的信息，越往后则越晚绘制
  child_positions : OpOperand[IntTuple2DLiteral] # 子元素的锚点在本图层内的位置（相对像素位置）
  child_refs : OpOperand[UIAssetElementNodeOp] # 子元素的引用
  child_zorders : OpOperand[IntLiteral] # 子元素的 Z 轴顺序(相对于本元素，越大越靠前、越晚画)

  def get_bbox(self) -> tuple[int, int, int, int] | None:
    # 只返回该元素的 bbox，不包括子元素
    return None

  def draw(self, drawctx : UIAssetDrawingContext) -> UIAssetElementDrawingData:
    return UIAssetElementDrawingData()

  def add_child(self, ref : UIAssetElementNodeOp, pos : tuple[int, int], zorder : int):
    self.child_refs.add_operand(ref)
    self.child_positions.add_operand(IntTuple2DLiteral.get(pos, context=self.context))
    self.child_zorders.add_operand(IntLiteral.get(zorder, context=self.context))

  def get_child_bbox(self) -> tuple[int, int, int, int] | None:
    cur_bbox = None
    numchildren = self.child_refs.get_num_operands()
    for i in range(numchildren):
      child = self.child_refs.get_operand(i)
      if not isinstance(child, UIAssetElementNodeOp):
        raise PPInternalError(f"Unexpected child type: {type(child)}")
      child_bbox = child.get_bbox()
      child_child_bbox = child.get_child_bbox()
      if child_bbox is not None:
        left, top, right, bottom = child_bbox
        if child_child_bbox is not None:
          c_left, c_top, c_right, c_bottom = child_child_bbox
          left = min(left, c_left)
          top = min(top, c_top)
          right = max(right, c_right)
          bottom = max(bottom, c_bottom)
      elif child_child_bbox is not None:
        left, top, right, bottom = child_child_bbox
      else:
        continue
      offset_x, offset_y = self.child_positions.get_operand(i).value
      left += offset_x
      right += offset_x
      top += offset_y
      bottom += offset_y
      if cur_bbox is None:
        cur_bbox = (left, top, right, bottom)
      else:
        cur_bbox = (min(cur_bbox[0], left), min(cur_bbox[1], top), max(cur_bbox[2], right), max(cur_bbox[3], bottom))
    return cur_bbox

@IROperationDataclassWithValue(UIAssetElementType)
class UIAssetElementGroupOp(UIAssetElementNodeOp):
  # 自身不含任何需要画的内容，仅用于组织其他元素（比如方便复用）
  @staticmethod
  def create(context : Context):
    return UIAssetElementGroupOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context)

@IROperationDataclass
class UIAssetDrawingResultElementOp(Operation):
  # UI素材元素画完之后的结果
  image_patch : OpOperand[Value] # 该元素的图像
  image_pos : OpOperand[IntTuple2DLiteral] # 该元素左上角在整个画布中的位置
  description : OpOperand[TranslatableLiteral | StringLiteral] # UIAssetElementDrawingData.description 的值

  @staticmethod
  def create(context : Context, image_patch : Value, image_pos : tuple[int, int], description : Translatable | str | None, name : str = '', loc : Location | None = None) -> UIAssetDrawingResultElementOp:
    image_pos_value = IntTuple2DLiteral.get(image_pos, context=context)
    description_value = None
    if isinstance(description, str):
      description_value = StringLiteral.get(description, context=context)
    elif isinstance(description, Translatable):
      description_value = TranslatableLiteral.get(description, context=context)
    else:
      raise PPInternalError(f'Unexpected description type: {type(description)}')
    return UIAssetDrawingResultElementOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc, image_patch=image_patch, image_pos=image_pos_value, description=description_value)

@dataclasses.dataclass
class UIAssetDrawingContext:
  drawing_cache : dict[UIAssetElementNodeOp, tuple[UIAssetElementDrawingData, TemporaryImageData | None]] = dataclasses.field(default_factory=dict)

  def get_drawing_data(self, node : UIAssetElementNodeOp) -> tuple[UIAssetElementDrawingData, TemporaryImageData | None]:
    if result := self.drawing_cache.get(node):
      return result
    result = node.draw(self)
    result.sanity_check()
    imagedata = None
    if result.image is not None:
      imagedata = TemporaryImageData.create(node.context, result.image)
    result_tuple = (result, imagedata)
    self.drawing_cache[node] = result_tuple
    return result_tuple

  def draw_stack(self, root : UIAssetElementNodeOp, xoffset : int, yoffset : int, stack : list[UIAssetElementNodeOp]) -> list[UIAssetDrawingResultElementOp]:
    if root in stack:
      raise PPInternalError("Circular reference detected in UIAssetElementNodeOp stack")
    stack.append(root)
    draw_orders : list[tuple[int, UIAssetElementNodeOp, tuple[int,int]]] = []
    draw_orders.append((0, root, (0,0)))
    numchildren = root.child_refs.get_num_operands()
    for i in range(numchildren):
      child = root.child_refs.get_operand(i)
      pos = root.child_positions.get_operand(i).value
      zorder = root.child_zorders.get_operand(i).value
      if not isinstance(child, UIAssetElementNodeOp):
        raise PPInternalError(f"Unexpected child type: {type(child)}")
      if child is root:
        raise PPInternalError("Circular reference detected in UIAssetElementNodeOp stack")
      draw_orders.append((zorder, child, pos))
    draw_orders.sort(key=lambda x: x[0])
    result = []
    for zorder, child, pos in draw_orders:
      if child is not root:
        cur_child_result = self.draw_stack(child, xoffset + pos[0], yoffset + pos[1], stack)
        result.extend(cur_child_result)
      else:
        # 绘制当前 root
        cur_draw_data, image_data = self.get_drawing_data(root)
        if image_data is not None:
          xrev, yrev = cur_draw_data.anchor
          op = UIAssetDrawingResultElementOp.create(root.context, image_data, (xoffset - xrev, yoffset - yrev), cur_draw_data.description)
          result.append(op)
    if stack[-1] is not root:
      raise PPInternalError("Stack corruption detected in UIAssetElementNodeOp stack")
    stack.pop()
    return result

class UIAssetKind(enum.Enum):
  GENERIC = enum.auto() # 不知道具体什么类型的图片
  BUTTON_ICON = enum.auto() # 以（正方形）图标为核心的小按钮
  BUTTON_TEXT = enum.auto() # 以文字为核心的中小型按钮

@IROperationDataclass
class UIAssetEntrySymbol(Symbol):
  # 每个 UIAssetEntryBaseSymbol 都代表一个实际需求（比如按钮，滑动条，对话框等）中的一个图片导出项
  # 如果需要额外的元数据（比如该需求对应一个滚动条，我们想知道滚动条的边框大小），请使用 Attributes
  kind : OpOperand[EnumLiteral[UIAssetKind]]
  body : Block # UIAssetDrawingResultElementOp 的列表
  canvas_size : OpOperand[IntTuple2DLiteral] # 画布大小
  origin_pos : OpOperand[IntTuple2DLiteral] # 原点在画布中的位置

  def take_image_layers(self, layers : list[UIAssetDrawingResultElementOp]):
    xmin = 0
    ymin = 0
    xmax = 0
    ymax = 0
    for op in layers:
      if not isinstance(op, UIAssetDrawingResultElementOp):
        raise PPInternalError(f"Unexpected type: {type(op)}")
      self.body.push_back(op)
      x, y = op.image_pos.get().value
      imagedata = op.image_patch.get()
      if not isinstance(imagedata, TemporaryImageData):
        raise PPInternalError(f"Unexpected type: {type(imagedata)}")
      w, h = imagedata.value.size
      xmin = min(xmin, x)
      ymin = min(ymin, y)
      xmax = max(xmax, x + w)
      ymax = max(ymax, y + h)
    total_width = xmax - xmin
    total_height = ymax - ymin
    self.canvas_size.set_operand(0, IntTuple2DLiteral.get((total_width, total_height), context=self.context))
    self.origin_pos.set_operand(0, IntTuple2DLiteral.get((-xmin, -ymin), context=self.context))

  def save_png(self, path : str):
    size_tuple = self.canvas_size.get().value
    origin_tuple = self.origin_pos.get().value
    image = PIL.Image.new('RGBA', size_tuple, (0,0,0,0))
    for op in self.body.body:
      if not isinstance(op, UIAssetDrawingResultElementOp):
        raise PPInternalError(f"Unexpected type: {type(op)}")
      imagedata = op.image_patch.get()
      if not isinstance(imagedata, TemporaryImageData):
        raise PPInternalError(f"Unexpected type: {type(imagedata)}")
      x, y = op.image_pos.get().value
      curlayer = PIL.Image.new('RGBA', size_tuple, (0,0,0,0))
      curlayer.paste(imagedata.value, (x + origin_tuple[0], y + origin_tuple[1]))
      image = PIL.Image.alpha_composite(image, curlayer)
    image.save(path)

  @staticmethod
  def create(context : Context, kind : UIAssetKind, name : str, loc : Location | None = None) -> UIAssetEntrySymbol:
    kind_value = EnumLiteral.get(value=kind, context=context)
    return UIAssetEntrySymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, name=name, loc=loc, kind=kind_value)

class UIAssetStyleData:
  # 用于描述基础样式（比如颜色组合）
  pass

class UIAssetImplementerBase:
  # 描述具体以怎样的方式来绘制单个需求的 UI 资源，输出 UIAssetElementNodeOp 序列
  # 每种资源（按钮、复选框等）应该都至少有一个实现类
  # 该类应该从 UIAssetStyleData 读取所需信息，其他选项信息得由 UIAssetStyler 提供
  pass

class UIAssetStyler:
  # 描述怎样使用 UIAssetImplementerBase 的子类来绘制需求下的所有 UI 资源
  # 如果我们在程序 UI 中用一个面板来展示所有的选项，那么此类决定面板里有哪些选项
  pass

@IROperationDataclass
class UIAssetPack(Operation):
  # 该类同时被用于表达 UI 需求和 UI 资源包
  # 一开始，使用方（比如 RenPy UI模板）准备一个需求，然后实现方将会把具体绘制方法填入需求中
  entries : SymbolTableRegion[UIAssetEntrySymbol]
  elements : Block

class UIAssetDesignerBase:
  # TODO 根据 UI 需求来实现 UI 资源生成的基类
  pass
