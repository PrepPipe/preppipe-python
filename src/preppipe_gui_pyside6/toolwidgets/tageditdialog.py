from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from preppipe_gui_pyside6.util.asset_widget_style import StyleManager
from ..componentwidgets.flowlayout import FlowLayout
from preppipe.util.imagepack import ImagePack

class TagBlock(QWidget):
    """自定义标签块组件"""
    deleted = Signal(str)  # 标签被删除时发出信号

    def __init__(self, tag_text, parent=None):
      super().__init__(parent)
      self.tag_text = tag_text

      # 设置布局，增加边距使标签块变大
      layout = QHBoxLayout(self)
      layout.setContentsMargins(12, 8, 12, 8)
      layout.setSpacing(6)

      # 创建标签文本，使用更大的字体
      self.label = QLabel(tag_text)
      font = self.label.font()
      font.setPointSize(font.pointSize() + 1)
      self.label.setFont(font)
      layout.addWidget(self.label)

      # 使用样式管理器设置标签块样式
      self.setStyleSheet(StyleManager.get_tag_block_style())

      # 设置鼠标形状为手形，提示可点击
      self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
      """点击整个标签块时删除标签"""
      # 直接触发删除信号并删除自身
      self.deleted.emit(self.tag_text)
      self.deleteLater()

class TagEditDialog(QDialog):
    """标签编辑对话框，用于编辑素材的标签"""
    def __init__(self, asset_id, asset_browser, parent=None):
      super().__init__(parent)
      self.asset_id = asset_id
      self.asset_browser = asset_browser
      self.has_edited = False  # 编辑状态标志
      # 获取素材名称
      asset_manager = AssetManager.get_instance()
      asset = asset_manager.get_asset(asset_id)
      asset_name = asset_id  # 默认使用asset_id
      if isinstance(asset, ImagePack):
        descriptor = ImagePack.get_descriptor_by_id(asset_id)
        if descriptor:
            # 使用get_name()方法获取友好名称
            name_obj = descriptor.get_name()
            if hasattr(name_obj, 'get'):
                # 如果是Translatable对象
                asset_name = name_obj.get()
            elif name_obj:
                # 如果是普通字符串
                asset_name = name_obj
      # 设置窗口标题格式：{标签编辑的当前语言翻译.get()}：{assetname}
      self.setWindowTitle(f"{self.asset_browser._tr_tag_edit_title.get()}：{asset_name}")
      # 设置对话框大小策略，允许根据内容自适应调整高度
      self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
      # 设置最小宽度，但不固定高度，让对话框能根据内容自动调整
      self.setMinimumWidth(400)
      # 创建主布局
      main_layout = QVBoxLayout(self)
      main_layout.setContentsMargins(16, 16, 16, 16)
      main_layout.setSpacing(16)
      # 顶部添加编辑框（居中）
      edit_line_container = QWidget()
      edit_line_layout = QHBoxLayout(edit_line_container)
      edit_line_layout.setContentsMargins(0, 0, 0, 0)
      edit_line_layout.addStretch()
      self.edit_line = QLineEdit()
      # 使用样式管理器设置输入框样式
      self.edit_line.setStyleSheet(StyleManager.get_style('edit_line'))
      self.edit_line.setPlaceholderText(self.asset_browser._tr_tag_edit_current_hint.get())
      self.edit_line.setFixedWidth(200)  # 设置固定宽度以便更好地居中
      edit_line_layout.addWidget(self.edit_line)
      edit_line_layout.addStretch()
      main_layout.addWidget(edit_line_container)
      # 中间添加标签容器（使用FlowLayout）
      self.tags_container = QWidget()
      self.tags_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
      self.tags_layout = FlowLayout(self.tags_container)
      self.tags_layout.setContentsMargins(8, 8, 8, 8)
      self.tags_layout.setSpacing(8)
      # 添加标签容器到主布局，不设置伸展因子让其根据内容自适应高度
      main_layout.addWidget(self.tags_container)

      # 移除确认按钮，逻辑移至对话框关闭时

      # 加载当前标签
      self.load_tags()

      # 创建自动完成功能
      self.completer = QCompleter()
      self.completer.setCaseSensitivity(Qt.CaseInsensitive)  # 不区分大小写
      self.completer.setCompletionMode(QCompleter.PopupCompletion)  # 弹出式完成模式
      self.completer.setFilterMode(Qt.MatchContains)  # 包含匹配模式，更灵活
      self.edit_line.setCompleter(self.completer)
      # 更新自动完成的标签列表
      self.update_completer_tags()
      # 连接信号
      self.edit_line.returnPressed.connect(self.on_edit_return_pressed)
      self.edit_line.editingFinished.connect(self.on_edit_finished)
      # 保存原始mousePressEvent方法引用
      original_mouse_press = self.edit_line.mousePressEvent
      # 重写mousePressEvent以处理点击事件并显示补全列表
      self.edit_line.mousePressEvent = lambda event, orig=original_mouse_press, completer=self.completer: (orig(event), completer.complete() if completer else None)

    def load_tags(self):
      """加载当前资产的标签"""
      # 清除现有的标签块
      while self.tags_layout.count() > 0:
        item = self.tags_layout.takeAt(0)
        if item.widget():
          item.widget().deleteLater()
        del item
      tags_dict = self.asset_browser.get_tags_dict()
      asset_tags = tags_dict.get(self.asset_id, set())
      # 转换标签为显示文本
      display_tags = []
      for tag in asset_tags:
        if tag in self.asset_browser.semantic_to_tag_text:
          display_tags.append(self.asset_browser.semantic_to_tag_text[tag])
        else:
          display_tags.append(tag)
      # 添加标签块
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
      # 强制布局更新
      self.tags_layout.update()

    def show_edit_line(self, text=""):
      """设置编辑框文本"""
      self.edit_line.setText(text)

    def update_completer_tags(self):
      """更新自动完成的标签列表"""
      all_tags = set(self.asset_browser.assets_by_tag.keys())

      # 创建字符串列表模型
      tags_model = QStringListModel(sorted(all_tags))
      self.completer.setModel(tags_model)

    def on_tag_deleted(self, tag_text):
      """处理标签删除事件"""
      # 从字典中移除
      tags_dict = self.asset_browser.get_tags_dict()
      if self.asset_id in tags_dict:
        semantic_tag = self.asset_browser.tag_text_to_semantic.get(tag_text, tag_text)
        if semantic_tag in tags_dict[self.asset_id]:
          tags_dict[self.asset_id].remove(semantic_tag)

          # 如果标签集为空，删除该资产的条目
          if not tags_dict[self.asset_id]:
            del tags_dict[self.asset_id]

          # 设置编辑标志
          self.has_edited = True

          # 保存到字典，但不同步更新
          self.asset_browser.save_tags_dict(tags_dict)

          # 更新自动完成列表
          self.update_completer_tags()

    def on_edit_return_pressed(self):
      """处理编辑框回车事件"""
      new_text = self.edit_line.text().strip()
      if new_text:
        # 排除"全部"标签
        if new_text == self.asset_browser._tr_all.get():

          self.edit_line.clear()
          self.edit_line.setFocus()
          return

        # 获取新标签的语义标识
        new_semantic = new_text
        # 检查新标签是否与预设标签的显示文本匹配
        for tag_text, semantic in self.asset_browser.tag_text_to_semantic.items():
          if tag_text == new_text:
            new_semantic = semantic
            break

        # 检查标签是否已存在
        tags_dict = self.asset_browser.get_tags_dict()
        # 由于asset_id在全局范围内保证存在，可以直接访问
        if new_semantic in tags_dict[self.asset_id]:
          # 标签已存在，清空编辑框并保持焦点
          self.edit_line.clear()
          self.edit_line.setFocus()
          return

        # 添加新标签
        tags_dict[self.asset_id].add(new_semantic)

        # 设置编辑标志
        self.has_edited = True

        # 保存到字典，但不同步更新
        self.asset_browser.save_tags_dict(tags_dict)

        # 更新自动完成列表
        self.update_completer_tags()

        # 更新界面
        self.add_tag_block(new_text)

      # 清空编辑框并保持焦点，方便用户继续添加标签
      self.edit_line.clear()
      self.edit_line.setFocus()

    def on_edit_finished(self):
      """处理编辑框完成编辑事件"""
      # 不再隐藏编辑框，因为对话框关闭时会自然消失
      # 如果有内容，按回车处理逻辑添加标签
      if self.edit_line.text().strip():
        self.on_edit_return_pressed()

    def keyPressEvent(self, event):
      """处理键盘事件"""
      # ESC键关闭对话框
      if event.key() == Qt.Key_Escape:
        self.accept()
      # 按Enter键直接处理，不再设置焦点
      elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
        super().keyPressEvent(event)
      else:
        super().keyPressEvent(event)

    def closeEvent(self, event):
      """处理对话框关闭事件，执行之前确认按钮的逻辑"""
      # 如果有编辑操作，同步更新
      if self.has_edited:
        self.asset_browser.update_thumbnail_tags()
        # 重新加载标签以确保数据完全同步
        self.asset_browser.load_tags()
      super().closeEvent(event)

    def accept(self):
      """重写accept方法，执行之前确认按钮的逻辑"""
      # 如果有编辑操作，同步更新
      if self.has_edited:
        self.asset_browser.update_thumbnail_tags()
        # 重新加载标签以确保数据完全同步
        self.asset_browser.load_tags()
      super().accept()