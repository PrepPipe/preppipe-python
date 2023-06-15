# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import dataclasses
import enum
import typing
from typing import Any

from ...irbase import *
from ...vnmodel_v4 import *
from ..commandsyntaxparser import *
from .vnast import *


def vncodegen(ast : VNAST) -> VNModel:
  return VNModel.create(ast.context)

