from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from preppipe_gui_pyside6.util.asset_widget_style import StyleManager
from ..componentwidgets.flowlayout import FlowLayout
from preppipe.util.imagepack import ImagePack
from ..util.tagmanager import TagManager

TR_gui_tageditdialog=TranslationDomain("gui_tageditdialog")

class TagBlock(QWidget):
    deleted = Signal(str)

    def __init__(self, tag_text, parent=None):
      super().__init__(parent)
      self.tag_text = tag_text
      layout = QHBoxLayout(self)
      layout.setContentsMargins(12, 8, 12, 8)
      layout.setSpacing(6)
      self.label = QLabel(tag_text)
      font = self.label.font()
      font.setPointSize(font.pointSize() + 1)
      self.label.setFont(font)
      layout.addWidget(self.label)
      StyleManager.apply_tag_block_style(self)
      self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
      self.deleted.emit(self.tag_text)
      self.deleteLater()

class TagEditDialog(QDialog):
    """标签编辑对话框，编辑素材标签"""
    _tr_tag_edit_hint = TR_gui_tageditdialog.tr("tageditdialog_tag_edit_hint",
        en="Enter to add, click to remove",
        zh_cn="回车添加标签，点击标签删除",
        zh_hk="回車添加標籤，點擊標籤删除",
    )
    _tr_tag_edit_title = TR_gui_tageditdialog.tr("tageditdialog_tag_edit_title",
        en="Edit Tags",
        zh_cn="编辑标签",
        zh_hk="編輯標籤",
    )
    def __init__(self, asset_id, asset_browser, parent=None):
      super().__init__(parent)
      self.asset_id = asset_id
      self.asset_browser = asset_browser
      self.has_edited = False
      self.tag_manager = TagManager.get_instance()
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
      self.edit_line.setStyleSheet(StyleManager.get_style('edit_line'))
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

      self.load_tags()
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
      display_tags = list(self.tag_manager.translate_tags(asset_tags))

      for tag in sorted(display_tags):
        self.add_tag_block(tag)

    def add_tag_block(self, tag_text):
      if not tag_text.strip():
        return
      tag_block = TagBlock(tag_text)
      tag_block.deleted.connect(self.on_tag_deleted)
      self.tags_layout.addWidget(tag_block)
      QTimer.singleShot(0, self._adjust_dialog_size)

    def update_completer_tags(self):
      tags_dict = self.tag_manager.get_tags_dict()
      all_tags = set()
      for tags in tags_dict.values():
        all_tags.update(tags)
      display_tags = self.tag_manager.translate_tags(all_tags)
      tags_model = QStringListModel(sorted(display_tags))
      self.completer.setModel(tags_model)

    def on_tag_deleted(self, tag_text):
      semantic_tag = self.tag_manager.get_tag_semantic(tag_text)
      if self.tag_manager.remove_tag_from_asset(self.asset_id, semantic_tag):
        self.has_edited = True
        QTimer.singleShot(0, self._adjust_dialog_size)

    def on_edit_return_pressed(self):
      new_text = self.edit_line.text().strip()
      if new_text:
        all_text = self.tag_manager.get_tr_all()
        if new_text == all_text:
          self.edit_line.clear()
          self.edit_line.setFocus()
          return

        new_semantic = self.tag_manager.get_tag_semantic(new_text)
        asset_tags = self.tag_manager.get_asset_tags(self.asset_id)

        if new_semantic in asset_tags:
          # 标签已存在，刷新显示以确保翻译正确
          self.has_edited = True
          self.load_tags()
        else:
          # 添加新标签
          self.tag_manager.add_tag_to_asset(self.asset_id, new_semantic)
          self.has_edited = True
          self.add_tag_block(new_text)

      self.edit_line.clear()
      self.edit_line.setFocus()

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
        self.asset_browser.update_asset_card_tags(self.asset_id)
        self.asset_browser.load_tags()

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