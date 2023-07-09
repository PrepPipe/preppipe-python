# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import shutil
import os
import subprocess

from .._version import __version__

def get_version_string() -> str:
  if shutil.which('git') is not None:
    utilpath = os.path.dirname(os.path.abspath(__file__))
    try:
      result = subprocess.run(['git', 'describe', '--tags'], timeout=1, capture_output=True, cwd=utilpath, check=False)
      if result.returncode == 0:
        return result.stdout.decode().strip()
    except: # pylint: disable=bare-except
      pass
  return __version__
