# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import math
import colorsys
import dataclasses
import typing
import io
import argparse
import concurrent.futures
import collections

import PIL
import PIL.Image
import PIL.ImageDraw
import xlsxwriter
import psd_tools

from ..exceptions import *
from ..commontypes import Color
from ..language import *
from ..tooldecl import ToolClassDecl
from .imagepack import *

@ToolClassDecl("imagepackrecolortester")
class ImagePackRecolorTester:
  # 用来测试 ImagePack 的选区改色功能

  @dataclasses.dataclass
  class RecolorTestResult:
    # 用来表示改色测试的结果。所有的图片都还没有缩放，导出时可能需要根据后端的要求进行缩放
    # 如果有 M 个基础图片，N 个目标颜色，那么这里的内容应该可以生成一个 （M+1)行、(N+2）列的表格，表格前两列时颜色和基础图片，后面的列是改色后的图片
    base_colors : list[Color] # 行标题，基础颜色（第一列）
    dest_colors : list[Color] # 列标题，目标颜色（第一行）
    base_images : list[PIL.Image.Image] # 第二列，未改色的基础图像
    dest_images : list[list[PIL.Image.Image]] # 第三列开始，改色后的图像 [base_index][color_index]

  @staticmethod
  def imagegen_colorbars(
    size: tuple[int,int],
    main_color: Color,
    bar_colors: list[Color],
    sat_variation: float = 0.0,  # amplitude of saturation variation
    value_variation: float = 0.1,  # amplitude of value variation
    period: float = 10.0         # period of variation
  ) -> list[PIL.Image.Image]:

    # -------------------------------------------------------------------------
    # 1) Convert main_color to HSV so we can vary saturation/value programmatically
    # -------------------------------------------------------------------------
    r0, g0, b0 = main_color.to_tuple_rgb()
    # Scale [0..255] to [0..1] for colorsys
    h0, s0, v0 = colorsys.rgb_to_hsv(r0 / 255.0, g0 / 255.0, b0 / 255.0)

    width, height = size

    # Parameters
    # We'll make the horizontal bar quite tall so it's visible
    horizontal_thickness = int(height * 2 / 3)

    # Parameters for the vertical bars (“teeth”)
    bar_width = max(4, width // (3*len(bar_colors)))  # or some proportion
    bar_height = height

    # -------------------------------------------------------------------------
    # 2) Helper function to create a vertical bar with alpha gradient
    # -------------------------------------------------------------------------
    def create_vertical_bar(color: Color,
                            bar_width: int,
                            bar_height: int) -> PIL.Image.Image:
      """
      Creates a small RGBA image (bar_width x bar_height) of a vertical bar
      whose alpha goes from 255 at the top to 0 at the bottom.
      """
      # Create an RGBA image for the bar
      bar_img = PIL.Image.new("RGBA", (bar_width, bar_height), (0,0,0,0)) # type: ignore
      # Create a mask (L mode) for the alpha gradient
      alpha_mask = PIL.Image.new("L", (bar_width, bar_height), 0)

      for y in range(bar_height):
        # fraction of the way down the bar
        frac = y / float(bar_height - 1) if bar_height > 1 else 1
        # alpha decreases towards bottom
        alpha_val = int(255 * (1 - frac))
        alpha_mask.paste(alpha_val, (0, y, bar_width, y+1))
        #for x in range(bar_width):
        #  alpha_mask.putpixel((x, y), alpha_val)

      # Paste the solid color into bar_img using alpha_mask
      r, g, b = color.to_tuple_rgb()
      solid_color = (r, g, b, 255)  # full opacity
      bar_img.paste(solid_color, (0, 0), mask=alpha_mask)

      return bar_img

    # -------------------------------------------------------------------------
    # 3) Create a base image (fully transparent), plus a separate bar image
    # -------------------------------------------------------------------------
    base = PIL.Image.new("RGBA", size, (0,0,0,0)) # type: ignore
    # draw_base = PIL.ImageDraw.Draw(base)

    # We'll create a separate image for the horizontal bar so we can do
    # pixel-by-pixel coloring (with varying saturation/value).
    bar_img = PIL.Image.new("RGBA", (width, horizontal_thickness), (0,0,0,0)) # type: ignore
    # Draw object for coloring the bar_img
    bar_draw = PIL.ImageDraw.Draw(bar_img)


    # We'll do a *diagonal* fraction from (0,0) -> (width-1, horizontal_thickness-1).
    denom = (width - 1) + (horizontal_thickness - 1)
    denom = denom if denom > 0 else 1  # avoid zero division

    for sum_xy in range(horizontal_thickness + width):
      frac = sum_xy / float(denom)
      angle = 2.0 * math.pi * period * frac

      s_new = s0 + sat_variation * math.sin(angle)
      v_new = v0 + value_variation * math.cos(angle)
      s_new = max(0.0, min(1.0, s_new))
      v_new = max(0.0, min(1.0, v_new))

      r_var, g_var, b_var = colorsys.hsv_to_rgb(h0, s_new, v_new)
      r_c = int(r_var * 255)
      g_c = int(g_var * 255)
      b_c = int(b_var * 255)
      bar_draw.line([(0, sum_xy), (sum_xy, 0)], fill=(r_c, g_c, b_c, 255))

    # 3b) Now we want a rounded-rectangle mask to shape bar_img.
    #     We'll create a mask and then combine it with bar_img.
    corner_radius = horizontal_thickness // 2
    mask = PIL.Image.new("L", (width, horizontal_thickness), 0)
    mask_draw = PIL.ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
      [0, 0, width, horizontal_thickness],
      radius=corner_radius,
      fill=255
    )
    # "Cut out" the corners in bar_img using the mask
    # (we do alpha_composite or putalpha; here we'll simply use the mask as alpha)
    rounded_bar = PIL.Image.new("RGBA", (width, horizontal_thickness), (0,0,0,0)) # type: ignore
    rounded_bar.paste(bar_img, (0,0), mask=mask)

    # 3c) Finally, paste the rounded_bar onto the base image at the correct Y
    horizontal_y1 = height - horizontal_thickness
    base.alpha_composite(rounded_bar, (0, horizontal_y1))

    # -------------------------------------------------------------------------
    # 4) Draw the vertical bars (“teeth”)
    # -------------------------------------------------------------------------
    images = [base]  # the first image in the stack is the base
    center_x = width // 2

    # We'll place them so their bottom overlaps with the bar's top edge
    base_offset_y = max(0, horizontal_y1 - (bar_height // 2))

    # Horizontal offset step between bars
    step_x = bar_width + 6

    for i, color in enumerate(bar_colors):
      # We'll place one bar on the "left" side (base) and
      # one bar on the "right" side (overlay). We offset them so
      # they're spaced nicely across the horizontal bar.

      # Example formula to spread them out from left to right:
      x_left  = center_x + (1 - len(bar_colors) + 2*i)   * step_x - (bar_width // 2)
      x_right = center_x + (1 - len(bar_colors) + 2*i+1) * step_x - (bar_width // 2)

      # Create the vertical bar tile
      bar_img_v = create_vertical_bar(color, bar_width, bar_height)

      # 1) Paste left bar onto the base
      base.alpha_composite(bar_img_v, (x_left, base_offset_y))

      # 2) Create an overlay image with the right bar
      overlay = PIL.Image.new("RGBA", size, (0,0,0,0)) # type: ignore
      overlay.alpha_composite(bar_img_v, (x_right, base_offset_y))

      images.append(overlay)

    return images

  @staticmethod
  def get_test_imagepack_from_layers(layers: list[PIL.Image.Image], mask_index : int, mask_color : Color) -> ImagePack:
    # 当我们生成用于测试的 ImagePack 时，layers 里只有 mask_index 指向的图层会生成一个基底图层和相同的选区图层，其他都作为额外的正常图层
    if mask_index < 0 or mask_index >= len(layers):
      raise ValueError("Invalid mask index")
    result = ImagePack(layers[0].width, layers[0].height)
    composite_layers = []
    for index, layer in enumerate(layers):
      composite_layers.append(index)
      is_mask = (index == mask_index)
      newlayer = ImagePack.LayerInfo(patch=ImageWrapper(image=layer), width=layer.width, height=layer.height, base=is_mask)
      result.layers.append(newlayer)
      if is_mask:
        mask = ImagePack.MaskInfo(mask=None, mask_color=mask_color, width=layer.width, height=layer.height, applyon=[mask_index])
        result.masks.append(mask)
    composite = ImagePack.CompositeInfo(layers=composite_layers)
    result.composites.append(composite)
    return result

  @staticmethod
  def test_recolor(pack : ImagePack, destcolors : list[Color], enable_parallelization : bool = True) -> list[PIL.Image.Image]:
    result = []
    if not enable_parallelization:
      for color in destcolors:
        forked = pack.fork_applying_mask([color], enable_parallelization=False)
        img = forked.get_composed_image(0).get()
        result.append(img)
    else:
      def _get_composed_image(pack, color):
        forked = pack.fork_applying_mask([color], enable_parallelization=False)
        return forked.get_composed_image(0).get()
      with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = []
        for color in destcolors:
          futures.append(executor.submit(_get_composed_image, pack, color))
        for future in futures:
          result.append(future.result())
    return result

  @staticmethod
  def prepare_imagepack_colorbar(*, size : tuple[int,int] | None = None, main_color: Color | None = None, bar_colors: list[Color] | None = None) -> ImagePack:
    if size is None:
      size = (600, 200)
    if main_color is None:
      main_color = Color.get((187, 187, 221))
    if bar_colors is None:
      bar_colors = [
        Color.get((255, 0, 0)),
        Color.get((0, 255, 0)),
        Color.get((0, 0, 255)),
        Color.get((255, 255, 0)),
        Color.get((0, 255, 255)),
        Color.get((255, 0, 255)),
        Color.get((255, 255, 255)),
        Color.get((0, 0, 0))
      ]
    return ImagePackRecolorTester.get_test_imagepack_from_layers(ImagePackRecolorTester.imagegen_colorbars(size, main_color, bar_colors), 0, main_color)

  @staticmethod
  def create_report(imgpacks : list[ImagePack], destcolors : list[Color]) -> RecolorTestResult:
    base_colors = [pack.masks[0].mask_color for pack in imgpacks]
    base_images = [pack.get_composed_image(0).get() for pack in imgpacks]
    dest_images = [ImagePackRecolorTester.test_recolor(pack, destcolors) for pack in imgpacks]
    return ImagePackRecolorTester.RecolorTestResult(
      base_colors=base_colors,
      dest_colors=destcolors,
      base_images=base_images,
      dest_images=dest_images
    )

  @staticmethod
  def export_xlsx(result : "ImagePackRecolorTester.RecolorTestResult", path : str):
    def is_deep_color(color_rgb: tuple[int,int,int]) -> bool:
      return sum(color_rgb) < 384
    max_image_width = 0
    max_image_height = 0
    def _insert_image(worksheet, row, col, pil_image, workbook):
      # Convert Pillow image to a PNG in-memory
      # Scale if needed
      nonlocal max_image_width
      nonlocal max_image_height
      width, height = pil_image.size
      max_width = 600
      img_buffer = io.BytesIO()
      ratio = 1.0
      if width > max_width:
        ratio = max_width / float(width)
        new_height = int(height * ratio)
        pil_image = pil_image.resize((max_width, new_height), PIL.Image.Resampling.LANCZOS)
        max_image_width = max_width
        max_image_height = max(max_image_height, new_height)
      else:
        max_image_width = max(max_image_width, width)
        max_image_height = max(max_image_height, height)
      pil_image.save(img_buffer, format="PNG")
      img_buffer.seek(0)

      # Insert with x_scale, y_scale
      # xlsxwriter's insert_image supports an option dict with 'image_data' for the bytes
      worksheet.insert_image(
        row, col,
        "",  # filename not needed if we pass image_data
        {
          "image_data": img_buffer,
          #"x_scale": ratio,
          #"y_scale": ratio,
          # optionally: "positioning": 1 to move/size with cells, etc.
        }
      )
    # 正式开始
    if parentdir := os.path.dirname(path):
      os.makedirs(parentdir, exist_ok=True)
    workbook = xlsxwriter.Workbook(path)
    worksheet = workbook.add_worksheet("Recolor Results")

    # Freeze the first row and the first two columns
    worksheet.freeze_panes(1, 2)

    # 2) Write the dest_colors in the first row, from col=2 onward
    for j, dest_color in enumerate(result.dest_colors):
      col = j + 2
      color_rgb = dest_color.to_tuple_rgb()
      hex_color = "#{:02X}{:02X}{:02X}".format(*color_rgb)
      # Decide font color
      font_color = "#FFFFFF" if is_deep_color(color_rgb) else "#000000"
      # Create a format for the cell
      cell_format = workbook.add_format({
        "bg_color": hex_color,
        "font_color": font_color,
        "align": "center",
        "valign": "vcenter",
        "bold": True,
        # optionally: "border": 1, etc.
      })
      # Write text
      worksheet.write(0, col, str(dest_color), cell_format)

    # 3) For each base row, write the base color in col=0 and the base image in col=1
    for i, base_color in enumerate(result.base_colors):
      row = i + 1
      color_rgb = base_color.to_tuple_rgb()
      hex_color = "#{:02X}{:02X}{:02X}".format(*color_rgb)
      font_color = "#FFFFFF" if is_deep_color(color_rgb) else "#000000"
      color_format = workbook.add_format({
        "bg_color": hex_color,
        "font_color": font_color,
        "align": "center",
        "valign": "vcenter"
      })

      # Write the base color text in (row, 0)
      worksheet.write(row, 0, str(base_color), color_format)

      # Insert the base image in (row, 1)
      if i < len(result.base_images):
        base_img = result.base_images[i]
        _insert_image(worksheet, row, 1, base_img, workbook)

      # 4) Recolored images in columns 2..(2 + len(dest_colors)-1)
      if i < len(result.dest_images):
        recolor_row_imgs = result.dest_images[i]  # list of images for this row
        for j, rec_img in enumerate(recolor_row_imgs):
          col = j + 2
          _insert_image(worksheet, row, col, rec_img, workbook)

    worksheet.set_column(0, 0, 20)  # base color column
    worksheet.set_column(1, 1+len(result.dest_colors), max_image_width / 7)  # image columns
    worksheet.set_default_row(max_image_height)  # image rows
    worksheet.set_row(0, 20)  # header row

    # 5) Close the workbook
    workbook.close()

  @staticmethod
  def scan_colors(use_narrow_range : bool = False) -> typing.Generator[Color, None, None]:
    # use_narrow_range==True 时不改 s 和 v
    for value in range(100, 10, -30):
      v = value / 100.0
      for hue in range(0, 360, 30):
        h = hue / 360.0
        for sat in range(100, 10, -30):
          s = sat / 100.0
          r, g, b = colorsys.hsv_to_rgb(h, s, v)
          color = Color.get((int(r*255), int(g*255), int(b*255)))
          yield color
          if use_narrow_range:
            break
      if use_narrow_range:
        break

  @staticmethod
  def get_images_from_psd(path : str) -> collections.OrderedDict[str, PIL.Image.Image]:
    psd = psd_tools.PSDImage.open(path)
    results = collections.OrderedDict()
    for layer in psd:
      results[layer.name] = layer.composite()
    return results

  @staticmethod
  def get_basecolor_from_image(image : PIL.Image.Image) -> Color:
    # https://stackoverflow.com/questions/3241929/how-to-find-the-dominant-most-common-color-in-an-image
    # 首先，如果图片太大，就先缩小
    smallimage = image.crop(image.getbbox())
    if smallimage.width > 256 or smallimage.height > 256:
      scale = 256 / max(smallimage.width, smallimage.height)
      smallimage = smallimage.resize((int(smallimage.width * scale), int(smallimage.height * scale)), PIL.Image.Resampling.LANCZOS)
    paletted = smallimage.convert('P', palette=PIL.Image.ADAPTIVE, colors=4)
    palette = paletted.getpalette()
    if palette is None:
      raise ValueError("Cannot get palette from image")
    color_counts = sorted(paletted.getcolors(), reverse=True)
    for i in range(4):
      palette_index = color_counts[i][1]
      if not isinstance(palette_index, int):
        raise ValueError("Invalid palette index")
      dominant_color = palette[palette_index*3:palette_index*3+3]
      if dominant_color[0] == 0 and dominant_color[1] == 0 and dominant_color[2] == 0:
        continue
      return Color.get(tuple(dominant_color))

  @staticmethod
  def tool_main(args : list[str] | None = None):
    parser = argparse.ArgumentParser(description="ImagePack Recoloring Tester")
    parser.add_argument("--psd", type=str, help="PSD file to load")
    parser.add_argument("--loaddir", type=str, help="Directory to load images")
    parser.add_argument("--srcscale", type=float, default=1.0, help="Scale factor for source images")
    parser.add_argument("--mask", type=str, nargs="+", help="Layer names to use as masks")
    parser.add_argument("--minimal", action="store_true", help="Use narrow color range")
    parser.add_argument("--xlsx-export", type=str, help="Output XLSX file")
    if args is None:
      args = sys.argv[1:]
    parsed_args = parser.parse_args(args)
    if parsed_args.xlsx_export is None:
      raise ValueError("No output file specified")
    dest_colors = [color for color in ImagePackRecolorTester.scan_colors(use_narrow_range=parsed_args.minimal)]

    baselayernames = []
    basecolors = {}
    if parsed_args.mask is not None:
      mask_exprs : list[str] = [] # <layername>[=<color>]
      for s in parsed_args.mask:
        mask_exprs.extend(s.split(","))
      for expr in mask_exprs:
        parts = expr.split("=")
        name = parts[0]
        baselayernames.append(name)
        if len(parts) > 1:
          basecolors[name] = Color.get(parts[1])

    imagepacks = []
    if parsed_args.psd or parsed_args.loaddir:
      if len(baselayernames) == 0:
        raise ValueError("No mask layers specified")
      images : collections.OrderedDict[str, PIL.Image.Image] = collections.OrderedDict()
      if parsed_args.psd:
        images = ImagePackRecolorTester.get_images_from_psd(parsed_args.psd)
      elif parsed_args.loaddir:
        for root, _, files in os.walk(parsed_args.loaddir):
          for file in sorted(files):
            if not file.lower().endswith(".png"):
              continue
            basename = os.path.splitext(file)[0]
            images[basename] = PIL.Image.open(os.path.join(root, file))
      else:
        raise RuntimeError()
      mask_info = []
      imagelist = []
      imagenames = []
      for name, img in images.items():
        if parsed_args.srcscale != 1.0:
          img = img.resize((int(img.width * parsed_args.srcscale), int(img.height * parsed_args.srcscale)), PIL.Image.Resampling.LANCZOS)
        imagelist.append(img)
        imagenames.append(name)
      for name in baselayernames:
        if name not in images:
          raise ValueError("Cannot find layer " + name)
        cur_image = images[name]
        cur_base_color = None
        if name in basecolors:
          cur_base_color = basecolors[name]
        if cur_base_color is None:
          cur_base_color = ImagePackRecolorTester.get_basecolor_from_image(cur_image)
        mask_info.append((imagenames.index(name), cur_base_color))
      for info in mask_info:
        pack = ImagePackRecolorTester.get_test_imagepack_from_layers(imagelist, info[0], info[1])
        imagepacks.append(pack)
    else:
      size = (600, 200)
      for color in dest_colors:
        pack = ImagePackRecolorTester.prepare_imagepack_colorbar(size=size, main_color=color)
        imagepacks.append(pack)
    if len(imagepacks) == 0:
      raise ValueError("No imagepack created")
    result = ImagePackRecolorTester.create_report(imagepacks, dest_colors)
    if xlsx := parsed_args.xlsx_export:
      ImagePackRecolorTester.export_xlsx(result, xlsx)

if __name__ == "__main__":
  raise RuntimeError("This module is not supposed to be executed directly. please use preppipe.pipeline_cmd with PREPPIPE_TOOL=" + getattr(ImagePackRecolorTester, "TOOL_NAME"))
