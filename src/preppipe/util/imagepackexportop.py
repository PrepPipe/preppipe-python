# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
from ..irbase import *
from ..exportcache import CacheableOperationSymbol
from .imagepack import *
from ..imageexpr import *

@IRObjectJsonTypeName("imagepack_export_op_symbol")
class ImagePackExportOpSymbol(CacheableOperationSymbol):
  # 所有对图片包的导出操作都会使用这个操作符
  _imagepack : OpOperand[StringLiteral]
  _fork_params : OpOperand # 可能是图片也可能是字符串等等
  _target_size : OpOperand[IntTupleLiteral] # 如果要缩放大小的话，这里存放目标大小
  # 以下两项用于描述图层导出的内容，两项的数量应该一致
  _layers_export_indices : OpOperand[IntLiteral] # 导出的图层的下标
  _layers_export_paths : OpOperand[StringLiteral] # 导出的路径
  # 以下两项用于描述图层组合的导出，两项的数量应该一致
  _composites_export_indices : OpOperand[IntLiteral] # 导出的图层组合的下标
  _composites_export_paths : OpOperand[StringLiteral] # 导出的路径

  def construct_init(self, *, imagepack : StringLiteral, target_size : IntTupleLiteral | None = None, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._imagepack = self._add_operand_with_value("imagepack", imagepack)
    self._fork_params = self._add_operand("fork_params")
    self._target_size = self._add_operand_with_value("target_size", target_size)
    self._layers_export_indices = self._add_operand("layers_export_indices")
    self._layers_export_paths = self._add_operand("layers_export_paths")
    self._composites_export_indices = self._add_operand("composites_export_indices")
    self._composites_export_paths = self._add_operand("composites_export_paths")
    if target_size is not None:
      if len(target_size.value) != 2:
        raise PPInternalError("Target size must be a 2-tuple")

  def post_init(self) -> None:
    self._imagepack = self.get_operand_inst("imagepack")
    self._fork_params = self.get_operand_inst("fork_params")
    self._target_size = self.get_operand_inst("target_size")
    self._layers_export_indices = self.get_operand_inst("layers_export_indices")
    self._layers_export_paths = self.get_operand_inst("layers_export_paths")
    self._composites_export_indices = self.get_operand_inst("composites_export_indices")
    self._composites_export_paths = self.get_operand_inst("composites_export_paths")

  def add_fork_param(self, param : Value) -> None:
    self._fork_params.add_operand(param)

  def add_layer_export(self, index : IntLiteral, path : StringLiteral) -> None:
    if self._target_size.get_num_operands() > 0:
      raise PPInternalError("Cannot add layer export if target size is specified")
    self._layers_export_indices.add_operand(index)
    self._layers_export_paths.add_operand(path)

  def add_composite_export(self, index : IntLiteral, path : StringLiteral) -> None:
    self._composites_export_indices.add_operand(index)
    self._composites_export_paths.add_operand(path)

  def finish_init(self) -> None:
    # 根据现有的参数，计算一个用于缓存输出的可读的字符串来作为这个操作符的名称
    resultname = "ImagePackExportOpSymbol[" + self._imagepack.get().get_string() + "]"
    if self._fork_params.get_num_operands() > 0:
      resultname += "<" + ",".join([str(use.value) for use in self._fork_params.operanduses()]) + ">" # 用于 fork 的参数
    if self._target_size.get_num_operands() > 0:
      resultname += str(self._target_size.get_operand(0).value)
    resultname += "{"
    for i in range(0, min(self._layers_export_indices.get_num_operands(), self._layers_export_paths.get_num_operands())):
      resultname += str(self._layers_export_indices.get_operand(i).value) + ":" + self._layers_export_paths.get_operand(i).get_string() + ","
    resultname += "}{"
    for i in range(0, min(self._composites_export_indices.get_num_operands(), self._composites_export_paths.get_num_operands())):
      resultname += str(self._composites_export_indices.get_operand(i).value) + ":" + self._composites_export_paths.get_operand(i).get_string() + ","
    resultname += "}"
    self._name = resultname

  def get_export_file_list(self) -> list[str]:
    # 返回这个操作导出的文件列表，只需要基于输出根目录的相对路径
    return [use.value.get_string() for uselist in [self._layers_export_paths.operanduses(), self._composites_export_paths.operanduses()] for use in uselist]

  def get_depended_assets(self) -> list[str]:
    # 返回这个操作依赖的资源文件列表
    result = [self._imagepack.get().get_string()]
    # 如果 fork 参数里有文本，我们需要把字体资源给加进来
    for use in self._fork_params.operanduses():
      value = use.value
      if isinstance(value, (StringLiteral, TextFragmentLiteral)):
        if len(value.get_string()) > 0:
          result.append(ImagePack.TEXT_IMAGE_FONT_ASSET)
          break
    return result

  def run_export(self, output_rootdir : str) -> None:
    # 执行这个操作的导出，output_rootdir 是输出根目录
    # 一般会在一个新的线程中执行这个操作
    imagepack = AssetManager.get_instance().get_asset(self._imagepack.get().get_string())
    if imagepack is None:
      # 如果图片包不存在，我们就不用继续了
      return
    if not isinstance(imagepack, ImagePack):
      raise PPInternalError("Asset is not an image pack: " + self._imagepack.get().get_string())
    # 如果需要 fork 操作，我们就执行 fork 操作
    if self._fork_params.get_num_operands() > 0:
      args : list[Color | PIL.Image.Image | str | tuple[str, Color] | None] = []
      for use in self._fork_params.operanduses():
        value = use.value
        if isinstance(value, StringLiteral):
          text = value.get_string()
          if len(text) == 0:
            args.append(None)
          else:
            args.append(text)
        elif isinstance(value, TextFragmentLiteral):
          text = value.get_string()
          color = value.style.get_color()
          if len(text) == 0:
            args.append(None)
          elif color is None:
            args.append(text)
          else:
            args.append((text, color))
        elif isinstance(value, ColorLiteral):
          args.append(value.value)
        elif isinstance(value, ImageAssetLiteralExpr):
          image = value.image.load()
          args.append(image)
        elif isinstance(value, ColorImageLiteralExpr):
          color = value.color.value
          args.append(color)
        else:
          raise PPInternalError("Unsupported fork parameter type: " + str(value))
      if len(args) < len(imagepack.masks):
        args += [None] * (len(imagepack.masks) - len(args))
      imagepack = imagepack.fork_applying_mask(args)
    num_composites_export = min(self._composites_export_indices.get_num_operands(), self._composites_export_paths.get_num_operands())
    for i in range(0, num_composites_export):
      index = self._composites_export_indices.get_operand(i).value
      path = self._composites_export_paths.get_operand(i).get_string()
      image = imagepack.get_composed_image(index)
      if self._target_size.get_num_operands() > 0:
        x, y = self._target_size.get_operand(0).value
        image = image.resize(size=(x, y))
      image.save(os.path.join(output_rootdir, path))
    num_layers_export = min(self._layers_export_indices.get_num_operands(), self._layers_export_paths.get_num_operands())
    for i in range(0, num_layers_export):
      index = self._layers_export_indices.get_operand(i).value
      path = self._layers_export_paths.get_operand(i).get_string()
      image = imagepack.layers[index].patch
      image.save(os.path.join(output_rootdir, path))
    # 完成

  def get_workload_cpu_usage_estimate(self) -> float:
    # 返回这个操作的 CPU 使用量估计(1: CPU 密集型；0: I/O 密集型)，用于计算线程池的大小和计算调度
    if self._fork_params.get_num_operands() > 0 or self._composites_export_indices.get_num_operands() > 0:
      # 在这两种情况下我们都需要执行图片组合或是 fork 操作，所以是 CPU 密集型
      return 1.0
    # 否则是 I/O 密集型，只需要输出现有的图片
    return 0.25

class ImagePackExportDataBuilder:
  # 我们使用该类在将 VNModel 转化为后端 IR/AST 时对图片包的引用进行整理
  # 并在后端 IR/AST 中生成对应的 ImagePackExportOpSymbol
  # 如果任意部分需要定制，后端可以继承这个类并实现对应的方法

  # 以下需要子类提供实现(也可以用这里的默认实现)
  # ---------------------------------------------------------------------
  def get_instance_id(self, pack_id : str, fork_params : tuple, pack_instance_index : int) -> str:
    # 通过图片包 ID、fork 参数和图片包实例的索引来获取一个唯一的 ID
    return pack_id + "_" + str(pack_instance_index)

  def place_imagepack_instance(self, instance_id : str, pack_id : str) -> str:
    # 当我们需要创建图片包实例时，我们应该把图片包放在哪
    # 图片包中的图层将保存在这个目录下，文件名由编号决定。
    # 此类会尝试将不同图片包实例中能共享的部分进行合并，同一图层可能被多个实例引用。
    return os.path.join("images", pack_id)

  def get_imagepack_layer_filename(self, pack_id : str, layer_index : int) -> str:
    # 保存图片包实例时，各个图层应该以什么文件名保存。这个函数也决定图片保存的格式
    # 路径已经由 place_imagepack_instance() 决定，这里只需要返回文件名即可
    return pack_id + "_L" + str(layer_index) + ".png"

  def place_imagepack_composite(self, instance_id : str, pack_id : str, composite_code : str) -> str:
    # 组合的图片应该放在哪
    return os.path.join("images", pack_id, 'E' + instance_id + '_' + composite_code + ".png")

  # 以下是提供给子类使用者的接口
  # ---------------------------------------------------------------------

  @dataclasses.dataclass
  class ImagePackElementReferenceInfo:
    # 如果对图片的引用可以不用独立的图片，而是用差分的方式来表示，那么这个类可以用来表示这个差分
    # 我们要求后端能够使用 instance_id + composite_code 来生成引用
    # 如果实际上需要用其他方式表示（比如差分不能直接用 composite_code 字符串、必须用纯数字编号）那么后端需要自己构建这样的转换
    instance_id : str
    composite_code : str

  def add_value(self, value : ImagePackElementLiteralExpr, is_require_merged_image : bool = False) -> ImagePackElementReferenceInfo | str:
    # 添加一个图片包元素到 builder 中
    # 如果 is_require_merged_image 为 True，那么我们生成时会保证生成一个单独的图片，路径是返回值
    # 否则我们会尝试使用差分的方式来表示这个图片，返回值是 ImagePackElementReferenceInfo
    raise NotImplementedError()

  @dataclasses.dataclass
  class LayerExportInfo:
    index : int
    offset_x : int
    offset_y : int
    path : str

  @dataclasses.dataclass
  class InstanceExportInfo:
    layer_exports : list # list[LayerExportInfo]
    composites : dict[str, tuple[int, ...]] # 差分组合的编码 -> 各个组成图层的编号

  def finalize(self, dest : SymbolTableRegion[ImagePackExportOpSymbol]) -> dict[str, InstanceExportInfo]:
    # 完成添加图片包元素的操作，生成 ImagePackExportOpSymbol 并整理所有的图片包实例信息
    # 我们生成的导出操作中会包含单个文件的输出操作，但是这个函数的返回值只包含图片包实例的信息
    # 在 RenPy 中，我们会使用此函数的返回值来生成 layeredimage 语句，而单个文件可以直接使用文件名、不需要额外的处理
    raise NotImplementedError()
