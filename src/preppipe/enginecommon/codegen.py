# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
from .ast import *
from ..irbase import *
from ..vnmodel import *

SelfType = typing.TypeVar('SelfType', bound='BackendCodeGenHelperBase') # pylint: disable=invalid-name
NodeType = typing.TypeVar('NodeType', bound=BackendASTNodeBase) # pylint: disable=invalid-name
class BackendCodeGenHelperBase(typing.Generic[NodeType]):
  # 这里我们提供标准的从 Block 末尾往前生成代码的接口
  # 我们使用 CODEGEN_MATCH_TREE 来组织代码生成的逻辑
  # 我们从每个 Block 的末尾开始，根据开始、结束时间将指令顺序化，并用 CODEGEN_MATCH_TREE 来生成代码
  CODEGEN_MATCH_TREE : typing.ClassVar[dict] = {}

  @classmethod
  def is_matchtree_installed(cls) -> bool:
    return len(cls.CODEGEN_MATCH_TREE) > 0

  @classmethod
  def install_codegen_matchtree(cls, matchtree: dict):
    # 每一个键都应该是 VNInstruction 的子类，每一个值要么是一个 dict 且键有 None，要么是一个函数
    # 函数应该是像 gen_XXX(self, instrs: list[VNInstruction], insert_before: NodeType) -> NodeType 这样
    # 返回值是下一个插入位置
    cls.CODEGEN_MATCH_TREE = matchtree
    def checktreerecursive(tree : dict, istop : bool):
      for k, v in tree.items():
        if k is not None:
          if not issubclass(k, VNInstruction):
            raise ValueError(f"Key {k} is not a subclass of VNInstruction")
        if isinstance(v, dict):
          if None not in v:
            raise ValueError(f"Value {v} is not a dict with None key")
          checktreerecursive(v, False)
        elif callable(v):
          pass
        else:
          raise ValueError(f"Unexpected value type {v}")
      if istop:
        return

  @classmethod
  def match_codegen_depth1(cls, ty : type) -> typing.Callable:
    match_result = cls.CODEGEN_MATCH_TREE[ty]
    if isinstance(match_result, dict):
      match_result = match_result[None]
    return match_result

  @classmethod
  def is_waitlike_instr(cls, instr : VNInstruction) -> bool:
    if isinstance(instr, VNWaitInstruction):
      return True
    return False

  def gen_terminator(self, terminator : VNTerminatorInstBase, **kwargs) -> NodeType:
    raise NotImplementedError()

  def codegen_block(self, b : Block, **kwargs):
    terminator = b.body.back
    assert isinstance(terminator, VNTerminatorInstBase)
    cur_insertpos = self.gen_terminator(terminator, **kwargs)
    if terminator is b.body.front:
      # 这个块里除了终结指令之外没有其他指令
      return
    cur_srcpos = terminator
    block_start = b.get_argument('start')
    visited_instrs = set()

    while True:
      # 从最后的指令开始往前
      if cur_srcpos is b.body.front:
        return
      cur_srcpos = cur_srcpos.get_prev_node()
      if isinstance(cur_srcpos, VNInstruction):
        if cur_srcpos in visited_instrs:
          continue
        instrs, gen = self.match_instr_patterns(cur_srcpos.get_finish_time(), block_start)
        cur_insertpos = gen(self, instrs, cur_insertpos)
        visited_instrs.update(instrs)
      else:
        if isinstance(cur_srcpos, MetadataOp):
          # 直接把它们复制过去
          cloned = cur_srcpos.clone()
          cloned.insert_before(cur_insertpos)
          cur_insertpos = cloned
        else:
          raise RuntimeError('Unexpected instruction kind: ' + type(cur_srcpos).__name__)

  def match_instr_patterns(self, finishtime : OpResult, blocktime : Value) -> tuple[list[VNInstruction], typing.Callable]:
    assert isinstance(finishtime, OpResult) and isinstance(finishtime.valuetype, VNTimeOrderType)
    cur_match_dict = self.CODEGEN_MATCH_TREE
    instrs = []
    while True:
      end_instr : VNInstruction = finishtime.parent
      assert isinstance(end_instr, VNInstruction)
      instrs.append(end_instr)
      match_type = type(end_instr)
      if match_type not in cur_match_dict:
        if None not in cur_match_dict:
          raise RuntimeError('Codegen for instr type not supported yet: ' + match_type.__name__)
        match_result = cur_match_dict[None]
      else:
        match_result = cur_match_dict[match_type]
      if isinstance(match_result, dict):
        cur_match_dict = match_result
        finishtime = end_instr.get_start_time()
        # 遇到以下三种情况时我们停止匹配：
        # 1. 已经到块的开头
        # 2. 前一个指令是上一步的类似等待的指令
        # 3. 除了当前匹配到的指令外，前一个指令的输出时间有其他使用者（我们不能把这个输出时间抢走）
        if finishtime is blocktime or self.is_waitlike_instr(finishtime.parent):
          return (instrs, match_result[None])
        for u in finishtime.uses:
          user_instr : VNInstruction = u.user.parent # type: ignore
          if user_instr is not end_instr and user_instr.try_get_parent_group() is not end_instr:
            # 情况三
            return (instrs, match_result[None])
        # 否则我们继续匹配
        continue
      return (instrs, match_result)
