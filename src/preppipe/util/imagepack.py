# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
import json
import typing
import zipfile
import io
import pathlib
import sys
import time
import colorsys
import math
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import numpy as np
import scipy as sp
import matplotlib
import matplotlib.colors
import cv2
import yaml
import dataclasses
import enum
import unicodedata
import textwrap

from preppipe.irbase import IRValueMapper, Location, Operation

from ..exceptions import *
from ..commontypes import Color
from ..language import *
from ..tooldecl import ToolClassDecl
from ..assets.assetclassdecl import AssetClassDecl, NamedAssetClassBase
from ..assets.assetmanager import AssetManager
from ..assets.fileasset import FileAssetPack

@AssetClassDecl("imagepack")
@ToolClassDecl("imagepack")
class ImagePack(NamedAssetClassBase):
  TR_imagepack = TranslationDomain("imagepack")

  class MaskInfo:
    mask : PIL.Image.Image | None # 如果为 None 则表示该 mask 覆盖所有适用的基底图层
    basename : str # 保存时使用的名称（不含后缀）
    offset_x : int
    offset_y : int
    applyon : tuple[int,...] # 应该将该 mask 用于这里列出来的图层（空的话就是所有 base 图层都要）
    mask_color : Color

    # 如果支持 projective transform，以下是四个顶点（左上，右上，左下，右下）在 mask 中的坐标
    # https://stackoverflow.com/questions/14177744/how-does-perspective-transformation-work-in-pil
    projective_vertices : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]] | None

    def __init__(self, mask : PIL.Image.Image | None, mask_color : Color, offset_x : int = 0, offset_y : int = 0, projective_vertices : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]] | None = None, basename : str = '', applyon : typing.Iterable[int] | None = None) -> None:
      self.mask = mask
      self.mask_color = mask_color
      self.offset_x = offset_x
      self.offset_y = offset_y
      self.projective_vertices = projective_vertices
      self.basename = basename
      if applyon is not None:
        self.applyon = tuple(applyon)
      else:
        self.applyon = ()

  class LayerInfo:
    # 保存时每个图层的信息
    patch : PIL.Image.Image # RGBA uint8 图片
    basename : str # 保存时使用的名称（不含后缀）
    offset_x : int
    offset_y : int

    # 如果是 True 的话，该层视为可被 mask 的部分
    # （重构原图时，当 mask 与该图层有重叠时，我们在添加结果时需将 mask 参数赋予该图层）
    base : bool
    # 如果是 True 的话，该层可以不受限制地单独被选取
    toggle : bool

    def __init__(self, patch : PIL.Image.Image, offset_x : int = 0, offset_y : int = 0, base : bool = False, toggle : bool = False, basename : str = '') -> None:
      self.patch = patch
      self.basename = basename
      self.offset_x = offset_x
      self.offset_y = offset_y
      self.base = base
      self.toggle = toggle

  class TempLayerInfo(LayerInfo):
    # 该类仅用于在生成 ImagePack 时使用，给 patch 附带 np.ndarray 类型的值
    # 保存后读取时不会使用此类
    patch_ndarray : np.ndarray # 应该是一个有 RGBA 通道, uint8 类型的矩阵 (shape=(height, width, 4))

    def __init__(self, patch_ndarray : np.ndarray, offset_x : int = 0, offset_y : int = 0, base : bool = False, toggle : bool = False) -> None:
      super().__init__(patch=PIL.Image.fromarray(patch_ndarray, 'RGBA'), offset_x=offset_x, offset_y=offset_y, base=base, toggle=toggle)
      self.patch_ndarray = patch_ndarray

    # 需要以下函数来把对象当作键值
    # basename 不参与以下逻辑
    def __eq__(self, __value: object) -> bool:
      if not isinstance(__value, self.__class__):
        return False
      if __value.offset_x != self.offset_x or __value.offset_y != self.offset_y:
        return False
      return np.array_equal(__value.patch_ndarray, self.patch_ndarray)

    def __hash__(self) -> int:
      return hash((self.offset_x, self.offset_y, tuple(np.average(self.patch_ndarray, (0,1)))))

  class CompositeInfo:
    # 保存时每个差分的信息
    basename : str
    layers : list[int]

    def __init__(self, layers : typing.Iterable[int], basename : str = '') -> None:
      self.layers = list(layers)
      self.basename = basename

  # 当 imagepack 初始化完成后，里面的所有内容都被视作 immutable, 所有的修改操作都得换新值
  # mask 是一些可以作用于 base （基底图）上的修饰
  # 正常生成最终图片时我们不使用 mask
  # 当我们需要使用 mask 时，我们先 fork_applying_mask(), 使用修改后的 base 创建一个新的 imagepack (不再有mask)，然后再生成图片
  # fork_applying_mask() 时，所有 layer 中的图都直接引用，不会复制

  # 全局值
  width : int
  height : int

  masks : list[MaskInfo]
  layers : list[LayerInfo]
  composites : list[CompositeInfo]

  # 其他不用于核心功能的元信息，例如：作者，描述等
  # 某些元信息可能会被用于其他辅助功能，比如生成预览图、头像图等
  # 目前有以下元信息：
  #   "author": str, 作者
  #   "license": str, 发布许可（没有的话就是仅限内部使用）
  #     - "cc0": CC0 1.0 Universal
  #   "overview_scale" : float, 用于生成预览图的缩放比例
  #   "diff_croprect": tuple[int,int,int,int], 用于生成差分图的裁剪矩形
  opaque_metadata : dict[str, typing.Any]

  def __init__(self, width : int, height : int) -> None:
    self.width = width
    self.height = height
    self.masks = []
    self.layers = []
    self.composites = []
    self.opaque_metadata = {}

  @staticmethod
  def _write_image_to_zip(image : PIL.Image.Image, path : str, z : zipfile.ZipFile):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    z.writestr(path, buffer.getvalue())

  def is_imagedata_loaded(self) -> bool:
    return len(self.layers) > 0

  def write_zip(self, path : str):
    if not self.is_imagedata_loaded():
      raise PPInternalError("writing ImagePack zip without data")
    z = zipfile.ZipFile(path, "w", zipfile.ZIP_STORED)
    jsonout = {}
    used_filenames = set()
    used_filenames.add("manifest.json")
    def check_filename(filename : str):
      nonlocal used_filenames
      if filename in used_filenames:
        raise PPInternalError("Duplicated name:" + filename)
      used_filenames.add(filename)

    jsonout["size"] = (self.width, self.height)
    # masks
    if len(self.masks) > 0:
      json_masks = []
      for m in self.masks:
        basename = m.basename
        if basename != "None":
          if len(basename) == 0:
            basename = 'm' + str(len(json_masks))
          filename = basename + ".png"
          check_filename(filename)
          if m.mask is None:
            raise PPInternalError("Mask is None but basename is not None")
          self._write_image_to_zip(m.mask, filename, z)
        else:
          basename = None
        jsonobj : dict[str, typing.Any] = {"mask" : basename, "x":m.offset_x, "y":m.offset_y, "maskcolor" : m.mask_color.get_string()}
        if m.projective_vertices is not None:
          jsonobj["projective"] = m.projective_vertices
        if len(m.applyon) > 0:
          jsonobj["applyon"] = m.applyon
        json_masks.append(jsonobj)
      jsonout["masks"] = json_masks
    # layers
    def collect_layer_group(prefix : str, layers : list[ImagePack.LayerInfo]):
      result = []
      for l in layers:
        basename = l.basename
        if len(basename) == 0:
          basename = prefix + str(len(result))
        filename = basename + ".png"
        check_filename(filename)
        jsonobj : dict[str, typing.Any] = {"x":l.offset_x, "y":l.offset_y, "p": basename}
        flags = []
        if l.base:
          flags.append("base")
        if l.toggle:
          flags.append("toggle")
        if len(flags) > 0:
          jsonobj["flags"] = flags
        result.append(jsonobj)
        self._write_image_to_zip(l.patch, filename, z)
      return result
    jsonout["layers"] = collect_layer_group("l", self.layers)

    # composites
    if len(self.composites) > 0:
      json_composites = []
      comp_index = 0
      for c in self.composites:
        comp_index += 1
        basename = c.basename
        if len(basename) == 0:
          basename = 'c' + str(comp_index)
        jsonobj = {"l" : c.layers, "n" : basename}
        json_composites.append(jsonobj)
      jsonout["composites"] = json_composites

    # metadata
    if len(self.opaque_metadata) > 0:
      jsonout["metadata"] = self.opaque_metadata

    manifest = json.dumps(jsonout, ensure_ascii=False,indent=None,separators=(',', ':'))
    z.writestr("manifest.json", manifest)
    z.close()

  @staticmethod
  def create_from_zip(path : str):
    pack = ImagePack(0, 0)
    pack.read_zip(path)
    return pack

  def read_zip(self, path : str):
    if len(self.layers) > 0 or len(self.masks) > 0:
      raise PPInternalError("Cannot reload when data is already loaded")

    z = zipfile.ZipFile(path, "r")

    # Read manifest.json
    manifest_str = z.read("manifest.json")
    manifest = json.loads(manifest_str)
    if not isinstance(manifest, dict):
      raise PPInternalError("Invalid manifest.json")

    # Extract size information
    width, height = manifest["size"]
    if self.width == 0 and self.height == 0:
      self.width = width
      self.height = height
    else:
      if width != self.width or height != self.height:
        raise PPInternalError("ImagePack size mismatch: " + str((width, height)) + " != " + str((self.width, self.height)))

    # Read masks
    if "masks" in manifest:
      masks = []
      for mask_info in manifest["masks"]:
        mask_basename = mask_info["mask"]
        mask_img = None
        if mask_basename is not None:
          mask_filename = mask_info["mask"] + ".png"
          mask_img = PIL.Image.open(z.open(mask_filename))
        mask_color = Color.get(mask_info["maskcolor"])
        offset_x = mask_info["x"]
        offset_y = mask_info["y"]
        projective_vertices = mask_info.get("projective", None)
        applyon = mask_info.get("applyon", [])

        masks.append(ImagePack.MaskInfo(mask=mask_img, mask_color=mask_color, offset_x=offset_x, offset_y=offset_y, projective_vertices=projective_vertices, basename=mask_info["mask"], applyon=applyon))
      self.masks = masks

    # Read layers
    def read_layer_group(prefix, group_name):
      layers = []
      if group_name in manifest:
        for layer_info in manifest[group_name]:
          layer_filename = layer_info["p"] + ".png"
          offset_x = layer_info["x"]
          offset_y = layer_info["y"]
          base = "base" in layer_info.get("flags", [])
          toggle = "toggle" in layer_info.get("flags", [])
          layer_img = PIL.Image.open(z.open(layer_filename))
          layers.append(ImagePack.LayerInfo(patch=layer_img, offset_x=offset_x, offset_y=offset_y, base=base, toggle=toggle, basename=layer_info["p"]))
      return layers

    self.layers = read_layer_group("l", "layers")

    # Read composites
    if "composites" in manifest:
      composites = []
      for comp_info in manifest["composites"]:
        composites.append(ImagePack.CompositeInfo(layers=comp_info["l"], basename=comp_info["n"]))
      self.composites = composites

    # metadata
    if "metadata" in manifest:
      self.opaque_metadata = manifest["metadata"]

  def get_composed_image(self, index : int) -> PIL.Image.Image:
    if not self.is_imagedata_loaded():
      raise PPInternalError("Cannot compose images without loading the data")
    layer_indices = self.composites[index].layers
    if len(layer_indices) == 0:
      raise PPInternalError("Empty composition? some thing is probably wrong")
    if len(layer_indices) == 1:
      curlayer = self.layers[layer_indices[0]]
      # 如果该图层正好覆盖整个图像，则直接返回
      if curlayer.offset_x == 0 and curlayer.offset_y == 0 and curlayer.patch.width == self.width and curlayer.patch.height == self.height:
        return curlayer.patch.copy()

    result = PIL.Image.new("RGBA", (self.width, self.height))

    for li in layer_indices:
      layer = self.layers[li]
      extended_patch = PIL.Image.new("RGBA", (self.width, self.height))
      extended_patch.paste(layer.patch, (layer.offset_x, layer.offset_y))
      result = PIL.Image.alpha_composite(result, extended_patch)
    return result

  def add_mask(self, maskimg : PIL.Image.Image, maskcolor : Color, projective_vertices : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]] | None = None, basename : str = '', applyon : typing.Iterable[int] | None = None):
    bbox = maskimg.getbbox()
    if bbox is None:
      raise PPInternalError("Empty mask?")
    offset_x = bbox[0]
    offset_y = bbox[1]
    maskimg = maskimg.crop(bbox).convert("P", colors=2)
    mask = ImagePack.MaskInfo(mask=maskimg, mask_color=maskcolor, offset_x=offset_x, offset_y=offset_y, projective_vertices=projective_vertices, basename=basename, applyon=applyon)
    self.masks.append(mask)

  @staticmethod
  def ndarray_hsv_to_rgb(hsv : np.ndarray) -> np.ndarray:
    #return np.apply_along_axis(ImagePack.hsv_to_rgb, 1, hsv)
    return (matplotlib.colors.hsv_to_rgb(hsv) * 255).astype(np.uint8)

  @staticmethod
  def ndarray_rgb_to_hsv(rgb : np.ndarray) -> np.ndarray:
    #return np.apply_along_axis(ImagePack.rgb_to_hsv, 1, rgb)
    return matplotlib.colors.rgb_to_hsv(rgb.astype(np.float32)/255.0)

  @staticmethod
  def change_color_hsv_pillow(base_data : np.ndarray, mask_data : np.ndarray | None, base_color : Color, new_color : Color | np.ndarray) -> np.ndarray:
    # base_data 应该是 RGB[A] 模式, mask_data 应该是 L （灰度）或者 1 (黑白)模式
    # 检查输入
    base_shape = base_data.shape
    assert len(base_shape) == 3  and base_shape[2] in (3, 4)

    if mask_data is not None:
      mask_shape = mask_data.shape
      assert len(mask_shape) == 2 and base_shape[0] == mask_shape[0] and base_shape[1] == mask_shape[1]
    base_hsv = ImagePack.ndarray_rgb_to_hsv(np.array(base_color.to_tuple_rgb()))

    # Find the indices where the mask is non-zero (where the region is)
    if mask_data is None:
      if base_shape[2] == 4:
        non_zero_indices = np.where(base_data[:,:,3] > 0)
      else:
        non_zero_indices = np.where(np.ones((base_shape[0], base_shape[1]), dtype=np.uint8))
    else:
      if base_shape[2] == 4:
        non_zero_indices = np.where((mask_data > 0) & (base_data[:,:,3] > 0))
      else:
        non_zero_indices = np.where(mask_data > 0)
    ImagePack.printstatus("non_zero_indices done")

    base_alpha = None
    if base_shape[2] == 4:
      base_alpha = base_data[non_zero_indices][:,3:4]
    base_forchange = base_data[non_zero_indices][:,:3]

    # Convert the RGB values in the region to HSV
    original_hsv = ImagePack.ndarray_rgb_to_hsv(base_forchange)

    # step 1: compute the base color vec and get the delta
    compensate_hsv = np.copy(original_hsv)
    compensate_hsv[:, 0] = base_hsv[0]
    base_rgb = ImagePack.ndarray_hsv_to_rgb(compensate_hsv)
    delta_rgb = base_forchange.astype(np.int16) - base_rgb.astype(np.int16)
    ImagePack.printstatus("base_decomp done")

    # step 2: compute the pure new color
    hsv_values = np.copy(original_hsv)
    if isinstance(new_color, Color):
      new_hsv = ImagePack.ndarray_rgb_to_hsv(np.array(new_color.to_tuple_rgb()))
      saturation_adjust = new_hsv[1] - base_hsv[1]
      value_adjust = new_hsv[2] - base_hsv[2]

      hsv_values[:, 0] = new_hsv[0]
      hsv_values[:, 1] = np.clip(hsv_values[:, 1] + saturation_adjust, 0, 1)
      hsv_values[:, 2] = np.clip(hsv_values[:, 2] + value_adjust, 0, 1)
    else:
      # new_color 应该是一个和原图等大小的 np.ndarray
      # 唯一的区别是 new_color 可以没有 alpha (实际上有了也会被忽略)
      newcolor_shape = new_color.shape
      assert len(newcolor_shape) == 3 and newcolor_shape[0] == base_shape[0] and newcolor_shape[1] == base_shape[1]
      newcolor_masked = new_color[non_zero_indices][:,:3]
      new_hsv = ImagePack.ndarray_rgb_to_hsv(newcolor_masked)
      saturation_adjust = new_hsv[:,1] - base_hsv[1]
      value_adjust = new_hsv[:,2] - base_hsv[2]

      hsv_values[:, 0] = new_hsv[:, 0]
      hsv_values[:, 1] = np.clip(hsv_values[:, 1] + saturation_adjust, 0, 1)
      hsv_values[:, 2] = np.clip(hsv_values[:, 2] + value_adjust, 0, 1)
    ImagePack.printstatus("hsv_values done")

    # Convert the modified HSV values back to RGB
    new_rgb = ImagePack.ndarray_hsv_to_rgb(hsv_values)
    new_rgb = np.clip(new_rgb.astype(np.int16) + delta_rgb, 0, 255).astype(np.uint8)

    # Combine RGB values with the original alpha channel
    if base_shape[2] == 4:
      assert base_alpha is not None
      nd = np.hstack((new_rgb,base_alpha))
      base_data[non_zero_indices] = nd
    else:
      base_data[non_zero_indices] = new_rgb

    return base_data

  TEXT_IMAGE_FONT_ASSET : typing.ClassVar[str] = "file-font-SourceHanSerif-thirdparty-Adobe"
  TEXT_IMAGE_FONT_PATH : typing.ClassVar[str] = "SourceHanSerif-Regular.ttc"

  @staticmethod
  def get_font_for_text_image(fontsize : int) -> PIL.ImageFont.ImageFont | PIL.ImageFont.FreeTypeFont:
    inst = AssetManager.get_instance()
    if SourceHanSerif := inst.get_asset(ImagePack.TEXT_IMAGE_FONT_ASSET):
      fontpath = os.path.join(SourceHanSerif.path, ImagePack.TEXT_IMAGE_FONT_PATH)
      return PIL.ImageFont.truetype(fontpath, fontsize)
    return PIL.ImageFont.load_default()

  @staticmethod
  def create_text_image_for_mask(text : str, color : Color | None, start_points : int, size : tuple[int, int], background_color : Color | None) -> PIL.Image.Image:
    def _is_character_fullwidth(ch : str):
      # https://stackoverflow.com/questions/23058564/checking-a-character-is-fullwidth-or-halfwidth-in-python
      return unicodedata.east_asian_width(ch) in ('F', 'W', 'A')
    text_height_multiplier = 1.1
    text_width_multiplier = 0.55
    min_text_size = 12
    for ch in text:
      if _is_character_fullwidth(ch):
        text_width_multiplier = 1.1
        break

    paragraphs = text.splitlines()
    def create_image_with_text(font_size: int, force_draw : bool = False):
      max_charcnt = max(1, int(math.floor(size[0] / (font_size * text_width_multiplier))))
      lines = []
      for p in paragraphs:
        lines.extend(textwrap.wrap(p, width=max_charcnt))
      text_height = font_size * len(lines) * text_height_multiplier
      if not force_draw and text_height > size[1]:  # If text height exceeds image height, return None
        return None

      font = ImagePack.get_font_for_text_image(font_size)
      color_tuple = (255, 255, 255, 0) if background_color is None else (background_color.r, background_color.g, background_color.b, 255)
      image = PIL.Image.new("RGBA", size, color_tuple)
      draw = PIL.ImageDraw.Draw(image)
      y_text = max(0, (size[1] - text_height) // 2)
      for line in lines:
        text_width = draw.textlength(line, font=font)
        text_height = font_size * text_height_multiplier
        x_text = max(0, (size[0] - text_width) // 2)
        draw.text((x_text, y_text), line, font=font, fill=(color.r, color.g, color.b, 255) if color else (0, 0, 0, 255))
        y_text += text_height

      return image

    font_size = start_points
    image = create_image_with_text(font_size)
    while image is None and font_size > min_text_size:
      font_size -= max(2, int(font_size/8))
      if font_size < min_text_size:
        font_size = min_text_size
      image = create_image_with_text(font_size)

    if image is None:
      image = create_image_with_text(font_size, force_draw = True)
    return image

  @staticmethod
  def get_starting_font_point_size(width : int, height : int) -> int:
    # 如果我们需要在选区图中加文字，此函数计算我们尝试的初始字体大小
    # 如果字太多的话会将字号缩小，所以这里是我们尝试的最大字号
    # 对于一个 16*9 的图，每行应该可以填大概30字
    # 不管对于任何分辨率，至少 24 点的字体是合适的
    return max(24, int(width/30*0.75))

  @staticmethod
  def get_projective_rectangular_size_for_text(vertices : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]]) -> tuple[int,int]:
    # 从四个顶点中计算出一个矩形的大小
    # 顶点是左上，右上，左下，右下
    # 返回的是宽和高
    xdiffmin = min(vertices[1][0] - vertices[0][0], vertices[3][0] - vertices[2][0])
    ydiffmin = min(vertices[2][1] - vertices[0][1], vertices[3][1] - vertices[1][1])
    return (xdiffmin, ydiffmin)

  def fork_applying_mask(self, args : list[Color | PIL.Image.Image | str | tuple[str, Color] | None]):
    # 创建一个新的 imagepack, 将 mask 所影响的部分替换掉
    if not self.is_imagedata_loaded():
      raise PPInternalError("Cannot fork_applying_mask() without data")
    if len(args) != len(self.masks):
      raise PPInternalError("Mask arguments not match: " + str(len(self.masks)) + " expected, " + str(len(args)) + " provided")
    resultpack = ImagePack(self.width, self.height)

    # 除了 mask 和 layers, 其他都照搬
    resultpack.composites = self.composites

    # 开始搬运 layers
    for layerindex in range(len(self.layers)): # pylint: disable=consider-using-enumerate
      l = self.layers[layerindex]
      if not l.base:
        resultpack.layers.append(l)
        continue
      cur_base = None
      ImagePack.printstatus("base apply start")
      for m, arg in zip(self.masks, args):
        # 如果当前 mask 不需要改动则跳过
        if arg is None:
          continue
        # 如果当前 mask 并不适用于该层则跳过
        if len(m.applyon) > 0 and layerindex not in m.applyon:
          continue
        # 如果当前 mask 不支持图像输入但给了图像则报错
        if m.projective_vertices is None and not isinstance(arg, Color):
          raise PPInternalError("Mask does not support image input")

        # 当前 mask 需要加在图层上
        # 将 base 转化为合适的形式
        if cur_base is None:
          # 把图弄全
          if l.patch.mode in ("RGBA", "RGB"):
            patch_array = np.array(l.patch)
          else:
            patch_array = np.array(l.patch.convert("RGBA"))
          cur_base = np.zeros((self.height, self.width, patch_array.shape[2]), dtype=np.uint8)
          cur_base[l.offset_y:l.offset_y+l.patch.height, l.offset_x:l.offset_x+l.patch.width] = patch_array
          ImagePack.printstatus("base prep done")

        # 在开始前，如果输入是图像且需要进行转换，则执行操作
        if isinstance(arg, Color):
          converted_arg = arg
        else:
          # 之前应该检查过了
          assert m.projective_vertices is not None
          if not isinstance(arg, PIL.Image.Image):
            start_point_size = ImagePack.get_starting_font_point_size(self.width, self.height)
            text_image_size = ImagePack.get_projective_rectangular_size_for_text(m.projective_vertices)
            text = ''
            color = None
            if isinstance(arg, str):
              text = arg
            elif isinstance(arg, tuple):
              text, color = arg
            arg = ImagePack.create_text_image_for_mask(text, color, start_point_size, text_image_size, m.mask_color)
          converted_arg = np.full((self.height, self.width, 3), m.mask_color.to_float_tuple_rgb(), dtype=np.float32)
          srcpoints = np.matrix([[0, 0], [arg.width-1, 0], [0, arg.height-1], [arg.width-1, arg.height-1]], dtype=np.float32)
          dstpoints = np.matrix(m.projective_vertices, dtype=np.float32)
          projective_matrix = cv2.getPerspectiveTransform(srcpoints, dstpoints)
          converted_arg = cv2.warpPerspective(src=np.array(arg.convert("RGB")).astype(np.float32)/255.0, M=projective_matrix, dsize=(self.width, self.height), dst=converted_arg, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_TRANSPARENT)
          converted_arg = (converted_arg * 255.0).astype(np.uint8)

        # 转换当前的 mask
        mask_data = None
        if m.mask is not None:
          mask_data = PIL.Image.new("L", (self.width, self.height), color=0)
          mask_data.paste(m.mask.convert("L"), (m.offset_x, m.offset_y))
          mask_data = np.array(mask_data)

        cur_base = ImagePack.change_color_hsv_pillow(cur_base, mask_data, m.mask_color, converted_arg)
        ImagePack.printstatus("mask applied")
      if cur_base is None:
        # 该图层可以原封不动地放到结果里
        resultpack.layers.append(l)
      else:
        if cur_base.shape[2] == 3:
          mode = "RGB"
        else:
          mode = "RGBA"
        newbase = PIL.Image.fromarray(cur_base, mode)
        bbox = newbase.getbbox()
        if bbox is None:
          raise PPInternalError("Empty base after applying mask?")
        offset_x, offset_y, xmax, ymax = bbox
        newlayer = ImagePack.LayerInfo(newbase.crop(bbox), offset_x=offset_x, offset_y=offset_y, base=True, toggle=l.toggle, basename=l.basename)
        resultpack.layers.append(newlayer)
        ImagePack.printstatus("crop done")
    return resultpack

  @staticmethod
  def inverse_pasting(base : PIL.Image.Image, result : PIL.Image.Image) -> np.ndarray | None:
    # 假设图片将以 paste 的方式进行叠层，计算使用的 patch
    base_array = np.array(base)
    result_array = np.array(result)

    # Create an empty patch image with transparent background
    patch_image = np.zeros_like(base_array)

    # Find pixels where the values are different
    diff_mask = np.any(base_array != result_array, axis=-1)
    if not np.any(diff_mask):
      return None

    patch_image[diff_mask] = result_array[diff_mask]
    return patch_image

  @staticmethod
  def inverse_alpha_composite(base : PIL.Image.Image, result : PIL.Image.Image) -> np.ndarray | None:
    # 假设图片将以 alpha blending 的方式叠层，计算使用的 patch
    # 基于维基百科中的算式：
    # 假设 a_b, a_r, a_p 是 base, result, 和 patch 的 alpha,
    # C_b, C_r, C_a 是颜色值，则：(所有值都在 [0-1] 区间)
    # a_r = a_p + a_b(1-a_p)
    # C_r*a_r = C_p*a_p + C_b*a_b*(1-a_p)
    base_array = np.array(base)
    result_array = np.array(result)

    # Create an empty patch image with transparent background
    patch_image = np.zeros_like(base_array)

    # Find pixels where the values are different
    diff_mask = np.any(base_array != result_array, axis=-1)
    if not np.any(diff_mask):
      return None

    indices = np.nonzero(diff_mask)
    rraw = result_array[indices]
    braw = base_array[indices]
    r = rraw.astype(np.float32) / 255.0
    b = braw.astype(np.float32) / 255.0
    a_r = r[:,3:4]
    a_b = b[:,3:4]
    C_r = r[:,:3]
    C_b = b[:,:3]
    # 首先算 alpha
    # 分三种情况：
    # 1. a_r == a_b == 1.0: 选尽可能小的 a_p
    # 2. a_r > a_b: 唯一的 a_p，可以算
    # 3. 其他情况：a_p = 0
    a_p = np.zeros_like(a_r)
    case_2_indices = np.nonzero(rraw[:,3:4] > braw[:,3:4])
    if len(case_2_indices[0]) > 0:
      a_p[case_2_indices] = (a_r[case_2_indices]-a_b[case_2_indices]) / (1.0-a_b[case_2_indices])

    case_1_indices = np.nonzero((rraw[:,3:4] == 255) & (braw[:,3:4] == 255))[0]
    if len(case_1_indices) > 0:
      # 基本算法是 a_p = (CrAr - CbAb) / (Cp - CbAb), 取最小的 a_p
      # 如果 CrAr >  CbAb, Cp 取1, a_p = (CrAr - CbAb) / (1.0 - CbAb)
      # 如果 CrAr <= CbAb, Cp 取0, a_p = (CrAr - CbAb) / (0.0 - CbAb)
      CrAr = np.multiply(C_r[case_1_indices], a_r[case_1_indices])
      CbAb = np.multiply(C_b[case_1_indices], a_b[case_1_indices])
      dividend = CrAr - CbAb
      divisor = np.where(dividend > 0, (1.0 - CbAb), (0.0 - CbAb))
      aptmp = np.divide(dividend, divisor)
      aptmp = np.nan_to_num(aptmp, copy=False)
      aptmp[aptmp < 0.0] = 0.0
      aptmp[aptmp > 1.0] = 1.0
      aptmp = np.amax(aptmp, axis=1)
      a_p[case_1_indices] = np.reshape(aptmp, (-1,1))

    ap_uint8 = (a_p * 255).astype(np.uint8)
    a_p = ap_uint8.astype(np.float32) / 255.0
    C_p = np.zeros_like(C_r)
    case_2_indices = np.nonzero(ap_uint8[:,0] == 255)
    if len(case_2_indices) > 0:
      C_p[case_2_indices] = C_r[case_2_indices]

    case_1_indices = np.nonzero((ap_uint8[:,0] < 255) & (ap_uint8[:,0] > 0))
    if len(case_1_indices) > 0:
      C_p[case_1_indices] = (C_r[case_1_indices]*a_r[case_1_indices] - C_b[case_1_indices]*(a_b[case_1_indices]*(1.0-a_p[case_1_indices])))/a_p[case_1_indices]
      C_p[C_p < 0.0] = 0.0
      C_p[C_p > 1.0] = 1.0

    #C_p = np.nan_to_num(np.where(a_p < 1.0, (C_r*a_r - C_b*(a_b*(1.0-a_p)))/a_p, C_r))
    results = np.hstack([C_p, a_p]) * 255.0
    # Update the patch image with non-matching pixels
    patch_image[indices] = results.astype(np.uint8)

    # Return the patch image
    return patch_image

  @staticmethod
  def infer_base_image(images : list[PIL.Image.Image]) -> PIL.Image.Image:
    raise PPNotImplementedError()

  @staticmethod
  def create_image_pack_entry(images : list[PIL.Image.Image], base_image : PIL.Image.Image | None = None):
    # codenames 放所有的 tr codename
    # trs 放所有的 tr 的值
    # 假设某一图片项对应的分别是 codename 和 tr ，则其名称可以用 TR_xxx.tr(codename, *tr) 来创建
    if not isinstance(images, list):
      raise PPInternalError()
    if len(images) == 0:
      raise PPInternalError()
    if base_image is None:
      base_image = ImagePack.infer_base_image(images)

    width = base_image.width
    height = base_image.height

    result_pack = ImagePack(width, height)
    result_pack.layers.append(ImagePack.LayerInfo(base_image, base=True))

    layer_dict : dict[ImagePack.LayerInfo, int] = {}
    layers = result_pack.layers

    def get_layer_index(offset_x : int, offset_y : int, patch : np.ndarray):
      nonlocal layer_dict
      nonlocal layers
      l = ImagePack.TempLayerInfo(patch, offset_x, offset_y)
      index = layer_dict.get(l)
      if index is not None:
        return index
      index = len(layers)
      layers.append(l)
      layer_dict[l] = index
      return index

    # 为了合并相近的 patch
    merge_distance = max(5, int(min(width,height)/100))
    tmp_y, tmp_x = np.ogrid[-merge_distance: merge_distance + 1, -merge_distance: merge_distance + 1]
    structure_matrix = tmp_x**2 + tmp_y**2 <= merge_distance**2
    # kernel_size = int(2 * merge_distance) + 1
    # kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)

    for img in images:
      ImagePack.printstatus("handling image " + str(len(result_pack.composites)))
      if img.width != width:
        raise PPInternalError()
      if img.height != height:
        raise PPInternalError()

      patch_image = ImagePack.inverse_alpha_composite(base_image, img)
      ImagePack.printstatus("invcomp done")
      if patch_image is None:
        # 该图就是基底图
        result_pack.composites.append(ImagePack.CompositeInfo([0]))
        continue

      # patch_image 是全图的 Patch, np array, RGBA
      #nonzero_regions = patch_image[:, :, 3]
      # 为了给后面的部分加速，我们只选取有内容的部分
      rows = np.any(patch_image, axis=1)
      cols = np.any(patch_image, axis=0)
      ymin, ymax = np.where(rows)[0][[0, -1]]
      xmin, xmax = np.where(cols)[0][[0, -1]]
      patch_base_x = int(xmin)
      patch_base_y = int(ymin)
      patch_image_trunc = patch_image[ymin:ymax+1, xmin:xmax+1, :]
      nonzero_regions = patch_image_trunc[:, :, 3]

      # fuzzy match 把相近的部分连接起来
      merged_nonzero_regions = sp.ndimage.binary_dilation(nonzero_regions, structure=structure_matrix)
      #merged_regions = sp.ndimage.convolve(nonzero_regions, kernel, mode='constant', cval=0)
      #merged_nonzero_regions = np.logical_or(nonzero_regions, merged_regions)
      ImagePack.printstatus("merged zones")

      # Label connected components
      labeled_regions, num_labels = sp.ndimage.label(merged_nonzero_regions)
      ImagePack.printstatus("labeling done")

      stack = [0]
      for label_id in range(1, num_labels + 1):
        component_mask = labeled_regions == label_id
        component_mask_imp = np.ma.masked_where(nonzero_regions == 0, component_mask, copy=False)
        indices = np.nonzero(component_mask_imp)
        rows, cols = indices
        col_min, col_max = np.min(cols), np.max(cols)
        row_min, row_max = np.min(rows), np.max(rows)
        patch_width = col_max - col_min + 1
        patch_height = row_max - row_min + 1
        patch_array = np.zeros((patch_height, patch_width, 4), dtype=patch_image.dtype)
        rowarray, colarray = np.subtract(indices, ((row_min,), (col_min,)))
        patch_array[(rowarray, colarray)] = patch_image_trunc[indices]
        layer = get_layer_index(patch_base_x + int(col_min), patch_base_y + int(row_min), patch_array)
        stack.append(layer)
      result_pack.composites.append(ImagePack.CompositeInfo(stack))
    return result_pack

  def optimize_masks(self):
    # 对任意一个选区，如果它现在有图片，但是它所覆盖的范围可以近似为全图，则把这个图片去掉以减小文件大小
    # 对于选区和基底图的操作的代码都是从 fork_applying_mask() 中复制过来的
    for m in self.masks:
      if m.mask is None:
        continue
      isFullyCovers = True
      mask_img = PIL.Image.new("L", (self.width, self.height), color=0)
      mask_img.paste(m.mask.convert("L"), (m.offset_x, m.offset_y))
      mask_data = np.array(mask_img)
      # 如果 mask_data 全是非零值，那么就是全图，我们已经可以确定了
      if not np.all(mask_data > 0):
        # 在不全是非零值的情况下继续检查
        def check_base_cover(l : ImagePack.LayerInfo) -> bool:
          nonlocal isFullyCovers
          # 如果当前基底图没有 alpha 通道，那么就不可能覆盖全图
          if l.patch.mode != "RGBA":
            isFullyCovers = False
            return True
          patch_array = np.array(l.patch)
          base_data = np.zeros((self.height, self.width, patch_array.shape[2]), dtype=np.uint8)
          base_data[l.offset_y:l.offset_y+l.patch.height, l.offset_x:l.offset_x+l.patch.width] = patch_array
          reference_non_zero_indices = np.where((mask_data > 0) & (base_data[:,:,3] > 0))
          new_non_zero_indices = np.where(base_data[:,:,3] > 0)
          if not np.equal(reference_non_zero_indices, new_non_zero_indices).all():
            isFullyCovers = False
            return True
          return False
        if m.applyon is None or len(m.applyon) == 0:
          for layer in self.layers:
            if layer.base:
              if check_base_cover(layer):
                break
        else:
          for layerindex in m.applyon:
            if check_base_cover(self.layers[layerindex]):
              break
      if isFullyCovers:
        m.mask = None
        m.basename = "None"

  def get_summary_no_variations(self) -> 'ImagePackSummary':
    # 在该图片组没有使用基底图变体时生成 ImagePackSummary
    # 我们需要以以下算法决定基底图成图和差分图：
    # 1. 遍历每个差分组合，找到它们的基底图部分
    # 2. 如果这个基底图的组合已经出现过了，那么这就作为差分图
    # 3. 如果这个基底图的组合没有出现过，那么这就作为基底图
    # base_index_map 用来检查基底图组合是否出现过
    base_index_map : dict[tuple[int, ...], int] = {}
    bases = []
    basenames = []
    diffs = []
    diffnames = []
    for i, info in enumerate(self.composites):
      name = info.basename
      indices = info.layers
      base_indices = tuple([x for x in indices if self.layers[x].base])
      if base_indices in base_index_map:
        # 这是一个差分图
        image = self.get_composed_image(i)
        if croprect := self.opaque_metadata["diff_croprect"]:
          box = tuple(croprect)
          if len(box) != 4:
            raise PPInternalError("Invalid croprect")
          image = image.crop(box)
        diffs.append(image)
        diffnames.append(name)
      else:
        # 这是一个基底图
        base_index_map[base_indices] = i
        image = self.get_composed_image(i)
        bases.append(image)
        basenames.append(name)
    # 最后生成 ImagePackSummary
    result = ImagePackSummary()
    overview_scale = self.opaque_metadata.get("overview_scale", None)
    if overview_scale is not None:
      if not isinstance(overview_scale, (int, float)) or overview_scale <= 0 or overview_scale > 1:
        raise PPInternalError("Invalid overview_scale")
    for image, name in zip(bases, basenames):
      if overview_scale is not None:
        image = image.resize((int(image.width * overview_scale), int(image.height * overview_scale)), PIL.Image.Resampling.LANCZOS)
      result.add_base(image, name)
    for image, name in zip(diffs, diffnames):
      if overview_scale is not None:
        image = image.resize((int(image.width * overview_scale), int(image.height * overview_scale)), PIL.Image.Resampling.LANCZOS)
      result.add_diff(image, name)
    return result

  TR_imagepack_overview_author = TR_imagepack.tr("overview_author",
    en="Author: {name}. This image is created by the PrepPipe compiler.",
    zh_cn="作者：{name}。 本图由语涵编译器生成。",
    zh_hk="作者：{name}。 本圖由語涵編譯器生成。",
  )
  TR_imagepack_overview_distributenote_internal = TR_imagepack.tr("overview_distributenote_internal",
    en="This image pack is distributed only for internal use. Do not distribute or use it outside of its intended purpose.",
    zh_cn="本图包仅供内部使用。请勿扩散或是用在与原用途不符的地方。",
    zh_hk="本圖包僅供內部使用。請勿擴散或是用在與原用途不符的地方。",
  )
  TR_imagepack_overview_distributenote_cc0 = TR_imagepack.tr("overview_distributenote_cc0",
    en="This image pack is distributed under the CC0 1.0 Universal (CC0 1.0) Public Domain Dedication.",
    zh_cn="本图包以 CC0 1.0 通用 (CC0 1.0) 公共领域贡献方式分发。",
    zh_hk="本圖包以 CC0 1.0 通用 (CC0 1.0) 公共領域貢獻方式分發。",
  )

  def write_overview_image(self, path : str):
    # 生成一个预览图
    # 先使用辅助函数生成 ImagePackSummary
    summary = self.get_summary_no_variations()
    # 再把元数据加上
    # 作者信息
    if author := self.opaque_metadata.get("author", None):
      author_comment = self.TR_imagepack_overview_author.format(name=author)
      summary.comments.append(author_comment)
    # 许可信息
    # 没写许可就是内部使用
    license_tr = self.TR_imagepack_overview_distributenote_internal
    if license := self.opaque_metadata.get("license", None):
      if license == "cc0":
        license_tr = self.TR_imagepack_overview_distributenote_cc0
      else:
        raise PPInternalError("Unknown license: " + license)
    summary.comments.append(license_tr.get())
    summary.write(pngpath=path)

  TR_imagepack_yamlparse_layers = TR_imagepack.tr("layers",
    en="layers",
    zh_cn="图层",
    zh_hk="圖層",
  )
  TR_imagepack_yamlparse_masks = TR_imagepack.tr("masks",
    en="masks",
    zh_cn="选区",
    zh_hk="選區",
  )
  TR_imagepack_yamlparse_composites = TR_imagepack.tr("composites",
    en="composites",
    zh_cn="组合",
    zh_hk="組合",
  )
  TR_imagepack_yamlparse_metadata = TR_imagepack.tr("metadata",
    en="metadata",
    zh_cn="元数据",
    zh_hk="元數據",
  )
  TR_imagepack_yamlparse_flags = TR_imagepack.tr("flags",
    en="flags",
    zh_cn="特殊标记",
    zh_hk="特殊標記",
  )
  TR_imagepack_yamlparse_base = TR_imagepack.tr("base",
    en="base",
    zh_cn="基底",
    zh_hk="基底",
  )
  TR_imagepack_yamlparse_toggle = TR_imagepack.tr("toggle",
    en="toggle",
    zh_cn="可选",
    zh_hk="可選",
  )
  TR_imagepack_yamlparse_maskcolor = TR_imagepack.tr("maskcolor",
    en="basecolor",
    zh_cn="基础颜色",
    zh_hk="基礎顏色",
  )
  TR_imagepack_yamlparse_applyon = TR_imagepack.tr("applyon",
    en="applyon",
    zh_cn="适用于",
    zh_hk="適用於",
  )
  TR_imagepack_yamlparse_projective = TR_imagepack.tr("projective",
    en="imagecoords",
    zh_cn="图像坐标",
    zh_hk="圖像坐標",
  )
  TR_imagepack_yamlparse_topleft = TR_imagepack.tr("topleft",
    en="topleft",
    zh_cn="左上",
    zh_hk="左上",
  )
  TR_imagepack_yamlparse_topright = TR_imagepack.tr("topright",
    en="topright",
    zh_cn="右上",
    zh_hk="右上",
  )
  TR_imagepack_yamlparse_bottomleft = TR_imagepack.tr("bottomleft",
    en="bottomleft",
    zh_cn="左下",
    zh_hk="左下",
  )
  TR_imagepack_yamlparse_bottomright = TR_imagepack.tr("bottomright",
    en="bottomright",
    zh_cn="右下",
    zh_hk="右下",
  )

  @staticmethod
  def convert_mask_image(mask : PIL.Image.Image) -> PIL.Image.Image:
    # 如果有 alpha 的话，只要 alpha 不是0就算是选区
    # 如果没有 alpha 的话，只要 RGB 不是纯黑就算是选区
    if mask.mode == "1":
      return mask
    if mask.mode == "L":
      maxchannel = np.array(mask)
    elif mask.mode == "RGBA":
      ma = np.array(mask)
      maxchannel = ma[:,:,3] # alpha
    else:
      ma = np.array(mask.convert("RGB"))
      maxchannel = np.maximum.reduce(ma, 2)
    ra = np.uint8(maxchannel > 0) * 255
    return PIL.Image.fromarray(ra, "L").convert("1", dither=PIL.Image.Dither.NONE)

  @staticmethod
  def build_image_pack_from_yaml(yamlpath : str):
    basepath = os.path.dirname(os.path.abspath(yamlpath))
    with open(yamlpath, "r", encoding="utf-8") as f:
      yamlobj = yaml.safe_load(f)
      result = ImagePack(0, 0)
      layers = None
      masks = None
      composites = None
      metadata = None
      for k in yamlobj.keys():
        if k in ImagePack.TR_imagepack_yamlparse_layers.get_all_candidates():
          layers = yamlobj[k]
        elif k in ImagePack.TR_imagepack_yamlparse_masks.get_all_candidates():
          masks = yamlobj[k]
        elif k in ImagePack.TR_imagepack_yamlparse_composites.get_all_candidates():
          composites = yamlobj[k]
        elif k in ImagePack.TR_imagepack_yamlparse_metadata.get_all_candidates():
          metadata = yamlobj[k]
        else:
          raise PPInternalError("Unknown key: " + k + "(supported keys: "
                                + str(ImagePack.TR_imagepack_yamlparse_layers.get_all_candidates()) + ", "
                                + str(ImagePack.TR_imagepack_yamlparse_masks.get_all_candidates()) + ", "
                                + str(ImagePack.TR_imagepack_yamlparse_composites.get_all_candidates()) + ", "
                                + str(ImagePack.TR_imagepack_yamlparse_metadata.get_all_candidates()) + ")")
      if layers is None:
        raise PPInternalError("No layers in " + yamlpath)
      layer_dict : dict[str, int] = {}
      for imgpathbase, d in layers.items():
        imgpath = imgpathbase + ".png"
        layerindex = len(result.layers)
        layer_dict[imgpathbase] = layerindex
        flag_base = False
        flag_toggle = False
        def add_flag(flag : str):
          nonlocal flag_base
          nonlocal flag_toggle
          if not isinstance(flag, str):
            raise PPInternalError("Invalid flag in " + yamlpath + ": " + str(flag))
          if flag in ImagePack.TR_imagepack_yamlparse_base.get_all_candidates():
            flag_base = True
          elif flag in ImagePack.TR_imagepack_yamlparse_toggle.get_all_candidates():
            flag_toggle = True
          else:
            raise PPInternalError("Unknown flag: " + flag + "(supported flags: "
                                  + str(ImagePack.TR_imagepack_yamlparse_base.get_all_candidates()) + ", "
                                  + str(ImagePack.TR_imagepack_yamlparse_toggle.get_all_candidates()) + ")")
        if isinstance(d, dict):
          for key, value in d.items():
            if key in ImagePack.TR_imagepack_yamlparse_flags.get_all_candidates():
              if isinstance(value, str):
                add_flag(value)
              elif isinstance(value, list):
                for flag in value:
                  add_flag(flag)
        if not os.path.exists(os.path.join(basepath, imgpath)):
          raise PPInternalError("Image file not found: " + imgpath)
        img = PIL.Image.open(os.path.join(basepath, imgpath))
        if result.width == 0 and result.height == 0:
          result.width = img.width
          result.height = img.height
        if img.width != result.width or img.height != result.height:
          raise PPInternalError("Image size mismatch: " + str((img.width, img.height)) + " != " + str((result.width, result.height)))
        # 尝试缩小图片本体，如果有大片空白的话只截取有内容的部分
        offset_x = 0
        offset_y = 0
        bbox = img.getbbox()
        if bbox is not None:
          offset_x, offset_y, xmax, ymax = bbox
          img = img.crop(bbox)
        newlayer = ImagePack.LayerInfo(img, offset_x=offset_x, offset_y=offset_y, base=flag_base, toggle=flag_toggle, basename=imgpathbase)
        result.layers.append(newlayer)
      if composites is None:
        for i, layer in enumerate(result.layers):
          result.composites.append(ImagePack.CompositeInfo([i], layer.basename))
      else:
        for stack_name, stack_list in composites.items():
          stack = []
          if stack_list is None:
            stack.append(layer_dict[stack_name])
          elif isinstance(stack_list, list):
            stack = [layer_dict[s] for s in stack_list]
          result.composites.append(ImagePack.CompositeInfo(stack, stack_name))

      if masks is not None:
        for imgpathbase, maskinfo in masks.items():
          applyon : list[int] | None = None
          maskcolor : Color | None = None
          projective_vertices_result : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]] | None = None
          if not isinstance(maskinfo, dict):
            raise PPInternalError("Invalid mask in " + yamlpath + ": expecting a dict but got " + str(maskinfo))
          for key, value in maskinfo.items():
            if key in ImagePack.TR_imagepack_yamlparse_maskcolor.get_all_candidates():
              maskcolor = Color.get(value)
            elif key in ImagePack.TR_imagepack_yamlparse_applyon.get_all_candidates():
              applyon = []
              if isinstance(value, str):
                applyon.append(layer_dict[value])
              elif isinstance(value, list):
                for entry in value:
                  applyon.append(layer_dict[entry])
              else:
                raise PPInternalError("Invalid applyon in " + yamlpath + ": expecting a list or str but got " + str(value))
              if len(applyon) == 0:
                applyon = None
            elif key in ImagePack.TR_imagepack_yamlparse_projective.get_all_candidates():
              if not isinstance(value, dict):
                raise PPInternalError("Invalid projective in " + yamlpath + ": expecting a dict but got " + str(value))
              topleft : tuple[int, int] | None = None
              topright : tuple[int, int] | None = None
              bottomleft : tuple[int, int] | None = None
              bottomright : tuple[int, int] | None = None
              def read_2int_tuple(v) -> tuple[int, int]:
                if not isinstance(v, list) or len(v) != 2:
                  raise PPInternalError("Invalid projective vertex in " + yamlpath + ": expecting a list of 2 but got " + str(v))
                x, y = v
                if not isinstance(x, int) or not isinstance(y, int):
                  raise PPInternalError("Invalid projective vertex in " + yamlpath + ": expecting a list of 2 int but got " + str(v))
                return (x, y)
              for k, v in value.items():
                if k in ImagePack.TR_imagepack_yamlparse_topleft.get_all_candidates():
                  topleft = read_2int_tuple(v)
                elif k in ImagePack.TR_imagepack_yamlparse_topright.get_all_candidates():
                  topright = read_2int_tuple(v)
                elif k in ImagePack.TR_imagepack_yamlparse_bottomleft.get_all_candidates():
                  bottomleft = read_2int_tuple(v)
                elif k in ImagePack.TR_imagepack_yamlparse_bottomright.get_all_candidates():
                  bottomright = read_2int_tuple(v)
                else:
                  raise PPInternalError("Invalid projective in " + yamlpath + ": unknown key " + k + "(supported keys: "
                                        + str(ImagePack.TR_imagepack_yamlparse_topleft.get_all_candidates()) + ", "
                                        + str(ImagePack.TR_imagepack_yamlparse_topright.get_all_candidates()) + ", "
                                        + str(ImagePack.TR_imagepack_yamlparse_bottomleft.get_all_candidates()) + ", "
                                        + str(ImagePack.TR_imagepack_yamlparse_bottomright.get_all_candidates()) + ")")
              if topleft is None or topright is None or bottomleft is None or bottomright is None:
                raise PPInternalError("Invalid projective in " + yamlpath + ": missing values")
              projective_vertices_result = (topleft, topright, bottomleft, bottomright)
            else:
              raise PPInternalError("Unknown key: " + key + "(supported keys: "
                                    + str(ImagePack.TR_imagepack_yamlparse_maskcolor.get_all_candidates()) + ", "
                                    + str(ImagePack.TR_imagepack_yamlparse_applyon.get_all_candidates()) + ", "
                                    + str(ImagePack.TR_imagepack_yamlparse_projective.get_all_candidates()) + ")")
          if maskcolor is None:
            raise PPInternalError("Invalid mask in " + yamlpath + ": missing maskcolor")
          maskimgpath = os.path.join(basepath, imgpathbase + ".png")
          # 读取选区图并将其转化为黑白图片
          original_mask = PIL.Image.open(maskimgpath)
          maskimg = ImagePack.convert_mask_image(original_mask)
          if maskimg.width != result.width or maskimg.height != result.height:
            raise PPInternalError("Mask size mismatch: " + str((maskimg.width, maskimg.height)) + " != " + str((result.width, result.height)))
          offset_x = 0
          offset_y = 0
          bbox = maskimg.getbbox()
          if bbox is not None:
            offset_x, offset_y, xmax, ymax = bbox
            maskimg = maskimg.crop(bbox)
          newmask = ImagePack.MaskInfo(mask=maskimg, mask_color=maskcolor, offset_x=offset_x, offset_y=offset_y, projective_vertices=projective_vertices_result, basename=imgpathbase, applyon=applyon)
          result.masks.append(newmask)

      if metadata is not None:
        if not isinstance(metadata, dict):
          raise PPInternalError("Invalid metadata in " + yamlpath + ": expecting a dict but got " + str(metadata))
        result.opaque_metadata.update(metadata)

      result.optimize_masks()
      return result

  # 以下是提供给外部使用的接口

  @staticmethod
  def create_from_asset_archive(path : str):
    return ImagePack.create_from_zip(path)

  @staticmethod
  def build_asset_archive(destpath : str, yamlpath : str, references_filename : str = "references.yml"):
    pack = ImagePack.build_image_pack_from_yaml(yamlpath)
    pack.write_zip(destpath)
    basepath = os.path.dirname(os.path.abspath(yamlpath))
    references_path = os.path.join(basepath, references_filename)
    if os.path.exists(references_path):
      return ImagePackDescriptor(pack, references_path)
    return None

  @classmethod
  def add_descriptor(cls, descriptor : "ImagePackDescriptor") -> None:
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError("Invalid descriptor")
    super().add_descriptor(descriptor)
    descriptor.register_translatables()

  def dump_asset_info_json(self) -> dict:
    # 给 AssetManager 用的，返回一个适用于 JSON 的 dict 对象
    result : dict[str, typing.Any] = {
      "width": self.width,
      "height": self.height,
    }
    # 如果有选区，就把所有选区的名称和支持的方式都放进去
    if len(self.masks) > 0:
      masks : list[dict] = []
      for m in self.masks:
        mask : dict[str, typing.Any] = {
          "name": m.basename,
        }
        if m.projective_vertices is not None:
          mask["projection"] = True
        masks.append(mask)
      result["masks"] = masks
    # 如果有组合，就把所有组合的名称放进去
    if len(self.composites) > 0:
      composites : list[str] = []
      for c in self.composites:
        composites.append(c.basename)
      result["composites"] = composites
    # 如果有元数据，就把所有元数据放进去
    if len(self.opaque_metadata) > 0:
      result["metadata"] = self.opaque_metadata
    return result

  @staticmethod
  def tool_main(args : list[str] | None = None):
    # 创建一个有以下参数的 argument parser: [--debug] [--create <yml> | --load <zip> | --asset <name>] [--save <zip>] [--fork [args]] [--export <dir>]
    Translatable._init_lang_list()
    parser = argparse.ArgumentParser(description="ImagePack tool")
    Translatable._language_install_arguments(parser) # pylint: disable=protected-access
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--create", metavar="<yml>", help="Create a new image pack from a yaml file")
    parser.add_argument("--load", metavar="<zip>", help="Load an existing image pack from a zip file")
    parser.add_argument("--asset", metavar="<name>", help="Load an existing image pack from embedded assets")
    parser.add_argument("--save", metavar="<zip>", help="Save the image pack to a zip file")
    parser.add_argument("--fork", nargs="*", metavar="[args]", help="Fork the image pack with the given arguments")
    parser.add_argument("--export", metavar="<dir>", help="Export the image pack to a directory")
    parser.add_argument("--export-overview", metavar="<path>", help="Export a single overview image to the specified path")
    if args is None:
      args = sys.argv[1:]
    parsed_args = parser.parse_args(args)

    if parsed_args.debug:
      ImagePack._debug = True
    Translatable._language_handle_arguments(parsed_args, ImagePack._debug) # pylint: disable=protected-access

    num_input_spec = 0
    if parsed_args.create is not None:
      num_input_spec += 1
    if parsed_args.load is not None:
      num_input_spec += 1
    if parsed_args.asset is not None:
      num_input_spec += 1
    if num_input_spec > 1:
      raise PPInternalError("Cannot specify more than one input")
    if num_input_spec == 0:
      raise PPInternalError("No input specified")

    ImagePack.printstatus("start pipeline")

    current_pack = None
    if parsed_args.create is not None:
      ImagePack.printstatus("executing --create")
      # 创建一个新的 imagepack
      # 从 yaml 中读取
      current_pack = ImagePack.build_image_pack_from_yaml(parsed_args.create)
    elif parsed_args.load is not None:
      # 从 zip 中读取
      ImagePack.printstatus("executing --load")
      current_pack = ImagePack.create_from_zip(parsed_args.load)
    elif parsed_args.asset is not None:
      # 从 asset 中读取
      ImagePack.printstatus("executing --asset")
      manager = AssetManager.get_instance()
      current_pack = manager.get_asset(parsed_args.asset)
      if current_pack is None:
        raise PPInternalError("Asset not found: " + parsed_args.asset)
      if not isinstance(current_pack, ImagePack):
        raise PPInternalError("Asset is not an image pack: " + parsed_args.asset)

    if parsed_args.save is not None:
      # 保存到 zip 中
      ImagePack.printstatus("executing --save")
      if current_pack is None:
        raise PPInternalError("Cannot save without input")
      current_pack.write_zip(parsed_args.save)

    if parsed_args.fork is not None:
      # 创建一个新的 imagepack, 将 mask 所影响的部分替换掉
      ImagePack.printstatus("executing --fork")
      if current_pack is None:
        raise PPInternalError("Cannot fork without input")
      if len(parsed_args.fork) != len(current_pack.masks):
        raise PPInternalError("Mask arguments not match: " + str(len(current_pack.masks)) + " expected, " + str(len(parsed_args.fork)) + " provided")
      processed_args = []
      for rawarg in parsed_args.fork:
        # 如果是 "None"，实际参数就是 None
        # 如果是 "#RRGGBB"，实际参数就是 Color.get("#RRGGBB")
        # 如果是 "<#RRGGBB>ABCD"，实际参数就是 ("ABCD", Color.get("#RRGGBB"))
        # 如果是文件路径，实际参数就是 PIL.Image.open(文件路径)
        # 其他情况下，实际参数就是原字符串
        if rawarg == "None":
          processed_args.append(None)
        elif rawarg.startswith("#"):
          processed_args.append(Color.get(rawarg))
        elif rawarg.startswith("<#") and len(rawarg) > 8 and rawarg[8] == ">":
          colorpart = rawarg[1:8]
          textpart = rawarg[9:]
          processed_args.append((textpart, Color.get(colorpart)))
        else:
          if os.path.exists(rawarg):
            processed_args.append(PIL.Image.open(rawarg))
          else:
            processed_args.append(rawarg)
      current_pack = current_pack.fork_applying_mask(processed_args)

    if parsed_args.export is not None:
      ImagePack.printstatus("executing --export")
      if current_pack is None:
        raise PPInternalError("Cannot export without input")
      pathlib.Path(parsed_args.export).mkdir(parents=True, exist_ok=True)
      for i, comp in enumerate(current_pack.composites):
        outputname = comp.basename + '.png'
        img = current_pack.get_composed_image(i)
        img.save(os.path.join(parsed_args.export, outputname), format="PNG")

    if parsed_args.export_overview is not None:
      ImagePack.printstatus("executing --export-overview")
      if current_pack is None:
        raise PPInternalError("Cannot export overview without input")
      current_pack.write_overview_image(parsed_args.export_overview)

  _starttime = time.time()
  _debug = False

  @staticmethod
  def printstatus(s : str):
    if not ImagePack._debug:
      return
    curtime = time.time()
    timestr = "[{:.6f}] ".format(curtime - ImagePack._starttime)
    print(timestr + s, flush=True)

class ImagePackSummary:
  # 用于绘制概览图的类
  # 概览图主要由两部分组成，左侧是纵向排列的基底图，右侧是先横向再纵向排列的局部差分图
  # 基底图和局部差分图都伴随文字注释，置于图像下方
  # 概览图底部有文字注释
  title : str # 概览图的标题
  bases : list[PIL.Image.Image] # 纵向排列的基底图
  basenames : list[str] # 基底图的名称、注释
  diffs : list[PIL.Image.Image] # 局部差分
  diffnames : list[str]
  comments : list[str] # 概览图下方的注释，每行是一个字符串
  fontsize : int # 所有名称文本的字号
  commentfontsize : int # 注释文本的字号（一般会比名称小一点）
  columnsep : int # 图像之间的横向间隔，既包括中间基底图与局部差分图之间的间隔，也包括右侧局部差分图之间的间隔
  rowsep : int # 图像之间的纵向间隔
  imagescale : float | None # 如果非空的话，所有的图片需要按照这个比例缩小 （应该是一个小于1的值）
  layout_base_transpose : bool # 基底图是否先横向填充（先行后列）
  layout_diff_transpose : bool # 局部差分图是否先纵向填充（先列后行）
  fontcache : typing.ClassVar[dict[int, PIL.ImageFont.ImageFont | PIL.ImageFont.FreeTypeFont]] = {} # 字体缓存

  def __init__(self):
    self.title = "ImagePackSummary"
    self.bases = []
    self.basenames = []
    self.diffs = []
    self.diffnames = []
    self.comments = []
    self.fontsize = 24
    self.commentfontsize = 16
    self.columnsep = 4
    self.rowsep = 4
    self.imagescale = None
    self.layout_base_transpose = False
    self.layout_diff_transpose = False

  def add_base(self, img : PIL.Image.Image, name : str):
    self.bases.append(img)
    self.basenames.append(name)

  def add_diff(self, img : PIL.Image.Image, name : str):
    self.diffs.append(img)
    self.diffnames.append(name)

  def get_font_for_imagedrawing(self, fontsize : int) -> PIL.ImageFont.ImageFont | PIL.ImageFont.FreeTypeFont:
    font = self.fontcache.get(fontsize)
    if font is not None:
      return font
    font = ImagePack.get_font_for_text_image(fontsize)
    self.fontcache[fontsize] = font
    return font

  def get_text_image(self, text : str, fontsize : int) -> PIL.Image.Image:
    # 首先估算大概需要多大的画布，然后画上去，最后把多算的部分去掉
    font = self.get_font_for_imagedrawing(fontsize)
    textheight = fontsize * 4 // 3
    textwidth = len(text) * 2 * fontsize
    padding = 10
    image = PIL.Image.new("RGBA", (textwidth + padding * 2, textheight + padding * 2), (255, 255, 255, 0))
    draw = PIL.ImageDraw.Draw(image)
    textcolor = (0, 0, 0, 255) # 黑色
    draw.text((padding, padding), text, font=font, fill=textcolor)
    bbox = image.getbbox()
    if bbox is None:
      return PIL.Image.new("RGBA", (1, 1), (255, 255, 255, 0))
    left, upper, right, lower = bbox
    leftreduce = max(left, padding)
    topreduce = max(upper, padding)
    leftextra = left - leftreduce
    topextra = upper - topreduce
    newright = right + leftextra
    newlower = lower + topextra
    return image.crop((leftreduce, topreduce, newright, newlower))

  def get_image_from_text(self, text : str, preferred_font_size : int, maxwidth : int) -> PIL.Image.Image:
    if len(text) == 0:
      return PIL.Image.new("RGBA", (1, 1), (255, 255, 255, 0))
    image = self.get_text_image(text, preferred_font_size)
    if image.width <= maxwidth:
      return image
    # 如果文字太长，我们按比例缩小字号
    while image.width > maxwidth and preferred_font_size > 1:
      cur_font_size = image.width * preferred_font_size // maxwidth
      if cur_font_size >= preferred_font_size:
        cur_font_size = preferred_font_size - 1
      elif cur_font_size < 1:
        cur_font_size = 1
      preferred_font_size = cur_font_size
      image = self.get_text_image(text, preferred_font_size)
    return image

  def write(self, pngpath : str | None = None, htmlpath : str | None = None):
    # 绘制概览图
    # 为了方便使用，除了传统的 PNG 图像，我们还可以生成一个 HTML 文件，用户可以通过文本查找来快速定位
    # 首先取基底图和局部差分图的高度和宽度
    # 决定布局时我们都按最大值来
    # 为了避免在没有基底图或是没有局部差分图的情况下出现除以0的情况，我们先初始化为1
    base_height = 1
    base_width = 1
    for img in self.bases:
      base_height = max(base_height, img.height)
      base_width = max(base_width, img.width)
    diff_height = 1
    diff_width = 1
    for img in self.diffs:
      diff_height = max(diff_height, img.height)
      diff_width = max(diff_width, img.width)
    # 然后把所有的文本全都转换为图片，便于计算整个概览图的大小
    # 如果文字太长，我们按比例缩小字号
    basename_images = []
    diffname_images = []
    basename_maxheight = 1
    diffname_maxheight = 1
    for basename in self.basenames:
      image = self.get_image_from_text(basename, self.fontsize, base_width)
      basename_images.append(image)
      basename_maxheight = max(basename_maxheight, image.height)
    for diffname in self.diffnames:
      image = self.get_image_from_text(diffname, self.fontsize, diff_width)
      diffname_images.append(image)
      diffname_maxheight = max(diffname_maxheight, image.height)
    # 接下来我们开始决定概览图的布局
    # 首先，左侧的基底图部分，如果有多张基底图，那么可以单列、双列或者更多列，直到基底图部分的宽度超过了高度
    # 对于每一种布局，我们都计算一下整个概览图的长宽是多少
    # 对于任意一个基底图部分的长宽，我们使用如下方式来计算局部差分部分的布局：
    # 1. 把基底图部分的长宽转化为“多出来”的局部差分的行数和列数，这样我们只考虑一种矩形的长宽（局部差分）
    # 2. 根据目标的屏幕长宽比，选择一个最接近的布局，计算出局部差分的行数和列数
    # 3. 根据局部差分的行数和列数，计算出整个概览图的长宽
    # 我们希望选取一种最接近屏幕长宽比的布局，暂定为 16:9
    best_numbasecolumns = 1
    best_numbaserows = 1
    best_numdiffrows = 1
    best_numdiffcols = 1
    best_equivalentdiffs = (1, 1)
    best_aspect_ratio = None
    target_aspect_ratio = 16 / 9
    grid_height = diff_height+ diffname_maxheight + self.rowsep
    grid_width = diff_width + self.columnsep
    numdiffs = len(self.diffs)
    # 从单列开始，逐渐增加列数，直到基底图的高度超过宽度
    for numbasecolumns in range(1, len(self.bases) + 1):
      # 先算基底图部分的大小
      basecolumnwidth = base_width * numbasecolumns + self.columnsep * (numbasecolumns - 1)
      numbaserows = (len(self.bases) + numbasecolumns - 1) // numbasecolumns
      basecolumnheight = (base_height + basename_maxheight) * numbaserows + self.rowsep * (numbaserows - 1)
      # 再算局部差分图部分的大小
      equivalentdiff_numrows = (basecolumnheight + grid_height - 1) // grid_height
      equivalentdiff_numcols = (basecolumnwidth + grid_width - 1) // grid_width
      equivnumdiffs = equivalentdiff_numrows * equivalentdiff_numcols + numdiffs
      # 根据目标的屏幕长宽比，选择一个最接近的布局
      column_row_ratio = target_aspect_ratio * (grid_height / grid_width)
      numdiffrows = int(math.sqrt(equivnumdiffs / column_row_ratio) + 0.5)
      if numdiffrows < equivalentdiff_numrows:
        numdiffrows = equivalentdiff_numrows
      numdiffcols = (equivnumdiffs + numdiffrows - 1) // numdiffrows
      # 根据局部差分的行数和列数，计算出整个概览图的长宽
      cur_aspect_ratio = (numdiffcols * grid_width) / (numdiffrows * grid_height)
      if best_aspect_ratio is None or abs(cur_aspect_ratio - target_aspect_ratio) < abs(best_aspect_ratio - target_aspect_ratio):
        best_aspect_ratio = cur_aspect_ratio
        best_numbasecolumns = numbasecolumns
        best_numbaserows = numbaserows
        best_numdiffrows = numdiffrows
        best_numdiffcols = numdiffcols
        best_equivalentdiffs = (equivalentdiff_numrows, equivalentdiff_numcols)
      # 如果基底图部分的宽度超过高度，那么我们就不再继续增加列数了
      if basecolumnheight < basecolumnwidth:
        break
    base_consumed_equivalent_diff_rows, base_consumed_equivalent_diff_cols = best_equivalentdiffs
    # 在这里决定图的顺序
    # 每个二维数组都以行号列号为索引，值为图的索引
    # 对于局部差分和基底图的对齐方式，我们有两种排版：
    # 1. 如果局部差分的总行数与基底图所占的行数相等或是只大1且可以缺基底图所占的列数（即局部差分部分不需要使用基底图下方的区域），那么我们使用简单排版，
    #     两块都是完整的矩形，相当于各自的大图组装完后再粘一块，中间只留 self.columnsep 的间隔
    # 2. 如果局部差分的总行数大于基底图所占的行数（即我们需要把一些局部差分放在基底图下方），那么我们使用复杂排版，
    #     相当于整体使用局部差分的格子，但是把左上角的一部分用基底图填充
    # 不管是哪种情况，差分的前 base_consumed_equivalent_diff_rows （有时+1） 行都会少 base_consumed_equivalent_diff_cols 列，预留给基底图
    # 即使是第一种排版也是这样
    base_order : list[list[int | None]] = []
    diff_order : list[list[int | None]] = []
    # 先定基底图的排版
    if len(self.bases) > 0:
      for i in range(best_numbaserows):
        base_order.append([None] * best_numbasecolumns)
      for i in range(len(self.bases)):
        if self.layout_base_transpose:
          # 先行后列
          row = i // best_numbasecolumns
          col = i % best_numbasecolumns
          base_order[row][col] = i
        else:
          # 先列后行
          row = i % best_numbaserows
          col = i // best_numbaserows
          base_order[row][col] = i
    # 再定局部差分图的排版
    if len(self.diffs) > 0:
      for i in range(best_numdiffrows):
        diff_order.append([None] * best_numdiffcols)
      # 我们把要排版的部分分为两块：
      # 1. 在基底图右侧的矩形部分，每行都会少 base_consumed_equivalent_diff_cols 列
      # 2. 在基底图下方的矩形部分，每行都是完整的
      equiv_columns = best_numdiffcols - base_consumed_equivalent_diff_cols
      equiv_rows = (base_consumed_equivalent_diff_rows+1)
      max_diffs_in_right_side = (base_consumed_equivalent_diff_rows+1) * equiv_columns
      if len(self.diffs) > max_diffs_in_right_side:
        # 我们需要把一些局部差分放在基底图下方
        # 得重算 max_diffs_in_right_side， 行数减一
        equiv_rows = base_consumed_equivalent_diff_rows
        max_diffs_in_right_side = base_consumed_equivalent_diff_rows * equiv_columns
      # 先把右侧的填满
      for i in range(max_diffs_in_right_side):
        if self.layout_diff_transpose:
          # 先列后行
          row = i % equiv_rows
          col = i // equiv_rows
          diff_order[row][col + base_consumed_equivalent_diff_cols] = i
        else:
          # 先行后列
          row = i // equiv_columns
          col = i % equiv_columns
          diff_order[row][col + base_consumed_equivalent_diff_cols] = i
      # 再把下方的填满
      bottom_rows = best_numdiffrows - equiv_rows
      for i in range(max_diffs_in_right_side, len(self.diffs)):
        equiv_index = i - max_diffs_in_right_side
        if self.layout_diff_transpose:
          # 先列后行
          row = equiv_index % bottom_rows
          col = equiv_index // bottom_rows
          diff_order[row + base_consumed_equivalent_diff_rows][col] = i
        else:
          # 先行后列
          row = equiv_index // best_numdiffcols
          col = equiv_index % best_numdiffcols
          diff_order[row + base_consumed_equivalent_diff_rows][col] = i
    # 开始根据以上布局来绘制概览图
    # 首先我们计算整个概览图的长宽（不含注释）
    overview_width = 0
    overview_height = 0
    comment_start_y = 0
    is_simple_layout = len(self.diffs) == 0 or len(self.diffs) <= max_diffs_in_right_side
    if is_simple_layout:
      overview_width = basecolumnwidth + (best_numdiffcols - base_consumed_equivalent_diff_cols) * grid_width
      overview_height = max(basecolumnheight, best_numdiffrows * grid_height - self.rowsep)
    else:
      overview_width = best_numdiffcols * grid_width - self.columnsep
      overview_height = best_numdiffrows * grid_height - self.rowsep
    # 到这里我们把注释也转化为图片，并把注释所占的空间也加上
    comment_images = []
    comment_maxheight = 0
    if len(self.comments) > 0:
      for comment in self.comments:
        image = self.get_image_from_text(comment, self.commentfontsize, overview_width)
        comment_images.append(image)
        comment_maxheight = max(comment_maxheight, image.height)
      comment_start_y = overview_height + self.rowsep
      overview_height += (self.rowsep + comment_maxheight) * len(self.comments)
    # 创建画布
    overview = PIL.Image.new("RGBA", (overview_width, overview_height), (255, 255, 255, 255))
    # 开始绘制
    # 记录一下每个图的绝对位置 <x, y, width, height>
    base_image_coordinates : list[tuple[int,int,int,int] | None] = [None] * len(self.bases)
    diff_image_coordinates : list[tuple[int,int,int,int] | None] = [None] * len(self.diffs)
    # 首先绘制基底图
    if len(self.bases) > 0:
      y = 0
      for i, row in enumerate(base_order):
        x = 0
        for j, index in enumerate(row):
          if index is not None:
            # 如果基底图的大小不到 <base_width, base_height>，我们把它放在中间
            img = self.bases[index].convert("RGBA")
            imgwidth = img.width
            imgheight = img.height
            xoffset = 0
            yoffset = 0
            if imgwidth < base_width:
              xoffset = (base_width - imgwidth) // 2
            if imgheight < base_height:
              yoffset = (base_height - imgheight) // 2
            overview.alpha_composite(img, (x + xoffset, y + yoffset))
            base_image_coordinates[index] = (x + xoffset, y + yoffset, imgwidth, imgheight)
            # 如果名称的大小不到 <base_width, basename_maxheight>，我们使他顶部居中（即调整 x 但不调整 y）
            img = basename_images[index]
            xoffset = 0
            if img.width < base_width:
              xoffset = (base_width - img.width) // 2
            overview.alpha_composite(img, (x + xoffset, y + base_height))
          x += base_width + self.columnsep
        y += base_height + basename_maxheight + self.rowsep
    # 再绘制局部差分图
    xstart = 0
    if is_simple_layout:
      xstart = basecolumnwidth + self.columnsep - base_consumed_equivalent_diff_cols * grid_width
    if len(self.diffs) > 0:
      y = 0
      for i, row in enumerate(diff_order):
        x = xstart
        for j, index in enumerate(row):
          if index is not None:
            img = self.diffs[index].convert("RGBA")
            overview.alpha_composite(img, (x, y))
            # 如果名称的大小不到 <diff_width, diffname_maxheight>，我们使他顶部居中（即调整 x 但不调整 y）
            img = diffname_images[index]
            xoffset = 0
            if img.width < diff_width:
              xoffset = (diff_width - img.width) // 2
            overview.alpha_composite(img, (x + xoffset, y + diff_height))
            diff_image_coordinates[index] = (x + xoffset, y, img.width, img.height)
          x += diff_width + self.columnsep
        y += diff_height + diffname_maxheight + self.rowsep
    # 最后绘制注释
    if len(self.comments) > 0:
      y = comment_start_y
      for comment in comment_images:
        overview.alpha_composite(comment, (0, y))
        y += comment.height + self.rowsep
    # 保存
    if pngpath is not None:
      overview.save(pngpath, format="PNG")
    # 如果有 htmlpath，我们还要生成 HTML 文件
    # 为了避免使用太多的小图片，生成的 html 也会使用上面生成的 PNG 图像，使用 CSS 来截取一个个小图片
    if htmlpath is not None:
      # 先把概览图也存过去，把后缀名替换为 .png
      basename = os.path.splitext(htmlpath)[0]
      overview.save(basename + ".png", format="PNG")
      # 然后生成 HTML 文件
      # TODO
      raise PPNotImplementedError()

@ImagePack._descriptor
@dataclasses.dataclass
class ImagePackDescriptor:
  class MaskParamType(enum.Enum):
    IMAGE = enum.auto() # 图片选区
    COLOR = enum.auto() # 颜色选区

  class MaskType(enum.Enum):
    BACKGROUND_SCREEN = enum.auto() # 屏幕
    BACKGROUND_COLOR_1 = enum.auto() # 指示色
    CHARACTER_COLOR_1 = enum.auto() # 衣服颜色
    CHARACTER_COLOR_2 = enum.auto() # 发色
    CHARACTER_COLOR_3 = enum.auto() # 装饰色

    def get_param_type(self) -> "ImagePackDescriptor.MaskParamType":
      if self == ImagePackDescriptor.MaskType.BACKGROUND_SCREEN:
        return ImagePackDescriptor.MaskParamType.IMAGE
      return ImagePackDescriptor.MaskParamType.COLOR

  def get_masks(self) -> tuple[ImagePack.MaskInfo, ...]:
    # 获取该图片组所有的选区
    # 由于要结合前端的参数读取，我们这里使用 enum 来表示选区的类型
    raise PPNotImplementedError()

  def get_named_combinations(self) -> dict[str, str]:
    # 获取该图片组所有有在 Translatable 定义名称的组合
    # 返回的 dict 的 key 是（当前语言下）组合的名称，value 是组合的编号
    raise PPNotImplementedError()

  def get_combinations(self) -> list[str]:
    # 获取该图片组所有的组合
    # 返回的 list 是组合的编号
    raise PPNotImplementedError()

  def is_valid_combination(self, name : str) -> bool:
    # 检查一个组合是否有效
    raise PPNotImplementedError()

  def get_size(self) -> tuple[int, int]:
    # 获取图片组的整体大小
    raise PPNotImplementedError()

  def get_bbox(self) -> tuple[int, int, int, int]:
    # 获取图片组的边界框(bbox)
    raise PPNotImplementedError()

  def register_translatables(self):
    raise PPNotImplementedError()

  def __init__(self, pack : ImagePack, references_path : str):
    raise PPNotImplementedError()

def _test_main():
  srcdir = pathlib.Path(sys.argv[1])
  image_paths = list(srcdir.glob("*.png"))
  images = [PIL.Image.open(path) for path in image_paths]

  pack = ImagePack.create_image_pack_entry(images, base_image=images[0])
  pack.add_mask(PIL.Image.open("../mask.png").convert('L'), Color.get((179, 178, 190)), projective_vertices=((1743,1381), (2215,1453), (1753,1682), (2227,1896)))
  ImagePack.printstatus("image pack created")
  pack.write_zip("pack.zip")
  ImagePack.printstatus("zip written")
  recpack = ImagePack.create_from_zip("pack.zip")
  ImagePack.printstatus("zip loaded")
  recpack = recpack.fork_applying_mask([PIL.Image.open("../testaddon.jpg")])
  ImagePack.printstatus("pack forked")
  index = 0
  pathlib.Path("recovered").mkdir(parents=True, exist_ok=True)
  for path, original in zip(image_paths, images):
    recovered = recpack.get_composed_image(index)
    index += 1
    basename = os.path.basename(path)
    with open("recovered/" + basename, "wb") as f:
      recovered.save(f, format="PNG")
  ImagePack.printstatus("recovered written")


if __name__ == "__main__":
  ImagePack.tool_main()

