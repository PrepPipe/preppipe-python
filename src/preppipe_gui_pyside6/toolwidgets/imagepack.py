import functools
import PIL.ImageQt
from ..toolwidgetinterface import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from preppipe.assets.assetmanager import *
from preppipe.util.imagepack import *
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
  charactersprite_layer_widgets : list[tuple[QCheckBox, QComboBox]] | None = None

  # 方便立绘视图根据启用的图层找差分序号，只在立绘视图中使用
  composites_reverse_dict : dict[tuple[int, ...], int] | None = None
  composite_code_to_index : dict[str, int] | None = None

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
    self.current_index = 0
    self.current_mask_params = None
    self.mask_param_widgets = []
    self.background_radio_buttons = None
    self.charactersprite_layer_widgets = None
    self.composites_reverse_dict = None
    self.composite_code_to_index = None

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
    if len(self.descriptor.masktypes) > 0:
      self.current_mask_params = [None] * len(self.descriptor.masktypes)
      layout = QFormLayout()
      self.ui.forkParamGroupBox.setLayout(layout)
      for index, mask in enumerate(self.descriptor.masktypes):
        nameLabel = QLabel(mask.trname.get())
        self.bind_text(nameLabel.setText, mask.trname)
        inputWidget = MaskInputWidget()
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
          '''pack_id : str # 图片组的 ID
  topref : Translatable | str # 所对应资源的名称
  authortags : tuple[str, ...] # 作者标签，如果有多个作者同时提供了相同名称的素材，可以用这个来区分
  packtype : ImagePackType # 图片组的类型
  masktypes : tuple[MaskType, ...] # 有几个选区、各自的类型
  composites_code : list[str] # 各个差分组合的编号（字母数字组合）
  composites_layers : list[list[int]] # 各个差分组合所用的图层
  composites_references : dict[str, Translatable] # 如果某些差分组合有（非编号的）名称，那么它们的名称存在这里
  layer_info : list[LayerInfo] # 各个图层的信息
  size : tuple[int, int] # 整体大小
  bbox : tuple[int, int, int, int] # 边界框'''
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
          grid_widgets.append((preset_label, preset_combo, apply_button))
          # 图层组部分（需要 charactersprite_gen 元数据）
          if charactersprite_gen := self.pack.opaque_metadata.get("charactersprite_gen", None):
            # 首先，基底部分一定得有
            base_options = charactersprite_gen["bases"]
            _, preset_kind_base_tr = ImagePack.PRESET_YAMLGEN_PARTS_KIND_PRESETS["preset_kind_base"]
            base_checkbox = QCheckBox(preset_kind_base_tr.get())
            base_checkbox.setChecked(True)
            base_checkbox.setEnabled(False)
            self.bind_text(base_checkbox.setText, preset_kind_base_tr)
            base_combo = QComboBox()
            for k, v in base_options.items():
              base_combo.addItem(k, v)
            grid_widgets.append((base_checkbox, base_combo, None))
            # 然后是各种差分
            parts = charactersprite_gen["parts"]
            for kind_enum, kind_tr in ImagePack.PRESET_YAMLGEN_PARTS_KIND_PRESETS.values():
              if kind_enum == ImagePack.CharacterSpritePartsBased_PartKind.BASE:
                continue
              parts_info = parts.get(kind_enum.name, None)
              if parts_info is None:
                continue
              def add_row(kind_tr, parts_list):
                kind_checkbox = QCheckBox(kind_tr.get())
                self.bind_text(kind_checkbox.setText, kind_tr)
                kind_combo = QComboBox()
                for part in parts_list:
                  kind_combo.addItem(part)
                grid_widgets.append((kind_checkbox, kind_combo, None))
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
          self.charactersprite_layer_widgets = []
          # TODO charactersprite_layer_widgets
          self.ui.sourceGroupBox.setLayout(layout)
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
    QMetaObject.invokeMethod(self, "updateCurrentImage", Qt.QueuedConnection)

  @Slot(int)
  def handleMaskParamUpdate(self, index : int):
    if self.current_mask_params is None:
      raise RuntimeError("current_mask_params is None")
    widget = self.mask_param_widgets[index]
    self.current_mask_params[index] = widget.getValue()
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
    QMetaObject.invokeMethod(self, "updateCurrentImage", Qt.QueuedConnection)

  @Slot()
  def updateCurrentPack(self):
    if self.current_mask_params is None or all(param is None for param in self.current_mask_params):
      self.current_pack = self.pack
    else:
      self.current_pack = self.pack.fork_applying_mask(self.current_mask_params, enable_parallelization=True)
    QMetaObject.invokeMethod(self, "updateCurrentImage", Qt.QueuedConnection)

  @Slot()
  def updateCurrentImage(self):
    if isinstance(self.current_index, list):
      img = self.current_pack.get_composed_image_lower(self.current_index)
    else:
      img = self.current_pack.get_composed_image(self.current_index)
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
    self.viewer.fit_to_view()

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
