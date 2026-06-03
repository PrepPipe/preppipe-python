# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from ..ast import *
from .showat_dedup import normalize_showat_for_placement_dedup

def duplicated_showat_removal(model : RenPyModel):
  def handle_block(block : Block):
    showat_locs : dict[str, str] = {} # imspec[0] -> normalized placement at
    for stmt in block.body:
      if isinstance(stmt, RenPyNode):
        if isinstance(stmt, RenPyShowNode):
          imspec_head = stmt.imspec.get_operand(0).value
          showat = None
          if stmt.atl.get_num_operands() > 0:
            showat = stmt.atl.get().get_string()
          placement_at = normalize_showat_for_placement_dedup(showat)
          if imspec_head in showat_locs:
            # 已有内容
            if placement_at is None:
              # 位置不变
              pass
            elif placement_at != showat_locs[imspec_head]:
              # 位置更新
              showat_locs[imspec_head] = placement_at
            else:
              # 放置位置与上次相同（忽略入场 ATL 差异）
              stmt.atl.drop_all_uses()
          else:
            # 新内容
            if placement_at is not None:
              showat_locs[imspec_head] = placement_at
          continue
        elif isinstance(stmt, RenPyHideNode):
          imspec_head = stmt.imspec.get_operand(0).value
          if imspec_head in showat_locs:
            showat_locs.pop(imspec_head)
          continue
        elif isinstance(stmt, RenPySceneNode):
          showat_locs.clear()
          continue
        if stmt.is_controlflow_instruction():
          showat_locs.clear()
          continue
        if stmt.has_child_block():
          for child in stmt.get_child_blocks():
            handle_block(child)

  for file in model.scripts():
    for node in file.body.body:
      if isinstance(node, MetadataOp):
        continue
      if not isinstance(node, RenPyNode):
        raise PPInternalError("Expected RenPyNode, got "+str(node))
      if not isinstance(node, RenPyLabelNode):
        continue
      handle_block(node.body)
