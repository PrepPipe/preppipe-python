# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 为了使部分分析和代码生成能更方便地执行，
# 我们在这里给每个函数的基本块进行排序
# 如果能用拓扑排序就拓扑排序，有循环时则把返回边给去掉，再拓扑排序

from ...vnmodel import *
from ...pipeline import MiddleEndDecl, TransformBase

def vn_sort_function_blocks(func : VNFunction):
  # 调用者应该确保函数体非空
  # 第一趟：DFS走遍函数内部：
  #   1. 构建函数内的 CFG
  #   2. 把 CFG 内的回边去掉，使 CFG 满足 DAG 要求
  #   3. 给函数内的基本块标号
  # 第二趟：对 CFG 进行拓扑排序，当有不止一个结点满足零入度条件时，使用标号最小的结点
  incoming_edges : dict[Block, list[Block]] = {}
  block_numbering : dict[Block, int] = {}
  def add_block_outgoing_edge(fromblock : Block, toBlock : Block):
    nonlocal incoming_edges
    if toBlock in incoming_edges:
      l = incoming_edges[toBlock]
      if fromblock not in l:
        l.append(fromblock)
    else:
      incoming_edges[toBlock] = [fromblock]
  pathset : set[Block] = set()
  worklist : list[Block] = [func.get_entry_block()]
  def dfs(block : Block):
    nonlocal pathset
    nonlocal worklist
    nonlocal incoming_edges
    nonlocal block_numbering

    # 先取标号
    if block in block_numbering:
      blockindex = block_numbering[block]
    else:
      blockindex = len(block_numbering)
      block_numbering[block] = blockindex

    assert block not in pathset
    pathset.add(block)
    terminator = block.body.back
    assert isinstance(terminator, VNTerminatorInstBase)
    if isinstance(terminator, VNLocalTransferInstBase):
      # 找到所有后继块，尝试加到边集中
      for u in terminator.target_list.operanduses():
        destblock = u.value
        assert isinstance(destblock, Block)
        # 跳过返回边
        if destblock in pathset:
          continue
        add_block_outgoing_edge(block, destblock)
        dfs(destblock)
      pass
    else:
      # 该块没有后继结点
      pass
    # 完成
  dfs(func.get_entry_block())

  # 开始第二趟
  # 如果某些块没被 CFG 连着，我们把它们放在 orphan_blocks 中并放在所有有标号的块之后
  ordered_blocks : list[Block] = []
  orphan_blocks : list[Block] = []
  remaining_blocks : list[Block] = []
  candidate_list : dict[int, Block] = {}
  numblocks = 0
  for block in func.body.blocks:
    numblocks += 1
    if block in block_numbering:
      remaining_blocks.append(block)
      if block not in incoming_edges:
        candidate_list[block_numbering[block]] = block
    else:
      orphan_blocks.append(block)

  while len(candidate_list) > 0:
    indices = sorted(candidate_list.keys())
    frontindex = indices[0]
    frontblock = candidate_list[frontindex]
    ordered_blocks.append(frontblock)
    del candidate_list[frontindex]
    # 把入边信息里所有以 frontblock 为源的边去掉
    # 如果有新的块不再有入边，把它们加入候选
    new_candidates : list[Block] = []
    for b, inedges in incoming_edges.items():
      if frontblock in inedges:
        inedges.remove(frontblock)
        if len(inedges) == 0:
          new_candidates.append(b)
    for b in new_candidates:
      del incoming_edges[b]
      candidate_list[block_numbering[b]] = b

  assert len(ordered_blocks) + len(orphan_blocks) == numblocks
  ordered_blocks.extend(orphan_blocks)
  for b in ordered_blocks:
    b.remove_from_parent()
  for b in ordered_blocks:
    func.body.push_back(b)

@MiddleEndDecl('vn-blocksorting', input_decl=VNModel, output_decl=VNModel)
class VNBlockSortingPass(TransformBase):
  def run(self) -> VNModel:
    assert len(self.inputs) == 1
    m = self.inputs[0]
    assert isinstance(m, VNModel)
    for ns in m.namespace:
      for func in ns.functions:
        if func.has_body():
          vn_sort_function_blocks(func)
    return m
