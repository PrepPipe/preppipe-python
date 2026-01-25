# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from ...vnmodel import (
  VNModel,
  VNNamespace,
  VNCharacterSymbol,
  VNSceneSymbol,
  VNAssetValueSymbol,
)


def _prune_region(symbols):
  to_remove = [s for s in symbols if isinstance(s, VNAssetValueSymbol) and s.use_empty()]
  for s in to_remove:
    s.erase_from_parent()


def prune_unused_asset_declarations(model: VNModel) -> None:
  """原地移除 model 中未被使用的资源声明（依赖 Value 的 uselist）。"""
  for ns in model.namespace:
    if not isinstance(ns, VNNamespace):
      continue
    for c in ns.characters:
      if not isinstance(c, VNCharacterSymbol):
        continue
      _prune_region(c.sprites)
      _prune_region(c.sideimages)
    for scene in ns.scenes:
      if not isinstance(scene, VNSceneSymbol):
        continue
      _prune_region(scene.backgrounds)
    _prune_region(ns.assets)
