# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
import typing

from preppipe.util.graphtrait import GenericNodeBase
from preppipe.vnmodel import VNFunction
from ..util import graphtrait
from ..vnmodel import *
from ..pipeline import BackendDecl, IODecl, TransformBase

# Inter-procedural Control-Flow Graph (ICFG)
# 虽然 ICFG 应该是抽象的、可服务于除 VNModel 之外其他带简单控制流信息的 IR 的图，
# 由于目前只有 VNModel 一个合适的IR，目前还是把 ICFG 与 VNModel 绑死
# 等以后有其他可适配的 IR 之后再做解耦
class ICFGNode(graphtrait.GenericNodeBase):
  # 所有 ICFG 结点的基类
  nodeindex : int

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self.nodeindex = 0

  def add_to_graph(self, graph : ICFG):
    self.nodeindex = graph.add_node(self)

  def get_function_context(self) -> VNFunction | None:
    return None

  def get_short_target_name(self) -> str:
    return ''

  def get_node_label(self) -> str:
    result = '#' + str(self.nodeindex) + ' '
    if func := self.get_function_context():
      result += '[' + func.name + '] '
    result += type(self).__name__
    short_target_name = self.get_short_target_name()
    if len(short_target_name) > 0:
      result += ' "' + short_target_name + '"'
    return result

class ICFGEdge(graphtrait.GenericEdgeBase):
  def __init__(self, fromnode : ICFGNode, tonode : ICFGNode) -> None:
    super().__init__()
    self.set_source_node(fromnode)
    self.set_dest_node(tonode)

  def get_edge_label(self) -> str:
    return ''

class GlobalICFGNode(ICFGNode):
  # 全局入口，每一个入口点会有一个该结点
  # 用户指定的入口函数可以由这个结点抵达
  entrypoint : str # 入口名称

  def __init__(self, entrypoint : str, **kwargs) -> None:
    super().__init__(**kwargs)
    self.entrypoint = entrypoint

  def add_to_graph(self, graph: ICFG):
    assert self.entrypoint not in graph.start_nodes
    graph.start_nodes[self.entrypoint] = self
    return super().add_to_graph(graph)

  def get_short_target_name(self) -> str:
    return self.entrypoint

class IntraICFGNode(ICFGNode):
  # 代表函数内的结点，一般是基本块或是指令
  block : Block

  def __init__(self, block : Block, **kwargs) -> None:
    super().__init__(**kwargs)
    self.block = block

  def add_to_graph(self, graph: ICFG):
    assert self.block not in graph.block_map
    graph.block_map[self.block] = self
    return super().add_to_graph(graph)

  def get_function_context(self) -> VNFunction:
    return self.block.parent.parent

  def get_short_target_name(self) -> str:
    return self.block.name

class InterICFGNode(ICFGNode):
  # 代表函数间跳转的结点
  pass

# 如果函数A结束时可能不返回：
# 1. 如果是直接跳转到另一个函数B (TailCall(B)): Call(A) --> FunEntry(A) --> FunExit(A) --> FunEntry(B) --> ... --> Ret(A)
# 2. 如果是直接进入结局(Ending): Call(A) --> FunEntry(A) --> FunExit(A) --> Ending (不会再到 Ret(A))

# 函数实际出入口
# 入口是一个 FunEntry，出口是一个 FunExit
# 为了表达不同的出入口效果，函数可能会有多个 FunExit 分别对应出口状态
class FunEntryICFGNode(InterICFGNode):
  func : VNFunction

  def __init__(self, func : VNFunction, **kwargs) -> None:
    super().__init__(**kwargs)
    self.func = func

  def add_to_graph(self, graph: ICFG):
    assert self.func not in graph.entry_map
    graph.entry_map[self.func] = self
    return super().add_to_graph(graph)

  def get_function_context(self) -> VNFunction:
    return self.func

class FunExitICFGNode(InterICFGNode):
  exitinst : VNExitInstBase

  def __init__(self, exitinst : VNExitInstBase, **kwargs) -> None:
    super().__init__(**kwargs)
    self.exitinst = exitinst

  def add_to_graph(self, graph: ICFG):
    assert self.exitinst not in graph.exit_map
    graph.exit_map[self.exitinst] = self
    return super().add_to_graph(graph)

  def get_function_context(self) -> VNFunction:
    return self.exitinst.parent_op

  def get_short_target_name(self) -> str:
    return self.exitinst.name

class EndingICFGNode(InterICFGNode):
  ending : VNEndingInst

  def __init__(self, ending : VNEndingInst, **kwargs) -> None:
    super().__init__(**kwargs)
    self.ending = ending

  def add_to_graph(self, graph: ICFG):
    assert self.ending not in graph.ending_map
    graph.ending_map[self.ending] = self
    return super().add_to_graph(graph)

  def get_function_context(self) -> VNFunction:
    return self.ending.parent_op

  def get_short_target_name(self) -> str:
    return self.ending.ending.get().get_string()

# 每一次函数调用都会有一个 Call 表示调用前的状态，和一个 Ret 表示返回后的状态
# 如果调用后不返回，Ret 可能不会有边指向它
# 一般而言，一次从函数A到函数B的调用应该有 (A)Call --> (B)FunEntry --> ... --> (B)FunExit --> (A)Ret， 括号内的字母表示结点的归属（函数A还是B）
class CallICFGNode(InterICFGNode):
  call : VNCallInst

  def __init__(self, call : VNCallInst, **kwargs) -> None:
    super().__init__(**kwargs)
    self.call = call

  def add_to_graph(self, graph: ICFG):
    assert self.call not in graph.callout_map
    graph.callout_map[self.call] = self
    return super().add_to_graph(graph)

  def get_function_context(self) -> VNFunction:
    return self.call.parent_op

  def get_short_target_name(self) -> str:
    return self.call.name

class RetICFGNode(InterICFGNode):
  call : VNCallInst

  def __init__(self, call : VNCallInst, **kwargs) -> None:
    super().__init__(**kwargs)
    self.call = call

  def add_to_graph(self, graph: ICFG):
    assert self.call not in graph.callret_map
    graph.callret_map[self.call] = self
    return super().add_to_graph(graph)

  def get_function_context(self) -> VNFunction:
    return self.call.parent_op

  def get_short_target_name(self) -> str:
    return self.call.name

class ICFG(graphtrait.GenericGraphBase):
  start_nodes : dict[str, GlobalICFGNode]
  block_map : dict[Block, IntraICFGNode]
  entry_map : dict[VNFunction, FunEntryICFGNode]
  exit_map : dict[VNExitInstBase, FunExitICFGNode]
  ending_map : dict[VNEndingInst, EndingICFGNode]
  callout_map : dict[VNCallInst, CallICFGNode]
  callret_map : dict[VNCallInst, RetICFGNode]
  sequence_number : int

  def __init__(self) -> None:
    super().__init__()
    self.start_nodes = {}
    self.block_map = {}
    self.entry_map = {}
    self.exit_map = {}
    self.ending_map = {}
    self.callout_map = {}
    self.callret_map = {}
    self.sequence_number = 0

  def add_node(self, node: ICFGNode) -> int:
    super().add_node(node)
    self.sequence_number += 1
    return self.sequence_number

  def get_entry_nodes(self) -> typing.Iterable[GlobalICFGNode]:
    return self.start_nodes.values()

  def get_graphviz_dot_source(self) -> str:
    exporter = graphtrait.GraphvizDotGraphExporter(self)
    exporter.set_node_colors({
      GlobalICFGNode : "purple",
      FunEntryICFGNode : "yellow",
      FunExitICFGNode : "green",
      CallICFGNode : "red",
      RetICFGNode : "blue",
      EndingICFGNode : "darkgreen",
      IntraICFGNode : "black",
    })
    visitor = graphtrait.GraphVisitor()
    visitor.visit(self, exporter)
    return exporter.dot.source

  @staticmethod
  def build(m : VNModel) -> ICFG:
    icfg = ICFG()
    pending_calls : dict[VNCallInst, tuple] = {}
    pending_tailcalls : dict[VNTailCallInst, FunExitICFGNode] = {}
    function_decls : dict[VNFunction, FunEntryICFGNode] = {}
    function_returnable_exits : dict[FunEntryICFGNode, list[FunExitICFGNode]] = {}
    def add_return_candidate(entry : FunEntryICFGNode, ret : FunExitICFGNode):
      if entry not in function_returnable_exits:
        function_returnable_exits[entry] = [ret]
      else:
        function_returnable_exits[entry].append(ret)
    def init_handle_function(f : VNFunction):
      entry = FunEntryICFGNode(f)
      entry.add_to_graph(icfg)
      if entrypoint := f.get_entry_point():
        g = GlobalICFGNode(entrypoint)
        g.add_to_graph(icfg)
        ICFGEdge(g, entry)

      # 跳过函数声明
      if f.body.blocks.size == 0:
        function_decls[f] = entry
        return

      # 首先过一遍所有基本块，把基本块的结点都做出来
      blocks = {}
      for b in f.body.blocks:
        curblock = IntraICFGNode(b)
        curblock.add_to_graph(icfg)
        blocks[b] = curblock
      entryblock = f.body.blocks.front

      # 保证能从函数入口到入口基本块
      ICFGEdge(entry, blocks[entryblock])

      # 开始处理函数体内部
      for b in f.body.blocks:
        curpos = blocks[b]
        for op in b.body:
          if isinstance(op, VNTerminatorInstBase):
            if isinstance(op, VNLocalTransferInstBase):
              # 去掉重边
              visited = set()
              for dest in op.get_local_cfg_dest():
                if dest not in visited:
                  visited.add(dest)
                  destentry = blocks[dest]
                  ICFGEdge(curpos, destentry)
            elif isinstance(op, VNExitInstBase):
              exitnode = FunExitICFGNode(op)
              exitnode.add_to_graph(icfg)
              ICFGEdge(curpos, exitnode)
              if isinstance(op, VNEndingInst):
                endingnode = EndingICFGNode(op)
                endingnode.add_to_graph(icfg)
                ICFGEdge(exitnode, endingnode)
              elif isinstance(op, VNReturnInst):
                add_return_candidate(entry, exitnode)
              elif isinstance(op, VNTailCallInst):
                pending_tailcalls[op] = exitnode
                add_return_candidate(entry, exitnode)
              else:
                raise NotImplementedError("Unexpected terminator type " + type(op).__name__)
            else:
              raise NotImplementedError("Unexpected terminator type " + type(op).__name__)
          elif isinstance(op, VNCallInst):
            callout = CallICFGNode(op)
            callret = RetICFGNode(op)
            callout.add_to_graph(icfg)
            callret.add_to_graph(icfg)
            pending_calls[op] = (callout, callret)
            ICFGEdge(curpos, callout)
            curpos = callret
      # OK

    # 首先解决函数内部的部分
    for ns in m.namespace:
      for f in ns.functions:
        init_handle_function(f)
    # 其次解决调用的前向边（调用者到被调用者）
    pending_callret_pairs : dict[FunEntryICFGNode, list[RetICFGNode]] = {}
    for callinst, calltuple in pending_calls.items():
      callout, callret = calltuple
      assert isinstance(callout, CallICFGNode)
      assert isinstance(callret, RetICFGNode)
      callee = callinst.target.get()
      if callee in function_decls:
        # 这只是个声明
        calleeentry = function_decls[callee]
        ICFGEdge(callout, calleeentry)
        ICFGEdge(calleeentry, callret)
        continue
      calleeentry = icfg.entry_map[callee]
      ICFGEdge(callout, calleeentry)
      if calleeentry not in pending_callret_pairs:
        pending_callret_pairs[calleeentry] = [callret]
      else:
        pending_callret_pairs[calleeentry].append(callret)
    for callinst, callexit in pending_tailcalls.items():
      callee = callinst.target.get()
      if callee in function_decls:
        # 这只是个声明
        calleeentry = function_decls[callee]
        ICFGEdge(callexit, calleeentry)
        continue
      calleeentry = icfg.entry_map[callee]
      ICFGEdge(callexit, calleeentry)
    # 最后解决调用的后向边（被调用者到调用者）
    completed_return_sites : dict[FunEntryICFGNode, set[ICFGNode]] = {}
    for declentry in function_decls.values():
      completed_return_sites[declentry] = set([declentry])
    def get_return_sites(e : FunEntryICFGNode) -> set[ICFGNode]:
      if e in completed_return_sites:
        return completed_return_sites[e]
      # 立即把当前结果放入 completed_return_sites 以应对可能出现的（有限、无限）递归
      result = set()
      completed_return_sites[e] = result
      if e not in function_returnable_exits:
        # 这函数永远在自己的基本块间循环
        return result
      for exitnode in function_returnable_exits[e]:
        exitinst = exitnode.exitinst
        if isinstance(exitinst, VNReturnInst):
          result.add(exitnode)
          continue
        if isinstance(exitinst, VNTailCallInst):
          for calledge in exitnode.get_outgoing_edges():
            calleenode = calledge.get_dest_node()
            assert isinstance(calleenode, FunEntryICFGNode)
            destset = get_return_sites(calleenode)
            if destset is not result:
              result.update(destset)
          continue
        raise NotImplementedError('Unexpected exit inst type: ' + type(exitinst).__name__)
      return result
    for entrynode, retlist in pending_callret_pairs.items():
      retfromsites = get_return_sites(entrynode)
      for fromnode in retfromsites:
        for tonode in retlist:
          ICFGEdge(fromnode, tonode)
    return icfg

  def get_node_weights(self) -> dict[ICFGNode, decimal.Decimal]:
    # 计算每个 ICFG 结点的权重，权重被定义为正常游玩（全结局，多周目遇重复内容时跳过）下某个 ICFG 结点的期望经历次数
    # 比如如果一段剧情在整个故事中反复出现，则结点的权重大于1
    # 又如果主线中有个小分支，完成任一分支即可继续主线，则分支上的结点的权重小于1
    # 从入口不可达的结点不会出现在该 dict 中

    # 正常的解法应该是这样：
    # 1. 生成一个 Context-sensitive ICFG ，被调用不止一次的函数的所有 ICFG 结点都在每个调用上下文中复制一遍
    # 2. 找到 Context-sensitive ICFG 中所有的 articulation point，这些结点是全结局时必须通过的点，权重为1
    #    于此同时，所有不可达的结点的权重为零
    # 3. 对每个可达但是不是 articulation point 的结点而言，它们一定在被 >=2 个 articulation point 截住的路径上；
    #    我们穷举所有从一个 articulation point 到另一个的路径（比如一共 N 条路径），根据经过结点的路径的数量来计算结点的权（比如 N 条路径经过结点 k 次，则权重 k/N）
    # 4. 把所有在 Context-sensitive ICFG 中的权重映射回原来的 ICFG 结点（就是加起来）
    # 现在为了图省事，暂时令所有的权值都为1，以后等有时间了再改
    # https://www.hackerearth.com/practice/algorithms/graphs/articulation-points-and-bridges/tutorial/
    # https://www.geeksforgeeks.org/articulation-points-or-cut-vertices-in-a-graph/
    result : dict[ICFGNode, decimal.Decimal] = {}
    for n in self.get_all_nodes():
      result[n] = decimal.Decimal(1)
    return result


@BackendDecl('dump-icfg', input_decl=VNModel, output_decl=IODecl("Graphviz DOT source", match_suffix="dot", nargs=1))
class DumpICFGPass(TransformBase):
  # 目前我们按照 IR 无关的方式设置命令（没有VN前缀），但是运行时检查是否是 VNModel
  # 等以后有其他需要 ICFG 的 IR 时，我们这里直接改检查，不用改调用方式
  def run(self) -> None:
    assert len(self.inputs) == 1
    model = self.inputs[0]
    assert isinstance(model, VNModel)
    graph = ICFG.build(model)
    with open(self.output, "w", encoding="utf-8") as f:
      f.write(graph.get_graphviz_dot_source())
