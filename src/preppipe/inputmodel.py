# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

"""Abstraction for input sources"""


##
# @namespace preppipe.inputmodel
# @~english @brief Abstraction for input sources
# @~chinese @brief 输入内容的抽象层
# @~
#
# **TESTBOLD**
#
# <details open>
# <summary>English</summary>
# Test detailed doc
# </details>
#
# <details open>
# <summary>中文</summary>
# 测试中文
# </details>
# 
# 
#

##
# @file preppipe/inputmodel.py
# @~english @brief See preppipe.inputmodel for documentation
# @~chinese @brief 请从 preppipe.inputmodel 查看文档
# @~

# from tabnanny import check
# from tkinter.font import names
import typing
import PIL.Image
import importlib
import hashlib
import enum

from .irbase import *
from .commontypes import *

class IMElementOp(Operation):
  # InputModel 中代表内容的Operation (可能是文本也可能是图案等）。这个类将内容的值与位置信息组合起来。
  _content_operand : OpOperand
  def __init__(self, name: str, loc: Location, content : Value, **kwargs) -> None:
    super().__init__(name = name, loc = loc, **kwargs)
    self._content_operand = self._add_operand_with_value('content', content)
  
  @property
  def content(self):
    return self._content_operand
    
class IMErrorElementOp(ErrorOp):
  # 该类代表读取中发生的错误
  # 内容项是对内容的最合适的形式的表述，错误项是关于该错误的字符串描述
  #_error_operand : OpOperand
  _content_operand : OpOperand
  
  def __init__(self, name: str, loc: Location, content : Value, error_code : str, error_msg : ConstantString = None, **kwargs) -> None:
    super().__init__(name = name, loc = loc, error_code=error_code, error_msg=error_msg, **kwargs)
    self._content_operand = self._add_operand_with_value('content', content)

  @property
  def content(self):
    return self._content_operand

class IMFrameOp(Operation):
  # frame 代表一个文档或文本框的顶层结构
  # 我们使用 IR 的 block 来代表文档内的一个 block，所以不需要专门的类；这些 block 将直接在 body 区内
  # (在前端，刚开始生成时，一个块代表一段（<p>），块内是一堆 IMElementOp)
  _body_region : Region
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._body_region = self._add_region('body')
  
  @property
  def body(self):
    return self._body_region

class IMListOp(Operation):
  # 该类代表一个列表(bullet point list / numbered list)
  # 虽然list也可作为资源（asset），但由于这样的列表可能会生成不同的结构（比如分支选项等），我们在前端先用这个类来表述，之后如果确定以资源的方式生成的话再把它们打包成资源。
  # 大部分的列表应该会被生成成其他东西，以表格活不到VNModel
  # 每个选项均是一个区
  _is_numbered : bool # is the list element numbered (i.e., instead of bulleted)
  
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)
    self._is_numbered = False
    self._add_intrinsic_attr('IsNumbered', 'is_numbered')
  
  def get_item_region_name(self, index : int) -> str:
    return str(index)

  def get_num_items(self) -> int:
    return self.get_num_regions()
  
  @property
  def is_numbered(self) -> bool:
    return self._is_numbered
  
  @is_numbered.setter
  def is_numbered(self, v : bool) -> None:
    self._is_numbered = v
  
  def add_list_item(self, start_base : int = 1) -> Region:
    index = self.get_num_items() + start_base
    return self._add_region(str(index))
  
  def get_item(self, index : int) -> Region:
    return self.get_region(self.get_item_region_name(index))
  
  def take_list_item(self, list_item : Region):
    name = ''
    if list_item.parent is not None:
      name = list_item.name
      list_item.remove_from_parent()
    if len(name) == 0 or name in self._regions:
      # create a new name
      index = self.get_num_items() + 1
      name = str(index)
      while name in self._regions:
        index += 1
        name = str(index)
    self._take_region(list_item, name)
  
  @property
  def body(self):
    return self._body

class IMDocumentOp(IMFrameOp):
  # 该类代表一个完整的文档
  #_namespace : str # 该文档所处的命名空间
  
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    # loc 包含了该文档文件的路径； name 被作为默认工程名或函数名使用
    super().__init__(name, loc, **kwargs)
  #  self._add_intrinsic_attr('Namespace', 'namespace')
  
  #@property
  #def namespace(self):
  #  return self._namespace
  
  #@namespace.setter
  #def namespace(self, v : str):
  #  self._namespace = v

class InputModelV2(Operation):
  _content : Region
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    # name 作为项目名，loc 是初始目录的位置
    super().__init__(name, loc, **kwargs)
    self._content = self._add_region('content')
  
  @property
  def content(self):
    return self._content

class IMSettings:
  # 该类用于存储所有在读取阶段有关的设置，读取完毕后可扔
  
  # 审计相关的部分
  # 如果运行该程序的系统不属于输入文件的作者，我们用这类审计手段来限制可访问的文件的范围
  _accessible_directories_whitelist : list[str] # 绝对路径,按搜索顺序排列
  
  def add_search_path(self, v : str):
    if os.path.isdir(v):
      self._accessible_directories_whitelist.append(os.path.abspath(v))
  
  def search(self, querypath : str, basepath : str, filecheckCB : callable) -> typing.Any:
    # querypath 是申请访问的文件名（来自文档内容，不可信），可能含后缀也可能不含，可能是绝对路径也可能是相对路径
    # basepath 是访问发起的文件路径，绝对路径
    # filecheckCB 是回调函数，接受一个绝对路径，若文件不符合要求则返回 None ，如果符合则返回任意非 None 的值，作为该 search() 的返回值
    raise NotImplementedError()
  
  def __init__(self) -> None:
    self._accessible_directories_whitelist = []

class IMParseCache:
  # 该类用于暂时存储设置，读取完毕后可扔
  _ctx : Context
  _extern_asset_dict : dict[str, AssetData] # 避免反复对同一个外部资源创建资源类实例
  
  def __init__(self, ctx : Context) -> None:
    self._ctx = ctx
  
  def query_image_asset(self, abspath : str) -> ImageAssetData:
    # abspath 应已通过审查
    raise NotImplementedError()
