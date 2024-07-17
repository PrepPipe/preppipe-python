# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 语涵编译器做输出时会有一些部分执行的很慢（比如导出自定义后的图片模板）
# 我们通过这个输出缓存来减少这种情况下的重复操作

import typing
import json
import os
import pathlib
import concurrent.futures

from ._version import __version__
from .irbase import *
from .irdataop import *
from .commontypes import *
from .exceptions import *
from .assets.assetmanager import AssetManager

@IRObjectJsonTypeName("cacheable_op_symbol")
class CacheableOperationSymbol(Symbol):
  # 用来描述单个可缓存的操作
  # 每一个 CacheableOperationSymbol 都应该有一个唯一的名称，此名称应该从操作的输入参数中生成，重名的操作应该被认为是相同的操作
  # 当顶层操作项需要有可缓存的操作时，应该使用一个 SymbolTableRegion[CacheableOperationSymbol] 来存储这些操作
  # 需要进行导出时使用 run_export_all() 方法来执行所有的操作

  # 我们使用 CacheableOperationSymbol.CACHE_FILE_NAME 所指定的文件来存储所有已执行过的操作
  # 如果一个操作没在这个文件中，我们就认为它没有被执行过，即使目标文件已经存在，我们也会重新执行这个操作
  # 如果一个操作在这个文件中，我们就认为它已经被执行过，如果目标文件已经存在，我们不会再次执行这个操作且不检查目标文件是否被改动过（有可能是用户特意改动的）
  # 但是如果文件不存在，我们会重新执行这个操作（用户可以以此强制重新生成文件）
  # 这个文件应该是一个 JSON 文件，格式如下：
  # {
  #   "version": <__version__>,
  #   "cacheable": [<name1>, <name2>, ...]
  # }
  CACHE_FILE_NAME : typing.ClassVar[str] = 'cache.json'

  def get_export_file_list(self) -> list[str]:
    # 返回这个操作导出的文件列表，只需要基于输出根目录的相对路径
    raise NotImplementedError("Should be implemented by subclass")

  def run_export(self, output_rootdir : str) -> None:
    # 执行这个操作的导出，output_rootdir 是输出根目录
    # 一般会在一个新的线程中执行这个操作
    raise NotImplementedError("Should be implemented by subclass")

  def get_depended_assets(self) -> list[str]:
    # 返回这个操作依赖的资源文件列表
    # 所有需要的资源都会在导出前预加载，这样资源使用时就不用管加载时的 race condition 问题
    return []

  def get_workload_cpu_usage_estimate(self) -> float:
    # 返回这个操作的 CPU 使用量估计(1: CPU 密集型；0: I/O 密集型)，用于计算线程池的大小和计算调度
    return 0.5

  @staticmethod
  def run_export_all(ops: "typing.Iterable[CacheableOperationSymbol]", output_rootdir : str) -> None:
    # 执行所有的操作; ops 一般应该是 SymbolTableRegion[CacheableOperationSymbol]
    cache_file_path = os.path.join(output_rootdir, CacheableOperationSymbol.CACHE_FILE_NAME)

    # 读取已执行过的操作
    existing_ops : set[str] = set()
    is_cache_require_change = False
    with open(cache_file_path, 'r', encoding="utf-8") as f:
      json_content = json.load(f)
      if json_content['version'] == __version__:
        # 我们只在版本号匹配时才读取缓存
        for op_name in json_content['cacheable']:
          if not isinstance(op_name, str):
            is_cache_require_change = True
            continue
          existing_ops.add(op_name)
      else:
        is_cache_require_change = True

    # 准备预加载资源
    asset_manager = AssetManager.get_instance()

    all_ops : list[str] = []
    todo_ops : list[tuple[CacheableOperationSymbol, float]] = [] # (op, cpu_usage_estimate)
    loaded_assets : set[str] = set()
    cpu_usage_sum = 0.0
    cpu_usage_minimum = 0.2
    for elem in ops:
      all_ops.append(elem.name)
      if elem.name in existing_ops:
        # 检查文件是否还都存在，都存在的话就跳过
        all_files_exist = True
        filelist = elem.get_export_file_list()
        for filename in filelist:
          if not os.path.exists(os.path.join(output_rootdir, filename)):
            all_files_exist = False
            break
        if all_files_exist:
          continue
      is_asset_preload_failed = False
      for asset in elem.get_depended_assets():
        if asset in loaded_assets:
          continue
        handle = asset_manager.get_asset(asset)
        if handle is None:
          # 无法加载资源的话就跳过这个操作
          is_asset_preload_failed = True
          break
        loaded_assets.add(asset)
      if is_asset_preload_failed:
        continue
      # 我们确认这个操作需要且可以执行
      cpu_usage_estimate = elem.get_workload_cpu_usage_estimate()
      if cpu_usage_estimate < 0 or cpu_usage_estimate > 1:
        raise ValueError("Invalid CPU usage estimate")
      todo_ops.append((elem, cpu_usage_estimate))
      cpu_usage_sum += max(cpu_usage_minimum, cpu_usage_estimate)
      is_cache_require_change = True

    threadpool = None
    task_count = len(todo_ops)
    if task_count > 0:
      # 有操作需要执行
      # 我们需要手动计算线程数量，因为默认值假设的是 I/O 密集型任务
      numthreads = os.cpu_count()
      threads_multiplier = task_count / cpu_usage_sum
      if numthreads is None:
        numthreads = 1
      numthreads = max(1, int(numthreads * threads_multiplier))
      threadpool = concurrent.futures.ThreadPoolExecutor(max_workers=numthreads)
      todo_ops.sort(key=lambda x: x[1], reverse=True)
      # 交替执行操作
      is_scheduling_io = True
      io_cpu_usage_sum = 0.0
      cpu_cpu_usage_sum = 0.0
      num_io_tasks_scheduled = 0
      num_cpu_tasks_scheduled = 0
      while num_io_tasks_scheduled + num_cpu_tasks_scheduled < task_count:
        if is_scheduling_io:
          op, cpu_usage_estimate = todo_ops[task_count - 1 - num_io_tasks_scheduled]
          threadpool.submit(op.run_export, output_rootdir)
          num_io_tasks_scheduled += 1
          io_cpu_usage_sum += max(cpu_usage_minimum, cpu_usage_estimate)
          next_cpu_usage = todo_ops[num_cpu_tasks_scheduled][1]
          if io_cpu_usage_sum > (next_cpu_usage + cpu_cpu_usage_sum):
            is_scheduling_io = False
        else:
          op, cpu_usage_estimate = todo_ops[num_cpu_tasks_scheduled]
          threadpool.submit(op.run_export, output_rootdir)
          num_cpu_tasks_scheduled += 1
          cpu_cpu_usage_sum += max(cpu_usage_minimum, cpu_usage_estimate)
          next_cpu_usage = todo_ops[task_count - 1 - num_io_tasks_scheduled][1]
          if cpu_cpu_usage_sum > (next_cpu_usage + io_cpu_usage_sum):
            is_scheduling_io = True

    if is_cache_require_change:
      # 更新缓存
      all_ops.sort()
      with open(cache_file_path, 'w', encoding="utf-8") as f:
        json.dump({
          "version": __version__,
          "cacheable": all_ops
        }, f)

    if threadpool is not None:
      threadpool.shutdown(wait=True)
