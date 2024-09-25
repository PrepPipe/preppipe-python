# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from .ast import *
from ..vnmodel import *
from ..util.imagepackexportop import ImagePackExportDataBuilder
from ..util.imagepack import *
from ..enginecommon.codegen import BackendCodeGenHelperBase

class WebGalImagePackExportDataBuilder(ImagePackExportDataBuilder):
  def _get_image_basedir(self, pack_id : str) -> str:
    descriptor : ImagePackDescriptor = ImagePack.get_descriptor_by_id(pack_id)
    match descriptor.packtype:
      case ImagePackDescriptor.ImagePackType.BACKGROUND:
        return "background"
      case _:
        return "figure"
  def place_imagepack_instance(self, instance_id : str, pack_id : str) -> str:
    # 当我们需要创建图片包实例时，我们应该把图片包放在哪
    # 图片包中的图层将保存在这个目录下，文件名由编号决定。
    # 此类会尝试将不同图片包实例中能共享的部分进行合并，同一图层可能被多个实例引用。
    return os.path.join(self._get_image_basedir(pack_id), pack_id)

  def place_imagepack_composite(self, instance_id : str, pack_id : str, composite_code : str) -> str:
    # 组合的图片应该放在哪
    return os.path.join(self._get_image_basedir(pack_id), 'E' + instance_id + '_' + composite_code + ".png")

class _WebGalCodeGenHelper(BackendCodeGenHelperBase[WebGalNode]):
  result : WebGalModel
  imagepack_handler : WebGalImagePackExportDataBuilder
  cur_ns : VNNamespace
  named_asset_dict : dict[Value, str]
  # 我们给每个 VNFunction 都创建一个单独的文件，同一文件下所有 VNFunction 都使用同一个名称前缀
  function_scenes : dict[VNFunction, str] # VNFunction -> 完整的文件相对路径名，包含后缀(.txt)



  def __init__(self, model : VNModel) -> None:
    super().__init__(model=model, imagepack_handler=WebGalImagePackExportDataBuilder())
    self.result = None
    self.cur_ns = None
    self.named_asset_dict = {}

    if not self.is_matchtree_installed():
      self.init_matchtable()

  @staticmethod
  def init_matchtable():
    # TODO instr table
    _WebGalCodeGenHelper.install_asset_basedir_matchtree({
      AudioAssetData : {
        VNStandardDeviceKind.O_VOICE_AUDIO :  "vocal",
        VNStandardDeviceKind.O_SE_AUDIO :     "vocal/soundeffect",
        VNStandardDeviceKind.O_BGM_AUDIO :    "bgm",
        None : "vocal/misc",
      },
      ImageAssetData : {
        VNStandardDeviceKind.O_BACKGROUND_DISPLAY : "background",
        VNStandardDeviceKind.O_FOREGROUND_DISPLAY : "figure",
        None: "figure/misc",
      }
      None : "misc",
      # TODO: video: "video"
    })
    _WebGalCodeGenHelper.install_asset_supported_formats({
      ImageAssetData : ["png", "jpeg", "jpg", "apng", "bmp", "webp", "gif"],
      AudioAssetData : ["mp3", "wav", "ogg"],
    })

  def _assign_function_labels(self, n : VNNamespace):
    for f in n.functions:
      srcfile = f.get_attr(VNFunction.ATTR_SRCFILE)
      if srcfile is not None:
        assert isinstance(srcfile, str)
      else:
        srcfile = ''
      srcfile_dir, srcfile_filename = os.path.split(srcfile)
      srcfile, _ = os.path.splitext(srcfile_filename)
      fullname = srcfile_dir + srcfile
      if f.name != srcfile:
        fullname = fullname + "_" + f.name
      self.function_scenes[f] = fullname + ".txt"

  def gen_terminator(self, terminator : VNTerminatorInstBase, **kwargs) -> WebGalNode:
    scene = kwargs['scene']
    raise NotImplementedError()

  def _codegen_function(self, f : VNFunction):
    fullpath = self.function_scenes[f]
    op = WebGalScriptFileOp.create(context=self.context, name=fullpath, loc=f.loc)
    self.result.add_script(op)
    # 因为 WebGal 的脚本没有明确的基本块的边界，所以我们直接把内容写到一个块内
    for block in f.body.blocks:
      codegen_kwargs = {"scene": op}
      self.codegen_block(block, **codegen_kwargs)
    # 然后再把 lost 的内容写到一个块内
    for block in f.lost.blocks:
      match block.name:
        case VNFunction.NAME_PREBODY:
          insert_before = op.body.body.front
          for op in block.body:
            if not isinstance(op, MetadataOp):
              raise ValueError("Unexpected operation in prebody block")
            op.clone().insert_before(insert_before)
        case VNFunction.NAME_POSTBODY:
          for op in block.body:
            if not isinstance(op, MetadataOp):
              raise ValueError("Unexpected operation in postbody block")
            op.body.body.push_back(op.clone())
        case _:
          continue

  def run(self) -> WebGalModel:
    # WebGal 暂不支持 DLC，所以我们把所有 VNNamespace 的内容都放一起
    assert self.result is None
    self.result = WebGalModel.create(self.model.context)
    for k in sorted(self.model.namespace.keys()):
      n = self.model.namespace.get(k)
      assert isinstance(n, VNNamespace)
      self.cur_ns = n
      self.collect_named_assets(n)
      self._assign_function_labels(n)
    for k in sorted(self.model.namespace.keys()):
      n = self.model.namespace.get(k)
      assert isinstance(n, VNNamespace)
      self.cur_ns = n
      for f in n.functions:
        self._codegen_function(f)

    imagepacks = self.imagepack_handler.finalize(self.result._cacheable_export_region) # pylint: disable=protected-access
    return self.result
