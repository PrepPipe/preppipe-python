# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *
from .vnstep import *
from .vnfunction import *
from .vnasset import *
from .vnrecord import *
from .vninstruction import *
from .vnnamespace import *

class VNInstructionBlockBuilder:
  # 该类作为方便指令创建的构建工具类的基类
  # 若构建工具类需要在某个块内添加指令，则可以继承该类

  _namespace : VNNamespace
  _location : Location

  # 当前插入点信息
  _insert_at_block_end : Block
  _insert_block_time : BlockArgument

  def __init__(self, namespace : VNNamespace, location : Location, insert_at_block_end: Block, insert_block_time : BlockArgument) -> None:
    self._namespace = namespace
    self._location = location
    self._insert_at_block_end = insert_at_block_end
    self._insert_block_time = insert_block_time
  
  @staticmethod
  def _get_block_start_time(block : Block) -> BlockArgument:
    return block.get_or_create_argument('开始时间', VNTimeOrderType.get(block.valuetype.context))
  
  @property
  def context(self) -> Context:
    return self._namespace.context

  @property
  def namespace(self) -> VNNamespace:
    return self._namespace
  
  @property
  def location(self) -> Location:
    return self._location
  
  @location.setter
  def location(self, loc : Location):
    assert loc.context is self._namespace.context
    self._location = loc
  
  # 位置信息没有deleter

  @property
  def insertion_block(self) -> Block:
    return self._insert_at_block_end
  
  @property
  def start_time(self) -> Value:
    return self._insert_block_time
  
  def get_parent_op(self) -> Operation:
    return self._insert_at_block_end.parent.parent

  def _check_loc(self, loc : Location = None) -> Location:
    if loc is not None:
      assert loc.context is self.context
    else:
      loc = self._location
    return loc

  def create_finish_step_inst(self, start_time : Value, name : str = '', loc : Location = None) -> VNFinishStepInst:
    loc = self._check_loc(loc)
    inst = VNFinishStepInst(name, loc)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_branch_inst(self, start_time : Value, default_target : Block, candidates : list[tuple[Value, Block]] = [], name : str = '', loc : Location = None) -> VNBranchInst:
    loc = self._check_loc(loc)
    inst = VNBranchInst(name, loc, default_target)
    for condition, target in candidates:
      inst.add_candidate_destination(condition, target)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_far_jump_inst(self, start_time : Value, target: Block, name : str = '', loc : Location = None) -> VNFarJumpInst:
    loc = self._check_loc(loc)
    inst = VNFarJumpInst(name, loc, target)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_wait_user_inst(self, start_time : Value, name : str = '', loc : Location = None) -> VNWaitUserInst:
    loc = self._check_loc(loc)
    inst = VNWaitUserInst(name, loc)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_remove_inst(self, start_time : Value, handle : Value, name : str = '', loc : Location = None, *, transition : Value = None) -> VNRemoveInst:
    loc = self._check_loc(loc)
    inst = VNRemoveInst(name, loc, handle, transition)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_clear_inst(self, start_time : Value, device : VNDeviceRecord, name : str = '', loc : Location = None, *, transition : Value = None) -> VNClearInst:
    loc = self._check_loc(loc)
    inst = VNClearInst(name, loc, device, transition)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst

  def _populate_displayable_manipulation_inst_common(self, inst : VNDisplayableManipulationInst, variant : Value = None, transition : Value = None, position : Value = None, zorder : int = None, effect : Value = None):
    if variant is not None:
      inst.variant = variant
    if transition is not None:
      inst.transition = transition
    if position is not None:
      inst.position = position
    if zorder is not None:
      inst.zorder = zorder
    if effect is not None:
      inst.effect = effect
  
  def _populate_audio_manipulation_inst_common(self, inst : VNAudioManipulationInst, variant : Value = None, volume : VNConstantFloat | float = None, playback_speed : VNConstantFloat | float = None, transition : Value = None):
    if variant is not None:
      inst.variant = variant
    if transition is not None:
      inst.transition = transition

    if volume is not None:
      inst.volume = volume
    if playback_speed is not None:
      inst.playback_speed = playback_speed

  def create_create_displayable_inst(self, start_time : Value, content : Value, variant : Value, position : Value, name : str = '', loc : Location = None, *, zorder : int = None, effect : Value = None, transition : Value = None) -> VNCreateDisplayableInst:
    loc = self._check_loc(loc)
    inst = VNCreateDisplayableInst(name, loc, content)
    self._populate_displayable_manipulation_inst_common(inst, variant, transition, position, zorder, effect)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_put_displayable_inst(self, start_time : Value, content : Value, variant : Value, position : Value, name : str = '', loc : Location = None, *, zorder : int = None, effect : Value = None, transition : Value = None) -> VNPutDisplayableInst:
    loc = self._check_loc(loc)
    inst = VNPutDisplayableInst(name, loc, content)
    self._populate_displayable_manipulation_inst_common(inst, variant, transition, position, zorder, effect)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_modify_displayable_inst(self, start_time : Value, handle : Value, name : str = '', loc : Location = None, *, variant : Value = None, position : Value = None, zorder : int = None, effect : Value = None, transition : Value = None) -> VNModifyDisplayableInst:
    loc = self._check_loc(loc)
    inst = VNModifyDisplayableInst(name, loc, handle)
    self._populate_displayable_manipulation_inst_common(inst, variant, position, zorder, transition, effect)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_create_audio_inst(self, start_time : Value, content : Value, variant : Value, name : str = '', loc : Location = None, *, volume : VNConstantFloat | float = None, playback_speed : VNConstantFloat | float = None, transition : Value = None) -> VNCreateAudioInst:
    loc = self._check_loc(loc)
    inst = VNCreateAudioInst(name, loc, content)
    self._populate_audio_manipulation_inst_common(inst, variant, volume, playback_speed, transition)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_put_audio_inst(self, start_time : Value, content : Value, variant : Value, name : str = '', loc : Location = None, *, volume : VNConstantFloat | float = None, playback_speed : VNConstantFloat | float = None, transition : Value = None) -> VNPutAudioInst:
    loc = self._check_loc(loc)
    inst = VNPutAudioInst(name, loc, content)
    self._populate_audio_manipulation_inst_common(inst, variant, volume, playback_speed, transition)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_modify_audio_inst(self, start_time : Value, handle : Value, name : str = '', loc : Location = None, *, variant : Value = None, volume : VNConstantFloat | float = None, playback_speed : VNConstantFloat | float = None, transition : Value = None) -> VNModifyAudioInst:
    loc = self._check_loc(loc)
    inst = VNModifyAudioInst(name, loc, handle)
    self._populate_audio_manipulation_inst_common(inst, variant, volume, playback_speed, transition)
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst
  
  def create_put_text_inst(self, start_time : Value, content : Value, variant : Value, name : str = '', loc : Location = None) -> VNPutTextInst:
    loc = self._check_loc(loc)
    inst = VNPutTextInst(name, loc, content)
    inst.variant = variant
    inst.start_time = start_time
    self._insert_at_block_end.push_back(inst)
    return inst

class VNStepBuilder(VNInstructionBlockBuilder):
  # 构建一个单步（一般是常规单步）
  _step : VNStep

  def __init__(self, namespace : VNNamespace, step : VNStep, insert_at_block_end : Block) -> None:
    # 若 insert_at_block_end 为 None， 我们就把插入点设在单步的结尾（假设单区单块）
    # 如果该单步还没有任何区与块，就都创建起来
    if insert_at_block_end is None:
      region_names = list(step.get_region_names())
      assert len(region_names) < 2
      region = None
      if len(region_names) == 0:
        region = step.get_or_create_region()
        insert_at_block_end = region.add_block('')
      else:
        region = step.get_region(region_names[0])
        assert region.blocks.size < 2
        if region.blocks.size == 0:
          insert_at_block_end = region.add_block('')
        else:
          insert_at_block_end = region.blocks.back
    # 找到作为插入点的块后，把该块的开始时间值存下来
    # 如果我们在此新建了一个块，就把开始时间参数也给加上去
    insert_block_time = VNInstructionBlockBuilder._get_block_start_time(insert_at_block_end)
    super().__init__(namespace, step.location, insert_at_block_end, insert_block_time)
    self._step = step
  
  @property
  def step(self) -> VNStep:
    return self._step

  def create_say_instruction_group(self, start_time : Value, characters : VNCharacterRecord | list[VNCharacterRecord] = None, name : str = '', loc : Location = None) -> VNSayInstructionGroup:
    loc = self._check_loc(loc)
    group = VNSayInstructionGroup(name, loc)
    if characters is not None:
      group.characters = characters
    group.start_time = start_time
    self._insert_at_block_end.push_back(group)
    return group
  
  def create_instruction_group_builder(self, group : VNInstructionGroup) -> VNInstructionBlockBuilder:
    assert isinstance(group, VNSayInstructionGroup)
    return VNInstructionBlockBuilder(self.namespace, self.location, group.body, group.body_start_time)


class VNBlockBuilder:
  # 在一个函数内的块内构建单步的构建工具类

  _namespace : VNNamespace
  _location : Location
  _insert_before_step : VNStep # if provided, all new steps are inserted before this step
  _insert_at_block_end : Block # if provided, all new steps are added at the end of this block

  def __init__(self, namespace : VNNamespace, *, location : Location = None, insert_before_step : VNStep = None, insert_at_block_end : Block = None) -> None:
    # should only provide one
    assert (insert_before_step is not None) != (insert_at_block_end is not None)

    self._namespace = namespace
    self._location = location
    if location is not None:
      assert location.context is self._namespace.context
    else:
      self._location = Location.getNullLocation(self._namespace.context)

    self._insert_before_step = insert_before_step
    self._insert_at_block_end = insert_at_block_end
  
  @property
  def context(self) -> Context:
    return self._namespace.context
  
  @property
  def namespace(self) -> VNNamespace:
    return self._namespace
  
  @property
  def location(self) -> Location:
    return self._location
  
  @location.setter
  def location(self, loc : Location):
    assert loc.context is self._namespace.context
    self._location = loc
  
  # 位置信息没有deleter
  
  def _check_loc(self, loc : Location = None) -> Location:
    if loc is not None:
      assert loc.context is self.context
    else:
      loc = self._location
    return loc

  def _insert_step_impl(self, step : VNStep):
    if self._insert_before_step is not None:
      step.insert_before(self._insert_before_step)
    self._insert_at_block_end.push_back(step)
  
  def create_call(self, callee : Value, loc : Location = None) -> VNCallStep:
    loc = self._check_loc(loc)
    result = VNCallStep('', loc, callee)
    self._insert_step_impl(result)
    return result
  
  def create_return(self, loc : Location = None) -> VNReturnStep:
    loc = self._check_loc(loc)
    result = VNReturnStep('', loc)
    self._insert_step_impl(result)
    return result
  
  def create_step(self, name : str = '', loc : Location = None) -> VNRegularStep:
    loc = self._check_loc(loc)
    result = VNRegularStep(name, loc)
    self._insert_step_impl(result)
    return result
  
  def create_step_builder(self, name : str = '', loc : Location = None) -> VNStepBuilder:
    step = self.create_step(name, loc)
    builder = VNStepBuilder(self._namespace, step)
    return builder
  