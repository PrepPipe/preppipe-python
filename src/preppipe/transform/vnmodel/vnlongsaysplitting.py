# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import unicodedata
import dataclasses
import argparse

from ...vnmodel import *
from ...pipeline import TransformBase, TransformArgumentGroup, MiddleEndDecl

def _is_character_fullwidth(ch : str):
  # https://stackoverflow.com/questions/23058564/checking-a-character-is-fullwidth-or-halfwidth-in-python
  return unicodedata.east_asian_width(ch) in ('F', 'W', 'A')

@dataclasses.dataclass
class _LongSaySplittingSettings:
  min_length_start_splitting : int = 180 # 发言长度达到多少个半宽字符时开始进行分隔
  target_length : int = 60 # 如果开始分隔，我们大概缩减到什么长度
  unknown_element_length : int = 6 # 如果有除了字符串字面值之外的内容，我们假设它的长度是多少

def vn_long_say_splitting(m : VNModel, setting : _LongSaySplittingSettings):
  assert setting.min_length_start_splitting >= setting.target_length and setting.target_length >= 0
  # 我们遍历所有的发言指令组，如果发言满足以下要求：
  # 1. 发言内容长过设定值
  # 2. 该发言内容没有编号（有编号 sayid 的话有可能会破坏编号）
  # 3. 该发言没有语音，只有发言者、发言内容，可能再加侧边头像图片
  # 4. 该发言的结束时间最多只有等待指令 (VNWaitInst) 一个使用者；可以没有使用者
  # 5. 该发言没有其他无法拆分的内容
  # 那么我们尝试将该发言拆分成更短的内容。结束时间将取最后一截发言的结束时间。

  def get_total_length_hw(sayoperand : OpOperand) -> int:
    total_length_hw = 0
    for u in sayoperand.operanduses():
      v = u.value
      if isinstance(v, (StringLiteral, TextFragmentLiteral)):
        s = v.get_string()
        for ch in s:
          total_length_hw += 2 if _is_character_fullwidth(ch) else 1
      else:
        total_length_hw += setting.unknown_element_length
    return total_length_hw

  def check_if_should_break(say: VNSayInstructionGroup) -> bool:
    if say.sayid.try_get_value():
      return False

    is_content_found = False
    for memberop in say.body.body:
      if isinstance(memberop, MetadataOp):
        continue
      if isinstance(memberop, VNPutInst):
        if memberop.transition.get_num_operands() > 0 or len(memberop.placeat) > 0:
          return False
        dev = memberop.device.try_get_value()
        assert isinstance(dev, VNDeviceSymbol)
        match dev.get_std_device_kind():
          case VNStandardDeviceKind.O_SAY_NAME_TEXT | VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY:
            pass
          case VNStandardDeviceKind.O_SAY_TEXT_TEXT:
            # 这是说话内容，我们需要检查内容长度
            is_content_found = True
            total_length = get_total_length_hw(memberop.content)
            if total_length <= setting.min_length_start_splitting:
              return False
          case _:
            # 不知道这是什么内容，很可能没法拆分
            return False
        continue
      # 到这的话这个成员指令既不是 MetadataOp 又不是 VNPutInst
      return False

    if not is_content_found:
      # 虽然不太可能，但万一没找到发言内容，我们也不拆分
      return False

    # 到这的话发言内容够长，其他条件都满足
    # 检查有谁使用了这个发言指令的结束时间
    # 如果只有一个等待指令，那么我们可以拆分
    is_unique_wait_found = False
    for u in say.get_finish_time().uses:
      user = u.user_op
      if isinstance(user, VNWaitInstruction):
        if is_unique_wait_found:
          # 找到了第二个等待，不行
          return False
        else:
          is_unique_wait_found = True
      else:
        # 有其他任何使用者时我们都不拆分
        return False

    # 所有检查完成，确认能够拆分
    return True

  def break_say(say : VNSayInstructionGroup):
    # 在这里我们只使用简单的基于标点符号的分句方法
    md_to_move : list[MetadataOp] = [] # 需要转移到第一个发言指令组前的元数据
    content_to_copy : list[VNPutInst] = [] # 需要在每个拆分出的发言指令组中重复的指令
    say_text_list : list[list[Value]] = [] # 拆分出的发言内容
    say_text_device : VNDeviceSymbol | None = None
    sentence_breakable_marks = '.?!;。？！；…'
    quote_dict = {
      '"' : '"', '“' : '”',
      '(' : ')', '（' : '）',
      '[' : ']', '【' : '】'
    }
    for memberop in say.body.body:
      if isinstance(memberop, MetadataOp):
        md_to_move.append(memberop)
      elif isinstance(memberop, VNPutInst):
        dev = memberop.device.try_get_value()
        assert isinstance(dev, VNDeviceSymbol)
        say_text_device = dev
        match dev.get_std_device_kind():
          case VNStandardDeviceKind.O_SAY_NAME_TEXT | VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY:
            content_to_copy.append(memberop)
          case VNStandardDeviceKind.O_SAY_TEXT_TEXT:
            cur_say_len = 0
            cur_say_hasend = False # 句中是否已有结束符
            cur_say_list : list[Value] = []
            cur_say_quotemode_stack : list[str] = []
            for u in memberop.content.operanduses():
              v = u.value
              if isinstance(v, (StringLiteral, TextFragmentLiteral)):
                s = v.get_string()
                last_break_pos = -1
                committed_content_pos = -1
                pos = 0
                for ch in s:
                  pos += 1
                  curlen = 2 if _is_character_fullwidth(ch) else 1
                  if len(cur_say_quotemode_stack) > 0 and ch in cur_say_quotemode_stack[-1]:
                    cur_say_quotemode_stack.pop()
                    cur_say_len += curlen
                    cur_say_hasend = False
                    continue
                  elif ch in quote_dict:
                    cur_say_quotemode_stack.append(quote_dict[ch])
                    cur_say_len += curlen
                    cur_say_hasend = False
                    continue
                  elif len(cur_say_quotemode_stack) > 0:
                    # 还在引号中
                    cur_say_len += curlen
                    continue
                  # 不在引号中的情况
                  if ch in sentence_breakable_marks:
                    # 这是个引号外的结束符号
                    cur_say_len += curlen
                    last_break_pos = pos
                    continue
                  # 也不是结束符号的话，看看我们是否已经把最后的内容输出了
                  # 还没的话进行输出
                  if cur_say_len >= setting.target_length:
                    if cur_say_hasend:
                      # 已经可以输出了，不需要现在该段文本的内容
                      assert len(cur_say_list) > 0
                      say_text_list.append(cur_say_list)
                      cur_say_list = []
                      cur_say_len = 0
                      cur_say_hasend = False
                    elif last_break_pos >= 0 and last_break_pos > committed_content_pos+1:
                      # 当前句需要该段文本中的一部分
                      newstr = s[committed_content_pos+1:last_break_pos]
                      assert len(newstr) > 0
                      newvalue = StringLiteral.get(newstr, m.context)
                      if isinstance(v, TextFragmentLiteral):
                        newvalue = TextFragmentLiteral.get(m.context, newvalue, v.style)
                      cur_say_list.append(newvalue)
                      say_text_list.append(cur_say_list)
                      cur_say_list = []
                      cur_say_len = 0
                      cur_say_hasend = False
                      committed_content_pos = last_break_pos - 1
                    # 如果都不满足的话，当前句还不能结束
                  cur_say_len += curlen
                  cur_say_hasend = False
                # 到这的话该句中的内容已经走完一遍了
                if committed_content_pos < len(s):
                  # 还有内容没有加到发言中
                  if committed_content_pos == -1:
                    newvalue = v
                  else:
                    newstr = s[committed_content_pos+1:]
                    assert len(newstr) > 0
                    newvalue = StringLiteral.get(newstr, m.context)
                    if isinstance(v, TextFragmentLiteral):
                      newvalue = TextFragmentLiteral.get(m.context, newvalue, v.style)
                  cur_say_list.append(newvalue)
                  if last_break_pos == len(s):
                    cur_say_hasend = True
              else:
                # 不是字符串字面值
                cur_say_list.append(v)
                cur_say_len += setting.unknown_element_length
                cur_say_hasend = False
            # 所有内容都处理完了
            if len(cur_say_list) > 0:
              say_text_list.append(cur_say_list)
          case _:
            raise RuntimeError('Should not happen')
      else:
        # 不是 MetadataOp 或 VNPutInst
        raise RuntimeError('Should not happen')
    # 原来的发言里的所有内容都处理完了
    if len(say_text_list) == 1:
      # 如果没有找到可断句的地方的话什么也不做
      return
    assert len(say_text_list) > 1

    # 先把元数据从发言指令组里面拉出来
    for md in md_to_move:
      md.remove_from_parent()
      md.insert_before(say)
    # 然后开始新建
    basename = say.name if len(say.name) > 0 else 'anon'
    say_index = 0
    cur_time = say.get_start_time()
    sayer = [u.value for u in say.sayer.operanduses()]
    for content in say_text_list:
      newsayname = basename + '_longsaysplitting_' + str(say_index)
      say_index += 1
      newsay = VNSayInstructionGroup.create(context=m.context, start_time=cur_time, sayer=sayer, name=newsayname, loc=say.location)
      newsay.insert_before(say)
      for child in content_to_copy:
        cloned = child.clone()
        cloned.set_start_time(cur_time)
        newsay.body.push_back(cloned)
      puttext = VNPutInst.create(context=m.context, start_time=cur_time, content=content, device=say_text_device, loc=say.location)
      newsay.body.push_back(puttext)
      newsay.group_finish_time.set_operand(0, puttext.get_finish_time())
      cur_time = newsay.get_finish_time()
      if say_index < len(say_text_list):
        wait = VNWaitInstruction.create(context=m.context, start_time=cur_time, loc=say.location)
        wait.insert_before(say)
        cur_time = wait.get_finish_time()
      else:
        # 这是最后一项
        say.get_finish_time().replace_all_uses_with(cur_time)
    say.erase_from_parent()
    # 结束

  def count_block_say_len(block : Block):
    cumulative = 0
    for op in block.body:
      if isinstance(op, VNSayInstructionGroup):
        for memberop in op.body.body:
          if isinstance(memberop, VNPutInst):
            if dev := memberop.device.try_get_value():
              if dev.get_std_device_kind() == VNStandardDeviceKind.O_SAY_TEXT_TEXT:
                cumulative += get_total_length_hw(memberop.content)
    return cumulative

  say_to_break : list[VNSayInstructionGroup] = []
  for ns in m.namespace:
    for func in ns.functions:
      for block in func.body.blocks:
        for op in block.body:
          if isinstance(op, VNSayInstructionGroup):
            # 检查是否需要拆分，需要的话就加到 say_to_break 里
            if check_if_should_break(op):
              say_to_break.append(op)
        if len(say_to_break) > 0:
          # 为了检验是否正确，如果我们要拆分发言的话，
          # 我们先统计一下该块的发言内容总共多长，然后做拆分，最后再统计一下
          # 如果字宽一致那就没问题，否则就肯定有 Bug
          say_len_before = count_block_say_len(block)
          for say in say_to_break:
            break_say(say)
          say_to_break.clear()
          say_len_after = count_block_say_len(block)
          if say_len_after != say_len_before:
            print('Say length not match after long say splitting: before=' + str(say_len_before) + ', after=' + str(say_len_after))
            raise RuntimeError('Say length not match after long say splitting')

@TransformArgumentGroup("vn-longsaysplitting", "Options for long say splitting pass")
@MiddleEndDecl('vn-longsaysplitting', input_decl=VNModel, output_decl=VNModel)
class VNLongSaySplittingPass(TransformBase):
  setting : typing.ClassVar[_LongSaySplittingSettings] = _LongSaySplittingSettings()

  @staticmethod
  def install_arguments(argument_group : argparse._ArgumentGroup):
    argument_group.add_argument("--longsaysplitting-length-split", nargs=1, type=int)
    argument_group.add_argument("--longsaysplitting-length-target", nargs=1, type=int)

  @staticmethod
  def handle_arguments(args : argparse.Namespace):
    if split_length := args.longsaysplitting_length_split:
      assert isinstance(split_length, list) and len(split_length) == 1
      VNLongSaySplittingPass.setting.min_length_start_splitting = split_length[0]
    if target_length := args.longsaysplitting_length_target:
      assert isinstance(target_length, list) and len(target_length) == 1
      VNLongSaySplittingPass.setting.target_length = target_length[0]

  def run(self) -> VNModel:
    assert len(self.inputs) == 1
    vn_long_say_splitting(self.inputs[0], VNLongSaySplittingPass.setting)
    return self.inputs[0]
