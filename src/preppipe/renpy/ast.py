# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from ..irbase import *

# 在此我们定义 RenPy 语法的一个子集，以供我们对 Renpy 进行生成
# （有朝一日应该也能把读取 Renpy 的功能做进来吧。。）
# 我们使用 IR 形式组成 AST 的结构，这样便于我们使用 IR 提供的一系列功能

#-----------------------------------------------------------
# 抽象基类
#-----------------------------------------------------------

class RenPyNode(IListNode):
  # 代表一个 AST 节点的基类，对应 renpy 的 renpy/ast.py
  # https://github.com/renpy/renpy/blob/master/renpy/ast.py#L558

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)

  @property
  def parent(self) -> RenPyNode:
    return super().parent

class RenPyBlockNode(IListNode):
  # 所有有 body 的节点的基类
  _body : IList[RenPyNode, RenPyNode]

  def __init__(self, **kwargs) -> None:
    super().__init__(**kwargs)
    self._body = IList(self)
  
  @property
  def body(self) -> IList[RenPyNode, RenPyNode]:
    return self._body

#-----------------------------------------------------------
# 特殊对象
#-----------------------------------------------------------

class RenPyPyCodeObject:
  # 源码：https://github.com/renpy/renpy/blob/master/renpy/ast.py#L448
  # ...不过我们只存一堆字符串作为源代码
  code : list[str]
  pass

#-----------------------------------------------------------
# 控制类节点
#-----------------------------------------------------------

class RenPyInitNode(RenPyBlockNode):
  # RenPy 的 init 块
  # 除了优先级外基本上只有个 body
  # 源码：https://github.com/renpy/renpy/blob/master/renpy/ast.py#L978
  priority : int
  pass

class RenPyLabelNode(RenPyBlockNode):
  # 主文章：RenPy Labels & Control Flow
  # https://www.renpy.org/doc/html/label.html#labels-control-flow
  # 源码：https://github.com/renpy/renpy/blob/master/renpy/ast.py#L1017
  name : str
  parameters: RenPyNode
  pass

class RenPyPythonNode(RenPyNode):
  # 普通的内嵌 Python 代码块
  # Python 的代码块由 RenPyPyCodeObject 代表，所以这个节点没有 body
  # 源码：https://github.com/renpy/renpy/blob/master/renpy/ast.py#L1090
  code : RenPyPyCodeObject
  hide : bool # 是否使用局部词典、避免污染上层环境的变量词典
  pass

class RenPyEarlyPythonNode(RenPyNode):
  # python early 块
  # 在 Screen 的文档这里有提及： https://www.renpy.org/doc/html/screen_python.html
  # 源码：https://github.com/renpy/renpy/blob/master/renpy/ast.py#L1146
  code : RenPyPyCodeObject
  hide : bool # 是否使用局部词典、避免污染上层环境的变量词典
  pass

#-----------------------------------------------------------
# 指令类节点
#-----------------------------------------------------------

class RenpySayNode(RenPyNode):
  # 主文章: RenPy Dialogue and Narration
  # https://www.renpy.org/doc/html/dialogue.html#dialogue-and-narration
  # 源码: https://github.com/renpy/renpy/blob/master/renpy/ast.py#L779

  # <who> [<attribute>] [@ <temporary attribute>] <what>
  who: RenPyNode
  what : RenPyNode
  attributes : RenPyNode
  temporary_attributes : RenPyNode
  pass

