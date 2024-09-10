# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 此入口用于在从 PyPI 安装 preppipe 本体后初始化内置资源

import os
import sys
import argparse
import tempfile
import urllib.request
import zipfile

from .imports import *
from .assetmanager import AssetManager

_builtin_asset_zip_urls = [
  "https://github.com/PrepPipe/preppipe-python/releases/download/latest-main/builtin-assets.zip",
  "https://github.com/PrepPipe/preppipe-python/releases/download/latest-develop/builtin-assets.zip",
]

def init_builtin_assets(args : list[str] | None = None):
  parser = argparse.ArgumentParser(description="PrepPipe Built-in Assets Initializer")
  parser.add_argument("zipfile", nargs='?', help="Path to the built-in assets ZIP file")
  parser.add_argument("-f", "--force", action="store_true", help="Force re-initialization")

  if args is None:
    args = sys.argv[1:]
  parsed_args = parser.parse_args(args)

  if AssetManager.is_builtin_manifest_exists() and not parsed_args.force:
    print("Built-in assets have already been initialized. Use --force to re-initialize.")
    return

  # 先建一个临时目录，不管是下载还是解压都会用到
  with tempfile.TemporaryDirectory() as tmpdir:
    print(f"Using temporary directory {tmpdir} for built-in assets download")
    zipfile_path = parsed_args.zipfile
    if zipfile_path is None:
      zipfile_path = os.path.join(tmpdir, "builtin-assets.zip")
      # 尝试从预定义的 URL 下载
      is_downloaded = False
      for url in _builtin_asset_zip_urls:
        try:
          print(f"Trying {url}")
          _download_percentage = 0
          _is_size_printed = False
          def _show_progress(block_num, block_size, total_size):
            nonlocal _download_percentage
            nonlocal _is_size_printed
            if not _is_size_printed:
              # print the total size in MB
              print(f"size: {total_size / 1024 / 1024:.2f} MB")
              _is_size_printed = True
            cur_percentage = int(block_num * block_size * 100 / total_size)
            # print a single dot for every 1% increase
            # once we reach every 10%, print the percentage
            for i in range(_download_percentage+1, cur_percentage+1):
              print(".", end="")
              if i % 10 == 0:
                print(f" {i}%")
            _download_percentage = cur_percentage
          urllib.request.urlretrieve(url, zipfile_path, _show_progress)
          is_downloaded = True
          print("Download completed.")
          break
        except Exception as e:
          # 下载失败，尝试下一个 URL
          print(f"Failed: {e}")
      if not is_downloaded:
        print("Failed to download built-in assets from all predefined URLs. Please download manually.")
        return
    # 解压
    zip_ref = zipfile.ZipFile(zipfile_path, 'r')
    zip_ref.extractall(tmpdir)
    zip_ref.close()
    # 检查有没有一个叫 assets 的目录，没有的话就报错
    assets_dir = os.path.join(tmpdir, "assets")
    if not os.path.isdir(assets_dir):
      print("No 'assets' directory found in the ZIP file. Please check the ZIP file.")
      return
    AssetManager.tool_main(["--build-embedded", assets_dir])

if __name__ == "__main__":
  init_builtin_assets()
