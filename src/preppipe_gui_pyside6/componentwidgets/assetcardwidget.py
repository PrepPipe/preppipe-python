# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
from preppipe.language import TranslationDomain
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack
from ..util.assettagmanager import AssetTagManager
from ..util.assetthumbnail import get_thumbnail_manager

TR_gui_assetcardwidget = TranslationDomain("gui_assetcardwidget")

class AssetCardStyleManager:

  _styles = {
    'light': {
      'normal': "background-color: rgba(245, 245, 245, 1.0); border: 1px solid rgba(220, 220, 220, 1.0); border-radius: 8px; padding: 2px;",
      'hover': "background-color: rgba(235, 235, 235, 1.0); border: 1px solid rgba(200, 200, 200, 1.0); border-radius: 8px; padding: 2px;",
      'selected': "background-color: rgba(220, 235, 255, 1.0); border: 2px solid #4a90e2; border-radius: 8px; padding: 1px;",
      'selected_hover': "background-color: rgba(210, 225, 250, 1.0); border: 2px solid #3a80d2; border-radius: 8px; padding: 1px;",
      'name_color': '#000000',
      'image_background': '#f8f8f8',
      'image_label': "border: none; background-color: {image_background};",
      'context_menu': "QMenu { background-color: #ffffff; border: 1px solid rgba(220, 220, 220, 1.0); } QMenu::item:selected { background-color: rgba(248, 248, 248, 0.95); } QMenu::item { padding: 4px 24px; } QMenu::separator { height: 1px; background-color: rgba(220, 220, 220, 1.0); }",
      'tags_button': {
        'normal': "QPushButton { background-color: rgba(235, 235, 235, 0.95); border: 1px solid rgba(220, 220, 220, 0.95); border-radius: {radius}px; color: #000000; padding: 0px 10px; text-align: center; outline: none; height: {height}px; qproperty-flat: false; }",
        'hover': "QPushButton:hover { background-color: rgba(245, 245, 245, 0.95); border-color: rgba(230, 230, 230, 0.95); border-radius: {radius}px; color: #000000; }",
        'pressed': "QPushButton:pressed { background-color: rgba(245, 245, 245, 0.95); border-color: rgba(220, 220, 220, 0.95); border-radius: {radius}px; color: #000000; }",
        'focus': "QPushButton:focus { background-color: rgba(235, 235, 235, 0.95); border: 1px solid rgba(220, 220, 220, 0.95); border-radius: {radius}px; color: #000000; outline: none; }",
        'flat': "QPushButton:flat { border-radius: {radius}px; }"
      }
    },
    'dark': {
      'normal': "background-color: rgba(50, 50, 50, 1.0); border: 1px solid rgba(70, 70, 70, 1.0); border-radius: 8px; padding: 2px;",
      'hover': "background-color: rgba(60, 60, 60, 1.0); border: none; border-radius: 8px; padding: 2px;",
      'selected': "background-color: rgba(80, 80, 80, 1.0); border: none; border-radius: 8px; padding: 2px;",
      'selected_hover': "background-color: rgba(100, 100, 100, 1.0); border: none; border-radius: 8px; padding: 2px;",
      'name_color': '#ffffff',
      'image_background': '#3a3a3a',
      'image_label': "border: none; background-color: {image_background};",
      'context_menu': "QMenu { background-color: #000000; border: 1px solid rgba(70, 70, 70, 1.0); } QMenu::item:selected { background-color: rgba(35, 35, 35, 0.95); } QMenu::item { padding: 4px 24px; } QMenu::separator { height: 1px; background-color: rgba(70, 70, 70, 1.0); }",
      'tags_button': {
        'normal': "QPushButton { background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: {radius}px; color: #CCCCCC; padding: 0px 10px; text-align: center; outline: none; height: {height}px; qproperty-flat: false; }",
        'hover': "QPushButton:hover { background-color: rgba(85, 85, 85, 0.95); border: none; border-radius: {radius}px; color: #DDDDDD; }",
        'pressed': "QPushButton:pressed { background-color: rgba(85, 85, 85, 0.95); border: none; border-radius: {radius}px; color: #DDDDDD; }",
        'focus': "QPushButton:focus { background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: {radius}px; color: #CCCCCC; outline: none; }",
        'flat': "QPushButton:flat { border: none; border-radius: {radius}px; }"
      }
    }
  }

  @staticmethod
  def detect_theme(palette=None):
    """检测当前系统主题是深色还是浅色"""
    if palette is None:
      palette = QApplication.palette()
    bg_color = palette.color(QPalette.Window)
    # 计算颜色亮度 (HSL亮度公式)
    brightness = (0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()) / 255
    return 'dark' if brightness < 0.5 else 'light'

  @staticmethod
  def get_style(style_name, palette=None):
    theme = AssetCardStyleManager.detect_theme(palette)
    return AssetCardStyleManager._styles[theme].get(style_name, "")

  @staticmethod
  def get_tags_button_style(height, palette=None):
    """获取标签按钮样式，根据高度动态计算圆角"""
    theme = AssetCardStyleManager.detect_theme(palette)
    radius = height // 2
    styles = []
    for key, template in AssetCardStyleManager._styles[theme].get('tags_button', {}).items():
      style = template.replace('{radius}', str(radius))
      style = style.replace('{height}', str(height))
      styles.append(style)
    return "\n".join(styles)

  @staticmethod
  def apply_tags_button_style(button, height, palette=None):
    style = AssetCardStyleManager.get_tags_button_style(height, palette)
    button.setStyleSheet(style)

  @staticmethod
  def apply_style(widget, is_selected=False, is_hover=False, palette=None):
    match (is_selected, is_hover):
      case (True, True):
        widget.setStyleSheet(AssetCardStyleManager.get_style('selected_hover', palette))
      case (True, False):
        widget.setStyleSheet(AssetCardStyleManager.get_style('selected', palette))
      case (False, True):
        widget.setStyleSheet(AssetCardStyleManager.get_style('hover', palette))
      case (False, False):
        widget.setStyleSheet(AssetCardStyleManager.get_style('normal', palette))

  @staticmethod
  def apply_label_style(label, palette=None):
    theme = AssetCardStyleManager.detect_theme(palette)
    color = AssetCardStyleManager._styles[theme].get('name_color', '#000000')
    style = f"color: {color}; padding: 4px 0; border: none; background-color: transparent;"
    label.setStyleSheet(style)

  @staticmethod
  def apply_image_label_style(label, palette=None):
    theme = AssetCardStyleManager.detect_theme(palette)
    image_background = AssetCardStyleManager._styles[theme].get('image_background', '#f0f0f0')
    template = AssetCardStyleManager.get_style('image_label', palette)
    style = template.format(image_background=image_background)
    label.setStyleSheet(style)

class AssetCardWidget(QPushButton):
  """素材卡片组件，目前在assetbrowser中用到，后续素材类型多了可以考虑扩展和复用
  外观描述：
  1. 整体为一个圆角卡片式按钮，支持选中和悬停状态样式
  2. 从上到下包含三个主要区域：
     - 图片区域：显示素材缩略图，居中对齐
     - 名称区域：显示素材名称，使用粗体字，超出宽度时自动截断
     - 标签区域：显示素材标签，采用按钮样式，超出宽度时自动截断
  3. 支持深色/浅色主题自动切换

  右键菜单：可进行查看详情（等同左键）、快捷添加最近标签、编辑标签（等同点击标签按钮）
  """

  _tr_no_tags = TR_gui_assetcardwidget.tr("assetcardwidget_no_tags",
    en="No tags",
    zh_cn="无标签",
    zh_hk="无标签",
  )
  _tr_show_detail = TR_gui_assetcardwidget.tr("assetcardwidget_show_detail",
    en="Show detail",
    zh_cn="显示详情",
    zh_hk="显示详情",
  )
  _tr_edit_tags = TR_gui_assetcardwidget.tr("assetcardwidget_edit_tags",
    en="Edit tags",
    zh_cn="编辑标签",
    zh_hk="编辑标签",
  )
  _tr_add_tag = TR_gui_assetcardwidget.tr("assetcardwidget_add_tag",
    en="Add tag",
    zh_cn="添加标签",
    zh_hk="添加标签",
  )
  _tr_no_custom_tags = TR_gui_assetcardwidget.tr("assetcardwidget_no_custom_tags",
    en="(no custom tags)",
    zh_cn="（无自定义标签）",
    zh_hk="（无自定义标签）",
  )

  clicked = Signal(str, QMouseEvent)
  tags_button_clicked = Signal(str, QPushButton)

  asset_id: str
  _is_selected: bool
  _is_hovered: bool
  _thumbnail_loaded: bool
  _name_full_text: str
  _tags_full_text: str
  name_font: QFont
  tags_font: QFont
  name_font_metrics: QFontMetrics
  tags_font_metrics: QFontMetrics
  tags_button: QPushButton
  layout: QVBoxLayout
  image_label: QLabel
  name_label: QLabel

  def __init__(self, asset_id: str, width: int, height: int, name_font=None, tags_font=None, parent=None):
    super().__init__(parent)
    self.asset_id = asset_id
    self._is_selected = False
    self._is_hovered = False
    self._thumbnail_loaded = False

    self._name_full_text = ''
    self._tags_full_text = ''

    self.name_font = name_font or QFont()
    self.tags_font = tags_font or QFont()
    self.name_font.setWeight(QFont.Weight.Bold)

    self.name_font_metrics = QFontMetrics(self.name_font)
    self.tags_font_metrics = QFontMetrics(self.tags_font)

    self.tags_button = None
    self._initialize_ui(width, height)

  def _calculate_elided_text(self, text, widget, margin):
    if not text:
      return ''
    font_metrics = widget.fontMetrics()
    available_width = max(widget.width() - margin, 0)
    return font_metrics.elidedText(text, Qt.ElideRight, available_width)

  def resizeEvent(self, event):
    super().resizeEvent(event)
    self._update_elided_text()

  def _update_elided_text(self):
    size = self.name_label.size()
    self.name_label.resizeEvent(QResizeEvent(size, size))
    self.tags_button.resizeEvent(None)

  def _initialize_ui(self, width: int, height: int):
    self.setFixedSize(width, height)
    self.layout = QVBoxLayout(self)
    self.layout.setContentsMargins(8, 8, 8, 8)
    self.layout.setSpacing(6)
    self.layout.setSizeConstraint(QLayout.SetFixedSize)

    AssetCardStyleManager.apply_style(self, False)
    self.setContextMenuPolicy(Qt.CustomContextMenu)
    self.customContextMenuRequested.connect(self._show_context_menu)
    self._create_image_section(width, height)
    self._create_name_section()
    self._create_tags_section()
    self.setMouseTracking(True)

  def _create_image_section(self, card_width: int, card_height: int):
    self.image_label = QLabel()
    self.image_label.setAlignment(Qt.AlignCenter)
    AssetCardStyleManager.apply_image_label_style(self.image_label)
    self.image_label.setMouseTracking(False)

    layout_margins = self.layout.contentsMargins()
    layout_spacing = self.layout.spacing()
    available_width = int(card_width - (layout_margins.left() + layout_margins.right()))
    available_height = int(card_height - (layout_margins.top() + layout_margins.bottom() +
                    self.name_font_metrics.height() + self.tags_font_metrics.height() + layout_spacing))

    self.image_label.setFixedSize(available_width, available_height)
    self.image_label.clear()

    self.image_label._last_width = -1
    self.image_label._last_height = -1
    self.image_label.resizeEvent = lambda event: self._on_image_resize(event)
    self.layout.addWidget(self.image_label)

  def _on_image_resize(self, event):
    if event:
      super(QLabel, self.image_label).resizeEvent(event)

    current_width = int(self.image_label.width())
    current_height = int(self.image_label.height())

    if (current_width != self.image_label._last_width or current_height != self.image_label._last_height):
      self.image_label._last_width = current_width
      self.image_label._last_height = current_height

      if self._thumbnail_loaded:
        thumbnail_manager = get_thumbnail_manager()
        self.image_label.setPixmap(thumbnail_manager.get_pixmap_for_asset(
          self.asset_id, current_width - 1, current_height - 1, margin_ratio=0.05))
      else:
        self.image_label.clear()

  def _create_name_section(self):
    self.name_label = QLabel()
    self.name_label.setAlignment(Qt.AlignCenter)
    self.name_label.setWordWrap(False)
    self.name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    self.name_label.setFont(self.name_font)
    self.name_label.setMinimumHeight(self.name_font_metrics.height() + 8)
    self.name_label.setTextInteractionFlags(Qt.NoTextInteraction)

    original_resize_event = self.name_label.resizeEvent
    def custom_resize_event(event):
      original_resize_event(event)
      if self._name_full_text:
        self.name_label.setText(self._calculate_elided_text(self._name_full_text, self.name_label, 8))
    self.name_label.resizeEvent = custom_resize_event
    AssetCardStyleManager.apply_label_style(self.name_label)
    self.name_label.setMouseTracking(False)
    self.layout.addWidget(self.name_label)

  def _create_tags_section(self):
    self.tags_button = QPushButton("", self)
    self.tags_button.setFont(self.tags_font)
    self.tags_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    self.tags_button.setMouseTracking(True)

    original_resize_event = self.tags_button.resizeEvent
    def custom_resize_event(event):
      fixed_width = self.tags_button.width()
      fixed_height = self.tags_button.height()

      original_resize_event(event)
      if self._tags_full_text:
        self.tags_button.setText(self._calculate_elided_text(self._tags_full_text, self.tags_button, 10))

      self.tags_button.setFixedWidth(fixed_width)
      self.tags_button.setFixedHeight(fixed_height)
    self.tags_button.resizeEvent = custom_resize_event

    tag_button_height = int(self.tags_font_metrics.height() * 1.4)
    self.tags_button.setFixedHeight(tag_button_height)
    self.tags_button.setFixedWidth(self.width() - self.layout.contentsMargins().left() - self.layout.contentsMargins().right())
    AssetCardStyleManager.apply_tags_button_style(self.tags_button, tag_button_height)

    self.tags_button.clicked.connect(self._on_tags_button_clicked)
    self.layout.addWidget(self.tags_button)

  def enterEvent(self, event):
    super().enterEvent(event)
    self._is_hovered = True
    self.update_style()

  def leaveEvent(self, event):
    super().leaveEvent(event)
    self._is_hovered = False
    self.update_style()

  def mousePressEvent(self, event):
    super().mousePressEvent(event)
    self.set_selected(True)
    self.clicked.emit(self.asset_id, event)

  def _on_tags_button_clicked(self):
    self.set_selected(True)
    self.tags_button_clicked.emit(self.asset_id, self.tags_button)
    self.tags_button.setDown(False)
    self.tags_button.clearFocus()
    self.tags_button.update()

  def _get_asset_name(self):
    asset = AssetManager.get_instance().get_asset(self.asset_id)
    if isinstance(asset, ImagePack) and (descriptor := ImagePack.get_descriptor_by_id(self.asset_id)) and (name_obj := descriptor.get_name()):
      return name_obj.get()
    return self.asset_id

  def update_text(self):
    self.update_name()
    self.update_tags()

  def update_name(self):
    self._name_full_text = self._get_asset_name()
    self.name_label.setText(self._calculate_elided_text(self._name_full_text, self.name_label, 8))

  def update_tags(self):
    asset_tags = AssetTagManager.get_instance().get_asset_tags_display(self.asset_id)
    self._tags_full_text = ", ".join(sorted(asset_tags)) if asset_tags else self._tr_no_tags.get()

    current_width = self.tags_button.width()
    current_height = self.tags_button.height()

    self.tags_button.resizeEvent(None)

    self.tags_button.setFixedWidth(current_width)
    self.tags_button.setFixedHeight(current_height)

  def set_selected(self, selected: bool):
    if self._is_selected != selected:
      self._is_selected = selected
      self.update_style()

  def showEvent(self, event):
    super().showEvent(event)

    if not self._thumbnail_loaded:
      current_width = int(self.image_label.width())
      current_height = int(self.image_label.height())

      if current_width > 0 and current_height > 0:
        self._load_thumbnail()

    self.update_text()

  def _load_thumbnail(self):
    thumbnail_manager = get_thumbnail_manager()
    thumbnail_manager.generate_thumbnail_async(self.asset_id, self._on_thumbnail_generated)

  def _on_thumbnail_generated(self, asset_id: str, thumbnail_path: str):
    if asset_id != self.asset_id or not thumbnail_path:
      return

    self._update_thumbnail_ui(asset_id)

  def _update_thumbnail_ui(self, asset_id: str, pixmap: QPixmap = None):
    if asset_id != self.asset_id:
      return

    if QThread.currentThread() != QApplication.instance().thread():
      if pixmap:
        QMetaObject.invokeMethod(self, '_update_thumbnail_ui',
                                Qt.QueuedConnection,
                                Q_ARG(str, asset_id),
                                Q_ARG(QPixmap, pixmap))
      else:
        QMetaObject.invokeMethod(self, '_update_thumbnail_ui',
                                Qt.QueuedConnection,
                                Q_ARG(str, asset_id))
      return

    current_width = int(self.image_label.width())
    current_height = int(self.image_label.height())
    thumbnail_manager = get_thumbnail_manager()

    if pixmap is None:
      pixmap = thumbnail_manager.get_pixmap_for_asset(
        self.asset_id, current_width - 1, current_height - 1, margin_ratio=0.05)

    if pixmap and not pixmap.isNull():
      self.image_label.setPixmap(pixmap)
      self._thumbnail_loaded = True
    else:
      self.image_label.setPixmap(thumbnail_manager.get_placeholder_pixmap(current_width - 1, current_height - 1))
      self._thumbnail_loaded = False

  def _show_context_menu(self, position):
    menu = QMenu(self)

    menu_style = AssetCardStyleManager.get_style('context_menu')
    menu.setStyleSheet(menu_style)

    show_detail_action = QAction(self._tr_show_detail.get(), self)
    show_detail_action.triggered.connect(lambda: self.clicked.emit(self.asset_id, QMouseEvent(QEvent.MouseButtonPress, QPoint(0, 0), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)))
    menu.addAction(show_detail_action)

    edit_tags_action = QAction(self._tr_edit_tags.get(), self)
    edit_tags_action.triggered.connect(self._on_tags_button_clicked)
    menu.addAction(edit_tags_action)

    add_tag_menu = menu.addMenu(self._tr_add_tag.get())
    add_tag_menu.setStyleSheet(menu_style)

    tag_manager = AssetTagManager.get_instance()
    recent_tags_display = tag_manager.get_recent_tags_display()

    if recent_tags_display:
      for tag_display in recent_tags_display:
        tag_action = QAction(tag_display, self)
        tag_semantic = tag_manager.get_tag_semantic(tag_display)
        tag_action.triggered.connect(lambda checked=False, tag=tag_semantic: self._add_tag_to_asset(tag))
        add_tag_menu.addAction(tag_action)
    else:
      no_tags_action = QAction(self._tr_no_custom_tags.get(), self)
      no_tags_action.setDisabled(True)
      add_tag_menu.addAction(no_tags_action)

    menu.exec_(self.mapToGlobal(position))

  def _add_tag_to_asset(self, tag_semantic):
    tag_manager = AssetTagManager.get_instance()
    if tag_manager.add_tag_to_asset(self.asset_id, tag_semantic)[0]:
      self.update_tags()

  def update_style(self, palette=None):
    AssetCardStyleManager.apply_style(self, self._is_selected, self._is_hovered, palette=palette)
    AssetCardStyleManager.apply_label_style(self.name_label)
    AssetCardStyleManager.apply_image_label_style(self.image_label)
    AssetCardStyleManager.apply_tags_button_style(self.tags_button, self.tags_button.height())
    self._update_elided_text()