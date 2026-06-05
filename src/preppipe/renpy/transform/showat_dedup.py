# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

"""Compare/dedup show ``at`` by placement only; ignore chained preppipe_sprite_* entry ATL."""

import re

# 与 codegen 链式 ``at screen2d_abs(...), preppipe_sprite_*`` 一致
_PREPPIPE_SPRITE_ATL_RE = re.compile(
  r",\s*preppipe_(?:sprite|at|move|rotate|zoom)[\w_]*\([^)]*\)",
  re.IGNORECASE,
)


def normalize_showat_for_placement_dedup(at_str: str | None) -> str | None:
  """去掉入场/特效 ATL 链，只保留 screen2d_abs 等放置 transform，供差分切换去重。"""
  if at_str is None:
    return None
  s = at_str.strip()
  if not s:
    return None
  prev = None
  while prev != s:
    prev = s
    s = _PREPPIPE_SPRITE_ATL_RE.sub("", s).strip().rstrip(",").strip()
  return s if s else None
