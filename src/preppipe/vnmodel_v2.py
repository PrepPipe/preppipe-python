# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import io
import pathlib
import typing
import PIL.Image
import pydub
import pathlib
import enum
from enum import Enum

from .commontypes import *

# IR design requirement:
# 1. all control and dataflow dependence must be available in the "main" part, without involving attributes
# 2. options that can affect VN gameplay but not content delivery (e.g., transitions like fade/dissolve/...) are attributes
# 3. Interfacing with the rest of pipeline:
#     - Backends can choose not to implement all functionalities in the IR. Some features are just impossible to implement.
#     - Frontends can choose not to use all functionalities here.
#     - IR transform / analysis must support all functionalities, including attributes. These code are expected to be part of preppipe and maintained in-tree.

# ----------------------------------------------------------
# Type system
# ----------------------------------------------------------
# Type objects carry the "type traits" of corresponding types
# Each trait object interface describes how to use a value as if it is the given type

 
class VNValueType(IRTypeObject):
  """Base class of all types"""
  def __eq__(self, other) -> bool:
    return (other is self) or type(self) == type(other)
  
  def is_bool_type(self):
    return isinstance(self, VNBoolTrait)
  def is_integer_type(self):
    return isinstance(self, VNIntegerTrait)
  def is_string_type(self):
    return isinstance(self, VNStringTrait)

class VNBoolTrait:
  def __init__(self) -> None:
    super().__init__()
  
class VNIntegerTrait:
  def __init__(self) -> None:
    super().__init__()

class VNFloatTrait:
  def __init__(self) -> None:
    super().__init__()

class VNStringTrait:
  def __init__(self) -> None:
    super().__init__()

class VNPredefinedComponent(Enum):
  # special components
  Control = enum.auto() # if completion of an instruction "takes time" (e.g., play animation, transition, or wait), the result should have a control trait
  Data = enum.auto()
  TextTerminal = enum.auto() # including (from back to front) text dialog box, character side image, and text screen. The "voice" channel is also included
  
  # visual components
  BackgroundBack = enum.auto() # after the background image; only shown when the background is undergoing transforms (when darking out, etc)
  Background = enum.auto()
  BackgroundCover = enum.auto() # layer above background and below everything else; used to cover a portion of background
  CharacterSpriteBack = enum.auto() # layer below character sprite; useful for effects, etc
  CharacterSprite = enum.auto()
  CharacterSpriteCover = enum.auto() # layer above character sprite; useful for effects, etc
  ForegroundBack = enum.auto() # layer below foreground images
  Foreground = enum.auto()
  ForegroundCover = enum.auto()
  
  # sound components
  BackgroundMusic = enum.auto()
  SoundEffect = enum.auto()
  

# type traits for special components
# we have no VNDataTrait; use more precise traits (e.g., VNBoolTrait for bool data)
class VNControlComponentTrait:
  def __init__(self) -> None:
    super().__init__()

class VNTextTerminalComponentTrait:
  def __init__(self) -> None:
    super().__init__()

# type traits for visual components
class VNVisualComponentTrait:
  def __init__(self) -> None:
    super().__init__()
    
  def get_visual_component(self) -> VNPredefinedComponent:
    raise NotImplementedError("VNVisualComponentTrait.get_visual_component() not implemented for " + type(self).__name__)

# type traits for sound component
class VNSoundComponentTrait:
  def __init__(self) -> None:
    super().__init__()
    
  def get_sound_component(self) -> VNPredefinedComponent:
    raise NotImplementedError("VNSoundComponentTrait.get_sound_component() not implemented for " + type(self).__name__)

# ----------------------------------------------------------
# Basic types
# ----------------------------------------------------------
class VNValue(IRValue):
  pass

class VNInstruction(VNValue):
  pass

class VNStep(IROp):
  # each step is an "observation point" that user can Save/Load
  # we assume that a user can Save/Load at the boundary of steps
  # this is the finest control flow unit we can access by names
  # step can be terminator or not (branching to other blocks in the same function),
  # and step can be no-break or not (say if a step is VERY long, we may want to break it down so that users S/L after it won't have a VERY long replay)
  # step can have temporary values that does not hit storage, but the last use must be within the step
  # because no temporary value can pass the boundary of steps, we only use data phi within steps
  # if we need to pass scene components through phi, they are listed on the step instead of the terminating instructions 
  pass

class VNFunction(IROp):
  # unit of gameplay sharing and individual entry point
  pass

class VNThread(IROp):
  # highest unit of story line where there is a "per-saving" state. (Each game save file = state of a thread)
  pass

class VNNamespace(IROp):
  # hierarchical storage unit for output packaging. Child namespace can assume parent exist, but not its peers or children
  pass

# ----------------------------------------------------------
# Instructions
# ----------------------------------------------------------

# control flow

class VNJoinInst(VNInstruction):
  # takes multiple control input, output a single control value. output control dispatched when all inputs are executed
  pass

class VNSleepInst(VNInstruction):
  # take one control input, produce one control output that dispatches after a certain amount of time after the input are executed
  pass

class VNBreakInst(VNInstruction):
  # take one or more control input, wait for all inputs to be executed, and finish the current step.
  # no output because it is a terminator
  pass

class VNBranchInst(VNInstruction):
  # multi-destination terminator that branch to other basic blocks when given condition satisfied
  # no output because it is a terminator
  pass

# ----------------------------------------------------------
# Special steps
# ----------------------------------------------------------
class VNMenuStep(VNStep):
  # preserve the previous text/say content, show a menu and let user select
  # (the previous step is likely no-break)
  # The observation point is the time for selection
  # logically we can think of a menu step as:
  # 1. a blocking wait step for user selection, followed by
  # 2. a no-break step that consumes the selection result and do whatever needs to be done
  pass

class VNSwitchStep(VNStep):
  # execute one of the region, depending on the condition they are satisfied
  pass

class VNRandomActionStep(VNStep):
  # execute one of the region. The region is selected randomly.
  # (very low priority to implement...)
  pass
