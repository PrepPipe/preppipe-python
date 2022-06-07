# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0


import os
import io
import pathlib
import typing
import PIL.Image
import pydub
import pathlib
import functools
import enum

from ..parser import *
from ...vnmodel_v2 import *
from ...inputmodel import *

class VNParsingStage(enum.Enum):
  # in the order of performing
  # only the CodeGeneration stage can be parallelized within a namespace
  Initialization = enum.auto() # no command should be in this stage
  MacroExpansion = enum.auto() # just a place holder; we do not support macro expansion for now
  GlobalSettingResolution = enum.auto() # handle all commands that affect the parsing globally (at least file scope)
  EnvironmentResolution = enum.auto() # break each document into different environment blocks to feed to different "sub"parser
  FunctionBoundaryResolution = enum.auto() # decide the boundary of functions. run this stage before the rest so that we have more detailed debug location for later stages
  AssetHandling = enum.auto() # handle all commands that transform / declare assets. all asset references should be updated after this stage. Should handle dependencies between assets
  CodeGeneration = enum.auto() # handle all commands local in each function. (auto-parallel)
  Completed = enum.auto()
  # declare macro expansion and comment commands with MacroExpansion stage
  # declare global options (e.g. default parsing mode, etc) in global setting resultion stage
  # declare custom environment commands and parsing option commands in environment resolution stage
  # declare commands that determine the start/end of functions in function boundary resolution stage
  # declare asset-related commands in asset handling stage
  # declare all rest of commands in CodeGeneration stage

  def next(self):
    match self:
      case VNParsingStage.Initialization:
        return VNParsingStage.MacroExpansion
      case VNParsingStage.MacroExpansion:
        return VNParsingStage.GlobalSettingResolution
      case VNParsingStage.GlobalSettingResolution:
        return VNParsingStage.EnvironmentResolution
      case VNParsingStage.EnvironmentResolution:
        return VNParsingStage.FunctionBoundaryResolution
      case VNParsingStage.FunctionBoundaryResolution:
        return VNParsingStage.AssetHandling
      case VNParsingStage.AssetHandling:
        return VNParsingStage.CodeGeneration
      case VNParsingStage.CodeGeneration:
        return VNParsingStage.Completed
      case _:
        raise NotImplementedError("Unhandled parsing stage " + str(self))

@IROpDecl
class VNPGenericDocumentOp(VNFunction):
  # generic document op
  _document_name : str # name (without suffix) of the doc
  _content : typing.List[IROp]
  
  def __init__(self, document_name : str) -> None:
    super().__init__()
    self._document_name = document_name
    self._content = []
  
  def add(self, item : IROp):
    self._content.append(item)
  
  def name(self):
    return self._document_name
  
  def get_region_dict(self) -> typing.Dict[str, typing.Any]:
    return {
      "": self._content
    }


# ------------------------------------------------------------------------------
# VNParser class
# ------------------------------------------------------------------------------

class VNParserContext(ParseContextBase):
  pass

class VNParser(ParserBase):
  model : VNModel
  input : InputModel
  current_stage : VNParsingStage
  def __init__(self) -> None:
    super().__init__()
    self.model = VNModel()
    self.input = None
    self.current_stage = VNParsingStage.Initialization
  
  def add(self, model : InputModel) -> None:
    # populate MLIR-like IR in this stage
    assert self.current_stage == VNParsingStage.Initialization
    if self.input is None:
      self.input = model
    else:
      self.input.merge_with(model)

  def get_result(self) -> VNModel:
    # TODO finalize
    assert self.current_stage == VNParsingStage.Completed
    return self.model

  def _run_initialization(self):
    # populate MLIR-like IR in this stage
    assert self.input is not None
    assert self.current_stage == VNParsingStage.Initialization

    for nsID, inputNS in self.input.namespaces.items():
      ns = VNNamespace(nsID)
      self.model.add_namespace(ns)
      # TODO add assets first
      for name, imdoc in inputNS.fileset.items():
        doc = VNPGenericDocumentOp(name)
        ns.temp_add_function_nocheck(doc)
        blocklist = self.parse_blocks(imdoc.blocks)
        for block in blocklist:
          doc.add(block)
    # use the next() method to update current stage so that we can add stages in a simpler manner
    self.current_stage = self.current_stage.next()

  def _run_macro_expansion(self):
    assert self.current_stage == VNParsingStage.MacroExpansion
    # use the next() method to update current stage so that we can add stages in a simpler manner
    self.current_stage = self.current_stage.next()

  def _run_global_setting_resolution(self):
    assert self.current_stage == VNParsingStage.GlobalSettingResolution
    # use the next() method to update current stage so that we can add stages in a simpler manner
    self.current_stage = self.current_stage.next()

  def _run_environment_resolution(self):
    assert self.current_stage == VNParsingStage.EnvironmentResolution
    # use the next() method to update current stage so that we can add stages in a simpler manner
    self.current_stage = self.current_stage.next()

  def _run_function_boundary_resolution(self):
    assert self.current_stage == VNParsingStage.FunctionBoundaryResolution
    # use the next() method to update current stage so that we can add stages in a simpler manner
    self.current_stage = self.current_stage.next()

  def _run_asset_handling(self):
    assert self.current_stage == VNParsingStage.AssetHandling
    # use the next() method to update current stage so that we can add stages in a simpler manner
    self.current_stage = self.current_stage.next()

  def _run_code_generation(self):
    assert self.current_stage == VNParsingStage.CodeGeneration
    # use the next() method to update current stage so that we can add stages in a simpler manner
    self.current_stage = self.current_stage.next()

  def run_to_stage(self, stage : VNParsingStage) -> None:
    assert self.current_stage.value <= stage.value
    while self.current_stage.value <= stage.value:
      match self.current_stage:
        case VNParsingStage.Initialization:
          self._run_initialization()
          continue
        case VNParsingStage.MacroExpansion:
          self._run_macro_expansion()
          continue
        case VNParsingStage.GlobalSettingResolution:
          self._run_global_setting_resolution()
          continue
        case VNParsingStage.EnvironmentResolution:
          self._run_environment_resolution()
          continue
        case VNParsingStage.FunctionBoundaryResolution:
          self._run_function_boundary_resolution()
          continue
        case VNParsingStage.AssetHandling:
          self._run_asset_handling()
          continue
        case VNParsingStage.CodeGeneration:
          self._run_code_generation()
          continue
        case VNParsingStage.Completed:
          # we are done if we reach here
          break
        case _:
          raise NotImplementedError("Unknown parsing stage " + str(self.current_stage))

  def run(self) -> None:
    # run all the stages
    self.run_to_stage(VNParsingStage.CodeGeneration)

  @staticmethod
  def parse(model: InputModel) -> VNModel:
    parser : VNParser = VNParser()
    parser.add(model)
    return parser.get_result()




_rh : FrontendCommandRegisterHelper = FrontendCommandRegisterHelper(VNParser)
_rh.add_common_alias_dict({
  "name": ['名称']
})
_rh.set_stage(VNParsingStage.Initialization)
_rh.set_stage(VNParsingStage.MacroExpansion)
_rh.set_stage(VNParsingStage.GlobalSettingResolution)
_rh.set_stage(VNParsingStage.EnvironmentResolution)
_rh.set_stage(VNParsingStage.FunctionBoundaryResolution)

@register(_rh, "Label", ["标签"])
def cmd_label(_ctx : VNParserContext, name : str) -> None:
  pass

_rh.set_stage(VNParsingStage.AssetHandling)
_rh.set_stage(VNParsingStage.CodeGeneration)

del _rh


