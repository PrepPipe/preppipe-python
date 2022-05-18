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
  
# ------------------------------------------------------------------------------
# helper types
# ------------------------------------------------------------------------------
class VNPBlockBase:
  # wrapper for IMBlock in VNParser
  _block : IMBlock

  def __init__(self, block : IMBlock) -> None:
    super().__init__()
    self._block = block

  def to_string(self, indent=0) -> str:
    return self._block.to_string(indent)

class VNPParagraphBlock(VNPBlockBase):
  # this is basically a parsed version of an IMParagraphBlock
  # all non-text elements are collected separately and we have a uniformed string representation in "text"
  # these non-text elements are replaced by "element_replacement_symbol" inside the "text", and "element_replacement_symbol" is guaranteed not to clash with existing contents
  # for implementation ease, non-text elements before the first piece of text or after the last piece of text will not have replacement symbol in the text
  # if there is no non-text elements, "element_replacement_symbol" will be empty
  # text is strip()ed and will not have leading/trailing whitespaces
  _text : str
  _element_replacement_symbol : str
  _nontext_elements_intext : typing.List[IMElement]
  _nontext_elements_beforetext : typing.List[IMElement]
  _nontext_elements_aftertext : typing.List[IMElement]

  def __init__(self, block: IMParagraphBlock, text : str, element_replacement_symbol: str, nontext_elements_intext : typing.List[IMElement], nontext_elements_beforetext : typing.List[IMElement], nontext_elements_aftertext : typing.List[IMElement]) -> None:
    super().__init__(block)
    self._text = text
    self._element_replacement_symbol = element_replacement_symbol
    self._nontext_elements_intext = nontext_elements_intext
    self._nontext_elements_beforetext = nontext_elements_beforetext
    self._nontext_elements_aftertext = nontext_elements_aftertext

  @property
  def text(self):
    return self._text

  @property
  def element_replacement_symbol(self):
    return self._element_replacement_symbol

  @property
  def nontext_elements_intext(self):
    return self._nontext_elements_intext

  @property
  def nontext_elements_beforetext(self):
    return self._nontext_elements_beforetext

  @property
  def nontext_elements_aftertext(self):
    return self._nontext_elements_aftertext

  @staticmethod
  def create(block: IMParagraphBlock):
    # step 1: from beginning to end, find the first text element with non-whitespace content
    pos_first_text = 0
    first_text : str = ""
    elements_beforetext : typing.List[IMElement] = []
    for i in range(len(block.element_list)):
      element = block.element_list[i]
      if isinstance(element, IMTextElement):
        first_text = element.text.lstrip()
        if len(first_text) > 0:
          pos_first_text = i
          break
      else:
        elements_beforetext.append(element)

    if len(first_text) == 0:
      # this block has no non-empty text elements
      # all elements are considered in text
      return VNPParagraphBlock(block, text="", element_replacement_symbol="", nontext_elements_intext=elements_beforetext, nontext_elements_beforetext=[], nontext_elements_aftertext=[])

    # step 2: from end to beginning, find the last text element with non-whitespace content
    pos_last_text = 0
    last_text : str = ""
    elements_aftertext : typing.List[IMElement] = []
    for i in range(len(block.element_list), 0, -1):
      idx = i-1
      element = block.element_list[idx]
      if isinstance(element, IMTextElement):
        if idx == pos_first_text:
          # only a single non-empty text element
          text = first_text.rstrip()
          return VNPParagraphBlock(block, text, element_replacement_symbol="", nontext_elements_intext=[], nontext_elements_beforetext=elements_beforetext, nontext_elements_aftertext=elements_aftertext)
        else:
          last_text = element.text.rstrip()
          if len(last_text) > 0:
            pos_last_text = idx
            break
      else:
        elements_aftertext.append(element)

    # step 3: separate text elements from other elements in the middle
    # consecutive text elements are concatenated
    assert pos_last_text > pos_first_text
    text_list : typing.List[str] = [first_text]
    elements_intext : typing.List[IMElement] = []
    pending_str : str | None = None
    for i in range(pos_first_text+1, pos_last_text, 1):
      element = block.element_list[i]
      if isinstance(element, IMTextElement):
        if pending_str is None:
          pending_str = element.text
        else:
          pending_str += element.text
      else:
        elements_intext.append(element)
        # if there are multiple elements back to back, we need to insert empty strings
        # so that correct number of replacement symbols appear in output string
        if pending_str is None:
          text_list.append("")
        else:
          text_list.append(pending_str)
          pending_str = None
    if pending_str is not None:
      text_list.append(pending_str + last_text)
    else:
      text_list.append(last_text)

    # step 4: determine the symbol for non-text elements
    # the string must not be a substring of any one in the text_list
    # we always use <E> as baseline, then add characters ('-' for now) between 'E' and '>' to avoid collisions
    max_len = 0
    for s in text_list:
      max_len = max(max_len, len(s))

    replacememt_symbol = ""
    for i in range(max_len):
      replacememt_symbol = "<E" + "-"*i + ">"
      hasCollision = False
      for s in text_list:
        if s.find(replacememt_symbol) >= 0:
          hasCollision = True
          break
      if not hasCollision:
        break

    # done!
    return VNPParagraphBlock(block, text=replacememt_symbol.join(text_list), element_replacement_symbol=replacememt_symbol, nontext_elements_intext=elements_intext, nontext_elements_beforetext=elements_beforetext, nontext_elements_aftertext=elements_aftertext)

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
class VNPUnknownCommandOp(VNPCommandOpBase):
  # commands that are not recognized
  pass

@IROpDecl
class VNPBadCallCommandOp(VNPCommandOpBase):
  # commands that are recognized but the parameter parsing failed
  pass


@IROpDecl
class VNPGenericBlockOp(IROp):
  # generic paragraph / block
  _block : VNPBlockBase

  def __init__(self, block : VNPBlockBase) -> None:
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
    assert self.current_stage == VNParsingStage.Completed
    return self.model

  def _create_blocks_handle_command_block(self, command_info : ParsedCommandInfo) -> IROp:
    raise NotImplementedError("_create_blocks_handle_command_block not implemented yet")

  def _create_blocks(self, block : IMBlock) -> typing.List[IROp]:
    # if we can parse the text block as commands, return a list of command block
    # otherwise just treat as a generic block
    blockwrap : VNPBlockBase = None
    if isinstance(block, IMParagraphBlock):
      blockwrap = VNPParagraphBlock.create(block)
      assert isinstance(blockwrap, VNPParagraphBlock)
      if block.paragraph_type == IMSpecialParagraphType.Regular and len(blockwrap.text) > 0:
        content_str = blockwrap.text
        command_scan_result = self.scanCommandFromText(content_str)
        if command_scan_result is not None:
          result_list = []
          for command_info in command_scan_result:
            command_op = self._create_blocks_handle_command_block(command_info)
            result_list.append(command_op)
          return result_list
    if blockwrap is None:
      blockwrap = VNPBlockBase(block)
    return [VNPGenericBlockOp(blockwrap)]

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
          blocklist = self._create_blocks(imb)
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
  

# comment not implemented yet
@frontendcommand(ParserType=VNParser, stage=VNParsingStage.MacroExpansion, command="Comment", command_alias=["注释"], custom_command_parsing=True)
def cmd_Comment(ctx : VNParserContext, input : CustomParseParameterType) -> None:
  return

@frontendcommand(ParserType=VNParser, stage=VNParsingStage.FunctionBoundaryResolution, command="Label", command_alias=["标签"])
def cmd_Label(ctx: VNParserContext, name: str) -> None:
  return


