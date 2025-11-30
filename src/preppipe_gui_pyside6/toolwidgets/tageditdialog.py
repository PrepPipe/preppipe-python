# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import *
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
  """标签编辑对话框专用样式管理器"""
  _styles = {
    'light': {
      'tag_block': {
        'normal': "QWidget { background-color: rgba(235, 235, 235, 0.95); border: none; border-radius: 12px; padding: 4px 8px; }",
        'hover': "QWidget:hover { background-color: rgba(225, 225, 225, 0.95); border: none; }",
        'custom_hover': "QWidget:hover { background-color: #ffb3b3; border: none; }",
        'preset_normal': "QWidget { background-color: rgba(220, 220, 220, 0.95); border: 1px solid rgba(200, 200, 200, 0.95); border-radius: 12px; padding: 4px 8px; }"
      },
      'edit_line': "background-color: rgba(235, 235, 235, 0.95); border: none; border-radius: 12px; padding: 4px 8px; color: #000000;"
    },
    'dark': {
      'tag_block': {
        'normal': "QWidget { background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: 12px; padding: 4px 8px; }",
        'hover': "QWidget:hover { background-color: rgba(85, 85, 85, 0.95); border: none; }",
        'custom_hover': "QWidget:hover { background-color: #662222; border: none; }",
        'preset_normal': "QWidget { background-color: rgba(40, 40, 40, 0.95); border: 1px solid rgba(60, 60, 60, 0.95); border-radius: 12px; padding: 4px 8px; }"
      },
      'edit_line': "background-color: rgba(65, 65, 65, 0.95); border: none; border-radius: 12px; padding: 4px 8px; color: #CCCCCC;"
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
    """获取指定样式"""
    theme = TagEditStyleManager.detect_theme(palette)
    return TagEditStyleManager._styles[theme].get(style_name, "")

  @staticmethod
  def apply_tag_block_style(widget, is_preset=False, palette=None):
    """应用标签块样式到部件"""
    theme = TagEditStyleManager.detect_theme(palette)
    tag_block_styles = TagEditStyleManager._styles[theme].get('tag_block', {})

    if is_preset:
        # 预设标签使用专门的预设样式，更有区分度
        style = tag_block_styles.get('preset_normal', '')
    else:
        # 自定义标签使用普通和红色悬浮样式
        style = tag_block_styles.get('normal', '') + '\n' + tag_block_styles.get('custom_hover', '')

    widget.setStyleSheet(style)

  @staticmethod
  def apply_edit_line_style(line_edit, palette=None):
    """应用样式到编辑行输入框"""
    style = TagEditStyleManager.get_style('edit_line', palette)
    line_edit.setStyleSheet(style)

class TagBlock(QWidget):
    deleted = Signal(str)

    def __init__(self, tag_text, is_preset=False, parent=None):
      super().__init__(parent)
      self.tag_text = tag_text
      self.is_preset = is_preset
      layout = QHBoxLayout(self)
      layout.setContentsMargins(12, 8, 12, 8)
      layout.setSpacing(6)
      self.label = QLabel(tag_text)
      font = self.label.font()
      font.setPointSize(font.pointSize() + 1)
      self.label.setFont(font)
      layout.addWidget(self.label)

      TagEditStyleManager.apply_tag_block_style(self, is_preset)

      if not is_preset:
          self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
      if not self.is_preset:
          self.deleted.emit(self.tag_text)
          self.deleteLater()

class TagEditDialog(QDialog):
    """标签编辑对话框，编辑素材标签"""
    # 定义信号，当标签修改完成时发出
    tags_changed = Signal(str)  # 参数为asset_id

    _tr_tag_edit_hint = TR_gui_tageditdialog.tr("tageditdialog_tag_edit_hint",
        en="Enter add tag, click remove",
        zh_cn="回车添加标签，点击标签删除",
        zh_hk="回車添加標籤，點擊標籤删除",
    )
    _tr_tag_edit_title = TR_gui_tageditdialog.tr("tageditdialog_tag_edit_title",
        en="Edit tags",
        zh_cn="编辑标签",
        zh_hk="編輯標籤",
    )
    _tr_recent_added = TR_gui_tageditdialog.tr("tageditdialog_recent_added",
        en="Recent added",
        zh_cn="最近添加",
        zh_hk="最近添加",
    )
    def __init__(self, asset_id, parent=None):
      super().__init__(parent)
      self.asset_id = asset_id
      self.has_edited = False
      self.tag_manager = AssetTagManager.get_instance()
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
      self.setWindowTitle(f"{title_text}：{asset_name}")
      self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
      self.setMinimumWidth(400)

      main_layout = QVBoxLayout(self)
      main_layout.setContentsMargins(16, 16, 16, 16)
      main_layout.setSpacing(16)
      main_layout.setSizeConstraint(QLayout.SetDefaultConstraint)

      edit_line_container = QWidget()
      edit_line_layout = QHBoxLayout(edit_line_container)
      edit_line_layout.setContentsMargins(0, 0, 0, 0)
      edit_line_layout.addStretch()
      self.edit_line = QLineEdit()
      TagEditStyleManager.apply_edit_line_style(self.edit_line)
      hint_text = self._tr_tag_edit_hint.get()
      self.edit_line.setPlaceholderText(hint_text)
      self.edit_line.setFixedWidth(200)
      edit_line_layout.addWidget(self.edit_line)
      edit_line_layout.addStretch()
      main_layout.addWidget(edit_line_container)

      self.tags_container = QWidget()
      self.tags_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
      self.tags_layout = FlowLayout(self.tags_container)
      self.tags_layout.setContentsMargins(8, 8, 8, 8)
      self.tags_layout.setSpacing(8)
      main_layout.addWidget(self.tags_container)

      recent_tags_section = QWidget()
      recent_tags_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
      recent_tags_layout = QVBoxLayout(recent_tags_section)
      recent_tags_layout.setContentsMargins(0, 0, 0, 0)
      recent_tags_layout.setSpacing(8)

      self.recent_tags_title = QLabel(self._tr_recent_added.get())
      recent_tags_layout.addWidget(self.recent_tags_title)

      self.recent_tags_container = QWidget()
      self.recent_tags_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
      self.recent_tags_layout = FlowLayout(self.recent_tags_container)
      self.recent_tags_layout.setContentsMargins(8, 4, 8, 4)
      self.recent_tags_layout.setSpacing(8)
      recent_tags_layout.addWidget(self.recent_tags_container)

      main_layout.addWidget(recent_tags_section)

      self.load_tags()
      self.load_recent_tags()
      self.completer = QCompleter()
      self.completer.setCaseSensitivity(Qt.CaseInsensitive)
      self.completer.setCompletionMode(QCompleter.PopupCompletion)
      self.completer.setFilterMode(Qt.MatchContains)
      self.edit_line.setCompleter(self.completer)
      self.update_completer_tags()
      self.edit_line.returnPressed.connect(self.on_edit_return_pressed)
      self.edit_line.editingFinished.connect(self.on_edit_finished)
      self.edit_line.mousePressEvent = self._on_edit_mouse_press

    def load_tags(self):
      while self.tags_layout.count() > 0:
        item = self.tags_layout.takeAt(0)
        if item.widget():
          item.widget().deleteLater()

      asset_tags = self.tag_manager.get_asset_tags(self.asset_id)

      preset_tags = []
      custom_tags = []

      for semantic_tag in asset_tags:
            display_tag = self.tag_manager.get_tag_display_text(semantic_tag)
            is_preset = self.tag_manager.is_preset_tag(semantic_tag)
            if is_preset:
                preset_tags.append((display_tag, semantic_tag))
            else:
                custom_tags.append((display_tag, semantic_tag))

      for display_tag, _ in sorted(preset_tags):
          self.add_tag_block(display_tag, True)

      for display_tag, _ in sorted(custom_tags):
          self.add_tag_block(display_tag, False)

    def load_recent_tags(self):
      """加载并显示最近添加的标签"""
      while self.recent_tags_layout.count() > 0:
        item = self.recent_tags_layout.takeAt(0)
        if item.widget():
          item.widget().deleteLater()

      recent_display_tags = self.tag_manager.get_recent_tags_display()

      for display_tag in recent_display_tags:
          self.add_recent_tag_block(display_tag)

      self.recent_tags_title.setVisible(True)

    def add_recent_tag_block(self, tag_text):
      """添加最近标签块"""
      if not tag_text.strip():
        return

      tag_block = TagBlock(tag_text, is_preset=False)
      tag_block.is_recent = True

      tag_block.mousePressEvent = lambda event, b=tag_block: self.on_recent_tag_clicked(b)

      tag_block.setCursor(Qt.PointingHandCursor)

      theme = TagEditStyleManager.detect_theme()
      tag_block_styles = TagEditStyleManager._styles[theme].get('tag_block', {})
      recent_tag_style = tag_block_styles.get('normal', '') + '\n' + tag_block_styles.get('hover', '')
      tag_block.setStyleSheet(recent_tag_style)

      self.recent_tags_layout.addWidget(tag_block)

    def add_tag_block(self, tag_text, is_preset=False):
      tag_block = TagBlock(tag_text, is_preset)
      tag_block.deleted.connect(self.on_tag_deleted)
      self.tags_layout.addWidget(tag_block)
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
      if self.tag_manager.remove_tag_from_asset(self.asset_id, semantic_tag):
        self.has_edited = True
        QTimer.singleShot(0, self._adjust_dialog_size)

    def on_edit_return_pressed(self):
      new_text = self.edit_line.text()
      if new_text:
        self._add_tag(new_text)
        self.edit_line.clear()
      self.edit_line.setFocus()

    def on_recent_tag_clicked(self, tag_block):
      """处理最近标签点击并添加标签"""
      self.recent_tags_layout.removeWidget(tag_block)
      self.recent_tags_layout.insertWidget(0, tag_block)
      self._add_tag(tag_block.tag_text)

    def _add_tag(self, tag_text):
      """添加标签的核心逻辑，供输入框回车和最近标签点击共同使用"""

      all_text = self.tag_manager.get_tr_all()
      if tag_text == all_text:
        return

      new_semantic = self.tag_manager.get_tag_semantic(tag_text)

      tag_updated,recent_updated=self.tag_manager.add_tag_to_asset(self.asset_id, new_semantic)
      if tag_updated:
        self.has_edited = True
        self.add_tag_block(tag_text)
      if recent_updated:
        self.load_recent_tags()

    def on_edit_finished(self):
      if self.edit_line.text().strip():
        self.on_edit_return_pressed()

    def keyPressEvent(self, event):
      if event.key() == Qt.Key_Escape:
        self.accept()
      else:
        super().keyPressEvent(event)

    def apply_changes(self):
      if self.has_edited:
        self.tags_changed.emit(self.asset_id)

    def closeEvent(self, event):
      self.apply_changes()
      super().closeEvent(event)

    def accept(self):
      self.apply_changes()
      super().accept()

    def _adjust_dialog_size(self):
      self.tags_layout.update()
      self.updateGeometry()
      self.adjustSize()

    def _on_edit_mouse_press(self, event):
      QLineEdit.mousePressEvent(self.edit_line, event)
      if self.completer:
        self.completer.complete()

    def changeEvent(self, event):
      """处理主题切换事件"""
      if event.type() == QEvent.PaletteChange:
        self._on_palette_changed(self.palette())
      super().changeEvent(event)

    def _on_palette_changed(self, palette):
      """在主题切换时更新所有TagBlock的样式"""
      for i in range(self.tags_layout.count()):
        item = self.tags_layout.itemAt(i)
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