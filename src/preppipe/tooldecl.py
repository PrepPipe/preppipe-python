# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 语涵编译器除了正常的编译流程外，可能还需要一些额外的工具，这些工具共用部分代码但是不使用基于 Transform 的流程和命令行参数读取。
# 第一个有此需求的工具是图片包生成工具 (preppipe.util.imagepack)。
# 为了支持将这些工具也包含到CI/CD流程中，我们使用环境变量 PREPPIPE_TOOL 来指定当前运行的工具，如果没有指定就用默认的编译流程。
# 该文件定义支持自动注册工具的修饰符

_registered_tools : dict[str, type] = {}

def ToolClassDecl(name : str): # pylint: disable=invalid-name
  def decorator(cls):
    assert name not in _registered_tools, f"Duplicate tool name {name}"
    # 确认该类有一个叫 tool_main(args : list[str] | None) 的静态方法
    assert hasattr(cls, "tool_main"), f"Tool {name} must have a static method tool_main(args : list[str] | None)"
    _registered_tools[name] = cls
    return cls
  return decorator
