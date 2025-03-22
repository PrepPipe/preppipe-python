import sys
from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *
import PIL
import PIL.Image
from preppipe.language import *
from preppipe.commontypes import Color
from ..translatablewidgetinterface import TranslatableWidgetInterface

TR_gui_maskinputwidget = TranslationDomain("gui_maskinputwidget")

# ---------------------------------------------------------------
# TextWithColorInputDialog class (adapted from the C++ version)
# ---------------------------------------------------------------
class TextWithColorInputDialog(QDialog, TranslatableWidgetInterface):
  _tr_text_input_placeholder = TR_gui_maskinputwidget.tr("text_input_placeholder",
    en="Please input text here",
    zh_cn="请输入文本内容",
    zh_hk="請輸入文本內容",
  )
  _tr_set_color = TR_gui_maskinputwidget.tr("set_color",
    en="Set Color",
    zh_cn="设置颜色",
    zh_hk="設置顏色",
  )
  _tr_textwithcolor_dialog_title_self = TR_gui_maskinputwidget.tr("textwithcolor_dialog_title_self",
    en="Please input text and color",
    zh_cn="请输入文本与颜色",
    zh_hk="請輸入文本與顏色",
  )
  _tr_textwithcolor_dialog_title_color = TR_gui_maskinputwidget.tr("textwithcolor_dialog_title_color",
    en="Please select a color",
    zh_cn="请选择颜色",
    zh_hk="請選擇顏色",
  )
  def __init__(self, color: QColor, text: str, parent=None):
    super().__init__(parent)
    self.bind_text(self.setWindowTitle, self._tr_textwithcolor_dialog_title_self)
    self.curColor = color

    # Create widgets
    self.lineEdit = QLineEdit()
    self.bind_text(self.lineEdit.setPlaceholderText, self._tr_text_input_placeholder)
    self.lineEdit.setText(text)

    self.colorPushButton = QPushButton(self._tr_set_color.get())
    self.bind_text(self.colorPushButton.setText, self._tr_set_color)
    # color preview label: show current color and hex code
    self.colorPreviewLabel = QLabel()
    self.colorPreviewLabel.setMinimumWidth(64)
    self.colorPreviewLabel.setAutoFillBackground(True)
    palette = self.colorPreviewLabel.palette()
    palette.setColor(self.colorPreviewLabel.backgroundRole(), self.curColor)
    palette.setColor(self.colorPreviewLabel.foregroundRole(), self.curColor)
    self.colorPreviewLabel.setPalette(palette)

    self.colorLabel = QLabel(self.curColor.name(QColor.HexRgb))

    self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

    # Layout setup: vertical layout
    mainLayout = QVBoxLayout(self)
    mainLayout.addWidget(self.lineEdit)
    hLayout = QHBoxLayout()
    hLayout.addWidget(self.colorPushButton)
    hLayout.addWidget(self.colorPreviewLabel)
    hLayout.addWidget(self.colorLabel)
    mainLayout.addLayout(hLayout)
    mainLayout.addWidget(self.buttonBox)

    # Signal connections
    self.colorPushButton.clicked.connect(self.colorChangeRequest)
    self.buttonBox.accepted.connect(self.accept)
    self.buttonBox.rejected.connect(self.reject)

    self.colorChanged()

  @Slot()
  def colorChangeRequest(self):
    newColor = QColorDialog.getColor(self.curColor, self, self._tr_textwithcolor_dialog_title_color.get())
    if newColor.isValid() and newColor != self.curColor:
      self.curColor = newColor
      self.colorChanged()

  def colorChanged(self):
    self.colorLabel.setText(self.curColor.name())
    palette = self.colorPreviewLabel.palette()
    palette.setColor(self.colorPreviewLabel.backgroundRole(), self.curColor)
    palette.setColor(self.colorPreviewLabel.foregroundRole(), self.curColor)
    self.colorPreviewLabel.setPalette(palette)

  def getText(self) -> str:
    return self.lineEdit.text()

  def getColor(self) -> QColor:
    return self.curColor

# ---------------------------------------------------------------
# MaskInputWidget class
# ---------------------------------------------------------------
class MaskInputWidget(QWidget, TranslatableWidgetInterface):
  valueChanged = Signal()

  _tr_not_specified = TR_gui_maskinputwidget.tr("not_specified",
    en="Not specified",
    zh_cn="未指定",
    zh_hk="未指定",
  )
  _tr_set_button_text = TR_gui_maskinputwidget.tr("set_button_text",
    en="Set",
    zh_cn="设置",
    zh_hk="設置",
  )
  _tr_set_color_fill = TR_gui_maskinputwidget.tr("set_color_fill",
    en="Color Fill",
    zh_cn="纯色填充",
    zh_hk="純色填充",
  )
  _tr_set_text = TR_gui_maskinputwidget.tr("set_text",
    en="Text",
    zh_cn="文本",
    zh_hk="文本",
  )
  _tr_set_image = TR_gui_maskinputwidget.tr("set_image",
    en="Image",
    zh_cn="图片",
    zh_hk="圖片",
  )
  _tr_remove_value = TR_gui_maskinputwidget.tr("remove_value",
    en="Clear",
    zh_cn="清空",
    zh_hk="清空",
  )

  # Class-level defaults (for new instances)
  default_color = QColor("#000000")
  default_text = ""
  default_text_color = QColor("#000000")
  default_image = ""

  def __init__(self, parent=None):
    super().__init__(parent)
    # Current state: type can be "color", "text", "image", or "none"
    self.current_type = "none"
    self.current_value = None
    self.current_value_converted = None
    self.is_color_only = False

    # Instance-level remembered values (initially from class defaults)
    self.last_color = MaskInputWidget.default_color
    self.last_text = MaskInputWidget.default_text
    self.last_text_color = MaskInputWidget.default_text_color
    self.last_image = MaskInputWidget.default_image

    # Create the three sub-widgets
    self.iconLabel = QLabel()
    self.valueLabel = QLabel(self._tr_not_specified.get())
    self.modifyButton = QPushButton(self._tr_set_button_text.get())
    self.bind_text(self.modifyButton.setText, self._tr_set_button_text)
    self.modifyButton.clicked.connect(self.showMenu)

    # Group these in a horizontal layout
    layout = QHBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(self.iconLabel)
    layout.addWidget(self.valueLabel)
    layout.addWidget(self.modifyButton)

    self.updateDisplay()

  def getValue(self) -> Color | PIL.Image.Image | tuple[str, Color] | None:
    return self.current_value_converted

  def setIsColorOnly(self, is_color_only: bool):
    self.is_color_only = is_color_only

  def getIsColorOnly(self) -> bool:
    return self.is_color_only

  def showMenu(self):
    menu = QMenu(self)
    action_color = menu.addAction(self._tr_set_color_fill.get())
    action_color.triggered.connect(self.setColorFill)
    if not self.is_color_only:
      action_text = menu.addAction(self._tr_set_text.get())
      action_text.triggered.connect(self.setTextInput)
      action_image = menu.addAction(self._tr_set_image.get())
      action_image.triggered.connect(self.setImageInput)

    menu.addSeparator()
    action_remove = menu.addAction(self._tr_remove_value.get())
    action_remove.triggered.connect(self.removeValue)
    # Position the menu under the button.
    menu.exec(self.modifyButton.mapToGlobal(QPoint(0, self.modifyButton.height())))

  @staticmethod
  def toPPColor(color: QColor) -> Color:
    return Color.get((color.red(), color.green(), color.blue()))

  @Slot()
  def setColorFill(self):
    color = QColorDialog.getColor(self.last_color, self, self._tr_set_color_fill.get())
    if color.isValid() and (self.current_type != "color" or color != self.current_value):
      self.current_type = "color"
      self.current_value = color
      self.current_value_converted = self.toPPColor(color)
      self.last_color = color
      MaskInputWidget.default_color = color
      self.updateDisplay()
      self.valueChanged.emit()

  @Slot()
  def setTextInput(self):
    dialog = TextWithColorInputDialog(self.last_text_color, self.last_text, self)
    if dialog.exec() == QDialog.Accepted:
      text = dialog.getText()
      color = dialog.getColor()
      if self.current_type != "text" or (text, color) != self.current_value:
        self.current_type = "text"
        self.current_value = (text, color)
        self.current_value_converted = (text, self.toPPColor(color))
        self.last_text = text
        self.last_text_color = color
        MaskInputWidget.default_text = text
        MaskInputWidget.default_text_color = color
        self.updateDisplay()
        self.valueChanged.emit()

  _tr_select_image_dialog_title = TR_gui_maskinputwidget.tr("select_image_dialog_title",
    en="Select Image",
    zh_cn="选择图片",
    zh_hk="選擇圖片",
  )
  _tr_select_image_dialog_filter_prefix= TR_gui_maskinputwidget.tr("select_image_dialog_filter_prefix",
    en="Images",
    zh_cn="图片",
    zh_hk="圖片",
  )
  _IMAGE_FORMATS_SUPPORTED = " (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif *.webp *.ico)"
  _tr_select_image_dialog_filter_all = TR_gui_maskinputwidget.tr("select_image_dialog_filter_all",
    en="All Files (*.*)",
    zh_cn="所有文件 (*.*)",
    zh_hk="所有文件 (*.*)",
  )
  _tr_unable_to_open_image_file = TR_gui_maskinputwidget.tr("unable_to_open_image_file",
    en="Unable to open the image file: ",
    zh_cn="无法打开图片文件：",
    zh_hk="無法打開圖片文件：",
  )
  @Slot()
  def setImageInput(self):
    start_dir = ""
    if self.last_image:
      start_dir = QFileInfo(self.last_image).absoluteDir().absolutePath()
    elif MaskInputWidget.default_image:
      start_dir = QFileInfo(MaskInputWidget.default_image).absoluteDir().absolutePath()
    filter_image = self._tr_select_image_dialog_filter_prefix.get() + self._IMAGE_FORMATS_SUPPORTED
    filter_all = self._tr_select_image_dialog_filter_all.get()
    filter_str = filter_image + ";;" + filter_all
    fileName, _ = QFileDialog.getOpenFileName(self, self._tr_select_image_dialog_title.get(), start_dir, filter_str)
    if fileName:
      # 这里我们不与原来的文件名进行比较，即使路径一样也视为内容有更新
      self.current_type = "image"
      self.current_value = fileName
      self.last_image = fileName
      MaskInputWidget.default_image = fileName
      self.updateDisplay()
      # 尝试打开图片文件，如果失败则不更新 current_value_converted
      is_valid = False
      exception_msg = ""
      try:
        self.current_value_converted = PIL.Image.open(fileName)
        # 打开之后立即读取，免得之后用的时候再读取时因为线程问题导致异常
        self.current_value_converted.load()
        is_valid = True
      except Exception as e:
        exception_msg = str(e)
      if is_valid:
        self.valueChanged.emit()
      else:
        QMessageBox.critical(self, self._tr_select_image_dialog_title.get(), self._tr_unable_to_open_image_file.get() + exception_msg)

  @Slot()
  def removeValue(self):
    if self.current_type != "none":
      self.current_type = "none"
      self.current_value = None
      self.current_value_converted = None
      self.updateDisplay()
      self.valueChanged.emit()

  @Slot()
  def updateValueLabel(self):
    text_color = QColor("#000000")
    text = self._tr_not_specified.get()
    tooltip = ""
    match self.current_type:
      case "color":
        if not isinstance(self.current_value, QColor):
          raise ValueError("Invalid color value")
        text = self.current_value.name(QColor.HexRgb)
      case "text":
        text, text_color = self.current_value
        if not isinstance(text, str):
          raise ValueError("Invalid text value")
        if not isinstance(text_color, QColor):
          raise ValueError("Invalid text color value")
      case "image":
        path = self.current_value
        if not isinstance(path, str):
          raise ValueError("Invalid image path value")
        tooltip = path
        text = os.path.basename(path)
      case "none":
        pass
      case _:
        raise ValueError("Invalid current type")
    self.valueLabel.setText(text)
    self.valueLabel.setToolTip(tooltip)
    palette = self.valueLabel.palette()
    palette.setColor(self.valueLabel.foregroundRole(), text_color)
    self.valueLabel.setPalette(palette)

  @Slot()
  def updateIconLabel(self):
    pixmap = None
    fillcolor = None
    match self.current_type:
      case "color":
        fillcolor = self.current_value
      case "text":
        fillcolor = self.current_value[1]
      case "image":
        pass
      case "none":
        pass
      case _:
        raise ValueError("Invalid current type")
    if fillcolor is not None:
      if not isinstance(fillcolor, QColor):
        raise ValueError("Invalid color value")
      if pixmap is not None:
        raise ValueError("Both fill color and image are set")
      pixmap = QPixmap(16, 16)
      pixmap.fill(fillcolor)
    if pixmap is not None:
      self.iconLabel.setPixmap(pixmap)
    else:
      self.iconLabel.clear()

  def updateDisplay(self):
    self.updateValueLabel()
    self.updateIconLabel()

  def update_text(self):
    super().update_text()
    self.updateValueLabel()
