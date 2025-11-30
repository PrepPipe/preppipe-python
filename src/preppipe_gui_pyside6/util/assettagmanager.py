# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import enum
from typing import Dict, Set, Optional, Any, List
from ..settingsdict import SettingsDict
from preppipe.language import TranslationDomain, Translatable

TR_gui_util_assettagmanager = TranslationDomain("gui_util_assettagmanager")
SETTINGS_KEY_TAGS = "persistent/assetmanager/custom_asset_tags"
SETTINGS_KEY_RECENT_TAGS = "persistent/assetmanager/recent_tags"
MAX_RECENT_TAGS = 5

class AssetTagType(enum.Enum):
  """素材标签类型枚举，关联翻译文本"""
  ALL = enum.auto(), TR_gui_util_assettagmanager.tr("assettagmanager_all",
    en="All",
    zh_cn="全部",
    zh_hk="全部",
  )
  BACKGROUND = enum.auto(), TR_gui_util_assettagmanager.tr("assettagmanager_background",
    en="Background",
    zh_cn="背景",
    zh_hk="背景",
  )
  CHARACTER_SPRITE = enum.auto(), TR_gui_util_assettagmanager.tr("assettagmanager_character_sprite",
    en="Character Sprite",
    zh_cn="立绘",
    zh_hk="立繪",
  )
  OTHER = enum.auto(), TR_gui_util_assettagmanager.tr("assettagmanager_other",
    en="Other",
    zh_cn="其他",
    zh_hk="其他",
  )

  @property
  def translatable(self) -> Translatable:
    """获取枚举值对应的翻译对象"""
    return self.value[1]

  @property
  def semantic(self) -> str:
    """获取枚举值对应的语义标识"""
    return self.name.lower()

class AssetTagManager:
  """素材标签管理器，采用单例模式实现

  负责管理素材标签的增删改查、语义映射、标签字典的持久化等功能，同时管理标签相关的多语言翻译
  """

  _instance: Optional['AssetTagManager'] = None

  def __new__(cls):
    """单例模式的创建方法"""
    if cls._instance is None:
      cls._instance = super(AssetTagManager, cls).__new__(cls)
      cls._instance._initialize()
    return cls._instance

  def _initialize(self):
    self.tag_text_to_semantic: Dict[str, str] = {}
    self.semantic_to_tag_text: Dict[str, Any] = {}
    self._initialize_semantic_mappings()

  @classmethod
  def get_instance(cls) -> 'AssetTagManager':
    """获取单例实例"""
    return cls()

  def _ensure_string(self, obj: Any) -> str:
    """确保对象转换为字符串"""
    return obj.get() if isinstance(obj, Translatable) else str(obj)

  def _add_tag_mapping(self, translatable_obj: Any, semantic: str) -> None:
    """添加标签映射"""
    if isinstance(translatable_obj, Translatable):
      for candidate_text in translatable_obj.get_all_candidates():
        self.tag_text_to_semantic[candidate_text] = semantic
    self.semantic_to_tag_text[semantic] = translatable_obj

  def _initialize_semantic_mappings(self):
    """初始化预定义标签的语义映射关系"""
    self.tag_text_to_semantic.clear()
    self.semantic_to_tag_text.clear()

    for tag_type in AssetTagType:
      self._add_tag_mapping(tag_type.translatable, tag_type.semantic)

  def update_semantic_mappings(self, all_text: str, background_text: str,
                character_sprite_text: str, other_text: str) -> None:
    """更新预定义标签的语义映射关系"""
    self.tag_text_to_semantic.clear()
    self.semantic_to_tag_text.clear()

    self._add_tag_mapping(all_text, AssetTagType.ALL.semantic)
    self._add_tag_mapping(background_text, AssetTagType.BACKGROUND.semantic)
    self._add_tag_mapping(character_sprite_text, AssetTagType.CHARACTER_SPRITE.semantic)
    self._add_tag_mapping(other_text, AssetTagType.OTHER.semantic)

  def add_custom_tag_mapping(self, tag_text: str, semantic: str) -> None:
    """添加自定义标签的语义映射"""
    self.tag_text_to_semantic[tag_text] = semantic
    self.semantic_to_tag_text[semantic] = tag_text

  def get_tag_semantic(self, tag_text: str) -> str:
    """获取标签显示文本对应的语义标识"""
    return self.tag_text_to_semantic.get(tag_text, tag_text)

  def get_tag_display_text(self, semantic: str) -> str:
    """获取语义标识对应的标签显示文本"""
    tag_text = self.semantic_to_tag_text.get(semantic, semantic)
    return self._ensure_string(tag_text)

  def get_tags_dict(self) -> Dict[str, Set[str]]:
    """获取标签字典，并确保只包含语义标识"""
    return self.clean_and_normalize_tags_dict(
      SettingsDict.instance().get(SETTINGS_KEY_TAGS, {})
    )

  def save_tags_dict(self, tags_dict: Dict[str, Set[str]]) -> None:
    """保存标签字典，并确保只保存语义标识"""
    SettingsDict.instance()[SETTINGS_KEY_TAGS] = self.clean_and_normalize_tags_dict(tags_dict)

  def clean_and_normalize_tags_dict(self, tags_dict: Dict[str, Any]) -> Dict[str, Set[str]]:
    """清理和规范化标签字典，确保只包含语义标识"""
    cleaned_dict: Dict[str, Set[str]] = {}
    text_to_semantic = self.tag_text_to_semantic

    for asset_id, tags in tags_dict.items():
      if isinstance(tags, set):
        tag_set = tags
      elif isinstance(tags, list):
        tag_set = set(tags)
      else:
        tag_set = {tags}

      cleaned_tags: Set[str] = {text_to_semantic.get(tag, tag) for tag in tag_set}
      if cleaned_tags:
        cleaned_dict[asset_id] = cleaned_tags

    return cleaned_dict

  def translate_tags(self, tags: Set[str]) -> Set[str]:
    """将语义标识转换为当前语言的显示文本"""
    semantic_to_text = self.semantic_to_tag_text
    return {
      self._ensure_string(semantic_to_text[tag]) if tag in semantic_to_text else tag
      for tag in sorted(tags)
    }

  def get_asset_tags_display(self, asset_id: str) -> Set[str]:
    """获取资产的显示标签文本集合"""
    return self.translate_tags(self.get_asset_tags(asset_id))

  def add_tag_to_asset(self, asset_id: str, tag_semantic: str) -> tuple[bool, bool]:
    """为资产添加标签，返回是否成功添加（标签之前不存在）和是否更新最近标签队列"""
    if self.is_preset_tag(tag_semantic):
      return False, False

    recent_tags = SettingsDict.instance().get(SETTINGS_KEY_RECENT_TAGS, [])
    if recent_tags is None:
      recent_tags = []

    is_recent_updated = False
    if tag_semantic not in recent_tags:
      recent_tags.remove(tag_semantic)
      is_recent_updated = True

      if len(recent_tags) == MAX_RECENT_TAGS:
        recent_tags.pop()

      recent_tags.insert(0, tag_semantic)
      SettingsDict.instance()[SETTINGS_KEY_RECENT_TAGS] = recent_tags
    elif recent_tags and tag_semantic != recent_tags[0]:
      recent_tags.remove(tag_semantic)
      is_recent_updated = True
      recent_tags.insert(0, tag_semantic)
      SettingsDict.instance()[SETTINGS_KEY_RECENT_TAGS] = recent_tags

    tags_dict = self.get_tags_dict()
    asset_tags = tags_dict.get(asset_id, set())

    if tag_semantic in asset_tags:
      return False, is_recent_updated
    tags_dict.setdefault(asset_id, set()).add(tag_semantic)
    self.save_tags_dict(tags_dict)
    return True, is_recent_updated

  def get_recent_tags(self) -> List[str]:
    """获取最近添加的标签队列"""
    return SettingsDict.instance().get(SETTINGS_KEY_RECENT_TAGS, [])

  def get_recent_tags_display(self) -> List[str]:
    """获取最近添加标签的显示文本列表"""
    recent_semantic_tags = self.get_recent_tags()
    display_tags = []

    for semantic_tag in recent_semantic_tags:
      display_tag = self.get_tag_display_text(semantic_tag)
      display_tags.append(display_tag)

    return display_tags

  def remove_tag_from_asset(self, asset_id: str, tag_semantic: str) -> bool:
    """从资产中移除标签"""
    tags_dict = self.get_tags_dict()
    asset_tags = tags_dict.get(asset_id)
    if asset_tags and tag_semantic in asset_tags:
      asset_tags.remove(tag_semantic)
      if not asset_tags:
        del tags_dict[asset_id]
      self.save_tags_dict(tags_dict)
      return True
    return False

  def get_asset_tags(self, asset_id: str) -> Set[str]:
    """获取资产的标签集合"""
    return self.get_tags_dict().get(asset_id, set())

  def get_all_tags(self) -> Set[str]:
    """获取所有标签（语义标识）"""
    return {
      tag
      for tags in self.get_tags_dict().values()
      for tag in tags
    }

  def get_tr_all(self) -> str:
    """获取"全部"标签的翻译文本"""
    return self._ensure_string(AssetTagType.ALL.translatable)

  def get_tr_background(self) -> str:
    """获取"背景"标签的翻译文本"""
    return self._ensure_string(AssetTagType.BACKGROUND.translatable)

  def get_tr_character(self) -> str:
    """获取"立绘"标签的翻译文本"""
    return self._ensure_string(AssetTagType.CHARACTER_SPRITE.translatable)

  def get_tr_other(self) -> str:
    """获取"其他"标签的翻译文本"""
    return self._ensure_string(AssetTagType.OTHER.translatable)

  def get_asset_tag_type_from_semantic(self, semantic: str) -> Optional[AssetTagType]:
    """根据语义标识获取标签类型枚举值"""
    for tag_type in AssetTagType:
      if tag_type.semantic == semantic:
        return tag_type
    return None

  def is_preset_tag(self, semantic: str) -> bool:
    """判断一个标签是否为预设标签

    Args:
      semantic: 标签的语义标识

    Returns:
      bool: 如果是预设标签返回True，否则返回False
    """
    return self.get_asset_tag_type_from_semantic(semantic) is not None