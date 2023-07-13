# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
from .pipeline import pipeline_main

# 我们在这里要把所有注册了转换的模块全都引用进来，不然的话当该模块作为 __main__ 的时候，那些注册的代码不会被执行，转换也无法从命令行被调用
# （以后应该搞个自定义的检查，代码里如果有加了注册的修饰符但没在这里包含的话就提示报错）

from .frontend import opendocument
from .frontend import commandsyntaxparser
from .renpy import passes as renpy_passes
from .frontend.vnmodel import passes as vnparser_passes
from .transform import passes as vnmodel_transform_passes
from .analysis import passes as vnmodel_analysis_passes
from . import testbench

if __name__ == "__main__":
  pipeline_main()
