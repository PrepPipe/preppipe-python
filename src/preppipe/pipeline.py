# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import sys
import os
import time
import importlib
import importlib.util
import traceback

from .irbase import *
from .util.audit import *
from ._version import __version__
from .language import TranslationDomain, Translatable
from .exceptions import *

# 这里提供一个类似 clang cc1 的界面，我们在这里支持详细的命令行设定
# driver 以后就提供一个更简单易用的界面

# ------------------------------------------------------------------------------
# 接口
# ------------------------------------------------------------------------------

# stage : 大致描述该步的输入输出特征
  # name : 启用该步的命令行
  # arg_title, arg_desc: 用于创建命令组的标题与描述（将会是 ArgumentParser.add_argument_group() 的参数）
  # ir_input_op, ir_output_op: 使用IR作为输入输出时，IR的类型要求。输入IR可以不止一种类型，输出必须是一种


class TransformBase:
  @staticmethod
  def install_arguments(argument_group : argparse._ArgumentGroup):
    # 给命令行解析器（ArgumentParser）添加专属于该转换的参数
    # 只会在注册时提供了 arg_title 的情况下调用
    pass

  @staticmethod
  def handle_arguments(args : argparse.Namespace):
    # 当命令行解析完毕后，如果该转换被启用，则该函数负责读取该转换所使用的参数
    # 只会在注册时提供了 arg_title 的情况下调用
    pass

  _ctx : Context
  _inputs : typing.List[Operation | str]
  _output : str

  def __init__(self, ctx : Context) -> None:
    # 此基类不会使用这些参数，子类在创建时应使用这样的参数列表
    # ctx: 所有 IR 共用的 Context
    self._ctx = ctx
    self._inputs = []
    self._output = ''

  def set_input(self, inputs: typing.List[Operation | str]) -> None:
    # 设置输入（不管是 IR 还是文件路径）
    # inputs: （不管是IR还是其他文件、路径参数的）输入，即使是单个也是一个 list
    # 该函数一定会在 run() 之前被调用一次，但是与 set_output_path() 的调用没有必然的先后
    self._inputs = inputs

  def set_output_path(self, output : str):
    # 设置输出（一个路径）
    # 只有输出不是IR的转换会被调用该函数，输出是 IR 的话下面的 run() 的返回值才是输出
    # 如果该函数被调用，则一定在 run() 之前被调用，并且最多调用一次
    self._output = output

  def run(self) -> Operation | typing.List[Operation] | None:
    # 执行该转换
    # 如果该转换输出IR，则返回值应该是该IR的顶层操作项
    # 如果该转换不输出IR，则不返回任何值，实现应该在 run() 返回前完成输出
    # 基本上这应该是每个转换类实例中最后一个执行的成员函数
    pass

  @property
  def inputs(self):
    return self._inputs

  @property
  def output(self):
    return self._output

  @property
  def context(self):
    return self._ctx

  def __str__(self) -> str:
    result = type(self).__name__
    iostr = ''
    if len(self.inputs) > 0:
      input_list = []
      for v in self.inputs:
        if isinstance(v, str):
          input_list.append('"' + v + '"')
        elif isinstance(v, Operation):
          input_list.append('[' + type(v).__name__ + ']"' + v.name + '"')
      iostr += TR_pipeline_input.get() + "={" + ', '.join(input_list) + '}'
    if len(self.output) > 0:
      if len(iostr) > 0:
        iostr += ', '
      iostr += TR_pipeline_output.get() + '="' + self.output + '"'
    if len(iostr) > 0:
      result += '(' + iostr + ')'
    return result

# 定义一个转换时，需要(1)定义一个 TransformBase 的子类，(2)使用以下的一个修饰符来注册它
# flag 是命令行上用来启用该转换的选项, ArgumentParser.add_arguments() 的第一个参数
# (https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.add_argument)
# 如果一个转换读取（非 IR 的）文件并生成一个 IR (顶层是 irbase 里的 Operation)，那么这是一个前端转换，用 @FrontendDecl 来注册
# 如果一个转换读取 IR 并生成非 IR 的内容，那么这是一个后端转换，用 @BackendDecl 来注册
# 如果一个转换读取的和输出的都是 IR，那么这是一个中端转换，用 @MiddleEndDecl 来注册
# （只有 MiddleEnd 中间 End 的 E 大写，其他两个都小写）
# （如果一个转换读取的和输出的都不是IR，那么它不应该出现在这。。应该是一个独立的工具）
# 修饰符所有的 input 参数都是表达输入的限制， output 参数代表输出的内容
# 如果某一项输入输出是 IR，那么 input/output 应该是顶层 Operation 的类型对象；如果任何 Operation 都可以（比如dump）那么就用 Operation 类型
# 如果某一项输入不是 IR, 那么 input/output 应该是一个 IODecl 实例来描述该转换的输入输出
#   IODecl 中的 description 用于在命令行帮助文本中描述该输入
#   IODecl 中的 match_suffix 用于在不使用该转换的选项（即该输入处于“无转换认领”的状态）时使用后缀名来查找该用哪个前端。（如果不是文件而是目录的话就算了。。）
#   IODecl 中的 nargs 用于描述该输入输出应该带多少个参数，这与 argparse 的 add_argument() 的 nargs 参数一致
#     一个正整数表示需要正好N个，'?'表示0-1个，'*'表示随便多少个，'+'表示至少一个
#     详情见 https://docs.python.org/3/library/argparse.html#nargs
# 如果某一项输入输出不是 IR，那么 input/output 要么为空，要么是一个关于文件名的正则表达式，如果命令行的输入输出参数匹配的话，即使没有提供 flag 所注的选项，该转换也会执行

@dataclasses.dataclass
class IODecl:
  description : str # 用于描述该输入输出的字符串
  match_suffix : str | typing.Tuple[str] | None = None # 用于自动匹配该输入输出的文件后缀名，None 则不作匹配。字符串需要包含'.'
  nargs : int | str = '*'

  def __str__(self) -> str:
    result = ''
    if len(self.description) > 0:
      result = self.description
    match_suffix_str = ''
    if self.match_suffix is not None:
      if isinstance(self.match_suffix, tuple):
        match_suffix_str = ', '.join(self.match_suffix)
      else:
        if not isinstance(self.match_suffix, str):
          raise PPAssertionError
        match_suffix_str = self.match_suffix
    if len(match_suffix_str) > 0:
      if len(result) > 0:
        result += ' '
      result += '(' + match_suffix_str + ')'
    return result

def FrontendDecl(flag : str, input_decl : IODecl, output_decl : type):
  def decorator_frontend_decl(cls):
    TransformRegistration.register_frontend_transform(cls, flag, input_decl, output_decl)
    return cls
  return decorator_frontend_decl

def MiddleEndDecl(flag : str, input_decl : type, output_decl : type):
  def decorator_middleend_decl(cls):
    TransformRegistration.register_middleend_transform(cls, flag, input_decl, output_decl)
    return cls
  return decorator_middleend_decl

def BackendDecl(flag : str, input_decl : type, output_decl : IODecl):
  def decorator_backend_decl(cls):
    TransformRegistration.register_backend_transform(cls, flag, input_decl, output_decl)
    return cls
  return decorator_backend_decl

def TransformArgumentGroup(title : str, desc : str | None = None):
  # 如果某个已经用以上修饰符注册过的转换需要额外的命令行参数，那么再在上面加这个修饰符
  # 转换的类需要定义 install_arguments() 函数，之后创建命令行解析器的时候该函数会被执行
  # 这个修饰符必须加在上述注册用修饰符之前，不然的话当该修饰符执行时，转换还是未注册状态，后面会出错
  def decorator_ag(cls):
    TransformRegistration.register_argument_group(cls, title, desc)
    return cls
  return decorator_ag

# ------------------------------------------------------------------------------
# 实现
# ------------------------------------------------------------------------------

TR_pipeline = TranslationDomain("pipeline")

TR_pipeline_input = TR_pipeline.tr("input",
  en="input",
  zh_cn="输入",
  zh_hk="輸入",
)
TR_pipeline_output = TR_pipeline.tr("output",
  en="output",
  zh_cn="输出",
  zh_hk="輸出",
)

# 我们想要记住命令行的顺序，所以用一个自定义的 Action
class _OrderedPassAction(argparse.Action):
  def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: str | typing.Sequence[typing.Any] | None, option_string: str | None = ...) -> None:
    if not 'ordered_passes' in namespace:
      setattr(namespace, 'ordered_passes', [])
    previous : typing.List[typing.Any] = namespace.ordered_passes
    previous.append((self.dest, values))
    setattr(namespace, 'ordered_passes', previous)

class TransformRegistration:
  @dataclasses.dataclass
  class TransformInfo:
    definition : type[TransformBase]
    flag : str
    input_decl : type[Operation] | IODecl
    output_decl : type[Operation] | IODecl
    arg_title : str | None
    arg_desc : str | None

  _registration_record : typing.ClassVar[typing.Dict[type, TransformInfo]] = {}
  _flag_to_type_dict : typing.ClassVar[typing.Dict[str, type]] = {}
  _frontend_records : typing.ClassVar[typing.Dict[str, TransformInfo]] = {}
  _middleend_records : typing.ClassVar[typing.Dict[str, TransformInfo]] = {}
  _backend_records : typing.ClassVar[typing.Dict[str, TransformInfo]] = {}

  # 我们假设每次运行的流程都是以下过程或其中的一部分：
    # 1. 前端读取非 IR 的文件，或者直接读取 IR 文件。这一步不需要区分读取的先后顺序，可以同时使用多个前端。该步结束时所有的“当前”IR都是同一类型，可能有一个顶层操作项也有可能有多个
    # 2. 中端读取上一步的结果，运行命令行给出的 0-N 个转换。这一步需要区分转换的先后顺序。每一个转换开始时 IR 类型相同，结束时也是，IR 顶层操作项的数量可能会减少。
    # 3. 后端读取 IR，生成非 IR 的输出。这一步同样不需要区分输出的先后顺序，可以同时使用多个后端。
    # 目前默认的 argparse.ArgumentParser 不能记录带参数的输入项的顺序，所以我们无法按命令行的顺序来执行操作。
    # （要这样也不是不行，就是很费劲）
    # 因此我们现在只区分中端转换的顺序，前后端的按字母顺序进行（还是要有个固定的顺序，方便复现问题）
  @dataclasses.dataclass
  class Pipeline:
    ctx : Context
    frontends : typing.List[TransformBase] # 所有的（初始化好的）前端
    middleends : typing.List[TransformBase] # 所有的中端
    backends : typing.List[TransformBase] # 所有的后端

  _tr_TransformRegistration_noinst = TR_pipeline.tr("transformregistration_noinst",
    en="TransformRegistration should not be instantiated. Please do not create the instance.",
    zh_cn="TransformRegistration 不应该被实例化，请勿创建其实例。",
    zh_hk="TransformRegistration 不應該被實例化，請勿創建其實例。",
  )

  def __init__(self) -> None:
    raise RuntimeError(self._tr_TransformRegistration_noinst)

  _tr_TransformRegistration_arg_before_reg = TR_pipeline.tr("transformregistration_arg_before_reg",
    en="Transform not registered yet when registering arguments (please double check if decorator @TransformArgumentGroup is added before @FrontendDecl/@MiddleEndDecl/@BackendDecl).",
    zh_cn="转换步骤在添加参数时还未注册 （请检查是否已将修饰符 @TransformArgumentGroup 加在 @FrontendDecl/@MiddleEndDecl/@BackendDecl 之前）。",
    zh_hk="轉換步驟在添加參數時還未註冊 （請檢查是否已將修飾符 @TransformArgumentGroup 加在 @FrontendDecl/@MiddleEndDecl/@BackendDecl 之前）。",
  )

  @staticmethod
  def register_argument_group(transform_cls, arg_title : str, arg_desc : str | None):
    if not issubclass(transform_cls, TransformBase):
      raise PPAssertionError("Registering transform not inherting from TransformBase")
    if not isinstance(arg_title, str):
      raise PPAssertionError("Transform argument title must be a string")
    if arg_desc is not None:
      if not isinstance(arg_desc, str):
        raise PPAssertionError("Transform argument group description must be a string")
    if transform_cls not in TransformRegistration._registration_record:
      raise RuntimeError(TransformRegistration._tr_TransformRegistration_arg_before_reg)
    info = TransformRegistration._registration_record[transform_cls]
    info.arg_title = arg_title
    info.arg_desc = arg_desc

  @staticmethod
  def _iodecl_to_string(decl : type | IODecl):
    if isinstance(decl, IODecl):
      return str(decl)
    if not (isinstance(decl, type) and issubclass(decl, Operation)):
      raise PPAssertionError("Invalid decl type; should be either IODecl instance or a type which is either Operation or one of its subclass")
    return decl.__name__

  _tr_TransformRegistration_install_args_without_reg = TR_pipeline.tr("transformregistration_install_args_without_reg",
    en="Pass overriding install_arguments() without argument title (did you forgot using @TransformArgumentGroup(<arg_title>) decorator?)",
    zh_cn="转换步骤覆盖了 install_arguments() 但是没有参数组名 （你是否忘记使用 @TransformArgumentGroup(<参数组名>) 修饰符？）",
    zh_hk="轉換步驟覆蓋了 install_arguments() 但是沒有參數組名 （你是否忘記使用 @TransformArgumentGroup(<參數組名>) 修飾符？）",
  )

  @staticmethod
  def setup_argparser(parser : argparse.ArgumentParser):

    def get_transform_helpstr(info : TransformRegistration.TransformInfo):
      return info.definition.__name__ + ': ' + TransformRegistration._iodecl_to_string(info.input_decl) + ' -> ' + TransformRegistration._iodecl_to_string(info.output_decl)

    # 处理前后端的辅助函数
    def add_frontend_transform_arg(group : argparse._ArgumentGroup, info : TransformRegistration.TransformInfo):
      group.add_argument('--' + info.flag, dest=info.flag, action=_OrderedPassAction, nargs = info.input_decl.nargs, help=get_transform_helpstr(info))

    def add_backend_transform_arg(group : argparse._ArgumentGroup, info : TransformRegistration.TransformInfo):
      group.add_argument('--' + info.flag, dest=info.flag, action=_OrderedPassAction, nargs = info.output_decl.nargs, help=get_transform_helpstr(info))

    # 处理中端的辅助函数
    def add_middleend_transform_arg(group : argparse._ArgumentGroup, info : TransformRegistration.TransformInfo):
      group.add_argument('--' + info.flag, dest=info.flag, action=_OrderedPassAction, nargs=0, help=get_transform_helpstr(info))

    def handle_stage_group(flags_dict : typing.Dict[str, TransformRegistration.TransformInfo], stage_name : str, stage_desc : str, cb_add_arg : typing.Callable):
      if not len(flags_dict) > 0:
        raise PPAssertionError("handling empty stage group?")
      group = parser.add_argument_group(title=stage_name, description=stage_desc)
      for flag, info in sorted(flags_dict.items()):
        cb_add_arg(group, info)
        if info.arg_title is not None:
          transform_arg_group = parser.add_argument_group(title=info.arg_title, description=info.arg_desc)
          info.definition.install_arguments(transform_arg_group)
        else:
          # 检查一下，如果该类型覆盖了 install_arguments 但是没有 arg_title, 我们报错（提示用 @TransformArgumentGroup 修饰符）
          if info.definition.install_arguments is not TransformBase.install_arguments:
            raise RuntimeError(TransformRegistration._tr_TransformRegistration_install_args_without_reg)

    # 函数主体
    # parser.add_argument('input', nargs='*', type=str)
    # parser.add_argument('--output', dest='output', action='store', nargs=1, type=str)
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='Show version and (if other commands specified) verbose debug information')
    if len(TransformRegistration._frontend_records) > 0:
      handle_stage_group(TransformRegistration._frontend_records, 'Front end', 'Options to enable frontend transforms', add_frontend_transform_arg)
    if len(TransformRegistration._middleend_records) > 0:
      handle_stage_group(TransformRegistration._middleend_records, 'Middle end', 'Options tp enable middle-end transforms', add_middleend_transform_arg)
    if len(TransformRegistration._backend_records) > 0:
      handle_stage_group(TransformRegistration._backend_records, 'Back end', 'Options tp enable backend transforms', add_backend_transform_arg)

  _tr_pipeline_mismatched_input_type = TR_pipeline.tr("pipeline_static_mismatched_input_type",
    en="IR type in pipeline does not match with the supported input type: current type: {curtype}, input type supported by the pass: {inputtype}. Please check if you missed flags or misplaced pass arguments.",
    zh_cn="管线中的 IR 类型与步骤支持的类型不一致： 当前类型： {curtype}, 步骤支持的输入类型： {inputtype}。请检查是否遗漏了步骤选项或是将其放错了位置。",
    zh_hk="管線中的 IR 類型與步驟支持的類型不一致： 當前類型： {curtype}, 步驟支持的輸入類型： {inputtype}。請檢查是否遺漏了步驟選項或是將其放錯了位置。",
  )
  _tr_pipeline_mismatched_output_type = TR_pipeline.tr("pipeline_static_mismatched_output_type",
    en="IR type in pipeline does not match with the output type: current type: {curtype}, output type emitted by the pass: {outputtype}. Please check if you missed flags or misplaced pass arguments.",
    zh_cn="管线中的 IR 类型与步骤输出的类型不一致： 当前类型： {curtype}, 步骤的输出类型： {outputtype}。请检查是否遗漏了步骤选项或是将其放错了位置。",
    zh_hk="管線中的 IR 類型與步驟輸出的類型不一致： 當前類型： {curtype}, 步驟的輸出類型： {outputtype}。請檢查是否遺漏了步驟選項或是將其放錯了位置。",
  )
  _tr_pipeline_stage = TR_pipeline.tr("static_prompt",
    en="Pipeline stage {index} ({flag}): ",
    zh_cn="管线步骤 {index} ({flag}): ",
    zh_hk="管線步驟 {index} ({flag}): "
  )

  @staticmethod
  def build_pipeline(parsed_args : argparse.Namespace, ctx : Context) -> typing.List[TransformBase]:
    # 找到所有被调用的转换，将它们的命令行参数解析好，然后组成最终的管线
    # 如果一个转换也没有就返回 None
    # 如果其中有什么问题，则我们抛出异常
    #   @dataclasses.dataclass
    #class Pipeline:
    #ctx : Context
    #frontends : typing.List[TransformBase] # 所有的（初始化好的）前端
    #middleends : typing.List[TransformRegistration.TransformInfo] # 所有的中端
    #backends : typing.List[typing.Tuple[TransformRegistration.TransformInfo, typing.Tuple[str]]] # 所有的后端以及它们的输出
    current_ir_type : type = None
    verbose = parsed_args.verbose
    ordered_passes : typing.List[typing.Tuple[str, typing.Any]] = getattr(parsed_args, "ordered_passes", [])
    pipeline : typing.List[TransformBase] = []
    initialized_tys : typing.Set[type] = set()
    pipeline_index = 0
    for flag, value in ordered_passes:
      pipeline_index += 1
      # print('Pipeline: before flag ' + flag + ': cur type = ' + ('None' if current_ir_type is None else current_ir_type.__name__))
      transform_cls = TransformRegistration._flag_to_type_dict[flag]
      info = TransformRegistration._registration_record[transform_cls]
      # 让转换读取相应的命令行参数
      if info.arg_title is not None:
        if transform_cls not in initialized_tys:
          initialized_tys.add(transform_cls)
          transform_cls.handle_arguments(parsed_args)
      # 然后再构建转换实例
      transform_inst : TransformBase = transform_cls(ctx)
      # 处理输入
      # 检查类型是否匹配，如果是前端的话直接把输入设定好
      input_decl = info.input_decl
      if isinstance(input_decl, type):
        if current_ir_type is None:
          current_ir_type = input_decl
        elif current_ir_type == Operation and input_decl != Operation and issubclass(input_decl, Operation):
          # 类型细化
          current_ir_type = input_decl
        # 如果类型是 Operation 的话就是什么 IR 都能输入，不进行检查
        elif input_decl != Operation and current_ir_type != Operation and input_decl != current_ir_type:
          # 找到错误，报错
          raise RuntimeError(TransformRegistration._tr_pipeline_stage.format(index=str(pipeline_index), flag=flag)
                            +TransformRegistration._tr_pipeline_mismatched_input_type.format(curtype=current_ir_type.__name__, inputtype=input_decl.__name__))
      elif isinstance(input_decl, IODecl):
        # 现在把输入赋值过去
        input_list = []
        if isinstance(value, list):
          input_list = value.copy()
        elif isinstance(value, str):
          input_list = [value]
        else:
          # raise RuntimeError("Unexpected value type " + str(type(value)))
          raise PPInternalError
        transform_inst.set_input(input_list)
      # 处理输出
      output_decl = info.output_decl
      if isinstance(output_decl, type):
        # 输出 IR
        # 先检查例外情况，如果输入是非IR，那么我们同样要求该类型与当前IR类型匹配
        if isinstance(input_decl, IODecl):
          if output_decl != Operation and current_ir_type is not None and current_ir_type != Operation and output_decl != current_ir_type:
            raise RuntimeError(TransformRegistration._tr_pipeline_stage.format(index=str(pipeline_index), flag=flag)
                              +TransformRegistration._tr_pipeline_mismatched_output_type.format(curtype=current_ir_type.__name__, outputtype=output_decl.__name__))
        # 更新当前 IR 类型
        if current_ir_type is None or current_ir_type == Operation or (output_decl is not Operation and issubclass(output_decl, Operation)):
          current_ir_type = output_decl
      elif isinstance(output_decl, IODecl):
        # 输出非 IR
        # 把输出值赋过去
        output_path = ''
        if isinstance(value, list):
          if not len(value) < 2:
            raise PPAssertionError("Pipeline currently only support 0-1 output taking path arguments")
          if len(value) != 0:
            output_path = value[0]
        else:
          output_path = value
        transform_inst.set_output_path(output_path)
      pipeline.append(transform_inst)
      if verbose:
        print(TransformRegistration._tr_pipeline_stage.format(index=str(pipeline_index), flag=flag) + str(transform_inst))
    return pipeline

  _tr_transform_already_registered = TR_pipeline.tr("transform_already_registered",
    en="Transform class {classname} is registered more than once. Please check if annotated with more than one of @FrontendDecl/@MiddleEndDecl/@BackendDecl.",
    zh_cn="转换步骤类 {classname} 被重复注册。请检查其是否被不止一个 @FrontendDecl/@MiddleEndDecl/@BackendDecl 所标注。",
    zh_hk="轉換步驟類 {classname} 被重復註冊。請檢查其是否被不止一個 @FrontendDecl/@MiddleEndDecl/@BackendDecl 所標註。"
  )
  _tr_transform_flag_already_used = TR_pipeline.tr("transform_flag_already_used",
    en="Pass flag {flag} already in use: registered class: {existing}, current class: {current}",
    zh_cn="步骤选项 {flag} 已被占用：已注册的类：{existing}, 当前正在注册的类：{current}",
    zh_hk="步驟選項 {flag} 已被占用：已註冊的類：{existing}, 當前正在註冊的類：{current}",
  )

  @staticmethod
  def register_transform_common(transform_cls, flag : str, input_decl : type | IODecl, output_decl : type | IODecl) -> TransformInfo:
    if not (isinstance(transform_cls, type) and issubclass(transform_cls, TransformBase)):
      raise PPAssertionError("Transform should be a subclass of TransformBase")
    if not (isinstance(flag, str) and not flag.startswith('-')):
      raise PPAssertionError("Transform flag must be a string without starting '-'")
    if transform_cls in TransformRegistration._registration_record:
      raise RuntimeError(TransformRegistration._tr_transform_already_registered.format(classname=str(transform_cls)))
    if flag in TransformRegistration._flag_to_type_dict:
      raise RuntimeError(TransformRegistration._tr_transform_flag_already_used.format(flag=flag, existing=str(TransformRegistration._flag_to_type_dict[flag]), current=str(transform_cls)))
    TransformRegistration._flag_to_type_dict[flag] = transform_cls
    info = TransformRegistration.TransformInfo(transform_cls, flag, input_decl, output_decl, None, None)
    TransformRegistration._registration_record[transform_cls] = info
    return info


  @staticmethod
  def register_frontend_transform(transform_cls, flag : str, input_decl : IODecl, output_decl : type):
    if not isinstance(input_decl, IODecl):
      raise PPAssertionError("Frontend must use IODecl for input declaration")
    if not (isinstance(output_decl, type) and issubclass(output_decl, Operation)):
      raise PPAssertionError("Frontend must use Operation subclass for output declaration")
    info = TransformRegistration.register_transform_common(transform_cls, flag, input_decl, output_decl)
    TransformRegistration._frontend_records[flag] = info

  @staticmethod
  def register_middleend_transform(transform_cls, flag : str, input_decl : type, output_decl : type):
    if not issubclass(input_decl, Operation):
      raise PPAssertionError("MiddleEnd must use Operation subclass for input declaration")
    if not issubclass(output_decl, Operation):
      raise PPAssertionError("MiddleEnd must use Operation subclass for output declaration")
    info = TransformRegistration.register_transform_common(transform_cls, flag, input_decl, output_decl)
    TransformRegistration._middleend_records[flag] = info

  @staticmethod
  def register_backend_transform(transform_cls, flag : str, input_decl : type, output_decl : IODecl):
    if not issubclass(input_decl, Operation):
      raise PPAssertionError("Backend must use Operation subclass for input declaration")
    if not isinstance(output_decl, IODecl):
      raise PPAssertionError("Backend must use IODecl for output declaration")
    info = TransformRegistration.register_transform_common(transform_cls, flag, input_decl, output_decl)
    TransformRegistration._backend_records[flag] = info

@FrontendDecl('load', input_decl=IODecl(description='IR file', nargs='+'), output_decl=Operation)
class _LoadIR(TransformBase):
  def run(self) -> Operation | typing.List[Operation]:
    raise PPNotImplementedError

@BackendDecl('save', input_decl=Operation, output_decl=IODecl('IR file', nargs=1))
class _SaveIR(TransformBase):
  def run(self) -> None:
    raise PPNotImplementedError

@BackendDecl('dump', input_decl=Operation, output_decl=IODecl('<No output>', nargs=0))
class _DumpIR(TransformBase):
  def run(self) -> None:
    for op in self.inputs:
      op.dump()

@BackendDecl('view', input_decl=Operation, output_decl=IODecl('<No output>', nargs=0))
class _ViewIR(TransformBase):
  def run(self) -> None:
    for op in self.inputs:
      op.view()

@BackendDecl('test-copy-dump', input_decl=Operation, output_decl=IODecl('<No output>', nargs=0))
class _TestCopyDumpIR(TransformBase):
  @staticmethod
  def save_dump(s : str, name : str)-> str:
    name_portion = 'anon'
    if len(name) > 0:
      sanitized_name = get_sanitized_filename(name)
      if len(sanitized_name) > 0:
        name_portion = sanitized_name
    file = tempfile.NamedTemporaryFile('w+b', suffix='.txt', prefix='preppipe_' + name_portion + '_', delete=False)
    file.write(s.encode())
    file.close()
    path = os.path.abspath(file.name)
    return path

  def run(self) -> None:
    src_dump = []
    clones = []
    for op in self.inputs:
      src_dump.append(str(op))
      clones.append(op.clone())
      op.drop_all_references()
    # pylint: disable=consider-using-enumerate
    for i in range(0, len(clones)):
      src = src_dump[i]
      clone = clones[i]
      dest = str(clone)
      if src != dest:
        src_path = _TestCopyDumpIR.save_dump(src, 'src')
        dest_path = _TestCopyDumpIR.save_dump(dest, 'dest')
        print('Diff: A=' + src_path + ', B=' + dest_path)
        raise PPInternalError('Cloned output not matching with input!')

@BackendDecl('json-export', input_decl=Operation, output_decl=IODecl('JSON file', nargs=1))
class _JsonExportIR(TransformBase):
  def run(self) -> Operation | typing.List[Operation] | None:
    if len(self.inputs) == 0:
      raise PPInternalError('No IR for export')
    exporter = IRJsonExporter(self.context)
    toplevel = None
    for op in self.inputs:
      if not isinstance(op, Operation):
        raise PPInternalError('Toplevel should be an operation')
      curop = op.json_export(exporter = exporter)
      if not isinstance(curop, dict):
        raise PPInternalError("Operation output should be a dict")
      if toplevel is None:
        # 0 --> 1
        toplevel = curop
      elif isinstance(toplevel, list):
        # N --> N+1
        toplevel.append(curop)
      else:
        # 1 --> 2
        toplevel = [toplevel, curop]
    json_str = exporter.write_json(toplevel)
    with open(self.output, "w", newline="\n", encoding="utf-8") as f:
      f.write(json_str)

class _PipelineManager:
  _TR_pipeline_version = TR_pipeline.tr("preppipe_version",
    en="preppipe {version}",
    zh_cn="语涵编译器 {version}",
    zh_hk="語涵編譯器 {version}",
  )
  _TR_pipeline_running = TR_pipeline.tr("running",
    en="Running",
    zh_cn="正在执行",
    zh_hk="正在執行",
  )
  _TR_pipeline_finished = TR_pipeline.tr("finished",
    en="Finished",
    zh_cn="执行结束",
    zh_hk="執行結束",
  )
  _TR_pipeline_base_prompt = TR_pipeline.tr("runtime_prompt",
    en="At pipeline step {step_count} ({flag}): ",
    zh_cn="步骤 {step_count} ({flag}): ",
    zh_hk="步驟 {step_count} ({flag}): ",
  )
  _TR_pipeline_no_input = TR_pipeline.tr("no_input",
    en="No IR input available. This probably means the previous pipeline stage does not produce any output. Please check if the source input is valid.",
    zh_cn="没有输入 IR。这一般是因为前一步骤没有产生任何输出。请确认源文件是否存在、有效。",
    zh_hk="沒有輸入 IR。這一般是因為前一步驟沒有產生任何輸出。請確認源文件是否存在、有效。",
  )
  _tr_pipeline_mismatched_input_type = TR_pipeline.tr("pipeline_runtime_mismatched_input_type",
    en="IR type in pipeline does not match with the supported input type: current type: {curtype}, input type supported by the pass: {inputtype}. Please contact the developer(s) to fix this.",
    zh_cn="管线中的 IR 类型与步骤支持的类型不一致： 当前类型： {curtype}, 步骤支持的输入类型： {inputtype}。请联系开发者以解决该问题。",
    zh_hk="管線中的 IR 類型與步驟支持的類型不一致： 當前類型： {curtype}, 步驟支持的輸入類型： {inputtype}。請聯系開發者以解決該問題。",
  )
  _tr_pipeline_mismatched_output_type = TR_pipeline.tr("pipeline_runtime_mismatched_output_type",
    en="IR type in pipeline does not match with the output type: current type: {curtype}, output type emitted by the pass: {outputtype}. Please contact the developer(s) to fix this.",
    zh_cn="管线中的 IR 类型与步骤输出的类型不一致： 当前类型： {curtype}, 步骤的输出类型： {outputtype}。请联系开发者以解决该问题。",
    zh_hk="管線中的 IR 類型與步驟輸出的類型不一致： 當前類型： {curtype}, 步驟的輸出類型： {outputtype}。請聯系開發者以解決該問題。",
  )
  _tr_pipeline_last_ir_notused = TR_pipeline.tr("pipeline_output_unused",
    en="Warning: last-stage IR not used and will be discarded. Please check if you missed any output transform flags.",
    zh_cn="警告：最后生成的 IR 未被使用，结果将被丢弃。请检查是否遗漏了输出步骤的选项。",
    zh_hk="警告：最後生成的 IR 未被使用，結果將被丟棄。請檢查是否遺漏了輸出步驟的選項。",
  )
  tr_pipeline_no_searchpath = TR_pipeline.tr("pipeline_no_searchpath",
    en="Warning: No search path is specified on command line. The program will not search any directory for assets. We need your explicit authorization with \"--searchpath <paths>...\" option to permit asset lookup in the specified directories.",
    zh_cn="警告：命令行参数中没有指定搜索路径。程序将不会在任何目录中查找资源。我们需要您使用 \"--searchpath <路径>...\" 来授权程序在指定的目录下查找资源。",
    zh_hk="警告：命令行參數中沒有指定搜索路徑。程序將不會在任何目錄中查找資源。我們需要您使用 \"--searchpath <路徑>...\" 來授權程序在指定的目錄下查找資源。",
  )

  @staticmethod
  def pipeline_main(args : typing.List[str] | None = None):
    Translatable._init_lang_list()
    # 先尝试读取插件
    _PipelineManager._load_plugins()
    # args 应该是不带 sys.argv[0] 的
    # (pipeline_cmd.py 中，这个参数是 sys.argv[1:])
    if args is None:
      args = sys.argv[1:]

    def _print_version_info():
      print(_PipelineManager._TR_pipeline_version.format(version=__version__))
    # 第一步：读取
    parser = argparse.ArgumentParser(prog='preppipe_pipeline', description='Direct commandline interface for preppipe')
    parser.add_argument('--searchpath', nargs='*')
    Translatable._language_install_arguments(parser) # pylint: disable=protected-access

    TransformRegistration.setup_argparser(parser)
    result_args = parser.parse_args(args)
    Translatable._language_handle_arguments(result_args, result_args.verbose) # pylint: disable=protected-access

    # if there is no valid action performed, we want to print the help message
    is_action_performed = False

    # print version info if needed
    if result_args.verbose:
      _print_version_info()
      is_action_performed = True

    ctx = Context()
    if result_args.searchpath:
      for path in result_args.searchpath:
        ctx.get_file_auditor().add_permissible_path(path)
        ctx.get_file_auditor().add_global_searchpath(path)
    else:
      print(_PipelineManager.tr_pipeline_no_searchpath.get())
    if result_args.verbose:
      ctx.get_file_auditor().dump()

    pipeline = TransformRegistration.build_pipeline(result_args, ctx)
    current_ir_ops : list[Operation | str] = []
    step_count = 0
    is_current_ir_used = False
    starttime = time.time()
    def get_timestr():
      curtime = time.time()
      timestr = "{:.2f}".format(curtime - starttime)
      return timestr
    for t in pipeline:
      step_count += 1
      transform_cls = type(t)
      info = TransformRegistration._registration_record[transform_cls]
      if result_args.verbose:
        print('[' + get_timestr() + '] ' + _PipelineManager._TR_pipeline_running.get() + ' ' + info.flag + " (" + str(step_count) + '/' + str(len(pipeline)) + ')')
      is_append_result = False
      if isinstance(info.input_decl, type):
        # 该转换读取IR
        if not issubclass(info.input_decl, Operation):
          raise PPAssertionError("Incompatible pipeline spec sliped through static check?")
        # 确认当前是否有有效的IR
        if len(current_ir_ops) == 0:
          raise RuntimeError(_PipelineManager._TR_pipeline_base_prompt.format(step_count=str(step_count), flag=info.flag) + _PipelineManager._TR_pipeline_no_input.get())
          #raise RuntimeError('At pipeline step ' + str(step_count) + ': (' + info.flag + '): No IR input available')
        # 检查当前 IR 是否每项都是指定类型
        # 如果类型是 Operation 就代表不限制输入类型
        if info.input_decl != Operation:
          for op in current_ir_ops:
            if not isinstance(op, info.input_decl):
              raise RuntimeError(_PipelineManager._TR_pipeline_base_prompt.format(step_count=str(step_count), flag=info.flag)
                                +_PipelineManager._tr_pipeline_mismatched_input_type.format(curtype=type(op).__name__, inputtype=info.input_decl.__name__))
              #raise RuntimeError('At pipeline step ' + str(step_count) + ': (' + info.flag + '): Mismatching IR type: expecting '+ info.input_decl.__name__ + ', found IR type: ' + type(op).__name__)
        # 检查完毕，可以继续
        t.set_input(current_ir_ops.copy())
        is_current_ir_used = True
      else:
        # 该转换读取外部文件
        # 不用做什么
        is_append_result = True
        pass
      # 对输入的数量做最终检查
      if len(t.inputs) == 0:
        if isinstance(info.input_decl, IODecl) and info.input_decl.nargs in [0, '?']:
          # in this case it is permissible to have zero input
          pass
        else:
          # 一般不会到这
          raise PPInternalError('At pipeline step ' + str(step_count) + ': (' + info.flag + '): No input available')
      run_result = t.run()
      if isinstance(info.output_decl, type):
        # 该转换输出 IR
        if not issubclass(info.output_decl, Operation):
          raise PPAssertionError("Should be caught during transform pass registration but is not")
        list_result : list[Operation] = []
        if isinstance(run_result, list):
          list_result = run_result.copy()
        elif isinstance(run_result, Operation):
          list_result = [run_result]
        else:
          if run_result is not None:
            raise PPInternalError('Unexpected return type for TransformBase.run(): ' + type(run_result).__name__)
        for r in list_result:
          if not isinstance(r, info.output_decl):
            raise PPInternalError('At pipeline step ' + str(step_count) + ': (' + info.flag + '): Unexpected output IR type: expecting ' + info.input_decl.__name__ + ', actual type: ' + type(r).__name__)
        if is_append_result:
          current_ir_ops = [*current_ir_ops, *list_result]
        else:
          current_ir_ops = list_result
          is_current_ir_used = False
      else:
        # 该转换输出非IR内容
        if not isinstance(info.output_decl, IODecl):
          raise PPAssertionError("Should be caught during transform pass registration but is not")

    if step_count > 0:
      is_action_performed = True

    if not is_action_performed:
      parser.print_usage()
      return

    if len(current_ir_ops) > 0 and not is_current_ir_used:
      print(_PipelineManager._tr_pipeline_last_ir_notused.get())

    if result_args.verbose:
      print('[' + get_timestr() + '] ' + _PipelineManager._TR_pipeline_finished.get())

    return

  _tr_plugin_loading = TR_pipeline.tr("plugin_loading",
    en="Loading plugin {modulename} from {filepath}",
    zh_cn="正在从 {filepath} 读取插件 {modulename}",
    zh_hk="正在從 {filepath} 讀取插件 {modulename}",
  )
  _tr_plugin_load_fail = TR_pipeline.tr("plugin_load_fail",
    en="Cannot load plugin {modulename} from {filepath}, skipped",
    zh_cn="无法从 {filepath} 读取插件 {modulename}, 跳过",
    zh_hk="無法從 {filepath} 讀取插件 {modulename}, 跳過",
  )

  @staticmethod
  def _load_module(module_name, file_path):
    print(_PipelineManager._tr_plugin_loading.format(modulename=module_name, filepath=file_path))
    is_loaded = False
    try:
      if spec := importlib.util.spec_from_file_location(module_name, file_path):
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        is_loaded = True
    except Exception as e:
      traceback.print_exception(e)
    if not is_loaded:
      print(_PipelineManager._tr_plugin_load_fail.format(modulename=module_name, filepath=file_path))

  _tr_plugin_load_start = TR_pipeline.tr("plugin_load_start",
    en="Loading plugin(s) from PREPPIPE_PLUGINS: ",
    zh_cn="即将从 PREPPIPE_PLUGINS 读取插件: ",
    zh_hk="即將從 PREPPIPE_PLUGINS 讀取插件: ",
  )

  @staticmethod
  def _load_plugins():
    if plugindir := os.environ.get("PREPPIPE_PLUGINS"):
      plugindir = os.path.realpath(plugindir)
      plugin_modulebase = "preppipe.plugin."
      if os.path.isdir(plugindir):
        dircontent = os.listdir(plugindir)
        if len(dircontent) > 0:
          print(_PipelineManager._tr_plugin_load_start.get() + '"' + plugindir + '"')
          for pluginname in dircontent:
            curpath = os.path.join(plugindir, pluginname)
            if os.path.isfile(curpath):
              # 检查是否是 Python 文件，是的话当作插件来导入
              basename, ext = os.path.splitext(pluginname)
              if ext.lower() == '.py':
                modulename = plugin_modulebase + basename
                _PipelineManager._load_module(modulename, curpath)
            elif os.path.isdir(curpath):
              filepath = os.path.join(plugindir, pluginname, pluginname + ".py")
              if os.path.isfile(filepath):
                modulename = plugin_modulebase + pluginname
                _PipelineManager._load_module(modulename, filepath)

def pipeline_main(args : typing.List[str] | None = None):
  # 保持一个统一性，这个全局函数作为对外的接口
  # 以后类型拆分或是重命名都不会改变这个函数的名称和输入
  _PipelineManager.pipeline_main(args)

if __name__ == "__main__":
  # 这个文件只是被所有转换步骤所引用，自身并没有向外的引用，所以只执行该文件的话步骤不会被注册
  raise PPNotImplementedError('Please invoke pipeline_cmd instead')
