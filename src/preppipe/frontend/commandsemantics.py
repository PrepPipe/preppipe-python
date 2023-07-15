# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0


from __future__ import annotations

import inspect
import types
import typing
import collections
import enum
import re

from ..irbase import *
from ..inputmodel import *
from ..nameresolution import NameResolver, NamespaceNode
from .commandsyntaxparser import GeneralCommandOp, CMDValueSymbol, CMDPositionalArgOp, CommandCallReferenceType

# ------------------------------------------------------------------------------
# 解析器定义 （语义分析阶段）
#
# 为了分离出抽象的命令处理与具体的解析器执行，我们在这里定义如下的抽象层：
# 1.  每个解析器都应继承自 ParserBase, ParserBase 中定义了“命令域” (command domain)
#     用以区分不同的解析器（比如视觉小说在 "vnmodel" 域下，以后有其他解析器也可以再加）
# 2.  解析器基类以及本文件中的函数提供:
#         - 命令解析(找到命令)
#         - 命令匹配(在已知的命令列表中查找属于哪个命令)，
#         - 参数类型转换（把源文本中的字符串等转化为命令记录中处理函数的参数）
#     子类来实现如何具体操作
# ------------------------------------------------------------------------------

# decorator for parse commands
# reference: https://realpython.com/primer-on-python-decorators/#decorators-with-arguments
# pylint: disable=invalid-name
def CommandDecl(ns: FrontendCommandNamespace, imports : dict[str, typing.Any], name : str, alias : typing.Dict[str | typing.Tuple[str, ...], typing.Dict[str, str]] = None):
  if alias is None:
    alias = {}
  def decorator_parsecommand(func):
    # register the command
    ns.register_command(func, imports, name, alias)
    return func

    # later on we may add debugging code to the wrapper... nothing for now
    #@functools.wraps(func)
    #def wrapper(*args, **kwargs):
    #  return func(*args, **kwargs)
    #return wrapper
  return decorator_parsecommand

# 如果命令参数实质上是个枚举类型，命令可以定义该枚举类型，继承 enum.Enum，并且加上这个修饰符
# 这个修饰符会添加一个 _translate() 的静态函数，用于把字符串转为枚举类型的值
# 不同语言的别名也会在该函数中转换
def FrontendParamEnum(alias : dict[str, set[str]]):
  def decorator_enum(cls):
    assert issubclass(cls, enum.Enum)
    used_keys = set()
    translation_dict = {} # （不同语言的）别名 -> 枚举类值
    for p in cls:
      if p.name in alias:
        used_keys.add(p.name)
        for v in alias[p.name]:
          assert v not in translation_dict
          translation_dict[v] = p
    if len(used_keys) != len(alias):
      for key in alias.keys():
        if key not in used_keys:
          raise RuntimeError('Invalid key "' + key + '" in ' + cls.__name__ + ' for alias')
    def translate_cb(name : str):
      if name in translation_dict:
        return translation_dict[name]
      if name in cls.__members__:
        return cls[name]
      return None
    setattr(cls, '_translate', staticmethod(translate_cb))
    return cls
  return decorator_enum

# 其他类型的参数
# 内联调用
@dataclasses.dataclass
class CallExprOperand:
  name : str
  args : list[Value | CallExprOperand] = dataclasses.field(default_factory=list) # XXXLiteral, CallExprOperand
  kwargs : typing.OrderedDict[str, Value | CallExprOperand] = dataclasses.field(default_factory=collections.OrderedDict)

# 所有延伸的数据的基类
# 这些数据是在命令之外的、根据语法整合进该命令的数据
# 比如列表项、特殊块
@dataclasses.dataclass(kw_only=True)
class ExtendDataExprBase:
  # 对于转换这些延伸参数时产生的警告或错误，我们其实没有其他很好的手段来保证它们在被用到时才报错、没用到时不报错
  # 所以我们现在把它们放在参数本身，这样如果命令真的用到了这些结果，我们再把它们报告出去
  # 设置 kw_only=True 以使 warnings 不影响子类的初始化
  warnings : list[tuple[str, str]] | None = None
  original_op : Operation | None = None # 原来的 IMListOp, IMSpecialBlockOp, 或者 IMTableOp

# 延伸的列表项（只能出现一次）
@dataclasses.dataclass
class ListExprOperand(ExtendDataExprBase):
  data : typing.OrderedDict[str, typing.Any] | list[str]

@dataclasses.dataclass
class SpecialBlockOperand(ExtendDataExprBase):
  pass

@dataclasses.dataclass
class TableExprOperand(ExtendDataExprBase):
  pass

@dataclasses.dataclass
class FrontendCommandInfo:
  # 为了支持函数重载，我们需要在同一个命令下绑定多个用于实现的函数以及他们的别名
  # 为方便起见，我们要求参数的所有别名必须一致(同一个规范名不能有多个别名)
  cname : str # 命令的规范名
  aliases : typing.Dict[str | typing.Tuple[str], typing.Dict[str, str]] # 所有 aliases 注册项合并后的结果，第一个 key 是命令名的别名，后面的key是参数规范名
  parameter_alias_dict : typing.Dict[str, str] # 从参数的别名到规范名
  handler_list : list[tuple[typing.Callable, inspect.Signature]] # 所有的实现都在这里

class FrontendCommandNamespace(NamespaceNode[FrontendCommandInfo]):

  @staticmethod
  def create(parent : FrontendCommandNamespace | None, cname : str) -> FrontendCommandNamespace:
    if parent is None:
      parent = FrontendCommandRegistry.get_global_namespace()
    return FrontendCommandNamespace(FrontendCommandRegistry.get_registry(), parent, cname)

  def __init__(self, tree: FrontendCommandRegistry, parent: FrontendCommandNamespace, cname: str | None) -> None:
    super().__init__(tree, parent, cname)

  def get_or_create_command_info(self, name : str) -> FrontendCommandInfo:
    command_info = self.lookup_name(name)
    if isinstance(command_info, FrontendCommandNamespace):
      raise RuntimeError('Name collision between namespace and command entry: "' + name + '"')
    if command_info is None:
      command_info = FrontendCommandInfo(cname = name, aliases = {}, parameter_alias_dict={}, handler_list=[])
      self.add_data_entry(name, command_info)
    assert isinstance(command_info, FrontendCommandInfo)
    assert command_info.cname == name
    return command_info

  def add_command_handler(self, command_info : FrontendCommandInfo, func : typing.Callable, imports : dict[str, typing.Any]):
    # 如果在这里报错（无法解析类型名）的话，请确保：
    # 1. 定义命令的源文件可以在没有 from __future__ import annotations 的情况下顺利使用类型标注
    # 2. 所有在回调函数参数类型的标注中的类全都在 imports 中（不过 imports 也可以为空）
    sig = inspect.signature(func, globals=imports, eval_str=True)
    command_info.handler_list.append((func, sig))

  def add_command_namealiases(self, command_info : FrontendCommandInfo, alias : dict[str | tuple[str, ...], dict[str, str]]):
    # 把别名信息合并进去
    # 我们需要同时处理 aliases 和 parameter_alias_dict
    for name_alias, param_alias_dict in alias.items():
      assert isinstance(name_alias, str) or isinstance(name_alias, tuple)
      assert isinstance(param_alias_dict, dict)
      if name_alias not in command_info.aliases:
        if isinstance(name_alias, str):
          self.add_local_alias(command_info.cname, name_alias)
        elif isinstance(name_alias, tuple):
          for a in name_alias:
            assert isinstance(a, str)
            self.add_local_alias(command_info.cname, a)
        else:
          raise RuntimeError('Unexpected name alias type')
        existing_dict : typing.Dict[str, str] = {}
        command_info.aliases[name_alias] = existing_dict
      else:
        existing_dict = command_info.aliases[name_alias]
      for param_cname, param_alias_name in param_alias_dict.items():
        assert isinstance(param_alias_name, str)
        assert isinstance(param_cname, str)
        if param_cname in existing_dict:
          if existing_dict[param_cname] != param_alias_name:
            raise RuntimeError('Parameter "' + param_cname + '" already has a different alias: "' + existing_dict[param_cname] + '" != "' + param_alias_name + '"')
        else:
          existing_dict[param_cname] = param_alias_name
          if param_alias_name in command_info.parameter_alias_dict:
            existing_cname = command_info.parameter_alias_dict[param_alias_name]
            if existing_cname != param_cname:
              raise RuntimeError('Conflicting alias for parameter "' + param_cname + '": "' + existing_cname + '" != "' + param_cname + '"')
          else:
            command_info.parameter_alias_dict[param_alias_name] = param_cname

  def register_command(self, func : typing.Callable, imports : dict[str, typing.Any], name : str, alias : dict[str | tuple[str, ...], dict[str, str]]) -> None:
    command_info = self.get_or_create_command_info(name)
    self.add_command_handler(command_info, func, imports)
    self.add_command_namealiases(command_info, alias)

class FrontendCommandRegistry(NameResolver[FrontendCommandInfo]):
  _global_ns : FrontendCommandNamespace

  @staticmethod
  def get_registry() -> FrontendCommandRegistry:
    return _frontend_command_registry

  @staticmethod
  def get_global_namespace() -> FrontendCommandNamespace:
    return FrontendCommandRegistry.get_registry().global_namespace

  @property
  def global_namespace(self) -> FrontendCommandNamespace:
    return self._global_ns

  def __init__(self) -> None:
    super().__init__()
    self._global_ns = FrontendCommandNamespace(self, None, None)

  def get_root_node(self) -> FrontendCommandNamespace:
    return self._global_ns


_frontend_command_registry = FrontendCommandRegistry()

# ------------------------------------------------------------------------------

ParserStateType = typing.TypeVar('ParserStateType')

class FrontendParserBase(typing.Generic[ParserStateType]):
  # 该类的实例记录了解析过程中用到的信息，可能有多个该类的实例对应同一个前端命令空间
  # 前端命令空间某种意义上是解析器类的一部分静态数据，因为命令的实际实现必定与解析器内部紧密相关
  # 我们把前端命令空间与解析器实现区分开主要有以下两个目的：
  # 1.  可以对命令的语义与实现进行分隔，以后若有更加合适的实现算法可以无缝衔接
  # 2.  命令名称解析可以复用
  # 我们要求命令的处理函数必须是一个独立的函数而不是绑定解析器类的成员函数，为了实现以下目标：
  # 1.  方便理解、方便后续改动。python 语言特性用的太复杂容易劝退新人
  # 2.  便于在不改解析器类源代码的基础上新增命令，用于实现类似宏的效果。用户可以在自己的脚本里新增命令。
  # 继承该类的子类应将其状态信息分为两部分：
  # 1.  在处理输入文档时不太会变动的（全局的）部分，这部分可以放在子类本体里
  # 2.  处理时会经常变动的部分，包括当前的输入位置、输出位置等（包括但不限于部分属于 IRBuilder 的状态）。
  #     这部分应该单独放在一个状态对象里，方便进行复制(fork)等操作
  # 第二部分的数据的类型应通过构造函数的 state_type 参数进行声明


  @dataclasses.dataclass
  class CommandInvocationInfo:
    # 如果我们找到了一个可以用于处理给定命令的回调函数，我们用这个类型来保存参数以及警告
    cb : callable
    args : list[typing.Any] = dataclasses.field(default_factory=list)
    kwargs : dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    warnings: list[tuple[str, typing.Any]] = dataclasses.field(default_factory=list)

    def add_parameter(self, param : inspect.Parameter, value : typing.Any) -> None:
      match param.kind:
        case inspect.Parameter.VAR_POSITIONAL | inspect.Parameter.VAR_KEYWORD:
          raise RuntimeError('Not expecting assignment to *arg / **kwarg')
        case inspect.Parameter.POSITIONAL_ONLY:
          self.args.append(value)
        case inspect.Parameter.POSITIONAL_OR_KEYWORD | inspect.Parameter.KEYWORD_ONLY:
          self.kwargs[param.name] = value
        case _:
          # should not be possible
          raise NotImplementedError()

    def try_add_parameter(self, param : inspect.Parameter, value : typing.Any) -> typing.Tuple[str, typing.Any] | None:
      # 尝试把给定的值赋予参数
      # 如果有错误的话返回错误
      target_value = _try_convert_parameter(param.annotation, value)
      if target_value is None:
        return ('cmdparser-param-conversion-failed', param.name)
      self.add_parameter(param, target_value)
      return None

    def add_warning(self, warn_code : str, warn_data : typing.Any):
      self.warnings.append((warn_code, warn_data))

  _ctx : Context
  _command_ns : FrontendCommandNamespace
  _state_type : type # 应与 ParserStateType 所注类型一致

  def __init__(self, ctx : Context, command_ns : FrontendCommandNamespace, state_type : type) -> None:
    self._ctx = ctx
    self._command_ns = command_ns
    self._state_type = state_type

  # 不管怎样我们都需要提供这些接口来方便新的外部的实现

  @property
  def context(self) -> Context:
    return self._ctx

  @property
  def command_ns(self) -> FrontendCommandNamespace:
    return self._command_ns

  @property
  def state_type(self) -> type:
    return self._state_type

  def lookup(self, name : str, using_path : typing.List[typing.Tuple[str]] = None):
    return self.command_ns.namespace_tree.unqualified_lookup(name, self.command_ns.get_namespace_path(), using_path)

  def handle_command_op(self, state : ParserStateType, op : GeneralCommandOp):
    head_symbol_table = op.get_symbol_table('head')
    namesymbol = head_symbol_table.get('name')
    assert isinstance(namesymbol, CMDValueSymbol)
    opname = namesymbol.value
    assert isinstance(opname, StringLiteral)
    # 目前我们不定义 fully qualified lookup，因为貌似没有适合作为命名空间分隔符的字符。。。
    lookup_result = self.lookup(opname.value)
    if lookup_result is None:
      self.handle_command_unrecognized(state, op, opname.value)
      return
    assert isinstance(lookup_result, FrontendCommandInfo)
    return self.handle_command_invocation(state, op, lookup_result)

  def handle_command_ambiguous(self, state : ParserStateType,
                               commandop : GeneralCommandOp, cmdinfo : FrontendCommandInfo,
                               matched_results : typing.List[CommandInvocationInfo],
                               unmatched_results : typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    # 但且仅当不止一个回调函数满足调用条件时发生
    pass

  def handle_command_unique_invocation(self, state : ParserStateType,
                                       commandop : GeneralCommandOp, cmdinfo : FrontendCommandInfo,
                                       matched_result : CommandInvocationInfo,
                                       unmatched_results : typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    # 仅当正好只有一个回调函数满足条件时发生
    pass

  def handle_command_no_match(self, state : ParserStateType, commandop : GeneralCommandOp, cmdinfo : FrontendCommandInfo, unmatched_results : typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    # 没有回调函数满足条件时发生
    pass

  @classmethod
  def convert_value(cls, value : Value) -> Value | CallExprOperand:
    assert isinstance(value, Value)
    if isinstance(value.valuetype, CommandCallReferenceType):
      assert isinstance(value, OpResult)
      callop = value.parent
      assert isinstance(callop, GeneralCommandOp)
      return cls.parse_commandop_as_callexpr(callop)
    return value

  def _extract_extend_data(self, commandop : GeneralCommandOp) -> ExtendDataExprBase | None:
    extend_data_block = commandop.get_region('extend_data').entry_block
    # 先把最可能出现的给解决
    if extend_data_block.body.empty:
      return None
    # 应该最多只有一个延伸参数
    if extend_data_block.body.size != 1:
      raise RuntimeError('More than one extend data?')

    op = extend_data_block.body.front
    if isinstance(op, IMListOp):
      # 我们需要把这个列表项转为 ListExprOperand
      warnings : list[tuple[str, str]] = []
      data = self._populate_listexpr(op, warnings)
      if len(warnings) == 0:
        warnings = None
      return ListExprOperand(data, warnings=warnings, original_op=op)

    if isinstance(op, IMSpecialBlockOp):
      return SpecialBlockOperand(original_op=op)

    if isinstance(op, IMTableOp):
      return TableExprOperand(original_op=op)

    # 其他的类型暂不支持
    raise NotImplementedError('Extend data type not supported: ' + str(type(op)))

  def _populate_listexpr(self, src : IMListOp, warnings : list[tuple[str, str]]) -> typing.OrderedDict[str, typing.Any] | list[str]:
    # 这里我们假设一个简单的情况，接受延伸内容的命令使用该列表来当一个 key-value store 来使用，键都是字符串，值是字符串或者图片、声音等资源
    # 值可以为空，但如果一个层级里所有的值都为空，那么这是一个列表 (list) 而不是一个字典 (dict)
    # 如果列表项整个为空，我们跳过该项
    # 如果整个列表为空，我们返回一个空的字典
    # 如果列表项键值有重复，
    # 如果命令对该列表的使用方式与我们这里的处理不一样（比如分支命令，列表表示不同选项，底下的内容作为独立的(可携带命令的)段落），那么命令总归可以接受原始的 GeneralCommandOp 输入来自行处理
    data : typing.OrderedDict[str, typing.Any] = collections.OrderedDict()
    # 记录每个键值所在的位置，便于在出现重复键值时生成警告
    prev_locations : dict[str, Location] = {}
    is_nonempty_value_found = False
    for item_region in src.regions:
      # 最多两个块，一个块有 IMElementOp，存的是列表项的内容，另一个块有子列表
      num_blocks = item_region.get_num_blocks()
      assert num_blocks <= 2
      if num_blocks == 0:
        continue
      # 第一个块一定有一个 IMElementOp，不会直接是子列表
      textblock = item_region.entry_block
      frontop = textblock.body.front
      text_str, asset_list = IMElementOp.collect_text_from_paragraph(textblock)
      text_str = text_str.strip()
      # 我们接受如下形式的语法：
      # <A>:<B>
      # <A>=<B>
      # <A> <B>
      # A 与 B 可以是用引号引起来的字符串，也可以没有引号（只要没有其他这些字符、没有空格）
      regex_str = r"^(?P<k>\"[^\"]*\"|'[^']*'|[^'\"=＝:： ]+)(\s*[ =＝:：]\s*(?P<v>.+|\0)?)?$"
      match_result = re.match(regex_str, text_str)
      if match_result is None:
        # 这一项没法读，记个错误然后跳过
        errcode = 'cmdparser-listitem-skipped-in-extend-data'
        msg = str(frontop.location)
        warnings.append((errcode, msg))
        continue
      key_str = match_result.group('k')
      value_str = match_result.group('v') # 可能是 None
      # 如果 key_str 是被引号引起来的，就把引号去掉
      if key_str.startswith('"') and key_str.endswith('"'):
        key_str = key_str[1:-1]
      elif key_str.startswith("'") and key_str.endswith("'"):
        key_str = key_str[1:-1]
      value_v = None
      if value_str is not None:
        if value_str == '\0':
          # 这是一个资源
          if len(asset_list) == 0:
            errcode = 'cmdparser-listitem-unresolved-asset-reference'
            msg = str(frontop.location)
            warnings.append((errcode, msg))
          else:
            value_v = asset_list[0]
        elif value_str.startswith('"') and value_str.endswith('"'):
          value_v = value_str[1:-1]
        elif value_str.startswith("'") and value_str.endswith("'"):
          value_v = value_str[1:-1]
        else:
          value_v = value_str
      if value_v is None and num_blocks > 1:
        # 应该还有一个列表项，我们读列表项的值
        listblock = textblock.get_next_node()
        assert isinstance(listblock, Block)
        assert listblock.body.size == 1
        frontop = listblock.body.front
        if isinstance(frontop, IMListOp):
          value_v = self._populate_listexpr(frontop, warnings)
      # 检查是否所有内容都用上了
      if isinstance(value_v, AssetData) and len(asset_list) > 1 or len(asset_list) > 0:
        errcode = 'cmdparser-listitem-extra-asset-unused'
        msg = str(frontop.location)
        warnings.append((errcode, msg))
      # 开始将当前项加到结果中
      if key_str in data:
        prev = prev_locations[key_str]
        errcode = 'cmdparser-listitem-overwrite'
        msg = '"' + key_str + '" @ ' + str(prev)
        warnings.append((errcode, msg))
      else:
        data[key_str] = value_v
        if value_v is not None:
          is_nonempty_value_found = True
    if not is_nonempty_value_found:
      # 把字典转化成列表
      return [k for k in data.keys()]
    return data

  @classmethod
  def parse_commandop_as_callexpr(cls, commandop : GeneralCommandOp) -> CallExprOperand:
    # 在命令内的调用表达式
    # 可以再内嵌调用表达式，但是不会有追加的列表、特殊块等参数
    call_name_symbol : CMDValueSymbol = commandop.get_symbol_table('head').get('name')
    assert isinstance(call_name_symbol, CMDValueSymbol)
    call_name = call_name_symbol.value.get_string()
    assert isinstance(call_name, str)

    positional_args = []
    posarg_block = commandop.get_region('positional_arg').entry_block
    for op in posarg_block.body:
      assert isinstance(op, CMDPositionalArgOp)
      opvalue = cls.convert_value(op.value)
      positional_args.append(opvalue)

    kwargs = collections.OrderedDict()
    kwargs_region = commandop.get_symbol_table('keyword_arg')
    for op in kwargs_region:
      assert isinstance(op, CMDValueSymbol)
      name = op.name
      value = cls.convert_value(op.value)
      # 内嵌的调用表达式没有参数别名
      # if name in cmdinfo.parameter_alias_dict:
      #   name = cmdinfo.parameter_alias_dict[name]
      kwargs[name] = value

    # 确认没有追加数据，如果有的话就报错
    extend_data_block = commandop.get_region('extend_data').entry_block
    if not extend_data_block.body.empty:
      raise RuntimeError('Extend data in (nested) call expression? (should only be in outer command)')

    return CallExprOperand(name=call_name, args=positional_args, kwargs=kwargs)

  @staticmethod
  def _check_is_extend_data(annotation : typing.Any) -> list[type]:
    # 给定一个命令回调函数的参数类型标注，如果是延伸参数类型，返回所有的类型标注
    # （如果该命令可以接受多种延伸参数类型，我们想把所有可接受的延伸参数类型找到）
    if isinstance(annotation, types.UnionType):
      # 这是 T1 | T2 | ...
      return [ty for ty in annotation.__args__ if issubclass(ty, ExtendDataExprBase)]
    assert isinstance(annotation, type)
    if issubclass(annotation, ExtendDataExprBase):
      return [annotation]
    return []

  def handle_command_invocation(self, state : ParserStateType, commandop : GeneralCommandOp, cmdinfo : FrontendCommandInfo):
    # 从所有候选命令实现中找到最合适的，并进行调用
    # 首先把参数准备好
    positional_args = []
    posarg_block = commandop.get_region('positional_arg').entry_block
    for op in posarg_block.body:
      assert isinstance(op, CMDPositionalArgOp)
      opvalue = self.convert_value(op.value)
      positional_args.append(opvalue)
    kwargs_region = commandop.get_symbol_table('keyword_arg')
    kwargs = collections.OrderedDict()
    for op in kwargs_region:
      assert isinstance(op, CMDValueSymbol)
      name = op.name
      value = self.convert_value(op.value)
      if name in cmdinfo.parameter_alias_dict:
        name = cmdinfo.parameter_alias_dict[name]
      kwargs[name] = value
    extend_data_value : ExtendDataExprBase = self._extract_extend_data(commandop)
    # 然后遍历所有项，找到所有能调用的回调函数
    matched_results : typing.List[FrontendParserBase.CommandInvocationInfo] = []
    unmatched_results : typing.List[typing.Tuple[callable, typing.Tuple[str, str]]] = [] # callback, fatal error tuple (code, parameter name)
    assert len(cmdinfo.handler_list) > 0
    for cb, sig in cmdinfo.handler_list:
      cur_match = FrontendParserBase.CommandInvocationInfo(cb)
      is_parser_param_found = False
      is_state_param_found = False
      is_context_param_found = False
      is_op_param_found = False
      is_extenddata_param_found = False
      is_first_param_for_positional_args = True
      first_fatal_error : tuple[str, typing.Any] = None
      used_args : set[str] = set()
      is_positional_arg_used = len(positional_args) == 0
      is_extend_data_used = extend_data_value is None

      for name, param in sig.parameters.items():
        # 无论如何我们不接受回调函数携带 *args 或 **kwargs，因为：
        # 1.  为了以后便于进行分析和讲解，所有参数必须显式地被声明出来（包括名称与类型），参与文档生成与(早晚要进行的)语言转换
        # 2.  为了确保源文档中所有参数都被正确使用，没有参数因为意外原因被丢掉，并且保证以后的兼容性
        # 同时我们也要求所有回调函数的所有参数都带类型
        if param.annotation == inspect.Parameter.empty:
          raise RuntimeError('parameter without type annotation in frontend command handler')
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
          raise RuntimeError('*args or **kwargs in frontend command handler not supported')
        # 检查是否是一些特殊的参数
        if isinstance(param.annotation, type) and issubclass(param.annotation, FrontendParserBase):
          if is_parser_param_found:
            raise RuntimeError('More than one parser parameter found')
          is_parser_param_found = True
          cur_match.add_parameter(param, self)
          if name in kwargs:
            cur_match.add_warning('cmdparser-special-param-name-conflict', name)
          continue
        if param.annotation == self.state_type:
          if is_state_param_found:
            raise RuntimeError('More than one state parameter found')
          is_state_param_found = True
          assert isinstance(state, self.state_type)
          cur_match.add_parameter(param, state)
          if name in kwargs:
            cur_match.add_warning('cmdparser-special-param-name-conflict', name)
          continue
        if param.annotation == Context:
          if is_context_param_found:
            raise RuntimeError('More than one context parameter found')
          is_context_param_found = True
          cur_match.add_parameter(param, self.context)
          if name in kwargs:
            cur_match.add_warning('cmdparser-special-param-name-conflict', name)
          continue
        if param.annotation == GeneralCommandOp:
          if is_op_param_found:
            raise RuntimeError('More than one GeneralCommandOp parameter found')
          is_op_param_found = True
          cur_match.add_parameter(param, commandop)
          if name in kwargs:
            cur_match.add_warning('cmdparser-special-param-name-conflict', name)
          continue
        # 如果有延伸的参数的话也检查它们是否匹配
        # 因为有可能有 T1 | T2 这样的标注，我们使用 check_is_extend_data() 来获取所有可能的类型，而不是只用单个 issubclass() / isinstance()
        if extend_data_value is not None:
          candidate_type_list = self._check_is_extend_data(param.annotation)
          is_type_match = False
          for t in candidate_type_list:
            if isinstance(extend_data_value, t):
              is_type_match = True
              break
          if is_type_match:
            if is_extenddata_param_found:
              raise RuntimeError('More than one extend data parameter found')
            is_extenddata_param_found = True
            is_extend_data_used = True
            cur_match.add_parameter(param, extend_data_value)
            if name in kwargs:
              cur_match.add_warning('cmdparser-special-param-name-conflict', name)
            continue
          elif len(candidate_type_list) > 0 and param.default == inspect.Parameter.empty:
            # 这种情况下，参数的标注确实是延伸的数据类型，但是当前提供的数据不是想要的类型
            # （我们需要检查一下初值，这样如果延伸的数据是可选的，我们也不会在这过早报错）
            first_fatal_error = ('cmdparser-mismatched-type-for-extend-data', name)
            break

        # 该命令不是一个特殊参数，尝试赋值
        # 如果 kwargs (关键字参数)有现成的值的话用这个，优先级最高
        # 其次如果这是第一个参数的话，用 positional_args （位置参数）也可以
        # 如果都没有的话如果有默认值的话用默认值
        # 都没有的话就算错误，不能用这个回调函数
        # 另外如果提供了 positional_args 但是在 kwargs 里有值的话同样报错，我们只接受对第一个参数使用 positional args
        if name in kwargs:
          if is_first_param_for_positional_args and len(positional_args) > 0:
            first_fatal_error = ('cmdparser-unused-positional-args', name)
            break
          used_args.add(name)
          is_first_param_for_positional_args = False
          first_fatal_error = cur_match.try_add_parameter(param, kwargs[name])
          if first_fatal_error is not None:
            break
          continue
        if is_first_param_for_positional_args and len(positional_args) > 0:
          # 如果该参数只能以 kwargs 出现的话也报错
          if param.kind == inspect.Parameter.KEYWORD_ONLY:
            first_fatal_error = ('cmdparser-kwarg-using-positional-value', name)
            break
          is_positional_arg_used = True
          is_first_param_for_positional_args = False
          first_fatal_error = cur_match.try_add_parameter(param, positional_args)
          if first_fatal_error is not None:
            break
          continue
        if param.default != inspect.Parameter.empty:
          cur_match.add_parameter(param, param.default)
          continue
        # 没有其他来源的值了，报错
        first_fatal_error = ('cmdparser-missing-param', name)
        break
      if first_fatal_error is not None:
        unmatched_results.append((cb, first_fatal_error))
        continue
      # 检查是否有参数没用上，有的话同样报错
      if not is_positional_arg_used:
        unmatched_results.append((cb, ('cmdparser-unused-param', '<positional>')))
        continue
      if not is_extend_data_used:
        # 即使命令直接使用 GeneralCommandOp 来读取延伸参数，只要它没有显式声明对延伸参数的引用，我们都不认为这是成功的匹配
        # （加一个不被使用的参数没有影响，但是其他命令可能只用 GeneralCommandOp 而不使用延伸参数，我们想找到这样的情况）
        unmatched_results.append((cb, ('cmdparser-unused-param', '<extenddata>')))
        continue
      for name, value in kwargs.items():
        if name not in used_args:
          first_fatal_error = ('cmdparser-unused-param', name)
          break
      if first_fatal_error is not None:
        unmatched_results.append((cb, first_fatal_error))
        continue
      # 所有检查全部通过，该调用可用
      matched_results.append(cur_match)
    assert len(matched_results) + len(unmatched_results) == len(cmdinfo.handler_list)
    if len(matched_results) == 0:
      return self.handle_command_no_match(state, commandop, cmdinfo, unmatched_results)
    if len(matched_results) == 1:
      return self.handle_command_unique_invocation(state, commandop, cmdinfo, matched_results[0], unmatched_results)
    return self.handle_command_ambiguous(state, commandop, cmdinfo, matched_results, unmatched_results)


  def handle_command_unrecognized(self, state : ParserStateType, op : GeneralCommandOp, opname : str) -> None:
    err = ErrorOp('', op.location, 'cmdparser-unrecognized-cmdname', StringLiteral.get('Command name not found: ' + opname, self.context))
    err.insert_before(op)

  def visit_op(self, state : ParserStateType, op : Operation) -> None:
    if isinstance(op, GeneralCommandOp):
      self.handle_command_op(state, op)
    else:
      for r in op.regions:
        for b in r.blocks:
          for op in b.body:
            self.visit_op(state, op)

def _try_convert_parameter_list(member_type : type | types.UnionType | typing._GenericAlias, value : typing.Any) -> typing.Any:
  result = []
  # 开始搞输入
  if isinstance(value, list):
    for v in value:
      cur_value = _try_convert_parameter(member_type, v)
      if cur_value is None:
        return None
      result.append(cur_value)
  else:
    cur_value = _try_convert_parameter(member_type, value)
    if cur_value is None:
      return None
    result.append(cur_value)
  return result

# 我们需要访问 typing._GenericAlias, typing._SpecialGenericAlias, 和 <enum>._translate()
# pylint: disable=protected-access
def _try_convert_parameter(ty : type | types.UnionType | typing._GenericAlias, value : typing.Any) -> typing.Any:
  # 如果类型标注是 typing.List[...] 这种的话，ty 的值会是像 typing._GenericAlias 的东西，这不算 type
  # 如果类型标注是 list[...] 这种的话， ty 的值会是像 types.GenericAlias 的东西，这是 type
  # 如果类型标注是 X | Y | ... 这种的话， ty 的值会是 types.UnionType，这也不是 type
  if isinstance(ty, types.GenericAlias) or isinstance(ty, typing._GenericAlias):
    if ty.__origin__ != list:
      # 我们只支持 list ，不支持像是 dict 等
      raise RuntimeError('Generic alias for non-list types not supported')
    if len(ty.__args__) != 1:
      # list[str] 可以， list[int | str] 可以， list[int, str] 不行
      raise RuntimeError('List type should have exactly one argument specifying the element type (can be union though)')
    return _try_convert_parameter_list(ty.__args__[0], value)

  if ty == list or isinstance(ty, typing._SpecialGenericAlias):
    # 这种情况下标注要么是 list 要么是 typing.List，都没有带成员类型
    raise RuntimeError('List type should specify the element type (e.g., list[str] or list[str | int])')

  if isinstance(ty, types.UnionType):
    for candidate_ty in ty.__args__:
      cur_result = _try_convert_parameter(candidate_ty, value)
      if cur_result is not None:
        return cur_result
    return None

  # 剩余的情况下， ty 都应该是 type
  # 如果这里报错的话请检查类型标注是否有问题
  assert isinstance(ty, type)

  # 参数类型是 list 的情况处理完了，到这应该不会要有复合的输入
  # 如果现在值是 list ，那么我们预计只有一项内容，我们将它展开
  if isinstance(value, list):
    if len(value) != 1:
      return None
    value = value[0]

  if isinstance(value, ty):
    return value

  # 到这里我们现在支持如下类型：
  # 整数型、浮点数型（仅作为输出，不作为输入）
  # 枚举类型（仅输出，可由字符串转换得来）
  # 延伸参数类型与调用表达式（不支持转换为其他类型，调用表达式可由文本、字符串转换得来）
  # 文本、字符串（可以转换成所有不是延伸参数类型的类型）

  if issubclass(ty, ExtendDataExprBase):
    # 如果类型不一致的话我们无法转换该类型的值
    return None

  # 此时如果输入类型是 ExtendDataExprBase 或者 CallExprOperand 的话，我们应该无法对其做转化了
  if isinstance(value, ExtendDataExprBase) or isinstance(value, CallExprOperand):
    return None

  # 此时输入类型应该只会是纯文本
  # 输出类型除了文本、字符串、整数、浮点数之外，还可能有调用表达式和枚举类型（需要从字符串转过去）

  # 首先把非基本类型的字符串解决了
  if ty == TextFragmentLiteral and isinstance(value, StringLiteral):
    context = value.get_context()
    return TextFragmentLiteral.get(context, value, TextStyleLiteral.get((), context))

  # 其他类型都可以从字符串转换过去，这里先将值转为字符串
  value_str = ''
  if isinstance(value, TextFragmentLiteral):
    value_str = value.get_string()
  elif isinstance(value, StringLiteral):
    value_str = value.get_string()
  else:
    raise NotImplementedError('Unexpected input value type')

  if ty == str:
    return value_str
  if ty == int:
    return int(value_str)
  if ty == float:
    return float(value_str)
  if ty == CallExprOperand:
    return CallExprOperand(name = value_str, args = [], kwargs = collections.OrderedDict())
  if issubclass(ty, enum.Enum):
    if not hasattr(ty, '_translate'):
      raise RuntimeError('Enum parameter not registered with @FrontendParamEnum')
    return ty._translate(value_str)

  raise NotImplementedError('Unexpected output value type')
