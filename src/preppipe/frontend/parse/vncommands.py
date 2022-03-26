# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0


import os
import io
import pathlib
import typing
import PIL.Image
import pydub
import pathlib
import functools
import enum
from enum import Enum
from .commands import *

@parsecommand("Comment")
def Comment(ctx : ParseContextBase) -> None:
  return

