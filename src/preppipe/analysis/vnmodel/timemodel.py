# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from preppipe.vnmodel import Block, Value, decimal
from ...vnmodel import *
from ...exceptions import *

class TimeModelBase:
  # VNModel 的 IR 使用抽象的“时间值”用来表达指令间的起止要求等
  # 时间模型可以用来将上述抽象的时间值转化为可以量化、比较的具象的值
  # 实际上就是计算每条指令需要在什么具体的时间开始、什么时间结束，
  # 这样抽象的时间值就被赋予了实际的时间，帮助我们进行比如估算资源素材的使用时间这样的操作
  # 该类描述的是时间模型结果的一个通用接口，我们可以有不同精度的时间模型用于不同的操作
  # 所有的时间模型都假设是上下文无关的（即一段指令所需时间只由指令本身决定，不管控制流从哪来到哪去）
  # 不同的时间模型的单位时间可以有不同的含义，比如精确一点的可以用秒，粗略点的可以指两指令间间隔的发言指令的数量

  # 在使用该模型估算资源使用情况时，如果时长值小于该值，我们需要提供警告
  # ...算了，以后再决定具体的值
  # DURATION_LOW_LIMIT_ASSETUSAGE : typing.ClassVar[decimal.Decimal] = decimal.Decimal(0)

  def get_duration(self, starttime : Value, endtime : Value, block : Block) -> decimal.Decimal:
    # 计算开始时间值到结束时间值之间流逝的时间
    # 两个时间值所涉及的指令一定在同一个基本块中
    raise PPNotImplementedError()


class SayCountTimeModel(TimeModelBase):
  # 我们使用发言指令的数量来表达时间

  # DURATION_LOW_LIMIT_ASSETUSAGE : typing.ClassVar[decimal.Decimal] = decimal.Decimal(3)

  def get_duration(self, starttime: Value, endtime: Value, block: Block) -> decimal.Decimal:
    assert isinstance(starttime.valuetype, VNTimeOrderType)
    assert isinstance(endtime.valuetype, VNTimeOrderType)
    if starttime is endtime:
      return decimal.Decimal(0)
    assert isinstance(endtime, OpResult)
    endinst = endtime.parent
    if endinst.parent_block is not block:
      assert isinstance(endinst.parent_op, VNInstructionGroup)
      endinst = endinst.parent_op
      assert endinst.parent_block is block

    if isinstance(starttime, BlockArgument):
      startinst = block.body.front
    elif isinstance(starttime, OpResult):
      startinst = starttime.parent.get_next_node()
      if startinst.parent_block is not block:
        assert isinstance(startinst.parent_op, VNInstructionGroup)
        startinst = startinst.parent_op
        assert startinst.parent_block is block
    else:
      raise PPInternalError("Unexpected starttime source")

    cnt = 0
    while True:
      if isinstance(startinst, VNSayInstructionGroup):
        cnt += 1
      if startinst is endinst:
        return decimal.Decimal(cnt)
      startinst = startinst.get_next_node()
