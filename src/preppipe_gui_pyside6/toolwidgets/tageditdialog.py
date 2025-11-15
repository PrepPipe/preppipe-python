from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from preppipe_gui_pyside6.util.asset_widget_style import StyleManager
from ..componentwidgets.flowlayout import FlowLayout
from preppipe.util.imagepack import ImagePack
from ..util.tagmanager import TagManager

class TagBlock(QWidget):
    """自定义标签块组件"""
    deleted = Signal(str)  # 标签被删除时发出信号

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
      """点击整个标签块时删除标签"""
      self.deleted.emit(self.tag_text)
      self.deleteLater()

class TagEditDialog(QDialog):
    """标签编辑对话框，用于编辑素材的标签"""
    def __init__(self, asset_id, asset_browser, parent=None):
      super().__init__(parent)
      self.asset_id = asset_id
      self.asset_browser = asset_browser
      self.has_edited = False  # 编辑状态标志
      self.tag_manager = TagManager.get_instance()
      # 获取素材名称
      asset_manager = AssetManager.get_instance()
      asset = asset_manager.get_asset(asset_id)
      asset_name = asset_id  # 默认使用asset_id
      if isinstance(asset, ImagePack):
        descriptor = ImagePack.get_descriptor_by_id(asset_id)
        if descriptor:
          name_obj = descriptor.get_name()
          if hasattr(name_obj, 'get'):
              asset_name = name_obj.get()
          elif name_obj:
              asset_name = name_obj
      self.setWindowTitle(f"{self.asset_browser.tag_manager.get_tr_tag_edit_title()}：{asset_name}")
      self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
      self.setMinimumWidth(400)

      main_layout = QVBoxLayout(self)
      main_layout.setContentsMargins(16, 16, 16, 16)
      main_layout.setSpacing(16)

      # 启用布局的大小约束以确保对话框可以根据内容调整大小
      main_layout.setSizeConstraint(QLayout.SetMinimumSize)
      main_layout.setSizeConstraint(QLayout.SetDefaultConstraint)

      edit_line_container = QWidget()
      edit_line_layout = QHBoxLayout(edit_line_container)
      edit_line_layout.setContentsMargins(0, 0, 0, 0)
      edit_line_layout.addStretch()

      self.edit_line = QLineEdit()
      self.edit_line.setStyleSheet(StyleManager.get_style('edit_line'))
      # 这里仍使用asset_browser中的变量，因为它与界面交互相关
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

      original_mouse_press = self.edit_line.mousePressEvent
      self.edit_line.mousePressEvent = lambda event, orig=original_mouse_press, completer=self.completer: (orig(event), completer.complete() if completer else None)

    def load_tags(self):
      """加载当前资产的标签"""
      while self.tags_layout.count() > 0:
        item = self.tags_layout.takeAt(0)
        if item.widget():
          item.widget().deleteLater()
        del item

      # 使用标签管理器获取资产的标签并转换为显示文本
      asset_tags = self.tag_manager.get_asset_tags(self.asset_id)
      display_tags = list(self.tag_manager.translate_tags(asset_tags))

      for tag in sorted(display_tags):
        self.add_tag_block(tag)

    def add_tag_block(self, tag_text):
      """添加一个标签块"""
      if not tag_text.strip():
        return
      tag_block = TagBlock(tag_text)
      tag_block.deleted.connect(self.on_tag_deleted)
      # 添加到流式布局中
      self.tags_layout.addWidget(tag_block)
      # 使用QTimer延迟更新对话框大小，确保Qt有足够时间完成内部布局计算
      QTimer.singleShot(0, self._adjust_dialog_size)

    def update_completer_tags(self):
      """更新补全的标签列表"""
      # 使用标签管理器获取所有可用标签
      tags_dict = self.tag_manager.get_tags_dict()
      all_tags = set()
      for tags in tags_dict.values():
        all_tags.update(tags)
      # 转换为显示文本
      display_tags = self.tag_manager.translate_tags(all_tags)
      tags_model = QStringListModel(sorted(display_tags))
      self.completer.setModel(tags_model)

    def on_tag_deleted(self, tag_text):
      """处理标签删除事件"""
      # 获取标签的语义标识
      semantic_tag = self.tag_manager.get_tag_semantic(tag_text)
      
      # 从资产中移除标签
      if self.tag_manager.remove_tag_from_asset(self.asset_id, semantic_tag):
        self.has_edited = True
        # 使用QTimer延迟更新对话框大小，确保Qt有足够时间完成内部布局计算
        QTimer.singleShot(0, self._adjust_dialog_size)

    def on_edit_return_pressed(self):
      """处理编辑框回车事件"""
      new_text = self.edit_line.text().strip()
      if new_text:
        if new_text == self.asset_browser.tag_manager.get_tr_all():
          self.edit_line.clear()
          self.edit_line.setFocus()
          return

        # 获取新标签的语义标识
        new_semantic = self.tag_manager.get_tag_semantic(new_text)

        # 检查标签是否已存在
        if new_semantic in self.tag_manager.get_asset_tags(self.asset_id):
          self.edit_line.clear()
          self.edit_line.setFocus()
          return

        # 添加标签到资产
        self.tag_manager.add_tag_to_asset(self.asset_id, new_semantic)
        self.has_edited = True
        self.add_tag_block(new_text)

      self.edit_line.clear()
      self.edit_line.setFocus()

    def on_edit_finished(self):
      """处理编辑框完成编辑事件"""
      if self.edit_line.text().strip():
        self.on_edit_return_pressed()

    def keyPressEvent(self, event):
      """处理键盘事件"""
      if event.key() == Qt.Key_Escape:
        self.accept()
      else:
        super().keyPressEvent(event)

    def apply_changes(self):
      """应用所有更改到资产浏览器"""
      if self.has_edited:
        # 只更新当前被编辑资产的标签，而不是所有资产
        self.asset_browser.update_thumbnail_tags(self.asset_id)
        # 加载标签列表以更新分类视图
        self.asset_browser.load_tags()

    def closeEvent(self, event):
      """处理对话框关闭事件"""
      self.apply_changes()
      super().closeEvent(event)

    def accept(self):
      """处理对话框确认事件"""
      self.apply_changes()
      super().accept()

    def _adjust_dialog_size(self):
      """调整对话框大小的辅助方法，用于延迟调用以确保正确计算"""
      # 先更新布局和几何信息
      self.tags_layout.update()
      self.updateGeometry()
      # 然后调整对话框大小
      self.adjustSize()