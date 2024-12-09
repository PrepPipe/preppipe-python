# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from ..ast import *

def duplicated_showat_removal(model : RenPyModel):
  def handle_block(block : Block):
    showat_locs : dict[str, str] = {} # imspec[0] -> showat string
    for stmt in block.body:
      if isinstance(stmt, RenPyNode):
        if isinstance(stmt, RenPyShowNode):
          imspec_head = stmt.imspec.get_operand(0).value
          showat = None
          if stmt.atl.get_num_operands() > 0:
            showat = stmt.atl.get().get_string()
          if imspec_head in showat_locs:
            # 已有内容
            if showat is None:
              # 位置不变
              pass
            elif showat != showat_locs[imspec_head]:
              # 位置更新
              showat_locs[imspec_head] = showat
            else:
              # 位置重复
              stmt.atl.drop_all_uses()
          else:
            # 新内容
            if showat is not None:
              showat_locs[imspec_head] = showat
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
