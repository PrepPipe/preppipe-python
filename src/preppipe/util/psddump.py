# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该文件用于分析 psd 文件的图层结构、显示相关信息以便后续编写图片包(ImagePack)的配置文件
# 可使用以下方式进行调用：
# python3 -m preppipe.util.psddump <psdfile> [<psdfile> ...]

import sys
import psd_tools
import psd_tools.api.layers

def _dump_psd_info(psdpath : str):
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
  if len(args) < 2:
    print("Usage: psddump.py <psdfile> [<psdfile> ...]")
    return 1
  for psdpath in args[1:]:
    _dump_psd_info(psdpath)
  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv))
