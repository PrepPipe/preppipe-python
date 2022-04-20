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
    if self == VNParsingStage.Initialization:
      return   VNParsingStage.MacroExpansion
    if self == VNParsingStage.MacroExpansion:
      return   VNParsingStage.GlobalSettingResolution
    if self == VNParsingStage.GlobalSettingResolution:
      return   VNParsingStage.EnvironmentResolution
    if self == VNParsingStage.EnvironmentResolution:
      return   VNParsingStage.FunctionBoundaryResolution
    if self == VNParsingStage.FunctionBoundaryResolution:
      return   VNParsingStage.AssetHandling
    if self == VNParsingStage.AssetHandling:
      return   VNParsingStage.CodeGeneration
    if self == VNParsingStage.CodeGeneration:
      return   VNParsingStage.Completed
    raise NotImplementedError("Unhandled parsing stage " + str(self))
  

# ------------------------------------------------------------------------------
# Temporary IROps etc for parsing
# ------------------------------------------------------------------------------

class VNPCommandOpBase(IROp):
  # base class for pending command handler calls
  handle_event_id : int # the index of handler call, used to tell the relative order of command handling.
  pass

@IROpDecl
class VNPParsedCommandOp(VNPCommandOpBase):
  # commands that the parser is responsible for setting up the operands
  pass

@IROpDecl
class VNPCustomParsedCommandOp(VNPCommandOpBase):
  # commands that the command will parse the operands from input
  pass

@IROpDecl
class VNPGenericBlockOp(IROp):
  # generic paragraph / block
  _block : IMBlock

  def __init__(self, block : IMBlock) -> None:
    super().__init__()
    self._block = block
  
  def to_string(self, indent=0) -> str:
    return self._block.to_string(indent)


@IROpDecl
class VNPGenericDocumentOp(VNFunction):
  # generic document op
  _document_name : str # name (without suffix) of the doc
  _content : typing.List[IROp] # [VNPParsedCommandOp, VNPCustomParsedCommandOp, VNPGenericBlockOp]
  
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
    # assert self.current_stage == VNParsingStage.Completed
    return self.model
  
  def _normalize_text_from_block(self, block: IMParagraphBlock):
    result = []
    last_str = ""
    for element in block.element_list:
      if isinstance(element, IMTextElement):
        # text element encountered
        last_str += element.text
      else:
        # non-text element encountered
        if len(last_str) > 0:
          result.append(last_str)
        last_str = ""
        result.append(element)
    if len(last_str) > 0:
      result.append(last_str)
    return result

  def _create_block_handle_command_block(self, block : IMParagraphBlock, body : list) -> IROp:
    # TODO handle non-text elements in command block
    assert len(body) == 1
    full_str : str = body[0]
    # TODO actually do the parsing
    # find substr in self._cls_command_name_suffix (which should contain all variants of ':') or whitespace to extract the command name
    # lookup the input parsing requirement, if it requires custom parsing then we are done
    # otherwise we parse all the parameters and populate the result op
    # print("Command found: "+full_str)
    return VNPGenericBlockOp(block)

  def _create_block(self, block : IMBlock) -> IROp:
    # if we can parse the text block as a command block, return a command block
    # otherwise just treat as a generic block
    if isinstance(block, IMParagraphBlock):
      if block.paragraph_type == IMSpecialParagraphType.Regular:
        contents = self._normalize_text_from_block(block)
        if len(contents) > 0 and isinstance(contents[0],str):
          if len(contents) == 1:
            # single string paragraph
            content_str : str = contents[0].strip()
            isStartMatch = content_str.startswith(self._cls_command_start)
            isEndMatch = content_str.endswith(self._cls_command_end)
            if isStartMatch and isEndMatch:
              # we found a command paragraph
              # try to get the command name
              start_pos = 0
              for start in self._cls_command_start:
                if content_str.startswith(start):
                  start_pos = len(start)
                  break
              assert start_pos > 0
              end_pos = len(content_str)
              for end in self._cls_command_end:
                if content_str.endswith(end):
                  end_pos -= len(end)
                  break
              return self._create_block_handle_command_block(block, [content_str[start_pos:end_pos]])
            elif isStartMatch or isEndMatch:
              # either the beginning or end is missing
              MessageHandler.warning("ParagraphBlock has command start/end symbol but not considered as command")
          else:
            # front_str : str = contents[0].lstrip()
            # TODO unimplemented
            raise NotImplementedError("We cannot handle non-text element in command block yet")
        elif len(contents) > 0:
          # the first element is not text
          # we may have images, etc as the first element that could block our search of commands
          # if the first text element starts with a command start symbol, we create a warning
          first_text_element_idx = 0
          for i in range(len(contents)):
            if isinstance(contents[i], str):
              first_text_element_idx = i
              break
          if first_text_element_idx > 0:
            first_text = content_str[first_text_element_idx].lstrip()
            if first_text.startswith(self._cls_command_start):
              MessageHandler.warning("ParagraphBlock has leading non-text element before command start/end symbol; command (if present) will not be parsed")


    return VNPGenericBlockOp(block)

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
        for imb in imdoc.blocks:
          block = self._create_block(imb)
          doc.add(block)

    self.current_stage = self.current_stage.next()

  def _run_macro_expansion(self):
    pass

  def run_to_stage(self, stage : VNParsingStage) -> None:
    assert self.current_stage.value <= stage.value
    while self.current_stage.value <= stage.value and self.current_stage.value < VNParsingStage.Completed.value:
      # TODO use python 3.10 pattern matching instead
      if self.current_stage == VNParsingStage.Initialization:
        self._run_initialization()
        return
      

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
def cmd_Comment(ctx : VNParserContext, input : CustomParseParameterType) -> None:
  return

@frontendcommand(ParserType=VNParser, stage=VNParsingStage.FunctionBoundaryResolution, command="Label", command_alias=["标签"])
def cmd_Label(ctx: VNParserContext, name: str) -> None:
  return


