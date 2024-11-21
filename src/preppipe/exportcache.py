# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 语涵编译器做输出时会有一些部分执行的很慢（比如导出自定义后的图片模板）
# 我们通过这个输出缓存来减少这种情况下的重复操作

import typing
import json
import os
import pathlib
import concurrent.futures

from . import __version__
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

  TR_exportcache = TranslationDomain("exportcache")
  CACHE_FILE_NAME : typing.ClassVar[str] = '.preppipe_export_cache.json'

  def get_export_file_list(self) -> list[str]:
    # 返回这个操作导出的文件列表，只需要基于输出根目录的相对路径
    raise NotImplementedError("Should be implemented by subclass")

  @classmethod
  def cls_prepare_export(cls, tp : concurrent.futures.ThreadPoolExecutor) -> None:
    # 如果需要执行操作，这个函数会在执行前被调用一次
    # 要 jit 或者做一些其他准备工作的话可以在这里做
    pass

  def instance_prepare_export(self, tp : concurrent.futures.ThreadPoolExecutor) -> bool:
    # 每个实例在执行前会在主线程调用这个函数
    # 如果返回 False 则表示这个操作不需要执行
    return True

  def run_export(self, output_rootdir : str) -> None:
    # 执行这个操作的导出，output_rootdir 是输出根目录
    # 一般会在一个新的线程中执行这个操作
    raise NotImplementedError("Should be implemented by subclass")

  _tr_exporting_file = TR_exportcache.tr("exporting_file",
    en="Exporting {file}",
    zh_cn="正在导出 {file}",
    zh_hk="正在導出 {file}",
  )
  _tr_updating_cache_file = TR_exportcache.tr("updating_cache_file",
    en="Updating cache file",
    zh_cn="正在更新缓存文件",
    zh_hk="正在更新快取檔案",
  )

  @staticmethod
  def report_exporting_file(relpath : str) -> None:
    MessageHandler.get().info(CacheableOperationSymbol._tr_exporting_file.format(file=relpath))

  @staticmethod
  def run_export_all(ops: "typing.Iterable[CacheableOperationSymbol]", output_rootdir : str) -> None:
    # 执行所有的操作; ops 一般应该是 SymbolTableRegion[CacheableOperationSymbol]
    cache_file_path = os.path.join(output_rootdir, CacheableOperationSymbol.CACHE_FILE_NAME)

    # 读取已执行过的操作
    existing_ops : set[str] = set()
    is_cache_require_change = False
    if os.path.exists(cache_file_path):
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

    all_ops : list[str] = []
    todo_ops_dict : dict[type, list[CacheableOperationSymbol]] = {}
    threadpool = None
    task_count = 0
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

      # 自定义准备工作
      if threadpool is None:
        threadpool = concurrent.futures.ThreadPoolExecutor()
      opclass = elem.__class__
      if opclass not in todo_ops_dict:
        opclass.cls_prepare_export(threadpool)
        todo_ops_dict[opclass] = []
      if not elem.instance_prepare_export(threadpool):
        continue
      todo_ops_dict[opclass].append(elem)
      task_count += 1

    if task_count > 0:
      is_cache_require_change = True
      if threadpool is None:
        raise PPInternalError("Threadpool not initialized")
      for opclass, op_list in todo_ops_dict.items():
        for op in op_list:
          threadpool.submit(op.run_export, output_rootdir)

    if is_cache_require_change:
      # 更新缓存
      MessageHandler.get().info(CacheableOperationSymbol._tr_updating_cache_file.get() + ' ' + CacheableOperationSymbol.CACHE_FILE_NAME)
      all_ops.sort()
      with open(cache_file_path, 'w', encoding="utf-8") as f:
        json.dump({
          "version": __version__,
          "cacheable": all_ops
        }, f)

    if threadpool is not None:
      threadpool.shutdown(wait=True)
