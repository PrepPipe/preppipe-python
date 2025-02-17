# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
import os
from ..irbase import *
from ..exportcache import CacheableOperationSymbol
from .imagepack import *
from ..imageexpr import *
from .message import MessageHandler
from ..commontypes import *
import concurrent.futures

@IRObjectJsonTypeName("imagepack_export_op_symbol")
class ImagePackExportOpSymbol(CacheableOperationSymbol):
  # 所有对图片包的导出操作都会使用这个操作符
  _imagepack : OpOperand[StringLiteral]
  _fork_params : OpOperand # 可能是图片也可能是字符串等等
  # 以下两项用于描述图层导出的内容，两项的数量应该一致
  _layers_export_indices : OpOperand[IntLiteral] # 导出的图层的下标
  _layers_export_paths : OpOperand[StringLiteral] # 导出的路径
  # 以下用于描述图层组合的导出，各项的数量应该一致
  _composites_export_indices : OpOperand[IntLiteral] # 导出的图层组合的下标
  _composites_export_paths : OpOperand[StringLiteral] # 导出的路径
  _composites_target_sizes : OpOperand[IntTuple2DLiteral] # 如果要缩放大小的话，这里存放目标大小（如果不缩放的话应该和原图大小一致）
  _fully_loaded_imagepacks : typing.ClassVar[dict[str, list[concurrent.futures.Future]] | None] = None # 用于记录已经加载过的图片包，避免重复加载

  _tr_imagepack_not_found = ImagePack.TR_imagepack.tr("export_op_imagepack_not_found",
    en="Image pack not found: {imagepack}",
    zh_cn="图片包未找到：{imagepack}",
    zh_hk="圖片包未找到：{imagepack}"
  )
  _tr_loading_imagepack = ImagePack.TR_imagepack.tr("loading_imagepack",
    en="Loading image pack: {imagepack}",
    zh_cn="正在载入图片包：{imagepack}",
    zh_hk="正在載入圖片包：{imagepack}",
  )

  def construct_init(self, *, imagepack : StringLiteral, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._imagepack = self._add_operand_with_value("imagepack", imagepack)
    self._fork_params = self._add_operand("fork_params")
    self._layers_export_indices = self._add_operand("layers_export_indices")
    self._layers_export_paths = self._add_operand("layers_export_paths")
    self._composites_export_indices = self._add_operand("composites_export_indices")
    self._composites_export_paths = self._add_operand("composites_export_paths")
    self._composites_target_sizes = self._add_operand("composites_target_sizes")

  def post_init(self) -> None:
    self._imagepack = self.get_operand_inst("imagepack")
    self._fork_params = self.get_operand_inst("fork_params")
    self._layers_export_indices = self.get_operand_inst("layers_export_indices")
    self._layers_export_paths = self.get_operand_inst("layers_export_paths")
    self._composites_export_indices = self.get_operand_inst("composites_export_indices")
    self._composites_export_paths = self.get_operand_inst("composites_export_paths")
    self._composites_target_sizes = self.get_operand_inst("composites_target_sizes")

  @staticmethod
  def create(context : Context, imagepack : StringLiteral | str, loc : Location | None = None) -> "ImagePackExportOpSymbol":
    # 因为最后会使用参数来生成这个 Symbol 的名称，所以创建时我们不支持 name 参数
    if isinstance(imagepack, str):
      imagepack = StringLiteral.get(imagepack, context)
    return ImagePackExportOpSymbol(init_mode=IRObjectInitMode.CONSTRUCT, context=context, imagepack=imagepack, loc=loc)

  def add_fork_param(self, param : Value) -> None:
    self._fork_params.add_operand(param)

  def add_layer_export(self, index : IntLiteral, path : StringLiteral) -> None:
    self._layers_export_indices.add_operand(index)
    self._layers_export_paths.add_operand(path)

  def add_composite_export(self, index : IntLiteral, path : StringLiteral, target_size : IntTuple2DLiteral) -> None:
    self._composites_export_indices.add_operand(index)
    self._composites_export_paths.add_operand(path)
    self._composites_target_sizes.add_operand(target_size)

  def finish_init(self) -> None:
    # 根据现有的参数，计算一个用于缓存输出的可读的字符串来作为这个操作符的名称
    resultname = "ImagePackExportOpSymbol[" + self._imagepack.get().get_string() + "]"
    if self._fork_params.get_num_operands() > 0:
      resultname += "<" + ",".join([str(use.value) for use in self._fork_params.operanduses()]) + ">" # 用于 fork 的参数
    resultname += "{"
    for i in range(0, self._layers_export_indices.get_num_operands()):
      resultname += str(self._layers_export_indices.get_operand(i).value) + ":" + self._layers_export_paths.get_operand(i).get_string() + ","
    resultname += "}{"
    for i in range(0, self._composites_export_indices.get_num_operands()):
      resultname += str(self._composites_export_indices.get_operand(i).value) + ":" + self._composites_export_paths.get_operand(i).get_string()
      resultname += " " + str(self._composites_target_sizes.get_operand(i).value) + ","
    resultname += "}"
    self._name = resultname

  def get_export_file_list(self) -> list[str]:
    # 返回这个操作导出的文件列表，只需要基于输出根目录的相对路径
    return [use.value.get_string() for uselist in [self._layers_export_paths.operanduses(), self._composites_export_paths.operanduses()] for use in uselist]

  @classmethod
  def cls_prepare_export(cls, tp : concurrent.futures.ThreadPoolExecutor) -> None:
    # 如果需要执行操作，这个函数会在执行前被调用一次
    # 要 jit 或者做一些其他准备工作的话可以在这里做
    if cls._fully_loaded_imagepacks is not None:
      raise PPInternalError("ImagePackExportOpSymbol.cls_prepare_export() called twice")
    cls._fully_loaded_imagepacks = {}
    # 不管怎样都尝试载入一下字体，可能会用到
    AssetManager.get_font()

  def instance_prepare_export(self, tp : concurrent.futures.ThreadPoolExecutor) -> bool:
    if self._fully_loaded_imagepacks is None:
      raise PPInternalError("ImagePackExportOpSymbol.cls_prepare_export() not called")
    imagepack_id = self._imagepack.get().get_string()
    imagepack = AssetManager.get_instance().get_asset(imagepack_id)
    if imagepack is None:
      # 如果图片包不存在，我们就不用继续了
      MessageHandler.warning(self._tr_imagepack_not_found.format(imagepack=self._imagepack.get().get_string()))
      return False
    if not isinstance(imagepack, ImagePack):
      raise PPInternalError("Asset is not an image pack: " + self._imagepack.get().get_string())
    # 检查我们是否需要载入该图片包的所有图片，是的话把它加到 _fully_loaded_imagepacks 中
    if imagepack_id not in self._fully_loaded_imagepacks:
      is_require_full_load = False
      # 目前我们需要在 (1) 有 fork 参数时， (2) 需要改变导出的大小时载入图片
      if self._fork_params.get_num_operands() > 0:
        is_require_full_load = True
      else:
        for i in range(0, self._composites_target_sizes.get_num_operands()):
          if self._composites_target_sizes.get_operand(i).value != (imagepack.width, imagepack.height):
            is_require_full_load = True
            break
      if is_require_full_load:
        future_list = []
        self._fully_loaded_imagepacks[imagepack_id] = future_list
        for l in imagepack.layers:
          if l.patch.image is None:
            tp.submit(l.patch.get)
        for m in imagepack.masks:
          if m.mask is not None:
            if m.mask.image is None:
              tp.submit(m.mask.get)
        descriptor = ImagePack.get_descriptor_by_id(imagepack_id)
        name_tr = descriptor.get_name()
        if not isinstance(name_tr, (Translatable, str)):
          raise PPInternalError("Unexpected type for ImagePack name: " + str(type(name_tr)))
        name_str = name_tr.get() if isinstance(name_tr, Translatable) else name_tr
        MessageHandler.get().info(self._tr_loading_imagepack.format(imagepack=name_str))
    return True

  def run_export(self, output_rootdir : str) -> None:
    # 执行这个操作的导出，output_rootdir 是输出根目录
    # 一般会在一个新的线程中执行这个操作
    imagepack_id = self._imagepack.get().get_string()
    if self._fully_loaded_imagepacks is None:
      raise PPInternalError("ImagePackExportOpSymbol.cls_prepare_export() not called")
    if imagepack_id in self._fully_loaded_imagepacks:
      concurrent.futures.wait(self._fully_loaded_imagepacks[imagepack_id])
    imagepack = AssetManager.get_instance().get_asset(imagepack_id)
    if not isinstance(imagepack, ImagePack):
      raise PPInternalError("Asset is not an image pack: " + self._imagepack.get().get_string())
    # 如果需要 fork 操作，我们就执行 fork 操作
    if self._fork_params.get_num_operands() > 0:
      args : list[Color | PIL.Image.Image | str | tuple[str, Color] | None] = []
      for use in self._fork_params.operanduses():
        value = use.value
        if isinstance(value, NullLiteral):
          args.append(None)
        elif isinstance(value, StringLiteral):
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
        elif isinstance(value, ImageAssetData):
          image = value.load()
          args.append(image)
        elif isinstance(value, ImageAssetLiteralExpr):
          # 应该不会出现
          image = value.image.load()
          args.append(image)
        elif isinstance(value, ColorImageLiteralExpr):
          color = value.color.value
          args.append(color)
        else:
          raise PPInternalError("Unsupported fork parameter type: " + str(value))
      if len(args) < len(imagepack.masks):
        args += [None] * (len(imagepack.masks) - len(args))
      imagepack = imagepack.fork_applying_mask(args, enable_parallelization=True)
    with concurrent.futures.ThreadPoolExecutor() as executor:
      num_composites_export = min(self._composites_export_indices.get_num_operands(), self._composites_export_paths.get_num_operands())
      for i in range(0, num_composites_export):
        index = self._composites_export_indices.get_operand(i).value
        path = self._composites_export_paths.get_operand(i).get_string()
        x, y = self._composites_target_sizes.get_operand(i).value
        image = imagepack.get_composed_image(index)
        resizeTo = (x, y) if (imagepack.width != x or imagepack.height != y) else None
        executor.submit(self._export_image_helper, output_rootdir, path, image, resizeTo)
      num_layers_export = min(self._layers_export_indices.get_num_operands(), self._layers_export_paths.get_num_operands())
      for i in range(0, num_layers_export):
        index = self._layers_export_indices.get_operand(i).value
        path = self._layers_export_paths.get_operand(i).get_string()
        image = imagepack.layers[index].patch
        executor.submit(self._export_image_helper, output_rootdir, path, image, None)
    # 完成

  @staticmethod
  def _export_image_helper(rootdir : str, relpath : str, image : ImageWrapper, resizeTo : tuple[int,int] | None) -> None:
    CacheableOperationSymbol.report_exporting_file(relpath=relpath)
    fullpath = os.path.join(rootdir, relpath)
    os.makedirs(os.path.dirname(fullpath), exist_ok=True)
    image.save_to_path(fullpath, resizeTo=resizeTo)

class ImagePackExportDataBuilder:
  # 我们使用该类在将 VNModel 转化为后端 IR/AST 时对图片包的引用进行整理
  # 并在后端 IR/AST 中生成对应的 ImagePackExportOpSymbol
  # 如果任意部分需要定制，后端可以继承这个类并实现对应的方法

  # 以下需要子类提供实现(也可以用这里的默认实现)
  # ---------------------------------------------------------------------
  def get_instance_id(self, pack_id : str, fork_params : tuple | None, pack_instance_index : int) -> str:
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

  def add_value(self, value : ImagePackElementLiteralExpr, is_require_merged_image : bool = False, referenced_by : typing.Any | None = None) -> ImagePackElementReferenceInfo | str:
    # 添加一个图片包元素到 builder 中
    # 如果 is_require_merged_image 为 True，那么我们生成时会保证生成一个单独的图片，路径是返回值
    # 否则我们会尝试使用差分的方式来表示这个图片，返回值是 ImagePackElementReferenceInfo
    return self._add_value_impl(value, is_require_merged_image, referenced_by)

  @dataclasses.dataclass
  class LayerExportInfo:
    index : int
    path : str
    offset_x : int
    offset_y : int
    width : int
    height : int

  @dataclasses.dataclass
  class InstanceExportInfo:
    layer_exports : list # list[LayerExportInfo]
    composites : dict[str, tuple[int, ...]] # 差分组合的编码 -> 各个组成图层的编号
    first_referenced_by : typing.Any | None = None

  def finalize(self, dest : SymbolTableRegion[ImagePackExportOpSymbol]) -> dict[str, InstanceExportInfo]:
    # 完成添加图片包元素的操作，生成 ImagePackExportOpSymbol 并整理所有的图片包实例信息
    # 我们生成的导出操作中会包含单个文件的输出操作，但是这个函数的返回值只包含图片包实例的信息
    # 在 RenPy 中，我们会使用此函数的返回值来生成 layeredimage 语句，而单个文件可以直接使用文件名、不需要额外的处理
    return self._finalize_impl(dest)

  # 以下是内部实现
  # ---------------------------------------------------------------------

  @dataclasses.dataclass
  class ImagePackInstanceInfo:
    instance_id : str
    instance_path : str
    op : ImagePackExportOpSymbol
    descriptor : ImagePackDescriptor
    first_referenced_by : typing.Any | None = None
    # 为了保持 ImagePackExportOpSymbol 输出内容的稳定性，我们需要在加入导出内容前对其进行排序
    # 以下是用于记录已经导出的内容，以便 (1) 在加新值时复用结果，(2) 在 finalize() 中填充 ImagePackExportOpSymbol 时保持顺序
    composite_export_dict : dict[tuple[int, tuple[int, int]], str] = dataclasses.field(default_factory=dict) # (composite_index, target_size -> path)
    layer_export_dict : dict[int, str] = dataclasses.field(default_factory=dict) # layer_index -> path
    element_reference_dict : "dict[int, ImagePackExportDataBuilder.ImagePackElementReferenceInfo]" = dataclasses.field(default_factory=dict) # composite_index -> reference_info

  instance_map : dict[str, dict[tuple | None, ImagePackInstanceInfo]] # pack_id -> fork_params -> (instance_id, op)
  global_instance_count : int

  def __init__(self) -> None:
    self.instance_map = {}
    self.global_instance_count = 0

  def _add_value_impl(self, value : ImagePackElementLiteralExpr, is_require_merged_image : bool = False, referenced_by : typing.Any | None = None) -> ImagePackElementReferenceInfo | str:
    pack_id = value.pack_id.get_string()
    pack_map = None
    if pack_id in self.instance_map:
      pack_map = self.instance_map[pack_id]
    else:
      pack_map = {}
      self.instance_map[pack_id] = pack_map
    fork_params = value.get_fork_operands()
    instance_info = None
    if fork_params in pack_map:
      instance_info = pack_map[fork_params]
    else:
      instance_index = self.global_instance_count
      self.global_instance_count += 1
      instance_id = self.get_instance_id(pack_id, fork_params, instance_index)
      instance_path = self.place_imagepack_instance(instance_id, pack_id)
      op = ImagePackExportOpSymbol.create(context=value.context, imagepack=pack_id)
      if fork_params is not None:
        for param in fork_params:
          op.add_fork_param(param)
      descriptor = ImagePack.get_descriptor_by_id(pack_id)
      if not isinstance(descriptor, ImagePackDescriptor):
        raise PPInternalError("Image pack descriptor not found: " + pack_id)
      instance_info = ImagePackExportDataBuilder.ImagePackInstanceInfo(instance_id=instance_id, instance_path=instance_path, op=op, descriptor=descriptor, first_referenced_by=referenced_by)
      pack_map[fork_params] = instance_info
    target_size_tuple = (value.size.value[0], value.size.value[1])
    composite_code = value.composite_name.value
    composite_index = instance_info.descriptor.get_composite_index_from_code(composite_code)
    if is_require_merged_image or target_size_tuple != instance_info.descriptor.size:
      # 我们需要生成一个单独的图片
      key_tuple = (composite_index, target_size_tuple)
      if key_tuple in instance_info.composite_export_dict:
        return instance_info.composite_export_dict[key_tuple]
      path = self.place_imagepack_composite(instance_info.instance_id, pack_id, composite_code)
      instance_info.composite_export_dict[key_tuple] = path
      return path
    # 否则我们使用差分的方式来表示这个图片
    if composite_index in instance_info.element_reference_dict:
      return instance_info.element_reference_dict[composite_index]
    reference_info = ImagePackExportDataBuilder.ImagePackElementReferenceInfo(instance_id=instance_info.instance_id, composite_code=composite_code)
    instance_info.element_reference_dict[composite_index] = reference_info
    # 查看这个差分组合有没有用到之前没有记下要导出的图层，有的话为他们生成导出路径
    for layer_index in instance_info.descriptor.get_layers_from_composite_index(composite_index):
      if layer_index not in instance_info.layer_export_dict:
        layer_path = os.path.join(instance_info.instance_path, self.get_imagepack_layer_filename(pack_id, layer_index))
        instance_info.layer_export_dict[layer_index] = layer_path
    return reference_info

  def _finalize_impl(self, dest : SymbolTableRegion[ImagePackExportOpSymbol]) -> dict[str, InstanceExportInfo]:
    resultdict : dict[str, ImagePackExportDataBuilder.InstanceExportInfo] = {}
    for pack_id, pack_map in sorted(self.instance_map.items()):
      for info in pack_map.values():
        for layer_index, layer_path in sorted(info.layer_export_dict.items()):
          converted_index = IntLiteral.get(layer_index, info.op.context)
          converted_path = StringLiteral.get(layer_path, info.op.context)
          info.op.add_layer_export(converted_index, converted_path)
        for key_tuple, path in sorted(info.composite_export_dict.items()):
          converted_index = IntLiteral.get(key_tuple[0], info.op.context)
          converted_path = StringLiteral.get(path, info.op.context)
          converted_target_size = IntTuple2DLiteral.get(key_tuple[1], info.op.context)
          info.op.add_composite_export(converted_index, converted_path, converted_target_size)
        info.op.finish_init()
        dest.add(info.op)
        # 如果没有差分组合的引用（全是单独图片的输出），我们不需要生成这个图片包实例的 InstanceExportInfo
        if len(info.layer_export_dict) == 0:
          continue
        layer_exports = []
        composite_exports = {}
        for layer_index, layer_path in sorted(info.layer_export_dict.items()):
          info_src = info.descriptor.get_layer_info(layer_index)
          export_info = ImagePackExportDataBuilder.LayerExportInfo(index=layer_index, path=layer_path, offset_x=info_src.offset_x, offset_y=info_src.offset_y, width=info_src.width, height=info_src.height)
          layer_exports.append(export_info)
        for composite_index, reference_info in sorted(info.element_reference_dict.items()):
          composite_code = reference_info.composite_code
          layers = tuple(info.descriptor.get_layers_from_composite_index(composite_index))
          composite_exports[composite_code] = layers
        instance_export_info = ImagePackExportDataBuilder.InstanceExportInfo(layer_exports=layer_exports, composites=composite_exports, first_referenced_by=info.first_referenced_by)
        resultdict[info.instance_id] = instance_export_info
    return resultdict

