# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 该文件存放一些帮助代码生成的函数
# 有些逻辑在解析与生成时都会用到，比如查找图片表达式等，我们把这些实现放在这

import collections
import decimal
import re
import traceback
import typing
import unicodedata

from ...irbase import *
from ...commontypes import Color
from ...imageexpr import *
from ..commandsemantics import *
from ..commandsemantics import _strip_wrapping_quotes_for_numeric  # import * 不导入以下划线开头的名称
from ..commandsyntaxparser import *
from .vnast import *
from ...util.message import MessageHandler
from ...exceptions import *
from ...language import TranslationDomain
from ...vnmodel import (
  VNDefaultTransitionType,
  VNDissolveSceneTransitionLit,
  VNFadeInSceneTransitionLit,
  VNFadeOutSceneTransitionLit,
  VNFadeToColorSceneTransitionLit,
  VNPushSceneTransitionLit,
  VNSlideInSceneTransitionLit,
  VNSlideOutSceneTransitionLit,
  VNZoomSceneTransitionLit,
)

_TR_vn_util = TranslationDomain("vn_util")

tr_vnutil_vtype_sayname = _TR_vn_util.tr("vtype_sayname",
  en="<SayName>",
  zh_cn="<发言名>",
  zh_hk="<發言名>",
)
tr_vnutil_vtype_imageexprtree = _TR_vn_util.tr("vtype_image_expr_tree",
  en="<ImageExprTree>",
  zh_cn="<图片表达式树>",
  zh_hk="<圖片表達式樹>",
)

class VNASTImageExprSource(enum.Enum):
  # 当我们要读取树结构的图片表达式时，用这个来表示图片表达式是用来干什么的
  # 这样当读取占位表达式时可以生成对应的结构
  SRC_CHARACTER_SPRITE    = enum.auto() # 人物立绘
  SRC_CHARACTER_SIDEIMAGE = enum.auto() # 人物头像
  SRC_SCENE_BACKGROUND    = enum.auto() # 场景背景

def emit_default_placeholder(context : Context, dest : ImageExprPlaceholderDest, description : StringLiteral | None = None) -> PlaceholderImageLiteralExpr:
  if description is None:
    description = StringLiteral.get('', context)
  placeholder = PlaceholderImageLiteralExpr.get(context=context, dest=dest, desc=description, size=IntTuple2DLiteral.get((0,0), context))
  return placeholder

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

def _read_image_helper(context : Context, pathexpr : str, basepath : str, warnings : list[tuple[str, str]]) -> ImageAssetData | None:
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
    return asset
  return None

def emit_image_expr_from_path(context : Context, pathexpr : str, basepath : str, warnings : list[tuple[str, str]]) -> BaseImageLiteralExpr | None:
  # 如果提供了图片路径，则当场读取图片内容，创建 ImageAssetLiteralExpr
  if asset := _read_image_helper(context, pathexpr, basepath, warnings):
    data = asset.load()
    assert data is not None
    bbox = ImageAssetLiteralExpr.prepare_bbox(context=context, imagedata=data)
    return ImageAssetLiteralExpr.get(context, image=asset, size=IntTuple2DLiteral.get(data.size, context), bbox=bbox)
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
_tr_decl = _TR_vn_util.tr("decl",
  en="Decl",
  zh_cn="声明",
  zh_hk="聲明",
)
_tr_colorfill = _TR_vn_util.tr("colorfill",
  en=["ColorFill", "ColourFill"],
  zh_cn="纯色填充",
  zh_hk="純色填充",
)
_tr_imagepreset = _TR_vn_util.tr("imagepreset",
  en="Preset",
  zh_cn="预设",
  zh_hk="預設",
)
_tr_imagepreset_background = _TR_vn_util.tr("imagepreset_background",
  en="BackgroundPreset",
  zh_cn="预设背景",
  zh_hk="預設背景",
)
_tr_template = _TR_vn_util.tr("template",
  en="Template",
  zh_cn="模板",
  zh_hk="模板",
)
_tr_composite_name = _TR_vn_util.tr("composite_name",
  en="Composite",
  zh_cn="差分组合",
  zh_hk="差分組合",
)
_tr_imagepreset_character = _TR_vn_util.tr("imagepreset_character",
  en="CharacterPreset",
  zh_cn="预设角色",
  zh_hk="預設角色",
)
_tr_image_template_not_found = _TR_vn_util.tr("image_template_not_found",
  en="Image template not found: {template}",
  zh_cn="未找到图片模板 {template}",
  zh_hk="未找到圖片模板 {template}",
)
_tr_composite_not_found = _TR_vn_util.tr("composite_not_found",
  en="Composite not found: {composite}",
  zh_cn="未找到差分组合 {composite}",
  zh_hk="未找到差分組合 {composite}",
)
_tr_image_template_parameter_not_supported = _TR_vn_util.tr("image_template_parameter_not_supported",
  en="Image \"{template}\" does not support parameter \"{param}\"",
  zh_cn="图片 \"{template}\" 不支持参数 \"{param}\"",
  zh_hk="圖片 \"{template}\" 不支持參數 \"{param}\"",
)
def emit_image_expr_from_callexpr(context : Context, call : CallExprOperand, basepath : str,
                                  placeholderdest : ImageExprPlaceholderDest, placeholderdesc: str,
                                  warnings : list[tuple[str, str]],
                                  children_out : list[tuple[list[str], BaseImageLiteralExpr, list[list[str]]]] | None = None,
                                  curstate_is_child : list[str] | None = None
                                  ) -> BaseImageLiteralExpr | None:
  # 调用表达式有以下几种可能：(所有的分辨率输入均为可选项，解析完成后我们会尝试推导分辨率)
  # 占位（描述=...，分辨率=...），描述可选，按位参数视为描述
  # 声明（引用=...，分辨率=...）, 引用必需，按位参数视为引用
  # 纯色填充（颜色=..., 分辨率=...），均必须，按位参数视为颜色
  # 预设背景（模板=...，差分组合=..., 屏幕=..., 指示色=..., 分辨率=...），只有模板必需，按位参数视为模板
  # 预设角色（模板=...，差分组合=..., 衣服颜色=..., 发色=..., 装饰色=..., 分辨率=...），只有模板必需，按位参数视为模板
  # 所有的分辨率（如果有的话）都是一个"宽*高"的字符串，比如 "1920*1080"

  def handle_placeholder_expr(desc : str = '', *, resolution : FrontendParserBase.Resolution | None = None) -> PlaceholderImageLiteralExpr:
    resolution_v = resolution.resolution if resolution is not None else (0,0)
    if len(desc) == 0:
      desc = placeholderdesc
    return PlaceholderImageLiteralExpr.get(context=context, dest=placeholderdest, desc=StringLiteral.get(desc, context), size=IntTuple2DLiteral.get(resolution_v, context))

  def handle_decl_expr(ref : str, *, resolution : FrontendParserBase.Resolution | None = None) -> DeclaredImageLiteralExpr:
    resolution_v = resolution.resolution if resolution is not None else (0,0)
    return DeclaredImageLiteralExpr.get(context=context, decl=StringLiteral.get(ref, context), size=IntTuple2DLiteral.get(resolution_v, context))

  def handle_colorfill_expr(color : Color, *, resolution : FrontendParserBase.Resolution | None = None) -> ColorImageLiteralExpr:
    resolution_v = resolution.resolution if resolution is not None else (0,0)
    return ColorImageLiteralExpr.get(context=context, color=ColorLiteral.get(color, context), size=IntTuple2DLiteral.get(resolution_v, context))

  # 关于图片模板的辅助函数
  def _helper_get_descriptor(template : str, type : ImagePackDescriptor.ImagePackType, default_id : str) -> ImagePackDescriptor:
    descriptor = ImagePackDescriptor.lookup(template, type)
    if descriptor is None:
      warnings.append(("vnutil-image-template-not-found", _tr_image_template_not_found.format(template=template)))
      descriptor = ImagePackDescriptor.lookup(default_id, type)
    if descriptor is None:
      raise PPInternalError("No default template found")
    return descriptor

  def _helper_prepare_fork_arguments(descriptor : ImagePackDescriptor, args : dict[ImagePackDescriptor.MaskType, typing.Any]) -> list[ImageAssetData | ColorLiteral | StringLiteral] | None:
    if args is None or len(args) == 0:
      return None
    result = []
    is_having_arg = False
    for mask in descriptor.get_masks():
      converted_arg = None
      if mask in args:
        value = args[mask]
        del args[mask]
        if value is not None:
          match mask.get_param_type():
            case ImagePackDescriptor.MaskParamType.IMAGE:
              if isinstance(value, ImageAssetData):
                converted_arg = value
              elif isinstance(value, Color):
                converted_arg = ColorLiteral.get(value, context)
              elif isinstance(value, str):
                if asset := _read_image_helper(context, value, "", warnings):
                  converted_arg = asset
                else:
                  converted_arg = StringLiteral.get(value, context)
              else:
                raise PPInternalError("Unknown type of mask param")
            case ImagePackDescriptor.MaskParamType.COLOR:
              if isinstance(value, Color):
                converted_arg = ColorLiteral.get(value, context)
              else:
                raise PPInternalError("Unknown type of mask param")
      result.append(converted_arg)
      if converted_arg is not None:
        is_having_arg = True
    if len(args) > 0:
      for mask in args.keys():
        template_str = str(descriptor.get_name())
        parameter_str = str(mask.trname)
        warnings.append(("vnutil-image-template-parameter-not-supported", _tr_image_template_parameter_not_supported.format(template=template_str, param=parameter_str)))
    if is_having_arg:
      return result
    return None

  def _helper_finalize_imagepreset_expr(descriptor : ImagePackDescriptor, composite : str, args : list[ImageAssetData | ColorLiteral | StringLiteral] | None, size : tuple[int,int] | None) -> ImagePackElementLiteralExpr:
    converted_size = None
    if size is not None:
      converted_size = IntTuple2DLiteral.get(size, context)
    if len(composite) == 0 and children_out is not None:
      composite = descriptor.get_default_composite()
      # 我们需要把该图片包中的所有差分组合都加到 children_out 中
      for c in descriptor.get_all_composites():
        imgexpr = ImagePackElementLiteralExpr.get(context=context, pack=descriptor.get_pack_id(), element=c, size=converted_size, mask_operands=args)
        primary_name = c
        all_names = [c]
        if tr := descriptor.try_get_composite_name(c):
          primary_name = tr.get()
          all_names.extend(tr.get_all_candidates())
        all_names.remove(primary_name)
        children_out.append(([primary_name], imgexpr, [[name] for name in all_names]))
    if composite_code := descriptor.get_composite_code_from_name(composite):
      return ImagePackElementLiteralExpr.get(context=context, pack=descriptor.get_pack_id(), element=composite_code, size=converted_size, mask_operands=args)
    if composite == descriptor.get_default_composite():
      raise PPInternalError("Default composite not found")
    warnings.append(("vnutil-composite-not-found", _tr_composite_not_found.format(composite=composite)))
    return ImagePackElementLiteralExpr.get(context=context, pack=descriptor.get_pack_id(), element=descriptor.get_default_composite(), size=converted_size, mask_operands=args)

  def handle_imagepreset_background_expr(template : str, *, composite : str = '', screen : ImageAssetData | str | None = None, indicator : Color | None = None, resolution : FrontendParserBase.Resolution | None = None) -> ImagePackElementLiteralExpr:
    descriptor = _helper_get_descriptor(template, ImagePackDescriptor.ImagePackType.BACKGROUND, "imagepack_background_A0T0")
    rawargs = {}
    if screen is not None:
      rawargs[ImagePackDescriptor.MaskType.BACKGROUND_SCREEN] = screen
    if indicator is not None:
      rawargs[ImagePackDescriptor.MaskType.BACKGROUND_COLOR_INDICATOR] = indicator
    converted_args = _helper_prepare_fork_arguments(descriptor, rawargs)
    # ImagePackElementLiteralExpr 支持从 ImagePackDescriptor 直接读取图片大小等信息
    resolution_v = resolution.resolution if resolution is not None else None
    return _helper_finalize_imagepreset_expr(descriptor, composite, converted_args, resolution_v)

  def handle_imagepreset_character_expr(template : str, *, composite : str = '', cloth : Color | None = None, hair : Color | None = None, decorate : Color | None = None, resolution : FrontendParserBase.Resolution | None = None) -> ImagePackElementLiteralExpr:
    descriptor = _helper_get_descriptor(template, ImagePackDescriptor.ImagePackType.CHARACTER, "imagepack_character_A0DT1")
    rawargs = {}
    if cloth is not None:
      rawargs[ImagePackDescriptor.MaskType.CHARACTER_COLOR_CLOTH] = cloth
    if hair is not None:
      rawargs[ImagePackDescriptor.MaskType.CHARACTER_COLOR_HAIR] = hair
    if decorate is not None:
      rawargs[ImagePackDescriptor.MaskType.CHARACTER_COLOR_DECORATE] = decorate
    converted_args = _helper_prepare_fork_arguments(descriptor, rawargs)
    resolution_v = resolution.resolution if resolution is not None else None
    return _helper_finalize_imagepreset_expr(descriptor, composite, converted_args, resolution_v)

  candidates_from_preset = []
  if placeholderdest == ImageExprPlaceholderDest.DEST_SCENE_BACKGROUND:
    candidates_from_preset.append(([_tr_imagepreset, _tr_imagepreset_background],
      handle_imagepreset_background_expr, {
        'template': _tr_template,
        'composite': _tr_composite_name,
        'screen': ImagePackDescriptor.MaskType.BACKGROUND_SCREEN.trname,
        'indicator': ImagePackDescriptor.MaskType.BACKGROUND_COLOR_INDICATOR.trname,
        'resolution': _tr_resolution
      }))
  elif placeholderdest == ImageExprPlaceholderDest.DEST_CHARACTER_SPRITE:
    candidates_from_preset.append(([_tr_imagepreset, _tr_imagepreset_character],
      handle_imagepreset_character_expr, {
        'template': _tr_template,
        'composite': _tr_composite_name,
        'cloth': ImagePackDescriptor.MaskType.CHARACTER_COLOR_CLOTH.trname,
        'hair': ImagePackDescriptor.MaskType.CHARACTER_COLOR_HAIR.trname,
        'decorate': ImagePackDescriptor.MaskType.CHARACTER_COLOR_DECORATE.trname,
        'resolution': _tr_resolution
      }))

  imageexpr = FrontendParserBase.resolve_call(call, [
    (_tr_placeholder, handle_placeholder_expr, {'desc': _tr_description, 'resolution': _tr_resolution}),
    (_tr_decl, handle_decl_expr, {'ref': _tr_ref, 'resolution': _tr_resolution}),
    (_tr_colorfill, handle_colorfill_expr, {'color': _tr_color, 'resolution': _tr_resolution}),
    *candidates_from_preset,
  ], warnings)
  if imageexpr is not None:
    return imageexpr
  return None

def emit_image_expr_from_str(context : Context, s : str, basepath : str,  placeholderdest : ImageExprPlaceholderDest, placeholderdesc : str, warnings : list[tuple[str, str]], children_out : list[tuple[list[str], BaseImageLiteralExpr, list[list[str]]]] | None = None) -> BaseImageLiteralExpr | None:
  # 不确定字符串是什么形式
  # 先尝试转化成调用表达式，不行的话试试当成路径
  # 都不行的话视为失败
  # 由于如果字符串不带()的话，命令解析代码不会将字符串内容视为调用，
  # 所以我们需要对这种情况特判
  # （现在仅有占位可以不需要额外参数，所以只需检查占位的情况）
  if _is_image_expr_name_placeholder(s):
    return emit_default_placeholder(context=context, dest=placeholderdest, description=StringLiteral.get(placeholderdesc, context))
  if cmd := try_parse_value_expr(s, context.null_location):
    if isinstance(cmd, GeneralCommandOp):
      callexpr = FrontendParserBase.parse_commandop_as_callexpr(cmd)
      return emit_image_expr_from_callexpr(context=context, call=callexpr, basepath=basepath, placeholderdest=placeholderdest, placeholderdesc=placeholderdesc, warnings=warnings, children_out=children_out)
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

# 通用场景过渡（与后端无关的固定符号），对应 effect_doc 第一节
_tr_transition_fade_in = _TR_vn_util.tr("fade_in",
  en="FadeIn",
  zh_cn=["淡入", "淡入时长"],
  zh_hk=["淡入", "淡入時長"],
)
_tr_transition_fade_out = _TR_vn_util.tr("fade_out",
  en="FadeOut",
  zh_cn=["淡出", "淡出时长"],
  zh_hk=["淡出", "淡出時長"],
)
_tr_transition_dissolve = _TR_vn_util.tr("dissolve",
  en="Dissolve",
  zh_cn="溶解",
  zh_hk="溶解",
)
_tr_transition_slide_in = _TR_vn_util.tr("slide_in",
  en="SlideIn",
  zh_cn="滑入",
  zh_hk="滑入",
)
_tr_transition_slide_out = _TR_vn_util.tr("slide_out",
  en="SlideOut",
  zh_cn="滑出",
  zh_hk="滑出",
)
_tr_transition_push = _TR_vn_util.tr("push",
  en="Push",
  zh_cn="推移",
  zh_hk="推移",
)
_tr_transition_fade_to_color = _TR_vn_util.tr("fade_to_color",
  en="FadeToColor",
  zh_cn="黑白酒",
  zh_hk="黑白酒",
)
_tr_transition_zoom = _TR_vn_util.tr("zoom",
  en="Zoom",
  zh_cn="缩放",
  zh_hk="縮放",
)
_tr_effect_shake = _TR_vn_util.tr("instant_shake", en="Shake", zh_cn="震动", zh_hk="震動")
_tr_effect_flash = _TR_vn_util.tr("instant_flash", en="Flash", zh_cn="闪烁", zh_hk="閃爍")
_tr_effect_amplitude = _TR_vn_util.tr("instant_amplitude", en="amplitude", zh_cn="幅度", zh_hk="幅度")
_tr_effect_decay = _TR_vn_util.tr("instant_decay", en="decay", zh_cn="衰减", zh_hk="衰減")
_tr_flash_fade_in = _TR_vn_util.tr("flash_fade_in", en="fade_in", zh_cn="切入时长", zh_hk="切入時長")
_tr_flash_fade_out = _TR_vn_util.tr("flash_fade_out", en="fade_out", zh_cn="恢复时长", zh_hk="恢復時長")
_tr_duration = _TR_vn_util.tr("duration",
  en="duration",
  zh_cn="时长",
  zh_hk="時長",
)
_tr_direction = _TR_vn_util.tr("direction",
  en="direction",
  zh_cn="方向",
  zh_hk="方向",
)
_tr_hold = _TR_vn_util.tr("hold",
  en="hold",
  zh_cn=["停留时长", "停留"],
  zh_hk=["停留時長", "停留"],
)
_tr_start_point = _TR_vn_util.tr("start_point",
  en="start_point",
  zh_cn="起始点",
  zh_hk="起始點",
)
_tr_end_point = _TR_vn_util.tr("end_point",
  en="end_point",
  zh_cn="结束点",
  zh_hk="結束點",
)
def _transition_decimal_to_value(context: Context, v: decimal.Decimal | int) -> Value:
  if isinstance(v, decimal.Decimal):
    return FloatLiteral.get(v, context)
  return FloatLiteral.get(decimal.Decimal(int(v)), context)


def coerce_instant_effect_float_operand(v : Value) -> float | None:
  """VN 代码生成阶段：把时长/幅度/衰减等字面值规范为 float（与命令解析 try_convert 一致）。失败返回 None，由调用方 emit_error。"""
  if isinstance(v, FloatLiteral):
    return float(v.value)
  if isinstance(v, IntLiteral):
    return float(int(v.value))
  try:
    conv = FrontendParserBase.try_convert_parameter(decimal.Decimal, v)
  except NotImplementedError:
    return None
  if conv is not None:
    return float(conv)
  return None


# 预设效果集名称（与后端无关的固定键，用于 AST effect_presets 查找）
EFFECT_PRESET_SLIDE_DIRECTION = "SlideDirection"
EFFECT_PRESET_ZOOM_DIRECTION = "ZoomDirection"
EFFECT_PRESET_ZOOM_POINT = "ZoomPoint"
EFFECT_PRESET_SHAKE_DIRECTION = "ShakeDirection"

# ---------------------------------------------------------------------------
# 场景转场 LiteralExpr（如 VNZoomSceneTransitionLit.direction / .point）在 parse 时已规范为英文键：
# 须在构造 IR 时即为规范英文蛇形键；codegen 只做「规范键 → 引擎参数」，不再做自然语言匹配。
# ---------------------------------------------------------------------------

CANONICAL_SLIDE_DIRECTIONS : typing.Final[frozenset[str]] = frozenset({"left", "right", "up", "down"})
CANONICAL_ZOOM_DIRECTIONS : typing.Final[frozenset[str]] = frozenset({"in", "out"})
CANONICAL_ZOOM_POINTS : typing.Final[frozenset[str]] = frozenset({
  "top_left", "top_center", "top_right",
  "center_left", "center", "center_right",
  "bottom_left", "bottom_center", "bottom_right",
})
CANONICAL_SHAKE_DIRECTIONS : typing.Final[frozenset[str]] = frozenset({"horizontal", "vertical"})

# 内置各预设效果集可能出现的 canonical_value（规范英文蛇形键）全集；与 ensure_builtin_effect_presets 注入的条目一致。
# 用户尚可在 EffectDecl 中为同名集追加条目，故运行时可能出现此处未列出的 canonical_value。
BUILTIN_EFFECT_PRESET_CANONICAL_BY_SET : typing.Final[dict[str, frozenset[str]]] = {
  EFFECT_PRESET_SLIDE_DIRECTION: CANONICAL_SLIDE_DIRECTIONS,
  EFFECT_PRESET_ZOOM_DIRECTION: CANONICAL_ZOOM_DIRECTIONS,
  EFFECT_PRESET_ZOOM_POINT: CANONICAL_ZOOM_POINTS,
  EFFECT_PRESET_SHAKE_DIRECTION: CANONICAL_SHAKE_DIRECTIONS,
}

# 未命中 EffectDecl 预设时，允许的英文别名 → 规范九点点键
_TRANSITION_ZOOM_POINT_ALIASES : typing.Final[dict[str, str]] = {
  "top": "top_center",
  "bottom": "bottom_center",
  "left": "center_left",
  "right": "center_right",
  "middle": "center",
  "centre": "center",
}


def canonicalize_transition_zoom_point(raw : str) -> str:
  if raw is None or not str(raw).strip():
    raise PPInvalidOperationError(
      "转场缩放点不能为空；请使用规范键（如 center、top_center）或在 EffectDecl 的 ZoomPoint 集中声明别名。",
    )
  key = str(raw).strip().replace(" ", "_").replace("-", "_").lower()
  if key in CANONICAL_ZOOM_POINTS:
    return key
  if key in _TRANSITION_ZOOM_POINT_ALIASES:
    return _TRANSITION_ZOOM_POINT_ALIASES[key]
  allowed = ", ".join(sorted(CANONICAL_ZOOM_POINTS))
  raise PPInvalidOperationError(
    f"不支持的转场缩放点 {raw!r}。请使用：{allowed}；或英文别名 top/bottom/left/right/middle；或在 EffectDecl 中为 ZoomPoint 声明别名。",
  )


def canonicalize_transition_slide_direction(raw : str) -> str:
  if raw is None or not str(raw).strip():
    raise PPInvalidOperationError(
      "滑移/推移方向不能为空；请使用 left、right、up、down（或在 EffectDecl 的 SlideDirection 集中声明别名）。",
    )
  s = str(raw).strip().lower()
  if s == "top":
    s = "up"
  if s == "bottom":
    s = "down"
  if s in CANONICAL_SLIDE_DIRECTIONS:
    return s
  raise PPInvalidOperationError(
    f"不支持的滑移/推移方向 {raw!r}。请使用：left、right、up、down。",
  )


def canonicalize_transition_zoom_direction(raw : str) -> str:
  if raw is None or not str(raw).strip():
    raise PPInvalidOperationError(
      "缩放转场方向不能为空；请使用 in 或 out（或在 EffectDecl 的 ZoomDirection 集中声明别名）。",
    )
  s = str(raw).strip().lower()
  if s in ("入",):
    s = "in"
  if s in ("出",):
    s = "out"
  if s in CANONICAL_ZOOM_DIRECTIONS:
    return s
  raise PPInvalidOperationError(
    f"不支持的缩放转场方向 {raw!r}。请使用：in、out。",
  )


def resolve_effect_preset_value(ast : VNAST, preset_set_name : str, user_input : str) -> StringLiteral | None:
  """
  根据 AST 中的 EffectDecl 预设效果集解析用户输入为规范键（StringLiteral）。
  若 ast 为 None 或未找到匹配则返回 None。
  """
  if ast is None:
    return None
  preset_set = ast.effect_presets.get(preset_set_name)
  if preset_set is None:
    return None
  raw = user_input.strip()
  raw_lower = raw.lower()
  for entry in preset_set.entries:
    if not isinstance(entry, VNASTEffectPresetEntrySymbol):
      continue
    canonical_str = entry.canonical_value.get().get_string()
    if raw == canonical_str or raw_lower == canonical_str.lower():
      return entry.canonical_value.get()
    for use in entry.aliases.operanduses():
      a = use.value.get_string()
      if a and (raw == a or raw_lower == a.lower()):
        return entry.canonical_value.get()
  return None


def ensure_builtin_effect_presets(ast : VNAST) -> None:
  """向 AST 注入内置预设效果集（SlideDirection、ZoomDirection），若尚不存在则创建。"""
  ctx = ast.context
  if ast.effect_presets.get(EFFECT_PRESET_SLIDE_DIRECTION) is None:
    slide = VNASTEffectPresetSetSymbol.create(ctx, EFFECT_PRESET_SLIDE_DIRECTION)
    for canonical, aliases in [
      ("left", ["左", "Left"]),
      ("right", ["右", "Right"]),
      ("up", ["上", "Up"]),
      ("down", ["下", "Down"]),
    ]:
      slide.entries.add(VNASTEffectPresetEntrySymbol.create(ctx, canonical, aliases))
    ast.effect_presets.add(slide)
  if ast.effect_presets.get(EFFECT_PRESET_ZOOM_DIRECTION) is None:
    zoom = VNASTEffectPresetSetSymbol.create(ctx, EFFECT_PRESET_ZOOM_DIRECTION)
    for canonical, aliases in [
      ("in", ["入", "In"]),
      ("out", ["出", "Out"]),
    ]:
      zoom.entries.add(VNASTEffectPresetEntrySymbol.create(ctx, canonical, aliases))
    ast.effect_presets.add(zoom)
  if ast.effect_presets.get(EFFECT_PRESET_ZOOM_POINT) is None:
    zoom_pt = VNASTEffectPresetSetSymbol.create(ctx, EFFECT_PRESET_ZOOM_POINT)
    for canonical, aliases in [
      ("top_left", ["左上"]),
      ("top_center", ["中上", "上中", "上"]),
      ("top_right", ["右上"]),
      ("center_left", ["左中", "左"]),
      ("center", ["中心", "中"]),
      ("center_right", ["右中", "右"]),
      ("bottom_left", ["左下"]),
      ("bottom_center", ["中下", "下中", "下"]),
      ("bottom_right", ["右下"]),
    ]:
      zoom_pt.entries.add(VNASTEffectPresetEntrySymbol.create(ctx, canonical, aliases))
    ast.effect_presets.add(zoom_pt)
  if ast.effect_presets.get(EFFECT_PRESET_SHAKE_DIRECTION) is None:
    sd = VNASTEffectPresetSetSymbol.create(ctx, EFFECT_PRESET_SHAKE_DIRECTION)
    for canonical, aliases in [
      ("horizontal", ["水平", "H", "X"]),
      ("vertical", ["垂直", "V", "Y"]),
    ]:
      sd.entries.add(VNASTEffectPresetEntrySymbol.create(ctx, canonical, aliases))
    ast.effect_presets.add(sd)


def parse_transition(context : Context, transition_name : str, transition_args : list[Literal], transition_kwargs : dict[str, Literal], warnings : list[tuple[str, str]], ast : VNAST | None = None) -> Value | tuple[StringLiteral, StringLiteral] | None:
  # - 未写转场名（空字符串）：返回 None，表示「本条 Transition 结点未指定效果」；外层 codegen 对立绘等仍会套用默认淡入/淡出。
  # - 显式「无」等：返回 DT_NO_TRANSITION，表示用户要求立刻切换、不要渐变。
  # - 后端专有：tuple[backend, expr]；通用场景转场：对应 LiteralExpr / 等价值。
  # ast 用于从 EffectDecl 预设效果集解析 direction 等多语言参数；为 None 时退化为仅接受英文规范键。

  transition_name = (transition_name or "").strip()
  if len(transition_name) == 0:
    return None

  # 1. 无：立即发生，无转场（与「未写转场名」不同，后者为 None）
  if transition_name in _tr_transition_none.get_all_candidates():
    return VNDefaultTransitionType.DT_NO_TRANSITION.get_enum_literal(context)

  # 黑白酒：表格常写「时长」，与溶解/淡入等单段转场混淆；须在 resolve_call 前给出明确错误（否则易落到 Ren'Py 运行期）
  if transition_name in _tr_transition_fade_to_color.get_all_candidates():
    for _kw in transition_kwargs:
      if unicodedata.normalize("NFKC", _kw).strip() == "时长":
        raise PPInvalidOperationError(
          "转场「黑白酒」不能使用参数「时长」。请使用「淡出」「淡出时长」「停留时长」「淡入」「淡入时长」与「颜色」。",
        )

  def handle_backend_specific_transition(expr : str, *, backend : str) -> tuple[StringLiteral, StringLiteral]:
    return (StringLiteral.get(backend, context), StringLiteral.get(expr, context))

  def _resolve_direction(preset_name: str, direction_str: str) -> StringLiteral:
    resolved = resolve_effect_preset_value(ast, preset_name, direction_str) if ast else None
    if resolved is not None:
      return resolved
    if preset_name == EFFECT_PRESET_SLIDE_DIRECTION:
      canon = canonicalize_transition_slide_direction(direction_str)
    elif preset_name == EFFECT_PRESET_ZOOM_DIRECTION:
      canon = canonicalize_transition_zoom_direction(direction_str)
    else:
      raise PPInternalError("未知的方向预设集: " + preset_name)
    return StringLiteral.get(canon, context)

  # 2. 通用场景过渡（与后端无关的固定符号）
  def handle_fade_in(duration: decimal.Decimal = decimal.Decimal("0.5")):
    return VNFadeInSceneTransitionLit.get(context, _transition_decimal_to_value(context, duration))

  def handle_fade_out(duration: decimal.Decimal = decimal.Decimal("0.5")):
    return VNFadeOutSceneTransitionLit.get(context, _transition_decimal_to_value(context, duration))

  def handle_dissolve(duration: decimal.Decimal = decimal.Decimal("0.5")):
    return VNDissolveSceneTransitionLit.get(context, _transition_decimal_to_value(context, duration))

  def handle_slide_in(duration: decimal.Decimal = decimal.Decimal("0.5"), *, direction: str):
    dir_lit = _resolve_direction(EFFECT_PRESET_SLIDE_DIRECTION, direction)
    return VNSlideInSceneTransitionLit.get(context, _transition_decimal_to_value(context, duration), dir_lit)

  def handle_slide_out(duration: decimal.Decimal = decimal.Decimal("0.5"), *, direction: str):
    dir_lit = _resolve_direction(EFFECT_PRESET_SLIDE_DIRECTION, direction)
    return VNSlideOutSceneTransitionLit.get(context, _transition_decimal_to_value(context, duration), dir_lit)

  def handle_push(duration: decimal.Decimal = decimal.Decimal("0.5"), *, direction: str):
    dir_lit = _resolve_direction(EFFECT_PRESET_SLIDE_DIRECTION, direction)
    return VNPushSceneTransitionLit.get(context, _transition_decimal_to_value(context, duration), dir_lit)

  def handle_fade_to_color(
    *,
    fade_out: decimal.Decimal = decimal.Decimal("0.5"),
    hold: decimal.Decimal = decimal.Decimal("0.2"),
    fade_in: decimal.Decimal = decimal.Decimal("0.5"),
    color: Color,
  ):
    color_lit = ColorLiteral.get(color, context)
    return VNFadeToColorSceneTransitionLit.get(
      context,
      _transition_decimal_to_value(context, fade_out),
      _transition_decimal_to_value(context, hold),
      _transition_decimal_to_value(context, fade_in),
      color_lit,
    )

  def _resolve_zoom_point(preset_name: str, point_str: str) -> StringLiteral:
    resolved = resolve_effect_preset_value(ast, preset_name, point_str) if ast else None
    if resolved is not None:
      return resolved
    canon = canonicalize_transition_zoom_point(point_str)
    return StringLiteral.get(canon, context)

  def handle_zoom(
    duration: decimal.Decimal = decimal.Decimal("0.5"),
    *,
    direction: str,
    start_point: str = "center",
    end_point: str = "center",
  ):
    dir_lit = _resolve_direction(EFFECT_PRESET_ZOOM_DIRECTION, direction)
    d_val = _transition_decimal_to_value(context, duration)
    dir_s = dir_lit.get_string().strip().lower()
    point_str = start_point if dir_s == "in" else end_point
    point_lit = _resolve_zoom_point(EFFECT_PRESET_ZOOM_POINT, point_str)
    return VNZoomSceneTransitionLit.get(context, dir_lit, d_val, point_lit)

  callexpr = CallExprOperand(transition_name, transition_args, collections.OrderedDict(transition_kwargs))
  transition_expr = FrontendParserBase.resolve_call(callexpr, [
    (_tr_transition_backend_transition, handle_backend_specific_transition, {'expr': _tr_expr, 'backend': _tr_backend}),
    (_tr_transition_fade_in, handle_fade_in, {'duration': _tr_duration}),
    (_tr_transition_fade_out, handle_fade_out, {'duration': _tr_duration}),
    (_tr_transition_dissolve, handle_dissolve, {'duration': _tr_duration}),
    (_tr_transition_slide_in, handle_slide_in, {'duration': _tr_duration, 'direction': _tr_direction}),
    (_tr_transition_slide_out, handle_slide_out, {'duration': _tr_duration, 'direction': _tr_direction}),
    (_tr_transition_push, handle_push, {'duration': _tr_duration, 'direction': _tr_direction}),
    (_tr_transition_fade_to_color, handle_fade_to_color, {'fade_out': _tr_transition_fade_out, 'hold': _tr_hold, 'fade_in': _tr_transition_fade_in, 'color': _tr_color}),
    (_tr_transition_zoom, handle_zoom, {'duration': _tr_duration, 'direction': _tr_direction, 'start_point': _tr_start_point, 'end_point': _tr_end_point}),
  ], warnings, strict=True)
  if transition_expr is not None:
    return transition_expr
  msgs = [m for _, m in warnings]
  raise PPInvalidOperationError(
    "转场「%s」无法用当前参数解析：%s"
    % (
      transition_name,
      "；".join(msgs)
      if msgs
      else "请检查参数名与类型（「黑白酒」须用：淡出/淡出时长、停留时长、淡入/淡入时长、颜色；勿使用单独的「时长」）。",
    ),
  )


_DEFAULT_TRANSITION_DURATION = decimal.Decimal("0.5")


def map_sprite_transition_entry_to_exit(context : Context, entry : Value) -> Value:
  """立绘退场：若包裹块给出的是「入场类」通用转场，映射为对应的退场类，避免把淡入等绑在 hide 上。

  DT_NO_TRANSITION 与已是退场类 / 未知值保持原样；DT_SPRITE_SHOW 视为默认入场，映射为默认淡出。"""
  if isinstance(entry, VNFadeInSceneTransitionLit):
    return VNFadeOutSceneTransitionLit.get(context, entry.duration)
  if isinstance(entry, VNDissolveSceneTransitionLit):
    return VNDissolveSceneTransitionLit.get(context, entry.duration)
  if isinstance(entry, VNSlideInSceneTransitionLit):
    return VNSlideOutSceneTransitionLit.get(context, entry.duration, entry.direction)
  if isinstance(entry, VNPushSceneTransitionLit):
    return VNPushSceneTransitionLit.get(context, entry.duration, entry.direction)
  if isinstance(entry, VNFadeToColorSceneTransitionLit):
    return VNFadeOutSceneTransitionLit.get(context, entry.fade_out)
  if isinstance(entry, VNZoomSceneTransitionLit):
    if entry.direction.get_string().strip().lower() == "in":
      return VNZoomSceneTransitionLit.get(
        context,
        StringLiteral.get("out", context),
        entry.duration,
        entry.point,
      )
    return entry
  dt = VNDefaultTransitionType.get_default_transition_type(entry)
  if dt == VNDefaultTransitionType.DT_NO_TRANSITION:
    return entry
  if dt == VNDefaultTransitionType.DT_SPRITE_SHOW:
    return VNFadeOutSceneTransitionLit.get(context, FloatLiteral.get(_DEFAULT_TRANSITION_DURATION, context))
  return entry


def default_scene_fade_in_lit(context : Context) -> VNFadeInSceneTransitionLit:
  """用户未在命令中指定转场时，对立绘/场景显示采用的默认效果（淡入）。"""
  return VNFadeInSceneTransitionLit.get(context, FloatLiteral.get(_DEFAULT_TRANSITION_DURATION, context))


def default_scene_fade_out_lit(context : Context) -> VNFadeOutSceneTransitionLit:
  """用户未在命令中指定转场时，对立绘/场景退场采用的默认效果（淡出）。"""
  return VNFadeOutSceneTransitionLit.get(context, FloatLiteral.get(_DEFAULT_TRANSITION_DURATION, context))


def default_scene_dissolve_lit(context : Context) -> VNDissolveSceneTransitionLit:
  """场景背景在切换时的默认转场（溶解，与 Ren'Py dissolve 一致）。"""
  return VNDissolveSceneTransitionLit.get(context, FloatLiteral.get(_DEFAULT_TRANSITION_DURATION, context))


_tr_effect_bounce = _TR_vn_util.tr("instant_bounce", en="Bounce", zh_cn="跳动", zh_hk="跳動")
_tr_motion_style = _TR_vn_util.tr("motion_style", en="style", zh_cn="方式", zh_hk="方式")
_tr_bounce_height_ratio = _TR_vn_util.tr("bounce_height_ratio", en="height", zh_cn="高度", zh_hk="高度")
_tr_bounce_count = _TR_vn_util.tr("instant_bounce_count", en="count", zh_cn="次数", zh_hk="次數")
_tr_effect_tremble = _TR_vn_util.tr("instant_tremble", en=["Tremble", "Shiver"], zh_cn="发抖", zh_hk="發抖")
_tr_tremble_period = _TR_vn_util.tr("tremble_period", en="period", zh_cn="周期", zh_hk="週期")
_tr_effect_grayscale = _TR_vn_util.tr("instant_grayscale", en="Grayscale", zh_cn="灰化", zh_hk="灰化")
_tr_effect_opacity = _TR_vn_util.tr("instant_opacity", en="Opacity", zh_cn="半透明", zh_hk="半透明")
_tr_effect_tint = _TR_vn_util.tr("instant_tint", en=["Tint", "ColorOverlay"], zh_cn="色调叠加", zh_hk="色調疊加")
_tr_effect_blur = _TR_vn_util.tr("instant_blur", en="Blur", zh_cn="模糊", zh_hk="模糊")
_tr_filter_strength = _TR_vn_util.tr("filter_strength", en="strength", zh_cn="强度", zh_hk="強度")
_tr_filter_alpha = _TR_vn_util.tr("filter_alpha", en="alpha", zh_cn="透明度", zh_hk="透明度")
_tr_effect_snow = _TR_vn_util.tr("instant_snow", en="Snow", zh_cn="雪", zh_hk="雪")
_tr_effect_rain = _TR_vn_util.tr("instant_rain", en="Rain", zh_cn="雨", zh_hk="雨")
_tr_weather_intensity = _TR_vn_util.tr("weather_intensity", en="intensity", zh_cn="强度", zh_hk="強度")
_tr_weather_fade_in = _TR_vn_util.tr("weather_fade_in", en="fade_in", zh_cn="淡入时长", zh_hk="淡入時長")
_tr_weather_fade_out = _TR_vn_util.tr("weather_fade_out", en="fade_out", zh_cn="淡出时长", zh_hk="淡出時長")
_tr_weather_vx = _TR_vn_util.tr("weather_horizontal_speed", en="horizontal_speed", zh_cn="水平速度", zh_hk="水平速度")
_tr_weather_vy = _TR_vn_util.tr("weather_vertical_speed", en="vertical_speed", zh_cn="垂直速度", zh_hk="垂直速度")


def _parse_effect_duration_sustain(v : typing.Any) -> float:
  """时长：数值为秒；字符串「持续」等表示无限（IR 用 -1.0），需配合「结束特效」。
  Word 格子里常为 TextFragmentLiteral 或带引号的 \"0\"，不得对非 float 字面值直接 float(v)。"""
  if isinstance(v, TextFragmentLiteral):
    raw = v.get_string()
  elif isinstance(v, StringLiteral):
    raw = v.get_string()
  elif isinstance(v, str):
    raw = v
  elif isinstance(v, FloatLiteral):
    return float(v.value)
  elif isinstance(v, IntLiteral):
    return float(int(v.value))
  else:
    try:
      return float(v)
    except (TypeError, ValueError):
      return 0.8
  t = _strip_wrapping_quotes_for_numeric(raw).strip().lower()
  if t in ("持续", "永续", "无限", "sustain", "infinite", "loop", "forever"):
    return -1.0
  try:
    return float(t)
  except ValueError:
    return -1.0 if t else 0.8


def _normalize_motion_style(v : typing.Any) -> str:
  if isinstance(v, StringLiteral):
    s = v.get_string()
  else:
    s = str(v or "")
  t = s.strip().lower().replace("-", "").replace("_", "")
  if t in ("", "linear", "线性", "匀速"):
    return "linear"
  if t in ("ease", "缓动"):
    return "ease"
  if t in ("easein", "缓入"):
    return "easein"
  if t in ("easeout", "缓出"):
    return "easeout"
  return t


def parse_weather_effect_overlay_fade_in(effect_kind : str, cmd_duration : typing.Any) -> float:
  """天气（雨/雪）命令「时长」：正数为全屏层 alpha 淡入秒数；「持续」或省略时用该效果类型的默认淡入（如雪/雨 0.8）。"""
  if cmd_duration is None:
    return parse_instant_effect_command_duration(effect_kind, None)
  raw = _parse_effect_duration_sustain(cmd_duration)
  if raw < 0:
    return parse_instant_effect_command_duration(effect_kind, None)
  return float(raw)


def parse_instant_effect_command_duration(effect_kind : str, cmd_duration : typing.Any) -> float:
  """场景/角色特效命令上的「时长」：秒；None 时按效果类型给默认；「持续」等同义词见 _parse_effect_duration_sustain。"""
  if cmd_duration is None:
    if effect_kind == "shake":
      return 0.5
    if effect_kind == "bounce":
      return 0.4
    if effect_kind == "tremble":
      return 0.8
    if effect_kind in ("grayscale", "opacity", "tint", "blur"):
      return 0.35
    if effect_kind in ("snow", "rain"):
      return 0.8
    return 0.0
  return _parse_effect_duration_sustain(cmd_duration)


def parse_instant_effect(
  context : Context,
  call : CallExprOperand,
  ast : VNAST | None,
  warnings : list[tuple[str, str]],
) -> tuple[str, ...]:
  """
  解析场景/角色即时特效（震动、闪烁、跳动、发抖及滤镜类）。**整体过渡/持续时长**由外层命令 **时长** 提供（滤镜为过渡到目标状态的秒数；持续见 _parse_effect_duration_sustain）。返回:
  ("shake", amplitude, decay, direction_str) 或
  ("flash", color_hex, fade_in, hold, fade_out) 或
  ("bounce", height_ratio, count, style_str) 或
  ("tremble", amplitude, period) 或
  ("grayscale", strength) 或 ("opacity", alpha) 或 ("tint", color_hex, strength) 或 ("blur", radius) 或
  ("snow", intensity, inner_fade_in, inner_fade_out) 或
  ("rain", intensity, inner_fade_in, inner_fade_out, horizontal_speed, vertical_speed)
  """
  def _shake_dir(s : str) -> str:
    s = (s or "").strip()
    if not s:
      return ""
    r = resolve_effect_preset_value(ast, EFFECT_PRESET_SHAKE_DIRECTION, s) if ast else None
    if r is not None:
      return r.get_string().lower()
    low = s.lower()
    if low in ("horizontal", "h", "x", "水平"):
      return "horizontal"
    if low in ("vertical", "v", "y", "垂直"):
      return "vertical"
    return low

  def _color_str(v) -> str:
    if isinstance(v, ColorLiteral):
      c = v.value
      return f"#{c.r:02x}{c.g:02x}{c.b:02x}"
    if isinstance(v, Color):
      return f"#{v.r:02x}{v.g:02x}{v.b:02x}"
    if isinstance(v, StringLiteral):
      t = v.get_string().strip().lower()
      if t in ("白", "white", "#fff", "#ffffff"):
        return "#ffffff"
      if t in ("黑", "black", "#000", "#000000"):
        return "#000000"
      if t.startswith("#") and len(t) >= 4:
        return t
    return "#ffffff"

  def handle_shake(
    *,
    amplitude: decimal.Decimal = decimal.Decimal("12"),
    decay: decimal.Decimal = decimal.Decimal(0),
    direction: typing.Any = "",
  ):
    dstr = direction.get_string() if isinstance(direction, StringLiteral) else str(direction or "")
    return ("shake", float(amplitude), float(decay), _shake_dir(dstr))

  def handle_flash(
    *,
    color: typing.Any = "#ffffff",
    fade_in: decimal.Decimal = decimal.Decimal("0.06"),
    hold: decimal.Decimal = decimal.Decimal("0.1"),
    fade_out: decimal.Decimal = decimal.Decimal("0.18"),
  ):
    if isinstance(color, str):
      co = _color_str(StringLiteral.get(color, context))
    else:
      co = _color_str(color)
    return ("flash", co, float(fade_in), float(hold), float(fade_out))

  def handle_bounce(
    *,
    height: decimal.Decimal = decimal.Decimal("0.04"),
    count: int = 1,
    style: typing.Any = "linear",
  ):
    c = max(1, int(count))
    return ("bounce", float(height), float(c), _normalize_motion_style(style))

  def handle_tremble(
    *,
    amplitude: decimal.Decimal = decimal.Decimal(6),
    period: decimal.Decimal = decimal.Decimal("0.14"),
  ):
    p = max(0.04, float(period))
    return ("tremble", float(amplitude), float(p))

  def handle_grayscale(strength: decimal.Decimal = decimal.Decimal(1)):
    st = max(0.0, min(1.0, float(strength)))
    return ("grayscale", st)

  def handle_opacity(alpha: decimal.Decimal = decimal.Decimal("0.7")):
    a = max(0.0, min(1.0, float(alpha)))
    return ("opacity", a)

  def handle_tint(
    *,
    color: typing.Any = "#ffffff",
    strength: decimal.Decimal = decimal.Decimal("0.6"),
  ):
    if isinstance(color, str):
      co = _color_str(StringLiteral.get(color, context))
    else:
      co = _color_str(color)
    st = max(0.0, min(1.0, float(strength)))
    return ("tint", co, st)

  def handle_blur(strength: decimal.Decimal = decimal.Decimal(8)):
    b = max(0.0, min(48.0, float(strength)))
    return ("blur", b)

  def handle_snow(
    *,
    intensity: decimal.Decimal = decimal.Decimal(100),
    fade_in: decimal.Decimal = decimal.Decimal("0.25"),
    fade_out: decimal.Decimal = decimal.Decimal("0.45"),
  ):
    n = max(10.0, min(400.0, float(intensity)))
    return ("snow", n, max(0.0, float(fade_in)), max(0.05, float(fade_out)))

  def handle_rain(
    *,
    intensity: decimal.Decimal = decimal.Decimal(140),
    fade_in: decimal.Decimal = decimal.Decimal("0.2"),
    fade_out: decimal.Decimal = decimal.Decimal("0.4"),
    horizontal_speed: decimal.Decimal = decimal.Decimal("-40"),
    vertical_speed: decimal.Decimal = decimal.Decimal(520),
  ):
    n = max(20.0, min(500.0, float(intensity)))
    vx = float(horizontal_speed)
    vy = max(80.0, min(1200.0, float(vertical_speed)))
    return ("rain", n, max(0.0, float(fade_in)), max(0.05, float(fade_out)), vx, vy)

  callexpr = CallExprOperand(call.name, call.args, collections.OrderedDict(call.kwargs))
  out = FrontendParserBase.resolve_call(
    callexpr,
    [
      (_tr_effect_shake, handle_shake, {"amplitude": _tr_effect_amplitude, "decay": _tr_effect_decay, "direction": _tr_direction}),
      (_tr_effect_flash, handle_flash, {"color": _tr_color, "fade_in": _tr_flash_fade_in, "hold": _tr_hold, "fade_out": _tr_flash_fade_out}),
      (_tr_effect_bounce, handle_bounce, {"height": _tr_bounce_height_ratio, "count": _tr_bounce_count, "style": _tr_motion_style}),
      (_tr_effect_tremble, handle_tremble, {"amplitude": _tr_effect_amplitude, "period": _tr_tremble_period}),
      (_tr_effect_grayscale, handle_grayscale, {"strength": _tr_filter_strength}),
      (_tr_effect_opacity, handle_opacity, {"alpha": _tr_filter_alpha}),
      (_tr_effect_tint, handle_tint, {"color": _tr_color, "strength": _tr_filter_strength}),
      (_tr_effect_blur, handle_blur, {"strength": _tr_filter_strength}),
      (_tr_effect_snow, handle_snow, {"intensity": _tr_weather_intensity, "fade_in": _tr_weather_fade_in, "fade_out": _tr_weather_fade_out}),
      (_tr_effect_rain, handle_rain, {"intensity": _tr_weather_intensity, "fade_in": _tr_weather_fade_in, "fade_out": _tr_weather_fade_out, "horizontal_speed": _tr_weather_vx, "vertical_speed": _tr_weather_vy}),
    ],
    warnings,
    strict=True,
  )
  if out is None:
    msgs = [m for _, m in warnings]
    raise PPInvalidOperationError(
      "即时特效「%s」无法用当前参数解析：%s" % (call.name, "；".join(msgs) if msgs else "未知特效名或参数不匹配。"),
    )
  return out


_tr_sprite_move = _TR_vn_util.tr("sprite_anim_move", en="Move", zh_cn="移动", zh_hk="移動")
_tr_sprite_scale = _TR_vn_util.tr("sprite_anim_scale", en="Scale", zh_cn="缩放", zh_hk="縮放")
_tr_sprite_rotate = _TR_vn_util.tr("sprite_anim_rotate", en="Rotate", zh_cn="旋转", zh_hk="旋轉")
_tr_sprite_scale_ratio = _TR_vn_util.tr("sprite_scale_ratio", en="scale", zh_cn="比例", zh_hk="比例")
_tr_rotate_angle = _TR_vn_util.tr("sprite_rotate_angle", en="angle", zh_cn="角度", zh_hk="角度")
_tr_ratio_x = _TR_vn_util.tr("sprite_ratio_x", en="x", zh_cn="横向比例", zh_hk="橫向比例")
_tr_ratio_y = _TR_vn_util.tr("sprite_ratio_y", en="y", zh_cn="纵向比例", zh_hk="縱向比例")
# spec 形参的 Translatable：首条为报错/文档中的可读说明；末条为内部占位，避免与用户关键字冲突（get_all_candidates 才会收录）
_tr_sprite_move_spec = _TR_vn_util.tr(
  "sprite_move_spec",
  en=["positional: horizontal ratio, vertical ratio [, duration]", "__pp_sprite_move_spec__"],
  zh_cn=["按位：横向比例、纵向比例（可选第三项时长）", "__pp_sprite_move_spec__"],
  zh_hk=["按位：橫向比例、縱向比例（可選第三項時長）", "__pp_sprite_move_spec__"],
)
_tr_sprite_scale_spec = _TR_vn_util.tr(
  "sprite_scale_spec",
  en=["positional: scale [, duration]", "__pp_sprite_scale_spec__"],
  zh_cn=["按位：比例（可选第二项时长）", "__pp_sprite_scale_spec__"],
  zh_hk=["按位：比例（可選第二項時長）", "__pp_sprite_scale_spec__"],
)
_tr_sprite_rotate_spec = _TR_vn_util.tr(
  "sprite_rotate_spec",
  en=["positional: degrees [, duration]", "__pp_sprite_rotate_spec__"],
  zh_cn=["按位：角度（度）（可选第二项时长）", "__pp_sprite_rotate_spec__"],
  zh_hk=["按位：角度（度）（可選第二項時長）", "__pp_sprite_rotate_spec__"],
)


def parse_character_sprite_move(
  context : Context,
  call : CallExprOperand,
  ast : VNAST | None,
  warnings : list[tuple[str, str]],
) -> tuple[str, float, float, float, float, float, str]:
  """
  解析角色立绘补间（移动/缩放/旋转）。返回:
  (move_kind, duration, n1, n2, n3, n4, style)
  move: n1=横向位置比例(0~1), n2=纵向位置比例, n3=n4=0
  scale: n1=目标缩放(相对1.0), n2=n3=n4=0（缩放中心固定为立绘中心）
  rotate: n1=角度(度), n2=n3=n4=0（绕中心旋转）
  """
  def handle_move(
    spec: list[decimal.Decimal],
    *,
    ratio_x: decimal.Decimal | None = None,
    ratio_y: decimal.Decimal | None = None,
    duration: decimal.Decimal = decimal.Decimal("0.5"),
    style: typing.Any = "linear",
  ):
    if len(spec) >= 2:
      x, y = spec[0], spec[1]
      dur = spec[2] if len(spec) >= 3 else duration
    elif len(spec) == 0 and ratio_x is not None and ratio_y is not None:
      x, y = ratio_x, ratio_y
      dur = duration
    else:
      raise PPInvalidOperationError(
        "立绘移动需要：两个按位参数（横向比例、纵向比例，可选第三项时长），或同时使用关键字「横向比例」「纵向比例」（时长、方式仍可用关键字）。",
      )
    return ("move", float(dur), float(x), float(y), 0.0, 0.0, _normalize_motion_style(style))

  def handle_scale(
    spec: list[decimal.Decimal],
    *,
    target_scale: decimal.Decimal | None = None,
    duration: decimal.Decimal = decimal.Decimal("0.5"),
    style: typing.Any = "linear",
  ):
    if len(spec) >= 1:
      sc = spec[0]
      dur = spec[1] if len(spec) >= 2 else duration
    elif target_scale is not None:
      sc = target_scale
      dur = duration
    else:
      raise PPInvalidOperationError(
        "立绘缩放需要：一个按位参数（目标比例，可选第二项时长），或使用关键字「比例」指定比例（时长、方式仍可用关键字）。",
      )
    return ("scale", float(dur), float(sc), 0.0, 0.0, 0.0, _normalize_motion_style(style))

  def handle_rotate(
    spec: list[decimal.Decimal],
    *,
    angle: decimal.Decimal | None = None,
    duration: decimal.Decimal = decimal.Decimal("0.5"),
    style: typing.Any = "linear",
  ):
    if len(spec) >= 1:
      ang = spec[0]
      dur = spec[1] if len(spec) >= 2 else duration
    elif angle is not None:
      ang = angle
      dur = duration
    else:
      raise PPInvalidOperationError(
        "立绘旋转需要：一个按位参数（角度，单位度；可选第二项时长），或使用关键字「角度」或 angle（时长、方式仍可用关键字）。",
      )
    return ("rotate", float(dur), float(ang), 0.0, 0.0, 0.0, _normalize_motion_style(style))

  callexpr = CallExprOperand(call.name, call.args, collections.OrderedDict(call.kwargs))
  out = FrontendParserBase.resolve_call(
    callexpr,
    [
      (_tr_sprite_move, handle_move, {
        "spec": _tr_sprite_move_spec,
        "ratio_x": _tr_ratio_x,
        "ratio_y": _tr_ratio_y,
        "duration": _tr_duration,
        "style": _tr_motion_style,
      }),
      (_tr_sprite_scale, handle_scale, {
        "spec": _tr_sprite_scale_spec,
        "target_scale": _tr_sprite_scale_ratio,
        "duration": _tr_duration,
        "style": _tr_motion_style,
      }),
      (_tr_sprite_rotate, handle_rotate, {
        "spec": _tr_sprite_rotate_spec,
        "angle": _tr_rotate_angle,
        "duration": _tr_duration,
        "style": _tr_motion_style,
      }),
    ],
    warnings,
    strict=True,
  )
  if out is None:
    msgs = [m for _, m in warnings]
    raise PPInvalidOperationError(
      "立绘补间「%s」无法用当前参数解析：%s" % (call.name, "；".join(msgs) if msgs else "未知补间名或参数不匹配。"),
    )
  return out


_tr_vnutil_placer_absolute = _TR_vn_util.tr("placer_absolute",
  en="AbsolutePosition",
  zh_cn="绝对位置",
  zh_hk="絕對位置",
)
_tr_vnutil_placer_absolute_anchor = _TR_vn_util.tr("placer_absolute_anchor",
  en="Anchor",
  zh_cn="锚点",
  zh_hk="錨點",
)
_tr_vnutil_placer_absolute_scale = _TR_vn_util.tr("placer_absolute_scale",
  en="Scale",
  zh_cn="缩放比例",
  zh_hk="縮放比例",
)
_tr_vnutil_placer_absolute_anchorcoord = _TR_vn_util.tr("placer_absolute_anchorcoord",
  en="AnchorCoord",
  zh_cn="锚点坐标",
  zh_hk="錨點坐標",
)
_tr_vnutil_placer_absolute_helptext = _TR_vn_util.tr("placer_absolute_helptext",
  en="AbsolutePosition(Anchor, Scale, [AnchorCoord])",
  zh_cn="绝对位置(锚点, 缩放比例 [,锚点坐标])",
  zh_hk="絕對位置(錨點, 縮放比例 [,錨點坐標])",
)
_tr_vnutil_placer_sprite = _TR_vn_util.tr("placer_sprite",
  en="SpriteDefaultConfig",
  zh_cn="立绘默认方案",
  zh_hk="立繪默認方案",
)
_tr_vnutil_placer_sprite_baseheight = _TR_vn_util.tr("placer_sprite_baseheight",
  en="BaseHeight",
  zh_cn="屏底高度",
  zh_hk="屏底高度",
)
_tr_vnutil_placer_sprite_topheight = _TR_vn_util.tr("placer_sprite_topheight",
  en="TopHeight",
  zh_cn="顶部高度",
  zh_hk="頂部高度",
)
_tr_vnutil_placer_sprite_xoffset = _TR_vn_util.tr("placer_sprite_xoffset",
  en="XOffset",
  zh_cn="横向偏移",
  zh_hk="橫向偏移",
)
_tr_vnutil_placer_sprite_xpos = _TR_vn_util.tr("placer_sprite_xpos",
  en="XPos",
  zh_cn="横向位置",
  zh_hk="橫向位置",
)
_tr_vnutil_placer_sprite_helptext = _TR_vn_util.tr("placer_sprite_helptext",
  en="SpriteDefaultConfig(BaseHeight, TopHeight, XOffset [,XPos])",
  zh_cn="立绘默认方案(屏底高度, 顶部高度, 横向偏移 [,横向位置])",
  zh_hk="立繪默認方案(屏底高度, 頂部高度, 橫向偏移 [,橫向位置])",
)

_tr_vnutil_placer_invalid_expr = _TR_vn_util.tr("placer_invalid_expr",
  en="Invalid placer expression: {expr}",
  zh_cn="无效的位置表达式: {expr}",
  zh_hk="無效的位置表達式: {expr}",
)

def resolve_placer_callexpr(context : Context, placer : CallExprOperand, defaultconf : VNASTImagePlacerParameterSymbol | None, warnings : list[tuple[str, str]], is_fillall : bool, callback : typing.Callable[[VNASTImagePlacerKind, list[Literal]], typing.Any]) -> typing.Any | None:
  def handle_placer_absolute(
    *,
    anchor : FrontendParserBase.Coordinate2D | None = None,
    scale : decimal.Decimal | None = None,
    anchorcoord : FrontendParserBase.Coordinate2D | None = None,
  ) -> typing.Any:
    if anchor is not None:
      result_anchor = anchor.to_tuple()
    elif defaultconf is not None:
      result_anchor = defaultconf.parameters.get(0).value
    else:
      result_anchor = VNASTImagePlacerKind.get_fixed_default_params(VNASTImagePlacerKind.ABSOLUTE)[0]
    if scale is not None:
      result_scale = scale
    elif defaultconf is not None:
      result_scale = defaultconf.parameters.get(1).value
    else:
      result_scale = VNASTImagePlacerKind.get_fixed_default_params(VNASTImagePlacerKind.ABSOLUTE)[1]
    if anchorcoord is not None:
      result_anchorcoord = anchorcoord.to_tuple()
    elif defaultconf is not None:
      result_anchorcoord = defaultconf.parameters.get(2).value if defaultconf.parameters.get_num_operands() > 2 else None
    else:
      result_anchorcoord = VNASTImagePlacerKind.get_additional_default_params(VNASTImagePlacerKind.ABSOLUTE) if is_fillall else None
    params = [IntTuple2DLiteral.get(result_anchor, context), FloatLiteral.get(result_scale, context)]
    if result_anchorcoord is not None:
      params.append(IntTuple2DLiteral.get(result_anchorcoord, context))
    return callback(VNASTImagePlacerKind.ABSOLUTE, params)

  def handle_placer_sprite(
    *,
    baseheight : decimal.Decimal | None = None,
    topheight : decimal.Decimal | None = None,
    xoffset : decimal.Decimal | None = None,
    xpos : decimal.Decimal | None = None,
  ) -> typing.Any:
    if baseheight is not None:
      result_baseheight = baseheight
    elif defaultconf is not None:
      result_baseheight = defaultconf.parameters.get(0).value
    else:
      result_baseheight = VNASTImagePlacerKind.get_fixed_default_params(VNASTImagePlacerKind.SPRITE)[0]
    if topheight is not None:
      result_topheight = topheight
    elif defaultconf is not None:
      result_topheight = defaultconf.parameters.get(1).value
    else:
      result_topheight = VNASTImagePlacerKind.get_fixed_default_params(VNASTImagePlacerKind.SPRITE)[1]
    if xoffset is not None:
      result_xoffset = xoffset
    elif defaultconf is not None:
      result_xoffset = defaultconf.parameters.get(2).value
    else:
      result_xoffset = VNASTImagePlacerKind.get_fixed_default_params(VNASTImagePlacerKind.SPRITE)[2]
    if xpos is not None:
      result_xpos = xpos
    elif defaultconf is not None:
      result_xpos = defaultconf.parameters.get(3).value if defaultconf.parameters.get_num_operands() > 3 else None
    else:
      result_xpos = VNASTImagePlacerKind.get_additional_default_params(VNASTImagePlacerKind.SPRITE) if is_fillall else None
      if result_xpos is not None:
        assert isinstance(result_xpos, decimal.Decimal)
    params : list[Literal] = [FloatLiteral.get(result_baseheight, context), FloatLiteral.get(result_topheight, context), FloatLiteral.get(result_xoffset, context)]
    if result_xpos is not None:
      params.append(FloatLiteral.get(result_xpos, context))
    return callback(VNASTImagePlacerKind.SPRITE, params)

  return FrontendParserBase.resolve_call(placer, [
    (_tr_vnutil_placer_absolute, handle_placer_absolute, {'anchor': _tr_vnutil_placer_absolute_anchor, 'scale': _tr_vnutil_placer_absolute_scale, 'anchorcoord': _tr_vnutil_placer_absolute_anchorcoord}),
    (_tr_vnutil_placer_sprite, handle_placer_sprite, {'baseheight': _tr_vnutil_placer_sprite_baseheight, 'topheight': _tr_vnutil_placer_sprite_topheight, 'xoffset': _tr_vnutil_placer_sprite_xoffset, 'xpos': _tr_vnutil_placer_sprite_xpos}),
  ], warnings, strict=True)

def resolve_placer_expr(context : Context, expr : ListExprTreeNode, defaultconf : VNASTImagePlacerParameterSymbol | None, presetplace : SymbolTableRegion[VNASTImagePresetPlaceSymbol], warnings : list[tuple[str, str]]) -> tuple[VNASTImagePlacerKind, list[Literal]] | None:
  # 尝试根据当前的配置解析一个完整的位置表达式
  # 如果解析失败且没有默认配置就返回 None
  # 如果解析失败但有默认配置，就根据默认配置补全参数
  anchorcoord_default_value = VNASTImagePlacerKind.get_additional_default_params(VNASTImagePlacerKind.ABSOLUTE)
  xpos_default_value = VNASTImagePlacerKind.get_additional_default_params(VNASTImagePlacerKind.SPRITE)
  assert isinstance(anchorcoord_default_value, tuple) and isinstance(xpos_default_value, decimal.Decimal)
  def construct_default_position_from_config(defaultconf : VNASTImagePlacerParameterSymbol) -> tuple[VNASTImagePlacerKind, list[Literal]]:
    match defaultconf.kind.get().value:
      case VNASTImagePlacerKind.ABSOLUTE:
        anchor = defaultconf.parameters.get(0).value
        scale = defaultconf.parameters.get(1).value
        anchorcoord = defaultconf.parameters.get(2).value if defaultconf.parameters.get_num_operands() > 2 else IntTuple2DLiteral.get(anchorcoord_default_value, context)
        return (VNASTImagePlacerKind.ABSOLUTE, [anchor, scale, anchorcoord])
      case VNASTImagePlacerKind.SPRITE:
        baseheight = defaultconf.parameters.get(0).value
        topheight = defaultconf.parameters.get(1).value
        xoffset = defaultconf.parameters.get(2).value
        xpos = defaultconf.parameters.get(3).value if defaultconf.parameters.get_num_operands() > 3 else FloatLiteral.get(xpos_default_value, context)
        return (VNASTImagePlacerKind.SPRITE, [baseheight, topheight, xoffset, xpos])
      case _:
        raise PPInternalError("Unknown placer kind")
  placer = expr.value
  is_placer_type_expected = False
  if isinstance(placer, str):
    is_placer_type_expected = True
    name = placer
    if preset := presetplace.get(name):
      parameters = [u.value for u in preset.parameters.operanduses()]
      return (preset.kind.get().value, parameters)
    # 如果有默认配置，尝试给当前项加上调用表达式的前后缀，再尝试解析
    if defaultconf is not None and len(name) > 0:
      prefix = ""
      match defaultconf.kind.get().value:
        case VNASTImagePlacerKind.ABSOLUTE:
          prefix = _tr_vnutil_placer_absolute.get()
        case VNASTImagePlacerKind.SPRITE:
          prefix = _tr_vnutil_placer_sprite.get()
        case _:
          raise PPInternalError("Unknown placer kind")
      complete_str = prefix + '(' + name + ')'
      is_converted = False
      if cmd := FrontendParserBase.try_get_callexproperand_or_str(context, complete_str):
        if isinstance(cmd, CallExprOperand):
          placer = cmd
          is_converted = True
          # 这里直接过渡到下一段 CallExprOperand 的处理
      if not is_converted:
        warnings.append(("vnparse-placer-invalid-expr", _tr_vnutil_placer_invalid_expr.format(expr=name)))
  if isinstance(placer, CallExprOperand):
    is_placer_type_expected = True
    if result := resolve_placer_callexpr(context=context, placer=placer, defaultconf=defaultconf, warnings=warnings, is_fillall=True, callback=lambda kind, parameters: (kind, parameters)):
      return result
  # 如果执行到这里，说明解析失败
  if not is_placer_type_expected:
    warnings.append(("vnparse-placer-invalid-expr", _tr_vnutil_placer_invalid_expr.format(expr=str(placer))))
  if defaultconf is not None:
    # 根据类别补全参数
    return construct_default_position_from_config(defaultconf)
  # 没有默认配置就没办法了
  return None

_tr_vnutil_presetplace_missing_name = _TR_vn_util.tr("presetplace_missing_name",
  en="Missing name for preset place : {expr}",
  zh_cn="缺少预设位置的名称: {expr}",
  zh_hk="缺少預設位置的名稱: {expr}",
)
_tr_vnutil_placer_invalid_config = _TR_vn_util.tr("placer_invalid_config",
  en="Invalid placer config: {expr}",
  zh_cn="无效的位置配置: {expr}",
  zh_hk="無效的位置配置: {expr}",
)

def parse_image_placer_config(context : Context, placing_expr : ListExprTreeNode, config : SymbolTableRegion[VNASTImagePlacerParameterSymbol], presetplace : SymbolTableRegion[VNASTImagePresetPlaceSymbol], warnings : list[tuple[str, str]]) -> None:
  # 这个函数用于处理图片声明时（比如声明角色时）对位置的设置
  # 绝对位置(锚点=坐标(x,y),缩放比例,<锚点坐标>)
  # 立绘默认方案(屏底高度,顶部高度,横向偏移,<横向位置>)
  if not isinstance(placing_expr.value, CallExprOperand):
    warnings.append(("vnparse-placer-invalid-config", _tr_vnutil_placer_invalid_config.format(expr=str(placing_expr.value))))
    return
  placer = placing_expr.value
  placersymbol = resolve_placer_callexpr(context=context, placer=placer, defaultconf=None, warnings=warnings, is_fillall=False, callback=lambda kind, parameters: VNASTImagePlacerParameterSymbol.create(context=context, kind=kind, parameters=parameters, loc = placing_expr.location))
  if placersymbol is None:
    return
  config.add(placersymbol)
  # 现在开始处理预设位置
  for child in placing_expr.children:
    if expr := resolve_placer_expr(context=context, expr=child, defaultconf=placersymbol, presetplace=presetplace, warnings=warnings):
      if child.key is None or len(child.key) == 0:
        warnings.append(("vnparse-placer-missing-name", _tr_vnutil_presetplace_missing_name.format(expr=str(child))))
        continue
      place = VNASTImagePresetPlaceSymbol.create(context=context, name=child.key, kind=expr[0], parameters=expr[1], loc=child.location)
      presetplace.add(place)
  # 完成！
setattr(parse_image_placer_config, "keywords", [
  _tr_vnutil_placer_absolute_helptext,
  _tr_vnutil_placer_sprite_helptext,
])

def infer_placeholder_sizes(t : SymbolTableRegion[VNASTNamespaceSwitchableValueSymbol], default_size : tuple[int, int], default_bbox : tuple[int, int, int, int]):
  # 原来只是为了给 PlaceholderImageLiteralExpr 推导大小，现在所有没设置大小的都进行推导
  value_uses : list[Use] = []
  has_unsized_uses = False
  exprs_requiring_size_inference = (PlaceholderImageLiteralExpr, DeclaredImageLiteralExpr, ColorImageLiteralExpr)
  for s in t:
    if not isinstance(s, VNASTNamespaceSwitchableValueSymbol):
      raise PPInternalError()
    for ns, operand in s.operands.items():
      if not isinstance(operand, OpOperand):
        raise PPInternalError()
      for use in operand.operanduses():
        if isinstance(use.value, BaseImageLiteralExpr):
          value_uses.append(use)
          if isinstance(use.value, exprs_requiring_size_inference) and use.value.size.value == (0,0):
            has_unsized_uses = True
        elif isinstance(use.value, StringLiteral):
          continue
        else:
          raise PPInternalError("Unexpected image value type: " + str(type(use.value)))
  if not has_unsized_uses:
    return
  # 我们只保留画幅面积最大(w*h 最大)的 bbox
  cur_bbox_xmin = 0
  cur_bbox_ymin = 0
  cur_bbox_xmax = 0
  cur_bbox_ymax = 0
  cur_width = 0
  cur_height = 0
  placeholder_uses : list[Use] = []
  for u in value_uses:
    expr = u.value
    if not isinstance(expr, BaseImageLiteralExpr):
      raise PPInternalError()
    w, h = expr.size.value
    if isinstance(expr, exprs_requiring_size_inference) and expr.size.value == (0,0):
      placeholder_uses.append(u)
    if w * h > cur_width * cur_height:
      # 如果画幅更大，则完全替换之前的结果
      cur_width = w
      cur_height = h
      cur_bbox_xmin, cur_bbox_ymin, cur_bbox_xmax, cur_bbox_ymax = expr.bbox.value
    elif w == cur_width and h == cur_height:
      # 取并集
      xmin, ymin, xmax, ymax = expr.bbox.value
      cur_bbox_xmin = min(cur_bbox_xmin, xmin)
      cur_bbox_ymin = min(cur_bbox_ymin, ymin)
      cur_bbox_xmax = max(cur_bbox_xmax, xmax)
      cur_bbox_ymax = max(cur_bbox_ymax, ymax)
  if cur_width == 0 and cur_height == 0:
    cur_width, cur_height = default_size
    cur_bbox_xmin, cur_bbox_ymin, cur_bbox_xmax, cur_bbox_ymax = default_bbox
  for u in placeholder_uses:
    expr = u.value
    if not isinstance(expr, exprs_requiring_size_inference):
      raise PPInternalError()
    newexpr = expr.get_with_updated_sizes(size=(cur_width, cur_height), bbox=(cur_bbox_xmin, cur_bbox_ymin, cur_bbox_xmax, cur_bbox_ymax))
    if not type(expr) is type(newexpr):
      raise PPInternalError()
    u.set_value(newexpr)

def parse_postprocessing_update_placeholder_imagesizes(ast : VNAST):
  screen_width, screen_height = ast.screen_resolution.get().value
  background_size = (screen_width, screen_height)
  charactersprite_width = int(600 * screen_height / 1080)
  charactersprite_size = (charactersprite_width, screen_height)
  charactersideimage_width = int(600 * min(screen_width, screen_height) / 1080)
  charactersideimage_size = (charactersideimage_width, charactersideimage_width)
  for f in ast.files.body:
    if not isinstance(f, VNASTFileInfo):
      raise PPInternalError("Unexpected file type")
    for c in f.characters:
      if not isinstance(c, VNASTCharacterSymbol):
        raise PPInternalError("Unexpected character type")
      infer_placeholder_sizes(c.sprites, charactersprite_size, (0, 0, charactersprite_size[0], charactersprite_size[1]))
      infer_placeholder_sizes(c.sideimages, charactersideimage_size, (0, 0, charactersideimage_size[0], charactersideimage_size[1]))
    for s in f.scenes:
      if not isinstance(s, VNASTSceneSymbol):
        raise PPInternalError("Unexpected scene type")
      infer_placeholder_sizes(s.backgrounds, background_size, (0, 0, background_size[0], background_size[1]))
