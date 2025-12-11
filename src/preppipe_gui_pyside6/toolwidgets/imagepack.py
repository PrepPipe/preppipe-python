import functools
import PIL.ImageQt
from ..toolwidgetinterface import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from preppipe.assets.assetmanager import *
from preppipe.util.imagepack import *
from preppipe.frontend.vnmodel import vnutil,vnparser
from ..forms.generated.ui_imagepackwidget import Ui_ImagePackWidget
from ..componentwidgets.imageviewerwidget import ImageViewerWidget
from ..componentwidgets.maskinputwidget import MaskInputWidget
from ..util.wait import WaitDialog

TR_gui_tool_imagepack = TranslationDomain("gui_tool_imagepack")

class ImagePackWidget(QWidget, ToolWidgetInterface):
  @classmethod
  def getToolInfo(cls, packid : str | None = None, category_kind : ImagePackDescriptor.ImagePackType | None = None) -> ToolWidgetInfo:
    if packid is None and category_kind is None:
      raise ValueError("At least one of packid and category_kind must be specified")
    if packid is not None and category_kind is not None:
      raise ValueError("Only one of packid and category_kind can be specified")
    if packid is None:
      match category_kind:
        case ImagePackDescriptor.ImagePackType.BACKGROUND:
          return ToolWidgetInfo(
            idstr="imagepack",
            name = ImagePackDocsDumper.tr_heading_background,
            data = {"category_kind": category_kind},
          )
        case ImagePackDescriptor.ImagePackType.CHARACTER:
          return ToolWidgetInfo(
            idstr="imagepack",
            name = ImagePackDocsDumper.tr_heading_charactersprite,
            data = {"category_kind": category_kind},
          )
        case _:
          raise NotImplementedError(f"Category kind {category_kind} is not supported")
    descriptor = ImagePack.get_descriptor_by_id(packid)
    if not isinstance(descriptor, ImagePackDescriptor):
      raise PPInternalError(f"Unexpected descriptor type {type(descriptor)}")
    return ToolWidgetInfo(
      idstr="imagepack",
      name = descriptor.topref,
      data={"packid": packid},
      widget=cls,
    )

  @classmethod
  def getChildTools(cls, packid : str | None = None, category_kind : ImagePackDescriptor.ImagePackType | None = None) -> list[type[ToolWidgetInterface] | ToolWidgetInfo] | None:
    if packid is not None:
      return None
    result = []
    for descriptor in ImagePack.MANIFEST.values():
      if not isinstance(descriptor, ImagePackDescriptor):
        raise PPInternalError(f"Unexpected descriptor type {type(descriptor)}")
      if descriptor.packtype != category_kind:
        continue
      result.append((ImagePackWidget, {"packid": descriptor.pack_id}))
    return result

  ui : Ui_ImagePackWidget
  viewer : ImageViewerWidget

  # 在 setData() 中初始化
  pack : ImagePack
  descriptor : ImagePackDescriptor
  # 如果有加选区参数，那么这里就是修改后的图片包，否则就是原来的
  current_pack : ImagePack

  # 当前的组合、选区参数
  current_index : int | list[int]
  current_mask_params : list[typing.Any] | None = None
  mask_param_widgets : list[MaskInputWidget]
  background_radio_buttons : list[QRadioButton] | None = None
  charactersprite_layer_preset_combobox : QComboBox | None = None
  charactersprite_layer_base_combobox : QComboBox | None = None
  charactersprite_layer_widgets : list[tuple[QCheckBox, QComboBox]] | None = None
  charactersprite_layer_group_dict : dict[str, int] | None = None # 当我们需要启用某个图层时，我们应该在哪个图层选项中找到这个

  # 方便立绘视图根据启用的图层找差分序号，只在立绘视图中使用
  composites_reverse_dict : dict[tuple[int, ...], int] | None = None
  composite_code_to_index : dict[str, int] | None = None

  # 用于在用代码修改角色立绘图层视图时避免更改当前图层
  charactersprite_is_programmatically_changing : bool

  # 虽然目前只有立绘视图使用但是我们都会提供
  layer_code_to_index : dict[str, int]

  # 用于加速立绘视图
  composition_cache : dict[int, ImageCompositionCache]
  # 第一个不是基底的图层的下标
  # 切换基底时，我们只需保存到比这个值小的最大的图层的缓存
  composition_cache_min_volatile_layer : int
  # 每组基底的 ImageCompositionCache.min_cached_layer
  composition_cache_min_cached_layers : dict[int, int]

  _tr_composition_selection = TR_gui_tool_imagepack.tr("composition_selection",
    en="Composition Selection",
    zh_cn="差分选择",
    zh_hk="差分選擇",
  )
  _tr_mask_parameters = TR_gui_tool_imagepack.tr("mask_parameters",
    en="Customization Parameters",
    zh_cn="选区修改参数",
    zh_hk="選區修改參數",
  )

  def __init__(self, parent: QWidget):
    super(ImagePackWidget, self).__init__(parent)
    self.ui = Ui_ImagePackWidget()
    self.ui.setupUi(self)
    self.viewer = ImageViewerWidget(self, context_menu_callback=self.populate_image_rightclick_menu)
    self.ui.viewerLayout.addWidget(self.viewer)
    self.bind_text(self.ui.sourceGroupBox.setTitle, self._tr_composition_selection)
    self.bind_text(self.ui.forkParamGroupBox.setTitle, self._tr_mask_parameters)
    self.ui.infoLabel.setText('') # 在详细信息功能完成前先隐藏该标签
    self.current_index = 0
    self.current_mask_params = None
    self.mask_param_widgets = []
    self.background_radio_buttons = None
    self.charactersprite_layer_preset_combobox = None
    self.charactersprite_layer_base_combobox = None
    self.charactersprite_layer_widgets = None
    self.charactersprite_layer_group_dict = None
    self.charactersprite_is_programmatically_changing = False
    self.composites_reverse_dict = None
    self.composite_code_to_index = None
    self.layer_code_to_index = {}
    self.composition_cache = {}
    self.composition_cache_min_volatile_layer = 0
    self.composition_cache_min_cached_layers = {}

  _tr_no_mask = TR_gui_tool_imagepack.tr("no_mask",
    en="This image pack contains no customizable regions.",
    zh_cn="该图片包没有可修改的选区。",
    zh_hk="該圖片包沒有可修改的選區。",
  )
  _tr_no_composite = TR_gui_tool_imagepack.tr("no_composite",
    en="This image pack contains no compositions.",
    zh_cn="该图片包没有差分组合。",
    zh_hk="該圖片包沒有差分組合。",
  )
  _tr_no_description = TR_gui_tool_imagepack.tr("no_description",
    en="This image pack contains no description.",
    zh_cn="该图片包没有描述。",
    zh_hk="該圖片包沒有描述。",
  )
  _tr_preset_label = TR_gui_tool_imagepack.tr("preset_label",
    en="Preset",
    zh_cn="预设",
    zh_hk="預設",
  )
  _tr_no_preset_prompt = TR_gui_tool_imagepack.tr("no_preset_prompt",
    en="(None)",
    zh_cn="（无预设）",
    zh_hk="（無預設）",
  )
  _tr_apply = TR_gui_tool_imagepack.tr("apply",
    en="Apply",
    zh_cn="应用",
    zh_hk="應用",
  )
  _tr_bracket_round = TR_gui_tool_imagepack.tr("bracket_round",
    en="({value})",
    zh_cn="（{value}）",
    zh_hk="（{value}）",
  )
  _tr_bracket_square = TR_gui_tool_imagepack.tr("bracket_square",
    en="[{value}]",
    zh_cn="【{value}】",
    zh_hk="【{value}】",
  )
  _tr_using_in_script = TR_gui_tool_imagepack.tr("using_in_script",
    en="Using in Script:",
    zh_cn="在剧本中使用：",
    zh_hk="在剧本中使用：",
  )
  _tr_colon = TR_gui_tool_imagepack.tr("colon",
    en=": ",
    zh_cn="：",
    zh_hk="：",
  )
  _tr_comma = TR_gui_tool_imagepack.tr("comma",
    en=", ",
    zh_cn="，",
    zh_hk="，",
  )
  _tr_place_1 = TR_gui_tool_imagepack.tr("place_1",
    en="Place1",
    zh_cn="地点1",
    zh_hk="地點1",
  )
  _tr_character_1 = TR_gui_tool_imagepack.tr("character_1",
    en="Character1",
    zh_cn="角色1",
    zh_hk="角色1",
  )

  def _get_current_composite_name(self) -> str:
    ref=self.descriptor.composites_references
    if isinstance(self.current_index, list):
      layers=self.pack.layers
      layer_codes = []
      for layer_index in self.current_index:
        layer = layers[layer_index]
        layer_codes.append(ImagePackDescriptor.get_layer_code(layer.basename))

      # 检查是否有预定义的基底组合缩写（如 B0=L1L2...）
      if charactersprite_gen := self.pack.opaque_metadata.get("charactersprite_gen", None):
        base_options = charactersprite_gen["bases"]
        # 尝试匹配基底组合，选择最完全匹配的（包含最多图层的）
        best_base_abbr = None
        best_base_codes = []
        for base_abbr, base_layer_codes in base_options.items():
          if set(base_layer_codes).issubset(set(layer_codes)):
            # 如果当前基底组合比之前找到的更完全（包含更多图层），则更新最佳匹配
            if len(base_layer_codes) > len(best_base_codes):
              best_base_abbr = base_abbr
              best_base_codes = base_layer_codes

        if best_base_abbr:
          # 使用最完全匹配的基底组合
          remaining_codes = [code for code in layer_codes if code not in best_base_codes]
          return best_base_abbr + ''.join(remaining_codes)

      # 如果没有匹配的基底组合，直接返回所有图层代码的拼接
      return ''.join(layer_codes)
    composite_code = self.descriptor.composites_code[self.current_index]
    if composite_code in ref:
      return ref[composite_code].get()
    return composite_code

  def _get_place_1_composition(self,composition_text:str) -> str:
    return f"{self._tr_place_1.get()}{self._tr_bracket_round.get().format(value=composition_text)}"

  def _build_modify_string(self, base_name: str) -> str:
    preset_params = [base_name]
    if self.current_mask_params:
      for mask_type, mask_value in zip(self.descriptor.get_masks(), self.current_mask_params):
        mask_name = mask_type.trname.get().lower()
        if isinstance(mask_value, Color):
          color_hex = mask_value.get_string()
          preset_params.append(f"{mask_name}={color_hex}")
    return f"{vnutil._tr_imagepreset.get()}{self._tr_bracket_round.get().format(value=self._tr_comma.get().join(preset_params))}"

  def _update_description(self):
    desc=self.descriptor.description
    desc_list:list[str]=[]
    match self.descriptor.packtype:
      case ImagePackDescriptor.ImagePackType.CHARACTER:
        '''角色描述格式（无差分不显示composite)：
        name(composite_name) (#composite_index)

        description

        using_in_script
        【decl:ch1】
          * character:preset(name)
        【character_enter:ch1】
        '''
        base_name=self.descriptor.topref.get()
        name,ch1=base_name,self._tr_character_1.get()
        if len(self.descriptor.composites_code):
          name=f"{base_name}{self._tr_bracket_round.get().format(value=self._get_current_composite_name())}"
          # 只有当current_index是预设组合时才显示索引
          if isinstance(self.current_index, int):
            name=f"{name} {self._tr_bracket_round.get().format(value=f'#{self.current_index}')}"
        decl=f"{vnparser.cmd_character_decl.CMD_INFO.name_tr.get()}{self._tr_colon.get()}{ch1}"
        preset=f"{vnparser._tr_chdecl_sprite.get()}{self._tr_colon.get()}{self._build_modify_string(base_name)}"
        action=f"{vnparser.cmd_character_entry.CMD_INFO.name_tr.get()}{self._tr_colon.get()}{ch1}"

        desc_list.append(name)
        desc_list.append('')
        desc_list.append(desc.get() if desc else self._tr_no_description.get())
        desc_list.append('')
        desc_list.append(self._tr_using_in_script.get())
        desc_list.append(self._tr_bracket_square.get().format(value=decl))
        desc_list.append(f"  * {preset}")
        desc_list.append(self._tr_bracket_square.get().format(value=action))
      case ImagePackDescriptor.ImagePackType.BACKGROUND:
        '''背景描述格式（无差分不显示composite)：
        name(composite_name) (#composite_index)

        description

        using_in_script
        【decl:scene1】
          * background:preset(name)
        【switch_scene:scene1(composite_name)】
        '''
        name=self.descriptor.topref.get()
        base_name=name
        composition=''
        if len(self.descriptor.composites_code):
          composition=self._get_current_composite_name()
          name=f"{base_name}{self._tr_bracket_round.get().format(value=composition)}"
          name=f"{name} {self._tr_bracket_round.get().format(value=f'#{self.current_index}')}"
        decl=f"{vnparser.cmd_scene_decl.CMD_INFO.name_tr.get()}{self._tr_colon.get()}{self._tr_place_1.get()}"
        preset=f"{vnparser._tr_scenedecl_background.get()}{self._tr_colon.get()}{self._build_modify_string(base_name)}"
        action=f"{vnparser.cmd_switch_scene.CMD_INFO.name_tr.get()}{self._tr_colon.get()}{self._get_place_1_composition(composition)}"

        desc_list.append(name)
        desc_list.append('')
        desc_list.append(desc.get() if desc else self._tr_no_description.get())
        desc_list.append('')
        desc_list.append(self._tr_using_in_script.get())
        desc_list.append(self._tr_bracket_square.get().format(value=decl))
        desc_list.append(f"  * {preset}")
        desc_list.append(self._tr_bracket_square.get().format(value=action))

    self.ui.infoLabel.setText('\n'.join(desc_list))

  def setData(self, packid : str | None = None, category_kind : ImagePackDescriptor.ImagePackType | None = None):
    if category_kind is not None:
      raise ValueError("Can only view individual image packs, not categories")
    if packid is None:
      raise ValueError("packid must be specified")
    pack = AssetManager.get_instance().get_asset(packid)
    if not isinstance(pack, ImagePack):
      raise PPInternalError(f"Unexpected pack type {type(pack)}")
    self.pack = pack
    self.descriptor = ImagePack.get_descriptor_by_id(packid)
    if not isinstance(self.descriptor, ImagePackDescriptor):
      raise PPInternalError(f"Unexpected descriptor type {type(self.descriptor)}")
    self.current_pack = pack
    for index, layer in enumerate(self.pack.layers):
      self.layer_code_to_index[ImagePackDescriptor.get_layer_code(layer.basename)] = index
    if len(self.descriptor.masktypes) > 0:
      self.current_mask_params = [None] * len(self.descriptor.masktypes)
      layout = QFormLayout()
      self.ui.forkParamGroupBox.setLayout(layout)
      for index, (mask, trname) in enumerate(self.descriptor.get_mask_details()):
        nameLabel = QLabel(trname.get())
        self.bind_text(nameLabel.setText, trname)
        inputWidget = MaskInputWidget()
        inputWidget.setDefaultColor(self.pack.masks[index].mask_color)
        match mask.get_param_type():
          case ImagePackDescriptor.MaskParamType.IMAGE:
            inputWidget.setIsColorOnly(False)
          case ImagePackDescriptor.MaskParamType.COLOR:
            inputWidget.setIsColorOnly(True)
          case _:
            raise NotImplementedError(f"Mask param type {mask.get_param_type()} is not supported")
        layout.addRow(nameLabel, inputWidget)
        self.add_translatable_widget_child(inputWidget)
        self.mask_param_widgets.append(inputWidget)
        inputWidget.valueChanged.connect(functools.partial(self.handleMaskParamUpdate, index))
    else:
      layout = QVBoxLayout()
      label = QLabel(self._tr_no_mask.get())
      self.bind_text(label.setText, self._tr_no_mask)
      label.setWordWrap(True)
      layout.addWidget(label)
      self.ui.forkParamGroupBox.setLayout(layout)
    if len(self.descriptor.composites_code) > 0:
      match self.descriptor.packtype:
        case ImagePackDescriptor.ImagePackType.BACKGROUND:
          layout = QVBoxLayout()
          self.background_radio_buttons = []
          for index, code in enumerate(self.descriptor.composites_code):
            radio_button = QRadioButton(code)
            if name := self.descriptor.composites_references.get(code, None):
              self.bind_text(radio_button.setText, name)
            self.background_radio_buttons.append(radio_button)
            if index == 0:
              radio_button.setChecked(True)
            radio_button.toggled.connect(self.handleBackgroundCompositionChange)
            layout.addWidget(radio_button)
          self.ui.sourceGroupBox.setLayout(layout)
        case ImagePackDescriptor.ImagePackType.CHARACTER:
          self.composites_reverse_dict = {}
          self.composite_code_to_index = {}
          for index, (layers, code) in enumerate(zip(self.descriptor.composites_layers, self.descriptor.composites_code)):
            self.composites_reverse_dict[tuple(layers)] = index
            self.composite_code_to_index[code] = index
          # 立绘视图的差分选择有两部分，第一部分是预设，单行，第二部分是基于图层组的差分自选，有多少图层组就有多少行
          # 第一部分分三列（预设的标签，下拉菜单选择预设，再加“应用”按钮），第二部分分两列（左边是复选框，右边是下拉菜单）
          # 我们统一使用 QGridLayout
          grid_widgets = []
          # 预设部分
          preset_label = QLabel(self._tr_preset_label.get())
          self.bind_text(preset_label.setText, self._tr_preset_label)
          preset_combo = QComboBox()
          apply_button = QPushButton(self._tr_apply.get())
          self.bind_text(apply_button.setText, self._tr_apply)
          if len(self.descriptor.composites_references) == 0:
            preset_combo.addItem(self._tr_no_preset_prompt.get())
            preset_combo.setEnabled(False)
            apply_button.setEnabled(False)
          else:
            for code, name in self.descriptor.composites_references.items():
              preset_combo.addItem(name.get(), code)
            apply_button.clicked.connect(self.handleCharacterCompositionChange_Preset)
          grid_widgets.append((preset_label, preset_combo, apply_button))
          self.charactersprite_layer_preset_combobox = preset_combo
          self.charactersprite_layer_widgets = []
          self.charactersprite_layer_group_dict = {}
          # 图层组部分（需要 charactersprite_gen 元数据）
          if charactersprite_gen := self.pack.opaque_metadata.get("charactersprite_gen", None):
            # 首先，基底部分一定得有
            base_options = charactersprite_gen["bases"]
            _, preset_kind_base_tr = ImagePack.PRESET_YAMLGEN_PARTS_KIND_PRESETS["preset_kind_base"]
            base_checkbox = QCheckBox(preset_kind_base_tr.get())
            base_checkbox.setChecked(True)
            base_checkbox.setEnabled(False)
            self.bind_text(base_checkbox.setText, preset_kind_base_tr)
            base_layers = set()
            base_combo = QComboBox()
            for k, v in base_options.items():
              base_combo.addItem(k, v)
              for layer in v:
                base_layers.add(layer)
            grid_widgets.append((base_checkbox, base_combo, None))
            self.charactersprite_layer_base_combobox = base_combo
            base_combo.currentIndexChanged.connect(self.handleCharacterCompositionChange_ByLayer)
            for layerindex in range(len(self.pack.layers)):
              layercode = ImagePackDescriptor.get_layer_code(self.pack.layers[layerindex].basename)
              if layercode not in base_layers:
                # 找到了第一个不属于基底的图层
                self.composition_cache_min_volatile_layer = layerindex
                # 我们需要找到每组基底中在该图层之下的最上层，缓存从这一层开始
                for base_index, data in enumerate(base_options.values()):
                  cur_min_cached_layer = 0
                  for layercode in data:
                    layerindex = self.layer_code_to_index[layercode]
                    if layerindex < self.composition_cache_min_volatile_layer and layerindex > cur_min_cached_layer:
                      cur_min_cached_layer = layerindex
                  self.composition_cache_min_cached_layers[base_index] = cur_min_cached_layer
                break
            # 然后是各种差分
            parts = charactersprite_gen["parts"]
            for kind_enum, kind_tr in ImagePack.PRESET_YAMLGEN_PARTS_KIND_PRESETS.values():
              if kind_enum == ImagePack.CharacterSpritePartsBased_PartKind.BASE:
                continue
              parts_info = parts.get(kind_enum.name, None)
              if parts_info is None:
                continue
              def add_row(kind_tr, parts_list):
                if self.charactersprite_layer_widgets is None or self.charactersprite_layer_group_dict is None:
                  raise RuntimeError("data uninitialized")
                row_index = len(self.charactersprite_layer_widgets)
                kind_checkbox = QCheckBox(kind_tr.get())
                self.bind_text(kind_checkbox.setText, kind_tr)
                kind_combo = QComboBox()
                for part in parts_list:
                  kind_combo.addItem(part)
                  self.charactersprite_layer_group_dict[part] = row_index
                grid_widgets.append((kind_checkbox, kind_combo, None))
                self.charactersprite_layer_widgets.append((kind_checkbox, kind_combo))
                kind_checkbox.toggled.connect(self.handleCharacterCompositionChange_ByLayer)
                kind_combo.currentIndexChanged.connect(self.handleCharacterCompositionChange_ByLayer)
              if kind_enum == ImagePack.CharacterSpritePartsBased_PartKind.DECORATION:
                # 该类型下每个子类都可独立选择
                for subkind_name, subkind_list in parts_info.items():
                  add_row(kind_tr, subkind_list)
              else:
                # 将所有子类别的选项合并
                all_parts = []
                for subkind_list in parts_info.values():
                  all_parts.extend(subkind_list)
                add_row(kind_tr, all_parts)
          layout = QGridLayout()
          for row, widgets in enumerate(grid_widgets):
            for col, widget in enumerate(widgets):
              if widget is None:
                continue
              layout.addWidget(widget, row, col)
          self.ui.sourceGroupBox.setLayout(layout)
          self.updateCharacterCompositionPanelFromCurrentIndex()
        case _:
          raise NotImplementedError(f"Pack type {self.descriptor.packtype} is not supported")
    else:
      layout = QVBoxLayout()
      label = QLabel(self._tr_no_composite.get())
      self.bind_text(label.setText, self._tr_no_composite)
      label.setWordWrap(True)
      layout.addWidget(label)
      self.ui.sourceGroupBox.setLayout(layout)
    # setData() 需要尽快返回，让组件先显示出来，后续再更新内容
    QMetaObject.invokeMethod(self, "finalize_init", Qt.QueuedConnection)
    self._update_description()

  @Slot()
  def finalize_init(self):
    self.updateCurrentImage()
    self.viewer.fit_to_view()

  def charactersprite_update_layer_preset_combobox_text(self):
    if self.charactersprite_layer_preset_combobox:
      if len(self.descriptor.composites_references) == 0:
        self.charactersprite_layer_preset_combobox.clear()
        self.charactersprite_layer_preset_combobox.addItem(self._tr_no_preset_prompt.get())
      else:
        current_index = self.charactersprite_layer_preset_combobox.currentIndex()
        self.charactersprite_layer_preset_combobox.clear()
        for code, name in self.descriptor.composites_references.items():
          self.charactersprite_layer_preset_combobox.addItem(name.get(), code)
        if current_index >= 0 and current_index < len(self.descriptor.composites_references):
          self.charactersprite_layer_preset_combobox.setCurrentIndex(current_index)

  def update_text(self):
    super().update_text()
    self._update_description()
    self.charactersprite_update_layer_preset_combobox_text()

  @Slot(int)
  def handleMaskParamUpdate(self, index : int):
    if self.current_mask_params is None:
      raise RuntimeError("current_mask_params is None")
    widget = self.mask_param_widgets[index]
    self.current_mask_params[index] = widget.getValue()
    self._update_description()
    WaitDialog.long_running_operation_start()
    QMetaObject.invokeMethod(self, "updateCurrentPack", Qt.QueuedConnection)

  @Slot()
  def handleBackgroundCompositionChange(self):
    if self.background_radio_buttons is None:
      raise RuntimeError("background_radio_buttons is None")
    new_index = 0
    for index, button in enumerate(self.background_radio_buttons):
      if button.isChecked():
        new_index = index
        break
    if self.current_index == new_index:
      return
    self.current_index = new_index
    self._update_description()
    QMetaObject.invokeMethod(self, "updateCurrentImage", Qt.QueuedConnection)

  def updateCharacterCompositionPanelFromCurrentIndex(self):
    if self.charactersprite_layer_widgets is None or self.charactersprite_layer_group_dict is None:
      raise RuntimeError("data uninitialized")
    current_layers = None
    if isinstance(self.current_index, list):
      current_layers = self.current_index
    else:
      current_layers = self.pack.composites[self.current_index if self.current_index is not None else 0].layers

    # 非基底图层的选项得在 self.charactersprite_layer_widgets 中修改，基底图层的选项在 self.charactersprite_layer_base_combobox 中
    # 我们先把 current_layers_set 中所有的非基底图层选项处理好，剩下的部分一定都是基底图层
    # 我们再在之后找个完全匹配的基底图层项
    dest_layer_widget_states = [(False, '')] * len(self.charactersprite_layer_widgets) # <是否启用，启用哪个图层>的列表
    base_layers = set()
    for layer_index in current_layers:
      codename = ImagePackDescriptor.get_layer_code(self.pack.layers[layer_index].basename)
      group_index = self.charactersprite_layer_group_dict.get(codename, None)
      if group_index is not None:
        dest_layer_widget_states[group_index] = (True, codename)
      else:
        base_layers.add(codename)

    # 开始决定哪些图层需要启用，先关掉 handleCharacterCompositionChange_ByLayer()
    self.charactersprite_is_programmatically_changing = True

    # 决定基底项应该用哪个
    if self.charactersprite_layer_base_combobox is not None:
      base_index = None
      for i in range(self.charactersprite_layer_base_combobox.count()):
        option_enabled_layers = self.charactersprite_layer_base_combobox.itemData(i, Qt.UserRole)
        if len(option_enabled_layers) == len(base_layers) and all(layer in option_enabled_layers for layer in base_layers):
          base_index = i
          break
      if base_index is not None:
        self.charactersprite_layer_base_combobox.setCurrentIndex(base_index)

    for groupindex, (checkbox, combobox) in enumerate(self.charactersprite_layer_widgets):
      if groupindex >= len(dest_layer_widget_states):
        raise RuntimeError("dest_layer_widget_states is too short")
      enabled, layername = dest_layer_widget_states[groupindex]
      checkbox.setChecked(enabled)
      if enabled:
        index = combobox.findText(layername)
        if index < 0:
          raise RuntimeError(f"Layer {layername} not found in combobox")
        combobox.setCurrentIndex(index)

    # 结束时恢复 handleCharacterCompositionChange_ByLayer()
    self.charactersprite_is_programmatically_changing = False

  @Slot()
  def handleCharacterCompositionChange_Preset(self):
    if self.charactersprite_layer_preset_combobox is None or self.composite_code_to_index is None:
      raise RuntimeError("charactersprite data incomplete")
    code = self.charactersprite_layer_preset_combobox.currentData()
    if code is not None:
      new_index = self.composite_code_to_index.get(code, 0)
      self.updateCharacterCompositionPanelFromCurrentIndex()
      if self.current_index != new_index:
        self.current_index = new_index
        self._update_description()
        QMetaObject.invokeMethod(self, "updateCurrentImage", Qt.QueuedConnection)

  @Slot()
  def handleCharacterCompositionChange_ByLayer(self):
    if self.charactersprite_is_programmatically_changing:
      return
    if self.charactersprite_layer_widgets is None or self.charactersprite_layer_group_dict is None or self.charactersprite_layer_base_combobox is None:
      raise RuntimeError("data uninitialized")
    base_layers = self.charactersprite_layer_base_combobox.currentData()
    current_layers = [self.layer_code_to_index[code] for code in base_layers]
    for checkbox, combobox in self.charactersprite_layer_widgets:
      if checkbox.isChecked():
        layername = combobox.currentText()
        current_layers.append(self.layer_code_to_index[layername])
    current_layers.sort()
    current_index = self.composites_reverse_dict.get(tuple(current_layers), None)
    new_index = current_index if current_index is not None else current_layers
    if self.current_index != new_index:
      self.current_index = new_index
      self._update_description()
      QMetaObject.invokeMethod(self, "updateCurrentImage", Qt.QueuedConnection)

  @Slot()
  def updateCurrentPack(self):
    if self.current_mask_params is None or all(param is None for param in self.current_mask_params):
      self.current_pack = self.pack
    else:
      self.current_pack = self.pack.fork_applying_mask(self.current_mask_params, enable_parallelization=True)
    self.composition_cache.clear()
    QMetaObject.invokeMethod(self, "updateCurrentImage", Qt.QueuedConnection)

  @Slot()
  def updateCurrentImage(self):
    composition_cache = None
    if self.charactersprite_layer_base_combobox is not None:
      base_index = self.charactersprite_layer_base_combobox.currentIndex()
      composition_cache = self.composition_cache.get(base_index, None)
      if composition_cache is None:
        composition_cache = ImageCompositionCache(min_cached_layer=self.composition_cache_min_cached_layers.get(base_index, 0))
        self.composition_cache[base_index] = composition_cache
    if isinstance(self.current_index, list):
      img = self.current_pack.get_composed_image_lower(self.current_index, composition_cache=composition_cache)
    else:
      img = self.current_pack.get_composed_image(self.current_index, composition_cache=composition_cache)
    self.set_image(img)

  def set_image(self, image: PIL.Image.Image | ImageWrapper):
    if isinstance(image, ImageWrapper):
      if path := image.path:
        pixmap = QPixmap.fromImage(QImage(path))
      else:
        pixmap = QPixmap.fromImage(PIL.ImageQt.ImageQt(image.get()))
    else:
      pixmap = QPixmap.fromImage(PIL.ImageQt.ImageQt(image))
    self.viewer.setImage(pixmap)

  _tr_save_overview_image = TR_gui_tool_imagepack.tr("save_overview_image",
    en="Save Overview Image",
    zh_cn="保存概览图",
    zh_hk="保存概覽圖",
  )
  @Slot()
  def requestSaveOverviewImage(self):
    if self.current_pack is None:
      return
    if file_path := self.viewer.get_png_save_path(self._tr_save_overview_image.get()):
      self.current_pack.write_overview_image(file_path, self.descriptor, None)
  def populate_image_rightclick_menu(self, menu: QMenu):
    menu.addSeparator()
    action_save_overview_image = menu.addAction(self._tr_save_overview_image.get())
    action_save_overview_image.triggered.connect(self.requestSaveOverviewImage)
    if self.current_pack is None:
      action_save_overview_image.setEnabled(False)
