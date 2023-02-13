# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
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

# we have three types of IRValue:
# 1. instruction. always available, local scope
# 2. assets. file based, not always available (we can have declarations only)
# 3. records. special data (position, transition effect, sayer info, etc), always available. ODR by default.
# we have symbol tables for (1) assets, and (2) functions

class VNInstruction(IROp):
  pass

class VNRecord(IROp):
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
  _name : str

  @property
  def name(self):
    return self._name
  
  def __init__(self) -> None:
    super().__init__()
    self._name = ""

class VNThread(IROp):
  # highest unit of story line where there is a "per-saving" state. (Each game save file = state of a thread)
  pass

class VNNamespace(IROp):
  # hierarchical storage unit for output packaging. Child namespace can assume parent exist, but not its peers or children
  _namespace: IRNamespaceIdentifier

  # we have the following regions defined: (during export they should be sorted)
  _functions : dict[str, VNFunction]
  _assets : dict[str, AssetBase]
  _records : dict[str, VNRecord]
  # symbol tables (including both internally defined and externally declared)
  _function_symbols : dict[str, IRSymbolTableEntry]
  _asset_symbols : dict[str, IRSymbolTableEntry]

  def __init__(self, ns : IRNamespaceIdentifier) -> None:
    super().__init__()
    self._namespace = ns
    self._functions = {}
    self._assets = {}
    self._records = {}
    self._function_symbols = {}
    self._asset_symbols = {}

  @property
  def namespace(self):
    return self._namespace
  
  def name(self) -> str:
    return self.namespace.to_string()
  
  def get_region_dict(self) -> typing.Dict[str, typing.Any]:
    return {
      "functions": self._functions.values(),
      "assets": self._assets.values(),
      "records": self._records.values()
    }
  
  def temp_add_function_nocheck(self, func : VNFunction):
    # only used when we are doing construction
    assert func.name not in self._functions
    self._functions[func.name] = func


class VNModel(IROp):
  # top-level object for VNModels
  # there is only one annonymous (name == "") region with a single block full of namespaces
  _namespaces : typing.Dict[IRNamespaceIdentifier, VNNamespace]

  def __init__(self) -> None:
    super().__init__()
    self._namespaces = {}
  
  @property
  def namespaces(self):
    return self._namespaces
  
  def add_namespace(self, ns : VNNamespace):
    assert ns.namespace not in self._namespaces
    self._namespaces[ns.namespace] = ns
  
  def get_region_dict(self) -> typing.Dict[str, typing.Any]:
    return {"": self._namespaces.values()}
  

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
