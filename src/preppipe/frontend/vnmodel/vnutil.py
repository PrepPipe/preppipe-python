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

def get_default_size_for_placeholders(dest : ImageExprPlaceholderDest, screen_resolution : tuple[int, int] | None = None) -> tuple[int, int]:
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
  return finalresolution

def emit_default_placeholder(context : Context, dest : ImageExprPlaceholderDest, description : StringLiteral | None = None) -> PlaceholderImageLiteralExpr:
  if description is None:
    description = StringLiteral.get('', context)
  placeholder = PlaceholderImageLiteralExpr.get(context=context, dest=dest, desc=description, size=IntTupleLiteral.get((0,0), context))
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
def emit_image_expr_from_callexpr(context : Context, call : CallExprOperand, placeholderdest : ImageExprPlaceholderDest, placeholderdesc: str, warnings : list[tuple[str, str]]) -> BaseImageLiteralExpr | None:
  # 调用表达式有以下几种可能：(所有的分辨率输入均为可选项，解析完成后我们会尝试推导分辨率)
  # 占位（描述=...，分辨率=...），描述可选，按位参数视为描述
  # 声明（引用=...，分辨率=...）, 引用必需，按位参数视为引用
  # 纯色填充（颜色=..., 分辨率=...），均必须，按位参数视为颜色
  # 所有的分辨率（如果有的话）都是一个"宽*高"的字符串，比如 "1920*1080"

  def handle_placeholder_expr(desc : str = '', *, resolution : FrontendParserBase.Resolution | None = None) -> PlaceholderImageLiteralExpr:
    resolution_v = resolution.resolution if resolution is not None else (0,0)
    if len(desc) == 0:
      desc = placeholderdesc
    return PlaceholderImageLiteralExpr.get(context=context, dest=placeholderdest, desc=StringLiteral.get(desc, context), size=IntTupleLiteral.get(resolution_v, context))

  def handle_decl_expr(ref : str, *, resolution : FrontendParserBase.Resolution | None = None) -> DeclaredImageLiteralExpr:
    resolution_v = resolution.resolution if resolution is not None else (0,0)
    return DeclaredImageLiteralExpr.get(context=context, decl=StringLiteral.get(ref, context), size=IntTupleLiteral.get(resolution_v, context))

  def handle_colorfill_expr(color : Color, *, resolution : FrontendParserBase.Resolution | None = None) -> ColorImageLiteralExpr:
    resolution_v = resolution.resolution if resolution is not None else (0,0)
    return ColorImageLiteralExpr.get(context=context, color=ColorLiteral.get(color, context), size=IntTupleLiteral.get(resolution_v, context))

  imageexpr = FrontendParserBase.resolve_call(call, [
    (_tr_placeholder, handle_placeholder_expr, {'desc': _tr_description, 'resolution': _tr_resolution}),
    (_tr_decl, handle_decl_expr, {'ref': _tr_ref, 'resolution': _tr_resolution}),
    (_tr_colorfill, handle_colorfill_expr, {'color': _tr_color, 'resolution': _tr_resolution}),
  ], warnings)
  if imageexpr is not None:
    return imageexpr
  return None

def emit_image_expr_from_str(context : Context, s : str, basepath : str,  placeholderdest : ImageExprPlaceholderDest, placeholderdesc : str, warnings : list[tuple[str, str]]) -> BaseImageLiteralExpr | None:
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
      return emit_image_expr_from_callexpr(context=context, call=callexpr, placeholderdest=placeholderdest, placeholderdesc=placeholderdesc, warnings=warnings)
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

  def handle_backend_specific_transition(expr : str, *, backend : str) -> tuple[StringLiteral, StringLiteral]:
    return (StringLiteral.get(backend, context), StringLiteral.get(expr, context))

  callexpr = CallExprOperand(transition_name, transition_args, collections.OrderedDict(transition_kwargs))
  transition_expr = FrontendParserBase.resolve_call(callexpr, [
    (_tr_transition_backend_transition, handle_backend_specific_transition, {'expr': _tr_expr, 'backend': _tr_backend}),
  ], warnings)
  return transition_expr

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
  def handle_placer_absolute(anchor : FrontendParserBase.Coordinate2D | None = None,
                             scale : decimal.Decimal | None = None,
                             anchorcoord : FrontendParserBase.Coordinate2D | None = None) -> typing.Any:
    if anchor is not None:
      result_anchor = anchor.to_tuple()
    elif defaultconf is not None:
      result_anchor = defaultconf.parameters.get(0).value
    else:
      result_anchor = (0,0)
    if scale is not None:
      result_scale = scale
    elif defaultconf is not None:
      result_scale = defaultconf.parameters.get(1).value
    else:
      result_scale = decimal.Decimal(1.0)
    if anchorcoord is not None:
      result_anchorcoord = anchorcoord.to_tuple()
    elif defaultconf is not None:
      result_anchorcoord = defaultconf.parameters.get(2).value if defaultconf.parameters.get_num_operands() > 2 else None
    else:
      result_anchorcoord = (0,0) if is_fillall else None
    params = [IntTupleLiteral.get(result_anchor, context), FloatLiteral.get(result_scale, context)]
    if result_anchorcoord is not None:
      params.append(IntTupleLiteral.get(result_anchorcoord, context))
    return callback(VNASTImagePlacerKind.ABSOLUTE, params)

  def handle_placer_sprite(baseheight : decimal.Decimal | None = None,
                            topheight : decimal.Decimal | None = None,
                            xoffset : decimal.Decimal | None = None,
                            xpos : decimal.Decimal | None = None) -> typing.Any:
    if baseheight is not None:
      result_baseheight = baseheight
    elif defaultconf is not None:
      result_baseheight = defaultconf.parameters.get(0).value
    else:
      result_baseheight = decimal.Decimal(0.0)
    if topheight is not None:
      result_topheight = topheight
    elif defaultconf is not None:
      result_topheight = defaultconf.parameters.get(1).value
    else:
      result_topheight = decimal.Decimal(1.0)
    if xoffset is not None:
      result_xoffset = xoffset
    elif defaultconf is not None:
      result_xoffset = defaultconf.parameters.get(2).value
    else:
      result_xoffset = decimal.Decimal(0.0)
    if xpos is not None:
      result_xpos = xpos
    elif defaultconf is not None:
      result_xpos = defaultconf.parameters.get(3).value if defaultconf.parameters.get_num_operands() > 3 else None
    else:
      result_xpos = decimal.Decimal(0.0) if is_fillall else None
    params : list[Literal] = [FloatLiteral.get(result_baseheight, context), FloatLiteral.get(result_topheight, context), FloatLiteral.get(result_xoffset, context)]
    if result_xpos is not None:
      params.append(FloatLiteral.get(result_xpos, context))
    return callback(VNASTImagePlacerKind.SPRITE, params)

  return FrontendParserBase.resolve_call(placer, [
    (_tr_vnutil_placer_absolute, handle_placer_absolute, {'anchor': _tr_vnutil_placer_absolute_anchor, 'scale': _tr_vnutil_placer_absolute_scale, 'anchorcoord': _tr_vnutil_placer_absolute_anchorcoord}),
    (_tr_vnutil_placer_sprite, handle_placer_sprite, {'baseheight': _tr_vnutil_placer_sprite_baseheight, 'topheight': _tr_vnutil_placer_sprite_topheight, 'xoffset': _tr_vnutil_placer_sprite_xoffset, 'xpos': _tr_vnutil_placer_sprite_xpos}),
  ], warnings)

def resolve_placer_expr(context : Context, expr : ListExprTreeNode, defaultconf : VNASTImagePlacerParameterSymbol | None, presetplace : SymbolTableRegion[VNASTImagePresetPlaceSymbol], warnings : list[tuple[str, str]]) -> tuple[VNASTImagePlacerKind, list[Literal]] | None:
  # 尝试根据当前的配置解析一个完整的位置表达式
  # 如果解析失败且没有默认配置就返回 None
  # 如果解析失败但有默认配置，就根据默认配置补全参数
  anchorcoord_default_value = (0, 0)
  xpos_default_value = decimal.Decimal(0.0)
  def construct_default_position_from_config(defaultconf : VNASTImagePlacerParameterSymbol) -> tuple[VNASTImagePlacerKind, list[Literal]]:
    match defaultconf.kind.get().value:
      case VNASTImagePlacerKind.ABSOLUTE:
        anchor = defaultconf.parameters.get(0).value
        scale = defaultconf.parameters.get(1).value
        anchorcoord = defaultconf.parameters.get(2).value if defaultconf.parameters.get_num_operands() > 2 else IntTupleLiteral.get(anchorcoord_default_value, context)
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
