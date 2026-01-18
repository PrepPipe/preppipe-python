# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import *
from PySide6.QtCore import Qt
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from ..componentwidgets.flowlayout import FlowLayout
from preppipe.util.imagepack import ImagePack
from ..util.assettagmanager import AssetTagManager
from PySide6.QtGui import QPalette

TR_gui_tageditdialog=TranslationDomain("gui_tageditdialog")

class TagEditStyleManager:
  _styles = {
    'light': {
      'tag_block': {
        'normal': "QWidget { background-color: rgba(235, 235, 235, 0.95); border: none; border-radius: 12px; padding: 4px 8px; }",
        'hover': "QWidget:hover { background-color: rgba(225, 225, 225, 0.95); border: none; }",
        'custom_hover': "QWidget:hover { background-color: #ffb3b3; border: none; }",
        'preset_normal': "QWidget { background-color: rgba(220, 220, 220, 0.95); border: 1px solid rgba(200, 200, 200, 0.95); border-radius: 12px; padding: 4px 8px; }"
      },
      'edit_line': "background-color: rgba(235, 235, 235, 0.95); border: 1px solid #CCCCCC; border-radius: 12px; padding: 4px 8px; color: #000000;"
    },
    'dark': {
      'tag_block': {
        'normal': "QWidget { background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: 12px; padding: 4px 8px; }",
        'hover': "QWidget:hover { background-color: rgba(85, 85, 85, 0.95); border: none; }",
        'custom_hover': "QWidget:hover { background-color: #662222; border: none; }",
        'preset_normal': "QWidget { background-color: rgba(40, 40, 40, 0.95); border: 1px solid rgba(60, 60, 60, 0.95); border-radius: 12px; padding: 4px 8px; }"
      },
      'edit_line': "background-color: rgba(65, 65, 65, 0.95); border: 1px solid #666666; border-radius: 12px; padding: 4px 8px; color: #CCCCCC;"
    }
  }

  @staticmethod
  def detect_theme(palette=None):
    if palette is None:
      palette = QApplication.palette()
    bg_color = palette.color(QPalette.Window)
    brightness = (0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()) / 255
    return 'dark' if brightness < 0.5 else 'light'

  @staticmethod
  def get_style(style_name, palette=None):
    theme = TagEditStyleManager.detect_theme(palette)
    return TagEditStyleManager._styles[theme].get(style_name, "")

  @staticmethod
  def apply_tag_block_style(widget, is_preset=False, palette=None):
    theme = TagEditStyleManager.detect_theme(palette)
    tag_block_styles = TagEditStyleManager._styles[theme].get('tag_block', {})

    if is_preset:
      style = tag_block_styles.get('preset_normal', '')
    else:
      style = tag_block_styles.get('normal', '') + '\n' + tag_block_styles.get('custom_hover', '')

    widget.setStyleSheet(style)

  @staticmethod
  def apply_edit_line_style(line_edit, palette=None):
    style = TagEditStyleManager.get_style('edit_line', palette)
    line_edit.setStyleSheet(style)

class TagBlock(QWidget):
  deleted = Signal(str)

  tag_text: str
  is_preset: bool
  label: QLabel
  is_recent: bool

  def __init__(self, tag_text, is_preset=False, parent=None):
    super().__init__(parent)
    self.tag_text = tag_text
    self.is_preset = is_preset
    layout = QHBoxLayout(self)
    layout.setContentsMargins(6, 3, 6, 3)
    layout.setSpacing(1)
    self.label = QLabel(tag_text)
    layout.addWidget(self.label)

    TagEditStyleManager.apply_tag_block_style(self, is_preset)

    if not is_preset:
      self.setCursor(Qt.PointingHandCursor)

  def mousePressEvent(self, event):
    if not self.is_preset:
      self.deleted.emit(self.tag_text)
      self.deleteLater()

class TagEditDialog(QDialog):
  '''
  标签编辑对话框，修改只在确认时保存，最近标签随编辑动态更新：
  1. 标题栏：显示"编辑标签:资产名称"
  2. 当前标签区域：显示当前资产已有的标签，点击可以删除
  3. 标签输入区域：包含一个输入框，用于输入新标签（回车添加）
  4. 最近标签区域：显示最近添加的标签，点击可以快速添加
  5. 按钮区域：包含确认和取消按钮，居右
  '''

  tags_changed = Signal(str)  # 参数为asset_id

  asset_id: str
  has_edited: bool
  tag_manager: AssetTagManager
  original_tags: set
  added_tags: set
  removed_tags: set
  current_tags_title: QLabel
  current_tags_scroll_area: QScrollArea
  current_tags_container: QWidget
  current_tags_layout: FlowLayout
  input_label: QLabel
  edit_line: QLineEdit
  recent_tags_title: QLabel
  recent_tags_scroll_area: QScrollArea
  recent_tags_container: QWidget
  recent_tags_layout: FlowLayout
  confirm_button: QPushButton
  cancel_button: QPushButton
  completer: QCompleter

  _tr_tag_edit_hint = TR_gui_tageditdialog.tr("tageditdialog_tag_edit_hint",
    en="Enter here",
    zh_cn="在此输入",
    zh_hk="在此輸入",
  )
  _tr_tag_edit_title = TR_gui_tageditdialog.tr("tageditdialog_tag_edit_title",
    en="Edit tags",
    zh_cn="编辑标签",
    zh_hk="編輯標籤",
  )
  _tr_current_tags = TR_gui_tageditdialog.tr("tageditdialog_current_tags",
    en="Current tags(click remove)",
    zh_cn="当前标签（点击标签删除）",
    zh_hk="當前標籤（點擊標籤删除）",
  )
  _tr_recent_added = TR_gui_tageditdialog.tr("tageditdialog_recent_added",
    en="Recent added(click add)",
    zh_cn="最近添加（点击标签添加）",
    zh_hk="最近添加（點擊標籤添加）",
  )
  _tr_confirm = TR_gui_tageditdialog.tr("tageditdialog_confirm",
    en="Confirm",
    zh_cn="确认",
    zh_hk="確認",
  )
  _tr_cancel = TR_gui_tageditdialog.tr("tageditdialog_cancel",
    en="Cancel",
    zh_cn="取消",
    zh_hk="取消",
  )
  _tr_input_tag = TR_gui_tageditdialog.tr("tageditdialog_input_tag",
    en="Input tag(enter to add)",
    zh_cn="输入标签（回车添加）",
    zh_hk="輸入標籤（回車添加）",
  )
  _tr_preset_tag_warning_title = TR_gui_tageditdialog.tr("tageditdialog_preset_tag_warning_title",
    en="Cannot add preset tag",
    zh_cn="无法添加预设标签",
    zh_hk="無法添加預設標籤",
  )
  _tr_preset_tag_warning_message = TR_gui_tageditdialog.tr("tageditdialog_preset_tag_warning_message",
    en="Preset tags cannot be manually added for now. Please contact support if you have any advice!",
    zh_cn="预设标签目前不支持手动添加。如果您有任何建议，欢迎联系开发者交流！",
    zh_hk="预设標籤目前不支持手動添加。如果您有任何建議，歡迎聯繫開發者交流！",
  )
  def __init__(self, asset_id, parent=None):
    super().__init__(parent)
    self.asset_id = asset_id
    self.has_edited = False
    self.tag_manager = AssetTagManager.get_instance()
    self.original_tags = set()
    self.added_tags = set()
    self.removed_tags = set()

    # 设置窗口标题
    asset_manager = AssetManager.get_instance()
    asset = asset_manager.get_asset(asset_id)
    asset_name = asset_id
    if isinstance(asset, ImagePack):
      descriptor = ImagePack.get_descriptor_by_id(asset_id)
      if descriptor:
        name_obj = descriptor.get_name()
        if hasattr(name_obj, 'get'):
          asset_name = name_obj.get()
        elif name_obj:
          asset_name = name_obj
    title_text = self._tr_tag_edit_title.get()
    self.setWindowTitle(f"{title_text}:{asset_name}")
    self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    self.setMinimumWidth(400)

    # 创建主布局（垂直布局）
    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(6, 16, 6, 6)
    main_layout.setSpacing(0)
    main_layout.setSizeConstraint(QLayout.SetDefaultConstraint)

    # ====================== 当前标签区域 ======================
    current_tags_section = QWidget()
    current_tags_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    current_tags_layout = QVBoxLayout(current_tags_section)
    current_tags_layout.setContentsMargins(0, 0, 0, 0)
    current_tags_layout.setSpacing(2)

    # 当前标签标题
    self.current_tags_title = QLabel(self._tr_current_tags.get())
    current_tags_layout.addWidget(self.current_tags_title)

    # 当前标签滚动区域
    self.current_tags_scroll_area = QScrollArea()
    self.current_tags_scroll_area.setWidgetResizable(True)
    self.current_tags_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.current_tags_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    self.current_tags_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    self.current_tags_scroll_area.setMinimumSize(0, 100)

    # 当前标签容器和流式布局
    self.current_tags_container = QWidget()
    self.current_tags_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    self.current_tags_layout = FlowLayout(self.current_tags_container, margin=0)
    self.current_tags_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    self.current_tags_layout.setVerticalSpacing(8)
    self.current_tags_layout.setHorizontalSpacing(8)
    self.current_tags_layout.setContentsMargins(4, 4, 4, 4)

    self.current_tags_scroll_area.setWidget(self.current_tags_container)
    current_tags_layout.addWidget(self.current_tags_scroll_area)
    main_layout.addWidget(current_tags_section)

    main_layout.addSpacing(16)

    # ====================== 标签输入区域 ======================
    edit_line_container = QWidget()
    edit_line_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    edit_line_layout = QVBoxLayout(edit_line_container)
    edit_line_layout.setContentsMargins(0, 0, 0, 0)
    edit_line_layout.setSpacing(8)

    # 输入框标签
    self.input_label = QLabel(self._tr_input_tag.get())
    self.input_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    edit_line_layout.addWidget(self.input_label)

    # 标签输入框
    self.edit_line = QLineEdit()
    TagEditStyleManager.apply_edit_line_style(self.edit_line)
    hint_text = self._tr_tag_edit_hint.get()
    self.edit_line.setPlaceholderText(hint_text)
    self.edit_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    edit_line_layout.addWidget(self.edit_line)
    main_layout.addWidget(edit_line_container)

    main_layout.addSpacing(16)

    # ====================== 最近标签区域 ======================
    recent_tags_section = QWidget()
    recent_tags_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    recent_tags_layout = QVBoxLayout(recent_tags_section)
    recent_tags_layout.setContentsMargins(0, 0, 0, 0)
    recent_tags_layout.setSpacing(2)

    # 最近标签标题
    self.recent_tags_title = QLabel(self._tr_recent_added.get())
    recent_tags_layout.addWidget(self.recent_tags_title)

    # 最近标签滚动区域
    self.recent_tags_scroll_area = QScrollArea()
    self.recent_tags_scroll_area.setWidgetResizable(True)
    self.recent_tags_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.recent_tags_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    self.recent_tags_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    self.recent_tags_scroll_area.setMinimumSize(0, 100)

    # 最近标签容器和流式布局
    self.recent_tags_container = QWidget()
    self.recent_tags_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    self.recent_tags_layout = FlowLayout(self.recent_tags_container, margin=0)
    self.recent_tags_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    self.recent_tags_layout.setVerticalSpacing(8)
    self.recent_tags_layout.setHorizontalSpacing(8)
    self.recent_tags_layout.setContentsMargins(4, 4, 4, 4)

    self.recent_tags_scroll_area.setWidget(self.recent_tags_container)
    recent_tags_layout.addWidget(self.recent_tags_scroll_area)
    main_layout.addWidget(recent_tags_section)

    # ====================== 按钮区域 ======================
    buttons_container = QWidget()
    buttons_layout = QHBoxLayout(buttons_container)
    buttons_layout.setContentsMargins(0, 16, 0, 0)
    buttons_layout.setSpacing(8)
    buttons_layout.addStretch()

    # 确认按钮
    self.confirm_button = QPushButton(self._tr_confirm.get())
    self.confirm_button.clicked.connect(self.on_confirm_clicked)
    buttons_layout.addWidget(self.confirm_button)

    # 取消按钮
    self.cancel_button = QPushButton(self._tr_cancel.get())
    self.cancel_button.clicked.connect(self.on_cancel_clicked)
    buttons_layout.addWidget(self.cancel_button)

    main_layout.addWidget(buttons_container)

    # ====================== 输入框自动补全 ======================
    self.completer = QCompleter()
    self.completer.setCaseSensitivity(Qt.CaseInsensitive)
    self.completer.setCompletionMode(QCompleter.PopupCompletion)
    self.completer.setFilterMode(Qt.MatchContains)
    self.edit_line.setCompleter(self.completer)

    # 连接信号和槽
    self.edit_line.returnPressed.connect(self.on_edit_return_pressed)
    self.edit_line.editingFinished.connect(self.on_edit_finished)
    self.edit_line.mousePressEvent = self._on_edit_mouse_press

    # 初始化补全标签列表
    self.update_completer_tags()

  def showEvent(self, event):
    if event.isAccepted():
      self.load_tags()
      self.load_recent_tags()
    super().showEvent(event)

  def load_tags(self):
    while self.current_tags_layout.count() > 0:
      item = self.current_tags_layout.takeAt(0)
      if item.widget():
        item.widget().deleteLater()

    self.original_tags = set(self.tag_manager.get_asset_tags(self.asset_id))
    self.added_tags.clear()
    self.removed_tags.clear()

    preset_tags = []
    custom_tags = []

    for semantic_tag in self.original_tags:
      display_tag = self.tag_manager.get_tag_display_text(semantic_tag)
      is_preset = self.tag_manager.is_preset_tag(semantic_tag)
      if is_preset:
        preset_info = self.tag_manager.get_asset_preset_tag_from_semantic(semantic_tag)
        if preset_info:
          preset_tags.append((display_tag, semantic_tag, preset_info.value))
      else:
        custom_tags.append((display_tag, semantic_tag))

    preset_tags.sort(key=lambda x: x[2])
    for display_tag, _, _ in preset_tags:
      self.add_tag_block(display_tag, True)

    custom_tags.sort(key=lambda x: x[0])
    for display_tag, _ in custom_tags:
      self.add_tag_block(display_tag, False)

  def load_recent_tags(self):
    while self.recent_tags_layout.count() > 0:
      item = self.recent_tags_layout.takeAt(0)
      if item.widget():
        item.widget().deleteLater()
    recent_display_tags = self.tag_manager.get_recent_tags_display(self.asset_id)
    for display_tag in recent_display_tags:
      self.add_recent_tag_block(display_tag)
    self.recent_tags_title.setVisible(True)

  def add_recent_tag_block(self, tag_text):
    if not tag_text.strip():
      return

    tag_block = TagBlock(tag_text, is_preset=False)
    tag_block.is_recent = True
    tag_block.mousePressEvent = lambda event, b=tag_block: self._add_tag(b.tag_text)
    tag_block.setCursor(Qt.PointingHandCursor)

    theme = TagEditStyleManager.detect_theme()
    tag_block_styles = TagEditStyleManager._styles[theme].get('tag_block', {})
    recent_tag_style = tag_block_styles.get('normal', '') + '\n' + tag_block_styles.get('hover', '')
    tag_block.setStyleSheet(recent_tag_style)

    self.recent_tags_layout.addWidget(tag_block)

  def add_tag_block(self, tag_text, is_preset=False):
    tag_block = TagBlock(tag_text, is_preset)
    tag_block.deleted.connect(self.on_tag_deleted)
    self.current_tags_layout.addWidget(tag_block)
    QTimer.singleShot(0, self._adjust_dialog_size)

  def update_completer_tags(self):
    tags_dict = self.tag_manager.get_tags_dict()
    all_tags = set()
    for tags in tags_dict.values():
      all_tags.update(tags)
    non_preset_tags = [tag for tag in all_tags if not self.tag_manager.is_preset_tag(tag)]
    display_tags = self.tag_manager.translate_tags(non_preset_tags)
    tags_model = QStringListModel(sorted(display_tags))
    self.completer.setModel(tags_model)

  def on_tag_deleted(self, tag_text):
    semantic_tag = self.tag_manager.get_tag_semantic(tag_text)

    if self.tag_manager.is_preset_tag(semantic_tag):
      return

    if (semantic_tag in self.original_tags and semantic_tag not in self.removed_tags) or \
       (semantic_tag in self.added_tags):
      self.has_edited = True
      if semantic_tag in self.added_tags:
        self.added_tags.remove(semantic_tag)
      else:
        self.removed_tags.add(semantic_tag)
      QTimer.singleShot(0, self._adjust_dialog_size)

  def on_edit_return_pressed(self):
    new_text = self.edit_line.text()
    if new_text:
      self._add_tag(new_text)
      self.edit_line.clear()
    self.edit_line.setFocus()

  def _add_tag(self, tag_text):
    all_text = self.tag_manager.get_tr_all()
    if tag_text == all_text:
      return

    new_semantic = self.tag_manager.get_tag_semantic(tag_text)
    if self.tag_manager.is_preset_tag(new_semantic):
      QMessageBox.warning(self, self._tr_preset_tag_warning_title.get(), self._tr_preset_tag_warning_message.get())
      return

    if (new_semantic in self.original_tags and new_semantic not in self.removed_tags) or \
       (new_semantic in self.added_tags):
      return

    self.has_edited = True
    if new_semantic in self.removed_tags:
      self.removed_tags.remove(new_semantic)
    else:
      self.added_tags.add(new_semantic)

    self.add_tag_block(tag_text)
    _, recent_updated = self.tag_manager.add_tag_to_asset(self.asset_id, new_semantic, temporary=True)
    if recent_updated:
      self.load_recent_tags()

  def on_edit_finished(self):
    if self.edit_line.text().strip():
      self.on_edit_return_pressed()

  def keyPressEvent(self, event):
    if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
      if self.edit_line.hasFocus():
        return
      else:
        self.on_confirm_clicked()
        return
    elif event.key() == Qt.Key_Escape:
      self.reject()
      return
    super().keyPressEvent(event)

  def apply_changes(self):
    if not self.has_edited:
      return

    final_tags = (self.original_tags - self.removed_tags) | self.added_tags
    self.tag_manager.update_asset_tags(self.asset_id, final_tags)
    self.tags_changed.emit(self.asset_id)
    self.added_tags.clear()
    self.removed_tags.clear()
    self.has_edited = False

  def closeEvent(self, event):
    self.apply_changes()
    super().closeEvent(event)

  def on_confirm_clicked(self):
    if self.edit_line.text().strip():
      self.on_edit_return_pressed()
    self.apply_changes()
    self.accept()

  def on_cancel_clicked(self):
    self.reject()

  def _adjust_dialog_size(self):
    self.current_tags_layout.update()
    self.recent_tags_layout.update()
    self.updateGeometry()
    self.adjustSize()
  def _on_edit_mouse_press(self, event):
    QLineEdit.mousePressEvent(self.edit_line, event)
    if self.completer:
      self.completer.complete()

  def changeEvent(self, event):
    if event.type() == QEvent.PaletteChange:
      self._on_palette_changed(self.palette())
    super().changeEvent(event)

  def _on_palette_changed(self, palette):
    for i in range(self.current_tags_layout.count()):
      item = self.current_tags_layout.itemAt(i)
      if item and item.widget():
        tag_block = item.widget()
        TagEditStyleManager.apply_tag_block_style(tag_block, tag_block.is_preset)

    for i in range(self.recent_tags_layout.count()):
      item = self.recent_tags_layout.itemAt(i)
      if item and item.widget():
        tag_block = item.widget()
        theme = TagEditStyleManager.detect_theme()
        tag_block_styles = TagEditStyleManager._styles[theme].get('tag_block', {})
        recent_tag_style = tag_block_styles.get('normal', '') + '\n' + tag_block_styles.get('hover', '')
        tag_block.setStyleSheet(recent_tag_style)

    TagEditStyleManager.apply_edit_line_style(self.edit_line)