# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
import json
import typing
import zipfile
import io
import pathlib
import sys
import time

import PIL.Image
import numpy as np
import scipy as sp

from ..exceptions import *
from ..commontypes import Color
from ..language import *

class ImagePack:
  class MaskInfo:
    mask : PIL.Image.Image
    basename : str # 保存时使用的名称（不含后缀）
    mask_color : Color

    # 如果支持 projective transform，以下是四个顶点（左上，右上，左下，右下）在 mask 中的坐标
    # https://stackoverflow.com/questions/14177744/how-does-perspective-transformation-work-in-pil
    projective_vertices : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]] | None

    def __init__(self, mask : PIL.Image.Image, mask_color : Color, projective_vertices : tuple[tuple[int,int],tuple[int,int],tuple[int,int],tuple[int,int]] | None = None) -> None:
      self.mask = mask
      self.mask_color = mask_color
      self.projective_vertices = projective_vertices

  class LayerInfo:
    # 保存时每个图层的信息
    patch : PIL.Image.Image # RGBA uint8 图片
    basename : str # 保存时使用的名称（不含后缀）
    offset_x : int
    offset_y : int

    # 如果是 True 的话，该层可以不受限制地单独被选取
    unconstrained : bool

    def __init__(self, patch : PIL.Image.Image, offset_x : int = 0, offset_y : int = 0, unconstrained : bool = False, basename : str = '') -> None:
      self.patch = patch
      self.basename = basename
      self.offset_x = offset_x
      self.offset_y = offset_y
      self.unconstrained = unconstrained

  class TempLayerInfo(LayerInfo):
    # 该类仅用于在生成 ImagePack 时使用，给 patch 附带 np.ndarray 类型的值
    # 保存后读取时不会使用此类
    patch_ndarray : np.ndarray # 应该是一个有 RGBA 通道, uint8 类型的矩阵 (shape=(height, width, 4))

    def __init__(self, patch_ndarray : np.ndarray, offset_x : int = 0, offset_y : int = 0, unconstrained : bool = False) -> None:
      super().__init__(patch=PIL.Image.fromarray(patch_ndarray, 'RGBA'), offset_x=offset_x, offset_y=offset_y, unconstrained=unconstrained)
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

  # 全局值
  width : int
  height : int

  # base 的下标预留为 0
  # 在 base 之下的图层的标号为负，放在 bg_layers 中，-1 -> [0], -2 -> [1], ...
  # 在 base 之上的图层标号为正，放在 layers 中，1 -> [0], 2 -> [1], ...

  base : PIL.Image.Image | None # 如果图片内容未加载则此项为 None
  masks : list[MaskInfo]
  layers : list[LayerInfo]
  bg_layers : list[LayerInfo]
  stacks : list[list[int]]

  # 与 Translatable 对接的按名存储部分
  packname : Translatable | None # 如果语言部分未加载则此项为 None
  masknames : list[Translatable]
  stacknames : list[Translatable]

  def __init__(self, width : int, height : int) -> None:
    self.width = width
    self.height = height
    self.base = None
    self.masks = []
    self.layers = []
    self.bg_layers = []
    self.stacks = []
    self.packname = None
    self.masknames = []
    self.stacknames = []

  def import_names(self, TR : TranslationDomain, packname : str, packname_trs : dict, stack_codenames : list[str], stack_trs : list[dict], mask_codenames : list[str], mask_trs : list[dict]):
    self.packname = TR.tr(code=packname, **packname_trs)
    for codename, trdict in zip(stack_codenames, stack_trs):
      self.stacknames.append(TR.tr(code=codename, **trdict))
    for codename, trdict in zip(mask_codenames, mask_trs):
      self.masknames.append(TR.tr(code=codename, **trdict))

  @staticmethod
  def _write_image_to_zip(image : PIL.Image.Image, path : str, z : zipfile.ZipFile):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    z.writestr(path, buffer.getvalue())

  def write_zip(self, path : str):
    if self.base is None:
      raise PPInternalError("writing ImagePack zip without data")
    z = zipfile.ZipFile(path, "w", zipfile.ZIP_STORED)
    self._write_image_to_zip(self.base, "base.png", z)
    jsonout = {}
    # masks
    if len(self.masks) > 0:
      json_masks = []
      for m in self.masks:
        basename = m.basename
        if len(basename) == 0:
          basename = 'm' + str(len(json_masks))
        filename = basename + ".png"
        jsonobj : dict[str, typing.Any] = {"mask" : basename, "maskcolor" : m.mask_color.get_string()}
        if m.projective_vertices is not None:
          jsonobj["projective"] = m.projective_vertices
        json_masks.append(jsonobj)
        self._write_image_to_zip(m.mask, filename, z)
      jsonout["masks"] = json_masks
    # layers
    def collect_layer_group(prefix : str, layers : list[ImagePack.LayerInfo]):
      result = []
      for l in layers:
        basename = l.basename
        if len(basename) == 0:
          basename = prefix + str(len(result)+1)
        filename = basename + ".png"
        jsonobj : dict[str, typing.Any] = {"x":l.offset_x, "y":l.offset_y, "p": basename}
        if l.unconstrained:
          jsonobj["unconstrained"] = True
        result.append(jsonobj)
        self._write_image_to_zip(l.patch, filename, z)
      return result
    jsonout["layers"] = collect_layer_group("l", self.layers)
    if len(self.bg_layers) > 0:
      jsonout["bglayers"] = collect_layer_group("bgl", self.bg_layers)
    jsonout["stacks"] = self.stacks
    manifest = json.dumps(jsonout, ensure_ascii=False,indent=None)
    z.writestr("manifest.json", manifest)
    z.close()

  def get_composed_image(self, index : int) -> PIL.Image.Image:
    if self.base is None:
      raise PPInternalError("Cannot compose images without loading the data")
    layer_indices = self.stacks[index].copy()
    if len(layer_indices) == 0:
      raise PPInternalError("Empty composition? some thing is probably wrong")
    if layer_indices[0] != 0:
      raise PPNotImplementedError("TODO composition with background layers")

    result = self.base.copy()
    layer_indices = layer_indices[1:]

    for li in layer_indices:
      layer = self.layers[li-1]
      extended_patch = PIL.Image.new("RGBA", (self.width, self.height))
      extended_patch.paste(layer.patch, (layer.offset_x, layer.offset_y))
      result = PIL.Image.alpha_composite(result, extended_patch)
    return result

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
    result_pack.base = base_image

    layer_dict : dict[ImagePack.LayerInfo, int] = {}
    layers = result_pack.layers

    def get_layer_index(offset_x : int, offset_y : int, patch : np.ndarray):
      nonlocal layer_dict
      nonlocal layers
      l = ImagePack.TempLayerInfo(patch, offset_x, offset_y)
      index = layer_dict.get(l)
      if index is not None:
        return index
      index = len(layers)+1 # 0 是给 base 预留的
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
      printstatus("handling image " + str(len(result_pack.stacks)))
      if img.width != width:
        raise PPInternalError()
      if img.height != height:
        raise PPInternalError()

      patch_image = ImagePack.inverse_alpha_composite(base_image, img)
      printstatus("invcomp done")
      if patch_image is None:
        # 该图就是基底图
        result_pack.stacks.append([0])
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
      printstatus("merged zones")

      # Label connected components
      labeled_regions, num_labels = sp.ndimage.label(merged_nonzero_regions)
      printstatus("labeling done")

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
      result_pack.stacks.append(stack)
    return result_pack

starttime = time.time()
def printstatus(s : str):
  curtime = time.time()
  timestr = "[{:.6f}] ".format(curtime - starttime)
  print(timestr + s)


def _test_main():
  srcdir = pathlib.Path(sys.argv[1])
  image_paths = list(srcdir.glob("*.png"))
  images = [PIL.Image.open(path) for path in image_paths]

  pack = ImagePack.create_image_pack_entry(images, base_image=images[0])
  printstatus("image pack created")
  pack.write_zip("pack.zip")
  printstatus("zip written")
  index = 0
  pathlib.Path("recovered").mkdir(parents=True, exist_ok=True)
  for path, original in zip(image_paths, images):
    recovered = pack.get_composed_image(index)
    index += 1
    basename = os.path.basename(path)
    with open("recovered/" + basename, "wb") as f:
      recovered.save(f, format="PNG")
  printstatus("recovered written")


if __name__ == "__main__":
  _test_main()

