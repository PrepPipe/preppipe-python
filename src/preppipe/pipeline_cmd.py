# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations
from .pipeline import pipeline_main

# 我们在这里要把所有注册了转换的模块全都引用进来，不然的话当该模块作为 __main__ 的时候，那些注册的代码不会被执行，转换也无法从命令行被调用
# 有使用 ToolClassDecl 的类的模块也应该在这里引用进来
# （以后应该搞个自定义的检查，代码里如果有加了注册的修饰符但没在这里包含的话就提示报错）

from .frontend import opendocument
from .frontend import docx
from .frontend import text
from .frontend import markdown
from .frontend import commandsyntaxparser
from .frontend import commanddocs
from .renpy import passes as renpy_passes
from .webgal import passes as webgal_passes
from .frontend.vnmodel import passes as vnparser_passes
from .frontend import inputexport
from .transform import passes as vnmodel_transform_passes
from .analysis import passes as vnmodel_analysis_passes
from . import testbench
from .util import imagepack
from .util import imagepackrecolortester
from .assets import imports as asset_imports
from .uiassetgen import toolentry as uiassetgen_toolentry

if __name__ == "__main__":
  pipeline_main()
