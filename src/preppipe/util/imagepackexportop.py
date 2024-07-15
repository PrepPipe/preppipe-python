# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

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
