# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该文件存放一些帮助代码生成的函数
# 有些逻辑在解析与生成时都会用到，比如查找图片表达式等，我们把这些实现放在这

import re

from ...irbase import *
from ...imageexpr import *
from ..commandsemantics import *
from ..commandsyntaxparser import *
from .vnast import *

class VNASTImageExprSource(enum.Enum):
  # 当我们要读取树结构的图片表达式时，用这个来表示图片表达式是用来干什么的
  # 这样当读取占位表达式时可以生成对应的结构
  SRC_CHARACTER_SPRITE    = enum.auto() # 人物立绘
  SRC_CHARACTER_SIDEIMAGE = enum.auto() # 人物头像
  SRC_SCENE_BACKGROUND    = enum.auto() # 场景背景

def emit_default_placeholder(context : Context, dest : ImageExprPlaceholderDest, screen_resolution : tuple[int, int] | None = None, description : StringLiteral | None = None) -> PlaceholderImageLiteralExpr:
  if screen_resolution is None:
    screen_resolution = (1920, 1080)
  finalresolution = screen_resolution
  width, height = screen_resolution
  match dest:
    case ImageExprPlaceholderDest.DEST_SCENE_BACKGROUND:
      pass
    case ImageExprPlaceholderDest.DEST_CHARACTER_SPRITE:
      width_p = int(600 * height / 1080)
      finalresolution = (width_p, height)
    case ImageExprPlaceholderDest.DEST_CHARACTER_SIDEIMAGE:
      width_p = int(600 * min(width, height) / 1080)
      finalresolution = (width_p, width_p)
    case _:
      pass
  if description is None:
    description = StringLiteral.get('', context)
  placeholder = PlaceholderImageLiteralExpr.get(context=context, dest=dest, desc=description, size=IntTupleLiteral.get(finalresolution, context))
  return placeholder

def parse_pixel_resolution_str(s : str) -> tuple[int, int] | None:
  # 解析一个 "Width*Height" 的字符串，返回 [宽,高] 的元组
  if result := re.match(r"""^(?P<width>\d+)\s*[*xX,]\s*(?P<height>\d+)$""", s):
    width = int(result.group("width"))
    height = int(result.group("height"))
    return (width, height)
  return None

def _try_open_image(p : str) -> tuple[str, str] | None:
  with PIL.Image.open(p) as image:
    format = image.format
    assert format is not None and len(format) > 0 # should have a format if loaded from file
    try:
      image.verify()
      return (p, format)
    except:
      return None
  return None

def emit_image_expr_from_path(context : Context, pathexpr : str, basepath : str) -> BaseImageLiteralExpr | None:
  # 如果提供了图片路径，则当场读取图片内容，创建 ImageAssetLiteralExpr
  # 如果是占位、声明这种，则根据情况特判
  if t := context.get_file_auditor().search(querypath=pathexpr, basepath=basepath, filecheckCB=_try_open_image):
    path, fmt = t
    asset = context.get_or_create_image_asset_data_external(path, fmt)
    data = asset.load()
    assert data is not None
    return ImageAssetLiteralExpr.get(context, image=asset, size=IntTupleLiteral.get(data.size, context))
  return None

def _is_image_expr_name_placeholder(s : str) -> bool:
  return s in ('Placeholder', '占位')

def emit_image_expr_from_callexpr(context : Context, call : CallExprOperand, placeholderdest : ImageExprPlaceholderDest, warnings : list[tuple[str, str]], screen_resolution : tuple[int, int] | None = None) -> BaseImageLiteralExpr | None:
  # 调用表达式有以下几种可能：
  # 占位（分辨率=...，描述=...），分辨率和描述均可选，按位参数视为分辨率
  # 声明（分辨率=...，引用=...）, 分辨率和引用均必需，不允许按位参数
  # 纯色填充（分辨率=..., 颜色=...），均必须，不允许按位参数
  # 所有的分辨率都是一个"宽*高"的字符串，比如 "1920*1080"

  _resolution_nametuple = ('Resolution', '分辨率')
  _description_nametuple = ('Description', '描述')
  _reference_nametuple = ('Ref', '引用')
  _color_nametuple = ('Color', '颜色', '顏色')

  def handle_resolution_arg(k : str, v : Value) -> tuple[int, int] | None:
    if isinstance(v, StringLiteral):
      resolution = parse_pixel_resolution_str(v.get_string())
      if resolution is not None:
        return resolution
    warnings.append(('vnparse-invalid-resolution-expr',str(v)))
    return None

  def handle_color_arg(k : str, v : Value) -> Color | None:
    if isinstance(v, StringLiteral):
      try:
        return Color.get(v.get_string())
      except:
        pass
    warnings.append(('vnparse-invalid-color-expr',str(v)))
    return None

  if _is_image_expr_name_placeholder(call.name):
    resolution = None
    description = None
    for k, v in call.kwargs.items():
      if k in _resolution_nametuple:
        resolution = handle_resolution_arg(k, v)
        continue
      if k in _description_nametuple:
        if isinstance(v, StringLiteral):
          description = v
        else:
          description = StringLiteral.get(str(v), context)
        continue
      # 到这就说明参数读取失败
      warnings.append(('vnparse-placeholderexpr-unexpected-argument', k))
    consumed_posargs = 0
    if resolution is None and len(call.args) > 0:
      firstarg = call.args[0]
      consumed_posargs += 1
      if isinstance(firstarg, StringLiteral):
        resolution = parse_pixel_resolution_str(firstarg.get_string())
      if resolution is None:
        warnings.append(('vnparse-invalid-resolution-expr',str(firstarg)))
    if len(call.args) > consumed_posargs:
      warnings.append(('vnparse-placeholderexpr-too-many-arguments', str(len(call.args)) + ' positional argument(s) provided, ' + str(consumed_posargs) + ' used'))
    if resolution is None and description is None:
      return emit_default_placeholder(context=context, dest=placeholderdest, screen_resolution=screen_resolution)
    if description is None:
      description = StringLiteral.get('', context)
    if resolution is None:
      resolution = screen_resolution
      if resolution is None:
        resolution = (1920, 1080)
    return PlaceholderImageLiteralExpr.get(context=context, dest=placeholderdest, desc=description, size=IntTupleLiteral.get(resolution, context))

  if call.name in ('Decl', '声明', '聲明'):
    resolution = None
    ref = None
    for k, v in call.kwargs.items():
      if k in _resolution_nametuple:
        resolution = handle_resolution_arg(k, v)
        continue
      if k in _reference_nametuple:
        if isinstance(v, StringLiteral):
          ref = v
        else:
          ref = StringLiteral.get(str(v), context)
        continue
      warnings.append(('vnparse-declexpr-unexpected-argument', k))

    # 缺了任一参数就用默认的占位表达式
    if ref is None:
      warnings.append(('vnparse-declexpr-missing-argument', str(_reference_nametuple)))
      return emit_default_placeholder(context=context, dest=placeholderdest, screen_resolution=screen_resolution)
    if resolution is None:
      warnings.append(('vnparse-declexpr-missing-argument', str(_resolution_nametuple)))
      return emit_default_placeholder(context=context, dest=placeholderdest, screen_resolution=screen_resolution)

    if len(call.args) > 0:
      warnings.append(('vnparse-declexpr-too-many-arguments', str(len(call.args)) + ' positional argument(s) provided, none used'))
    return DeclaredImageLiteralExpr.get(context=context, decl=ref, size=IntTupleLiteral.get(resolution, context))

  if call.name in ('ColorFill', '纯色填充', '純色填充'):
    resolution = None
    color = None
    for k, v in call.kwargs.items():
      if k in _resolution_nametuple:
        resolution = handle_resolution_arg(k, v)
        continue
      if k in _color_nametuple:
        color = handle_color_arg(k, v)
        continue
      warnings.append(('vnparse-colorfillexpr-unexpected-argument', k))

    if resolution is None or color is None:
      if color is None:
        warnings.append(('vnparse-colorfillexpr-missing-argument', str(_color_nametuple)))
      if resolution is None:
        warnings.append(('vnparse-colorfillexpr-missing-argument', str(_resolution_nametuple)))
      return emit_default_placeholder(context=context, dest=placeholderdest, screen_resolution=screen_resolution)

    if len(call.args) > 0:
      warnings.append(('vnparse-declexpr-too-many-arguments', str(len(call.args)) + ' positional argument(s) provided, none used'))

    return ColorImageLiteralExpr.get(context=context, color=ColorLiteral.get(color, context), size=IntTupleLiteral.get(resolution, context))

  # 暂不支持的表达式类型
  return None

def emit_image_expr_from_str(context : Context, s : str, basepath : str,  placeholderdest : ImageExprPlaceholderDest, warnings : list[tuple[str, str]], screen_resolution : tuple[int, int] | None = None) -> BaseImageLiteralExpr | None:
  # 不确定字符串是什么形式
  # 先尝试转化成调用表达式，不行的话试试当成路径
  # 都不行的话视为失败
  # 由于如果字符串不带()的话，命令解析代码不会将字符串内容视为调用，
  # 所以我们需要对这种情况特判
  # （现在仅有占位可以不需要额外参数，所以只需检查占位的情况）
  if _is_image_expr_name_placeholder(s):
    return emit_default_placeholder(context=context, dest=placeholderdest, screen_resolution=screen_resolution)
  if cmd := try_parse_value_expr(s, context.null_location):
    if isinstance(cmd, GeneralCommandOp):
      callexpr = FrontendParserBase.parse_commandop_as_callexpr(cmd)
      return emit_image_expr_from_callexpr(context=context, call=callexpr, placeholderdest=placeholderdest, warnings=warnings, screen_resolution=screen_resolution)
    s = cmd
  if result := emit_image_expr_from_path(context=context, pathexpr=s, basepath=basepath):
    return result
  return None

def _try_open_audio(p : str) -> str | None:
  try:
    f = pydub.AudioSegment.from_file(p)
    if len(f) > 0:
      # len(f) 是时长，单位是毫秒
      return p
  except:
    return None
  return None

def emit_audio_from_path(context : Context, pathexpr : str, basepath : str) -> AudioAssetData | None:
  if path := context.get_file_auditor().search(querypath=pathexpr, basepath=basepath, filecheckCB=_try_open_audio):
    return context.get_or_create_audio_asset_data_external(path, None)
  return None

def parse_transition(context : Context, transition_name : str, transition_args : list[Literal], transition_kwargs : dict[str, Literal], warnings : list[tuple[str, str]]) -> Value | tuple[StringLiteral, StringLiteral] | None:
  # 如果没有提供转场，就返回 None
  # 如果提供了后端专有的转场，则返回 tuple[StringLiteral, StringLiteral] 表示后端名和表达式
  # 如果提供了通用的转场，则返回对应的值 (Value)

  if len(transition_name) == 0:
    return None

  # 目前我们支持以下转场：
  # 1. 无：立即发生，无转场
  # 2. 后端转场<表达式，后端>：后端专有的表达式
  # 等以后做通用的再加
  if transition_name in ("None", "无", "無"):
    return VNDefaultTransitionType.DT_NO_TRANSITION.get_enum_literal(context)

  if transition_name in ("BackendTransition", "后端转场", "後端轉場"):
    backend_name = None
    expr = None
    def try_set_backend(s : Literal):
      nonlocal backend_name
      if isinstance(s, StringLiteral):
        backend_name = s
      elif isinstance(s, TextFragmentLiteral):
        backend_name = s.content
      else:
        warnings.append(("vncodegen-transition-invalid-argument", "unexpected backend value type: " + type(s).__name__))

    def try_set_expr(s : Literal):
      nonlocal expr
      if isinstance(s, StringLiteral):
        expr = s
      elif isinstance(s, TextFragmentLiteral):
        expr = s.content
      else:
        warnings.append(("vncodegen-transition-invalid-argument", "unexpected expression value type: " + type(s).__name__))

    if len(transition_args) > 0:
      if len(transition_args) == 1:
        try_set_expr(transition_args[0])
      else:
        warnings.append(("vncodegen-transition-unused-args", "extra positional arguments " + ','.join([str(v) for v in transition_args[1:]]) + " ignored"))
    for k, v in transition_kwargs.items():
      if k in ("expr", "表达式", "表達式"):
        try_set_expr(v)
      elif k in ("backend", "后端", "後端"):
        try_set_backend(v)
    if backend_name is None or expr is None:
      # 如果任意一项没填，视为默认转场
      warnings.append(("vncodegen-transition-incomplete-args", "BackendTransition expects both <expr, backend>; using default transition"))
      return None
    return (backend_name, expr)
  return None
