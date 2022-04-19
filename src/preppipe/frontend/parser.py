# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0


import os
import io
import pathlib
import typing
import PIL.Image
from matplotlib.pyplot import annotate
from numpy import empty
import pydub
import pathlib
import functools
import inspect
import string
import enum
from enum import Enum

from preppipe.inputmodel import IMParagraphBlock

from ..commontypes import *
from ..util import *

# a context object for commands handling
# Derive from this class and implement at least these functions
# probably include a reference to the parent parser object as well
class ParseContextBase:
  def get_file_string(self) -> str:
    raise NotImplementedError("ParseContextBase.get_file_string() not implemented for " + type(self).__name__)
  
  def get_location_string(self) -> str:
    raise NotImplementedError("ParseContextBase.get_location_string() not implemented for " + type(self).__name__)
  
  def get_message_loc(self) -> typing.Tuple[str, str]:
    return (self.get_file_string(), self.get_location_string())

# base class for parser(s) taking InputModel as input (only VNModel parser for now)
class ParserBase:
  # class variables for commands registration
  # in the constructor, these registry will be COPIED to instances
  _cls_registered_parse_commands : typing.ClassVar[typing.List] = [] # list of CommandInfo
  _cls_command_alias_dict : typing.ClassVar[typing.Dict[str, int]] = {} # map from command alias names (including canonical names) to string
  
  # instance / member variables (copy of _cls*)
  _registered_parse_commands : typing.List[typing.Any] = [] # list of CommandInfo
  _command_alias_dict : typing.Dict[str, int] # map from command alias names (including canonical names) to string
  
  def __init__(self) -> None:
    super().__init__()
    self._registered_parse_commands = self._cls_registered_parse_commands.copy()
    self._command_alias_dict = self._cls_command_alias_dict.copy()
    
  
  def invoke(self, command : str, ctx : ParseContextBase, *args, **kwargs):
    # the caller is expected to catch exception if the invocation failed
    if command in self._command_alias_dict:
      # command found; try to invoke
      # we should have already checked the signature of the callback
      info : CommandInfo = self._registered_parse_commands[self._command_alias_dict[command]]
      
      # for arguments in the kwargs, if they are from an alias, convert them to the canonical name
      new_kwargs = {}
      for param, value in kwargs.items():
        # if the param is using the canonical name, just add to new_kwargs
        # if not, try to convert to canonical name
        # if the param name is not found, generate a warning
        
        if param in info._kwarg_rename_dict:
          new_kwargs[info._kwarg_rename_dict[param]] = value
        else:
          # this parameter is not recognized and will be dropped
          # print a warning and suggest alternatives with minimal edit distance
          suggest = TypoSuggestion(param)
          
          for name in info._kwarg_rename_dict.keys():
            suggest.add_candidate(name)
          
          file = ""
          loc = ""
          if ctx is not None:
            file = ctx.get_file_string()
            loc = ctx.get_location_string()
          MessageHandler.warning("Unknown parameter \"" + param + "\" for command \"" + command + "\"; suggested alternative(s): [" + ",".join(suggest.get_result()) + "]", file, loc)
      
      # new_kwargs ready
      return info._func(ctx, *args, **new_kwargs)
    
    # if the execution reaches here, the command is not found
    suggest = TypoSuggestion(command)
    suggest.add_candidate(self._command_alias_dict.keys())
    results = suggest.get_result()
    file = ""
    loc = ""
    if ctx is not None:
      file = ctx.get_file_string()
      loc = ctx.get_location_string()
    MessageHandler.critical_warning("Unknown command \"" + command + "\"; suggested alternative(s): [" + ",".join(results) + "]", file, loc)
    return None


class KeywordArgumentInfo(typing.NamedTuple):
  canonical_name : str
  aliases : typing.List[str]
  annotation : type
  required : bool

class CustomParseParameterType(typing.NamedTuple):
  command_block: IMParagraphBlock # the command block that this command have

  # position of the first unparsed text (leading whitespace stripped)
  element_index: int # index to the element
  character_index: int # index to the (first unparsed) text

class CommandInfo:
  class CustomParsingParameterOption(enum.Enum):
    NotCustomParsing = enum.auto()
    Full = enum.auto() # parameter is CustomParseParameterType
    PlainText = enum.auto() # parameter is str

  # data members
  # ones from input
  _func : callable
  _command : str # canonical (english) name
  _command_alias : typing.List[str] # list of (non-english) name of command
  # these are built upon construction
  _kwarg_rename_dict : typing.Dict[str, str] # (non-)canonical name -> canonical name; canonical names are also included
  _kwargs_info : typing.List[KeywordArgumentInfo]
  _positional_type : type # None if not taking positional arguments, the type if it takes. This can be typing.Any.
  _stage: typing.Any # when the commands are supposed to be executed
  _custom_parsing_parameter_option : CustomParsingParameterOption
  
  def __init__(self, func : callable, command : str, command_alias : typing.List[str], kwarg_rename_dict : typing.Dict[str, str], kwargs_info : typing.List[KeywordArgumentInfo], positional_type : type, stage: typing.Any, *, custom_parsing_parameter_option : CustomParsingParameterOption = CustomParsingParameterOption.NotCustomParsing) -> None:
    self._func = func
    self._command = command
    self._command_alias = command_alias
    self._kwarg_rename_dict = kwarg_rename_dict
    self._kwargs_info = kwargs_info
    self._positional_type = positional_type
    self._stage = stage
    self._custom_parsing_parameter_option = custom_parsing_parameter_option
  
  @staticmethod
  def _is_type_annotation_supported(ty : type) -> bool:
    return True

  @staticmethod
  def _do_register_command(result_info, ParserType: type, command : str, command_alias : typing.List[str]):
    assert inspect.isclass(ParserType) and issubclass(ParserType, ParserBase)
    index = len(ParserType._cls_registered_parse_commands)
    ParserType._cls_registered_parse_commands.append(result_info)
    ParserType._cls_command_alias_dict[command] = index
    for alias in command_alias:
      ParserType._cls_command_alias_dict[alias] = index
  
  @staticmethod
  def _register_custom_parsing_command(func: callable, command : str, command_alias : typing.List[str], ParserType: type, stage: typing.Any):
    # registration of commands that require custom parsing (after the command name is handled)
    # example commands requiring custom parsing: comment ("[Comment: xxx]"), expression evaluation ("[Expression hp-1]")
    # beside the parse context, we expect the function callable to take one of the following set of parameters:
    # 1. single str: we will call the function with all the text element converted to str (discarding all styles and non-text elements)
    # 2. CustomParseParameterType: we call the function with full details populated in the struct
    # reminder that command registration should not fault
    assert inspect.isclass(ParserType) and issubclass(ParserType, ParserBase)
    sig = inspect.signature(func)
    error_list = [] # list of error strings
    if len(sig.parameters) != 2:
      err = "Registering command \"" + command + "\" with custom parsing: unexpected number of parameters (should be 2 instead of "+ str(len(sig.parameters))+ ")"
      error_list.append(err)
    
    isPlainTextArg = False
    numParamParsed = 0
    
    for param in sig.parameters.values():
      numParamParsed += 1
      if numParamParsed == 1:
        # this is the context parameter
        # we check that if its type is annotated, it should be subclass of parse context
        if param.annotation != inspect.Parameter.empty:
          if not isinstance(param.annotation, ParseContextBase):
            err = "Context parameter \"" + param.name + "\" annotated with type " + str(param.annotation) + ", not derived from ParseContextBase"
            error_list.append(err)
      elif numParamParsed == 2:
        # if we have type annotation, make sure it is either str or CustomParseParameterType
        if param.annotation != inspect.Parameter.empty:
          if isinstance(param.annotation, str):
            isPlainTextArg = True
          elif isinstance(param.annotation, CustomParseParameterType):
            isPlainTextArg = False
          else:
            err = "Raw text parameter \"" + param.name + "\" annotated with type " + str(param.annotation) + ", not in [str, CustomParseParameterType]"
            error_list.append(err)
    
    # check whether there is a name clash
      if command in ParserType._cls_command_alias_dict:
        error_list.append("Command \"" + command + "\" is already declared")
      else:
        # we only check aliases if the canonical name is available
        # (if the canonical name is in use, the aliases are likely also in use)
        for alias in command_alias:
          if alias in ParserType._cls_command_alias_dict:
            error_list.append("Alias \"" + alias + "\" is already in use")
    
    if len(error_list) > 0:
      MessageHandler.critical_warning("Registering handler for command \"" + command + "\" failed:\n  " + "\n  ".join(error_list))
      return
    
    custom_parsing_parameter_option = CommandInfo.CustomParsingParameterOption.PlainText if isPlainTextArg else CommandInfo.CustomParsingParameterOption.Full
    result_info = CommandInfo(func, command, command_alias, {}, [], None, stage, custom_parsing_parameter_option=custom_parsing_parameter_option)
    CommandInfo._do_register_command(result_info, ParserType, command, command_alias)
    return
  
  @staticmethod
  def _register(func : callable, command : str, command_alias : typing.List[str], parameter_alias : typing.Dict[str, typing.List[str]], kwargs_decl : typing.Dict[str, typing.List[str]], ParserType: type, stage: typing.Any, *, custom_command_parsing : bool = False):
    # if there is a validation problem, we generate an error message and do nothing, instead of possibly crashing
    # (will be annoying if importing library causing crashing)
    
    # ParserType: class object of the parser (should be derived from ParserBase)
    # stage: a (parser-defined) value indicating when should the command be evaluated
    assert inspect.isclass(ParserType) and issubclass(ParserType, ParserBase)
    
    # special case handling first
    if custom_command_parsing:
      # warn when not used
      if len(parameter_alias) > 0 or len(kwargs_decl) > 0:
        MessageHandler.warning("Registering command \"" + command + "\" with custom parsing: parameter_alias and/or kwargs_decl specified but ignored")
      return CommandInfo._register_custom_parsing_command(func, command, command_alias, ParserType, stage)
    
    error_list = [] # list of error strings
    result_info : CommandInfo = None
    
    # check if the entry is valid
    # use a loop that only loop once so that we can "break" to outside
    # because we want to test as many conditions as possible, we do not "break" unless the error-checking cannot proceed
    while True:
      if not callable(func):
        error_list.append("argument not a callable")
        break
      
      sig = inspect.signature(func)
      kwargs_info : typing.List[KeywordArgumentInfo] = []
      kwarg_rename_dict : typing.Dict[str, str] = {}
      positional_type : type = None
      
      # for error checking
      named_args : typing.Set[str] = set()
      var_positional_name : str = ""
      
      def is_name_valid(name : str):
        if len(name) == 0:
          return False
        if name[0] in string.whitespace or name[-1] in string.whitespace:
          return False
        return True
      
      def add_kwarg_mapping(fromname : str, toname : str):
        nonlocal kwarg_rename_dict
        if not is_name_valid(fromname):
          error_list.append("Parameter name invalid: \"" + fromname + "\"")
          return
        if fromname in kwarg_rename_dict:
          existing_cname = kwarg_rename_dict.get(fromname)
          if existing_cname == toname:
            error_list.append("Duplicated parameter name mapping: \"" + fromname + "\" -> \"" + toname + "\"")
            return
          error_list.append("Conflicting parameter name mapping: \"" + fromname + "\" -> [\"" + existing_cname + "\", \"" + toname + "\"]")
          return
        kwarg_rename_dict[fromname] = toname
      
      # build the kwargs list
      # the first parameter of func should be the context object, and it should not be included in the kwargs list
      isFirstIteration = True
      for param in sig.parameters.values():
        if isFirstIteration:
          isFirstIteration = False
          # we also check that if its type is annotated, it should be subclass of parse context
          if param.annotation != inspect.Parameter.empty:
            if not isinstance(param.annotation, ParseContextBase):
              err = "Context parameter \"" + param.name + "\" annotated with type " + str(param.annotation) + ", not derived from ParseContextBase"
              error_list.append(err)
          continue
        # subsequent parameters
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
          error_list.append("Positional-only argument \"" + param.name + "\" not supported")
          continue
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
          # *args in the parameter list
          var_positional_name = param.name
          positional_type = typing.Any
          if param.annotation != inspect.Parameter.empty:
            if not CommandInfo._is_type_annotation_supported(param.annotation):
              error_list.append("Parameter type \"" + str(param.annotation) + "\" not supported")
              continue
            positional_type = param.annotation
        if param.kind == inspect.Parameter.VAR_KEYWORD:
          # **kwargs in the parameter list
          # we probably will not use it, so do nothing here
          continue
        
        if param.kind not in [inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY]:
          # this is really an assertion... if the assertion fails, we must have unhandled argument kinds
          error_list.append("Parameter \"" + str(param.name) + "\" has unsupported parameter kind")
          continue
        
        param_info = KeywordArgumentInfo(
          canonical_name = param.name,
          aliases = [] if param.name not in parameter_alias else parameter_alias[param.name],
          annotation = typing.Any if param.annotation == inspect.Parameter.empty else param.annotation,
          required = (param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD)
        )
        kwargs_info.append(param_info)
        
        add_kwarg_mapping(param.name, param.name)
        if param.name in parameter_alias:
          for alias in parameter_alias[param.name]:
            add_kwarg_mapping(alias, param.name)
        named_args.add(param.name)
      
      # all parameters handled
      for cname in parameter_alias:
        if cname in named_args:
          continue
        # if control comes to here, this entry is not used
        if cname == var_positional_name:
          # only warn if it makes a difference
          if len(parameter_alias[cname]) > 0:
            error_list.append("Alias for vararg \"" + cname + "\" not supported")
        else:
          suggest = TypoSuggestion(cname)
          suggest.add_candidate(named_args)
          error_list.append("Parameter alias for \"" + cname + "\" unused because no such parameter; candidates: [\"" + "\", \"".join(suggest.get_result()) + "\"]")
      
      for kwa_name, kwa_alias in kwargs_decl.items():
        if kwa_name in named_args:
          error_list.append("Parameter alias for \"" + kwa_name + "\" should be specified in parameter_alias instead of kwargs_decl")
          continue
        if kwa_name == var_positional_name:
          error_list.append("Alias for vararg \"" + kwa_name + "\" not supported")
          continue
        add_kwarg_mapping(kwa_name, kwa_name)
        for alias in kwa_alias:
          add_kwarg_mapping(alias, kwa_name)
      
      if isFirstIteration:
        # this function does not take any parameters
        error_list.append("function not taking any parameter")
      
      # check whether there is a name clash
      if command in ParserType._cls_command_alias_dict:
        error_list.append("Command \"" + command + "\" is already declared")
      else:
        # we only check aliases if the canonical name is available
        # (if the canonical name is in use, the aliases are likely also in use)
        for alias in command_alias:
          if alias in ParserType._cls_command_alias_dict:
            error_list.append("Alias \"" + alias + "\" is already in use")
      
      # all validation completed
      if len(error_list) > 0:
        break
      
      # no error encountered; create registration entry
      result_info = CommandInfo(func, command, command_alias, kwarg_rename_dict, kwargs_info, positional_type, stage)
      
      # we MUST have a break here to exit the loop
      break
      
    if len(error_list) > 0:
      MessageHandler.critical_warning("Registering handler for command \"" + command + "\" failed:\n  " + "\n  ".join(error_list))
      return
    
    CommandInfo._do_register_command(result_info, ParserType, command, command_alias)
    return

# decorator for parse commands
# reference: https://realpython.com/primer-on-python-decorators/#decorators-with-arguments
def frontendcommand(ParserType: type, stage: typing.Any, command : str, command_alias : typing.List[str] = [], parameter_alias : typing.Dict[str, typing.List[str]] = {}, kwargs_decl : typing.Dict[str, typing.List[str]] = {}, *args, **kwargs):
  def decorator_parsecommand(func):
    # register the command
    CommandInfo._register(func, command, command_alias, parameter_alias, kwargs_decl, ParserType, stage, *args, **kwargs)
    
    # later on we may add debugging code to the wrapper... nothing for now
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
      return func(*args, **kwargs)
    return wrapper
  return decorator_parsecommand
