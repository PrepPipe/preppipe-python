#!/usr/bin/env python3

import typing
import PIL.Image
from enum import Enum
import re

import preppipe.commontypes
from preppipe.vnmodel import *

class EngineSupport:
  """All engine support classes inherit this class, so that we can use reflection to query all supported engines"""
  pass

# we define an MIR infrastructure for backend... Engine Model (EM)

class EMInstruction:
  
  # abstract opcode data
  opcode : typing.Any
  
  # list of operands
  operand_list : typing.List[typing.Any] = []
  
  def __init__(self, opcode, operand_list : typing.List[typing.Any] = []) -> None :
    self.opcode = opcode
    if len(operand_list) == 0:
      self.operand_list = []
    else:
      self.operand_list = operand_list
  
  def set_operand_list(self, operand_list : typing.List[typing.Any]) -> None:
    self.operand_list = operand_list
  
  def add_operand(self, operand : typing.Any) -> None:
    self.operand_list.append(operand)
  
  def get_num_operands(self):
    return len(self.operand_list)
  
  def get_operand(self, index : int) -> typing.Any:
    return self.operand_list[index]

  def get_opcode(self) -> typing.Any:
    return self.opcode
  
  def get_operand_dict(self, arglist : typing.List[str]) -> typing.Dict[str, typing.Any]:
    assert(len(arglist) == len(self.operand_list))
    result : typing.Dict[str, typing.Any] = {}
    for i in range(0, len(self.operand_list)):
      result[arglist[i]] = self.operand_list[i]
    return result
    

class EMBasicBlock:
  
  label : str = ""
  instr_list : typing.List[EMInstruction] = []
  
  def __init__(self, label : str = "") -> None :
    self.label = label
    self.instr_list = []
  
  def add_instruction(self, instr : EMInstruction) -> EMInstruction:
    self.instr_list.append(instr)
    return instr
  
  def get_instruction_list(self) -> typing.List[EMInstruction]:
    return self.instr_list
  
  def get_label(self) -> str:
    return self.label

class EMFunction:
  """It is fine if left unused; not all engines support functions"""
  basicblock_list : typing.List[typing.Any] = []
  
  def __init__(self) -> None :
    self.basicblock_list = []
  
  def add_basicblock(self, bb : typing.Any):
    self.basicblock_list.append(bb)
    return bb
  

# helper functions

def _get_label_name(name : str, type_prefix : str, scope_prefix: str, name_dict : typing.Dict[str, typing.Any], prefix : str = "") -> str:
  # get the base name
  base_label = re.sub(r'[^a-zA-Z0-9_]', '', name.replace(" ", "_"))
  
  # ensure the name does not start with number or underscore, or is not empty
  if len(base_label) > 0:
    frontchar = base_label[0]
    if frontchar == '_' or frontchar.isnumeric():
      base_label = type_prefix + "_" + base_label
  else:
    # we have no alphanumetic characters
    base_label = type_prefix + "_anon"
  
  # make sure it is unique
  # we may have duplicates
  
  # try to add scope prefix to resolve this
  if prefix + base_label in name_dict and len(scope_prefix) > 0:
    base_label = scope_prefix + "_" + base_label
  
  # now add the prefix; we no longer add prefix to base label
  if len(prefix) > 0:
    base_label = prefix + base_label
  
  # if not working, add a numeric suffix
  numeric_suffix = 0
  result = base_label
  while result in name_dict:
    numeric_suffix += 1
    result = base_label + '_' + str(numeric_suffix)
  
  # done
  return result

def label_branch_targets(model : VNModel, reserved_set : typing.Set[str] = [], include_basicblock : bool = True) -> typing.Dict[VNValue, str]:
  """Assign all functions (and optionally basic blocks) with a label that is:
  1. alphanumeric, non-empty
  2. does not start with underscore '_'
  3. unique across all functions and basic blocks
  
  We may need this labeling even when functions already has no duplicated label so avoid sanitization issue or reserved keywords
  """
  name_dict = {} # label -> element (used internally)
  elem_dict = {} # element -> label (for returning)
  
  # add all reserved keywords to name_dict
  for reserved in reserved_set:
    assert isinstance(reserved, str)
    name_dict[reserved] = None
  
  # actual work
  for func in model.get_function_list():
    func_label = _get_label_name(func.get_name(), "control_label", "", name_dict)
    name_dict[func_label] = func
    elem_dict[func] = func_label
    if include_basicblock:
      for bb in func.get_basicblock_list():
        bbname = bb.get_name()
        if len(bbname) == 0 and bb is func.get_entry_block():
          bbname = "entry"
        bb_label = _get_label_name(bbname, "control_label", func_label, name_dict)
        name_dict[bb_label] = bb
        elem_dict[bb] = bb_label
  
  return elem_dict

def label_basicblocks(func : VNFunction, reserved_set : typing.Set[str] = []) -> typing.Dict[VNBasicBlock, str]:
  """Assign labels to basic blocks with the same criteria as label_branch_targets:
  
  1. alphanumeric, non-empty
  2. does not start with underscore '_'
  3. unique
  """
  name_dict = {} # label -> element (used internally)
  elem_dict = {} # element -> label (for returning)
  
  # add all reserved keywords to name_dict
  for reserved in reserved_set:
    assert isinstance(reserved, str)
    name_dict[reserved]= None
    
  for bb in func.get_basicblock_list():
    bbname = bb.get_name()
    if len(bbname) == 0 and bb is func.get_entry_block():
      bbname = "entry"
    bb_label = _get_label_name(bbname, "label", "", name_dict, ".")
    name_dict[bb_label] = bb
    elem_dict[bb] = bb_label
  
  return elem_dict

def label_sayer_identity(model : VNModel, reserved_set : typing.Set[str] = []) -> typing.Dict[str, str]:
  """make sure all characters and sayers have (alphanumeric) labels"""
  name_dict = {}
  elem_dict = {}
  for reserved in reserved_set:
    assert isinstance(reserved, str)
    name_dict[reserved] = None
  for character in model.get_character_list():
    name = _get_label_name(character.get_name(), "character", "", name_dict)
    name_dict[name] = character
    elem_dict[character] = name
  for sayer in model.get_sayer_list():
    character = sayer.get_identity()
    character_label = elem_dict[character]
    name = _get_label_name(character_label + sayer.get_name(), "sayer", "", name_dict)
    name_dict[name] = sayer
    elem_dict[sayer] = name
  return elem_dict
  