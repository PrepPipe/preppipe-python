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
  MacroExpansion = enum.auto() # just a place holder; we do not support macro expansion for now
  GlobalSettingResolution = enum.auto() # handle all commands that affect the parsing globally (at least file scope)
  EnvironmentResolution = enum.auto() # break each document into different environment blocks to feed to different "sub"parser
  FunctionBoundaryResolution = enum.auto() # decide the boundary of functions
  AssetHandling = enum.auto() # handle all commands that transform / declare assets. all asset references should be updated after this stage. Should handle dependencies between assets
  CodeGeneration = enum.auto() # handle all commands local in each function. (auto-parallel)
  # declare macro expansion and comment commands with MacroExpansion stage
  # declare global options (e.g. default parsing mode, etc) in global setting resultion stage
  # declare custom environment commands and parsing option commands in environment resolution stage
  # declare commands that determine the start/end of functions in function boundary resolution stage
  # declare asset-related commands in asset handling stage
  # declare all rest of commands in CodeGeneration stage
  

class VNParser(ParserBase):
  def __init__(self) -> None:
    super().__init__()
  
  def add(self, model : InputModel) -> None:
    # populate MLIR-like IR in this stage
    pass
  def get_result(self) -> VNModel:
    pass
  def run_to_stage(self, stage : VNParsingStage) -> None:
    pass
  def run(self) -> None:
    # run all the stages
    self.run_to_stage(VNParsingStage.CodeGeneration)

  @staticmethod
  def parse(model: InputModel) -> VNModel:
    parser : VNParser = VNParser()
    parser.add(model)
    return parser.get_result()
  

# comment not implemented yet
@frontendcommand(ParserType=VNParser, stage=VNParsingStage.MacroExpansion, command="Comment", command_alias=["注释"], custom_command_parsing=True)
def cmd_Comment(ctx : ParseContextBase) -> None:
  return

@frontendcommand(ParserType=VNParser, stage=VNParsingStage.FunctionBoundaryResolution, command="Label", command_alias=["标签"])
def cmd_Label(ctx: ParseContextBase, name: str) -> None:
  return


