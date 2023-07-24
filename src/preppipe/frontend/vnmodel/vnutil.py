# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该文件存放一些帮助代码生成的函数
# 有些逻辑在解析与生成时都会用到，比如查找图片表达式等，我们把这些实现放在这

import re
import traceback

from ...irbase import *
from ...imageexpr import *
from ..commandsemantics import *
from ..commandsyntaxparser import *
from .vnast import *
from ...commontypes import MessageHandler
from ...exceptions import *
from ...language import TranslationDomain

_TR_vn_util = TranslationDomain("vn_util")

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

_tr_vn_util_image_open_failed = _TR_vn_util.tr("image_open_failed",
  en="File {path} cannot be opened as image.",
  zh_cn="文件 {path} 不能用作图片。",
  zh_hk="文件 {path} 不能用作圖片。",
)
_tr_vn_util_image_verify_failed = _TR_vn_util.tr("image_verify_failed",
  en="Image file {path} verification failed and cannot be used as image.",
  zh_cn="图片文件 {path} 校验失败，无法用作图片。",
  zh_hk="圖片文件 {path} 校驗失敗，無法用作圖片。",
)

def emit_image_expr_from_path(context : Context, pathexpr : str, basepath : str, warnings : list[tuple[str, str]]) -> BaseImageLiteralExpr | None:
  # 如果提供了图片路径，则当场读取图片内容，创建 ImageAssetLiteralExpr
  # 如果是占位、声明这种，则根据情况特判
  def _try_open_image(p : str) -> tuple[str, str] | None:
    nonlocal warnings
    try:
      with PIL.Image.open(p) as image:
        format = image.format
        if format is None or len(format) == 0:
          raise PPAssertionError("should have a format if loaded from file")
        try:
          image.verify()
          return (p, format)
        except Exception as e:
          traceback.print_exception(e)
          msg = _tr_vn_util_image_verify_failed.format(path=p)
          MessageHandler.critical_warning(msg)
          warnings.append(("vnutil-image-verify-failed", msg))
          return None
    except Exception:
      warnings.append(("vnutil-image-open-failed", _tr_vn_util_image_open_failed.format(path=p)))
    return None
  if t := context.get_file_auditor().search(querypath=pathexpr, basepath=basepath, filecheckCB=_try_open_image):
    path, fmt = t
    asset = context.get_or_create_image_asset_data_external(path, fmt)
    data = asset.load()
    assert data is not None
    return ImageAssetLiteralExpr.get(context, image=asset, size=IntTupleLiteral.get(data.size, context))
  return None

_tr_placeholder = _TR_vn_util.tr("placeholder",
  en="Placeholder",
  zh_cn="占位",
  zh_hk="占位",
)

def _is_image_expr_name_placeholder(s : str) -> bool:
  return s in _tr_placeholder.get_all_candidates()

_tr_resolution = _TR_vn_util.tr("resolution",
  en="Resolution",
  zh_cn="分辨率",
  zh_hk="分辨率",
)
_tr_description = _TR_vn_util.tr("description",
  en="Description",
  zh_cn="描述",
  zh_hk="描述",
)
_tr_ref = _TR_vn_util.tr("ref",
  en="Ref",
  zh_cn="引用",
  zh_hk="引用",
)
_tr_color = _TR_vn_util.tr("color",
  en=["Color", "Colour"],
  zh_cn="颜色",
  zh_hk="顏色",
)

_tr_invalid_resolution_expr = _TR_vn_util.tr("invalid_resolution_expr",
  en="Not a valid resolution expression: \"{expr}\". Please use expression like, for example, \"1920*1080\" for 1920 pixel in width and 1080 pixels in height.",
  zh_cn="这不是一个有效的分辨率表达式: \"{expr}\"。比如如果宽 1920 像素、高 1080 像素，请使用 \"1920*1080\" 这样的表达式。",
  zh_hk="這不是一個有效的分辨率表達式: \"{expr}\"。比如如果寬 1920 像素、高 1080 像素，請使用 \"1920*1080\" 這樣的表達式。",
)
_tr_invalid_color_expr = _TR_vn_util.tr("invalid_color_expr",
  en="Not a valid color expression: \"{expr}\". We currently support (1) \"#RRGGBB\" (e.g., #FF0000 for red), (2) keyword colors including \"red\", \"green\", \"blue\", \"white\", \"black\".",
  zh_cn="这不是一个有效的颜色表达式： \"{expr}\"。我们目前支持 (1) \"#RRGGBB\" (比如 #FF0000 是红色), (2) 颜色关键词，包括“红色”，“绿色”，“蓝色”，“白色”，“黑色”。",
  zh_hk="這不是一個有效的顏色表達式： \"{expr}\"。我們目前支持 (1) \"#RRGGBB\" (比如 #FF0000 是紅色), (2) 顏色關鍵詞，包括「紅色」，「綠色」，「藍色」，「白色」，「黑色」。",
)
_tr_placeholderexpr_unexpected_kwarg = _TR_vn_util.tr("placeholderexpr_unexpected_keyword_argument",
  en="Unexpected keyword argument \"{keyword}\" in the Placeholder image expression. Expected arguments include: {args}",
  zh_cn="占位图表达式中不存在参数 \"{keyword}\"。需要的参数包括： {args}",
  zh_hk="占位圖表達式中不存在參數 \"{keyword}\"。需要的參數包括： {args}",
)
_tr_placeholderexpr_too_many_positional_arguments = _TR_vn_util.tr("placeholderexpr_too_many_positional_arguments",
  en="Placeholder image expression takes at most one positional argument (for the resolution); {num} provided. The extra argument(s) are ignored.",
  zh_cn="占位图表达式只取最多一个按位参数（分辨率），但是现在提供了 {num} 个。多余的参数将被忽略。",
  zh_hk="占位圖表達式只取最多一個按位參數（分辨率），但是現在提供了 {num} 個。多余的參數將被忽略。",
)
_tr_decl = _TR_vn_util.tr("decl",
  en="Decl",
  zh_cn="声明",
  zh_hk="聲明",
)
_tr_declexpr_unexpected_kwarg = _TR_vn_util.tr("declexpr_unexpected_keyword_argument",
  en="Unexpected keyword argument \"{keyword}\" in the image declaration expression. Expected argument(s) include: {args}",
  zh_cn="图片声明表达式中不存在参数 \"{keyword}\"。需要的参数包括： {args}",
  zh_hk="圖片聲明表達式中不存在參數 \"{keyword}\"。需要的參數包括： {args}",
)
_tr_declexpr_missing_argument = _TR_vn_util.tr("declexpr_missing_argument",
  en="Missing argument(s) {missing} in the image declaration expression. We will use the default placeholder instead.",
  zh_cn="图片声明表达式中没有提供参数： {missing}。我们将使用默认占位图。",
  zh_hk="圖片聲明表達式中沒有提供參數： {missing}。我們將使用默認占位圖。",
)
_tr_declexpr_too_many_positional_arguments = _TR_vn_util.tr("declexpr_too_many_positional_arguments",
  en="Image declaration expression does not allow positional argument (i.e., you need to specify the name of the argument beside the value); {num} provided. The argument(s) are ignored.",
  zh_cn="图片声明表达式不允许按位参数(换句话说，除了参数值外还需要提供参数的名称)，但是现在提供了 {num} 个按位参数。这些参数将被忽略。",
  zh_hk="圖片聲明表達式不允許按位參數(換句話說，除了參數值外還需要提供參數的名稱)，但是現在提供了 {num} 個按位參數。這些參數將被忽略。",
)
_tr_colorfill = _TR_vn_util.tr("colorfill",
  en=["ColorFill", "ColourFill"],
  zh_cn="纯色填充",
  zh_hk="純色填充",
)
_tr_colorfillexpr_unexpected_kwarg = _TR_vn_util.tr("colorfillexpr_unexpected_keyword_argument",
  en="Unexpected keyword argument \"{keyword}\" in the color fill expression. Expected argument(s) include: {args}",
  zh_cn="纯色填充表达式中不存在参数 \"{keyword}\"。需要的参数包括： {args}",
  zh_hk="純色填充表達式中不存在參數 \"{keyword}\"。需要的參數包括： {args}",
)
_tr_colorfillexpr_missing_argument = _TR_vn_util.tr("colorfillexpr_missing_argument",
  en="Missing argument(s) {missing} in the color fill expression. We will use the default placeholder instead.",
  zh_cn="纯色填充表达式中没有提供参数： {missing}。我们将使用默认占位图。",
  zh_hk="純色填充表達式中沒有提供參數： {missing}。我們將使用默認占位圖。",
)
_tr_colorfillexpr_too_many_positional_arguments = _TR_vn_util.tr("colorfillexpr_too_many_positional_arguments",
  en="Ccolor fill expression does not allow positional argument (i.e., you need to specify the name of the argument beside the value); {num} provided. The argument(s) are ignored.",
  zh_cn="纯色填充表达式不允许按位参数(换句话说，除了参数值外还需要提供参数的名称)，但是现在提供了 {num} 个按位参数。这些参数将被忽略。",
  zh_hk="純色填充表達式不允許按位參數(換句話說，除了參數值外還需要提供參數的名稱)，但是現在提供了 {num} 個按位參數。這些參數將被忽略。",
)
def emit_image_expr_from_callexpr(context : Context, call : CallExprOperand, placeholderdest : ImageExprPlaceholderDest, warnings : list[tuple[str, str]], screen_resolution : tuple[int, int] | None = None) -> BaseImageLiteralExpr | None:
  # 调用表达式有以下几种可能：
  # 占位（分辨率=...，描述=...），分辨率和描述均可选，按位参数视为分辨率
  # 声明（分辨率=...，引用=...）, 分辨率和引用均必需，不允许按位参数
  # 纯色填充（分辨率=..., 颜色=...），均必须，不允许按位参数
  # 所有的分辨率都是一个"宽*高"的字符串，比如 "1920*1080"

  def handle_resolution_arg(k : str, v : Value) -> tuple[int, int] | None:
    if isinstance(v, StringLiteral):
      resolution = parse_pixel_resolution_str(v.get_string())
      if resolution is not None:
        return resolution
    msg = _tr_invalid_resolution_expr.format(expr=str(v))
    warnings.append(('vnparse-invalid-resolution-expr', msg))
    return None

  def handle_color_arg(k : str, v : Value) -> Color | None:
    if isinstance(v, StringLiteral):
      try:
        return Color.get(v.get_string())
      except:
        pass
    msg = _tr_invalid_color_expr.format(expr=str(v))
    warnings.append(('vnparse-invalid-color-expr',msg))
    return None

  if _is_image_expr_name_placeholder(call.name):
    resolution = None
    description = None
    for k, v in call.kwargs.items():
      if k in _tr_resolution.get_all_candidates():
        resolution = handle_resolution_arg(k, v)
        continue
      if k in _tr_description.get_all_candidates():
        if isinstance(v, StringLiteral):
          description = v
        else:
          description = StringLiteral.get(str(v), context)
        continue
      # 到这就说明参数读取失败
      expected_args = [_tr_resolution.get(), _tr_description.get()]
      msg = _tr_placeholderexpr_unexpected_kwarg.format(keyword=k, args=str(expected_args))
      warnings.append(('vnparse-placeholderexpr-unexpected-argument', msg))
    consumed_posargs = 0
    if resolution is None and len(call.args) > 0:
      firstarg = call.args[0]
      consumed_posargs += 1
      if isinstance(firstarg, StringLiteral):
        resolution = parse_pixel_resolution_str(firstarg.get_string())
      if resolution is None:
        msg = _tr_invalid_resolution_expr.format(expr=str(firstarg))
        warnings.append(('vnparse-invalid-resolution-expr',msg))
    if len(call.args) > consumed_posargs:
      msg = _tr_placeholderexpr_too_many_positional_arguments.format(num=str(len(call.args)))
      warnings.append(('vnparse-placeholderexpr-too-many-positional-arguments', msg))
    if resolution is None and description is None:
      return emit_default_placeholder(context=context, dest=placeholderdest, screen_resolution=screen_resolution)
    if description is None:
      description = StringLiteral.get('', context)
    if resolution is None:
      resolution = screen_resolution
      if resolution is None:
        resolution = (1920, 1080)
    return PlaceholderImageLiteralExpr.get(context=context, dest=placeholderdest, desc=description, size=IntTupleLiteral.get(resolution, context))

  if call.name in _tr_decl.get_all_candidates():
    resolution = None
    ref = None
    for k, v in call.kwargs.items():
      if k in _tr_resolution.get_all_candidates():
        resolution = handle_resolution_arg(k, v)
        continue
      if k in _tr_ref.get_all_candidates():
        if isinstance(v, StringLiteral):
          ref = v
        else:
          ref = StringLiteral.get(str(v), context)
        continue
      expected_args = [_tr_resolution.get(), _tr_ref.get()]
      msg = _tr_declexpr_unexpected_kwarg.format(keyword=k, args=str(expected_args))
      warnings.append(('vnparse-declexpr-unexpected-argument', msg))

    # 缺了任一参数就用默认的占位表达式
    if ref is None or resolution is None:
      missing_args=[]
      if ref is None:
        missing_args.append(_tr_ref.get())
      if resolution is None:
        missing_args.append(_tr_resolution.get())
      msg = _tr_declexpr_missing_argument.format(missing=str(missing_args))
      warnings.append(('vnparse-declexpr-missing-argument',msg))
      return emit_default_placeholder(context=context, dest=placeholderdest, screen_resolution=screen_resolution)

    if len(call.args) > 0:
      msg = _tr_declexpr_too_many_positional_arguments.format(num=str(len(call.args)))
      warnings.append(('vnparse-declexpr-too-many-arguments', msg))
    return DeclaredImageLiteralExpr.get(context=context, decl=ref, size=IntTupleLiteral.get(resolution, context))

  if call.name in _tr_colorfill.get_all_candidates():
    resolution = None
    color = None
    for k, v in call.kwargs.items():
      if k in _tr_resolution.get_all_candidates():
        resolution = handle_resolution_arg(k, v)
        continue
      if k in _tr_color.get_all_candidates():
        color = handle_color_arg(k, v)
        continue
      expected_args = [_tr_resolution.get(), _tr_color.get()]
      msg = _tr_colorfillexpr_unexpected_kwarg.format(keyword=k, args=str(expected_args))
      warnings.append(('vnparse-colorfillexpr-unexpected-argument', msg))

    if resolution is None or color is None:
      missing_args = []
      if color is None:
        missing_args.append(_tr_color.get())
      if resolution is None:
        missing_args.append(_tr_resolution.get())
      msg = _tr_colorfillexpr_missing_argument.format(missing=str(missing_args))
      warnings.append(('vnparse-colorfillexpr-missing-argument', msg))
      return emit_default_placeholder(context=context, dest=placeholderdest, screen_resolution=screen_resolution)

    if len(call.args) > 0:
      msg = _tr_colorfillexpr_too_many_positional_arguments.format(num=str(len(call.args)))
      warnings.append(('vnparse-declexpr-too-many-arguments', msg))

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
  if result := emit_image_expr_from_path(context=context, pathexpr=s, basepath=basepath, warnings=warnings):
    return result
  return None

_tr_audio_zero_duration = _TR_vn_util.tr("audio_zero_duration",
  en="Audio has zero duration and cannot be used: {file} (Probably an error in the file or in the program)",
  zh_cn="音频时长为零，无法使用： {file} (应该是文件或程序出错)",
  zh_hk="音頻時長為零，無法使用： {file} (應該是文件或程序出錯)",
)
_tr_audio_cannot_open = _TR_vn_util.tr("audio_cannot_open",
  en="Error when opening potential audio file {file}: {err}",
  zh_cn="尝试打开可能的音频文件 {file} 时出错： {err}",
  zh_hk="嘗試打開可能的音頻文件 {file} 時出錯： {err}",
)

def emit_audio_from_path(context : Context, pathexpr : str, basepath : str, warnings : list[tuple[str, str]]) -> AudioAssetData | None:
  def _try_open_audio(p : str) -> str | None:
    nonlocal warnings
    try:
      f = pydub.AudioSegment.from_file(p)
      if len(f) > 0:
        # len(f) 是时长，单位是毫秒
        return p
      else:
        warnings.append(('vnutil-audio-zero-duration', _tr_audio_zero_duration.format(file=p)))
    except Exception as e:
      warnings.append(('vnutil-audio-cannot-open', _tr_audio_cannot_open.format(file=p, err=str(e))))
      return None
    return None
  if path := context.get_file_auditor().search(querypath=pathexpr, basepath=basepath, filecheckCB=_try_open_audio):
    return context.get_or_create_audio_asset_data_external(path, None)
  return None

_tr_transition_none = _TR_vn_util.tr("none",
  en="None",
  zh_cn="无",
  zh_hk="無",
)
_tr_transition_backend_transition = _TR_vn_util.tr("backend_transition",
  en="BackendTransition",
  zh_cn="后端转场",
  zh_hk="後端轉場",
)
_tr_transition_invalid_valuetype = _TR_vn_util.tr("transition_invalid_valuetype",
  en="Invalid value type: {vty} (should be a string)",
  zh_cn="错误的值类型： {vty} (应该是个字符串)",
  zh_hk="錯誤的值類型： {vty} (應該是個字符串)"
)
_tr_transition_backend_extra_positional_args = _TR_vn_util.tr("transition_backend_extra_positional_args",
  en="Backend transition expression takes at most one positional argument (the expression); extra positional arguments {extra} ignored.",
  zh_cn="后端转场表达式取最多一个按位参数（表达式内容）；多余的按位参数将被忽略： {extra}",
  zh_hk="後端轉場表達式取最多一個按位參數（表達式內容）；多余的按位參數將被忽略： {extra}",
)
_tr_expr = _TR_vn_util.tr("expr",
  en="expr",
  zh_cn="表达式",
  zh_hk="表達式",
)
_tr_backend = _TR_vn_util.tr("backend",
  en="backend",
  zh_cn="后端",
  zh_hk="後端",
)
_tr_backend_transition_missing_arguments = _TR_vn_util.tr("backend_transition_missing_arguments",
  en="Backend transition expression expects both <expr, backend> argument; using default transition",
  zh_cn="后端转场表达式需要<表达式，后端>两个参数，参数不足；我们将使用默认转场效果。",
  zh_hk="後端轉場表達式需要<表達式，後端>兩個參數，參數不足；我們將使用默認轉場效果。",
)

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
  if transition_name in _tr_transition_none.get_all_candidates():
    return VNDefaultTransitionType.DT_NO_TRANSITION.get_enum_literal(context)

  if transition_name in _tr_transition_backend_transition.get_all_candidates():
    backend_name = None
    expr = None
    def try_set_backend(s : Literal):
      nonlocal backend_name
      if isinstance(s, StringLiteral):
        backend_name = s
      elif isinstance(s, TextFragmentLiteral):
        backend_name = s.content
      else:
        warnings.append(("vncodegen-transition-invalid-argument", _tr_transition_invalid_valuetype.format(vty=type(s).__name__)))

    def try_set_expr(s : Literal):
      nonlocal expr
      if isinstance(s, StringLiteral):
        expr = s
      elif isinstance(s, TextFragmentLiteral):
        expr = s.content
      else:
        warnings.append(("vncodegen-transition-invalid-argument", _tr_transition_invalid_valuetype.format(vty=type(s).__name__)))

    if len(transition_args) > 0:
      if len(transition_args) == 1:
        try_set_expr(transition_args[0])
      else:
        msg = _tr_transition_backend_extra_positional_args.format(extra=','.join([str(v) for v in transition_args[1:]]))
        warnings.append(("vncodegen-transition-unused-args", msg))
    for k, v in transition_kwargs.items():
      if k in _tr_expr.get_all_candidates():
        try_set_expr(v)
      elif k in _tr_backend.get_all_candidates():
        try_set_backend(v)
    if backend_name is None or expr is None:
      # 如果任意一项没填，视为默认转场
      warnings.append(("vncodegen-transition-incomplete-args", _tr_backend_transition_missing_arguments.get()))
      return None
    return (backend_name, expr)
  return None
