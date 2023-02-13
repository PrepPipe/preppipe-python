# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import enum

class IRJsonRepr(enum.Enum):
  # 对象的一些值在 JSON 对象中所使用的键 (key)
  # 我们希望这些值尽量短以节省空间
  # 为了保证无歧义，即使对象类型不同，我们在这里也不会复用
  LOCATION_FILE_PATH = 'fp'
  TYPE_PARAMETERIZED_PARAM = 'tp'
  VALUE_VALUETYPE = 't' # the type of the value
  VALUE_VALUEID = 'vid' # an ID representing the value
