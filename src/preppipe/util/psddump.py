# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该文件用于分析 psd 文件的图层结构、显示相关信息以便后续编写图片包(ImagePack)的配置文件
# 可使用以下方式进行调用：
#   python3 -m preppipe.util.psddump <psdfile> [<psdfile> ...]
#   python3 -m preppipe.util.psddump --layer-modes-only [--include-hidden] <psdfile>  # 仅输出非常规混合模式的图层

import argparse
import sys
import psd_tools
import psd_tools.api.layers
from typing import Any


def _export_layer_modes_only(psdpath : str, skip_hidden : bool = True) -> None:
  """只输出非常规混合模式（非 normal/pass_through）的图层列表，使用 L1-、L2- 风格命名。"""
  psd = psd_tools.PSDImage.open(psdpath)
  layer_data : list[dict[str, Any]] = []
  layer_index = 0

  def visit(stack : list[str], layer : psd_tools.api.layers.Layer) -> None:
    nonlocal layer_index
    if skip_hidden and not layer.visible:
      return
    layer_name = layer.name
    if not isinstance(layer, psd_tools.api.layers.Group):
      layer_index += 1
      layer_name = f"L{layer_index}-{layer.name}"
    layer_data.append({
      "name": layer_name,
      "blend_mode": layer.blend_mode.name.lower(),
    })
    if isinstance(layer, psd_tools.api.layers.Group) and len(layer) > 0:
      stack.append(layer.name)
      for child in layer:
        visit(stack, child)
      stack.pop()

  layer_stack : list[str] = []
  for layer in psd:
    visit(layer_stack, layer)

  print(f"图层模式：")
  for layer in layer_data:
    if layer["blend_mode"] not in ("normal", "pass_through"):
      print(f"  {layer['name']}：{layer['blend_mode']}")


def _dump_psd_info(psdpath : str) -> None:
  psd = psd_tools.PSDImage.open(psdpath)
  print(f"{psdpath}: {psd.width}x{psd.height}")
  def visit(stack : list[str], layer : psd_tools.api.layers.Layer) -> None:
    fullname = '/'.join(stack + [layer.name])
    size_info = f"{layer.width}x{layer.height} @ ({layer.left},{layer.top})"
    layer_kind : str = "U"
    additional_info = []
    is_expected_blendmode = False
    if isinstance(layer, psd_tools.api.layers.Group):
      layer_kind = "G"
      is_expected_blendmode = layer.blend_mode == psd_tools.api.layers.BlendMode.PASS_THROUGH
    elif isinstance(layer, psd_tools.api.layers.PixelLayer):
      layer_kind = "P"
      is_expected_blendmode = layer.blend_mode == psd_tools.api.layers.BlendMode.NORMAL
    elif isinstance(layer, psd_tools.api.layers.ShapeLayer):
      layer_kind = "S"
    prefix = f"[{layer_kind}]" + ("   " if layer.visible else "[H]")
    if not is_expected_blendmode:
      additional_info.append(f"BlendMode={layer.blend_mode.name}")
    if layer.clipping:
      additional_info.append("Clipping")
    print(f"{prefix} \"{fullname}\": {size_info} " + ", ".join(additional_info))
    if isinstance(layer, psd_tools.api.layers.Group) and len(layer) > 0:
      stack.append(layer.name)
      for child in layer:
        visit(stack, child)
      stack.pop()
  layer_stack : list[str] = []
  for layer in psd:
    visit(layer_stack, layer)

def main(args : list[str]) -> int:
  parser = argparse.ArgumentParser(
    description="分析 PSD 图层结构，或仅输出非常规混合模式的图层列表。",
    epilog="示例: python -m preppipe.util.psddump --layer-modes-only a.psd",
  )
  parser.add_argument("psdfiles", nargs="+", metavar="psdfile", help="PSD 文件路径")
  parser.add_argument(
    "--layer-modes-only",
    action="store_true",
    help="仅输出非常规混合模式（如 multiply）的图层，使用 L1-、L2- 命名",
  )
  parser.add_argument(
    "--include-hidden",
    action="store_true",
    help="包含隐藏图层（仅与 --layer-modes-only 配合时生效）",
  )
  parsed = parser.parse_args(args[1:])

  if parsed.layer_modes_only:
    for psdpath in parsed.psdfiles:
      _export_layer_modes_only(psdpath, skip_hidden=not parsed.include_hidden)
  else:
    for psdpath in parsed.psdfiles:
      _dump_psd_info(psdpath)
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv))
