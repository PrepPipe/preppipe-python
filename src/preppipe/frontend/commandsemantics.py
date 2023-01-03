# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
 

from __future__ import annotations

from ..irbase import *
from ..inputmodel import *
from ..nameresolution import NameResolver, NamespaceNode
from .commandsyntaxparser import GeneralCommandOp, CMDValueSymbol, CMDPositionalArgOp
import inspect
import types

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
def CommandDecl(ns: FrontendCommandNamespace, imports : dict[str, typing.Any], name : str, alias : typing.Dict[str | typing.Tuple[str], typing.Dict[str, str]] = {}):
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

@dataclasses.dataclass
class FrontendCommandInfo:
  # 为了支持函数重载，我们需要在同一个命令下绑定多个用于实现的函数以及他们的别名
  # 为方便起见，我们要求参数的所有别名必须一致(同一个规范名不能有多个别名)
  cname : str # 命令的规范名
  aliases : typing.Dict[str | typing.Tuple[str], typing.Dict[str, str]] # 所有 aliases 注册项合并后的结果，第一个 key 是命令名的别名，后面的key是参数规范名
  parameter_alias_dict : typing.Dict[str, str] # 从参数的别名到规范名
  handler_list : list[tuple[callable, inspect.Signature]] # 所有的实现都在这里

class FrontendCommandNamespace(NamespaceNode[FrontendCommandInfo]):
  
  @staticmethod
  def create(parent : FrontendCommandNamespace | None, cname : str) -> FrontendCommandNamespace:
    if parent is None:
      parent = FrontendCommandRegistry.get_global_namespace()
    return FrontendCommandNamespace(FrontendCommandRegistry.get_registry(), parent, cname)
  
  def __init__(self, tree: FrontendCommandRegistry, parent: FrontendCommandNamespace, cname: str | None) -> None:
    super().__init__(tree, parent, cname)
  
  def register_command(self, func : callable, imports : dict[str, typing.Any], name : str, alias : typing.Dict[str, typing.Dict[str, str]]) -> None:
    cur_entry = self.lookup_name(name)
    if isinstance(cur_entry, FrontendCommandNamespace):
      raise RuntimeError('Name collision between namespace and command entry: "' + name + '"')
    if cur_entry is None:
      cur_entry = FrontendCommandInfo(cname = name, aliases = {}, parameter_alias_dict={}, handler_list=[])
      self.add_data_entry(name, cur_entry)
    assert cur_entry.cname == name
    # 如果在这里报错（无法解析类型名）的话，请确保：
    # 1. 定义命令的源文件可以在没有 from __future__ import annotations 的情况下顺利使用类型标注
    # 2. 所有在回调函数参数类型的标注中的类全都在 imports 中（不过 imports 也可以为空）
    sig = inspect.signature(func, globals=imports, eval_str=True)
    cur_entry.handler_list.append((func, sig))
    # 把别名信息合并进去
    # 我们需要同时处理 aliases 和 parameter_alias_dict
    for name_alias, param_alias_dict in alias.items():
      assert isinstance(name_alias, str) or isinstance(name_alias, tuple)
      assert isinstance(param_alias_dict, dict)
      existing_dict = None
      if name_alias not in cur_entry.aliases:
        if isinstance(name_alias, str):
          self.add_local_alias(name, name_alias)
        elif isinstance(name_alias, tuple):
          for a in name_alias:
            assert isinstance(a, str)
            self.add_local_alias(name, a)
        else:
          raise RuntimeError('Unexpected name alias type')
        existing_dict : typing.Dict[str, str] = {}
        cur_entry.aliases[name_alias] = existing_dict
      else:
        existing_dict = cur_entry.aliases[name_alias]
      for param_cname, param_alias_name in param_alias_dict.items():
        assert isinstance(param_alias_name, str)
        assert isinstance(param_cname, str)
        if param_cname in existing_dict:
          if existing_dict[param_cname] != param_alias_name:
            raise RuntimeError('Parameter "' + param_cname + '" already has a different alias: "' + existing_dict[param_cname] + '" != "' + param_alias_name + '"')
        else:
          existing_dict[param_cname] = param_alias_name
          if param_alias_name in cur_entry.parameter_alias_dict:
            existing_cname = cur_entry.parameter_alias_dict[param_alias_name]
            if existing_cname != param_cname:
              raise RuntimeError('Conflicting alias for parameter "' + param_cname + '": "' + existing_cname + '" != "' + param_cname + '"')
          else:
            cur_entry.parameter_alias_dict[param_alias_name] = param_cname
    

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
    self.set_root(self._global_ns)
  

_frontend_command_registry = FrontendCommandRegistry()

# ------------------------------------------------------------------------------

class FrontendParserBase:
  # 该类的实例记录了解析过程中用到的信息，可能有多个该类的实例对应同一个前端命令空间
  # 前端命令空间某种意义上是解析器类的一部分静态数据，因为命令的实际实现必定与解析器内部紧密相关
  # 我们把前端命令空间与解析器实现区分开主要有以下两个目的：
  # 1.  可以对命令的语义与实现进行分隔，以后若有更加合适的实现算法可以无缝衔接
  # 2.  命令名称解析可以复用
  # 我们要求命令的处理函数必须是一个独立的函数而不是绑定解析器类的成员函数，为了实现以下目标：
  # 1.  方便理解、方便后续改动。python 语言特性用的太复杂容易劝退新人
  # 2.  便于在不改解析器类源代码的基础上新增命令，用于实现类似宏的效果。用户可以在自己的脚本里新增命令。

  _ctx : Context
  _command_ns : FrontendCommandNamespace
  
  def __init__(self, ctx : Context, command_ns : FrontendCommandNamespace) -> None:
    self._ctx = ctx
    self._command_ns = command_ns
  
  # 不管怎样我们都需要提供这两个接口来方便新的外部的实现
  
  @property
  def context(self) -> Context:
    return self._ctx
  
  @property
  def command_ns(self) -> FrontendCommandNamespace:
    return self._command_ns
  
  def lookup(self, name : str, using_path : typing.List[typing.Tuple[str]] = []):
    return self.command_ns.namespace_tree.unqualified_lookup(name, self.command_ns.namespace_path, using_path)
  
  def handle_command_op(self, op : GeneralCommandOp):
    head_symbol_table = op.get_symbol_table('head')
    namesymbol = head_symbol_table.get('name')
    assert isinstance(namesymbol, CMDValueSymbol)
    opname = namesymbol.value
    assert isinstance(opname, ConstantString)
    # 目前我们不定义 fully qualified lookup，因为貌似没有适合作为命名空间分隔符的字符。。。
    lookup_result = self.lookup(opname.value)
    if lookup_result is None:
      self.handle_command_unrecognized(op, opname.value)
      return
    assert isinstance(lookup_result, FrontendCommandInfo)
    return self.handle_command_invocation(op, lookup_result)
  
  def handle_command_ambiguous(self, commandop : GeneralCommandOp, cmdinfo : FrontendCommandInfo,
                               matched_results : typing.List[typing.Tuple[callable, typing.List[typing.Any], typing.Dict[str, typing.Any], typing.List[typing.Tuple[str, typing.Any]]]],
                               unmatched_results : typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    # 但且仅当不止一个回调函数满足调用条件时发生
    pass
  
  def handle_command_unique_invocation(self, commandop : GeneralCommandOp, cmdinfo : FrontendCommandInfo,
                                       target_cb : callable,
                                       target_args : typing.List[typing.Any],
                                       target_kwargs : typing.Dict[str, typing.Any],
                                       target_warnings : typing.List[typing.Tuple[str, typing.Any]],
                                       unmatched_results : typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    # 仅当正好只有一个回调函数满足条件时发生
    pass
  
  def handle_command_no_match(self, commandop : GeneralCommandOp, cmdinfo : FrontendCommandInfo, unmatched_results : typing.List[typing.Tuple[callable, typing.Tuple[str, str]]]):
    # 没有回调函数满足条件时发生
    pass
  
  def handle_command_invocation(self, commandop : GeneralCommandOp, cmdinfo : FrontendCommandInfo):
    # 从所有候选命令实现中找到最合适的，并进行调用
    # 首先把参数准备好
    positional_args = []
    posarg_block = commandop.get_region('positional_arg').entry_block
    for op in posarg_block.body:
      assert isinstance(op, CMDPositionalArgOp)
      positional_args.append(op.value)
    kwargs_region = commandop.get_symbol_table('keyword_arg')
    kwargs = {}
    for op in kwargs_region:
      assert isinstance(op, CMDValueSymbol)
      name = op.name
      value = op.value
      if name in cmdinfo.parameter_alias_dict:
        name = cmdinfo.parameter_alias_dict[name]
      kwargs[name] = value
    # 然后遍历所有项，找到所有能调用的回调函数
    matched_results : typing.List[typing.Tuple[callable, typing.List[typing.Any], typing.Dict[str, typing.Any], typing.List[typing.Tuple[str, typing.Any]]]] = [] # <callback, args, kwargs, warning>
    unmatched_results : typing.List[typing.Tuple[callable, typing.Tuple[str, str]]] = [] # callback, fatal error tuple (code, parameter name)
    assert len(cmdinfo.handler_list) > 0
    for cb, sig in cmdinfo.handler_list:
      is_parser_param_found = False
      is_context_param_found = False
      is_op_param_found = False
      target_args = []
      target_kwargs = {}
      warnings : typing.List[typing.Tuple[str, typing.Any]] = []
      is_first_param_for_positional_args = True
      first_fatal_error : typing.Tuple[str, typing.Any] = None
      used_args : typing.Set[str] = set()
      is_positional_arg_used = False
      if len(positional_args) == 0:
        is_positional_arg_used = True
      
      def add_parameter(name : str, param : inspect.Parameter, value : typing.Any) -> None:
        match param.kind:
          case inspect.Parameter.VAR_POSITIONAL | inspect.Parameter.VAR_KEYWORD:
            raise RuntimeError('Not expecting assignment to *arg / **kwarg')
          case inspect.Parameter.POSITIONAL_ONLY:
            target_args.append(value)
          case inspect.Parameter.POSITIONAL_OR_KEYWORD | inspect.Parameter.KEYWORD_ONLY:
            target_kwargs[name] = value
          case _:
            raise NotImplementedError()
      def check_special_param_conflict(name : str) -> None:
        if name in kwargs:
          warningcode = 'cmdparser-special-param-name-conflict'
          warnings.append((warningcode, name))
      def try_add_parameter(param : inspect.Parameter, value : typing.Any) -> typing.Tuple[str, typing.Any] | None:
        # 尝试把给定的值赋予参数
        # 如果有错误的话返回错误
        target_value = _try_convert_parameter(param.annotation, value)
        if target_value is None:
          return ('cmdparser-param-conversion-failed', param.name)
        add_parameter(param.name, param, target_value)
        return

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
        if issubclass(param.annotation, FrontendParserBase):
          if is_parser_param_found:
            raise RuntimeError('More than one parser parameter found')
          is_parser_param_found = True
          add_parameter(name, param, self)
          check_special_param_conflict(name)
          continue
        if param.annotation == Context:
          if is_context_param_found:
            raise RuntimeError('More than one context parameter found')
          is_context_param_found = True
          add_parameter(name, param, self.context)
          check_special_param_conflict(name)
          continue
        if issubclass(param.annotation, GeneralCommandOp):
          if is_op_param_found:
            raise RuntimeError('More than one GeneralCommandOp parameter found')
          is_op_param_found = True
          add_parameter(name, param, commandop)
          check_special_param_conflict(name)
          continue
        
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
          first_fatal_error = try_add_parameter(param, kwargs[name])
          if first_fatal_error is not None:
            break
          continue
        if is_first_param_for_positional_args and len(positional_args) > 0:
          # 如果该参数只能以 kwargs 出现的话也报错
          if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            first_fatal_error = ('cmdparser-kwarg-using-positional-value', name)
            break
          is_positional_arg_used = True
          is_first_param_for_positional_args = False
          first_fatal_error = try_add_parameter(param, positional_args)
          if first_fatal_error is not None:
            break
          continue
        if param.default != inspect.Parameter.empty:
          add_parameter(name, param, param.default)
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
      for name, value in kwargs.items():
        if name not in used_args:
          first_fatal_error = ('cmdparser-unused-param', name)
          break
      if first_fatal_error is not None:
        unmatched_results.append((cb, first_fatal_error))
        continue
      # 所有检查全部通过，该调用可用
      t = (cb, target_args, target_kwargs, warnings)
      matched_results.append(t)
    assert len(matched_results) + len(unmatched_results) == len(cmdinfo.handler_list)
    if len(matched_results) == 0:
      return self.handle_command_no_match(commandop, cmdinfo, unmatched_results)
    if len(matched_results) == 1:
      matched_tuple = matched_results[0]
      target_cb = matched_tuple[0]
      target_args = matched_tuple[1]
      target_kwargs = matched_tuple[2]
      target_warnings = matched_tuple[3]
      return self.handle_command_unique_invocation(commandop, cmdinfo, target_cb, target_args, target_kwargs, target_warnings, unmatched_results)
    return self.handle_command_ambiguous(commandop, cmdinfo, matched_results, unmatched_results)
        
  
  def handle_command_unrecognized(self, op : GeneralCommandOp, opname : str) -> None:
    err = ErrorOp('', op.location, 'cmdparser-unrecognized-cmdname', ConstantString.get('Command name not found: ' + opname, self.context))
    err.insert_before(op)
  
  def visit_op(self, op : Operation) -> None:
    if isinstance(op, GeneralCommandOp):
      self.handle_command_op(op)
    else:
      for r in op.regions:
        for b in r.blocks:
          for op in b.body:
            self.visit_op(op)
  
  
def _try_convert_parameter(ty : type, value : typing.Any) -> typing.Any:
  # 如果类型标注是 typing.List[...] 这种的话，ty 的值会是像 typing._GenericAlias 的东西，这不算 type
  # 如果类型标注是 list[...] 这种的话， ty 的值会是像 types.GenericAlias 的东西，这是 type
  # 如果这里报错的话请检查类型标注是否有问题
  assert isinstance(ty, type)
  
  # 预计的类型有这些
  permitted_type_set_input = {ConstantString, ConstantText, ConstantTextFragment}
  permitted_elementary_type_set_output = {str, int, float, ConstantString, ConstantText, ConstantTextFragment}
  if not isinstance(value, list) and type(value) not in permitted_type_set_input:
    return None
  if not isinstance(ty, types.GenericAlias) and ty not in permitted_elementary_type_set_output:
    return None
  
  # 如果参数类型是 list 的话，确认只有一个参数类型
  if isinstance(ty, types.GenericAlias):
    assert ty.__origin__ == list
    assert len(ty.__args__) == 1
    innerty = ty.__args__[0]
    result = []
    # 开始搞输入
    if isinstance(value, list):
      for v in value:
        cur_value = _try_convert_parameter(innerty, v)
        if cur_value is None:
          return None
        result.append(cur_value)
    else:
      cur_value = _try_convert_parameter(innerty, value)
      if cur_value is None:
        return None
      result.append(cur_value) 
    return result
  
  # 参数类型是 list 的情况处理完了，到这应该不会要有复合的输入
  # 如果现在值是 list ，那么我们预计只有一项内容，我们将它展开
  if isinstance(value, list):
    return _try_convert_parameter(ty, value[0])
  
  # 以下都是从单值到单值的转换
  if type(value) == ty:
    return value
  
  # 首先把非基本类型的解决了
  if ty in [ConstantText, ConstantTextFragment, ConstantString]:
    cur_value = value
    if isinstance(value, ConstantString):
      assert ty == ConstantText or ty == ConstantTextFragment
      context = value.get_context()
      cur_value = ConstantTextFragment.get(context, value, ConstantTextStyle.get((), context))
      if ty == ConstantTextFragment:
        return cur_value
    assert ty == ConstantText
    context = cur_value.get_context()
    return ConstantText.get(context, [cur_value])

  # 基本类型都可以从字符串转换过去，这里先将值转为字符串
  value_str = ''
  if isinstance(value, ConstantText):
    value_str = value.get_string()
  elif isinstance(value, ConstantTextFragment):
    value_str = value.get_string()
  elif isinstance(value, ConstantString):
    value_str = value.value
  else:
    raise NotImplementedError('Unexpected input value type')
  
  if ty == str:
    return value_str
  if ty == int:
    return int(value_str)
  if ty == float:
    return float(value_str)
  raise NotImplementedError('Unexpected output value type')
