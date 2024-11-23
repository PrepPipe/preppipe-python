# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
from .ast import *
from ..irbase import *
from ..vnmodel import *
from ..util.imagepackexportop import *

SelfType = typing.TypeVar('SelfType', bound='BackendCodeGenHelperBase') # pylint: disable=invalid-name
NodeType = typing.TypeVar('NodeType', bound=BackendASTNodeBase) # pylint: disable=invalid-name
class BackendCodeGenHelperBase(typing.Generic[NodeType]):
  # 这里我们提供标准的从 Block 末尾往前生成代码的接口
  # 我们使用 CODEGEN_MATCH_TREE 来组织代码生成的逻辑
  # 我们从每个 Block 的末尾开始，根据开始、结束时间将指令顺序化，并用 CODEGEN_MATCH_TREE 来生成代码
  CODEGEN_MATCH_TREE : typing.ClassVar[dict] = {}
  ASSET_BASEDIR_MATCH_TREE : typing.ClassVar[dict] = {}
  ASSET_SUPPORTED_FORMATS : typing.ClassVar[dict[type, list[str]]] = {}

  # 我们一般应该只有在素材确定被用到的时候才将其写到输出目录
  # 然而一般来说我们会先扫过所有场景、角色声明、素材声明等，然后再处理剧本内容
  # 所以我们需要暂时在不知道它是否被用到的时候先把名称记录下来
  # TODO 添加对更多资源类型的支持
  class NamedAssetKind(enum.Enum):
    NAMED_MISC = enum.auto()
    CHARACTER_SPRITE = enum.auto()
    CHARACTER_SIDEIMAGE = enum.auto()
    BACKGROUND = enum.auto()
    CG = enum.auto()

    @staticmethod
    def get_filter_from_user_hint(hint : VNStandardDeviceKind):
      match hint:
        # 目前还没有做对音频资源的声明，所以他们不可能是带名字的资源
        case VNStandardDeviceKind.O_BGM_AUDIO:
          return BackendCodeGenHelperBase.NamedAssetKind.NAMED_MISC
        case VNStandardDeviceKind.O_SE_AUDIO:
          return BackendCodeGenHelperBase.NamedAssetKind.NAMED_MISC
        case VNStandardDeviceKind.O_VOICE_AUDIO:
          return BackendCodeGenHelperBase.NamedAssetKind.NAMED_MISC
        case VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
          return (BackendCodeGenHelperBase.NamedAssetKind.CHARACTER_SPRITE, # 人物立绘
                  BackendCodeGenHelperBase.NamedAssetKind.NAMED_MISC) # 其他前景（物件图）
        case VNStandardDeviceKind.O_BACKGROUND_DISPLAY:
          return (BackendCodeGenHelperBase.NamedAssetKind.BACKGROUND, # 背景
                  BackendCodeGenHelperBase.NamedAssetKind.CG) # CG
        case VNStandardDeviceKind.O_SAY_SIDEIMAGE_DISPLAY:
          return BackendCodeGenHelperBase.NamedAssetKind.CHARACTER_SIDEIMAGE
        case _:
          return BackendCodeGenHelperBase.NamedAssetKind.NAMED_MISC

  @dataclasses.dataclass
  class NamedAssetInfo:
    value : Value
    kind : "BackendCodeGenHelperBase.NamedAssetKind"
    self_symbol : VNAssetValueSymbol | None = None # 该资源在哪被声明的（比如某角色的某立绘差分）
    parent_symbol : VNSymbol | None = None # 该资源的父级符号（比如哪个角色）
    internal_data : typing.Any | None = None
    used : bool = False # 是否被用到了。只在所有代码生成完后才能最终决定

  # --------------------------------------------------------------------------
  # 子类可以（应该）使用的成员
  model : VNModel
  imagepack_handler : ImagePackExportDataBuilder

  # --------------------------------------------------------------------------
  # 这个类自己用的成员
  anon_asset_index_dict : collections.OrderedDict[str, int] # parent dir -> anon index
  asset_decl_info_dict : collections.OrderedDict[Value, list[NamedAssetInfo]]

  # --------------------------------------------------------------------------

  def __init__(self, model : VNModel, imagepack_handler : ImagePackExportDataBuilder | None) -> None:
    self.model = model
    self.imagepack_handler = imagepack_handler if imagepack_handler is not None else ImagePackExportDataBuilder()
    self.anon_asset_index_dict = collections.OrderedDict()
    self.asset_decl_info_dict = collections.OrderedDict()

  @property
  def context(self) -> Context:
    return self.model.context

  @classmethod
  def is_matchtree_installed(cls) -> bool:
    return len(cls.CODEGEN_MATCH_TREE) > 0

  @classmethod
  def install_codegen_matchtree(cls, matchtree: dict):
    # 每一个键都应该是 VNInstruction 的子类，每一个值要么是一个 dict 且键有 None，要么是一个函数
    # 函数应该是像 gen_XXX(self, instrs: list[VNInstruction], insert_before: NodeType) -> NodeType 这样
    # 返回值是下一个插入位置
    cls.CODEGEN_MATCH_TREE = matchtree
    def checktreerecursive(tree : dict, istop : bool):
      for k, v in tree.items():
        if k is not None:
          if not issubclass(k, VNInstruction):
            raise ValueError(f"Key {k} is not a subclass of VNInstruction")
        if isinstance(v, dict):
          if None not in v:
            raise ValueError(f"Value {v} is not a dict with None key")
          checktreerecursive(v, False)
        elif callable(v):
          pass
        else:
          raise ValueError(f"Unexpected value type {v}")
    checktreerecursive(matchtree, True)

  @classmethod
  def install_asset_basedir_matchtree(cls, matchtree: dict):
    # 每个键都应该是 AssetData 的子类，每个值要么是一个 dict 且键是 VNStandardDeviceKind 或是 None，要么是一个字符串（即该资源类型的基础路径）
    cls.ASSET_BASEDIR_MATCH_TREE = matchtree
    def checktreerecursive(tree : dict, istop : bool):
      for k, v in tree.items():
        if k is not None:
          if istop:
            if not issubclass(k, AssetData):
              raise ValueError(f"Key {k} is not a subclass of AssetData")
          else:
            if not isinstance(k, VNStandardDeviceKind):
              raise ValueError(f"Key {k} is not an instance of VNStandardDeviceKind")
        if isinstance(v, dict):
          if istop:
            checktreerecursive(v, False)
          else:
            raise ValueError(f"Value {v} is a dict but not at top level")
        elif isinstance(v, str):
          pass
        else:
          raise ValueError(f"Unexpected value type {v}")
    checktreerecursive(matchtree, True)

  @classmethod
  def install_asset_supported_formats(cls, formats: dict):
    # 每个键都应该是 AssetData 的子类，每个值应该是一个字符串列表，表示支持的格式
    cls.ASSET_SUPPORTED_FORMATS = formats
    for k, v in formats.items():
      if not issubclass(k, AssetData):
        raise ValueError(f"Key {k} is not a subclass of AssetData")
      if len(v) == 0:
        raise ValueError(f"Value {v} is an empty list")
      if not all(isinstance(x, str) for x in v):
        raise ValueError(f"Value {v} is not a list of strings")

  # --------------------------------------------------------------------------
  # 需要子类实现的接口

  def gen_terminator(self, terminator : VNTerminatorInstBase, **kwargs) -> NodeType:
    raise NotImplementedError()

  def get_result(self) -> BackendProjectModelBase:
    raise NotImplementedError()

  # --------------------------------------------------------------------------

  @classmethod
  def match_codegen_depth1(cls, ty : type) -> typing.Callable:
    match_result = cls.CODEGEN_MATCH_TREE[ty]
    if isinstance(match_result, dict):
      match_result = match_result[None]
    return match_result

  @classmethod
  def is_waitlike_instr(cls, instr : VNInstruction) -> bool:
    if isinstance(instr, VNWaitInstruction):
      return True
    return False

  def codegen_block(self, b : Block, **kwargs):
    terminator = b.body.back
    assert isinstance(terminator, VNTerminatorInstBase)
    cur_insertpos = self.gen_terminator(terminator, **kwargs)
    if terminator is b.body.front:
      # 这个块里除了终结指令之外没有其他指令
      return
    cur_srcpos = terminator
    block_start = b.get_argument('start')
    visited_instrs = set()

    while True:
      # 从最后的指令开始往前
      if cur_srcpos is b.body.front:
        return
      cur_srcpos = cur_srcpos.get_prev_node()
      if isinstance(cur_srcpos, VNInstruction):
        if cur_srcpos in visited_instrs:
          continue
        instrs, gen = self.match_instr_patterns(cur_srcpos.get_finish_time(), block_start)
        cur_insertpos = gen(self, instrs, cur_insertpos)
        visited_instrs.update(instrs)
      else:
        if isinstance(cur_srcpos, MetadataOp):
          # 直接把它们复制过去
          cloned = cur_srcpos.clone()
          cloned.insert_before(cur_insertpos)
          cur_insertpos = cloned
        else:
          raise RuntimeError('Unexpected instruction kind: ' + type(cur_srcpos).__name__)

  def match_instr_patterns(self, finishtime : OpResult, blocktime : Value) -> tuple[list[VNInstruction], typing.Callable]:
    assert isinstance(finishtime, OpResult) and isinstance(finishtime.valuetype, VNTimeOrderType)
    cur_match_dict = self.CODEGEN_MATCH_TREE
    instrs = []
    while True:
      end_instr : VNInstruction = finishtime.parent
      assert isinstance(end_instr, VNInstruction)
      instrs.append(end_instr)
      match_type = type(end_instr)
      if match_type not in cur_match_dict:
        if None not in cur_match_dict:
          raise RuntimeError('Codegen for instr type not supported yet: ' + match_type.__name__)
        match_result = cur_match_dict[None]
      else:
        match_result = cur_match_dict[match_type]
      if isinstance(match_result, dict):
        cur_match_dict = match_result
        finishtime = end_instr.get_start_time()
        # 遇到以下三种情况时我们停止匹配：
        # 1. 已经到块的开头
        # 2. 前一个指令是上一步的类似等待的指令
        # 3. 除了当前匹配到的指令外，前一个指令的输出时间有其他使用者（我们不能把这个输出时间抢走）
        if finishtime is blocktime or self.is_waitlike_instr(finishtime.parent):
          return (instrs, match_result[None])
        for u in finishtime.uses:
          user_instr : VNInstruction = u.user.parent # type: ignore
          if user_instr is not end_instr and user_instr.try_get_parent_group() is not end_instr:
            # 情况三
            return (instrs, match_result[None])
        # 否则我们继续匹配
        continue
      return (instrs, match_result)

  def get_asset_rootpath(self, v : AssetData, user_hint : VNStandardDeviceKind | None) -> str:
    ty_key = type(v)
    if ty_key not in self.ASSET_BASEDIR_MATCH_TREE:
      ty_key = None
    cur_match_dict = self.ASSET_BASEDIR_MATCH_TREE[ty_key]
    if isinstance(cur_match_dict, dict):
      if user_hint in cur_match_dict:
        return cur_match_dict[user_hint]
      return cur_match_dict[None]
    elif isinstance(cur_match_dict, str):
      return cur_match_dict
    else:
      raise RuntimeError('Unexpected match tree value type: ' + type(cur_match_dict).__name__)


  def get_asset_export_path(self, v : AssetData, parentdir : str, export_format_ext : str | None) -> str:
    # 给指定的资源生成一个在 parentdir 下的导出路径
    # 如果 export_format_ext 提供的话，应该是一个小写的后缀名，不带 '.'，没提供的话就是不改变原来的后缀名
    # 这里我们也要处理去重等情况
    NAME_ANON = 'anon'
    basename = NAME_ANON
    baseext = str(v.format)
    if export_format_ext == baseext:
      export_format_ext = None
    if len(baseext) == 0:
      baseext = 'bin'
    if loc := v.location:
      fileloc = loc.get_file_path()
      assert len(fileloc) > 0
      basepath, oldext = os.path.splitext(fileloc)
      basename = os.path.basename(basepath)
      assert oldext[0] == '.'
      baseext = oldext[1:]
    if export_format_ext is not None:
      baseext = export_format_ext
    # 找到一个没被用上的名字
    cur_path = parentdir + '/' + basename + '.' + baseext
    if existing := self.get_result().get_asset(cur_path):
      # 如果内容一样就直接报错（不应该尝试生成导出路径）
      # 不然的话加后缀直到不重名
      if existing.get_asset_value() is v:
        raise RuntimeError('Should not happen')
      suffix = 0
      if basename == NAME_ANON and parentdir in self.anon_asset_index_dict:
        suffix = self.anon_asset_index_dict[parentdir]
      cur_path = parentdir + '/' + basename + '_' + str(suffix) + '.' + baseext
      while existing := self.get_result().get_asset(cur_path):
        if existing.get_asset_value() is v:
          raise RuntimeError('Should not happen')
        suffix += 1
        cur_path = parentdir + '/' + basename + '_' + str(suffix) + '.' + baseext
      if basename == NAME_ANON:
        self.anon_asset_index_dict[parentdir] = suffix + 1
    return cur_path

  def get_asset_export_format(self, v : AssetData) -> str:
    supported_formats = self.ASSET_SUPPORTED_FORMATS[type(v)]
    cur_format = str(v.format)
    if cur_format in supported_formats:
      return cur_format
    return supported_formats[0]

  def add_assetdata(self, v : AssetData, user_hint : VNStandardDeviceKind | None = None) -> str:
    rootdir = self.get_asset_rootpath(v, user_hint)

    # 看看是否需要转换格式，需要的话把值和后缀都改了
    export_format = self.get_asset_export_format(v)
    path = self.get_asset_export_path(v, rootdir, export_format)
    file = BackendFileAssetOp.create(context=v.context, assetref=v, export_format=export_format, path=path)
    self.get_result().add_asset(file)
    return path

  def _add_asset_name(self, v : Value, info : NamedAssetInfo):
    if v not in self.asset_decl_info_dict:
      self.asset_decl_info_dict[v] = []
    self.asset_decl_info_dict[v].append(info)

  def query_asset_name(self, v : Value, *, symbol : VNSymbol | None = None, kind : NamedAssetKind | tuple[NamedAssetKind, ...] | None = None) -> list[NamedAssetInfo]:
    if v in self.asset_decl_info_dict:
      result = []
      for entry in self.asset_decl_info_dict[v]:
        if symbol is not None and entry.self_symbol is not symbol:
          continue
        if kind is not None:
          if entry.kind not in kind if isinstance(kind, tuple) else entry.kind != kind:
            continue
        result.append(entry)
      return result
    return []

  def collect_named_assets(self, n : VNNamespace):
    for c in n.characters:
      for symb in c.sprites:
        value = symb.get_value()
        self._add_asset_name(value, self.NamedAssetInfo(value=value, kind=self.NamedAssetKind.CHARACTER_SPRITE, self_symbol=symb, parent_symbol=c))
      for symb in c.sideimages:
        value = symb.get_value()
        self._add_asset_name(value, self.NamedAssetInfo(value=value, kind=self.NamedAssetKind.CHARACTER_SIDEIMAGE, self_symbol=symb, parent_symbol=c))
    for b in n.scenes:
      for bg in b.backgrounds:
        value = bg.get_value()
        self._add_asset_name(value, self.NamedAssetInfo(value=value, kind=self.NamedAssetKind.BACKGROUND, self_symbol=bg, parent_symbol=b))
    for a in n.assets:
      value = a.get_value()
      self._add_asset_name(value, self.NamedAssetInfo(value=value, kind=self.NamedAssetKind.NAMED_MISC, self_symbol=a))

  def get_handle_value_and_device(self, handlein : Value) -> tuple[Value, VNDeviceSymbol]:
    assert isinstance(handlein, (VNCreateInst, VNModifyInst, BlockArgument))
    if isinstance(handlein, BlockArgument):
      raise PPNotImplementedError('Handles from block arguments not supported yet')
    if isinstance(handlein, VNCreateInst):
      value = handlein.content.get()
    elif isinstance(handlein, VNModifyInst):
      value = handlein.content.get()
    else:
      raise PPInternalError('Should not happen')
    rootdev = None
    curhandle = handlein
    while not isinstance(curhandle, VNCreateInst):
      assert isinstance(curhandle, VNModifyInst)
      curhandle = curhandle.handlein.get()
    rootdev = curhandle.device.get()
    return (value, rootdev)

  def get_root_handle(self, handlein : Value) -> VNCreateInst:
    assert isinstance(handlein, (VNCreateInst, VNModifyInst, BlockArgument))
    if isinstance(handlein, VNCreateInst):
      return handlein
    if isinstance(handlein, BlockArgument):
      raise PPNotImplementedError('Handles from block arguments not supported yet')
    curhandle = handlein
    while not isinstance(curhandle, VNCreateInst):
      assert isinstance(curhandle, VNModifyInst)
      curhandle = curhandle.handlein.get()
    return curhandle
