# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from .ast import *
from ..vnmodel import *
from ..enginecommon.codegen import BackendCodeGenHelperBase

class _WebGalCodeGenHelper(BackendCodeGenHelperBase[WebGalNode]):
  pass
