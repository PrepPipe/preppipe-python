# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from preppipe.irbase import Operation, typing
from preppipe.util.audit import typing

from ..icfg import ICFG
from .timemodel import TimeModelBase
from .timemodel import SayCountTimeModel
from ...vnmodel import *
from ...pipeline import TransformBase, BackendDecl, IODecl
from ...language import TranslationDomain

_TR_assetusage = TranslationDomain("assetusage")

@dataclasses.dataclass(frozen=True)
class AssetUsage:
  # 我们统计所有资源的使用情况：
  # “资源” Asset 包括：
  # 1. 已包含在 IR 中的内容 （AssetData 的实例）
  # 2. 只在 IR 中声明的内容 （继承了 AssetDeclarationTrait 的实例）
  # 3. 占位资源 （继承了 AssetPlaceholderTrait 的实例）
  # 其他所有值均不视为资源，包括字符串内容等
  # “使用情况”包含两部分的“使用时长、次数”的统计信息：
  # 1. 对于在使用句柄的指令(Create/Modify)，资源的“使用情况”包含通过时间模型所计算的总时长
  # 2. 对于 Put 指令，资源的“使用情况”包含对 Put 次数的统计

  # 所有直接出场的值（直接在 Create/Put/Modify 中用到的值，不向下解析为资源）所出场的总时长、出现次数
  # 因为都有算上 ICFG 结点的权重，所以“出现次数”这样的整数也用 decimal.Decimal 表示
  direct_value_usage_duration : dict[Value, dict[VNDeviceSymbol, decimal.Decimal]]
  direct_value_usage_occurrence : dict[Value, dict[VNDeviceSymbol, decimal.Decimal]]

  # 所有“资源”（包括 AssetData, Decl, Placeholder）直接或间接出现在哪些 direct_value_usage 的键里
  # 如果一个值直接出现在 Create/Put/Modify 等指令中，则该 list[Value] 会包含该值本身
  asset_references : dict[Value, list[Value]]

  # 设备类型 --> [<资源，使用总时长>] (降序排列)
  asset_usage_stat : dict[VNDeviceSymbol, list[tuple[Value, decimal.Decimal, decimal.Decimal]]]

  _tr_assetusage = _TR_assetusage.tr("header",
    en="Asset usages:",
    zh_cn="资源使用情况：",
    zh_hk="資源使用情況：",
  )
  _tr_usage_detail_duration = _TR_assetusage.tr("detail_duration",
    en="{duration} say(s)",
    zh_cn="{duration} 句发言",
    zh_hk="{duration} 句發言",
  )
  _tr_usage_detail_occurrence = _TR_assetusage.tr("detail_occurrence",
    en="{occurrence} appearance with unknown duration",
    zh_cn="{occurrence} 次使用（未知时长）",
    zh_hk="{occurrence} 次使用（未知時長）",
  )

  def __str__(self) -> str:
    result = [self._tr_assetusage.get()]
    for dev, vlist in self.asset_usage_stat.items():
      pretty_name = VNStandardDeviceKind.get_pretty_device_name(dev.name)
      result.append(pretty_name + ':')
      for asset, duration, occurrence in vlist:
        details = []
        if duration > 0:
          details.append(self._tr_usage_detail_duration.format(duration=str(duration)))
        if occurrence > 0:
          details.append(self._tr_usage_detail_occurrence.format(occurrence=str(occurrence)))
        detailstr = ' + '.join(details)
        result.append('    ' + str(asset) + ': ' + detailstr)
    return '\n'.join(result)

  def pretty_print(self) -> str:
    # 已在 __str__ 中实现
    return str(self)

  @staticmethod
  def build(m : VNModel, icfg : ICFG, t : TimeModelBase) -> AssetUsage:
    direct_value_usage_duration : dict[Value, dict[VNDeviceSymbol, decimal.Decimal]] = {}
    direct_value_usage_occurrence : dict[Value, dict[VNDeviceSymbol, decimal.Decimal]] = {}
    asset_references : dict[Value, list[Value]] = {}
    asset_usage_stat : dict[VNDeviceSymbol, list[tuple[Value, decimal.Decimal, decimal.Decimal]]] = {}
    weights = icfg.get_node_weights()
    def add_usage(v : Value, dev : VNDeviceSymbol, weight : decimal.Decimal, dest : dict[Value, dict[VNDeviceSymbol, decimal.Decimal]]):
      if v not in dest:
        dest[v] = {dev : weight}
        return
      d = dest[v]
      if dev not in d:
        d[dev] = weight
      else:
        d[dev] += weight
    # 我们遍历所有函数，得出每个函数的基本块的各个段的资源使用情况，再乘以 ICFG 结点权重
    # 函数内遍历时需要知道每个基本块入口处有哪些句柄（和他们的值）仍然有效，避免漏掉使用区间
    def handle_function(f : VNFunction):
      # 实际处理一个函数
      # 第一遍遍历时只计算句柄值的所用时长，不计算句柄值所用资源的使用时长
      # 因为第一遍遍历时我们有可能在处理过句柄使用者后再遇到句柄提供者（比如有个循环，循环入口和循环体内对同一句柄加了不同素材）
      # 不过第一遍遍历就可以把使用 Put 的资源的情况统计好了
      # 第一遍遍历完成后，我们需要将对句柄的使用情况转化为对资源的使用情况
      # 为此我们需要计算句柄引用的各资源的权重，而由于句柄可以引用另一个句柄的值（比如两个块相互跳转，一个句柄来回运），互相之间可以有环，这实际上需要一个迭代
      blockarg_handle_dependencies : dict[BlockArgument, list[tuple[Value, decimal.Decimal]]] = {} # （作为块参数的）句柄值的依赖关系图（边集数组）
      handle_usage_states : dict[Value, decimal.Decimal] = {} # 里面的键都是句柄值
      live_handles : dict[Block, list[Value]] = {} # 进入基本块时仍有效的句柄，不包含那些被用作块参数的句柄
      live_handles[f.get_entry_block()] = []
      def update_handle_usage(h : Value, w : decimal.Decimal):
        if h in handle_usage_states:
          handle_usage_states[h] += w
        else:
          handle_usage_states[h] = w
      for block in f.body.blocks:
        # 首先把当前所有“存活”的句柄算上
        live_handle_state_dict : dict[Value, Value] = {} # 句柄 --> 开始时间值
        starttime = block.get_argument('start')
        assert isinstance(starttime.valuetype, VNTimeOrderType)
        for cur_live_handle in live_handles[block]:
          live_handle_state_dict[cur_live_handle] = starttime
        # 把 BlockArgument 中的句柄也给加上
        for arg in block.arguments():
          if arg.name == 'start':
            continue
          assert isinstance(arg.valuetype, VNHandleType)
          live_handle_state_dict[arg] = starttime
        cur_icfg_node = icfg.block_map[block]
        def handle_vninst(op : VNInstruction):
          nonlocal cur_icfg_node
          curtime = op.get_start_time()
          def commit_usages():
            # 结算所有当前有效的句柄
            nonlocal cur_icfg_node
            curweight = weights[cur_icfg_node]
            for handle, start in live_handle_state_dict.items():
              duration = t.get_duration(starttime=start, endtime=curtime, block=block)
              update_handle_usage(handle, duration * curweight)
            return curweight
          # 开始遍历所有指令
          if isinstance(op, VNTerminatorInstBase):
            curweight = commit_usages()
            # 确定在进入基本块时有哪些句柄仍然可用
            # 如果句柄被用于参数传递，我们将该句柄视为不可用
            if isinstance(op, VNLocalTransferInstBase):
              for i in range(0, op.target_list.get_num_operands()):
                destblock : Block = op.target_list.get_operand(i)
                destargs : OpOperand = op.get_blockarg_operandinst(i)
                passedhandles : set[Value] = set()
                # 我们需要把进入目标块时的句柄都整理出来放在 live_handles 中
                argindex = 0
                for u in destargs.operanduses():
                  handle = u.value
                  assert handle in live_handle_state_dict
                  passedhandles.add(handle)
                  arg = destblock.get_argument(str(argindex))
                  if arg not in blockarg_handle_dependencies:
                    blockarg_handle_dependencies[arg] = [(handle, curweight)]
                  else:
                    blockarg_handle_dependencies[arg].append((handle, curweight))
                  argindex += 1
                mergeset = []
                for handle in live_handle_state_dict.keys():
                  if handle in passedhandles:
                    continue
                  mergeset.append(handle)
                if destblock not in live_handles:
                  live_handles[destblock] = mergeset
                else:
                  # 如果已经有记录，就取交集
                  live_handles[destblock] = [v for v in live_handles[destblock] if v in mergeset]
            else:
              # 没有下游指令，不需要考虑后面有什么基本块
              assert isinstance(op, VNExitInstBase)
          elif isinstance(op, VNCallInst):
            curweight = commit_usages()
            cur_icfg_node = icfg.callret_map[op]
            live_handle_state_dict.clear()
          elif isinstance(op, VNPutInst):
            curweight = weights[cur_icfg_node]
            add_usage(op.content.get(), op.device.get(), curweight, direct_value_usage_occurrence)
          elif isinstance(op, VNCreateInst):
            curweight = weights[cur_icfg_node]
            live_handle_state_dict[op] = op.get_start_time()
          elif isinstance(op, VNRemoveInst):
            curweight = weights[cur_icfg_node]
            handle = op.handlein.get()
            durationstart = live_handle_state_dict[handle]
            durationend = op.get_finish_time()
            duration = t.get_duration(starttime=durationstart, endtime=durationend, block=block)
            update_handle_usage(handle, duration * curweight)
            del live_handle_state_dict[handle]
          elif isinstance(op, VNModifyInst):
            # 我们视其为 Remove + Create
            curweight = weights[cur_icfg_node]
            handle = op.handlein.get()
            durationstart = live_handle_state_dict[handle]
            durationend = op.get_start_time() # 为了在不改内容时不重复计算时长
            duration = t.get_duration(starttime=durationstart, endtime=durationend, block=block)
            update_handle_usage(handle, duration * curweight)
            del live_handle_state_dict[handle]
            live_handle_state_dict[op] = op.get_start_time()
          else:
            pass
        for op in block.body:
          if isinstance(op, MetadataOp):
            continue
          assert isinstance(op, VNInstruction)
          if isinstance(op, VNInstructionGroup) and not isinstance(op, VNBackendInstructionGroup):
            for comp in op.body.body:
              if isinstance(comp, MetadataOp):
                continue
              handle_vninst(comp)
          else:
            handle_vninst(op)
      # 接下来把 blockarg_handle_dependencies 里面的解析掉
      # 1. 把所有值的权重标准化（normalize, 使其和为1）
      # 2. 将问题转化为方程组，用库解方程组
      # 在这里我们先假设没有需要解方程组的情况，所有 BlockArgument 直接取值自现有的句柄（而不能是另一个 BlockArgument）
      # 等以后有需要了再把解方程组的代码加上
      blockarg_resolved : dict[BlockArgument, list[tuple[Value, decimal.Decimal]]] = {}
      for arg, srclist in blockarg_handle_dependencies.items():
        assert len(srclist) > 0
        if len(srclist) == 1:
          blockarg_resolved[arg] = [(srclist[0][0], decimal.Decimal(1))]
          continue
        weightsum = decimal.Decimal(0)
        for v, w in srclist:
          weightsum += w
          # 如果句柄值不是直接来自 Create/Modify 指令（而是另一个 BlockArgument），解析他们就需要解方程，暂时不做
          if not isinstance(v, (VNCreateInst, VNModifyInst)):
            raise NotImplementedError("TODO 暂不支持")
        resultlist = []
        for v, w in srclist:
          resultlist.append((v, w/weightsum))
        blockarg_resolved[arg] = resultlist
      # 现在所有句柄应该都能解析了
      for v, usage in handle_usage_states.items():
        if isinstance(v, (VNCreateInst, VNModifyInst)):
          add_usage(v.content.get(), v.device.get(), usage, direct_value_usage_duration)
        elif isinstance(v, BlockArgument):
          assert v in blockarg_resolved
          for comp, w in blockarg_resolved[v]:
            assert isinstance(comp, (VNCreateInst, VNModifyInst))
            assert w <= 1
            add_usage(comp.content.get(), comp.device.get(), usage * w, direct_value_usage_duration)
      # 然后把所有的值解析为对资源的引用
      decomposed_values : set[Value] = set(direct_value_usage_duration.keys())
      decomposed_values.update(direct_value_usage_occurrence.keys())
      for directvalue in decomposed_values:
        # 我们预计所有的内容值都由以下元素组成：
        # 1. AssetData 的子类，代表内嵌的内容
        # 2. AssetPlaceholderTrait 或 AssetDeclarationTrait 的子类，代表占位、声明的内容
        # 3. LiteralExpr 的子类，可以引用其他资源，表示对一个或多个资源的某种处理
        #    注意 LiteralExpr 子类也可能继承 AssetPlaceholderTrait 或 AssetDeclarationTrait，如果是这样的话我们视其为第二类
        # 4. 其他无法识别的内容（应该是 Literal），全部忽略
        worklist = collections.deque()
        worklist.append(directvalue)
        while not len(worklist) == 0:
          curvalue = worklist.popleft()
          if isinstance(curvalue, (AssetData, AssetPlaceholderTrait, AssetDeclarationTrait)):
            if curvalue not in asset_references:
              asset_references[curvalue] = [directvalue]
            else:
              # 同一资源有可能被引用不止一次
              if directvalue not in asset_references[curvalue]:
                asset_references[curvalue].append(directvalue)
          elif isinstance(curvalue, LiteralExpr):
            for v in curvalue.get_value_tuple():
              worklist.append(v)
          else:
            pass
      # 最后再汇总所有的资源引用情况
      for assetvalue, vlist in asset_references.items():
        usage_duration : dict[VNDeviceSymbol, decimal.Decimal] = {}
        usage_occurrence : dict[VNDeviceSymbol, decimal.Decimal] = {}
        def mergeusage(dst : dict[VNDeviceSymbol, decimal.Decimal], src : dict[VNDeviceSymbol, decimal.Decimal]):
          for dev, v in src.items():
            if dev in dst:
              dst[dev] += v
            else:
              dst[dev] = v
        for v in vlist:
          if v in direct_value_usage_duration:
            mergeusage(usage_duration, direct_value_usage_duration[v])
          if v in direct_value_usage_occurrence:
            mergeusage(usage_occurrence, direct_value_usage_occurrence[v])
        alldevices = set(usage_duration.keys())
        alldevices.update(usage_occurrence.keys())
        for dev in alldevices:
          total_duration = usage_duration[dev] if dev in usage_duration else decimal.Decimal(0)
          total_occurrence = usage_occurrence[dev] if dev in usage_occurrence else decimal.Decimal(0)
          if dev not in asset_usage_stat:
            asset_usage_stat[dev] = [(assetvalue, total_duration, total_occurrence)]
          else:
            asset_usage_stat[dev].append((assetvalue, total_duration, total_occurrence))

    for ns in m.namespace:
      for f in ns.functions:
        if f.has_body():
          handle_function(f)

    # 对 asset_usage_stat 进行排序
    for vlist in asset_usage_stat.values():
      # occurence 降序为第二顺序
      vlist.sort(key=lambda t : t[2], reverse=True)
      # duration 降序为第一顺序
      vlist.sort(key=lambda t : t[1], reverse=True)

    return AssetUsage(direct_value_usage_duration=direct_value_usage_duration, direct_value_usage_occurrence=direct_value_usage_occurrence, asset_references=asset_references, asset_usage_stat=asset_usage_stat)

@BackendDecl('vn-assetusage', input_decl=VNModel, output_decl=IODecl("Output Report", match_suffix="txt", nargs=1))
class VNAssetUsagePass(TransformBase):
  def run(self) -> None:
    assert len(self.inputs) == 1
    model = self.inputs[0]
    assert isinstance(model, VNModel)
    graph = ICFG.build(model)
    # graph.dump_graphviz_dot()
    tm = SayCountTimeModel()
    usage = AssetUsage.build(model, graph, tm)
    with open(self.output, "w", encoding="utf-8") as f:
      f.write(usage.pretty_print())
