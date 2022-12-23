# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
 

from __future__ import annotations

from ..irbase import *
from ..inputmodel import *
from ..nameresolution import NameResolver, NamespaceNode

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
def CommandDecl(ns: FrontendCommandNamespace, name : str, alias : typing.Dict[str | typing.Tuple[str], typing.Dict[str, str]] = {}):
  def decorator_parsecommand(func):
    # register the command
    ns.register_command(func, name, alias)
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
  handler_list : typing.List[callable] # 所有的实现都在这里

class FrontendCommandNamespace(NamespaceNode[FrontendCommandInfo]):
  
  @staticmethod
  def create(parent : FrontendCommandNamespace | None, cname : str) -> FrontendCommandNamespace:
    if parent is None:
      parent = FrontendCommandRegistry.get_global_namespace()
    return FrontendCommandNamespace(FrontendCommandRegistry.get_registry(), parent, cname)
  
  def __init__(self, tree: FrontendCommandRegistry, parent: FrontendCommandNamespace, cname: str | None) -> None:
    super().__init__(tree, parent, cname)
  
  def register_command(self, func : callable, name : str, alias : typing.Dict[str, typing.Dict[str, str]]) -> None:
    cur_entry = self.lookup_name(name)
    if isinstance(cur_entry, FrontendCommandNamespace):
      raise RuntimeError('Name collision between namespace and command entry: "' + name + '"')
    if cur_entry is None:
      cur_entry = FrontendCommandInfo(cname = name, aliases = {}, parameter_alias_dict={}, handler_list=[])
      self.add_data_entry(name, cur_entry)
    assert cur_entry.cname == name
    cur_entry.handler_list.append(func)
    # 把别名信息合并进去
    # 我们需要同时处理 aliases 和 parameter_alias_dict
    for name_alias, param_alias_dict in alias.items():
      assert isinstance(name_alias, str)
      assert isinstance(param_alias_dict, dict)
      existing_dict = None
      if name_alias not in cur_entry.aliases:
        self.add_local_alias(name, name_alias)
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
  

_frontend_command_registry = FrontendCommandRegistry()

# ------------------------------------------------------------------------------

class ParserBase:
  
  @dataclasses.dataclass
  class CommandInfo:
    callback: callable
    name : str
    name_aliases : typing.Tuple[str]
    parameter_aliases : typing.Dict[str, str]
    
  # 每个子类私有的静态变量 class variables
  __command_table : typing.ClassVar[typing.Dict[str, CommandInfo]] = {} # name -> info
  __command_alias_dict : typing.ClassVar[typing.Dict[str, str]] = {} # alias -> name
  
  __command_domain : typing.ClassVar[typing.Tuple[str]] = ()
  
  
  # 子类实例的成员变量 instance variables
  _ctx : Context
  
  def __init__(self, ctx : Context) -> None:
    self._ctx = ctx
  
  @property
  def context(self) -> Context:
    return self._ctx
  
  # 每个子类都应该定义相同的 get_command_domain(), 确保下游的子类能够使用该函数取得当前类的命令域
  @staticmethod
  def get_command_domain():
    return ParserBase.__command_domain
  
  @classmethod
  def register_command(cls, callback : callable, name : str, alias : typing.Dict[str, typing.Dict[str, str]]):
    # TODO
    pass
  
  
  
  # 我们定义两种类型的命令，一种是所有参数都可以
  def invoke_custom_parsed_command(self, command_name : str, _command_domain : typing.Tuple[str], callback : callable, command_op : GeneralCommandOp):
    return callback(self, command_op)
  
  def invoke_general_command(self, _command_name : str, _command_domain : typing.Tuple[str], callback : callable, command_op : GeneralCommandOp, *args, **kwargs):
    return callback(self, command_op, *args, **kwargs)

class VNParser(ParserBase):
  # TODO move to separate file
  __command_table : typing.List[str] = [*ParserBase.__command_table, 'vnmodel']