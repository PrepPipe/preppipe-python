# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

"""由通用特效 IR 推导 WebGAL game/animation JSON 关键帧（与 Ren'Py preppipert 语义对齐的采样）。

TODO(WebGAL): 当前 `webgal/codegen` 对上述 IR 一律 `PPInternalError`，本模块保留供后续恢复导出时使用。
"""

from __future__ import annotations

import hashlib
import json
import math
import re

_SHAKE_SEG_S = 0.05
_SHAKE_CYCLE_S = 0.2


def _shake_offset_in_cycle(t_local: float, amp: float) -> float:
  if abs(amp) < 1e-12:
    return 0.0
  c = _SHAKE_CYCLE_S
  s = _SHAKE_SEG_S
  t_local = max(0.0, min(float(t_local), c - 1e-12))
  si = min(3, int(t_local // s))
  frac = (t_local - si * s) / s
  a = float(amp)
  if si == 0:
    return frac * a
  if si == 1:
    return a + frac * (-2.0 * a)
  if si == 2:
    return -a + frac * (a * 0.45 + a)
  return a * 0.45 * (1.0 - frac)


def shake_xy_keyframes(duration_s: float, amplitude: float, direction: str) -> list[dict]:
  """position.x/y 为像素偏移；与 preppipert._preppipe_char_shake_transform 同周期波形。"""
  d = max(0.0, float(duration_s))
  dkey = str(direction or "").strip().lower()
  xh = 0 if dkey in ("vertical", "v", "y", "垂直") else 1
  yh = 0 if dkey in ("horizontal", "h", "x", "水平") else 1
  ax = float(amplitude) * xh
  ay = float(amplitude) * yh
  if d <= 1e-9:
    return [{"position": {"x": 0, "y": 0}, "duration": 0}]
  step_s = 1.0 / 60.0
  frames: list[dict] = []
  t = 0.0
  prev_x = prev_y = 0.0
  while t < d:
    tl = t % _SHAKE_CYCLE_S
    ox = _shake_offset_in_cycle(tl, ax)
    oy = _shake_offset_in_cycle(tl, ay)
    seg = min(step_s, d - t)
    dur_ms = max(1, int(round(seg * 1000)))
    if not frames:
      frames.append({"position": {"x": ox, "y": oy}, "duration": 0})
    else:
      frames.append({"position": {"x": ox, "y": oy}, "duration": dur_ms})
    prev_x, prev_y = ox, oy
    t += seg
  ox = oy = 0.0
  frames.append({"position": {"x": ox, "y": oy}, "duration": max(1, int(round(0.02 * 1000)))})
  return frames


def bounce_y_keyframes(duration_s: float, height_px: float, count: int) -> list[dict]:
  d = max(0.0, float(duration_s))
  h = float(height_px)
  n = max(1, int(count))
  if d <= 1e-9:
    return [{"position": {"x": 0, "y": 0}, "duration": 0}]

  def y_at(t: float) -> float:
    if t >= d:
      return 0.0
    t = min(float(t), d - 1e-12)
    fb = ((t / d) * n) % 1.0
    if fb < 0.5:
      return -h * (fb * 2.0)
    return -h * (2.0 - 2.0 * fb)

  step_s = 1.0 / 60.0
  frames: list[dict] = []
  t = 0.0
  while t < d:
    yy = y_at(t)
    seg = min(step_s, d - t)
    dur_ms = max(1, int(round(seg * 1000)))
    if not frames:
      frames.append({"position": {"x": 0, "y": yy}, "duration": 0})
    else:
      frames.append({"position": {"x": 0, "y": yy}, "duration": dur_ms})
    t += seg
  frames.append({"position": {"x": 0, "y": 0}, "duration": max(1, int(round(0.02 * 1000)))})
  return frames


def _ease_linear(t: float) -> float:
  return t


def _ease_ease(t: float) -> float:
  return t * t * (3.0 - 2.0 * t)


def _ease_in(t: float) -> float:
  return t * t


def _ease_out(t: float) -> float:
  return 1.0 - (1.0 - t) * (1.0 - t)


def _ease_fn(style: str):
  s = (style or "linear").strip().lower()
  if s == "ease":
    return _ease_ease
  if s == "easein":
    return _ease_in
  if s == "easeout":
    return _ease_out
  return _ease_linear


def move_xy_keyframes(
  sx: float, sy: float, ex: float, ey: float, duration_s: float, style: str
) -> list[dict]:
  d = max(0.0, float(duration_s))
  ease = _ease_fn(style)
  if d <= 1e-9:
    return [{"position": {"x": 0, "y": 0}, "duration": 0}]
  dx_total = float(ex) - float(sx)
  dy_total = float(ey) - float(sy)
  n = max(2, min(32, int(d * 30) + 1))
  frames: list[dict] = []
  for i in range(n):
    t = i / (n - 1) if n > 1 else 1.0
    u = ease(t)
    px = dx_total * u
    py = dy_total * u
    if i == 0:
      frames.append({"position": {"x": px, "y": py}, "duration": 0})
    else:
      prev_u = ease((i - 1) / (n - 1) if n > 1 else 0.0)
      seg_t = (t - ((i - 1) / (n - 1) if n > 1 else 0.0)) * d
      dur_ms = max(1, int(round(seg_t * 1000)))
      frames.append({"position": {"x": px, "y": py}, "duration": dur_ms})
  return frames


def scale_keyframes(z_end: float, duration_s: float) -> list[dict]:
  d = max(0.0, float(duration_s))
  z1 = float(z_end)
  if d <= 1e-9:
    return [{"scale": {"x": z1, "y": z1}, "duration": 0}]
  n = max(2, min(24, int(d * 24) + 1))
  frames: list[dict] = []
  for i in range(n):
    t = i / (n - 1) if n > 1 else 1.0
    z = 1.0 + (z1 - 1.0) * t
    if i == 0:
      frames.append({"scale": {"x": z, "y": z}, "duration": 0})
    else:
      seg_t = d / (n - 1)
      dur_ms = max(1, int(round(seg_t * 1000)))
      frames.append({"scale": {"x": z, "y": z}, "duration": dur_ms})
  return frames


def rotate_keyframes(angle_rad: float, duration_s: float) -> list[dict]:
  d = max(0.0, float(duration_s))
  a = float(angle_rad)
  if d <= 1e-9:
    return [{"rotation": a, "duration": 0}]
  n = max(2, min(24, int(d * 24) + 1))
  frames: list[dict] = []
  for i in range(n):
    t = i / (n - 1) if n > 1 else 1.0
    ang = a * t
    if i == 0:
      frames.append({"rotation": ang, "duration": 0})
    else:
      seg_t = d / (n - 1)
      dur_ms = max(1, int(round(seg_t * 1000)))
      frames.append({"rotation": ang, "duration": dur_ms})
  return frames


def tremble_x_keyframes(amplitude: float, half_period_s: float, n_cycles: int) -> list[dict]:
  amp = float(amplitude)
  hp = max(0.001, float(half_period_s))
  n = max(1, int(n_cycles))
  dur_ms = max(1, int(round(hp * 1000)))
  frames: list[dict] = [{"position": {"x": 0, "y": 0}, "duration": 0}]
  for _ in range(n):
    frames.append({"position": {"x": amp, "y": 0}, "duration": dur_ms})
    frames.append({"position": {"x": -amp, "y": 0}, "duration": dur_ms})
  frames.append({"position": {"x": 0, "y": 0}, "duration": max(1, int(round(0.02 * 1000)))})
  return frames


def tremble_loop_x_keyframes(amplitude: float, period_s: float, duration_s: float) -> list[dict]:
  """有限时长内循环往复（与 repeat 近似）。"""
  amp = float(amplitude)
  per = max(0.04, float(period_s))
  d = float(duration_s)
  halfp = max(0.001, per / 2.0)
  n = max(1, int(d / per))
  return tremble_x_keyframes(amp, halfp, n)


_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def parse_hex_rgb(color: str) -> tuple[int, int, int]:
  s = (color or "#ffffff").strip()
  m = _HEX_RE.match(s)
  if not m:
    return 255, 255, 255
  h = m.group(1)
  if len(h) == 3:
    h = "".join(c * 2 for c in h)
  r = int(h[0:2], 16)
  g = int(h[2:4], 16)
  b = int(h[4:6], 16)
  return r, g, b


def flash_keyframes(fade_in_s: float, hold_s: float, fade_out_s: float, color: str) -> list[dict]:
  fi = max(0.0, float(fade_in_s))
  hld = max(0.0, float(hold_s))
  fo = max(0.0, float(fade_out_s))
  r, g, b = parse_hex_rgb(color)
  frames: list[dict] = [{"alpha": 1.0, "brightness": 1.0, "duration": 0}]
  if fi > 1e-9:
    n = max(2, int(fi * 30) + 1)
    for i in range(1, n + 1):
      t = i / n
      frames.append(
        {
          "alpha": 1.0 - t * 0.82,
          "brightness": 1.0 + 0.4 * t,
          "colorRed": r,
          "colorGreen": g,
          "colorBlue": b,
          "duration": max(1, int(round(fi * 1000 / n))),
        }
      )
  if hld > 1e-9:
    frames.append(
      {
        "alpha": 0.18,
        "brightness": 1.4,
        "colorRed": r,
        "colorGreen": g,
        "colorBlue": b,
        "duration": max(1, int(round(hld * 1000))),
      }
    )
  if fo > 1e-9:
    n = max(2, int(fo * 30) + 1)
    for i in range(1, n + 1):
      t = i / n
      frames.append(
        {
          "alpha": 0.18 + t * 0.82,
          "brightness": 1.4 - t * 0.4,
          "colorRed": int(round(r + (255 - r) * t)),
          "colorGreen": int(round(g + (255 - g) * t)),
          "colorBlue": int(round(b + (255 - b) * t)),
          "duration": max(1, int(round(fo * 1000 / n))),
        }
      )
  frames.append(
    {
      "alpha": 1.0,
      "brightness": 1.0,
      "colorRed": 255,
      "colorGreen": 255,
      "colorBlue": 255,
      "duration": max(1, int(round(0.02 * 1000))),
    }
  )
  return frames


def stable_animation_name(prefix: str, payload: dict) -> str:
  raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
  h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
  safe_p = re.sub(r"[^a-zA-Z0-9_]", "_", prefix)[:24]
  return f"pp_{safe_p}_{h}"


def animation_json_dumps(frames: list[dict]) -> str:
  return json.dumps(frames, ensure_ascii=False, separators=(",", ":"))
