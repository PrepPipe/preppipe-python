# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *
from .vnstep import *
from .vnfunction import *
from .vnasset import *
from .vnrecord import *
from .vnnamespace import *

class VNStepBuilder:
  _namespace : VNNamespace
  _step : VNStep
  _insert_at_block_end : Block
  def __init__(self, namespace : VNNamespace, step : VNStep, insert_at_block_end : Block) -> None:
    self._namespace = namespace
    self._step = step
    self._insert_at_block_end = insert_at_block_end
    # 若 insert_at_block_end 为 None， 我们就把插入点设在单步的结尾（假设单区单块）
    # 如果该单步还没有任何区与块，就都创建起来
    if insert_at_block_end is None:
      region_names = list(step.get_region_names())
      assert len(region_names) < 2
      region = None
      if len(region_names) == 0:
        region = step.get_or_create_region()
        self._insert_at_block_end = region.add_block('')
      else:
        region = step.get_region(region_names[0])
        assert region.blocks.size < 2
        if region.blocks.size == 0:
          self._insert_at_block_end = region.add_block('')
        else:
          self._insert_at_block_end = region.blocks.back
  
  @property
  def namespace(self) -> VNNamespace:
    return self._namespace


class VNBlockBuilder:
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
  