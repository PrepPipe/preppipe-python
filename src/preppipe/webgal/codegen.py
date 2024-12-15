# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from .ast import *
from ..vnmodel import *
from ..util.imagepackexportop import ImagePackExportDataBuilder
from ..util.imagepack import *
from ..util import nameconvert
from ..imageexpr import *
from ..enginecommon.codegen import BackendCodeGenHelperBase

class WebGalImagePackExportDataBuilder(ImagePackExportDataBuilder):
  def _get_image_basedir(self, pack_id : str) -> str:
    descriptor : ImagePackDescriptor = ImagePack.get_descriptor_by_id(pack_id)
    match descriptor.packtype:
      case ImagePackDescriptor.ImagePackType.BACKGROUND:
        return "background"
      case _:
        return "figure"
  def place_imagepack_instance(self, instance_id : str, pack_id : str) -> str:
    # 当我们需要创建图片包实例时，我们应该把图片包放在哪
    # 图片包中的图层将保存在这个目录下，文件名由编号决定。
    # 此类会尝试将不同图片包实例中能共享的部分进行合并，同一图层可能被多个实例引用。
    return os.path.join(self._get_image_basedir(pack_id), pack_id)

  def place_imagepack_composite(self, instance_id : str, pack_id : str, composite_code : str) -> str:
    # 组合的图片应该放在哪
    return os.path.join(self._get_image_basedir(pack_id), 'E' + instance_id + '_' + composite_code + ".png")

@irdataop.IROperationDataclass
class WebGalWaitPseudoNode(WebGalNode):
  # WebGal 的 wait 是默认的，只有上一条指令有 "next" 标记时才不会 wait
  # 我们在第一遍生成时对所有指令添加 next 标记，然后有需要 wait 的地方我们添加该伪指令
  # 后续处理时所有的此指令都会被去掉，前一指令的 next 标记也一并去除
  @staticmethod
  def create(context : Context):
    return WebGalWaitPseudoNode(init_mode=IRObjectInitMode.CONSTRUCT, context=context, loc=None)

@dataclasses.dataclass
class _WebGalFunctionState:
  handle_ids : dict[Value, str] = dataclasses.field(default_factory=dict)
  handle_num : int = 0

class _WebGalCodeGenHelper(BackendCodeGenHelperBase[WebGalNode]):
  result : WebGalModel
  imagepack_handler : WebGalImagePackExportDataBuilder
  cur_ns : VNNamespace

  # 我们给每个 VNFunction 都创建一个单独的文件，同一文件下所有 VNFunction 都使用同一个名称前缀
  function_scenes : dict[VNFunction, str] # VNFunction -> 完整的文件相对路径名，包含后缀(.txt)
  cur_function_state : _WebGalFunctionState | None

  # 如果有指定入口，我们会生成一个 start.txt 来跳转过去
  entry_point : str | None = None


  def __init__(self, model : VNModel) -> None:
    super().__init__(model=model, imagepack_handler=WebGalImagePackExportDataBuilder())
    self.result = None
    self.cur_ns = None
    self.function_scenes = {}
    self.cur_function_state = None

    if not self.is_matchtree_installed():
      self.init_matchtable()

  @staticmethod
  def init_matchtable():
    _WebGalCodeGenHelper.install_codegen_matchtree({
      VNWaitInstruction : {
        VNSayInstructionGroup: _WebGalCodeGenHelper.gen_say_wait,
        None: _WebGalCodeGenHelper.gen_wait,
      },
      VNSayInstructionGroup: _WebGalCodeGenHelper.gen_say_nowait,
      VNSceneSwitchInstructionGroup : _WebGalCodeGenHelper.gen_sceneswitch,
      VNCreateInst : _WebGalCodeGenHelper.gen_create_put,
      VNPutInst : _WebGalCodeGenHelper.gen_create_put,
      VNModifyInst : _WebGalCodeGenHelper.gen_modify,
      VNRemoveInst : _WebGalCodeGenHelper.gen_remove,
      VNCallInst : _WebGalCodeGenHelper.gen_call,
      VNBackendInstructionGroup : _WebGalCodeGenHelper.gen_asm,
    })
    _WebGalCodeGenHelper.install_asset_basedir_matchtree({
      AudioAssetData : {
        VNStandardDeviceKind.O_VOICE_AUDIO :  "vocal",
        VNStandardDeviceKind.O_SE_AUDIO :     "vocal/soundeffect",
        VNStandardDeviceKind.O_BGM_AUDIO :    "bgm",
        None : "vocal/misc",
      },
      ImageAssetData : {
        VNStandardDeviceKind.O_BACKGROUND_DISPLAY : "background",
        VNStandardDeviceKind.O_FOREGROUND_DISPLAY : "figure",
        None: "figure/misc",
      },
      None : "misc",
      # TODO: video: "video"
    })
    _WebGalCodeGenHelper.install_asset_supported_formats({
      ImageAssetData : ["png", "jpeg", "jpg", "apng", "bmp", "webp", "gif"],
      AudioAssetData : ["mp3", "wav", "ogg"],
    })

  def get_result(self) -> WebGalModel:
    return self.result

  def _assign_function_labels(self, n : VNNamespace):
    for f in n.functions:
      srcfile = f.get_attr(VNFunction.ATTR_EXPORT_TO_FILE)
      if srcfile is not None:
        assert isinstance(srcfile, str)
      else:
        srcfile = ''
      srcfile_dir, srcfile_filename = os.path.split(srcfile)
      srcfile, _ = os.path.splitext(srcfile_filename)
      fullname = srcfile_dir + srcfile
      if f.name != srcfile:
        fullname = fullname + "_" + f.name
      self.function_scenes[f] = fullname + ".txt"

  def lower_condition(self, cond : Value, node : WebGalNode):
    raise PPNotImplementedError()

  def emit_condition_as_expr(self, cond : Value) -> str:
    raise PPNotImplementedError()

  def gen_branch(self, branch : VNBranchInst, scene : WebGalScriptFileOp, label_dict : dict[Block, str]) -> WebGalNode:
    defaultBranch : Block = branch.get_default_branch_target()
    insert_before = None
    for i in range(0, branch.get_num_conditional_branch()):
      target, cond = branch.get_conditional_branch_tuple(i)
      target_label = label_dict[target]
      jump = WebGalJumpLabelNode.create(self.context, target_label, loc=branch.location)
      self.lower_condition(cond, jump)
      scene.body.body.push_back(jump)
      if insert_before is None:
        insert_before = jump
    jump = WebGalJumpLabelNode.create(self.context, label_dict[defaultBranch], loc=branch.location)
    scene.body.body.push_back(jump)
    if insert_before is None:
      insert_before = jump
    return insert_before

  def gen_menu(self, menu : VNMenuInst, scene : WebGalScriptFileOp, label_dict : dict[Block, str]) -> WebGalNode:
    choose = WebGalChooseNode.create(self.context, loc=menu.location)
    for i in range(0, menu.get_num_options()):
      text = menu.text_list.get_operand(i)
      cond = menu.condition_list.get_operand(i)
      target = menu.target_list.get_operand(i)
      target_label = label_dict[target]
      if isinstance(cond, BoolLiteral) and cond.value:
        cond = None
      else:
        cond = self.emit_condition_as_expr(cond)
      branch = WebGalChooseBranchNode.create(self.context, text=text, destination=target_label, loc=menu.location)
      if cond is not None:
        if isinstance(cond, str):
          cond = StringLiteral.get(cond, context=self.context)
        branch.condition_show.set_operand(0, cond)
      choose.choices.body.push_back(branch)
    scene.body.body.push_back(choose)
    return choose

  def gen_terminator(self, terminator : VNTerminatorInstBase, **kwargs) -> WebGalNode:
    scene = kwargs['scene']
    label_dict = kwargs['label_dict']
    if isinstance(terminator, VNBranchInst):
      return self.gen_branch(terminator, scene, label_dict)
    elif isinstance(terminator, VNMenuInst):
      return self.gen_menu(terminator, scene, label_dict)
    elif isinstance(terminator, VNReturnInst):
      return_label = label_dict[None]
      return_node = WebGalJumpLabelNode.create(self.context, return_label, loc=terminator.location)
      scene.body.body.push_back(return_node)
      return return_node
    elif isinstance(terminator, VNTailCallInst):
      target_func = terminator.target.get()
      target_scene = self.function_scenes[target_func]
      call_node = WebGalChangeSceneNode.create(self.context, scene=target_scene, loc=terminator.location)
      scene.body.body.push_back(call_node)
      return call_node
    elif isinstance(terminator, VNEndingInst):
      end_node = WebGalEndNode.create(self.context, loc=terminator.location)
      scene.body.body.push_back(end_node)
      return end_node
    raise NotImplementedError()

  # gen_XXX(self, instrs: list[VNInstruction], insert_before: NodeType) -> NodeType
  def get_asset_candidate_common(self, v : Value, user_hint : VNStandardDeviceKind | None = None) -> BackendCodeGenHelperBase.NamedAssetInfo | None:
    kind_filter = self.NamedAssetKind.get_filter_from_user_hint(user_hint) if user_hint is not None else None
    named_assets_list = self.query_asset_name(v, kind=kind_filter)
    if len(named_assets_list) == 0:
      return None
    return named_assets_list[0]

  def strip_asset_rootdir(self, fullrelpath : str) -> str:
    # WebGal 要求素材保存在对应的素材目录中（比如背景在 background/image1.png）
    # 但是引用时需要只提供相对于素材目录的路径 （比如 image1.png）
    # 此函数将第一类路径输入 (background/image1.png) 转化为第二类 (image1.png)
    path_split_results = fullrelpath.replace('\\', '/').split("/")
    if len(path_split_results) < 2 or path_split_results[0] not in (
      "background",
      "bgm",
      "figure",
      "video",
      "vocal",
    ):
      return fullrelpath
    return '/'.join(path_split_results[1:])

  def get_image_expr(self, v : Value, user_hint : VNStandardDeviceKind | None = None) -> str:
    if isinstance(v, VNAssetValueSymbol):
      return self.get_image_expr(v.get_value(), user_hint)
    asset_ref = self.get_asset_candidate_common(v, user_hint)
    if asset_ref is not None and asset_ref.internal_data is not None:
      if not isinstance(asset_ref.internal_data, str):
        raise PPInternalError("Named asset having unexpected internal data type")
      return asset_ref.internal_data

    def wrapup(path : str):
      refpath = self.strip_asset_rootdir(path)
      if asset_ref is not None:
        asset_ref.internal_data = refpath
        asset_ref.used = True
      return refpath

    if isinstance(v, ImageAssetLiteralExpr):
      return wrapup(self.add_assetdata(v.image, user_hint))

    if isinstance(v, AssetData):
      return wrapup(self.add_assetdata(v, user_hint))

    if isinstance(v, ImagePackElementLiteralExpr):
      ref = self.imagepack_handler.add_value(v, True)
      if isinstance(ref, str):
        return wrapup(ref)
      elif isinstance(ref, ImagePackExportDataBuilder.ImagePackElementReferenceInfo):
        raise PPInternalError("WebGal does not support layered image combined ref")
      else:
        raise PPInternalError('Unknown image pack reference type')

    if isinstance(v, PlaceholderImageLiteralExpr):
      return wrapup(self.lower_placeholder_image(v, user_hint))

    if isinstance(v, ColorImageLiteralExpr):
      return wrapup(self.lower_colorimage_image(v, user_hint))

    raise PPInternalError("Unexpected value type")

  def get_audio_expr(self, v : Value, src_dev : VNStandardDeviceKind | None) -> str:
    asset_ref = self.get_asset_candidate_common(v, src_dev)
    if asset_ref is not None and asset_ref.internal_data is not None:
      if not isinstance(asset_ref.internal_data, str):
        raise PPInternalError("Named asset having unexpected internal data type")
      return asset_ref.internal_data
    if isinstance(v, AssetData):
      path = self.add_assetdata(v, src_dev)
      refpath = self.strip_asset_rootdir(path)
      if asset_ref is not None:
        asset_ref.internal_data = refpath
        asset_ref.used = True
      return refpath
    raise PPInternalError("Unexpected value type")

  def get_asset_instance_id(self, v : Value) -> str:
    if self.cur_function_state is None:
      raise PPInternalError("Requesting asset instance id without function state")
    return self.cur_function_state.handle_ids[v]

  def collect_say_text(self, src : OpOperand) -> list[Value]:
    result = []
    for u in src.operanduses():
      v = u.value
      if isinstance(v, (StringLiteral, TextFragmentLiteral)):
        result.append(v)
        continue
      if isinstance(v, VNValueSymbol):
        raise NotImplementedError("Currently not supporting VNValueSymbol codegen")
      raise NotImplementedError("Unexpected value type for text: " + type(v).__name__)
    return result

  def generate_say_impl(self, say : VNSayInstructionGroup, insert_before: WebGalNode, isNoWait : bool = False) -> WebGalNode:
    sayer : str = ''
    contents : list[str] = []
    voice : str | None = None
    voice_volume : int | None = None # 暂不支持
    flag_concat = False
    flag_notend = isNoWait
    is_sayername_specified = False
    mode='adv'
    for op in say.body.body:
      assert isinstance(op, VNInstruction)
      if isinstance(op, VNPutInst):
        # 首先根据设备类型决定
        # 我们暂不支持侧边头像
        dev = op.device.get()
        assert isinstance(dev, VNDeviceSymbol)
        match dev.get_std_device_kind():
          case VNStandardDeviceKind.O_SAY_NAME_TEXT:
            # 我们以后再支持在名称上用变量等内容
            # 现在就假设只有一个 StringLiteral
            # 暂时不支持给旁白加发言名
            assert sayer is not None
            name_data = self.collect_say_text(op.content)
            assert len(name_data) == 1
            sayername = name_data[0]
            sayerstyle = None
            if isinstance(sayername, StringLiteral):
              sayername_str = sayername.get_string()
            elif isinstance(sayername, TextFragmentLiteral):
              sayerstyle = sayername.style
              sayername_str = sayername.get_string()
            else:
              raise RuntimeError("Unexpected sayername type: " + str(type(sayername)))
            is_sayername_specified = True
          case VNStandardDeviceKind.O_SAY_TEXT_TEXT:
            what = self.collect_say_text(op.content)
            for s in what:
              if not isinstance(s, (StringLiteral, TextFragmentLiteral)):
                raise PPInternalError("Unsupported say text type")
              contents.append(s.get_string())
            if parent_dev := dev.get_parent_device():
              match parent_dev.get_std_device_kind():
                case VNStandardDeviceKind.N_SCREEN_SAY_ADV:
                  mode='adv'
                case VNStandardDeviceKind.N_SCREEN_SAY_NVL:
                  mode='nvl'
                case _:
                  pass
          case VNStandardDeviceKind.O_VOICE_AUDIO:
            embed_voice = op.content.get()
            path = self.get_audio_expr(embed_voice, VNStandardDeviceKind.O_VOICE_AUDIO)
            rootdir = self.get_asset_rootpath(embed_voice, VNStandardDeviceKind.O_VOICE_AUDIO)
            relpath = os.path.relpath(path, rootdir)
            voice = relpath
          # 忽略其他不支持的设备
          case _:
            continue
    # 目前我们只支持 adv 模式
    contents_list = [StringLiteral.get(x, context=self.context) for x in contents]
    contents_l = StringListLiteral.get(self.context, contents_list)
    node = WebGalSayNode.create(context=self.context, sayer=sayer, content=contents_l, loc=say.location)
    if voice is not None:
      node.voice.set_operand(0, StringLiteral.get(voice, self.context))
    if flag_concat:
      node.flag_concat.set_operand(0, BoolLiteral.get(True, self.context))
    if flag_notend:
      node.flag_notend.set_operand(0, BoolLiteral.get(True, self.context))
    node.insert_before(insert_before)
    return node

  def gen_say_wait(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    assert len(instrs) == 2
    wait = instrs[0]
    say = instrs[1]
    assert isinstance(say, VNSayInstructionGroup) and isinstance(wait, VNWaitInstruction)
    return self.generate_say_impl(say, insert_before)

  def gen_say_nowait(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    assert len(instrs) == 1
    instr = instrs[0]
    assert isinstance(instr, VNSayInstructionGroup)
    return self.generate_say_impl(instr, insert_before, isNoWait=True)

  def gen_sceneswitch(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    assert len(instrs) == 1
    sceneswitch = instrs[0]
    assert isinstance(sceneswitch, VNSceneSwitchInstructionGroup)
    top_insert_place = None
    for op in sceneswitch.body.body:
      assert isinstance(op, VNInstruction)
      match_result = self.match_codegen_depth1(type(op))
      genresult = match_result(self, [op], insert_before)
      if top_insert_place is None:
        top_insert_place = genresult
    if top_insert_place is None:
      return insert_before
    return top_insert_place

  def gen_create_put(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    # VNCreateInst/VNPutInst
    assert len(instrs) == 1
    instr = instrs[0]
    assert isinstance(instr, VNPlacementInstBase)
    if self.cur_function_state is None:
      raise PPInternalError("Doing codegen for Create/Put without function state")
    content = instr.content.get()
    device : VNDeviceSymbol = instr.device.get()
    # placeat : SymbolTableRegion
    devkind = device.get_std_device_kind()
    if devkind is None:
      # 暂不支持
      return insert_before
    match devkind:
      case VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
        # 放置在前景，用 changeFigure
        image = self.get_image_expr(content, user_hint=devkind)
        changeFigure = WebGalChangeFigureNode.create(context=self.context, figure=image, loc=instr.location)
        # TODO 添加其他信息
        changeFigure.set_flag_next()
        changeFigure.insert_before(insert_before)
        if isinstance(instr, VNCreateInst):
          id_str = "handle_" + str(self.cur_function_state.handle_num)
          self.cur_function_state.handle_num += 1
          self.cur_function_state.handle_ids[instr] = id_str
          changeFigure.id_str.set_operand(0, StringLiteral.get(id_str, context=self.context))
        return changeFigure
      case VNStandardDeviceKind.O_BACKGROUND_DISPLAY:
        # 背景，用 changeBg
        image = self.get_image_expr(content, user_hint=devkind)
        changeBg = WebGalChangeBGNode.create(context=self.context, bg=image, loc=instr.location)
        changeBg.set_flag_next()
        changeBg.insert_before(insert_before)
        return changeBg
      case VNStandardDeviceKind.O_SE_AUDIO:
        # 音效，用 playEffect
        audio = self.get_audio_expr(content, devkind)
        playEffect = WebGalPlayEffectNode.create(context=self.context, effect=audio, loc=instr.location)
        playEffect.set_flag_next()
        playEffect.insert_before(insert_before)
        if isinstance(instr, VNCreateInst):
          id_str = "handle_" + str(self.cur_function_state.handle_num)
          self.cur_function_state.handle_num += 1
          self.cur_function_state.handle_ids[instr] = id_str
          playEffect.id_str.set_operand(0, StringLiteral.get(id_str, context=self.context))
        return playEffect
      case VNStandardDeviceKind.O_BGM_AUDIO:
        # 背景音乐，用 bgm
        audio = self.get_audio_expr(content, devkind)
        node = WebGalBGMNode.create(context=self.context, bgm=audio, loc=instr.location)
        node.set_flag_next()
        node.insert_before(insert_before)
        unlockNode = WebGalUnlockBGMNode.create(context=self.context, bgm=audio, loc=instr.location)
        unlockNode.set_flag_next()
        unlockNode.insert_before(insert_before)
        return node
      case VNStandardDeviceKind.O_SAY_NAME_TEXT | VNStandardDeviceKind.O_SAY_TEXT_TEXT | VNStandardDeviceKind.O_VOICE_AUDIO:
        # 这些都应该在特定的指令组中特殊处理，不应该在这里处理
        raise RuntimeError('Should not happen')
      case _:
        # 暂不支持
        return insert_before

  def gen_modify(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    assert len(instrs) == 1
    instr = instrs[0]
    assert isinstance(instr, VNModifyInst)
    roothandle = self.get_root_handle(instr.handlein.get())
    rootdev = roothandle.device.get()
    if devkind := rootdev.get_std_device_kind():
      match devkind:
        case VNStandardDeviceKind.O_BACKGROUND_DISPLAY:
          newvalue = instr.content.get()
          newexpr = self.get_image_expr(newvalue, devkind)
          newnode = WebGalChangeBGNode.create(context=self.context, bg=newexpr, loc=instr.location)
          newnode.set_flag_next()
          newnode.insert_before(insert_before)
          return newnode
        case VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
          id_str = self.get_asset_instance_id(roothandle)
          newvalue = instr.content.get()
          newexpr = self.get_image_expr(newvalue, devkind)
          newnode = WebGalChangeFigureNode.create(context=self.context, figure=newexpr, loc=instr.location)
          newnode.id_str.set_operand(0, StringLiteral.get(id_str, context=self.context))
          newnode.set_flag_next()
          newnode.insert_before(insert_before)
          #TODO 设置转场和位置
          return newnode
        case _:
          raise NotImplementedError("TODO")
    return insert_before

  def gen_remove(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    assert len(instrs) == 1
    instr = instrs[0]
    assert isinstance(instr, VNRemoveInst)
    roothandle = self.get_root_handle(instr.handlein.get())
    rootdev = roothandle.device.get()
    if kind := rootdev.get_std_device_kind():
      match kind:
        case VNStandardDeviceKind.O_BACKGROUND_DISPLAY | VNStandardDeviceKind.O_FOREGROUND_DISPLAY:
          if kind == VNStandardDeviceKind.O_BACKGROUND_DISPLAY:
            node = WebGalChangeBGNode.create(context=self.context, bg="none", loc=instr.location)
          else:
            image_id = self.get_asset_instance_id(roothandle)
            id_str = StringLiteral.get(image_id, context=self.context)
            node = WebGalChangeFigureNode.create(context=self.context, figure="none", loc=instr.location)
            node.id_str.set_operand(0, id_str)
          node.set_flag_next()
          node.insert_before(insert_before)
          if transition := instr.transition.try_get_value():
            # TODO 暂不支持转场
            pass
          return node
        case VNStandardDeviceKind.O_BGM_AUDIO:
          stop = WebGalBGMNode.create(context=self.context, bgm="none", loc=instr.location)
          stop.set_flag_next()
          stop.insert_before(insert_before)
          return stop
        case VNStandardDeviceKind.O_SE_AUDIO:
          stop = WebGalPlayEffectNode.create(context=self.context, effect="none", loc=instr.location)
          stop.set_flag_next()
          stop.insert_before(insert_before)
          return stop
        case _:
          pass
    # 如果不是标准设备的话暂不支持，直接忽略
    return insert_before

  def gen_call(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    callinst = instrs[0]
    if not isinstance(callinst, VNCallInst):
      raise PPInternalError("Unexpected instruction type")
    target_func = callinst.target.get()
    target_scene = self.function_scenes[target_func]
    call_node = WebGalCallSceneNode.create(self.context, scene=target_scene, loc=callinst.location)
    call_node.insert_before(insert_before)
    return call_node

  def gen_asm(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    if len(instrs) != 1:
      raise PPInternalError("Unexpected number of instructions")
    group = instrs[0]
    if not isinstance(group, VNBackendInstructionGroup):
      raise PPInternalError("Unexpected instruction type")
    firstinstr = None
    for op in group.body.body:
      if isinstance(op, (MetadataOp, WebGalNode)):
        cloned = op.clone()
        cloned.insert_before(insert_before)
        if firstinstr is None and isinstance(op, WebGalNode):
          firstinstr = cloned
    return firstinstr if firstinstr is not None else insert_before

  def gen_wait(self, instrs: list[VNInstruction], insert_before: WebGalNode) -> WebGalNode:
    wait = WebGalWaitPseudoNode.create(self.context)
    wait.insert_before(insert_before)
    return wait

  def _assign_block_labels(self, f : VNFunction) -> dict[Block | None, str]:
    # 为每个基本块分配一个标签，入口除外
    # 由于 WebGal 没有 return 指令，为了实现返回，我们需要给返回指令预留一个标签，放在脚本的最后
    labels = {}
    inverse_dict = {}
    anon_num = 0
    entry_block = f.body.blocks[0]
    for block in f.body.blocks:
      if block is entry_block:
        continue

      if len(block.name) == 0:
        labelname = "anon_" + str(anon_num)
        while labelname in inverse_dict:
          anon_num += 1
          labelname = "anon_" + str(anon_num)
      else:
        labelname = nameconvert.str2identifier(block.name)
        num = 0
        while labelname in inverse_dict:
          labelname = labelname + "_" + str(num)
          num += 1
      labels[block] = labelname
      inverse_dict[labelname] = block
    # 给返回指令预留一个标签
    label_return = "pp_return"
    num = 0
    while label_return in inverse_dict:
      label_return = label_return + "_" + str(num)
      num += 1
    labels[None] = label_return
    return labels

  def _codegen_function(self, f : VNFunction):
    if not f.has_body():
      return
    # WebGal 所有脚本在 scene 目录下，我们直接在这一步加路径前缀
    fullpath = os.path.join("scene", self.function_scenes[f])
    op = WebGalScriptFileOp.create(context=self.context, name=fullpath, loc=f.location)
    self.result.add_script(op)
    label_dict = self._assign_block_labels(f)
    self.cur_function_state = _WebGalFunctionState()

    if entry := f.get_entry_point():
      if entry != 'main':
        raise RuntimeError('Unrecognized entry point')
      if fullpath !=  "scene/start.txt":
        self.entry_point = self.function_scenes[f]

    # 因为 WebGal 的脚本没有明确的基本块的边界，所以我们直接把内容写到一个块内
    for block in f.body.blocks:
      if block is f.body.blocks.front:
        # 入口块不需要标签
        pass
      else:
        block_label = label_dict[block]
        labelnode = WebGalLabelNode.create(context=self.context, label=block_label)
        op.body.push_back(labelnode)
      codegen_kwargs = {"scene": op, "label_dict": label_dict}
      self.codegen_block(block, **codegen_kwargs)

    # 添加返回标签
    return_label = label_dict[None]
    returnnode = WebGalLabelNode.create(context=self.context, label=return_label)
    op.body.push_back(returnnode)

    # 执行后续处理
    self._post_process_pass(op)

    # 然后再把 lost 的内容写到一个块内
    for block in f.lost.blocks:
      match block.name:
        case VNFunction.NAME_PREBODY:
          insert_before = op.body.body.front
          for op in block.body:
            if not isinstance(op, MetadataOp):
              raise ValueError("Unexpected operation in prebody block")
            op.clone().insert_before(insert_before)
        case VNFunction.NAME_POSTBODY:
          for op in block.body:
            if not isinstance(op, MetadataOp):
              raise ValueError("Unexpected operation in postbody block")
            op.body.body.push_back(op.clone())
        case _:
          continue
    self.cur_function_state = None

  def _post_process_pass(self, op : WebGalScriptFileOp):
    # 我们在这里需要做以下转换：
    # 1. 目前 switch scene 会生成连续的 changeBg，前一个将旧的背景去掉，后一个设定新背景。我们在这把前一个给去掉
    # 2. 目前 wait 的实现是使用 WebGalWaitPseudoNode 来标记前一个指令不需要 -next, 我们在这把所有的 WebGalWaitPseudoNode 全部去掉
    if op.body.body.empty:
      raise PPInternalError("Empty script file???")
    curnode : WebGalNode | MetadataOp | None = op.body.body.front
    while curnode is not None:
      if not isinstance(curnode, (WebGalNode, MetadataOp)):
        raise PPInternalError("Unexpected node type: " + str(type(curnode)))
      isDeleteCurNode = False
      # 开始判断
      if isinstance(curnode, WebGalChangeBGNode):
        bg = curnode.bg.try_get_value()
        if bg is not None and bg.get_string() == "none" and curnode.get_flag_next():
          # 这是一个 changeBg:none -next
          # 尝试找到紧挨着的下一个 changeBg，如果有的话就可以去掉这个了
          nextnode = curnode.get_next_node()
          while nextnode is not None:
            if isinstance(nextnode, MetadataOp):
              nextnode = nextnode.get_next_node()
              continue
            if isinstance(nextnode, WebGalChangeBGNode):
              isDeleteCurNode = True
            break
      if isinstance(curnode, WebGalWaitPseudoNode):
        isDeleteCurNode = True
        precedingNode : WebGalNode | None = None
        candidate = curnode.get_prev_node()
        while candidate is not None:
          if isinstance(candidate, MetadataOp):
            candidate = candidate.get_prev_node()
            continue
          if isinstance(candidate, WebGalNode):
            if isinstance(candidate, WebGalLabelNode):
              break
            precedingNode = candidate
            break
        if precedingNode is not None:
          if not isinstance(precedingNode, WebGalNode):
            raise PPInternalError("Unexpected node type: " + str(type(precedingNode)))
          if precedingNode.get_flag_next():
            precedingNode.set_flag_next(False)
      # 收尾
      prevnode = curnode
      curnode = curnode.get_next_node()
      if isDeleteCurNode:
        prevnode.erase_from_parent()

  def run(self) -> WebGalModel:
    # WebGal 暂不支持 DLC，所以我们把所有 VNNamespace 的内容都放一起
    assert self.result is None
    self.result = WebGalModel.create(self.model.context)
    for k in sorted(self.model.namespace.keys()):
      n = self.model.namespace.get(k)
      assert isinstance(n, VNNamespace)
      self.cur_ns = n
      self.collect_named_assets(n)
      self._assign_function_labels(n)
    for k in sorted(self.model.namespace.keys()):
      n = self.model.namespace.get(k)
      assert isinstance(n, VNNamespace)
      self.cur_ns = n
      for f in n.functions:
        self._codegen_function(f)
    if self.entry_point is not None:
      if op := self.result.get_script("scene/start.txt"):
        pass
      start = WebGalScriptFileOp.create(context=self.context, name="scene/start.txt", loc=None)
      self.result.add_script(start)
      start.body.body.push_back(WebGalCallSceneNode.create(self.context, scene=self.entry_point, loc=None))
      start.body.body.push_back(WebGalEndNode.create(context=self.context, loc=None))

    imagepacks = self.imagepack_handler.finalize(self.result._cacheable_export_region) # pylint: disable=protected-access
    return self.result

def codegen_webgal(m : VNModel):
  codegen = _WebGalCodeGenHelper(m)
  return codegen.run()
