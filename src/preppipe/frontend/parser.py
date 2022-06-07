# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import io
import pathlib
import typing
import types
import PIL.Image
import pydub
import pathlib
import functools
import inspect
import string
import enum
import dataclasses
import datetime
import collections
from enum import Enum

from preppipe.inputmodel import *

from ..commontypes import *
from ..util import *
from .commandast import *
from .commandastparser import create_command_ast

# information of parameter type declarations
# we always support the following types in any parser without type declaration:
#     basic abstract types : int, float, str, bool
#     classes with native support in python:
#         datetime.date/time/datetime/timedelta
# we also always support the (implicit) conversion between these types
# TODO implement TypeDeclInfo

class TypeDeclInfo:
  _definition : type
  _basetypes : typing.List[type] | type
  def __init__(self, cls : type, BaseTypes : typing.List[type] | type) -> None:
    super().__init__()
    self._definition = cls
    self._basetypes = BaseTypes

  @staticmethod
  def _register(cls : type, BaseTypes : typing.List[type] | type, ParserType : type, *args, **kwargs):
    assert issubclass(ParserType, ParserBase)
    # do all the checkings first
    # if all checks passed, we populate the info into the parser
    if isinstance(BaseTypes, list):
      for memberTy in BaseTypes:
        if isinstance(memberTy, list):
          # we should never have this case
          MessageHandler.critical_warning('Parameter Type ' + str(cls) + 'registration failed: nexted list of types not supported: ' + str(BaseTypes))
          return
        unsupported_subtree = ParserType.get_unsupported_type_subtree(memberTy)
        if unsupported_subtree is not None:
          break
    else:
      unsupported_subtree = ParserType.get_unsupported_type_subtree(BaseTypes)
    if unsupported_subtree is not None:
      # the source types are not supported
      MessageHandler.critical_warning('Parameter Type ' + str(cls) + 'registration failed: unsupported base type: ' + str(unsupported_subtree))
      return
    # okay, the type is supported
    # populate the info
    decl = TypeDeclInfo(cls, BaseTypes)
    ParserType._cls_paramtype_dict[cls] = decl


# decorator for parser parameter types
# only classes not natively supported (the supported ones are listed above) need this annotation
# base types are types that the value can be converted from
# each type must be (1) natively supported types listed above, or (2) types already annotated by typedecl annotator, or (3) list / tuple / union of supported types
# we expect the decorated class to contain a static method called get()
# get() should take a single parameter that can handle any type listed in BaseTypes
# get() should either return an instance of the annotated type if the conversion is successful, or return None
# we have a list of type declarations at the end
def typedecl(ParserType: type, BaseTypes: typing.List[type] | type, *args, **kwargs):
  def decorator_typedecl(cls):
    # register the command
    TypeDeclInfo._register(cls, BaseTypes, ParserType, *args, **kwargs)
    return cls
  return decorator_typedecl

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
  # class variables for argument types registration
  # only base supported types (including native and registered) will appear here; list/tuple/union of types will NOT appear here
  # at the time of writing, we have no use cases requring per-instance type declaration registry, so currently it is per-class
  _cls_paramtype_dict : typing.ClassVar[typing.Dict[type, TypeDeclInfo]] = {}

  # class variables for commands registration
  # in the constructor, these registry will be COPIED to instances
  _cls_registered_parse_commands : typing.ClassVar[typing.List[CommandInfo]] = []
  _cls_command_alias_dict : typing.ClassVar[typing.Dict[str, int]] = {} # map from command alias names (including canonical names) to string

  # class variables for syntax
  _cls_command_start : typing.ClassVar[typing.Tuple] = ('[', '【')
  _cls_command_end   : typing.ClassVar[typing.Tuple] = (']', '】')
  _cls_command_name_suffix : typing.ClassVar[typing.Tuple] = (':', '：')
  
  # instance / member variables (copy of _cls*)
  _registered_parse_commands : typing.List[CommandInfo]
  _command_alias_dict : typing.Dict[str, int] # map from command alias names (including canonical names) to string
  
  def __init__(self) -> None:
    super().__init__()
    self._registered_parse_commands = self._cls_registered_parse_commands.copy()
    self._command_alias_dict = self._cls_command_alias_dict.copy()
  
  @staticmethod
  def is_natively_supported_type(ty : type) -> bool:
    # element types
    if ty in [str, float, int, bool]:
      return True
    # types that python have native support
    # datetime
    if ty in [datetime.timedelta]:
      return True
    return False
  
  @classmethod
  def get_unsupported_type_subtree(cls, ty : type | types.UnionType) -> type | types.UnionType | None:
    # return None if the type is supported, part of the type tree if not supported

    # case of lists should be handled by the caller; we do not expect to handle lists here
    if isinstance(ty, list):
      return ty
    
    if isinstance(ty, type):
      # this is a concrete type, instead of a generic type
      # at time of writing, neither generic types nor types.UnionType objects are instance of types
      if cls.is_natively_supported_type(ty):
        return None
      if ty in cls._cls_paramtype_dict:
        return None
      return ty
    
    # check for unions, e.g. str | int
    if isinstance(ty, types.UnionType):
      for memberTy in ty.__args__:
        subtree = cls.get_unsupported_type_subtree(memberTy)
        if subtree is not None:
          return subtree
      return None
    
    # our last guess is that this is a generic type
    # they are typing._GenericAlias and should have:
    # __origin__ : should be in [list, tuple]
    # __args__ : same as the one from types.UnionType
    if hasattr(ty, '__origin__') and hasattr(ty, '__args__'):
      if not ty.__origin__ in [list, tuple]:
        # unsupported generic type
        return ty
      # check all member types
      for memberTy in ty.__args__:
        subtree = cls.get_unsupported_type_subtree(memberTy)
        if subtree is not None:
          return subtree
      return None
    
    # ok, we really don't know what is passed in
    return ty

  def is_type_supported(self, ty : type | types.UnionType) -> bool:
    return self.get_unsupported_type_subtree(ty) is None
    
  def get_command(self, command : str) -> int | typing.List[str]:
    # if the command is found, we return an index of that command
    # otherwise, we return a list of strings that are the closest name to the provided
    index = self._command_alias_dict.get(command, -1)
    if index >= 0:
      # command found
      return index
    # command name not found
    suggest = TypoSuggestion(command)
    suggest.add_candidate(self._command_alias_dict.keys())
    return suggest.get_result()
  
  def get_command_index(self, command : str) -> int:
    return self._command_alias_dict.get(command, -1)
  
  def is_command_using_custom_parsing(self, command_index : int) -> bool:
    return self._registered_parse_commands[command_index]._custom_parsing_parameter_option != CommandInfo.CustomParsingParameterOption.NotCustomParsing
  
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

  def parse_blocks(self, blocklist : typing.List[IMBlock]) -> typing.List[IROp]:
    return _parser_parse_blocks_impl(self, blocklist)

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
          if not issubclass(param.annotation, ParseContextBase):
            err = "Context parameter \"" + param.name + "\" annotated with type " + str(param.annotation) + ", not derived from ParseContextBase"
            error_list.append(err)
      elif numParamParsed == 2:
        # if we have type annotation, make sure it is either str or CustomParseParameterType
        if param.annotation != inspect.Parameter.empty:
          if param.annotation is str:
            isPlainTextArg = True
          elif param.annotation is CustomParseParameterType:
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
            if not issubclass(param.annotation, ParseContextBase):
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

# helper class to register multiple commands more conveniently
class FrontendCommandRegisterHelper:
  _ParserType : type
  _stage : typing.Any
  _common_param_alias : typing.Dict[str, typing.List[str]]

  def __init__(self, ParserType: type, stage: typing.Any = None) -> None:
    self._ParserType = ParserType
    self._stage = stage
    self._common_param_alias = {}
  
  def set_stage(self, stage : typing.Any) -> None:
    self._stage = stage
  
  def add_common_alias_entry(self, name : str, alias : typing.list[str]) -> None:
    assert isinstance(name, str)
    assert isinstance(alias, list)
    self._common_param_alias[name] = alias
  
  def add_common_alias_dict(self, aliases : typing.Dict[str, typing.List[str]]) -> None:
    assert isinstance(aliases, dict)
    for name, alias in aliases.items():
      assert isinstance(name, str)
      assert isinstance(alias, list)
      for s in alias:
        assert isinstance(s, str)
    self._common_param_alias.update(aliases)

  def collect_alias(self, decllist : typing.Iterable[str], preserve_empty_key : bool = False) -> typing.Dict[str, typing.List[str]]:
    result : typing.Dict[str, typing.List[str]] = {}
    for param in decllist:
      # exclude all special parameters defined by preppipe
      if param.startswith('_'):
        continue
      if param in self._common_param_alias:
        result[param] = self._common_param_alias.get(param)
      elif preserve_empty_key:
        result[param] = []
    return result
  
  def register(self, func : callable, command_name : str, command_alias : typing.List[str] = [], kwarglist : typing.List[str] = [], *args, **kwargs) -> None:
    sig = inspect.signature(func)
    parameter_aliases = self.collect_alias(sig.parameters.keys())
    kwargs_decl : typing.Dict[str, typing.List[str]] = {}
    if len(kwarglist) > 0:
      kwargs_decl = self.collect_alias(kwarglist, preserve_empty_key = True)
    CommandInfo._register(func, command_name, command_alias, parameter_aliases, kwargs_decl, self._ParserType, self._stage, *args, **kwargs)

# decorator for use with registration helper
def register(helper : FrontendCommandRegisterHelper, command_name : str, command_alias : typing.List[str] = [], *args, **kwargs):
  def decorator_parsecommand(func):
    helper.register(func, command_name, command_alias, *args, **kwargs)
    return func
  return decorator_parsecommand

# ------------------------------------------------------------------------------
# Initial AST-like generic IR definition
# ------------------------------------------------------------------------------

@IROpDecl
class ParserElementBase(IROp):
  # base class of any in-paragraph element
  pass

@IROpDecl
class ParserNonTextElementOp(ParserElementBase):
  # base class of any non-text element. these are reference to assets, etc and does not "own" the data
  _element_data : IMElement

  def __init__(self, element : IMElement) -> None:
    super().__init__()
    self._element_data = element

  @property
  def element_data(self):
    return self._element_data

@IROpDecl
class ParserTextElementOp(ParserElementBase):
  _element_data : IMTextElement

  def __init__(self, element : IMTextElement) -> None:
    super().__init__()
    self._element_data = element
  
  @property
  def element_data(self):
    return self._element_data
  
  def to_string(self, indent=0) -> str:
    return type(self).__name__ + ' ' + self._element_data.to_string(indent)

@IROpDecl
class ParserParagraphBlockOp(IROp):
  # this is basically a parsed version of an IMParagraphBlock
  # all non-text elements are replaced with null characters in the text
  # we ensure that no non-text elements will appear before text and no non-text elements appear after text (the parser will break them down)
  # single region, single block; all member elements are listed in the block
  _text : str # an overall version of the text with leading/trailing whitespace removed. The real data will still have these whitespaces
  _members : typing.List[ParserElementBase]

  def __init__(self, members : typing.List[ParserElementBase] = [], text : str = "") -> None:
    super().__init__()
    self._text = text
    self._members = members
  
  def add_element(self, element : ParserElementBase):
    self._members.append(element)

  def get_region_dict(self) -> typing.Dict[str, typing.Any]:
    return {'members': self._members}
  
  def to_string(self, indent=0) -> str:
    return type(self).__name__ + ' "' + self._text + '"'

@IROpDecl
class ParserCommentOp(ParserParagraphBlockOp):
  # just use a different class to emphasize that this is comment
  def __init__(self, members: typing.List[ParserElementBase] = [], text: str = "") -> None:
    super().__init__(members, text)

class ParserCommandArgumentInfo:
  positionals : typing.List[ParserElementBase] # all values are constrained to be single-element; if the text has inconsistent styles, we will do majority vote to get a single style
  keyword_arguments : typing.OrderedDict[str, ParserElementBase] # we will drop style info on parameter names
  
  def __init__(self) -> None:
    self.positionals = []
    self.keyword_arguments = collections.OrderedDict()
  
  def add_positional_arg(self, arg : ParserElementBase):
    self.positionals.append(arg)
  
  def add_keyword_arg(self, name : str, value : ParserElementBase):
    self.keyword_arguments[name] = value

@IROpDecl
class ParserCommandBase(ParserParagraphBlockOp):
  _command_name : str # if parsed, what's the name of the command
  _command_index : int # if parsed and recognized by the parser, what's the index of the command
  
  # at least one of the below will be non-None
  _arguments : ParserCommandArgumentInfo | None # we will not have parsed arguments only when we cannot parse them out
  _raw_args : ParserParagraphBlockOp | None # we will not have raw_args set if the command is recognized and only use the parsed argument
  
  def __init__(self) -> None:
    super().__init__()
    self._command_name = ""
    self._command_index = -1
    self._arguments = None
    self._raw_args = None
  
  def set_command(self, name : str, index : int = -1):
    self._command_name = name
    self._command_index = index
  
  def set_argument_info(self, info : ParserCommandArgumentInfo):
    self._arguments = info
  
  def set_raw_argument_block(self, info : ParserParagraphBlockOp):
    self._raw_args = info
  
  def to_string(self, indent=0) -> str:
    result : str = type(self).__name__
    if len (self._command_name) > 0:
      result += ' ' + self._command_name
    # since we only create raw_args when needed, raw_args is probably more helpful when it is available
    if self._raw_args is not None:
      result += ' [' + self._raw_args.to_string(indent) + ']'
    elif self._arguments is not None:
      result += ' ('
      isFirst = True
      for p in self._arguments.positionals:
        if isFirst:
          isFirst = False
        else:
          result += ', '
        result += p.to_string(indent)
      for k, v in self._arguments.keyword_arguments.items():
        if isFirst:
          isFirst = False
        else:
          result += ', '
        result += k + '=' + v.to_string(indent)
      result += ')'
    return result

@IROpDecl
class ParserUnrecognizedCommandOp(ParserCommandBase):
  def __init__(self, members: typing.List[ParserElementBase] = [], text: str = "") -> None:
    super().__init__(members, text)

@IROpDecl
class ParserCommandOp(ParserCommandBase):
  # the class if the command is recognized
  # (we may still have syntax errors though, e.g. missing mandatory parameters and unrecognized parameters)
  # (in vnparser, they will be expanded/checked right before they being evaluated so that commands in earlier stages have chance to update the arguments)
  def __init__(self) -> None:
    super().__init__()

@IROpDecl
class ParserInputOp(IROp):
  pass

def _create_nontext_element(element : IMElement) -> ParserElementBase:
  return ParserNonTextElementOp(element)

def _create_element(element : IMElement) -> ParserElementBase:
  if isinstance(element, IMTextElement):
    return ParserTextElementOp(element)
  return _create_nontext_element(element)

def _create_element_from_commandast_element(element : ElementValueNode) -> ParserElementBase:
  raise NotImplementedError()
  if element.getContent() == '\0':
    # this is a non-text element
    pass

def _create_command_blocks(element_lookup_dict : typing.Dict[int, int], element_list : typing.List[IROp], all_text : str, parser : ParserBase) -> typing.List[IROp]:
  ast = create_command_ast(all_text, None)
  if ast is None:
    return None
  result : typing.List[IROp] = []
  def get_value(v: ElementValueNode) -> ParserElementBase:
    if v.getContent() == '\0':
      # this is a non-text element
      # v.start must exactly point to the non-text element
      element_index = element_lookup_dict.get(v.start, -1)
      assert element_index > 0 and element_index < len(element_list) # greater than zero because the first element should always be a text element
      element = element_list[element_index]
      assert isinstance(element, ParserElementBase)
      return element
    # this is a text element
    # we need to do a range search
    start_pos = max(k for k in element_lookup_dict if k <= v.start)
    element_index = element_lookup_dict.get(start_pos, -1)
    assert element_index >= 0
    element = element_list[element_index]
    assert isinstance(element, ParserTextElementOp)
    # we can directly pass the element if there is no need to change the range of the text
    element_data : IMTextElement = element.element_data
    text_len = len(element_data.text)
    trimlen_left = v.start - start_pos
    trimlen_right = start_pos + text_len - v.end
    if trimlen_left == 0 and trimlen_right == 0:
      return element
    # TODO if the AST node maps to multiple text elements with different styles, we will need to merge them into one element
    # the following assertion will fault if this happens
    assert trimlen_left >= 0 and trimlen_right >= 0
    newtext = element_data.text
    if trimlen_right > 0:
      newtext = element_data.text[trimlen_left : -trimlen_right]
    elif trimlen_left > 0:
      newtext = element_data.text[trimlen_left:]
    newTextElement = IMTextElement(newtext, element_data.styles)
    return ParserTextElementOp(newTextElement)
  
  def get_member_list_and_text(v : ASTNodeBase) -> typing.Tuple[typing.List[ParserElementBase], str]:
    cur_member_list : typing.List[ParserElementBase] = []
    cur_text : str = ""
    cur_start = v.start
    while cur_start < v.end:
      exact_start_pos = max(k for k in element_lookup_dict if k <= cur_start)
      element_index = element_lookup_dict.get(exact_start_pos, -1)
      cur_element_text = '\0'
      cur_element_len = 1
      cur_element = element_list[element_index]
      if isinstance(cur_element, ParserTextElementOp):
        cur_text_imelement : IMTextElement = cur_element.element_data
        cur_element_text = cur_text_imelement.text
        cur_element_len = len(cur_element_text)
      # most common case: the current element is exactly inside the range
      if exact_start_pos == cur_start and cur_start + cur_element_len <= v.end:
        cur_member_list.append(cur_element)
        cur_text += cur_element_text
        cur_start += cur_element_len
      else:
        # we need to trim part of the element
        assert isinstance(cur_element, ParserTextElementOp)
        cur_text_imelement : IMTextElement = cur_element.element_data
        start_trim_len = cur_start - exact_start_pos
        new_text = cur_text_imelement.text
        if start_trim_len > 0:
          # this should only be possible in the first iteration
          assert len(cur_member_list) == 0
          new_text = cur_text_imelement.text[start_trim_len:]
        end_trim_len = exact_start_pos + cur_element_len - v.end
        if end_trim_len > 0:
          new_text = new_text[:-end_trim_len]
        new_text_element = IMTextElement(new_text, cur_text_imelement.styles)
        cur_member_list.append(new_text_element)
        cur_text += new_text
        cur_start += len(new_text)
    return cur_member_list, cur_text

  for body in ast.bodylist:
    if isinstance(body, CommandNode):
      # we are guaranteed to have a name field in this cast
      cur_element = ParserCommandOp()
      command_name = body.name.getContent()
      command_index = parser.get_command_index(command_name)
      cur_element.set_command(command_name, command_index)
      argument_info = None
      raw_args = None
      if body.parsed_args is not None:
        argument_info = ParserCommandArgumentInfo()
        for positional in body.parsed_args.positionals:
          value = get_value(positional)
          argument_info.add_positional_arg(value)
        for kwarg in body.parsed_args.keywordargs:
          key = kwarg.keyword.getContent()
          value= get_value(kwarg.value)
          argument_info.add_keyword_arg(key, value)
      cur_element.set_argument_info(argument_info)
      is_need_raw_arg = True
      if argument_info is not None and command_index >= 0:
        is_need_raw_arg = parser.is_command_using_custom_parsing(command_index)
      if is_need_raw_arg:
        # need to convert body.raw_args (ASTNodeBase) to a paragraph op
        # we preserve the null character in the text, so only the beginning / end element needs adjustment
        # check trivial case first
        if body.raw_args.start >= body.raw_args.end:
          raw_args = ParserParagraphBlockOp(members = [], text = "")
        else:
          members = []
          start_pos = max(k for k in element_lookup_dict if k <= body.raw_args.start)
          start_element_index = element_lookup_dict.get(start_pos, -1)
          assert start_element_index >= 0
          # stel 1: add all the elements to the new member list
          start_pos_list = list(element_lookup_dict.keys())
          cur_src_element_index = start_element_index
          end_pos = start_pos
          while cur_src_element_index < len(element_list):
            cur_start_pos = start_pos_list[cur_src_element_index]
            assert element_lookup_dict[cur_start_pos] == cur_src_element_index
            assert end_pos == cur_start_pos
            if cur_start_pos >= body.raw_args.end:
              break
            cur_src_element = element_list[cur_src_element_index]
            if isinstance(cur_src_element, IMTextElement):
              end_pos = cur_start_pos + len(cur_src_element.text)
            else:
              end_pos = cur_start_pos + 1 # length of the null character
            members.append(cur_src_element)
            cur_src_element_index +=1
          assert len(members) > 0
          # step 2: trim the first element if needed
          if body.raw_args.start < start_pos:
            # note that we CANNOT modify element in place; we will create a new element with the updated data and replace the reference in the source list
            front_element = members[0]
            if isinstance(front_element, IMTextElement):
              front_trim_len = start_pos - body.raw_args.start
              element_text = front_element.text[front_trim_len:]
              new_element = IMTextElement(element_text, front_element.styles)
              members[0] = new_element
            else:
              # should not be possible
              raise RuntimeError("Unexpected trimming of non-text element")
          # step 3: trim the last element if needed
          if body.raw_args.end > end_pos:
            back_element = members[-1]
            if isinstance(back_element, IMTextElement):
              back_trim_len = end_pos - body.raw_args.end
              element_text = back_element.text[:-back_trim_len]
              new_element = IMTextElement(element_text, back_element.styles)
              members[-1] = new_element
          raw_args = ParserParagraphBlockOp(members, body.raw_args.text)
        # finished creating raw args
      cur_element.set_raw_argument_block(raw_args)
      result.append(cur_element)
      # we will do this after the arguments are handled properly
    elif isinstance(body, UnrecognizedPartNode):
      # we are guaranteed not having the name field
      op_members, op_text = get_member_list_and_text(body)
      cur_element = ParserUnrecognizedCommandOp(op_members, op_text)
      result.append(cur_element)
    elif isinstance(body, CommentNode):
      op_members, op_text = get_member_list_and_text(body)
      cur_element = ParserCommentOp(op_members, op_text)
      result.append(cur_element)
  return result

def _parser_parse_blocks_impl(parser : ParserBase, blocklist : typing.List[IMBlock]) -> typing.List[IROp]:
  result : typing.List[IROp] = []
  for block in blocklist:
    if isinstance(block, IMParagraphBlock):
      # step 1: break the block into smaller blocks if needed
      # we will need to break down the block if the block is a paragraph block and there are non-text elements before / after the text
      # such elements will create trouble for command parsing code
      nontext_elements_before = []
      first_text_pos = -1
      for i in range(len(block.element_list)):
        element = block.element_list[i]
        if isinstance(element, IMTextElement):
          text = element.text.strip()
        if len(text) > 0:
          first_text_pos = i
          break
        else:
          converted_element = _create_nontext_element(element)
          nontext_elements_before.append(converted_element)
      
      # now we should have handled all elements before the first non-empty text
      # whitespaces between these non-text elements are dropped
      if len(nontext_elements_before) > 0:
        newblock = ParserParagraphBlockOp(nontext_elements_before)
        result.append(newblock)
      del nontext_elements_before

      if first_text_pos == -1:
        # this block has no non-empty text element
        # nothing else to do here
        continue

      # ok, now we reached first text element that is not empty
      # next, get the trailing non-text element handled
      nontext_elements_after = []
      last_text_pos = 0
      for i in range(len(block.element_list)-1, first_text_pos, -1):
        element = block.element_list[i]
        if isinstance(element, IMTextElement):
          text = element.text.strip()
        if len(text) > 0:
          last_text_pos = i
          break
        else:
          converted_element = _create_nontext_element(element)
          nontext_elements_after.append(converted_element)
      
      # create the main text block now
      element_list = []
      all_text = ""
      element_lookup_dict : typing.Dict[int, int] = {} # [pos in all_text] -> index in element_list; useful for locating the non-text element from its position in all_text
      for i in range(first_text_pos, last_text_pos+1):
        element = block.element_list[i]
        element_op = _create_element(element)
        element_lookup_dict[len(all_text)] = len(element_list)
        element_list.append(element_op)
        if isinstance(element, IMTextElement):
          # we need to trim the text for whitespace before adding to all_text
          text_to_add = element.text
          if i == first_text_pos:
            text_to_add = element.text.lstrip()
          elif i == last_text_pos:
            text_to_add = element.text.rstrip()
          all_text += text_to_add
        else:
          all_text += '\0'
      assert len(all_text) > 0
      is_handled = False
      if all_text.startswith(('[', '\u3010')):
        # try to parse it as commands or other special blocks
        result_part = _create_command_blocks(element_lookup_dict, element_list, all_text, parser)
        if result_part is not None:
          result.extend(result_part)
          is_handled = True
      if not is_handled:
        newblock = ParserParagraphBlockOp(element_list, all_text)
        result.append(newblock)

      # handle trailing elements if needed
      if len(nontext_elements_after) > 0:
        # before creating the block, we need to reverse the order of elements because we iterated from back to front in the loop
        nontext_elements_after.reverse()
        newblock = ParserParagraphBlockOp(nontext_elements_after)
        result.append(newblock)
    else:
      raise NotImplementedError("Cannot handle non-paragraph blocks for now")
  return result


# ----------------------------------------------------------
# list of (possibly?) commonly used types
# ----------------------------------------------------------

# distance types

@dataclasses.dataclass
@typedecl(ParserType=ParserBase, BaseTypes=str)
class PhysicalDistance:
  dist_meter : float

  @staticmethod
  def get(value : str) -> PhysicalDistance:
    return _get_PhysicalDistance_impl(value)

@dataclasses.dataclass
@typedecl(ParserType=ParserBase, BaseTypes=[int|str])
class PixelDistance:
  dist_pixel : int

  @staticmethod
  def get(value : int | str) -> PixelDistance:
    return _get_PixelDistance_impl(value)

@dataclasses.dataclass
@typedecl(ParserType=ParserBase, BaseTypes=str)
class PixelSize:
  width_pixel : int
  height_pixel : int

  @staticmethod
  def get(value : str) -> PixelSize:
    return _get_PixelSize_impl(value)

# ----------------------------------------------------------
# conversion functions TODO
# ----------------------------------------------------------

def _get_PhysicalDistance_impl(value : str) -> PhysicalDistance:
  pass

def _get_PixelDistance_impl(value : int | str) -> PixelDistance:
  pass

def _get_PixelSize_impl(value : str) -> PixelSize:
  pass
