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
  current_index : int | list[int] | None = None
  current_mask_params : list[typing.Any] | None = None
  mask_param_widgets : list[MaskInputWidget]

  def __init__(self, parent: QWidget):
    super(ImagePackWidget, self).__init__(parent)
    self.ui = Ui_ImagePackWidget()
    self.ui.setupUi(self)
    self.viewer = ImageViewerWidget(self, context_menu_callback=self.populate_image_rightclick_menu)
    self.ui.viewerLayout.addWidget(self.viewer)
    self.current_index = None
    self.current_mask_params = None
    self.mask_param_widgets = []

  _tr_no_mask = TR_gui_tool_imagepack.tr("no_mask",
    en="This image pack contains no customizable mask regions.",
    zh_cn="该图片包没有可修改的选区。",
    zh_hk="該圖片包沒有可修改的選區。",
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
        inputWidget.valueChanged.connect(functools.partial(self.handleMaskParamUpdate, index), Qt.QueuedConnection)
    else:
      layout = QVBoxLayout()
      label = QLabel(self._tr_no_mask.get())
      self.bind_text(label.setText, self._tr_no_mask)
      label.setWordWrap(True)
      layout.addWidget(label)
      self.ui.forkParamGroupBox.setLayout(layout)
    # setData() 需要尽快返回，让组件先显示出来，后续再更新内容
    QMetaObject.invokeMethod(self, "updateCurrentImage", Qt.QueuedConnection)

  @Slot(int)
  def handleMaskParamUpdate(self, index : int):
    if self.current_mask_params is None:
      raise RuntimeError("current_mask_params is None")
    widget = self.mask_param_widgets[index]
    self.current_mask_params[index] = widget.getValue()
    self.updateCurrentPack()

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
      index = self.current_index if self.current_index is not None else 0
      img = self.current_pack.get_composed_image(index)
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

  def populate_image_rightclick_menu(self, menu: QMenu):
    # TODO
    custom_action = menu.addAction("Custom Operation")
    custom_action.triggered.connect(lambda: print("Custom operation executed."))