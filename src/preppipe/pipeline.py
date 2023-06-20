# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import sys

from .irbase import *
from .util.audit import *
from ._version import __version__

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
      iostr += 'input={' + ', '.join(input_list) + '}'
    if len(self.output) > 0:
      if len(iostr) > 0:
        iostr += ', '
      iostr += 'output="' + self.output + '"'
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
        assert isinstance(self.match_suffix, str)
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

def BackendDecl(flag : str, input_decl : str, output_decl : IODecl):
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
    definition : type
    flag : str
    input_decl : type | IODecl
    output_decl : type | IODecl
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

  def __init__(self) -> None:
    raise RuntimeError('TransformRegistration should not be instantiated')

  @staticmethod
  def register_argument_group(transform_cls, arg_title : str, arg_desc : str | None):
    assert issubclass(transform_cls, TransformBase)
    assert isinstance(arg_title, str)
    if arg_desc is not None:
      assert isinstance(arg_desc, str)
    if transform_cls not in TransformRegistration._registration_record:
      raise RuntimeError('Transform not registered yet (check the order of decorators)')
    info = TransformRegistration._registration_record[transform_cls]
    info.arg_title = arg_title
    info.arg_desc = arg_desc

  @staticmethod
  def _iodecl_to_string(decl : type | IODecl):
    if isinstance(decl, IODecl):
      return str(decl)
    assert isinstance(decl, type) and issubclass(decl, Operation)
    return decl.__name__

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

    def handle_stage_group(flags_dict : typing.Dict[str, TransformRegistration.TransformInfo], stage_name : str, stage_desc : str, cb_add_arg : callable):
      assert len(flags_dict) > 0
      group = parser.add_argument_group(title=stage_name, description=stage_desc)
      for flag, info in sorted(flags_dict.items()):
        cb_add_arg(group, info)
        if info.arg_title is not None:
          transform_arg_group = parser.add_argument_group(title=info.arg_title, description=info.arg_desc)
          info.definition.install_arguments(transform_arg_group)

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
    ordered_passes : typing.List[typing.Tuple[str, typing.Any]] = parsed_args.ordered_passes
    pipeline : typing.List[TransformBase] = []
    initialized_tys : typing.Set[type] = set()
    for flag, value in ordered_passes:
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
          raise RuntimeError('Mismatching IR type in pipeline: at pass "' + flag + '": current type: ' + current_ir_type.__name__ + ', input type: ' + input_decl.__name__)
      elif isinstance(input_decl, IODecl):
        # 现在把输入赋值过去
        input_list = []
        if isinstance(value, list):
          input_list = value.copy()
        elif isinstance(value, str):
          input_list = [value]
        else:
          raise RuntimeError("Unexpected value type " + str(type(value)))
        transform_inst.set_input(input_list)
      # 处理输出
      output_decl = info.output_decl
      if isinstance(output_decl, type):
        # 输出 IR
        # 先检查例外情况，如果输入是非IR，那么我们同样要求该类型与当前IR类型匹配
        if isinstance(input_decl, IODecl):
          if output_decl != Operation and current_ir_type is not None and current_ir_type != Operation and output_decl != current_ir_type:
            raise RuntimeError('Mismatching IR type in pipeline: at pass "' + flag + '": current type: ' + current_ir_type.__name__ + ', input type: ' + input_decl.__name__)
        # 更新当前 IR 类型
        if current_ir_type is None or current_ir_type == Operation or (output_decl is not Operation and issubclass(output_decl, Operation)):
          current_ir_type = output_decl
      elif isinstance(output_decl, IODecl):
        # 输出非 IR
        # 把输出值赋过去
        output_path = ''
        if isinstance(value, list):
          assert len(value) < 2
          if len(value) != 0:
            output_path = value[0]
        else:
          output_path = value
        transform_inst.set_output_path(output_path)
      pipeline.append(transform_inst)
    if verbose:
      # 把当前流水线的内容全都显示一下
      for i in range(0, len(pipeline)):
        print("Pipeline "+str(i) + ':' + str(pipeline[i]))
    return pipeline

  @staticmethod
  def register_transform_common(transform_cls, flag : str, input_decl : type | IODecl, output_decl : type | IODecl) -> TransformInfo:
    assert isinstance(transform_cls, type)
    assert issubclass(transform_cls, TransformBase)
    assert isinstance(flag, str) and not flag.startswith('-')
    if transform_cls in TransformRegistration._registration_record:
      raise RuntimeError('Transform ' + str(transform_cls) + ' registered more than once??')
    if flag in TransformRegistration._flag_to_type_dict:
      raise RuntimeError('Flag "' + flag + '" already in use: existing: ' + str(TransformRegistration._flag_to_type_dict[flag]) + ', current: ' + str(transform_cls))
    TransformRegistration._flag_to_type_dict[flag] = transform_cls
    info = TransformRegistration.TransformInfo(transform_cls, flag, input_decl, output_decl, None, None)
    TransformRegistration._registration_record[transform_cls] = info
    return info


  @staticmethod
  def register_frontend_transform(transform_cls, flag : str, input_decl : IODecl, output_decl : type):
    assert isinstance(input_decl, IODecl)
    assert isinstance(output_decl, type)
    assert issubclass(output_decl, Operation)
    info = TransformRegistration.register_transform_common(transform_cls, flag, input_decl, output_decl)
    TransformRegistration._frontend_records[flag] = info

  @staticmethod
  def register_middleend_transform(transform_cls, flag : str, input_decl : type, output_decl : str):
    assert issubclass(input_decl, Operation)
    assert issubclass(output_decl, Operation)
    info = TransformRegistration.register_transform_common(transform_cls, flag, input_decl, output_decl)
    TransformRegistration._middleend_records[flag] = info

  @staticmethod
  def register_backend_transform(transform_cls, flag : str, input_decl : type, output_decl : IODecl):
    assert issubclass(input_decl, Operation)
    assert isinstance(output_decl, IODecl)
    info = TransformRegistration.register_transform_common(transform_cls, flag, input_decl, output_decl)
    TransformRegistration._backend_records[flag] = info

@FrontendDecl('load', input_decl=IODecl(description='IR file', nargs='+'), output_decl=Operation)
class _LoadIR(TransformBase):
  def run(self) -> Operation | typing.List[Operation]:
    raise NotImplementedError()

@BackendDecl('save', input_decl=Operation, output_decl=IODecl('IR file', nargs=1))
class _SaveIR(TransformBase):
  def run(self) -> None:
    raise NotImplementedError()

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
        raise RuntimeError('Cloned output not matching with input!')

@BackendDecl('json-export', input_decl=Operation, output_decl=IODecl('JSON file', nargs=1))
class _JsonExportIR(TransformBase):
  def run(self) -> Operation | typing.List[Operation] | None:
    if len(self.inputs) == 0:
      raise RuntimeError('No IR for export')
    exporter = IRJsonExporter(self.context)
    toplevel = None
    for op in self.inputs:
      if not isinstance(op, Operation):
        raise RuntimeError('Toplevel should be an operation')
      curop = op.json_export(exporter = exporter)
      assert isinstance(curop, dict)
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
    with open(self.output, "w", newline="\n") as f:
      f.write(json_str)

def pipeline_main(args : typing.List[str] = None):
  # args 应该是不带 sys.argv[0] 的
  # (pipeline_cmd.py 中，这个参数是 sys.argv[1:])
  if args is None:
    args = sys.argv[1:]

  def _print_version_info():
    print('preppipe ' + __version__)
  # 第一步：读取
  parser = argparse.ArgumentParser(prog='preppipe_pipeline', description='Direct commandline interface for preppipe')

  TransformRegistration.setup_argparser(parser)
  result_args = parser.parse_args(args)

  # if there is no valid action performed, we want to print the help message
  is_action_performed = False

  # print version info if needed
  if result_args.verbose:
    _print_version_info()
    is_action_performed = True

  ctx = Context()
  ctx.get_file_auditor().add_permissible_path(os.getcwd())
  pipeline = TransformRegistration.build_pipeline(result_args, ctx)
  current_ir_ops = []
  step_count = 0
  is_current_ir_used = False
  for t in pipeline:
    step_count += 1
    transform_cls = type(t)
    info = TransformRegistration._registration_record[transform_cls]
    is_append_result = False
    if isinstance(info.input_decl, type):
      # 该转换读取IR
      assert issubclass(info.input_decl, Operation)
      # 确认当前是否有有效的IR
      if len(current_ir_ops) == 0:
        raise RuntimeError('At pipeline step ' + str(step_count) + ': (' + info.flag + '): No IR input available')
      # 检查当前 IR 是否每项都是指定类型
      # 如果类型是 Operation 就代表不限制输入类型
      if info.input_decl != Operation:
        for op in current_ir_ops:
          if not isinstance(op, info.input_decl):
            raise RuntimeError('At pipeline step ' + str(step_count) + ': (' + info.flag + '): Mismatching IR type: expecting '+ info.input_decl.__name__ + ', found IR type: ' + type(op).__name__)
      # 检查完毕，可以继续
      t.set_input(current_ir_ops.copy())
      is_current_ir_used = True
    else:
      # 该转换读取外部文件
      # 不用做什么
      is_append_result = True
      pass
    if len(t.inputs) == 0:
      if isinstance(info.input_decl, IODecl) and info.input_decl.nargs in [0, '?']:
        # in this case it is permissible to have zero input
        pass
      else:
        raise RuntimeError('At pipeline step ' + str(step_count) + ': (' + info.flag + '): No input available')
    run_result = t.run()
    if isinstance(info.output_decl, type):
      # 该转换输出 IR
      assert issubclass(info.output_decl, Operation)
      list_result = []
      if isinstance(run_result, list):
        list_result = run_result.copy()
      elif isinstance(run_result, Operation):
        list_result = [run_result]
      else:
        if run_result is not None:
          raise RuntimeError('Unexpected return type for TransformBase.run(): ' + type(run_result).__name__)
      for r in list_result:
        if not isinstance(r, info.output_decl):
          raise RuntimeError('At pipeline step ' + str(step_count) + ': (' + info.flag + '): Unexpected output IR type: expecting ' + info.input_decl.__name__ + ', actual type: ' + type(r).__name__)
      if is_append_result:
        current_ir_ops = [*current_ir_ops, *list_result]
      else:
        current_ir_ops = list_result
        is_current_ir_used = False
    else:
      # 该转换输出非IR内容
      assert isinstance(info.output_decl, IODecl)

  if step_count > 0:
    is_action_performed = True

  if not is_action_performed:
    parser.print_usage()
    return

  if len(current_ir_ops) > 0 and not is_current_ir_used:
    print('Warning: last-stage IR not used')

  return

if __name__ == "__main__":
  raise NotImplementedError('Please invoke pipeline_cmd instead')
