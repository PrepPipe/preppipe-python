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

@IRObjectJsonTypeName("im_element_op")
class IMElementOp(Operation):
  # InputModel 中代表内容的Operation (可能是文本也可能是图案等）。这个类将内容的值与位置信息组合起来。
  _content_operand : OpOperand

  def construct_init(self, *, content : Value, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_operand_with_value('content', content)

  def post_init(self) -> None:
    super().post_init()
    self._content_operand = self.get_operand_inst('content')

  @staticmethod
  def create(content : Value, name : str, loc : Location):
    return IMElementOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, content=content, name=name, loc=loc)

  @property
  def content(self):
    return self._content_operand

  @staticmethod
  def collect_text_from_paragraph(b : Block) -> tuple[str, list[AssetData]]:
    # 把给定段落（以块表示）的文本提取出来：
    # 所有文本内容都会只保留字符串
    # 所有资源会被替换成 '\0' 并加到资源列表中
    # 如果段落中有其他不是 IMElementOp 的操作项（比如命令等）则直接忽略
    return _collect_text_from_paragraph_impl(b)

@IRObjectJsonTypeName("im_err_element_op")
class IMErrorElementOp(ErrorOp):
  # 该类代表读取中发生的错误
  # 内容项是对内容的最合适的形式的表述，错误项是关于该错误的字符串描述
  #_error_operand : OpOperand
  _content_operand : OpOperand

  def construct_init(self, *, content : Value, error_code: str, error_msg: StringLiteral | None = None, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(error_code=error_code, error_msg=error_msg, name=name, loc=loc, **kwargs)
    self._add_operand_with_value('content', content)

  def post_init(self) -> None:
    super().post_init()
    self._content_operand = self.get_operand_inst('content')

  @staticmethod
  def create(name: str, loc: Location, content : Value, error_code : str, error_msg : StringLiteral | None = None):
    return IMErrorElementOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, content=content, error_code=error_code, error_msg=error_msg, name=name, loc=loc)

  @property
  def content(self):
    return self._content_operand

@IRObjectJsonTypeName("im_frame_op")
class IMFrameOp(Operation):
  # frame 代表一个文档或文本框的顶层结构
  # 我们使用 IR 的 block 来代表文档内的一个 block，所以不需要专门的类；这些 block 将直接在 body 区内
  # (在前端，刚开始生成时，一个块代表一段（<p>），块内是一堆 IMElementOp)
  _body_region : Region

  def construct_init(self, *, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_region('body')

  def post_init(self) -> None:
    super().post_init()
    self._body_region = self.get_region('body')

  @property
  def body(self):
    return self._body_region

  @staticmethod
  def create(name : str, loc : Location):
    return IMFrameOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

@IRObjectJsonTypeName("im_list_op")
class IMListOp(Operation):
  # 该类代表一个列表(bullet point list / numbered list)
  # 虽然list也可作为资源（asset），但由于这样的列表可能会生成不同的结构（比如分支选项等），我们在前端先用这个类来表述，之后如果确定以资源的方式生成的话再把它们打包成资源。
  # 大部分的列表应该会被生成成其他东西，以表格活不到VNModel
  # 每个选项均是一个区

  def construct_init(self, *, name: str = '', loc: Location | None = None, **kwargs) -> None:
    super().construct_init(name=name, loc=loc, **kwargs)
    self.set_attr('IsNumbered', False)

  def get_item_region_name(self, index : int) -> str:
    return str(index)

  def get_num_items(self) -> int:
    return self.get_num_regions()

  @property
  def is_numbered(self) -> bool:
    v = self.get_attr('IsNumbered')
    assert isinstance(v, bool)
    return v

  @is_numbered.setter
  def is_numbered(self, v : bool) -> None:
    self.set_attr('IsNumbered', v)

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

  @staticmethod
  def create(name : str, loc : Location):
    return IMListOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

@IRObjectJsonTypeName("im_document_op")
class IMDocumentOp(IMFrameOp):
  # 该类代表一个完整的文档

  @staticmethod
  def create(name : str, loc : Location):
    return IMDocumentOp(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

class InputModelV2(Operation):
  _content : Region

  def construct_init(self, *, name: str = '', loc: Location | None = None, **kwargs) -> None:
    # name 作为项目名，loc 是初始目录的位置
    super().construct_init(name=name, loc=loc, **kwargs)
    self._add_region('content')

  def post_init(self) -> None:
    super().post_init()
    self._content = self.get_region('content')

  @property
  def content(self):
    return self._content

  @staticmethod
  def create(name : str, loc : Location):
    return InputModelV2(init_mode=IRObjectInitMode.CONSTRUCT, context=loc.context, name=name, loc=loc)

class IMSettings:
  # 该类用于存储所有在读取阶段有关的设置，读取完毕后可扔

  # 审计相关的部分
  # 如果运行该程序的系统不属于输入文件的作者，我们用这类审计手段来限制可访问的文件的范围
  _accessible_directories_whitelist : list[str] # 绝对路径,按搜索顺序排列

  def add_search_path(self, v : str):
    if os.path.isdir(v):
      self._accessible_directories_whitelist.append(os.path.abspath(v))

  def check_is_path_accessible(self, abspath : str) -> bool:
    # 检查 abspath 是否为目录白名单中之一
    # TODO 现在还是暂时不做这个
    return True

  def search(self, querypath : str, basepath : str, filecheckCB : typing.Callable) -> typing.Any:
    # querypath 是申请访问的文件名（来自文档内容，不可信），可能含后缀也可能不含，可能是绝对路径也可能是相对路径
    # basepath 是访问发起的文件路径，绝对路径
    # filecheckCB 是回调函数，接受一个绝对路径，若文件不符合要求则返回 None ，如果符合则返回任意非 None 的值，作为该 search() 的返回值
    raise NotImplementedError()

  def __init__(self) -> None:
    self._accessible_directories_whitelist = []

def _collect_text_from_paragraph_impl(b : Block) -> tuple[str, list[AssetData]]:
  content_str = ''
  asset_list : typing.List[AssetData] = []
  for op in b.body:
    # 忽略所有非语义消息
    if isinstance(op, MetadataOp):
      continue
    if not isinstance(op, IMElementOp):
      # 碰到了一项非内容的，直接忽略
      continue
    # 找到了一项内容
    # 尝试读取内容并组成命令文本
    assert isinstance(op, IMElementOp)
    content_operand : OpOperand = op.content
    for i in range(0, content_operand.get_num_operands()):
      v = content_operand.get(i)
      if isinstance(v, TextFragmentLiteral):
        content_str += v.get_string()
      elif isinstance(v, TextLiteral):
        content_str += v.get_string()
      elif isinstance(v, AssetData):
        content_str += '\0'
        asset_list.append(v)
      else:
        raise NotImplementedError('TODO support other possible element types in IMElementOp')

  return (content_str, asset_list)