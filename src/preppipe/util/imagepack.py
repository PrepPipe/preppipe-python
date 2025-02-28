# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
import json
import typing
import io
import pathlib
import sys
import time
import colorsys
import datetime
import base64
import math
import itertools
import collections
import copy
import decimal
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.PngImagePlugin
import numpy as np
import scipy as sp
import matplotlib
import matplotlib.colors
import cv2
import yaml
import yaml.resolver
import yaml.constructor
import yaml.scanner
import yaml.parser
import yaml.composer
import dataclasses
import enum
import unicodedata
import textwrap
import re
import graphviz
import shutil
import concurrent.futures

from preppipe.irbase import IRValueMapper, Location, Operation

from ..exceptions import *
from ..commontypes import Color
from ..language import *
from ..tooldecl import ToolClassDecl
from ..assets.assetclassdecl import *
from ..assets.assetmanager import AssetManager
from ..assets.fileasset import FileAssetPack
from .message import MessageHandler

@dataclasses.dataclass
class ImageWrapper:
  # 在资源构建和对背景图片包的操作中，我们经常是不需要实际读取图片的，复制就行了
  # 该类用于替代所有需要 PIL.Image.Image 的地方以支持按需读取
  # path 应该指向一个 PNG 文件
  # 如果 image 和 path 同时不为 None 的话，它们一定是同一张图片
  image : PIL.Image.Image | None = None
  path : str | None = None

  def get(self) -> PIL.Image.Image:
    if self.image is not None:
      return self.image
    image = PIL.Image.open(self.path)
    self.image = image
    return image

  def has_backing_store(self) -> bool:
    return self.path is not None

  def save_png(self, pngpath : str):
    if self.path is not None:
      shutil.copy(self.path, pngpath)
      return
    self.get().save(pngpath)

  def save_to_path(self, path : str, resizeTo : tuple[int, int] | None = None):
    if resizeTo is None:
      if os.path.splitext(path)[1].lower() == ".png":
        self.save_png(path)
        return
    # 到这里的话，要么格式不对，要么需要改大小，所以必须读文件
    image = self.get()
    dstimage = image
    if resizeTo is not None:
      dstimage = image.resize(size=resizeTo)
    dstimage.save(path)

  @staticmethod
  def create_untrusted(path : str):
    # 用这个来处理构建图片包时的第一次读取。我们需要读取一次来保证这是个有效的图片
    image = PIL.Image.open(path)
    if os.path.splitext(path)[1].lower() == ".png":
      return ImageWrapper(image=image, path=path)
    return ImageWrapper(image=image)

@AssetClassDecl("imagepack")
@ToolClassDecl("imagepack")
class ImagePack(NamedAssetClassBase):
  TR_imagepack = TranslationDomain("imagepack")

  class MaskInfo:
    mask : ImageWrapper | None # 如果为 None 则表示该 mask 覆盖所有适用的基底图层
    basename : str # 保存时使用的名称（不含后缀）
    offset_x : int
    offset_y : int
    width : int
    height : int
    applyon : tuple[int,...] # 应该将该 mask 用于这里列出来的图层（空的话就是所有 base 图层都要）
    mask_color : Color

    # 如果支持 projective transform，以下是四个顶点（左上，右上，左下，右下）在 mask 中的坐标
    # https://stackoverflow.com/questions/14177744/how-does-perspective-transformation-work-in-pil
    projective_vertices : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]] | None

    def __init__(self, mask : ImageWrapper | None, mask_color : Color,
                 offset_x : int = 0, offset_y : int = 0,
                 width : int = 0, height : int = 0,
                 projective_vertices : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]] | None = None,
                 basename : str = '', applyon : typing.Iterable[int] | None = None) -> None:
      self.mask = mask
      self.mask_color = mask_color
      self.offset_x = offset_x
      self.offset_y = offset_y
      self.width = width
      self.height = height
      self.projective_vertices = projective_vertices
      self.basename = basename
      if applyon is not None:
        self.applyon = tuple(applyon)
      else:
        self.applyon = ()
      if width == 0 or height == 0:
        raise RuntimeError("Zero-sized mask?")

    def get_shrinked(self, ratio : decimal.Decimal):
      newwidth = int(self.width * ratio)
      newheight = int(self.height * ratio)
      newmask = ImageWrapper(self.mask.get().resize((newwidth, newheight), resample=PIL.Image.Resampling.NEAREST)) if self.mask is not None else None
      newprojective = None
      if self.projective_vertices is not None:
        newprojective = tuple((int(x * ratio), int(y * ratio)) for x, y in self.projective_vertices)
      return ImagePack.MaskInfo(mask=newmask,
                                offset_x=int(self.offset_x * ratio),
                                offset_y=int(self.offset_y * ratio),
                                width=newwidth, height=newheight,
                                projective_vertices=newprojective, # type: ignore
                                basename=self.basename, applyon=self.applyon, mask_color=self.mask_color)

  class LayerInfo:
    # 保存时每个图层的信息
    patch : ImageWrapper # RGBA uint8 图片
    basename : str # 保存时使用的名称（不含后缀）
    offset_x : int
    offset_y : int
    width : int
    height : int

    # 如果是 True 的话，该层视为可被 mask 的部分
    # （重构原图时，当 mask 与该图层有重叠时，我们在添加结果时需将 mask 参数赋予该图层）
    base : bool
    # 如果是 True 的话，该层可以不受限制地单独被选取
    toggle : bool

    def __init__(self, patch : ImageWrapper,
                 offset_x : int = 0, offset_y : int = 0,
                 width : int = 0, height : int = 0,
                 base : bool = False, toggle : bool = False, basename : str = '') -> None:
      self.patch = patch
      self.basename = basename
      self.offset_x = offset_x
      self.offset_y = offset_y
      self.width = width
      self.height = height
      self.base = base
      self.toggle = toggle
      if width == 0 or height == 0:
        raise RuntimeError("Zero-sized layer?")

    def get_shrinked(self, ratio : decimal.Decimal):
      newwidth = int(self.width * ratio)
      newheight = int(self.height * ratio)
      newpatch = self.patch.get().resize((newwidth, newheight), resample=PIL.Image.Resampling.LANCZOS)
      return ImagePack.LayerInfo(patch=ImageWrapper(image=newpatch),
                                offset_x=int(self.offset_x * ratio),
                                offset_y=int(self.offset_y * ratio),
                                width=newwidth, height=newheight,
                                base=self.base, toggle=self.toggle, basename=self.basename)

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
  #   "overview_scale" : decimal.Decimal, 用于生成预览图或是文档时的缩放比例
  #   "diff_croprect": tuple[int,int,int,int], 用于生成差分图的裁剪矩形
  #   "modified": bool, 用于标注是否已修改选区
  #   "original_size": tuple[int,int], 用于标注原始大小，只在第一次改变大小时设置
  # 如果新加的元数据需要在图缩小时更新，记得改 fork_and_shrink()
  opaque_metadata : dict[str, typing.Any]

  OPAQUE_METADATA_DECIMALS : typing.ClassVar[list[str]] = [
    "overview_scale",
  ]

  def __init__(self, width : int, height : int) -> None:
    self.width = width
    self.height = height
    self.masks = []
    self.layers = []
    self.composites = []
    self.opaque_metadata = {}

  @staticmethod
  def _write_image_to_path(image : ImageWrapper, filename : str, basepath : str):
    destpath = os.path.join(basepath, filename)
    if image.path is not None:
      shutil.copy(image.path, destpath)
      return
    image.get().save(destpath)

  def is_imagedata_loaded(self) -> bool:
    return len(self.layers) > 0

  def write_to_path(self, path : str):
    if not self.is_imagedata_loaded():
      raise PPInternalError("writing ImagePack without data")
    os.makedirs(path, exist_ok=True)
    self.clear_directory_recursive(path)
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
          self._write_image_to_path(m.mask, filename, path)
        else:
          basename = None
        jsonobj : dict[str, typing.Any] = {
          "mask" : basename,
          "x" : m.offset_x,
          "y" : m.offset_y,
          "w" : m.width,
          "h" : m.height,
          "maskcolor" : m.mask_color.get_string(),
        }
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
        jsonobj : dict[str, typing.Any] = {
          "x" : l.offset_x,
          "y" : l.offset_y,
          "w" : l.width,
          "h" : l.height,
          "p" : basename,
        }
        flags = []
        if l.base:
          flags.append("base")
        if l.toggle:
          flags.append("toggle")
        if len(flags) > 0:
          jsonobj["flags"] = flags
        result.append(jsonobj)
        self._write_image_to_path(l.patch, filename, path)
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
      jsonout["metadata"] = ImagePack.get_metadata_dict_for_serialization(self.opaque_metadata)

    with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as f:
      json.dump(jsonout, f, ensure_ascii=False, indent=None, separators=(',', ':'))

  @staticmethod
  def get_metadata_dict_for_serialization(metadata : dict[str, typing.Any]) -> dict[str, typing.Any]:
    metadata = copy.deepcopy(metadata)
    for k in ImagePack.OPAQUE_METADATA_DECIMALS:
      if k in metadata:
        metadata[k] = metadata[k].as_tuple()
    return metadata

  @staticmethod
  def recover_metadata_from_dict_serialized(metadata : dict[str, typing.Any]) -> dict[str, typing.Any]:
    metadata = copy.deepcopy(metadata)
    for k in ImagePack.OPAQUE_METADATA_DECIMALS:
      if k in metadata:
        metadata[k] = decimal.Decimal(metadata[k])
    return metadata

  @staticmethod
  def create_from_path(path : str):
    pack = ImagePack(0, 0)
    pack.read_from_path(path)
    return pack

  def read_from_path(self, path : str):
    if len(self.layers) > 0 or len(self.masks) > 0:
      raise PPInternalError("Cannot reload when data is already loaded")

    # Read manifest.json
    with open(os.path.join(path, "manifest.json"), "r", encoding="utf-8") as f:
      manifest = json.load(f)
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
          mask_img = ImageWrapper(path=os.path.join(path, mask_filename))
        mask_color = Color.get(mask_info["maskcolor"])
        offset_x = mask_info["x"]
        offset_y = mask_info["y"]
        width = mask_info["w"]
        height = mask_info["h"]
        projective_vertices = mask_info.get("projective", None)
        applyon = mask_info.get("applyon", [])

        masks.append(ImagePack.MaskInfo(mask=mask_img, mask_color=mask_color,
                                        offset_x=offset_x, offset_y=offset_y,
                                        width=width, height=height,
                                        projective_vertices=projective_vertices,
                                        basename=mask_info["mask"], applyon=applyon))
      self.masks = masks

    # Read layers
    def read_layer_group(prefix, group_name):
      layers = []
      if group_name in manifest:
        for layer_info in manifest[group_name]:
          layer_filename = layer_info["p"] + ".png"
          offset_x = layer_info["x"]
          offset_y = layer_info["y"]
          width = layer_info["w"]
          height = layer_info["h"]
          base = "base" in layer_info.get("flags", [])
          toggle = "toggle" in layer_info.get("flags", [])
          layer_img = ImageWrapper(path=os.path.join(path, layer_filename))
          layers.append(ImagePack.LayerInfo(patch=layer_img,
                                            offset_x=offset_x, offset_y=offset_y,
                                            width=width, height=height,
                                            base=base, toggle=toggle, basename=layer_info["p"]))
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
      self.opaque_metadata = ImagePack.recover_metadata_from_dict_serialized(manifest["metadata"])

  def get_composed_image(self, index : int) -> ImageWrapper:
    if not self.is_imagedata_loaded():
      raise PPInternalError("Cannot compose images without loading the data")
    layer_indices = self.composites[index].layers
    if len(layer_indices) == 0:
      raise PPInternalError("Empty composition? some thing is probably wrong")
    if len(layer_indices) == 1:
      curlayer = self.layers[layer_indices[0]]
      # 如果该图层正好覆盖整个图像，则直接返回
      if curlayer.offset_x == 0 and curlayer.offset_y == 0 and curlayer.width == self.width and curlayer.height == self.height:
        return curlayer.patch

    result = PIL.Image.new("RGBA", (self.width, self.height))

    for li in layer_indices:
      layer = self.layers[li]
      extended_patch = PIL.Image.new("RGBA", (self.width, self.height))
      extended_patch.paste(layer.patch.get(), (layer.offset_x, layer.offset_y))
      result = PIL.Image.alpha_composite(result, extended_patch)
    return ImageWrapper(image=result)

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

  @staticmethod
  def get_font_for_text_image(fontsize : int) -> PIL.ImageFont.ImageFont | PIL.ImageFont.FreeTypeFont:
    return AssetManager.get_font(fontsize)

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
      image = PIL.Image.new("RGBA", size, color_tuple) # type: ignore
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
      if image is None:
        raise RuntimeError("Force draw failed?")
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

  @staticmethod
  def create_forked_layer(imgwidth : int, imgheight : int, l : LayerInfo, layerindex: int, applicable_forks : list[tuple[MaskInfo, Color | PIL.Image.Image | str | tuple[str, Color] | None]]) -> LayerInfo:
    # 开始修改，先把图弄全
    if l.patch.get().mode in ("RGBA", "RGB"):
      patch_array = np.array(l.patch.get())
    else:
      patch_array = np.array(l.patch.get().convert("RGBA"))
    cur_base = np.zeros((imgheight, imgwidth, patch_array.shape[2]), dtype=np.uint8)
    cur_base[l.offset_y:l.offset_y+l.height, l.offset_x:l.offset_x+l.width] = patch_array

    for m, arg in applicable_forks:
      # 在开始前，如果输入是图像且需要进行转换，则执行操作
      if isinstance(arg, Color):
        converted_arg = arg
      else:
        # 之前应该检查过了
        assert m.projective_vertices is not None
        if not isinstance(arg, PIL.Image.Image):
          start_point_size = ImagePack.get_starting_font_point_size(imgwidth, imgheight)
          text_image_size = ImagePack.get_projective_rectangular_size_for_text(m.projective_vertices)
          text = ''
          color = None
          if isinstance(arg, str):
            text = arg
          elif isinstance(arg, tuple):
            text, color = arg
          arg = ImagePack.create_text_image_for_mask(text, color, start_point_size, text_image_size, m.mask_color)
        converted_arg = np.full((imgheight, imgwidth, 3), m.mask_color.to_float_tuple_rgb(), dtype=np.float32)
        srcpoints = np.matrix([[0, 0], [arg.width-1, 0], [0, arg.height-1], [arg.width-1, arg.height-1]], dtype=np.float32)
        dstpoints = np.matrix(m.projective_vertices, dtype=np.float32)
        projective_matrix = cv2.getPerspectiveTransform(srcpoints, dstpoints)
        converted_arg = cv2.warpPerspective(src=np.array(arg.convert("RGB")).astype(np.float32)/255.0, M=projective_matrix, dsize=(imgwidth, imgheight), dst=converted_arg, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_TRANSPARENT)
        converted_arg = (converted_arg * 255.0).astype(np.uint8) # type: ignore

      # 转换当前的 mask
      mask_data = None
      if m.mask is not None:
        mask_data = PIL.Image.new("L", (imgwidth, imgheight), color=0)
        mask_data.paste(m.mask.get().convert("L"), (m.offset_x, m.offset_y))
        mask_data = np.array(mask_data)

      cur_base = ImagePack.change_color_hsv_pillow(cur_base, mask_data, m.mask_color, converted_arg)

    if cur_base.shape[2] == 3:
      mode = "RGB"
    else:
      mode = "RGBA"
    newbase = PIL.Image.fromarray(cur_base, mode)
    bbox = newbase.getbbox()
    if bbox is None:
      raise PPInternalError("Empty base after applying mask?")
    offset_x, offset_y, xmax, ymax = bbox
    return ImagePack.LayerInfo(ImageWrapper(image=newbase.crop(bbox)),
                                    offset_x=offset_x, offset_y=offset_y,
                                    width=xmax-offset_x, height=ymax-offset_y,
                                    base=True, toggle=l.toggle, basename=l.basename)

  def fork_applying_mask(self, args : list[Color | PIL.Image.Image | str | tuple[str, Color] | None], enable_parallelization : bool = False):
    # 创建一个新的 imagepack, 将 mask 所影响的部分替换掉
    if not self.is_imagedata_loaded():
      raise PPInternalError("Cannot fork_applying_mask() without data")
    if len(args) != len(self.masks):
      raise PPInternalError("Mask arguments not match: " + str(len(self.masks)) + " expected, " + str(len(args)) + " provided")
    resultpack = ImagePack(self.width, self.height)

    # 除了 mask 和 layers, 其他都照搬
    resultpack.composites = self.composites
    resultpack.opaque_metadata = copy.deepcopy(self.opaque_metadata)
    resultpack.opaque_metadata["modified"] = True

    # 开始搬运 layers
    forkinglayers : dict[int, list[tuple[ImagePack.MaskInfo, Color | PIL.Image.Image | str | tuple[str, Color] | None]]] = {}
    newlayers : dict[int, ImagePack.LayerInfo | None] = {}
    for layerindex, l in enumerate(self.layers):
      if not l.base:
        newlayers[layerindex] = l
        continue

      # 检查当前基底是否必须修改，不修改的话还是可以直接搬
      applicable_forks : list[tuple[ImagePack.MaskInfo, Color | PIL.Image.Image | str | tuple[str, Color] | None]] = []
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
        # 到这的话就应该需要了
        applicable_forks.append((m, arg))

      if len(applicable_forks) == 0:
        newlayers[layerindex] = l
        continue

      forkinglayers[layerindex] = applicable_forks

    if len(forkinglayers) > 0:
      if len(forkinglayers) == 1 or not enable_parallelization:
        for layerindex, applicable_forks in forkinglayers.items():
          newlayers[layerindex] = ImagePack.create_forked_layer(self.width, self.height, self.layers[layerindex], layerindex, applicable_forks)
      else:
        futures = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
          for layerindex, applicable_forks in forkinglayers.items():
            futureobj = executor.submit(ImagePack.create_forked_layer, self.width, self.height, self.layers[layerindex], layerindex, applicable_forks)
            futures[layerindex] = futureobj
        for layerindex, future in futures.items():
          newlayers[layerindex] = future.result()
    if len(resultpack.layers) > 0:
      raise PPInternalError("Layers already initialized?")
    for i in range(len(self.layers)):
      newlayer = newlayers[i]
      if newlayer is None:
        raise PPInternalError("layer not computed")
      resultpack.layers.append(newlayer)
    return resultpack

  def fork_and_shrink(self, ratio : decimal.Decimal, enable_parallelization : bool = False):
    # 创建一个新的 imagepack, 把该图包按 ratio 缩小
    # ratio 必须在 (0, 1) 之间
    if not self.is_imagedata_loaded():
      raise PPInternalError("Cannot fork without loading the data")
    if ratio <= 0 or ratio >= 1:
      raise PPInternalError("Invalid ratio: " + str(ratio) + ", must be in (0, 1)")
    target_width = int(self.width * ratio)
    target_height = int(self.height * ratio)
    resultpack = ImagePack(target_width, target_height)

    # composites 可以直接搬
    resultpack.composites = self.composites

    # 其他的元数据也可以直接搬，部分需要修改
    resultpack.opaque_metadata = copy.deepcopy(self.opaque_metadata)
    if "original_size" not in self.opaque_metadata:
      resultpack.opaque_metadata["original_size"] = (self.width, self.height)
    if "diff_croprect" in self.opaque_metadata:
      x1, y1, x2, y2 = self.opaque_metadata["diff_croprect"]
      resultpack.opaque_metadata["diff_croprect"] = (int(x1 * ratio), int(y1 * ratio), int(x2 * ratio), int(y2 * ratio))
    if "overview_scale" in self.opaque_metadata:
      # resultpack.opaque_metadata["overview_scale"] = self.opaque_metadata["overview_scale"] / ratio
      # 现在我们直接把这个值改成 1.0，因为原值只是为了在生成预览图时用，一般图片包整个缩小之后会以其他方式生成预览，不再需要这个值
      resultpack.opaque_metadata["overview_scale"] = decimal.Decimal(1.0)

    newlayers = []
    def shrink_layer(l : ImagePack.LayerInfo, ratio : decimal.Decimal) -> ImagePack.LayerInfo:
      return l.get_shrinked(ratio)
    if len(self.layers) > 1 and enable_parallelization:
      futures = []
      with concurrent.futures.ThreadPoolExecutor() as executor:
        for l in self.layers:
          futureobj = executor.submit(shrink_layer, l, ratio)
          futures.append(futureobj)
      for f in futures:
        newlayers.append(f.result())
    else:
      for l in self.layers:
        newlayers.append(shrink_layer(l, ratio))
    resultpack.layers = newlayers
    if len(self.masks) > 0:
      resultpack.masks = []
      for m in self.masks:
        resultpack.masks.append(m.get_shrinked(ratio))
    return resultpack

  def shrink_for_overview(self):
    if overview_scale := self.opaque_metadata.get("overview_scale", None):
      return self.fork_and_shrink(overview_scale)
    return self

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

  def optimize_masks(self):
    # 对任意一个选区，如果它现在有图片，但是它所覆盖的范围可以近似为全图，则把这个图片去掉以减小文件大小
    # 对于选区和基底图的操作的代码都是从 fork_applying_mask() 中复制过来的
    for m in self.masks:
      if m.mask is None:
        continue
      isFullyCovers = True
      mask_img = PIL.Image.new("L", (self.width, self.height), color=0)
      mask_img.paste(m.mask.get().convert("L"), (m.offset_x, m.offset_y))
      mask_data = np.array(mask_img)
      # 如果 mask_data 全是非零值，那么就是全图，我们已经可以确定了
      if not np.all(mask_data > 0):
        # 在不全是非零值的情况下继续检查
        def check_base_cover(l : ImagePack.LayerInfo) -> bool:
          nonlocal isFullyCovers
          # 如果当前基底图没有 alpha 通道，那么就不可能覆盖全图
          if l.patch.get().mode != "RGBA":
            isFullyCovers = False
            return True
          patch_array = np.array(l.patch)
          base_data = np.zeros((self.height, self.width, patch_array.shape[2]), dtype=np.uint8)
          base_data[l.offset_y:l.offset_y+l.height, l.offset_x:l.offset_x+l.width] = patch_array
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

  def get_summary_no_variations(self, descriptor : 'ImagePackDescriptor') -> 'ImagePackSummary':
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
      if isinstance(descriptor, ImagePackDescriptor):
        codename = descriptor.composites_code[i]
        if t := descriptor.composites_references.get(codename, None):
          name = codename + ' (' + t.get() + ')'
        else:
          name = codename
      base_indices = tuple([x for x in indices if self.layers[x].base])
      if base_indices in base_index_map:
        # 这是一个差分图
        image = self.get_composed_image(i).get()
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
        image = self.get_composed_image(i).get()
        bases.append(image)
        basenames.append(name)
    # 最后生成 ImagePackSummary
    result = ImagePackSummary()
    overview_scale = self.opaque_metadata.get("overview_scale", None)
    if overview_scale is not None:
      if not isinstance(overview_scale, decimal.Decimal) or overview_scale <= 0 or overview_scale > 1:
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

  TR_imagepack_overview_name = TR_imagepack.tr("overview_name",
    en="Name: \"{name}\". ",
    zh_cn="名称：\"{name}\"。",
    zh_hk="名稱：\"{name}\"。",
  )
  TR_imagepack_overview_anonymous = TR_imagepack.tr("overview_anonymous",
    en="(Anonymous) ",
    zh_cn="（无名称信息。）",
    zh_hk="（無名稱資訊。）",
  )
  TR_imagepack_overview_author = TR_imagepack.tr("overview_author",
    en="Author: {name}. ",
    zh_cn="作者：{name}。",
    zh_hk="作者：{name}。",
  )
  TR_imagepack_overview_forked = TR_imagepack.tr("overview_forked",
    en="[Image content modified.]",
    zh_cn="[图片内容已修改。]",
    zh_hk="[圖片內容已修改。]",
  )
  TR_imagepack_overview_size_note = TR_imagepack.tr("overview_size_note",
    en="Original size: {width} x {height}. ",
    zh_cn="原始尺寸：{width} x {height}。",
    zh_hk="原始尺寸：{width} x {height}。",
  )
  TR_imagepack_overview_complexity_note = TR_imagepack.tr("overview_complexity_note",
    en="{numlayers} layers, {numcomposites} compositions. ",
    zh_cn="图层 {numlayers} 个，差分组合 {numcomposites} 个。",
    zh_hk="圖層 {numlayers} 個，差分組合 {numcomposites} 個。",
  )
  TR_imagepack_overview_distributenote_internal = TR_imagepack.tr("overview_distributenote_internal",
    en="This image pack is distributed only for internal use. Do not distribute or use it outside of its intended purpose.",
    zh_cn="本图包仅供内部使用。请勿扩散或是用在与原用途不符的地方。",
    zh_hk="本圖包僅供內部使用。請勿擴散或是用在與原用途不符的地方。",
  )
  TR_imagepack_overview_distributenote_cc0 = TR_imagepack.tr("overview_distributenote_cc0",
    en="This image pack is distributed under the CC0 1.0 Universal (CC0 1.0) Public Domain Dedication.",
    zh_cn="本图片包以 CC0 1.0 通用 (CC0 1.0) 公共领域贡献方式分发。",
    zh_hk="本圖片包以 CC0 1.0 通用 (CC0 1.0) 公共領域貢獻方式分發。",
  )

  def write_overview_image(self, path : str, descriptor : "ImagePackDescriptor", interactive_html_path : str | None = None):
    # 生成一个预览图
    # 先使用辅助函数生成 ImagePackSummary
    summary = self.get_summary_no_variations(descriptor)
    # 再把元数据加上
    # http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html#:~:text=4.2.3.%20Textual%20information
    # 图片包名称，从 descriptor 中获取
    summary.pngmetadata["Software"] = Translatable.tr_program_name.get()
    summary.pngmetadata["Creation Time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    imgpack_name = ''
    if isinstance(descriptor, ImagePackDescriptor):
      if isinstance(descriptor.topref, str):
        imgpack_name = descriptor.topref
      elif isinstance(descriptor.topref, Translatable):
        imgpack_name = descriptor.topref.get()
      else:
        raise PPInternalError("Invalid topref")
    if len(imgpack_name) == 0:
      first_line = self.TR_imagepack_overview_anonymous.get()
    else:
      first_line = self.TR_imagepack_overview_name.format(name=imgpack_name)
      summary.pngmetadata["Title"] = imgpack_name
    # 作者信息
    if author := self.opaque_metadata.get("author", None):
      first_line += self.TR_imagepack_overview_author.format(name=author)
      summary.pngmetadata["Author"] = author
    original_width, original_height = self.opaque_metadata.get("original_size", (self.width, self.height))
    first_line += self.TR_imagepack_overview_size_note.format(width=str(original_width), height=str(original_height))
    first_line += self.TR_imagepack_overview_complexity_note.format(numlayers=str(len(self.layers)), numcomposites=str(len(self.composites)))
    if self.opaque_metadata.get("modified", False):
      first_line += self.TR_imagepack_overview_forked.get()
    summary.comments.append(first_line)
    # 许可信息
    # 没写许可就是内部使用
    license_tr = self.TR_imagepack_overview_distributenote_internal
    copyright_str = "Closed distribution"
    if license := self.opaque_metadata.get("license", None):
      if license == "cc0":
        license_tr = self.TR_imagepack_overview_distributenote_cc0
        copyright_str = "CC0 1.0 Universal (CC0 1.0) Public Domain Dedication"
      else:
        raise PPInternalError("Unknown license: " + license)
    summary.comments.append(license_tr.get())
    summary.pngmetadata["Copyright"] = copyright_str
    summary.write(pngpath=path)

    if interactive_html_path is not None:
      if not isinstance(descriptor, ImagePackDescriptor):
        raise PPInternalError("Invalid descriptor")
      _ImagePackHTMLExport.write_html(
        interactive_html_path, self, descriptor,
        html_title=imgpack_name,
        html_author=Translatable.tr_program_name.get(),
        html_description="\n".join(summary.comments))


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
  TR_imagepack_yamlparse_generation = TR_imagepack.tr("generation",
    en="generation",
    zh_cn="生成",
    zh_hk="生成",
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

  # https://stackoverflow.com/questions/47340294/pyyaml-load-number-as-decimal
  @staticmethod
  def _decimal_constructor(loader, node):
    return decimal.Decimal(loader.construct_scalar(node))

  class ImagePackYamlResolver(yaml.resolver.BaseResolver):
    pass

  ImagePackYamlResolver.add_implicit_resolver(
          '!decimal',
          re.compile(r'''^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?
                      |\.[0-9_]+(?:[eE][-+][0-9]+)?
                      |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*
                      |[-+]?\.(?:inf|Inf|INF)
                      |\.(?:nan|NaN|NAN))$''', re.X),
          list('-+0123456789.'))

  for ch, vs in yaml.resolver.Resolver.yaml_implicit_resolvers.items():
    ImagePackYamlResolver.yaml_implicit_resolvers.setdefault(ch, []).extend(
        (tag, regexp) for tag, regexp in vs
        if not tag.endswith('float')
    )

  class ImagePackYamlLoader(yaml.reader.Reader, yaml.scanner.Scanner, yaml.parser.Parser, yaml.composer.Composer, yaml.constructor.SafeConstructor, ImagePackYamlResolver):
    def __init__(self, stream):
      yaml.reader.Reader.__init__(self, stream)
      yaml.scanner.Scanner.__init__(self)
      yaml.parser.Parser.__init__(self)
      yaml.composer.Composer.__init__(self)
      yaml.constructor.SafeConstructor.__init__(self)
      ImagePack.ImagePackYamlResolver.__init__(self)

  yaml.add_constructor('!decimal', _decimal_constructor, ImagePackYamlLoader)

  @staticmethod
  def load_yaml(yamlpath : str) -> dict[str, typing.Any]:
    # 读取 yaml 文件，支持 include，且所有 float 全都解析为 decimal.Decimal
    def read_yaml_dict(yamlpath : str) -> dict:
      with open(yamlpath, "r", encoding="utf-8") as f:
        result = yaml.load(f, Loader=ImagePack.ImagePackYamlLoader) # type: ignore
        if not isinstance(result, dict):
          raise PPInternalError("Invalid yaml config: " + yamlpath)
        return result
    def handle_include_resursive(include_path : str, cur_path : str) -> dict[str, typing.Any]:
      if not os.path.isabs(include_path):
        include_path = os.path.join(os.path.dirname(cur_path), include_path)
      if not os.path.exists(include_path):
        raise PPInternalError("Cannot find included file: " + include_path)
      result = read_yaml_dict(include_path)
      if "include" in result:
        next_include_path = result["include"]
        child = handle_include_resursive(next_include_path, include_path)
        child.update(result)
        result = child
      return result
    result = {}
    if os.path.exists(yamlpath):
      result = read_yaml_dict(yamlpath)
      if "include" in result:
        child = handle_include_resursive(result["include"], yamlpath)
        child.update(result)
        result = child
    # 为了避免检查是否有未用到的字段时因为 include 而出错，我们在这把 include 字段去掉
    if "include" in result:
      del result["include"]
    return result

  @staticmethod
  def build_image_pack_from_yaml(yamlpath : str):
    basepath = os.path.dirname(os.path.abspath(yamlpath))
    yamlobj = ImagePack.load_yaml(yamlpath)
    result = ImagePack(0, 0)
    layers = None
    masks = None
    composites = None
    metadata = None
    generation = None
    for k in yamlobj.keys():
      if k in ImagePack.TR_imagepack_yamlparse_layers.get_all_candidates():
        layers = yamlobj[k]
      elif k in ImagePack.TR_imagepack_yamlparse_masks.get_all_candidates():
        masks = yamlobj[k]
      elif k in ImagePack.TR_imagepack_yamlparse_composites.get_all_candidates():
        composites = yamlobj[k]
      elif k in ImagePack.TR_imagepack_yamlparse_metadata.get_all_candidates():
        metadata = yamlobj[k]
      elif k in ImagePack.TR_imagepack_yamlparse_generation.get_all_candidates():
        generation = yamlobj[k]
      else:
        raise PPInternalError("Unknown key: " + k + "(supported keys: "
                              + str(ImagePack.TR_imagepack_yamlparse_layers.get_all_candidates()) + ", "
                              + str(ImagePack.TR_imagepack_yamlparse_masks.get_all_candidates()) + ", "
                              + str(ImagePack.TR_imagepack_yamlparse_composites.get_all_candidates()) + ", "
                              + str(ImagePack.TR_imagepack_yamlparse_metadata.get_all_candidates()) + ", "
                              + str(ImagePack.TR_imagepack_yamlparse_generation.get_all_candidates())
                              + ")")
    if generation is not None:
      layers, masks, composites, metadata = ImagePack.handle_yaml_generation(generation, layers, masks, composites, metadata)
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
      patch = ImageWrapper.create_untrusted(os.path.join(basepath, imgpath))
      img = patch.get()
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
        if offset_x != 0 or offset_y != 0 or xmax != img.width or ymax != img.height:
          img = img.crop(bbox)
          patch = ImageWrapper(image=img)
      newlayer = ImagePack.LayerInfo(patch,
                                      offset_x=offset_x, offset_y=offset_y,
                                      width=img.width, height=img.height,
                                      base=flag_base, toggle=flag_toggle, basename=imgpathbase)
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
        curmask = None
        offset_x = 0
        offset_y = 0
        maskwidth = result.width
        maskheight = result.height
        # 读取选区图并将其转化为黑白图片
        # 如果该选区图不存在，我们默认其覆盖全图（这种情况下应该已经限定生效的基地图层）
        if os.path.exists(maskimgpath):
          original_mask = PIL.Image.open(maskimgpath)
          maskimg = ImagePack.convert_mask_image(original_mask)
          if maskimg.width != result.width or maskimg.height != result.height:
            raise PPInternalError("Mask size mismatch: " + str((maskimg.width, maskimg.height)) + " != " + str((result.width, result.height)))
          bbox = maskimg.getbbox()
          if bbox is not None:
            offset_x, offset_y, xmax, ymax = bbox
            maskimg = maskimg.crop(bbox)
          curmask = ImageWrapper(image=maskimg)
          maskwidth = maskimg.width
          maskheight = maskimg.height
        else:
          # 覆盖全图时不指定文件名
          imgpathbase = None
        # 到这里的话，有无选区图的情况都处理完毕，开始写回
        newmask = ImagePack.MaskInfo(mask=curmask,
                                      mask_color=maskcolor,
                                      offset_x=offset_x, offset_y=offset_y,
                                      width=maskwidth, height=maskheight,
                                      projective_vertices=projective_vertices_result, basename=imgpathbase, applyon=applyon)
        result.masks.append(newmask)

    if metadata is not None:
      if not isinstance(metadata, dict):
        raise PPInternalError("Invalid metadata in " + yamlpath + ": expecting a dict but got " + str(metadata))
      result.opaque_metadata.update(metadata)

    result.optimize_masks()
    return result

  TR_imagepack_yamlgen_parts = TR_imagepack.tr("parts",
    en="parts",
    zh_cn="部件",
    zh_hk="部件",
  )
  TR_imagepack_yamlgen_parts_kind = TR_imagepack.tr("parts_kind",
    en="parts_kind",
    zh_cn="部件类型",
    zh_hk="部件類型",
  )
  class CharacterSpritePartsBased_PartKind(enum.Enum):
    UNKNOWN = 0
    BASE = enum.auto()
    EYEBROW = enum.auto()
    EYE = enum.auto()
    MOUTH = enum.auto()
    FULLFACE = enum.auto()
    DECORATION = enum.auto()

  PRESET_YAMLGEN_PARTS_KIND_PRESETS = {
    "preset_kind_base" : (CharacterSpritePartsBased_PartKind.BASE, TR_imagepack.tr("preset_kind_base",
      en="base",
      zh_cn="基底",
      zh_hk="基底",
    )),
    "preset_kind_eyebrow" : (CharacterSpritePartsBased_PartKind.EYEBROW, TR_imagepack.tr("preset_kind_eyebrow",
      en="eyebrow",
      zh_cn="眉毛",
      zh_hk="眉毛",
    )),
    "preset_kind_eye" : (CharacterSpritePartsBased_PartKind.EYE, TR_imagepack.tr("preset_kind_eye",
      en="eye",
      zh_cn="眼睛",
      zh_hk="眼睛",
    )),
    "preset_kind_mouth" : (CharacterSpritePartsBased_PartKind.MOUTH, TR_imagepack.tr("preset_kind_mouth",
      en="mouth",
      zh_cn="嘴巴",
      zh_hk="嘴巴",
    )),
    "preset_kind_fullface" : (CharacterSpritePartsBased_PartKind.FULLFACE, TR_imagepack.tr("preset_kind_fullface",
      en="fullface",
      zh_cn="全脸",
      zh_hk="全臉",
    )),
    "preset_kind_decoration" : (CharacterSpritePartsBased_PartKind.DECORATION, TR_imagepack.tr("preset_kind_decoration",
      en="decoration",
      zh_cn="装饰",
      zh_hk="裝飾",
    )),
  }
  TR_imagepack_yamlgen_tags = TR_imagepack.tr("tags",
    en="tags",
    zh_cn="标签",
    zh_hk="標籤",
  )
  PRESET_YAMLGEN_TAGS_PRESETS = {
    "preset_tag_general" : TR_imagepack.tr("preset_tag_general",
      en="general",
      zh_cn="通用",
      zh_hk="通用",
    ),
    "preset_tag_smile" : TR_imagepack.tr("preset_tag_smile",
      en="smile",
      zh_cn="笑容",
      zh_hk="笑容",
    ),
    "preset_tag_angry" : TR_imagepack.tr("preset_tag_angry",
      en="angry",
      zh_cn="愤怒",
      zh_hk="憤怒",
    ),
    "preset_tag_sad" : TR_imagepack.tr("preset_tag_sad",
      en="sad",
      zh_cn="悲伤",
      zh_hk="悲傷",
    ),
    "preset_tag_surprised" : TR_imagepack.tr("preset_tag_surprised",
      en="surprised",
      zh_cn="惊讶",
      zh_hk="驚訝",
    ),
    "preset_tag_confused" : TR_imagepack.tr("preset_tag_confused",
      en="confused",
      zh_cn="困惑",
      zh_hk="困惑",
    ),
    "preset_tag_scared" : TR_imagepack.tr("preset_tag_scared",
      en="scared",
      zh_cn="害怕",
      zh_hk="害怕",
    ),
    "preset_tag_base" : TR_imagepack.tr("preset_tag_base",
      en="base",
      zh_cn="基底",
      zh_hk="基底",
    ),
  }
  TR_imagepack_yamlgen_parts_exclusions = TR_imagepack.tr("parts_exclusions",
    en="exclusions",
    zh_cn="互斥",
    zh_hk="互斥",
  )
  TR_imagepack_yamlgen_parts_depends = TR_imagepack.tr("parts_depends",
    en="depends",
    zh_cn="依赖",
    zh_hk="依賴",
  )

  @dataclasses.dataclass
  class CharacterSpritePartsBased_PartsDecl:
    name : str # 完整的名称，需要与图片名匹配
    codename : str # 完整名称头部的一串纯字母数字的字符串，用于给其他部分引用
    kind : str # 部件类型
    tags : list[str] | None = None # 标签
    exclusions : list[tuple[str, ...]] | None = None # 互斥的组合，列表中每一组都是互斥的部分的 codename，当前部件的任意一组中所有部件的 codename 已经全被选中的话就不能使用当前部件
    depends : list[tuple[str, ...]] | None = None # 依赖的组合，当前部件的任意一组中所有部件的 codename 都被选中的话才能使用当前部件

  @staticmethod
  def yaml_generation_charactersprite_parts_based(data : dict, layers : dict | None, masks : dict | None, composites : dict | None, metadata : dict | None) -> tuple[dict | None, dict | None, dict | None, dict | None]:
    part_kinds : collections.OrderedDict[str, str | Translatable] = collections.OrderedDict()
    tags : collections.OrderedDict[str, str | Translatable] = collections.OrderedDict()
    parts : collections.OrderedDict[str, ImagePack.CharacterSpritePartsBased_PartsDecl] = collections.OrderedDict() # codename -> parts_decl

    # 为了支持立绘在使用相同表情时能有不同的基底（比如不同的衣服样式），我们也有基底间的排列组合，这些标签会被用于生成基底的组合
    base_tags : list[str] = []

    kinds_enum_map : dict[str, ImagePack.CharacterSpritePartsBased_PartKind] = {}

    # 除了装饰部件以外，每种部件类型最多只能声明一次
    used_part_kinds : set[ImagePack.CharacterSpritePartsBased_PartKind] = set()

    def get_translated_partiallists(srclist : list[str]) -> list[tuple[str]]:
      # 把形如 ["M1Y1", "M2Y2"] 的依赖列表转换为形如 [("M1", "Y1"), ("M2", "Y2")] 的列表
      result = []
      for s in srclist:
        # 我们使用正则表达式进行匹配，每个部件代号由一个或多个大写字母和一个或多个数字组成
        pattern = r'[A-Z]+\d+'
        matches = re.findall(pattern, s)
        result.append(tuple(matches))
      return result

    for k, v in data.items():
      if k in ImagePack.TR_imagepack_yamlgen_parts_kind.get_all_candidates():
        if not isinstance(v, dict):
          raise PPInternalError("Invalid parts_kind in generation: expecting a dict but got " + str(v) + " (type: " + str(type(v)) + ")")
        for kind_name, kind_raw_tr in v.items():
          if isinstance(kind_raw_tr, str):
            kind_enum, kind_name_tr = ImagePack.PRESET_YAMLGEN_PARTS_KIND_PRESETS.get(kind_raw_tr, (ImagePack.CharacterSpritePartsBased_PartKind.UNKNOWN, None))
            kinds_enum_map[kind_name] = kind_enum
            part_kinds[kind_name] = kind_name_tr if kind_name_tr is not None else kind_raw_tr
            if kind_enum == ImagePack.CharacterSpritePartsBased_PartKind.UNKNOWN:
              raise PPInternalError("Custom part kind is not implemented yet: " + kind_raw_tr)
            elif kind_enum != ImagePack.CharacterSpritePartsBased_PartKind.DECORATION:
              if kind_enum in used_part_kinds:
                raise PPInternalError("Duplicate part kind: " + kind_name)
              used_part_kinds.add(kind_enum)
          elif isinstance(kind_raw_tr, dict):
            tr_code = "parts_kind_tr_" + kind_name
            kind_name_tr = ImagePack.TR_imagepack.tr(tr_code, **kind_raw_tr)
            part_kinds[kind_name]
            raise PPNotImplementedError("Custom part kind is not implemented yet")
          else:
            raise PPInternalError("Invalid parts_kind value (" + kind_name + ") in generation: expecting a str or dict but got " + str(kind_raw_tr) + " (type: " + str(type(kind_raw_tr)) + ")")
      elif k in ImagePack.TR_imagepack_yamlgen_tags.get_all_candidates():
        if not isinstance(v, dict):
          raise PPInternalError("Invalid tags in generation: expecting a dict but got " + str(v) + " (type: " + str(type(v)) + ")")
        for tag_name, tag_raw_tr in v.items():
          if isinstance(tag_raw_tr, str):
            if tag_name_tr := ImagePack.PRESET_YAMLGEN_TAGS_PRESETS.get(tag_raw_tr, None):
              tags[tag_name] = tag_name_tr
              if tag_raw_tr == "preset_tag_base":
                base_tags.append(tag_name)
            else:
              tags[tag_name] = tag_raw_tr
          elif isinstance(tag_raw_tr, dict):
            tr_code = "tags_tr_" + tag_name
            tag_name_tr = ImagePack.TR_imagepack.tr(tr_code, **tag_raw_tr)
            tags[tag_name] = tag_name_tr
          else:
            raise PPInternalError("Invalid tag value (" + tag_name + ") in generation: expecting a str or dict but got " + str(tag_raw_tr) + " (type: " + str(type(tag_raw_tr)) + ")")
      elif k in ImagePack.TR_imagepack_yamlgen_parts.get_all_candidates():
        if not isinstance(v, dict):
          raise PPInternalError("Invalid parts in generation: expecting a dict but got " + str(v) + " (type: " + str(type(v)) + ")")
        for part_kind, kind_data in v.items():
          if not isinstance(kind_data, dict):
            raise PPInternalError("Invalid part declaration in generation: expecting a dict but got " + str(kind_data) + " (type: " + str(type(kind_data)) + ")")
          for part_name, part_decl in kind_data.items():
            codename = part_name.split("-")[0]
            if re.match(r'^[A-Z]+\d+$', codename) is None:
              raise PPInternalError("Invalid part declaration in generation: codename must be a string of uppercase letters followed by digits: " + codename)
            if codename in parts:
              raise PPInternalError("Invalid part declaration in generation: codename " + codename + " is already used")
            part_entry = ImagePack.CharacterSpritePartsBased_PartsDecl(part_name, codename, part_kind, None, None, None)
            parts[codename] = part_entry
            if part_decl is None:
              pass
            elif isinstance(part_decl, str):
              part_entry.tags = [part_decl]
            elif isinstance(part_decl, list):
              part_entry.tags = part_decl
            elif isinstance(part_decl, dict):
              for key, value in part_decl.items():
                if key in ImagePack.TR_imagepack_yamlgen_tags.get_all_candidates():
                  if isinstance(value, str):
                    part_entry.tags = [value]
                  elif isinstance(value, list):
                    part_entry.tags = value
                  else:
                    raise PPInternalError("Invalid tags in part declaration in generation: expecting a str or list but got " + str(value) + " (type: " + str(type(value)) + ")")
                elif key in ImagePack.TR_imagepack_yamlgen_parts_exclusions.get_all_candidates():
                  part_entry.exclusions = get_translated_partiallists(value)
                elif key in ImagePack.TR_imagepack_yamlgen_parts_depends.get_all_candidates():
                  part_entry.depends = get_translated_partiallists(value)
                else:
                  raise PPInternalError("Unknown key in part declaration in generation: " + key + "(supported keys: "
                                        + str(ImagePack.TR_imagepack_yamlgen_tags.get_all_candidates()) + ", "
                                        + str(ImagePack.TR_imagepack_yamlgen_parts_exclusions.get_all_candidates()) + ", "
                                        + str(ImagePack.TR_imagepack_yamlgen_parts_depends.get_all_candidates()) + ")")
      else:
        raise PPInternalError("Unknown key in generation: " + k + "(supported keys: "
                              + str(ImagePack.TR_imagepack_yamlgen_parts.get_all_candidates()) + ", "
                              + str(ImagePack.TR_imagepack_yamlgen_parts_kind.get_all_candidates()) + ", "
                              + str(ImagePack.TR_imagepack_yamlgen_tags.get_all_candidates()) + ")")
    # 检查一下输入有没有问题，所有标签是否都有定义，所有部件是否都有定义
    # 同时我们也将对象分类
    base_parts_by_tag : dict[str, list[str]] = {}
    fullface_parts : list[str] = []
    parts_by_tag_kind : dict[str, typing.OrderedDict[str, list[str]]] = {}
    for codename, part in parts.items():
      if kinds_enum_map[part.kind] == ImagePack.CharacterSpritePartsBased_PartKind.FULLFACE:
        # 全脸表情部件不应该有标签、互斥或依赖
        if part.tags is not None:
          raise PPInternalError("Fullface part " + codename + " should not have tags")
        if part.exclusions is not None:
          raise PPInternalError("Fullface part " + codename + " should not have exclusions")
        if part.depends is not None:
          raise PPInternalError("Fullface part " + codename + " should not have dependencies")
        fullface_parts.append(codename)
        continue

      # 除全脸表情部件外，其他所有部件都应该有标签
      is_base = kinds_enum_map[part.kind] == ImagePack.CharacterSpritePartsBased_PartKind.BASE
      if part.tags is None:
        raise PPInternalError("Part " + codename + " should have tags")
      for t in part.tags:
        if t not in tags:
          raise PPInternalError("Part " + codename + " has a tag that does not exist: " + t)
        if is_base:
          if t not in base_tags:
            raise PPInternalError("Part " + codename + " is a base part but has a tag that is not a base tag: " + t)
        elif t in base_tags:
          raise PPInternalError("Part " + codename + " is not a base part but has a base tag: " + t)
        if is_base:
          if t not in base_parts_by_tag:
            base_parts_by_tag[t] = []
          base_parts_by_tag[t].append(codename)
        else:
          if t not in parts_by_tag_kind:
            parts_by_tag_kind[t] = collections.OrderedDict()
          if part.kind not in parts_by_tag_kind[t]:
            parts_by_tag_kind[t][part.kind] = []
          parts_by_tag_kind[t][part.kind].append(codename)
      if part.exclusions is not None:
        for exclusion in part.exclusions:
          for ex in exclusion:
            if ex not in parts:
              raise PPInternalError("Part " + codename + " has an exclusion that does not exist: " + ex)
            if (kinds_enum_map[parts[ex].kind] == ImagePack.CharacterSpritePartsBased_PartKind.BASE) != is_base:
              raise PPInternalError("Part " + codename + " has an exclusion that is not consistent with the base part status of " + ex)
      if part.depends is not None:
        for depend in part.depends:
          for de in depend:
            if de not in parts:
              raise PPInternalError("Part " + codename + " has a dependency that does not exist: " + de)
            if (kinds_enum_map[parts[de].kind] == ImagePack.CharacterSpritePartsBased_PartKind.BASE) != is_base:
              raise PPInternalError("Part " + codename + " has a dependency that is not consistent with the base part status of " + de)
    base_parts_combinations : collections.OrderedDict[tuple[str, ...], bool] = collections.OrderedDict() # 值一定是 True，我们只是要一个有序的集合
    all_parts_used : set[str] = set()
    for tag, base_parts_list in base_parts_by_tag.items():
      base_tuple = tuple(base_parts_list)
      if base_tuple in base_parts_combinations:
        continue
      base_parts_combinations[base_tuple] = True
      all_parts_used.update(base_parts_list)
    nonbase_parts_dedup_set : set[tuple[str, ...]] = set()
    nonbase_parts_combinations : list[tuple[str, ...]] = []
    def try_add_combinations(parts_list : tuple[str, ...]):
      # 如果已经生成过这个组合，直接返回
      refnames_sorted_tuple = tuple(sorted(parts_list))
      if refnames_sorted_tuple in nonbase_parts_dedup_set:
        return
      # 检查是否有互斥或者依赖条件没有满足
      for part in parts_list:
        part_decl = parts[part]
        if part_decl.exclusions is not None:
          for exclusion in part_decl.exclusions:
            if all(p in parts_list for p in exclusion):
              return
        if part_decl.depends is not None:
          is_dependency_satisfied = False
          for depend in part_decl.depends:
            if all(p in parts_list for p in depend):
              is_dependency_satisfied = True
              break
          if not is_dependency_satisfied:
            return
      # 加到组合里
      nonbase_parts_combinations.append(parts_list)
      nonbase_parts_dedup_set.add(refnames_sorted_tuple)
      all_parts_used.update(parts_list)
    for tag in tags.keys():
      if tag in base_tags:
        continue
      if tag not in parts_by_tag_kind:
        continue
      parts_by_kind = parts_by_tag_kind[tag]
      main_parts : list[list[str]] = [] # 眉毛、眼睛、嘴巴
      d_parts : list[list[str]] = [] # 装饰
      for kind in part_kinds.keys():
        kind_enum = kinds_enum_map[kind]
        if kind_enum == ImagePack.CharacterSpritePartsBased_PartKind.DECORATION:
          if cur_d_parts := parts_by_kind.get(kind):
            d_parts.append(cur_d_parts)
          continue
        if kind_enum in (ImagePack.CharacterSpritePartsBased_PartKind.BASE, ImagePack.CharacterSpritePartsBased_PartKind.FULLFACE):
          continue
        # 剩下的应该只有眉毛、眼睛、嘴巴
        if kind_enum not in (ImagePack.CharacterSpritePartsBased_PartKind.EYEBROW, ImagePack.CharacterSpritePartsBased_PartKind.EYE, ImagePack.CharacterSpritePartsBased_PartKind.MOUTH):
          raise PPNotImplementedError("Unknown part kind: " + kind)
        if cur_main_parts := parts_by_kind.get(kind):
          main_parts.append(cur_main_parts)
      # 生成所有可能的组合
      for main_parts_combination in itertools.product(*main_parts):
        try_add_combinations(main_parts_combination)
        if len(d_parts) > 0:
          for num_d_parts in range(1, len(d_parts)+1):
            for d_parts_combination_list in itertools.combinations(d_parts, num_d_parts):
              for d_parts_combination in itertools.product(*d_parts_combination_list):
                try_add_combinations(main_parts_combination + d_parts_combination)
    for fullface_part in fullface_parts:
      try_add_combinations((fullface_part,))
    # 仅供调试：把所有组合都打印出来
    # for combination in nonbase_parts_combinations:
    #   print(combination)
    # 如果有部件没有被用到，报错
    for codename, part in parts.items():
      if codename not in all_parts_used:
        raise PPInternalError("Part " + codename + " is not used in any combination")
    # 如果没有组合结果，报错
    if len(base_parts_combinations) == 0 or len(nonbase_parts_combinations) == 0:
      raise PPInternalError("No valid combinations")
    # 生成结果
    # 首先按照部件的声明顺序添加图层，每个部件都是一个图层
    result_layers : dict[str, dict] = {}
    if layers is not None:
      result_layers.update(layers)
    for codename, part in parts.items():
      part_dict = {}
      if kinds_enum_map[part.kind] == ImagePack.CharacterSpritePartsBased_PartKind.BASE:
        part_dict[ImagePack.TR_imagepack_yamlparse_flags.get()] = ImagePack.TR_imagepack_yamlparse_base.get()
      result_layers[part.name] = part_dict
    result_composites : dict[str, list[str]] = {}
    if composites is not None:
      raise PPInternalError("Manually-specified composites are not supported in this generation algorithm")
    for base_combination in base_parts_combinations.keys():
      combination_codename_base = "".join(base_combination)
      combination_layers_base = [parts[part].name for part in base_combination]
      for nonbase_combination in nonbase_parts_combinations:
        combination_codename = combination_codename_base + "".join(nonbase_combination)
        combination_layers = combination_layers_base + [parts[part].name for part in nonbase_combination]
        result_composites[combination_codename] = combination_layers
    return (result_layers, masks, result_composites, metadata)

  @staticmethod
  def handle_yaml_generation(generation : dict[str, typing.Any], layers : dict | None, masks : dict | None, composites : dict | None, metadata : dict | None) -> tuple[dict | None, dict | None, dict | None, dict | None]:
    if "charactersprite_parts_based" in generation:
      data = generation["charactersprite_parts_based"]
      return ImagePack.yaml_generation_charactersprite_parts_based(data, layers, masks, composites, metadata)
    raise PPInvalidOperationError("Unknown generation algorithm : " + str(generation))

  # 以下是提供给外部使用的接口

  @staticmethod
  def create_from_asset_archive(path : str):
    return ImagePack.create_from_path(path)

  @staticmethod
  def build_asset_archive(name : str, destpath : str, yamlpath : str, references_filename : str = "references.yml"):
    pack = ImagePack.build_image_pack_from_yaml(yamlpath)
    pack.write_to_path(destpath)
    basepath = os.path.dirname(os.path.abspath(yamlpath))
    references_path = os.path.join(basepath, references_filename)
    descriptor = ImagePackDescriptor(pack, name, references_path, destpath)
    ImagePack.add_descriptor(descriptor)
    return descriptor

  @classmethod
  def get_candidate_id(cls, descriptor : "ImagePackDescriptor") -> str:
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError("Unexpected descriptor type: " + str(type(descriptor)))
    return descriptor.get_pack_id()

  @classmethod
  def get_candidate_name(cls, descriptor : "ImagePackDescriptor") -> Translatable | str:
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError("Unexpected descriptor type: " + str(type(descriptor)))
    return descriptor.get_name()

  def dump_asset_info_json(self, name : str) -> dict:
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
      result["metadata"] = ImagePack.get_metadata_dict_for_serialization(self.opaque_metadata)
    # 如果有 Descriptor，就把 Descriptor 中的信息也放进去
    if descriptor := self.get_descriptor_by_id(name):
      result["descriptor"] = descriptor.dump_asset_info_json()
    return result

  @staticmethod
  def tool_main(args : list[str] | None = None):
    # 创建一个有以下参数的 argument parser: [--debug] [--create <yml> | --load <zip> | --asset <name>] [--save <zip>] [--fork [args]] [--export <dir>]
    parser = argparse.ArgumentParser(description="ImagePack tool")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--create", metavar="<yml>", help="Create a new image pack from a yaml file")
    parser.add_argument("--load", metavar="<zip>", help="Load an existing image pack from a zip file")
    parser.add_argument("--asset", metavar="<name>", help="Load an existing image pack from embedded assets")
    parser.add_argument("--save", metavar="<zip>", help="Save the image pack to a zip file")
    parser.add_argument("--shrink", metavar="<ratio>", help="Shrink the image pack by the specified ratio (0-1)")
    parser.add_argument("--fork", nargs="*", metavar="[args]", help="Fork the image pack with the given arguments")
    parser.add_argument("--export", metavar="<dir>", help="Export the image pack to a directory")
    parser.add_argument("--export-overview", metavar="<path>", help="Export a single overview image to the specified path")
    parser.add_argument("--export-overview-html", metavar="<path>", help="Export an interactive HTML to the specified path; require --asset and --export-overview")
    if args is None:
      args = sys.argv[1:]
    parsed_args = parser.parse_args(args)

    if parsed_args.debug:
      ImagePack._debug = True

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
    if parsed_args.export_overview_html and (parsed_args.export_overview is None or parsed_args.asset is None):
      raise PPInternalError("Cannot export overview HTML without --export-overview and --asset")

    ImagePack.print_executing_command("start pipeline")

    current_pack = None
    current_pack_descriptor = None
    if parsed_args.create is not None:
      ImagePack.print_executing_command("--create")
      # 创建一个新的 imagepack
      # 从 yaml 中读取
      current_pack = ImagePack.build_image_pack_from_yaml(parsed_args.create)
    elif parsed_args.load is not None:
      # 从 zip 中读取
      ImagePack.print_executing_command("--load")
      current_pack = ImagePack.create_from_path(parsed_args.load)
    elif parsed_args.asset is not None:
      # 从 asset 中读取
      ImagePack.print_executing_command("--asset")
      manager = AssetManager.get_instance()
      current_pack = manager.get_asset(parsed_args.asset)
      if current_pack is None:
        raise PPInternalError("Asset not found: " + parsed_args.asset)
      if not isinstance(current_pack, ImagePack):
        raise PPInternalError("Asset is not an image pack: " + parsed_args.asset)
      current_pack_descriptor = ImagePack.get_descriptor_by_id(parsed_args.asset)

    if parsed_args.save is not None:
      # 保存到 zip 中
      ImagePack.print_executing_command("--save")
      if current_pack is None:
        raise PPInternalError("Cannot save without input")
      current_pack.write_to_path(parsed_args.save)

    if parsed_args.shrink is not None:
      # 缩小 imagepack
      ImagePack.print_executing_command("--shrink")
      if current_pack is None:
        raise PPInternalError("Cannot shrink without input")
      ratio = decimal.Decimal(parsed_args.shrink)
      if ratio <= 0 or ratio >= 1:
        raise PPInternalError("Invalid shrink ratio: " + str(ratio))
      current_pack = current_pack.fork_and_shrink(ratio)

    if parsed_args.fork is not None:
      # 创建一个新的 imagepack, 将 mask 所影响的部分替换掉
      ImagePack.print_executing_command("--fork")
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
      ImagePack.print_executing_command("--export")
      if current_pack is None:
        raise PPInternalError("Cannot export without input")
      pathlib.Path(parsed_args.export).mkdir(parents=True, exist_ok=True)
      for i, comp in enumerate(current_pack.composites):
        outputname = comp.basename + '.png'
        img = current_pack.get_composed_image(i)
        img.save_png(os.path.join(parsed_args.export, outputname))

    if parsed_args.export_overview is not None:
      ImagePack.print_executing_command("--export-overview")
      if current_pack is None:
        raise PPInternalError("Cannot export overview without input")
      current_pack.write_overview_image(parsed_args.export_overview, current_pack_descriptor, parsed_args.export_overview_html)

  _debug = False

  @staticmethod
  def printstatus(s : str):
    if not ImagePack._debug:
      return
    MessageHandler.info(s)

  _tr_algo_checkpoint = TR_imagepack.tr("algo_checkpoint",
    en="Algorithm Checkpoint: {name}",
    zh_cn="算法检查点：{name}",
    zh_hk="算法檢查點：{name}"
  )
  @staticmethod
  def print_checkpoint(name : str):
    ImagePack.printstatus(ImagePack._tr_algo_checkpoint.format(name=name))

  _tr_executing_command = TR_imagepack.tr("executing_command",
    en="Executing command: {command}",
    zh_cn="执行命令：{command}",
    zh_hk="執行命令：{command}"
  )
  @staticmethod
  def print_executing_command(command : str):
    ImagePack.printstatus(ImagePack._tr_executing_command.format(command=command))

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
  pngmetadata : dict[str, str] # 写入 PNG 文件的 iTXt chunk 的元数据
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
    self.pngmetadata = {}
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

  def write(self, pngpath : str):
    # 绘制概览图
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
      num_diffs_at_right = min(max_diffs_in_right_side, len(self.diffs))
      for i in range(num_diffs_at_right):
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
      for i in range(num_diffs_at_right, len(self.diffs)):
        equiv_index = i - num_diffs_at_right
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
    pnginfo = None
    if len(self.pngmetadata) > 0:
      pnginfo = PIL.PngImagePlugin.PngInfo()
      for k, v in self.pngmetadata.items():
        pnginfo.add_itxt(k, v)
    overview.save(pngpath, format="PNG", pnginfo=pnginfo)

class _ImagePackHTMLExport:
  @staticmethod
  def escape(htmlstring : str) -> str:
    escapes = {'\"': '&quot;',
              '\'': '&#39;',
              '<': '&lt;',
              '>': '&gt;'}
    # This is done first to prevent escaping other escapes.
    htmlstring = htmlstring.replace('&', '&amp;')
    for seq, esc in escapes.items():
      htmlstring = htmlstring.replace(seq, esc)
    return htmlstring

  @staticmethod
  def getBase64(image : ImageWrapper) -> bytes:
    if image.path is not None:
      with open(image.path, 'rb') as f:
        return base64.b64encode(f.read())
    f = io.BytesIO()
    image.get().save(f, format='PNG')
    bytes_out = f.getvalue()
    encoded = base64.b64encode(bytes_out)
    return encoded

  @staticmethod
  def convertToJSVariable(data : typing.Any, variable_name : str) -> str:
    def getValueRecursive(data):
      if isinstance(data, int):
        return str(data)
      if isinstance(data, str):
        return '"' + data + '"'
      if isinstance(data, (list, tuple)):
        result = []
        for item in data:
          result.append(getValueRecursive(item))
        return '[' + ','.join(result) + ']'
      if isinstance(data, dict):
        result = []
        for key, value in data.items():
          assert isinstance(key, str) or isinstance(key, int)
          result.append('"' + str(key) + '":' + getValueRecursive(value))
        return '{' + ','.join(result) + '}'
      raise RuntimeError("Unexpected data type " + str(type(data)))
    return "const " + variable_name + " = " + getValueRecursive(data) + ";"

  TR_overview_start = ImagePack.TR_imagepack.tr("overview_html_start",
    en="Start",
    zh_cn="开始",
    zh_hk="開始",
  )
  TR_overview_finish = ImagePack.TR_imagepack.tr("overview_html_finish",
    en="Finish",
    zh_cn="完成",
    zh_hk="完成",
  )

  HTML_UI_LABELS : typing.ClassVar[dict[str, Translatable]] = {
    "zoom_label" : ImagePack.TR_imagepack.tr("overview_html_zoom_label",
      en="Zoom: ",
      zh_cn="缩放：",
      zh_hk="縮放：",
    ),
    "show_codenames_label" : ImagePack.TR_imagepack.tr("overview_html_show_codenames_label",
      en="Show layer code only",
      zh_cn="只显示图层编号",
      zh_hk="只顯示圖層編號",
    ),
    "composition_label" : ImagePack.TR_imagepack.tr("overview_html_composition_label",
      en="Composition: ",
      zh_cn="组合：",
      zh_hk="組合：",
    ),
    "save_view" : ImagePack.TR_imagepack.tr("overview_html_save_view",
      en="Save image",
      zh_cn="保存图片",
      zh_hk="保存圖片",
    ),
    "preset_label" : ImagePack.TR_imagepack.tr("overview_html_preset_label",
      en="Preset: ",
      zh_cn="预设：",
      zh_hk="預設：",
    ),
    "preset_apply" : ImagePack.TR_imagepack.tr("overview_html_preset_apply",
      en="Apply",
      zh_cn="应用",
      zh_hk="應用",
    ),
  }
  @staticmethod
  def write_html(html_path : str, imgpack : ImagePack, descriptor : 'ImagePackDescriptor',
                 html_title : str = "Interactive Imagepack viewer",
                 html_author : str = "PrepPipe Compiler",
                 html_description : str = "Interactive Imagepack viewer") -> None:
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError("HTML export requires descriptor (cannot be used on temporarily created imagepack)")

    imgdata : list[str] = [] # html img elements
    layer_pos_size_info : list[tuple[int,int,int,int]] = [] # x, y, w, h
    layer_codenames : list[str] = [] # 应该都是代码名 (L0, ...)
    layer_rawnames : list[str] = [] # 应该是代码名+描述（L0-白天）
    for i, layer in enumerate(imgpack.layers):
      # 首先把元数据加进去
      layer_pos_size_info.append((layer.offset_x, layer.offset_y, layer.width, layer.height))
      rawname = layer.basename
      codename = rawname.split("-")[0]
      layer_codenames.append(codename)
      layer_rawnames.append(rawname)
      # 最后生成图片元素。这些图片都是塞在一个不可见的 div 中，不会被直接显示，我们只是把内容放在这
      b64encoded = _ImagePackHTMLExport.getBase64(layer.patch).decode('utf-8')
      imgdata.append(f'<img id="img_l{i}" src="data:image/png;base64, {b64encoded}" style="position: absolute; left: 0px; top: 0px;" />')
    composites_descriptive_names : dict[str, str] = {}
    for k, v in descriptor.composites_references.items():
      composites_descriptive_names[k] = v.get()

    # 我们要在这里确定图层类别的组合关系（比如一般来说立绘表情的图层组是 B[MYK|Q]D*）
    # 作画时我们可能有其他的图层类别的命名规则（比如 M 可能有多个子类别）
    # 在此我们都希望能够自动发现这些顺序关系
    # 我们先构建一个图层类别的有向图，如果类别B紧挨着类别A，则画一条从A到B的有向边
    # 然后我们对这个有向图进行拓扑排序，得到的顺序就是我们希望的顺序
    layer_group_outgoing_edges : dict[str, collections.OrderedDict[str, bool]] = {} # 从某个类别出发的有向边（不含自环）
    layer_group_incoming_edges : dict[str, collections.OrderedDict[str, bool]] = {} # 到达某个类别的有向边（不含自环）
    layer_group_with_self_edges : collections.OrderedDict[str, bool] = collections.OrderedDict() # 有自环的类别
    def add_layer_group_transition_edge(from_group : str, to_group : str):
      if from_group == to_group:
        layer_group_with_self_edges[from_group] = True
        return
      if from_group not in layer_group_outgoing_edges:
        layer_group_outgoing_edges[from_group] = collections.OrderedDict()
      layer_group_outgoing_edges[from_group][to_group] = True
      if to_group not in layer_group_incoming_edges:
        layer_group_incoming_edges[to_group] = collections.OrderedDict()
      layer_group_incoming_edges[to_group][from_group] = True
    all_layer_groups : collections.OrderedDict[str, int] = collections.OrderedDict()
    for codename in descriptor.composites_code:
      # 先把 codename 分成图层类别的列表 （即把 B0M1Y2K3D4 分为 ['B', 'M', 'Y', 'K', 'D']）
      layer_group_names : list[str] = []
      last_layer_group_name = ''
      for c in codename:
        if c.isdigit():
          if len(last_layer_group_name) > 0:
            layer_group_names.append(last_layer_group_name)
            last_layer_group_name = ''
          continue
        last_layer_group_name += c
      if len(last_layer_group_name) > 0:
        layer_group_names.append(last_layer_group_name)
      # 记录已有的类别（每个只记一次）
      cur_set = set()
      for layer_group in layer_group_names:
        if layer_group in cur_set:
          continue
        cur_set.add(layer_group)
        if layer_group not in all_layer_groups:
          all_layer_groups[layer_group] = 1
        else:
          all_layer_groups[layer_group] += 1
      # layer_group_names.insert(0, 'START')
      # layer_group_names.append('FINISH')
      # 然后我们把这个列表中的相邻元素两两配对，加入有向图
      for i in range(len(layer_group_names) - 1):
        add_layer_group_transition_edge(layer_group_names[i], layer_group_names[i + 1])
    # 找到所有的等效图层类别，它们应该由一样的入边和出边
    equivalence_map : dict[tuple[tuple[str,...], tuple[str,...]], list[str]] = {} # <入边，出边> -> 满足条件的图层类别
    for layer_group in all_layer_groups.keys():
      inedge_tuple = tuple(layer_group_incoming_edges.get(layer_group, {}).keys())
      outedge_tuple = tuple(layer_group_outgoing_edges.get(layer_group, {}).keys())
      key_tuple = (inedge_tuple, outedge_tuple)
      if key_tuple not in equivalence_map:
        equivalence_map[key_tuple] = [layer_group]
      else:
        equivalence_map[key_tuple].append(layer_group)
    # 做一次拓扑排序 (DFS)
    layer_group_orders : list[str] = []
    worklist : collections.deque[str] = collections.deque()
    def add_to_worklist(layer_group):
      layer_group_orders.append(layer_group)
      worklist.append(layer_group)
    def drain_worklist():
      while len(worklist) > 0:
        cur_layer_group = worklist.pop() # DFS
        if cur_layer_group in layer_group_outgoing_edges:
          outedges = layer_group_outgoing_edges[cur_layer_group]
          for next_layer_group in outedges.keys():
            layer_group_incoming_edges[next_layer_group].pop(cur_layer_group)
            if len(layer_group_incoming_edges[next_layer_group]) == 0:
              add_to_worklist(next_layer_group)
              drain_worklist()
    for layer_group in all_layer_groups.keys():
      if layer_group not in layer_group_incoming_edges:
        if layer_group not in layer_group_orders:
          add_to_worklist(layer_group)
          drain_worklist()
    if len(layer_group_orders) < len(all_layer_groups):
      raise PPInternalError("Cycle detected in layer group ordering")
    mandatory_layer_groups = []
    for layer_group, count in all_layer_groups.items():
      if count == len(descriptor.composites_code):
        mandatory_layer_groups.append(layer_group)
    variadic_layer_groups = list(layer_group_with_self_edges.keys())
    equivalent_layer_groups : dict[str, list[str]] = {}
    for layer_groups in equivalence_map.values():
      if len(layer_groups) > 1:
        for layer_group in layer_groups:
          equivalent_layer_groups[layer_group] = layer_groups
    layer_group_descriptive_names : dict[str, str] = {} # TODO

    datadecl : list[str] = [
      _ImagePackHTMLExport.convertToJSVariable(imgpack.width, "total_width"),
      _ImagePackHTMLExport.convertToJSVariable(imgpack.height, "total_height"),
      _ImagePackHTMLExport.convertToJSVariable(descriptor.packtype.name, "imgpack_type"),
      _ImagePackHTMLExport.convertToJSVariable(layer_pos_size_info, "layer_pos_size_info"),
      _ImagePackHTMLExport.convertToJSVariable(layer_codenames, "layer_codenames"),
      _ImagePackHTMLExport.convertToJSVariable(layer_rawnames, "layer_rawnames"),
      _ImagePackHTMLExport.convertToJSVariable(descriptor.composites_code, "composites_codenames"),
      _ImagePackHTMLExport.convertToJSVariable(composites_descriptive_names, "composites_descriptive_names"),
      _ImagePackHTMLExport.convertToJSVariable(layer_group_orders, "layer_group_orders"),
      _ImagePackHTMLExport.convertToJSVariable(layer_group_descriptive_names, "layer_group_descriptive_names"),
      _ImagePackHTMLExport.convertToJSVariable(mandatory_layer_groups, "mandatory_layer_groups"),
      _ImagePackHTMLExport.convertToJSVariable(variadic_layer_groups, "variadic_layer_groups"),
      _ImagePackHTMLExport.convertToJSVariable(equivalent_layer_groups, "equivalent_layer_groups"),
    ]

    ui_translations = {}
    for k, v in _ImagePackHTMLExport.HTML_UI_LABELS.items():
      ui_translations[k] = v.get()

    parameter_dict : dict[bytes, str] = {}
    parameter_dict[b"pp_imgpack_title"] = _ImagePackHTMLExport.escape(html_title)
    parameter_dict[b"pp_imgpack_author"] = _ImagePackHTMLExport.escape(html_author)
    parameter_dict[b"pp_imgpack_description"] = _ImagePackHTMLExport.escape(html_description)
    parameter_dict[b"pp_imgpack_script_datadecl"] = "\n".join(datadecl)
    parameter_dict[b"pp_imgpack_imgdata"] = "\n".join(imgdata)
    parameter_dict[b"pp_imgpack_ui_translations"] = _ImagePackHTMLExport.convertToJSVariable(ui_translations, "ui_translations")

    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "imagepackhelper", "overview_html_template.html")
    with open(html_path, "wb") as dst:
      with open(template_path, "rb") as f:
        while line := f.readline():
          if line.startswith(b"$$"):
            varname = line[2:].strip()
            if varname not in parameter_dict:
              raise PPInternalError(f"Template variable {varname} not found in parameter_dict")
            dst.write(parameter_dict[varname].encode("utf-8"))
            dst.write(b"\n")
          else:
            dst.write(line)

@ImagePack._descriptor
class ImagePackDescriptor:
  # 这是只给素材引用的翻译域，只有根据素材动态生成的内容才能放这。其余还是用 ImagePack.TR_imagepack
  TR_ref = TranslationDomain("imagepack-reference")

  class ImagePackType(enum.Enum):
    BACKGROUND = enum.auto() # 背景
    CHARACTER = enum.auto() # 角色立绘

  class MaskParamType(enum.Enum):
    IMAGE = enum.auto() # 图片选区
    COLOR = enum.auto() # 颜色选区

  class MaskType(enum.Enum):
    BACKGROUND_SCREEN = enum.auto(), ImagePack.TR_imagepack.tr("maskparam_screen",
      en="Screen",
      zh_cn="屏幕",
      zh_hk="屏幕",
    )
    BACKGROUND_COLOR_INDICATOR = enum.auto(), ImagePack.TR_imagepack.tr("maskparam_color_indicator",
      en="IndicatorColor",
      zh_cn="指示色",
      zh_hk="指示色",
    )
    CHARACTER_COLOR_CLOTH = enum.auto(), ImagePack.TR_imagepack.tr("maskparam_color_cloth",
      en="ClothColor",
      zh_cn="衣服颜色",
      zh_hk="衣服顏色",
    )
    CHARACTER_COLOR_HAIR = enum.auto(), ImagePack.TR_imagepack.tr("maskparam_color_hair",
      en="HairColor",
      zh_cn="发色",
      zh_hk="髮色",
    )
    CHARACTER_COLOR_DECORATE = enum.auto(), ImagePack.TR_imagepack.tr("maskparam_color_decorate",
      en="DecorateColor",
      zh_cn="装饰色",
      zh_hk="裝飾色",
    )

    def __new__(cls, *args, **kwds):
      obj = object.__new__(cls)
      obj._value_ = args[0]
      return obj

    def __init__(self, _, trname : Translatable):
      self._trname_ = trname

    @property
    def trname(self) -> Translatable:
      return self._trname_

    def get_param_type(self) -> "ImagePackDescriptor.MaskParamType":
      if self == ImagePackDescriptor.MaskType.BACKGROUND_SCREEN:
        return ImagePackDescriptor.MaskParamType.IMAGE
      return ImagePackDescriptor.MaskParamType.COLOR

  @dataclasses.dataclass
  class LayerInfo:
    offset_x : int
    offset_y : int
    width : int
    height : int

    def to_tuple(self) -> tuple[int, int, int, int]:
      return (self.offset_x, self.offset_y, self.width, self.height)

    @staticmethod
    def from_tuple(t : tuple[int, int, int, int]) -> "ImagePackDescriptor.LayerInfo":
      return ImagePackDescriptor.LayerInfo(t[0], t[1], t[2], t[3])

  # 对于以下大部分使用 Translatable | str 的参数来说，如果有 references.yml 文件，我们会从中读取并使用 Translatable
  # 否则就只用 str 存现有的推导出来的值
  pack_id : str # 图片组的 ID
  topref : Translatable | str # 所对应资源的名称
  authortags : tuple[str, ...] # 作者标签，如果有多个作者同时提供了相同名称的素材，可以用这个来区分
  packtype : ImagePackType # 图片组的类型
  masktypes : tuple[MaskType, ...] # 有几个选区、各自的类型
  composites_code : list[str] # 各个差分组合的编号（字母数字组合）
  composites_layers : list[list[int]] # 各个差分组合所用的图层
  composites_references : dict[str, Translatable] # 如果某些差分组合有（非编号的）名称，那么它们的名称存在这里
  layer_info : list[LayerInfo] # 各个图层的信息
  size : tuple[int, int] # 整体大小
  bbox : tuple[int, int, int, int] # 边界框

  def __getstate__(self):
    return {
      'pack_id': self.pack_id,
      'topref': self.topref,
      'authortags': self.authortags,
      'packtype': self.packtype.name,
      'masktypes': [m.name for m in self.masktypes],
      'composites_code': self.composites_code,
      'composites_layers': self.composites_layers,
      'composites_references': self.composites_references,
      'layer_info': [info.to_tuple() for info in self.layer_info],
      'size': self.size,
      'bbox': self.bbox
    }

  def __setstate__(self, state):
    self.pack_id = state['pack_id']
    self.topref = state['topref']
    self.authortags = state['authortags']
    self.packtype = ImagePackDescriptor.ImagePackType[state['packtype']]
    self.masktypes = tuple([ImagePackDescriptor.MaskType[s] for s in state['masktypes']])
    self.composites_code = state['composites_code']
    self.composites_layers = state['composites_layers']
    self.composites_references = state['composites_references']
    self.layer_info = [ImagePackDescriptor.LayerInfo.from_tuple(info) for info in state['layer_info']]
    self.size = state['size']
    self.bbox = state['bbox']

  # 以下作为缓存的信息，不存文件
  composites_code_map : dict[str, int] | None = None

  def get_pack_id(self) -> str:
    return self.pack_id

  def get_name(self) -> Translatable | str:
    return self.topref

  def get_author_tags(self) -> tuple[str, ...]:
    return self.authortags

  def get_image_pack_type(self) -> ImagePackType:
    return self.packtype

  def get_masks(self) -> tuple[MaskType, ...]:
    # 获取该图片组所有的选区
    # 由于要结合前端的参数读取，我们这里使用 enum 来表示选区的类型
    return self.masktypes

  def get_all_composites(self) -> typing.Iterable[str]:
    # 获取该图片组所有的组合
    return self.composites_code

  def get_default_composite(self) -> str:
    # 获取默认的组合
    return self.composites_code[0]

  def try_get_composite_name(self, code : str) -> Translatable | None:
    return self.composites_references.get(code)

  def is_valid_composite(self, code : str) -> bool:
    # 检查一个组合是否有效
    if self.composites_code_map is None:
      self.composites_code_map = {}
      for i in range(0, len(self.composites_code)):
        self.composites_code_map[self.composites_code[i]] = i
    return code in self.composites_code_map

  def get_composite_index_from_code(self, code : str) -> int:
    if not self.is_valid_composite(code):
      raise PPInternalError("Invalid composite code: " + code)
    if self.composites_code_map is None:
      # 应该在 self.is_valid_composite() 中初始化的
      raise PPInternalError("composites_code_map not initialized?")
    return self.composites_code_map[code]

  def get_layers_from_composite_index(self, index : int) -> typing.Iterable[int]:
    return self.composites_layers[index]

  def get_composite_code_from_name(self, name : str) -> str | None:
    if self.is_valid_composite(name):
      return name
    for code, tr in self.composites_references.items():
      if name in tr:
        return code
    return None

  def get_layer_info(self, index : int) -> LayerInfo:
    return self.layer_info[index]

  def get_size(self) -> tuple[int, int]:
    # 获取图片组的整体大小
    return self.size

  def get_bbox(self) -> tuple[int, int, int, int]:
    # 获取图片组的边界框(bbox)
    return self.bbox

  def __init__(self, pack : ImagePack, pack_name : str, references_path : str, pack_path : str):
    # 首先在读取 references.yml 之前，尝试从图片包本体中读取信息并初始化所有成员
    self.pack_id = pack_name
    self.topref = self.pack_id
    # 尝试从图片包中找到作者信息
    if "author" in pack.opaque_metadata:
      self.authortags = tuple(pack.opaque_metadata["author"])
    else:
      self.authortags = tuple()
    # 关于判断图片包类型，我们目前假设有图片选区的都是背景，没有的都是角色立绘
    is_screen_found = False
    for mask in pack.masks:
      if mask.projective_vertices is not None:
        is_screen_found = True
        break
    masktypelist = []
    if is_screen_found:
      self.packtype = ImagePackDescriptor.ImagePackType.BACKGROUND
      for mask in pack.masks:
        if mask.projective_vertices is not None:
          masktypelist.append(ImagePackDescriptor.MaskType.BACKGROUND_SCREEN)
        else:
          masktypelist.append(ImagePackDescriptor.MaskType.BACKGROUND_COLOR_INDICATOR)
    else:
      self.packtype = ImagePackDescriptor.ImagePackType.CHARACTER
      for mask in pack.masks:
        match len(masktypelist):
          case 0:
            masktypelist.append(ImagePackDescriptor.MaskType.CHARACTER_COLOR_CLOTH)
          case 1:
            masktypelist.append(ImagePackDescriptor.MaskType.CHARACTER_COLOR_HAIR)
          case _:
            masktypelist.append(ImagePackDescriptor.MaskType.CHARACTER_COLOR_DECORATE)
    self.masktypes = tuple(masktypelist)
    # 从图片包组合的名称中提取编号
    regex_pattern = re.compile(r'^(?P<code>[A-Z0-9]+)(?:-.+)?$')
    def get_code_from_composite_name(name : str) -> str:
      # 名称要么是纯编号，要么是"<编号>-<描述>"
      # 编号是只由大写字母和数字组成的字符串，我们不管其他的内容
      if result := re.match(regex_pattern, name):
        return result.group("code")
      raise PPInternalError("Cannot extract code from composite name: " + name)
    self.composites_code = [get_code_from_composite_name(composite.basename) for composite in pack.composites]
    self.composites_layers = [composite.layers for composite in pack.composites]
    self.composites_references = {}
    self.layer_info = []
    for layer in pack.layers:
      info = ImagePackDescriptor.LayerInfo(layer.offset_x, layer.offset_y, layer.width, layer.height)
      self.layer_info.append(info)
    self.size = (pack.width, pack.height)
    # 计算 bbox，取所有基底图的并集
    xmin = pack.width
    ymin = pack.height
    xmax = 0
    ymax = 0
    for l in pack.layers:
      if not l.base:
        continue
      xmin = min(xmin, l.offset_x)
      ymin = min(ymin, l.offset_y)
      xmax = max(xmax, l.offset_x + l.width)
      ymax = max(ymax, l.offset_y + l.height)
      if xmin == 0 and ymin == 0 and xmax == pack.width and ymax == pack.height:
        break
    self.bbox = (xmin, ymin, xmax, ymax)

    # 默认的初始化完毕，开始读取 references.yml
    references = ImagePack.load_yaml(references_path)
    if len(references) == 0:
      return
    # 为检查是否有没用上的项
    used_keys = set()
    used_keys.add("include")
    if "reference" in references:
      used_keys.add("reference")
      refvalue = references["reference"]
      if isinstance(refvalue, dict):
        tr_id = self.pack_id + "-reference"
        tr_obj = ImagePackDescriptor.TR_ref.tr(code=tr_id, **refvalue)
        self.topref = tr_obj
      elif isinstance(refvalue, str):
        self.topref = refvalue
      else:
        raise PPInternalError("Invalid reference value: " + str(refvalue))
    if "author_tags" in references:
      used_keys.add("author_tags")
      tags = references["author_tags"]
      if not isinstance(tags, list):
        raise PPInternalError("Invalid author tags: " + str(tags))
      for t in tags:
        if not isinstance(t, str):
          raise PPInternalError("Invalid author tag: " + str(t))
      self.authortags = tuple(tags)
    if "kind" in references:
      used_keys.add("kind")
      kind_str = references["kind"]
      self.packtype = ImagePackDescriptor.ImagePackType[kind_str]
    if "masks" in references:
      used_keys.add("masks")
      masks = references["masks"]
      if not isinstance(masks, list):
        raise PPInternalError("Invalid masks: " + str(masks))
      masktypelist = []
      for m in masks:
        if not isinstance(m, str):
          raise PPInternalError("Invalid mask type: " + str(m))
        masktypelist.append(ImagePackDescriptor.MaskType[m])
      self.masktypes = tuple(masktypelist)
    if "composites" in references:
      used_keys.add("composites")
      valid_composites = set(self.composites_code)
      for code, d in references["composites"].items():
        if code not in valid_composites:
          raise PPInternalError("Invalid composite code: " + code)
        if not isinstance(d, dict):
          raise PPInternalError("Invalid composite translatable arguments: " + str(d))
        tr_id = self.pack_id + "-composite-" + code
        tr_obj = ImagePackDescriptor.TR_ref.tr(code=tr_id, **d)
        self.composites_references[code] = tr_obj
    # 暂时没有其他参数了
    for keys in references.keys():
      if keys not in used_keys:
        raise PPInternalError("Unknown key in references: " + keys)
    # 完成

  @staticmethod
  def lookup(name : str, requested_type : ImagePackType | None = None) -> "ImagePackDescriptor":
    if candidate := ImagePack.get_descriptor_by_id(name):
      if requested_type is None or candidate.packtype == requested_type:
        return candidate
    # 尝试按名称搜索
    # 我们支持将作者名称加在素材名称前，以'/'分隔
    authortag : str = ''
    purename : str = ''
    splitresult = name.split('/')
    if len(splitresult) == 2:
      authortag, purename = splitresult
    else:
      purename = name
    candidates = ImagePack.get_descriptor_candidates(purename)
    for d in candidates:
      if requested_type is None or d.packtype == requested_type:
        if len(authortag) == 0 or authortag in d.authortags:
          return d
    return None

  def dump_asset_info_json(self) -> dict[str, typing.Any]:
    result : dict[str, typing.Any] = {}
    if isinstance(self.topref, Translatable):
      result["name"] = self.topref.dump_candidates_json()
    result["packtype"] = self.packtype.name
    result["composites_code"] = self.composites_code
    if len(self.composites_references) > 0:
      reference_dict = {}
      for k, v in self.composites_references.items():
        reference_dict[k] = v.dump_candidates_json()
      result["composites_references"] = reference_dict
    return result

@AssetDocsDumperDecl(ImagePack)
class ImagePackDocsDumper(AssetDocsDumperBase):
  TR_docs = TranslationDomain("imagepack-docs")
  _tr_type_heading = TR_docs.tr("type_heading",
    en="Image Packs",
    zh_cn="图片包",
    zh_hk="圖片包",
  )
  @classmethod
  def get_heading_for_type(cls) -> str:
    return cls._tr_type_heading.get()

  _tr_heading_background_template = TR_docs.tr("heading_background_template",
    en="Background Template",
    zh_cn="背景模板",
    zh_hk="背景模板",
  )
  _tr_heading_background = TR_docs.tr("heading_background",
    en="Background",
    zh_cn="背景",
    zh_hk="背景",
  )

  heading_list = [
    _tr_heading_background_template,
    _tr_heading_background,
  ]

  @classmethod
  def get_heading_for_sort_order(cls, sort_order : int) -> str:
    return cls.heading_list[sort_order].get()

  def try_claim_asset(self, name : str, asset : NamedAssetClassBase) -> int:
    if not isinstance(asset, ImagePack):
      return -1
    descriptor : ImagePackDescriptor = ImagePack.get_descriptor_by_id(name)
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError()
    match descriptor.packtype:
      case ImagePackDescriptor.ImagePackType.BACKGROUND:
        return self.export_background_common(name, asset, descriptor)
      case ImagePackDescriptor.ImagePackType.CHARACTER:
        # TODO
        return -1
      case _:
        return -1

  def resize_for_docs(self, asset : ImagePack) -> ImagePack:
    if "overview_scale" in asset.opaque_metadata:
      scale = asset.opaque_metadata["overview_scale"]
      return asset.fork_and_shrink(scale)
    return asset

  @dataclasses.dataclass
  class BackgroundExportInfo:
    composites_filepaths : list[str]
    masks_filepaths : list[str]

  _backgrounds : dict[str, BackgroundExportInfo]

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._backgrounds = {}

  def export_background_common(self, name : str, asset : ImagePack, descriptor : ImagePackDescriptor) -> int:
    asset = self.resize_for_docs(asset)
    composites_filepaths = []
    masks_filepaths = []
    export_basepath = os.path.join(self.dumpinfo.base_path, self.dumpinfo.common_export_path, name)
    export_refpath = os.path.join(self.dumpinfo.base_path_ref, self.dumpinfo.common_export_path, name)
    os.makedirs(export_basepath, exist_ok=True)
    for index in range(len(asset.composites)):
      code = descriptor.composites_code[index]
      filename = code + ".png"
      actual_path = os.path.join(export_basepath, filename)
      refpath = os.path.join(export_refpath, filename)
      asset.get_composed_image(index).save_png(actual_path)
      composites_filepaths.append(refpath)
    for index in range(len(asset.masks)):
      filename = f"mask_{index}.png"
      actual_path = os.path.join(export_basepath, filename)
      refpath = os.path.join(export_refpath, filename)
      fork_args : list[Color | None] = [None] * len(asset.masks)
      fork_args[index] = Color.get((0,0,0))
      forked = asset.fork_applying_mask(args=fork_args) # type: ignore
      forked.get_composed_image(0).save_png(actual_path)
      masks_filepaths.append(refpath)
    info = self.BackgroundExportInfo(composites_filepaths, masks_filepaths)
    self._backgrounds[name] = info
    if len(masks_filepaths) > 0:
      return 0 # 背景模板
    return 1 # 背景

  _tr_mask = TR_docs.tr("mask",
    en="Mask: {name}",
    zh_cn="选区：{name}",
    zh_hk="選區：{name}",
  )

  def dump_background(self, dest : typing.TextIO, name : str, asset : ImagePack, descriptor : ImagePackDescriptor):
    info = self._backgrounds[name]
    dest.write(f"#### {str(descriptor.topref)}\n\n")
    def write_image(label : str, refpath : str):
      dest.write(f"=== \"{label}\"\n\n")
      dest.write(f"    ![{label}]({refpath})\n\n")
    for index, refpath in enumerate(info.composites_filepaths):
      code = descriptor.composites_code[index]
      label = code
      if tr := descriptor.try_get_composite_name(code):
        label = tr.get()
      write_image(label, refpath)
    for index, refpath in enumerate(info.masks_filepaths):
      masktype = descriptor.masktypes[index]
      label = self._tr_mask.format(name=masktype.trname.get())
      write_image(label, refpath)
    original_width = asset.width
    original_height = asset.height
    if "original_size" in asset.opaque_metadata:
      original_width, original_height = asset.opaque_metadata["original_size"]
    author_note = ''
    if author := asset.opaque_metadata.get("author", None):
      author_note = ImagePack.TR_imagepack_overview_author.format(name=author)
    size_note = ImagePack.TR_imagepack_overview_size_note.format(width=str(original_width), height=str(original_height))
    complexity_note = ImagePack.TR_imagepack_overview_complexity_note.format(numlayers=str(len(asset.layers)), numcomposites=str(len(asset.composites)))
    additional_notes = [author_note, size_note, complexity_note]
    dest.write("\n")
    for note in additional_notes:
      if len(note) > 0:
        dest.write("* " + note + "\n")
    dest.write("\n")
  def dump(self, dest : typing.TextIO, name : str, asset : NamedAssetClassBase, sort_order : int) -> None:
    descriptor : ImagePackDescriptor = ImagePack.get_descriptor_by_id(name)
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError()
    if not isinstance(asset, ImagePack):
      raise PPInternalError()
    match sort_order:
      case 0 | 1:
        self.dump_background(dest, name, asset, descriptor)

if __name__ == "__main__":
  # 由于这个模块会被其他模块引用，所以如果这是 __main__，其他地方再引用该模块，模块内的代码会被执行两次，导致出错
  raise RuntimeError("This module is not supposed to be executed directly. please use preppipe.pipeline_cmd with PREPPIPE_TOOL=imagepack")

