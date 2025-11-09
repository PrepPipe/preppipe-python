# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import os
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from preppipe.language import *
from preppipe.assets.assetmanager import AssetManager
from preppipe.util.imagepack import ImagePack, ImagePackDescriptor
from ..toolwidgetinterface import *
from ..forms.generated.ui_assetbrowserwidget import Ui_AssetBrowserWidget
from ..settingsdict import SettingsDict
from ..util.asset_thumbnail import generate_thumbnail_from_imagepack

TR_gui_tool_assetbrowser = TranslationDomain("gui_tool_assetbrowser")

class AssetBrowserWidget(QWidget, ToolWidgetInterface):
  ui: Ui_AssetBrowserWidget

  # 设置字典中存储标签的键
  SETTINGS_KEY_TAGS = "persistent/assetmanager/custom_asset_tags"
  SETTINGS_KEY_CURRENT_TAG = "persistent/assetmanager/current_tag"
  # 当前选中的标签
  current_tag: str
  # 标签到素材的映射字典，格式：{tag_name: {asset_id: asset_object}}
  assets_by_tag: dict[str, dict[str, object]]
  # 缩略图缓存字典
  thumbnail_cache: dict[str, str]
  # 用于异步加载的线程池
  thread_pool: QThreadPool
  # 缩略图容器字典，用于快速访问
  thumbnail_items: dict[str, QWidget]
  # 所有素材ID列表
  all_asset_ids: list[str]



  _tr_select_tag = TR_gui_tool_assetbrowser.tr("select_tag",
    en="Select a tag",
    zh_cn="选择一个标签",
    zh_hk="選擇一個標籤",
  )

  _tr_toolname_assetbrowser = TR_gui_tool_assetbrowser.tr("toolname_assetbrowser",
    en="Asset Browser",
    zh_cn="素材浏览器",
    zh_hk="素材瀏覽器",
  )

  _tr_tooltip_assetbrowser = TR_gui_tool_assetbrowser.tr("tooltip_assetbrowser",
    en="Browse and manage your assets with thumbnails",
    zh_cn="浏览和管理带有缩略图的素材",
    zh_hk="瀏覽和管理帶有縮圖的素材",
  )

  _tr_all = TR_gui_tool_assetbrowser.tr("all",
    en="All",
    zh_cn="全部",
    zh_hk="全部",
  )

  _tr_background = TR_gui_tool_assetbrowser.tr("background",
    en="Background",
    zh_cn="背景",
    zh_hk="背景",
  )

  _tr_character = TR_gui_tool_assetbrowser.tr("character",
    en="Character",
    zh_cn="立绘",
    zh_hk="立繪",
  )

  _tr_other = TR_gui_tool_assetbrowser.tr("other",
    en="Other",
    zh_cn="其他",
    zh_hk="其他",
  )

  _tr_no_tags = TR_gui_tool_assetbrowser.tr("no_tags",
    en="No Tags",
    zh_cn="无标签",
    zh_hk="無標籤",
  )

  _tr_tag_edit_hint = TR_gui_tool_assetbrowser.tr("tag_edit_hint",
    en="Click tag to edit, press Delete to remove",
    zh_cn="单击标签编辑，按Delete键删除",
    zh_hk="單擊標籤編輯，按Delete鍵删除",
  )

  def __init__(self, parent: QWidget):
    super(AssetBrowserWidget, self).__init__(parent)
    self.ui = Ui_AssetBrowserWidget()
    self.ui.setupUi(self)
    self.current_tag = ""
    self.assets_by_tag = {}
    self.thumbnail_cache = {}
    self.thread_pool = QThreadPool()
    self.thumbnail_items = {}
    self.all_asset_ids = []
    # 上次打开的素材ID
    self.last_opened_asset_id = None
    # 用于存储标签文本与其语义标识的映射
    self.tag_text_to_semantic = {}
    # 用于存储语义标识与其标签文本的映射
    self.semantic_to_tag_text = {}
    # 用于存储标签按钮的引用
    self.tag_buttons = {}

    # 字体缓存 - 预先创建并缓存字体以提高性能
    self.tags_font = QFont()
    self.tags_font.setPointSizeF(self.tags_font.pointSizeF() * 0.9)
    # 创建名称标签使用的加粗字体缓存
    self.name_font = QFont()
    self.name_font.setWeight(QFont.Weight.Bold)
    # 缓存字体度量以避免重复计算
    self.tags_font_metrics = QFontMetrics(self.tags_font)
    self.name_font_metrics = QFontMetrics(self.name_font)
    # 正常状态样式 - 透明的淡雅灰白色调卡牌效果
    self.normal_style = "background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(245, 245, 245, 0.8), stop:1 rgba(232, 232, 232, 0.8)); border: 1px solid rgba(208, 208, 208, 0.8); border-radius: 8px; padding: 2px;"
    # 悬浮状态样式 - 稍深一点的透明灰白色调
    self.hover_style = "background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(240, 240, 240, 0.8), stop:1 rgba(224, 224, 224, 0.8)); border: 1px solid rgba(176, 176, 176, 0.8); border-radius: 8px; padding: 2px;"
    # 选中状态样式 - 透明的淡雅浅灰色调
    self.selected_style = "background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(232, 232, 232, 0.85), stop:1 rgba(224, 224, 224, 0.85)); border: 2px solid rgba(160, 160, 160, 0.85); border-radius: 8px; padding: 1px;"
    # 选中且悬浮状态样式 - 稍深的透明灰色调
    self.selected_hover_style = "background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(229, 229, 229, 0.85), stop:1 rgba(216, 216, 216, 0.85)); border: 2px solid rgba(128, 128, 128, 0.85); border-radius: 8px; padding: 1px;"

    # 绑定文本
    self.bind_text(self.ui.categoryTitleLabel.setText, self._tr_select_tag)

    # 连接信号槽
    self.ui.categoriesListWidget.itemClicked.connect(self.on_tag_selected)

    # 禁用横向滚动条
    self.ui.thumbnailsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    # 允许垂直滚动条根据需要显示
    self.ui.thumbnailsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    # 直接使用UI文件中定义的FlowLayout
    self.flow_layout = self.ui.thumbnailsFlowLayout
    self.flow_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    # 设置更大的垂直间距以优化卡片之间的行距
    self.flow_layout.setVerticalSpacing(15)

    # 连接大小变化信号，当窗口大小改变时重新调整布局
    self.ui.thumbnailsScrollAreaWidgetContents.resizeEvent = self._on_container_resized

    # 加载所有素材和标签
    self.load_all_assets()
    self.load_tags()

    # 从设置中加载之前保存的标签选择（考虑多语言情况）
    settings = SettingsDict.instance()
    saved_tag = settings.get(self.SETTINGS_KEY_CURRENT_TAG)
    if saved_tag:
      # 识别保存标签的语义类别（不依赖于语言）
      tag_semantic_category = None
      if saved_tag in ["All", "全部"]:
        tag_semantic_category = "all"
      elif saved_tag in ["Background", "背景"]:
        tag_semantic_category = "background"
      elif saved_tag in ["Character", "立绘", "立繪"]:
        tag_semantic_category = "character"
      elif saved_tag in ["Other", "其他"]:
        tag_semantic_category = "other"
      else:
        # 自定义标签
        tag_semantic_category = "custom"

      # 基于语义类别查找并选择对应的标签
      target_tag = None
      if tag_semantic_category != "custom":
        # 预定义标签
        if tag_semantic_category == "all":
          target_tag = self._tr_all.get()
        elif tag_semantic_category == "background":
          target_tag = self._tr_background.get()
        elif tag_semantic_category == "character":
          target_tag = self._tr_character.get()
        elif tag_semantic_category == "other":
          target_tag = self._tr_other.get()
      else:
        # 自定义标签，直接使用保存的文本
        target_tag = saved_tag

      # 查找并选中对应的标签
      if target_tag:
        for i in range(self.ui.categoriesListWidget.count()):
          item = self.ui.categoriesListWidget.item(i)
          if item and item.text() == target_tag:
            self.ui.categoriesListWidget.setCurrentItem(item)
            # 触发标签选择事件
            self.on_tag_selected(item)
            break

  def load_all_assets(self):
    """加载所有素材ID"""
    asset_manager = AssetManager.get_instance()
    self.all_asset_ids = []

    for asset_id, asset_info in asset_manager._assets.items():
      asset = asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
        self.all_asset_ids.append(asset_id)

  def load_tags(self):
    """从设置字典中加载标签并统一合并归类"""
    settings = SettingsDict.instance()
    tags_dict = settings.get(self.SETTINGS_KEY_TAGS, {})

    # 初始化标签到素材的映射字典
    self.assets_by_tag = {}

    # 从assetmanager获取所有素材
    asset_manager = AssetManager.get_instance()

    # 首先根据素材类型进行分类并建立预设标签的映射关系
    # 初始化预设标签的语义映射
    background_tag = self._tr_background.get()
    character_tag = self._tr_character.get()
    other_tag = self._tr_other.get()

    # 保存语义映射关系
    self.tag_text_to_semantic[background_tag] = "background"
    self.tag_text_to_semantic[character_tag] = "character"
    self.tag_text_to_semantic[other_tag] = "other"
    self.semantic_to_tag_text["background"] = background_tag
    self.semantic_to_tag_text["character"] = character_tag
    self.semantic_to_tag_text["other"] = other_tag

    # 初始化预设标签的素材映射
    self.assets_by_tag[background_tag] = {}
    self.assets_by_tag[character_tag] = {}
    self.assets_by_tag[other_tag] = {}

    # 根据素材类型自动分类
    for asset_id in self.all_asset_ids:
      try:
        asset = asset_manager.get_asset(asset_id)
        if isinstance(asset, ImagePack):
          descriptor = ImagePack.get_descriptor_by_id(asset_id)
          if descriptor:
            pack_type = descriptor.get_image_pack_type()

            # 根据类型确定标签
            if pack_type == ImagePackDescriptor.ImagePackType.BACKGROUND:
              category_tag = background_tag
              semantic = "background"
            elif pack_type == ImagePackDescriptor.ImagePackType.CHARACTER:
              category_tag = character_tag
              semantic = "character"
            else:
              category_tag = other_tag
              semantic = "other"

            # 检查是否有自定义标签设置
            has_custom_tags = asset_id in tags_dict and tags_dict[asset_id]

            # 添加到对应标签的素材映射
            # 即使有自定义标签，也添加到预设标签的映射中，以便在预设标签下也能找到该素材
            self.assets_by_tag[category_tag][asset_id] = asset

            # 自动为资产添加类型标签，但仅在没有自定义标签的情况下
            if not has_custom_tags:
              if asset_id not in tags_dict:
                tags_dict[asset_id] = set()
              # 使用语义标识存储
              tags_dict[asset_id].add(semantic)
      except Exception:
        continue

    # 处理用户自定义标签 - 首先清理和规范化标签字典
    cleaned_tags_dict = {}
    for asset_id, tags in tags_dict.items():
      cleaned_tags = set()
      # 确保tags是集合类型
      tag_set = set(tags) if isinstance(tags, (list, set)) else {tags}

      for tag in tag_set:
        # 检查标签是否是显示文本，如果是则转换为语义标识
        if tag in self.tag_text_to_semantic:
          # 是显示文本，转换为语义标识
          semantic_tag = self.tag_text_to_semantic[tag]
          cleaned_tags.add(semantic_tag)
        elif tag in self.semantic_to_tag_text or not tag in self.tag_text_to_semantic:
          # 已经是语义标识或自定义标签，直接使用
          cleaned_tags.add(tag)

      if cleaned_tags:
        cleaned_tags_dict[asset_id] = cleaned_tags

    # 使用清理后的标签字典更新tags_dict
    tags_dict = cleaned_tags_dict

    # 现在处理标签到素材的映射
    for asset_id, tags in tags_dict.items():
      try:
        asset = asset_manager.get_asset(asset_id)
        if isinstance(asset, ImagePack):
          for tag in tags:
            # 转换语义标识为当前语言的标签文本
            if tag in self.semantic_to_tag_text:
              display_tag = self.semantic_to_tag_text[tag]
            else:
              # 自定义标签保持原样
              display_tag = tag

            # 确保标签存在于assets_by_tag中
            if display_tag not in self.assets_by_tag:
              self.assets_by_tag[display_tag] = {}

            # 添加素材到标签映射
            self.assets_by_tag[display_tag][asset_id] = asset
      except Exception:
        continue

    # 保存更新后的标签字典
    self.save_tags_dict(tags_dict)

    # 显示标签列表
    self.update_tags_list()

    # 尝试加载上次选中的标签，如果不存在则默认选择全部
    settings = SettingsDict.instance()
    saved_tag = settings.get(self.SETTINGS_KEY_CURRENT_TAG, self._tr_all.get())

    # 检查saved_tag是否是语义标识
    if saved_tag in self.semantic_to_tag_text:
      # 是语义标识，获取当前语言的标签文本
      tag_text = self.semantic_to_tag_text[saved_tag]
      # 确保使用语义标识调用
      semantic_tag = saved_tag
    else:
      # 可能是旧版保存的标签文本，尝试转换为语义标识
      semantic_tag = self.tag_text_to_semantic.get(saved_tag, "custom")
      tag_text = saved_tag
      # 如果找不到对应的语义标识，并且不是"全部"标签，则使用默认标签
      if semantic_tag == "custom" and saved_tag != self._tr_all.get():
        semantic_tag = "all"
        tag_text = self._tr_all.get()

    # 更新设置，确保保存的是语义标识
    settings[self.SETTINGS_KEY_CURRENT_TAG] = semantic_tag

    self.current_tag = tag_text
    self.ui.categoryTitleLabel.setText(self.current_tag)
    self.load_thumbnails_for_tag(semantic_tag)

    # 选中对应的标签项
    # 查找与当前显示的标签文本匹配的列表项
    tag_found = False
    for i in range(self.ui.categoriesListWidget.count()):
      item = self.ui.categoriesListWidget.item(i)
      if item.text() == self.current_tag:
        self.ui.categoriesListWidget.setCurrentItem(item)
        tag_found = True
        break

    # 如果没有找到，尝试使用语义标识对应的标签文本
    if not tag_found and semantic_tag in self.semantic_to_tag_text:
        target_tag_text = self.semantic_to_tag_text[semantic_tag]
        for i in range(self.ui.categoriesListWidget.count()):
          item = self.ui.categoriesListWidget.item(i)
          if item.text() == target_tag_text:
            self.ui.categoriesListWidget.setCurrentItem(item)
            self.current_tag = target_tag_text
            self.ui.categoryTitleLabel.setText(self.current_tag)
            break

  def update_tags_list(self):
    """更新标签列表显示，按分类组织标签，并建立语义映射关系，同时显示标签对应的素材个数"""
    # 确保全部标签的映射关系存在
    all_text = self._tr_all.get()
    self.tag_text_to_semantic[all_text] = "all"
    self.semantic_to_tag_text["all"] = all_text

    self.ui.categoriesListWidget.clear()

    # 添加一个特殊的全部标签（默认选中）
    # 全部标签的素材个数是所有素材ID的数量
    all_count = len(self.all_asset_ids)
    all_item = QListWidgetItem(f"{all_text} ({all_count})")
    font = all_item.font()
    font.setBold(True)
    all_item.setFont(font)
    self.ui.categoriesListWidget.addItem(all_item)

    # 按预定义的顺序添加主要分类标签
    main_categories = [
      (self._tr_background.get(), "background"),
      (self._tr_character.get(), "character"),
      (self._tr_other.get(), "other")
    ]
    displayed_main_categories = {cat[0] for cat in main_categories}

    for category_str, semantic in main_categories:
      # 确保映射关系存在
      self.tag_text_to_semantic[category_str] = semantic
      self.semantic_to_tag_text[semantic] = category_str

      # 获取该标签对应的素材个数
      count = len(self.assets_by_tag.get(category_str, {}))
      # 始终显示预定义标签
      item = QListWidgetItem(f"{category_str} ({count})")
      # 可以为主要分类添加特殊样式
      font = item.font()
      font.setBold(False)
      item.setFont(font)
      self.ui.categoriesListWidget.addItem(item)

    # 添加其他自定义标签（按字母顺序）
    # 获取所有不在预定义标签中的标签
    custom_tags = sorted([tag for tag in self.assets_by_tag.keys() if tag not in displayed_main_categories])
    for tag in custom_tags:
      # 获取该标签对应的素材个数
      count = len(self.assets_by_tag.get(tag, {}))
      item = QListWidgetItem(f"{tag} ({count})")
      self.ui.categoriesListWidget.addItem(item)
      # 对于自定义标签，直接使用原始文本作为语义标识，保持一致性
      if tag not in self.tag_text_to_semantic:
        self.tag_text_to_semantic[tag] = tag
        self.semantic_to_tag_text[tag] = tag

  def get_tags_dict(self) -> dict[str, set[str]]:
    """获取标签字典，并确保只包含语义标识"""
    settings = SettingsDict.instance()
    tags_dict = settings.get(self.SETTINGS_KEY_TAGS, {})

    # 确保返回的是dict[str, set[str]]格式，并清理显示文本标签
    result = {}
    for asset_name, tags in tags_dict.items():
      # 确保是集合类型
      if isinstance(tags, set):
        tag_set = set(tags)
      else:
        tag_set = set(tags)

      # 清理集合中的显示文本标签，只保留语义标识
      cleaned_tags = set()
      for tag in tag_set:
        # 如果标签是显示文本，找到对应的语义标识
        if tag in self.tag_text_to_semantic:
          cleaned_tags.add(self.tag_text_to_semantic[tag])
        else:
          # 已经是语义标识或自定义标签
          cleaned_tags.add(tag)

      result[asset_name] = cleaned_tags

    return result

  def save_tags_dict(self, tags_dict: dict[str, set[str]]):
    """保存标签字典，并确保只保存语义标识"""
    # 清理标签字典，确保只保存语义标识而不是显示文本
    cleaned_dict = {}
    for asset_name, tags in tags_dict.items():
      cleaned_tags = set()
      for tag in tags:
        # 如果标签是显示文本，找到对应的语义标识
        if tag in self.tag_text_to_semantic:
          cleaned_tags.add(self.tag_text_to_semantic[tag])
        else:
          # 已经是语义标识或自定义标签
          cleaned_tags.add(tag)
      cleaned_dict[asset_name] = cleaned_tags

    settings = SettingsDict.instance()
    settings[self.SETTINGS_KEY_TAGS] = cleaned_dict

  def save_tags(self):
    """保存标签到设置字典"""
    # 这里不需要单独保存标签列表，因为标签会作为素材标签的一部分被保存
    # 只需要确保标签字典中的标签是最新的
    tags_dict = self.get_tags_dict()
    self.save_tags_dict(tags_dict)

  def on_tag_selected(self, item: QListWidgetItem):
    """处理标签选择事件"""
    # 从显示文本中提取纯标签文本（去除计数部分）
    display_text = item.text()
    if ' (' in display_text:
      tag_text = display_text.split(' (')[0]
    else:
      tag_text = display_text

    # 获取当前标签文本用于显示
    self.current_tag = tag_text
    self.ui.categoryTitleLabel.setText(self.current_tag)

    # 获取标签的语义标识
    tag_semantic = self.tag_text_to_semantic.get(self.current_tag, "custom")

    # 保存当前选中的标签语义标识到设置
    settings = SettingsDict.instance()
    settings[self.SETTINGS_KEY_CURRENT_TAG] = tag_semantic

    # 加载对应的缩略图
    self.load_thumbnails_for_tag(tag_semantic)



  def get_thumbnail_cache_dir(self) -> str:
    """获取缩略图缓存目录"""
    temp_dir = SettingsDict.get_current_temp_dir()
    cache_dir = os.path.join(temp_dir, "asset_thumbnails")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

  def load_thumbnails_for_tag(self, tag: str):
    """加载指定标签的缩略图，预定义标签使用语义标识，自定义标签直接使用原始文本"""
    # 清空现有缩略图
    self.clear_thumbnails()

    # 获取要显示的素材ID列表
    asset_ids_to_show = []
    asset_manager = AssetManager.get_instance()

    # 确定要显示的素材
    if tag == "all" or tag == self._tr_all.get():
      # 显示所有素材
      asset_ids_to_show = self.all_asset_ids
    else:
      # 查找对应的显示标签文本
      display_tag = None
      if tag in self.semantic_to_tag_text:
        display_tag = self.semantic_to_tag_text[tag]
      else:
        # 可能是直接的标签文本
        display_tag = tag

      # 从assets_by_tag获取该标签下的所有素材ID
      if display_tag in self.assets_by_tag:
        asset_ids_to_show = list(self.assets_by_tag[display_tag].keys())
      else:
        # 如果找不到，尝试基于语义类别自动匹配
        semantic = self.tag_text_to_semantic.get(display_tag, tag)
        tag_semantic_category = semantic.split('_')[0]  # 提取基本语义类别

        if tag_semantic_category and tag_semantic_category != "custom":
          for asset_id in self.all_asset_ids:
            try:
              asset = asset_manager.get_asset(asset_id)
              if isinstance(asset, ImagePack):
                descriptor = ImagePack.get_descriptor_by_id(asset_id)
                if descriptor:
                  pack_type = descriptor.get_image_pack_type()
                  # 基于语义类别匹配
                  if (tag_semantic_category == "background" and pack_type == ImagePackDescriptor.ImagePackType.BACKGROUND) or \
                     (tag_semantic_category == "character" and pack_type == ImagePackDescriptor.ImagePackType.CHARACTER):
                    asset_ids_to_show.append(asset_id)
            except Exception:
              # 忽略单个资产的错误，继续处理其他资产
              continue

    if not asset_ids_to_show:
      return

    # 获取缓存目录
    cache_dir = self.get_thumbnail_cache_dir()

    # 确保缓存目录存在
    os.makedirs(cache_dir, exist_ok=True)

    # 检查并生成缩略图
    for asset_id in asset_ids_to_show:
      # 检查缓存是否存在
      thumbnail_path = os.path.join(cache_dir, f"{asset_id}_thumbnail.png")

      if os.path.exists(thumbnail_path):
        # 直接使用缓存
        self.thumbnail_cache[asset_id] = thumbnail_path
        self.add_thumbnail_to_flow(asset_id, thumbnail_path)
      else:
        # 异步生成缩略图
        worker = ThumbnailGeneratorWorker(asset_id, cache_dir)
        worker.signals.result.connect(self.on_thumbnail_generated)
        self.thread_pool.start(worker)

  def show_asset_context_menu(self, asset_id: str, pos: QPoint):
    """显示素材的上下文菜单"""
    menu = QMenu(self)

    # 添加标签操作
    tags_menu = menu.addMenu("标签")

    # 获取当前素材的标签
    tags_dict = self.get_tags_dict()
    asset_tags = tags_dict.get(asset_id, set())

    # 添加现有标签的勾选项
    for tag in sorted(self.all_tags):
      action = tags_menu.addAction(tag)
      action.setCheckable(True)
      action.setChecked(tag in asset_tags)
      action.triggered.connect(lambda checked, t=tag: self.toggle_asset_tag(asset_id, t, checked))

    # 显示菜单
    menu.exec_(pos)

  def toggle_asset_tag(self, asset_id: str, tag: str, checked: bool):
    """切换素材的标签，始终使用语义标识存储"""
    tags_dict = self.get_tags_dict()

    if asset_id not in tags_dict:
      tags_dict[asset_id] = set()

    # 确定要使用的标签语义标识
    tag_to_use = None
    if tag in self.tag_text_to_semantic:
      # 预定义标签，使用语义标识
      tag_to_use = self.tag_text_to_semantic[tag]
    else:
      # 自定义标签，使用标签文本作为语义标识
      tag_to_use = tag
      # 确保映射关系存在
      if tag not in self.tag_text_to_semantic:
        self.tag_text_to_semantic[tag] = tag
        self.semantic_to_tag_text[tag] = tag

    # 获取素材对象
    asset_manager = AssetManager.get_instance()
    asset = asset_manager.get_asset(asset_id)

    if checked:
      # 检查标签是否已经存在（只检查语义标识）
      if tag_to_use not in tags_dict[asset_id]:
        tags_dict[asset_id].add(tag_to_use)
      # 清理可能存在的显示文本标签，确保只存储语义标识
      for existing_tag in list(tags_dict[asset_id]):
        if existing_tag in self.tag_text_to_semantic and existing_tag != tag_to_use:
          tags_dict[asset_id].discard(existing_tag)
      # 更新assets_by_tag映射
      if tag not in self.assets_by_tag:
        self.assets_by_tag[tag] = {}
      self.assets_by_tag[tag][asset_id] = asset
    else:
      # 移除标签，但保留自动生成的系统标签（预设标签）
      if tag not in [self._tr_background.get(), self._tr_character.get(), self._tr_other.get()]:
        # 检查标签是否存在
        if tag_to_use in tags_dict[asset_id]:
          # 只移除语义标识
          tags_dict[asset_id].discard(tag_to_use)
          # 更新assets_by_tag映射
          if tag in self.assets_by_tag and asset_id in self.assets_by_tag[tag]:
            del self.assets_by_tag[tag][asset_id]
          # 如果标签没有素材了，删除该标签
          if tag in self.assets_by_tag and not self.assets_by_tag[tag]:
            del self.assets_by_tag[tag]

    # 保存更新后的标签字典，确保只保存语义标识
    self.save_tags_dict(tags_dict)
    # 更新标签列表，显示最新的计数
    self.update_tags_list()

  def add_new_tag_for_asset(self, asset_id: str):
    """为素材添加新标签的方法已被禁用"""
    QMessageBox.information(self, "标签管理", "标签创建功能已禁用。请在其他位置管理标签。")

  def _on_container_resized(self, event):
    """当容器大小改变时重新调整布局"""
    # 直接调用原始QWidget的resizeEvent方法
    QWidget.resizeEvent(self.ui.thumbnailsScrollAreaWidgetContents, event)

    # 获取当前容器宽度
    current_width = self.ui.thumbnailsContainerWidget.width()

    # 检查是否需要重新布局（初始化时或宽度实际变化时）
    if not hasattr(self, '_last_container_width') or current_width != self._last_container_width:
      # 记录当前宽度
      self._last_container_width = current_width

      # 如果有缩略图，智能调整缩略图大小而不是重新加载
      if self.thumbnail_items and current_width > 0:
        # 计算最佳缩略图大小
        card_width = self._calculate_optimal_card_width(current_width)
        card_height = int(card_width * 1.2)  # 保持1:1.2的宽高比

        # 更新FlowLayout中的项目大小
        self.flow_layout.setItemSize(QSize(card_width, card_height))

        # 为每个缩略图调整内部元素大小
        for asset_id, widget in self.thumbnail_items.items():
          # 调整缩略图容器大小
          widget.setFixedSize(card_width, card_height)

          # 找到内部的图像标签并调整
          for child in widget.findChildren(QLabel):
            # 假设第一个QLabel是图像标签
            if widget.findChildren(QLabel).index(child) == 0:
              # 获取布局信息
              layout = widget.layout()
              margins = layout.contentsMargins()
              spacing = layout.spacing()

              # 计算图像可用空间
              available_width = card_width - (margins.left() + margins.right())

              # 计算图像高度（减去名称和标签的高度）
              name_label_height = self.name_font_metrics.height()
              tags_label_height = self.tags_font_metrics.height()
              name_tags_height = name_label_height + tags_label_height + spacing
              available_height = card_height - (margins.top() + margins.bottom() + name_tags_height)

              # 设置图像标签大小
              child.setFixedSize(available_width, available_height)

              # 更新图像缩放
              if hasattr(child, '_last_width'):
                child._last_width = -1  # 强制重新调整大小
                break
            # 处理名称标签和标签标签，更新其文本省略
            elif hasattr(child, '_full_text'):
              # 触发文本省略更新
              if hasattr(child, 'resizeEvent') and child.resizeEvent:
                child.resizeEvent(QResizeEvent(child.size(), child.size()))

    # 通知FlowLayout更新布局
    self.flow_layout.update()

    return event

  def _calculate_optimal_card_width(self, container_width):
    """根据容器宽度计算最佳卡片宽度"""
    # 最小卡片宽度（保证可读性）
    min_card_width = 160
    # 获取间距
    spacing = self.flow_layout.spacing()

    # 计算可显示的最大列数
    columns = max(1, container_width // (min_card_width + spacing))

    # 限制最小列数为2，除非容器宽度实在太小
    if container_width >= min_card_width * 2 + spacing:
      columns = max(columns, 2)

    # 计算卡片宽度，确保能均匀分布在容器中
    if columns > 1:
      card_width = (container_width - (columns - 1) * spacing) // columns
      # 确保卡片宽度不小于最小宽度
      card_width = max(card_width, min_card_width)
    else:
      # 单列时，使用最小宽度但不超过容器宽度
      card_width = min(min_card_width, container_width)

    return card_width

  class TagEditDialog(QDialog):
    """标签编辑对话框，用于编辑素材的标签"""
    def __init__(self, asset_id, asset_browser, parent=None):
      super().__init__(parent)
      self.asset_id = asset_id
      self.asset_browser = asset_browser
      self.setWindowTitle("编辑标签")
      self.resize(300, 400)

      # 创建布局
      main_layout = QVBoxLayout(self)

      # 创建标签列表
      self.tag_list_widget = QListWidget()
      self.tag_list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
      main_layout.addWidget(self.tag_list_widget)

      # 添加简短文本提示
      hint_label = QLabel(self.asset_browser._tr_tag_edit_hint.get())
      hint_label.setAlignment(Qt.AlignCenter)
      hint_label.setStyleSheet("color: #666666; font-size: 12px;")
      main_layout.addWidget(hint_label)

      # 加载当前标签
      self.load_tags()

      # 连接信号
      self.tag_list_widget.itemClicked.connect(self.edit_tag)  # 改为单击编辑

      # 连接键盘事件
      self.tag_list_widget.installEventFilter(self)

      # 如果有标签，选中第一个并直接进入编辑模式
      if self.tag_list_widget.count() > 0:
        self.tag_list_widget.setCurrentRow(0)
        # 延迟一点执行编辑，确保界面已完全初始化
        QTimer.singleShot(0, lambda: self.tag_list_widget.editItem(self.tag_list_widget.currentItem()))
      else:
        # 如果没有标签，创建一个空的标签并直接编辑
        empty_tag_item = QListWidgetItem("")
        empty_tag_item.setFlags(empty_tag_item.flags() | Qt.ItemIsEditable)
        self.tag_list_widget.addItem(empty_tag_item)
        self.tag_list_widget.setCurrentRow(0)
        # 延迟一点执行编辑，确保界面已完全初始化
        QTimer.singleShot(0, lambda: self.tag_list_widget.editItem(empty_tag_item))

    def load_tags(self):
      """加载当前资产的标签"""
      self.tag_list_widget.clear()
      tags_dict = self.asset_browser.get_tags_dict()
      asset_tags = tags_dict.get(self.asset_id, set())

      # 转换标签为显示文本
      display_tags = []
      for tag in asset_tags:
        if tag in self.asset_browser.semantic_to_tag_text:
          display_tags.append(self.asset_browser.semantic_to_tag_text[tag])
        else:
          display_tags.append(tag)

      # 添加到列表
      for tag in sorted(display_tags):
        item = QListWidgetItem()
        item.setText(tag)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.tag_list_widget.addItem(item)



    def edit_tag(self, item):
      """编辑标签"""
      old_text = item.text()
      # 启动编辑
      self.tag_list_widget.editItem(item)
      # 连接编辑完成信号
      self.tag_list_widget.itemChanged.connect(lambda i: self.on_tag_edited(i, old_text))

    def on_tag_edited(self, item, old_text):
      """处理标签编辑完成事件，支持预设标签和自定义标签"""
      new_text = item.text().strip()
      if not new_text:
        # 如果新文本为空，删除标签
        self.remove_tag(item)
      elif new_text != old_text:
        # 更新标签
        tags_dict = self.asset_browser.get_tags_dict()
        if self.asset_id in tags_dict:
          # 获取旧标签的语义标识
          old_semantic = old_text
          if old_text in self.asset_browser.tag_text_to_semantic:
            old_semantic = self.asset_browser.tag_text_to_semantic[old_text]

          # 获取新标签的语义标识
          new_semantic = new_text
          # 检查新标签是否与预设标签的显示文本匹配
          for tag_text, semantic in self.asset_browser.tag_text_to_semantic.items():
            if tag_text == new_text:
              new_semantic = semantic
              break

          # 移除旧标签
          if old_semantic in tags_dict[self.asset_id]:
            tags_dict[self.asset_id].remove(old_semantic)

          # 添加新标签（无论是否是预设标签都允许）
          tags_dict[self.asset_id].add(new_semantic)

          # 保存并更新
          self.asset_browser.save_tags_dict(tags_dict)
          self.asset_browser.update_thumbnail_tags()

      # 断开信号连接
      try:
        self.tag_list_widget.itemChanged.disconnect()
      except:
        pass

    def remove_tag(self, item):
      """移除标签"""
      tag_text = item.text()

      # 从字典中移除
      tags_dict = self.asset_browser.get_tags_dict()
      if self.asset_id in tags_dict:
        semantic_tag = self.asset_browser.tag_text_to_semantic.get(tag_text, tag_text)
        if semantic_tag in tags_dict[self.asset_id]:
          tags_dict[self.asset_id].remove(semantic_tag)

          # 如果标签集为空，删除该资产的条目
          if not tags_dict[self.asset_id]:
            del tags_dict[self.asset_id]

          # 保存并更新
          self.asset_browser.save_tags_dict(tags_dict)
          self.asset_browser.update_thumbnail_tags()

      # 从列表中移除
      row = self.tag_list_widget.row(item)
      self.tag_list_widget.takeItem(row)

    def eventFilter(self, obj, event):
      """事件过滤器，处理键盘事件"""
      if event.type() == QEvent.KeyPress:
        # ESC键关闭对话框
        if event.key() == Qt.Key_Escape:
          self.accept()
          return True

        # Delete键删除选中的标签
        if event.key() == Qt.Key_Delete and obj == self.tag_list_widget:
          current_item = self.tag_list_widget.currentItem()
          if current_item:
            self.remove_tag(current_item)
          return True

        # Backspace键处理：当编辑框为空时删除标签
        if event.key() == Qt.Key_Backspace:
          # 获取当前正在编辑的项目
          current_item = self.tag_list_widget.currentItem()
          editor = self.tag_list_widget.itemDelegate().editor()

          # 如果正在编辑且文本为空
          if editor and current_item and isinstance(editor, QLineEdit) and editor.text() == "":
            # 检查是否是最后一个标签
            if self.tag_list_widget.count() > 1:
              # 不是最后一个，则删除当前标签
              self.remove_tag(current_item)
              # 选择下一个标签并开始编辑
              if self.tag_list_widget.currentItem():
                QTimer.singleShot(0, lambda: self.tag_list_widget.editItem(self.tag_list_widget.currentItem()))
            # 如果是最后一个标签，只保留输入框（不删除）
            return True

        if obj == self.tag_list_widget and event.key() in (Qt.Key_Up, Qt.Key_Down):
          # 方向键已经由QListWidget处理，这里只需要在适当的时候编辑项目
          if event.key() == Qt.Key_Up and self.tag_list_widget.currentRow() > 0:
            QTimer.singleShot(0, lambda: self.tag_list_widget.editItem(self.tag_list_widget.currentItem()))
          elif event.key() == Qt.Key_Down and self.tag_list_widget.currentRow() < self.tag_list_widget.count() - 1:
            QTimer.singleShot(0, lambda: self.tag_list_widget.editItem(self.tag_list_widget.currentItem()))

      return super().eventFilter(obj, event)

  def add_thumbnail_to_flow(self, asset_id: str, thumbnail_path: str):
    """将缩略图添加到流布局中，使用根据容器大小动态计算的尺寸"""
    # 计算最佳卡片大小
    container_width = self.ui.thumbnailsContainerWidget.width()
    card_width = self._calculate_optimal_card_width(container_width)
    card_height = int(card_width * 1.2)  # 保持1:1.2的宽高比

    # 创建缩略图容器
    thumbnail_container = QWidget()
    thumbnail_container.setFixedSize(card_width, card_height)
    container_layout = QVBoxLayout(thumbnail_container)

    # 设置布局参数，增加内边距使内容在卡牌中有更好的视觉效果
    container_layout.setContentsMargins(8, 8, 8, 8)
    container_layout.setSpacing(6)
    container_layout.setSizeConstraint(QLayout.SetFixedSize)

    # 创建图片标签
    image_label = QLabel()
    image_label.setAlignment(Qt.AlignCenter)
    image_label.setStyleSheet("border: none;")
    image_label.setMouseTracking(False)

    # 计算图片标签的大小
    layout_margins = container_layout.contentsMargins()
    layout_spacing = container_layout.spacing()

    # 计算名称和标签的高度
    name_label_height = self.name_font_metrics.height()
    tags_label_height = self.tags_font_metrics.height()

    # 计算图片区域的可用空间
    available_width = card_width - (layout_margins.left() + layout_margins.right())
    available_height = card_height - (layout_margins.top() + layout_margins.bottom() +
                                      name_label_height + tags_label_height + layout_spacing)

    # 设置图片标签固定大小
    image_label.setFixedSize(available_width, available_height)

    # 获取资产类型信息
    is_character, is_background = self._get_asset_type_info(asset_id)

    # 加载并设置图片
    pixmap = QPixmap(thumbnail_path)
    if not pixmap.isNull():
      # 使用提取的方法进行缩放
      scaled_pixmap = self._scale_pixmap_for_asset(pixmap, available_width, available_height, is_character, is_background)

    # 设置图片并确保居中显示
    image_label.setPixmap(scaled_pixmap)
    # 记录当前尺寸，避免不必要的更新
    image_label._last_width = available_width
    image_label._last_height = available_height

    # 连接图片标签的调整大小信号以更新图片
    image_label.resizeEvent = lambda event, img=image_label, path=thumbnail_path, aid=asset_id: self._update_image_on_resize(event, img, path, aid)

    # 创建名称标签 - 移除背景样式，使其成为纯文本标签
    name_label = QLabel()
    name_label.setAlignment(Qt.AlignCenter)
    name_label.setWordWrap(False)  # 禁止自动换行
    # 移除背景样式，使用简单的文本样式
    name_label.setStyleSheet("color: #000000; padding: 4px 0;")
    name_label.setMouseTracking(False)
    # 设置名称标签为自适应宽度策略
    name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    name_label.setMinimumHeight(name_label.fontMetrics().height() + 8)  # 保持足够的高度
    name_label.setTextInteractionFlags(Qt.NoTextInteraction)

    # 获取友好名称
    asset_manager = AssetManager.get_instance()
    asset = asset_manager.get_asset(asset_id)
    friendly_name = asset_id  # 默认使用asset_id

    if isinstance(asset, ImagePack):
        descriptor = ImagePack.get_descriptor_by_id(asset_id)
        if descriptor:
            # 使用get_name()方法获取友好名称
            name_obj = descriptor.get_name()
            if hasattr(name_obj, 'get'):
                # 如果是Translatable对象
                friendly_name = name_obj.get()
            elif name_obj:
                # 如果是普通字符串
                friendly_name = name_obj

    # 存储完整文本以便后续更新
    name_label._full_text = friendly_name
    # 初始设置省略文本（考虑边距）
    font_metrics = name_label.fontMetrics()
    text_margins = 8  # 文本左右边距总和
    name_label.setText(font_metrics.elidedText(friendly_name, Qt.ElideRight, card_width - text_margins))
    # 连接调整大小信号以在布局变化时重新计算省略
    name_label.resizeEvent = self._handle_label_resize

    # 添加标签显示区域
    tags_widget = QWidget()
    tags_widget.setObjectName(f"tags_widget_{asset_id}")
    tags_layout = QHBoxLayout(tags_widget)
    tags_layout.setContentsMargins(0, 0, 0, 0)
    tags_layout.setSpacing(4)
    tags_layout.setAlignment(Qt.AlignCenter)

    # 设置标签小部件的大小策略
    tags_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    tags_widget.setMinimumHeight(tags_label_height)

    # 加载标签
    tags_dict = self.get_tags_dict()
    asset_tags = tags_dict.get(asset_id, set())

    # 转换标签为翻译后的文本，确保每个标签只显示一次
    translated_tags = set()
    for tag in sorted(asset_tags):
      # 优先检查是否是语义标识
      if tag in self.semantic_to_tag_text:
        # 使用当前语言的翻译文本
        translated_tags.add(self.semantic_to_tag_text[tag])
      else:
        # 自定义标签保持原样
        translated_tags.add(tag)

    # 创建标签按钮
    tags_text = ", ".join(sorted(translated_tags))
    tags_button = QPushButton(tags_text if tags_text else "无标签")
    tags_button.setObjectName(f"tags_button_{asset_id}")
    # 使用标签字体作为标签按钮的字体
    tags_button.setFont(self.tags_font)

    # 使用缓存的name_font作为名称标签的字体（加粗效果）
    name_label.setFont(self.name_font)

    # 设置按钮的大小策略
    tags_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    tags_button.setMinimumHeight(tags_label_height)
    tags_button.setFlat(True)

    # 设置按钮样式 - 圆角标签按钮，使用深灰色以与其他元素区分
    tags_button.setStyleSheet("""
      QPushButton {
        background-color: rgba(65, 65, 65, 0.95);
        border: 1px solid rgba(70, 70, 70, 0.95);
        border-radius: 20px;
        color: #FFFFFF;
        padding: 4px 14px;
        font-size: 9pt;
        font-weight: 500;
        text-align: center;
        outline: none;
      }
      QPushButton:hover {
        background-color: rgba(85, 85, 85, 0.95);
        border-color: rgba(90, 90, 90, 0.95);
        color: #FFFFFF;
      }
      QPushButton:pressed {
        background-color: rgba(85, 85, 85, 0.95);
        border-color: rgba(70, 70, 70, 0.95);
        color: #FFFFFF;
      }
      QPushButton:focus {
        background-color: rgba(65, 65, 65, 0.95);
        border: 1px solid rgba(70, 70, 70, 0.95);
        color: #FFFFFF;
        outline: none;
      }
    """)

    # 简化实现：直接使用按钮的文本属性，避免嵌套QLabel导致的重叠问题
    tags_button.setText(tags_text if tags_text else self._tr_no_tags.get())
    # 存储完整文本以便后续更新
    tags_button._full_text = tags_text if tags_text else self._tr_no_tags.get()

    # 为标签按钮添加调整大小事件以正确处理文本省略
    def resize_button_text(event, button=tags_button):
      # 计算可用宽度（考虑边距）
      if hasattr(button, '_full_text'):
        font_metrics = button.fontMetrics()
        # 按钮有内边距，需要减去
        available_width = button.width() - 12  # 估计的内边距总和
        elided_text = font_metrics.elidedText(button._full_text, Qt.ElideRight, available_width)
        button.setText(elided_text)

    tags_button.resizeEvent = resize_button_text
    # 初始调整大小以确保文本正确省略
    resize_button_text(None)

    # 连接点击信号到标签编辑对话框
    def on_tags_button_clicked(aid=asset_id):
      # 直接调用标签编辑对话框
      self.open_tag_edit_dialog(aid)

    tags_button.clicked.connect(on_tags_button_clicked)

    # 存储标签按钮的asset_id，用于标识和后续更新
    tags_button._asset_id = asset_id

    # 添加到标签布局
    tags_layout.addWidget(tags_button)

    # 存储按钮引用
    if asset_id not in self.tag_buttons:
      self.tag_buttons[asset_id] = []
    self.tag_buttons[asset_id].append(tags_button)

    # 添加到容器布局 - 保持图片、名称、标签的顺序
    container_layout.addWidget(image_label)
    container_layout.addWidget(name_label)
    container_layout.addWidget(tags_widget)

    # 设置容器样式 - 更透明的背景，让图片和文字成为主体
    thumbnail_container.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); border: 1px solid rgba(200, 200, 200, 0.2); border-radius: 8px; padding: 2px;")

    # 添加到FlowLayout
    self.flow_layout.addWidget(thumbnail_container)

    # 存储到字典中以便后续访问
    self.thumbnail_items[asset_id] = thumbnail_container

    # 设置右键菜单
    thumbnail_container.setContextMenuPolicy(Qt.CustomContextMenu)
    thumbnail_container.customContextMenuRequested.connect(
      lambda pos, aid=asset_id: self.show_asset_context_menu(aid, thumbnail_container.mapToGlobal(pos))
    )

    # 设置鼠标事件处理
    thumbnail_container.setMouseTracking(True)
    thumbnail_container.enterEvent = lambda event, aid=asset_id: self.on_thumbnail_enter(aid, event)
    thumbnail_container.leaveEvent = lambda event, aid=asset_id: self.on_thumbnail_leave(aid, event)
    thumbnail_container.mousePressEvent = lambda event, aid=asset_id: self.on_thumbnail_clicked(aid, event)

    # 恢复上次选中的高亮状态
    if asset_id == self.last_opened_asset_id:
      # 确保选中样式也使用更透明的背景
      thumbnail_container.setStyleSheet("background-color: rgba(220, 230, 245, 0.2); border: 2px solid #4a90e2; border-radius: 8px; padding: 1px;")

  def on_thumbnail_clicked(self, asset_id: str, event):
    """处理缩略图容器的点击事件"""
    # 获取点击位置相对于容器的坐标
    pos = event.pos()

    # 检查点击是否在标签按钮区域内
    if asset_id in self.tag_buttons:
      for button in self.tag_buttons[asset_id]:
        # 检查点击位置是否在按钮的几何区域内
        if button.geometry().contains(pos):
          # 如果点击在标签按钮上，不执行容器的点击逻辑
          return

    # 如果不是点击在标签按钮上，执行原有的点击处理逻辑
    # 这里应该是原有的点击处理代码
    # 由于我们替换了原始方法，需要确保原有功能正常
    # 检查是否是右键点击
    if event.button() == Qt.RightButton:
      # 显示上下文菜单
      self.show_asset_context_menu(asset_id, event.globalPos())
    else:
      # 左键点击的处理逻辑（如果有）
      pass

  def _get_asset_type_info(self, asset_id):
    """获取资产类型信息（立绘、背景或其他）"""
    is_character = False
    is_background = False
    asset_manager = AssetManager.get_instance()
    asset = asset_manager.get_asset(asset_id)
    if isinstance(asset, ImagePack):
      descriptor = ImagePack.get_descriptor_by_id(asset_id)
      if descriptor:
        pack_type = descriptor.get_image_pack_type()
        is_character = pack_type == descriptor.ImagePackType.CHARACTER
        is_background = pack_type == descriptor.ImagePackType.BACKGROUND
    return is_character, is_background

  def _scale_pixmap_for_asset(self, pixmap, width, height, is_character, is_background):
    """根据资产类型缩放像素图"""
    if is_character:
      # 立绘：优先适应高度，保持9:16比例
      scaled_pixmap = pixmap.scaledToHeight(height, Qt.SmoothTransformation)
      # 如果宽度超过可用宽度，则再按宽度缩放
      if scaled_pixmap.width() > width:
        scaled_pixmap = scaled_pixmap.scaledToWidth(width, Qt.SmoothTransformation)
    elif is_background:
      # 背景：优先适应宽度，保持16:9比例
      scaled_pixmap = pixmap.scaledToWidth(width, Qt.SmoothTransformation)
      # 如果高度超过可用高度，则再按高度缩放
      if scaled_pixmap.height() > height:
        scaled_pixmap = scaled_pixmap.scaledToHeight(height, Qt.SmoothTransformation)
    else:
      # 其他类型：使用KeepAspectRatio确保图片适应空间，但保持比例
      scaled_pixmap = pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return scaled_pixmap

  def _update_image_on_resize(self, event, image_label, thumbnail_path, asset_id):
    """当图片标签大小改变时更新图片"""
    # 直接调用原始QLabel的resizeEvent方法
    QLabel.resizeEvent(image_label, event)

    # 添加宽度跟踪，避免频繁更新
    current_width = image_label.width()
    current_height = image_label.height()

    # 检查是否已初始化或尺寸实际发生变化
    if not hasattr(image_label, '_last_width') or not hasattr(image_label, '_last_height'):
      # 初始化时需要更新
      need_update = True
    else:
      # 只有当尺寸实际变化时才更新
      need_update = (current_width != image_label._last_width or
                    current_height != image_label._last_height)

    # 只有在需要更新且尺寸有效时才进行处理
    if need_update and current_width > 0 and current_height > 0:
      # 记录当前尺寸
      image_label._last_width = current_width
      image_label._last_height = current_height

      # 加载并设置图片
      pixmap = QPixmap(thumbnail_path)
      if not pixmap.isNull():
        # 获取资产类型信息
        is_character, is_background = self._get_asset_type_info(asset_id)

        # 使用提取的方法进行缩放
        scaled_pixmap = self._scale_pixmap_for_asset(pixmap, current_width, current_height, is_character, is_background)

        # 设置图片并确保居中显示
        image_label.setPixmap(scaled_pixmap)

  # calculate_grid_position方法已不再需要，因为FlowLayout会自动管理位置

  def clear_thumbnails(self):
    """清空缩略图流布局，确保删除所有布局项"""
    # 删除所有布局项，包括widget和非widget项
    while self.flow_layout.count() > 0:
      item = self.flow_layout.takeAt(0)
      if item.widget() is not None:
        item.widget().deleteLater()
      # 移除布局项本身
      del item

    self.thumbnail_items.clear()
    # 保留last_opened_asset_id，这样重新加载缩略图时可以恢复选中状态

  def _handle_label_resize(self, event):
        """通用的标签大小调整处理方法"""
        # 直接调用原始QLabel的resizeEvent方法
        QLabel.resizeEvent(self, event)

        # 只有当文本存在且宽度有变化时才重新计算省略
        if hasattr(self, '_full_text') and self.width() > 0:
          # 检查是否需要更新
          current_width = self.width()
          if not hasattr(self, '_last_width') or current_width != self._last_width:
              # 记录当前宽度
              self._last_width = current_width
              # 重新计算省略文本，考虑边距
              font_metrics = self.fontMetrics()
              text_margins = 8  # 为文本预留边距
              elided_text = font_metrics.elidedText(self._full_text, Qt.ElideRight, current_width - text_margins)
          self.setText(elided_text)

  def on_thumbnail_generated(self, asset_id: str, thumbnail_path: str):
    """当缩略图生成完成后调用"""
    # 检查是否是主线程，如果不是，使用信号槽机制切换到主线程
    if QThread.currentThread() != QApplication.instance().thread():
      # 在主线程中调用此方法
      QMetaObject.invokeMethod(self, 'on_thumbnail_generated',
                              Qt.QueuedConnection,
                              Q_ARG(str, asset_id),
                              Q_ARG(str, thumbnail_path))
      return

    if thumbnail_path:
      # 缓存缩略图路径
      self.thumbnail_cache[asset_id] = thumbnail_path
      # 添加到流布局
      self.add_thumbnail_to_flow(asset_id, thumbnail_path)

      # 如果是最后打开的资源，更新其样式为选中样式
      if self.last_opened_asset_id and self.last_opened_asset_id == asset_id:
        if asset_id in self.thumbnail_items:
          self.thumbnail_items[asset_id].setStyleSheet(self.selected_style)

  def on_thumbnail_enter(self, asset_id: str, event: QEvent):
    """处理鼠标进入缩略图事件"""
    if asset_id in self.thumbnail_items:
      # 设置更透明的悬浮样式，使图片和文字成为主体
      if asset_id == self.last_opened_asset_id:
        # 选中项的悬浮状态 - 更暗的背景
        self.thumbnail_items[asset_id].setStyleSheet("""
          QWidget {
            background-color: rgba(200, 210, 225, 0.3);
            border: 2px solid #4a90e2;
            border-radius: 8px;
            padding: 1px;
          }
        """)
      else:
        # 普通项的悬浮状态 - 更暗的背景
        self.thumbnail_items[asset_id].setStyleSheet("""
          QWidget {
            background-color: rgba(235, 235, 235, 0.3);
            border: 1px solid rgba(180, 180, 180, 0.4);
            border-radius: 8px;
            padding: 2px;
          }
        """)

  def on_thumbnail_leave(self, asset_id: str, event: QEvent):
    """处理鼠标离开缩略图事件"""
    if asset_id in self.thumbnail_items:
      # 恢复更透明的样式，使图片和文字成为主体
      if asset_id == self.last_opened_asset_id:
        # 选中项 - 更透明
        self.thumbnail_items[asset_id].setStyleSheet("""
          QWidget {
            background-color: rgba(220, 230, 245, 0.2);
            border: 2px solid #4a90e2;
            border-radius: 8px;
            padding: 1px;
          }
        """)
      else:
        # 普通项 - 更透明
        self.thumbnail_items[asset_id].setStyleSheet("""
          QWidget {
            background-color: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(200, 200, 200, 0.2);
            border-radius: 8px;
            padding: 2px;
          }
        """)

  def on_thumbnail_clicked(self, asset_id: str, event: QMouseEvent):
    """处理缩略图点击事件，打开详情页面"""
    # 只有左键点击才打开详情页面
    if event.button() == Qt.LeftButton:
      from ..mainwindowinterface import MainWindowInterface
      from .imagepack import ImagePackWidget
      from preppipe.util.imagepack import ImagePack

      # 检查是否为ImagePack类型的资源
      asset_manager = AssetManager.get_instance()
      asset = asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
        # 取消之前选中项的高亮 - 使用更透明样式
        if self.last_opened_asset_id and self.last_opened_asset_id in self.thumbnail_items:
          self.thumbnail_items[self.last_opened_asset_id].setStyleSheet("""
            QWidget {
              background-color: rgba(255, 255, 255, 0.2);
              border: 1px solid rgba(200, 200, 200, 0.2);
              border-radius: 8px;
              padding: 2px;
            }
          """)

        # 更新上次打开的资源ID并高亮当前项 - 使用更透明样式
        self.last_opened_asset_id = asset_id
        if asset_id in self.thumbnail_items:
          self.thumbnail_items[asset_id].setStyleSheet("""
            QWidget {
              background-color: rgba(220, 230, 245, 0.2);
              border: 2px solid #4a90e2;
              border-radius: 8px;
              padding: 1px;
            }
          """)

        # 请求打开ImagePackWidget
        MainWindowInterface.getHandle(self).requestOpen(
          ImagePackWidget.getToolInfo(packid=asset_id)
        )
    else:
      # 对于右键点击，确保调用原有的mousePressEvent以显示上下文菜单
      if asset_id in self.thumbnail_items:
        QWidget.mousePressEvent(self.thumbnail_items[asset_id], event)



  @classmethod
  def getToolInfo(cls, **kwargs) -> ToolWidgetInfo:
    return ToolWidgetInfo(
      idstr="assetbrowser",
      name=cls._tr_toolname_assetbrowser,
      tooltip=cls._tr_tooltip_assetbrowser,
      widget=cls,
    )

  def open_tag_edit_dialog(self, asset_id):
    """打开标签编辑对话框"""
    dialog = self.TagEditDialog(asset_id, self, self)
    dialog.exec()

  def update_thumbnail_tags(self):
    """更新现有缩略图的标签文本，而不重新加载整个缩略图"""
    # 直接从设置中获取标签字典，确保使用语义标识而不是显示文本
    tags_dict = self.get_tags_dict()

    # 遍历所有缩略图项
    for asset_id, thumbnail_widget in self.thumbnail_items.items():
      # 获取缩略图的资产标签（使用语义标识）
      asset_tags = tags_dict.get(asset_id, set())

      # 转换标签为翻译后的文本，确保每个标签只显示一次
      translated_tags = set()
      for tag in sorted(asset_tags):
        # 优先检查是否是语义标识
        if tag in self.semantic_to_tag_text:
          # 使用当前语言的翻译文本
          translated_tags.add(self.semantic_to_tag_text[tag])
        else:
          # 自定义标签保持原样
          translated_tags.add(tag)

      # 更新标签按钮的文本
      tags_text = ", ".join(sorted(translated_tags))
      # 优先通过字典查找按钮
      if asset_id in self.tag_buttons:
        for button in self.tag_buttons[asset_id]:
          # 直接更新按钮的_full_text属性
          button._full_text = tags_text if tags_text else self._tr_no_tags.get()
          # 触发调整大小事件以正确显示省略的文本
          if hasattr(button, 'resizeEvent'):
            button.resizeEvent(None)
      else:
        # 如果字典中没有，尝试通过对象名查找
        tags_button = thumbnail_widget.findChild(QPushButton, f"tags_button_{asset_id}")
        if tags_button:
          # 直接更新按钮的_full_text属性
          tags_button._full_text = tags_text if tags_text else self._tr_no_tags.get()
          # 触发调整大小事件以正确显示省略的文本
          if hasattr(tags_button, 'resizeEvent'):
            tags_button.resizeEvent(None)

      # 同时更新资产名称（如果是Translatable对象）
      asset_manager = AssetManager.get_instance()
      asset = asset_manager.get_asset(asset_id)
      if isinstance(asset, ImagePack):
          descriptor = ImagePack.get_descriptor_by_id(asset_id)
          if descriptor:
              # 使用get_name()方法获取友好名称
              name_obj = descriptor.get_name()
              if hasattr(name_obj, 'get'):
                  # 如果是Translatable对象
                  friendly_name = name_obj.get()
                  # 查找并更新名称标签
                  for child in thumbnail_widget.findChildren(QLabel):
                      # 查找名称标签（假设是第一个QLabel）
                      if child.objectName() != f"tags_label_{asset_id}":
                          if hasattr(child, '_full_text'):
                              child._full_text = friendly_name
                          # 重新设置省略文本
                          card_width = thumbnail_widget.width()
                          text_margins = 8  # 文本左右边距总和
                          font_metrics = child.fontMetrics()
                          child.setText(font_metrics.elidedText(friendly_name, Qt.ElideRight, card_width - text_margins))
                          break

  def update_text(self):
    super().update_text()

    # 保存当前选中标签的语义标识
    current_semantic = None
    current_item = self.ui.categoriesListWidget.currentItem()
    if current_item:
      # 从显示文本中提取纯标签文本（去除计数部分）
      display_text = current_item.text()
      if ' (' in display_text:
        tag_text = display_text.split(' (')[0]
      else:
        tag_text = display_text

      if tag_text in self.tag_text_to_semantic:
        current_semantic = self.tag_text_to_semantic[tag_text]



    # 重新加载标签，确保使用当前语言的翻译
    self.load_tags()

    # 根据保存的语义标识重新选择标签
    if current_semantic and current_semantic in self.semantic_to_tag_text:
      # 查找对应的标签文本并选中
      target_text = self.semantic_to_tag_text[current_semantic]
      for i in range(self.ui.categoriesListWidget.count()):
        item = self.ui.categoriesListWidget.item(i)
        if item:
          # 从显示文本中提取纯标签文本
          display_text = item.text()
          if ' (' in display_text:
            tag_text = display_text.split(' (')[0]
          else:
            tag_text = display_text

          if tag_text == target_text:
            self.ui.categoriesListWidget.setCurrentItem(item)
            # 更新当前标签
            self.current_tag = target_text
            self.ui.categoryTitleLabel.setText(self.current_tag)
            # 更新现有缩略图的标签文本，而不重新加载整个缩略图
            self.update_thumbnail_tags()

            # 确保使用正确的语义标识加载缩略图
            if hasattr(self, 'load_thumbnails_for_tag'):
              self.load_thumbnails_for_tag(current_semantic)
            break
    elif not current_item:
      # 如果之前没有选择，默认选择第一个标签（通常是"全部"）
      if self.ui.categoriesListWidget.count() > 0:
        self.ui.categoriesListWidget.setCurrentRow(0)
        # 更新当前标签
        first_item = self.ui.categoriesListWidget.item(0)
        if first_item:
          # 从显示文本中提取纯标签文本
          display_text = first_item.text()
          if ' (' in display_text:
            tag_text = display_text.split(' (')[0]
          else:
            tag_text = display_text
          self.current_tag = tag_text
          self.ui.categoryTitleLabel.setText(self.current_tag)

          # 获取语义标识并加载缩略图
          tag_semantic = self.tag_text_to_semantic.get(tag_text, "all")
          if hasattr(self, 'load_thumbnails_for_tag'):
            self.load_thumbnails_for_tag(tag_semantic)
        # 更新现有缩略图的标签文本
        self.update_thumbnail_tags()


# 缩略图生成工作线程类
class ThumbnailGeneratorWorkerSignals(QObject):
  result = Signal(str, str)  # asset_id, thumbnail_path


class ThumbnailGeneratorWorker(QRunnable):
  def __init__(self, asset_id: str, cache_dir: str):
    super().__init__()
    self.asset_id = asset_id
    self.cache_dir = cache_dir
    self.signals = ThumbnailGeneratorWorkerSignals()

  def run(self):
    try:
      # 获取图片包类型以确定合适的缩略图尺寸
      descriptor = ImagePack.get_descriptor_by_id(self.asset_id)
      pack_type = descriptor.get_image_pack_type() if descriptor else None

      # 根据图片包类型设置不同的缩略图尺寸
      if pack_type == ImagePackDescriptor.ImagePackType.BACKGROUND:
        # 背景图使用宽屏比例
        thumbnail_size = (192, 108)  # 基于标准宽屏比例
      elif pack_type == ImagePackDescriptor.ImagePackType.CHARACTER:
        # 立绘使用人物比例
        thumbnail_size = (108, 192)  # 基于人物比例
      else:
        # 默认使用正方形
        thumbnail_size = (128, 128)

      # 生成缩略图，传入特定尺寸
      image = generate_thumbnail_from_imagepack(self.asset_id, use_default_sizes=False, target_size=thumbnail_size)
      if image:
        # 保存缩略图
        thumbnail_path = os.path.join(self.cache_dir, f"{self.asset_id}_thumbnail.png")
        image.save(thumbnail_path)
        # 发送结果信号
        self.signals.result.emit(self.asset_id, thumbnail_path)
      else:
        self.signals.result.emit(self.asset_id, "")
    except Exception as e:
      print(f"生成缩略图失败: {self.asset_id}, 错误: {e}")
      # 如果生成失败，发送空路径
      self.signals.result.emit(self.asset_id, "")