# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ..irbase import *
from .vntype import *

class VNAsset(Operation, AssetBase):
  def __init__(self, name: str, loc: Location, **kwargs) -> None:
    super().__init__(name, loc, **kwargs)

class VNImageAsset(VNAsset):
  pass