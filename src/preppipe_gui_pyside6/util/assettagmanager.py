# SPDX-FileCopyrightText: 2025 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import enum
from typing import Optional, Any
from PySide6.QtCore import Signal, QObject
from ..settingsdict import SettingsDict
from preppipe.language import TranslationDomain, Translatable

TR_gui_util_assettagmanager = TranslationDomain("gui_util_assettagmanager")
SETTINGS_KEY_TAGS = "persistent/assetmanager/custom_asset_tags"
SETTINGS_KEY_RECENT_TAGS = "assetmanager/recent_tags"
MAX_RECENT_TAGS = 5

'''
考虑到预设标签（如背景、立绘）在多语言切换下可能出现的问题，统一通过sematic_tag
——(1)用户自定义标签 (2)系统标签（enum名称的小写）
机制确保不同语言环境下预设标签的行为一致，而不是直接使用AssetTagType。
'''

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
    return self.value[1]

  @property
  def semantic(self) -> str:
    return self.name.lower()

class AssetTagManager(QObject):
  """素材标签管理器，采用单例模式实现，默认仅从主线程中通过UI交互编辑，较低频操作

  负责管理素材标签的增删改查、语义映射、标签字典的持久化等功能，同时管理标签相关的多语言翻译

  """

  _instance: Optional['AssetTagManager'] = None
  tags_updated = Signal()

  tag_text_to_semantic: dict[str, str]
  semantic_to_tag_text: dict[str, Translatable | str]

  def __new__(cls):
    if cls._instance is None:
      cls._instance = super(AssetTagManager, cls).__new__(cls)
      cls._instance._initialize()
    return cls._instance

  def _initialize(self):
    self.tag_text_to_semantic: dict[str, str] = {}
    self.semantic_to_tag_text: dict[str, Translatable | str] = {}
    self._initialize_semantic_mappings()

  @classmethod
  def get_instance(cls) -> 'AssetTagManager':
    if cls._instance is None:
      cls._instance = cls()
    return cls._instance

  def _ensure_string(self, obj: Any) -> str:
    return str(obj)

  def _add_tag_mapping(self, translatable_obj: Any, semantic: str) -> None:
    if isinstance(translatable_obj, Translatable):
      for candidate_text in translatable_obj.get_all_candidates():
        self.tag_text_to_semantic[candidate_text] = semantic
    self.semantic_to_tag_text[semantic] = translatable_obj

  def _initialize_semantic_mappings(self):
    self.tag_text_to_semantic.clear()
    self.semantic_to_tag_text.clear()

    for tag_type in AssetTagType:
      self._add_tag_mapping(tag_type.translatable, tag_type.semantic)

  def get_tag_semantic(self, tag_text: str) -> str:
    return self.tag_text_to_semantic.get(tag_text, tag_text)

  def get_tag_display_text(self, semantic: str) -> str:
    tag_text = self.semantic_to_tag_text.get(semantic, semantic)
    return self._ensure_string(tag_text)

  def get_tags_dict(self) -> dict[str, set[str]]:
    return self._clean_and_normalize_tags_dict(
      SettingsDict.instance().get(SETTINGS_KEY_TAGS, {})
    )

  def _save_tags_dict(self, tags_dict: dict[str, set[str]]) -> None:
    SettingsDict.instance()[SETTINGS_KEY_TAGS] = self._clean_and_normalize_tags_dict(tags_dict)
    self.tags_updated.emit()

  def _clean_and_normalize_tags_dict(self, tags_dict: dict[str, set[str]]) -> dict[str, set[str]]:
    """清理和规范化标签字典，确保只包含语义标识"""
    cleaned_dict: dict[str, set[str]] = {}
    text_to_semantic = self.tag_text_to_semantic

    for asset_id, tags in tags_dict.items():
      cleaned_tags: set[str] = {text_to_semantic.get(tag, tag) for tag in tags}
      if cleaned_tags:
        cleaned_dict[asset_id] = cleaned_tags

    return cleaned_dict

  def translate_tags(self, tags: set[str]) -> set[str]:
    """将语义标识转换为当前语言的显示文本"""
    semantic_to_text = self.semantic_to_tag_text
    return {
      self._ensure_string(semantic_to_text[tag]) if tag in semantic_to_text else tag
      for tag in sorted(tags)
    }

  def get_asset_tags_display(self, asset_id: str) -> set[str]:
    return self.translate_tags(self.get_asset_tags(asset_id))

  def add_tag_to_asset(self, asset_id: str, tag_semantic: str, temporary: bool = False) -> tuple[bool, bool]:
    """为资产添加标签，返回是否成功添加（标签之前不存在）和是否更新最近标签队列

    Args:
      asset_id: 资产ID
      tag_semantic: 标签的语义标识
      temporary: 是否为临时添加，临时添加时只更新最近标签，不实际保存到资产

    Returns:
      (是否成功添加, 是否更新最近标签)
    """
    if self.is_preset_tag(tag_semantic):
      return False, False

    recent_tags = SettingsDict.instance().get(SETTINGS_KEY_RECENT_TAGS, [])
    if recent_tags is None:
      recent_tags = []

    is_recent_updated = False
    if tag_semantic not in recent_tags:
      is_recent_updated = True
      if len(recent_tags) == MAX_RECENT_TAGS:
        recent_tags.pop()
      recent_tags.insert(0, tag_semantic)
      SettingsDict.instance()[SETTINGS_KEY_RECENT_TAGS] = recent_tags

    if temporary:
      return True, is_recent_updated

    tags_dict = self.get_tags_dict()
    asset_tags = tags_dict.get(asset_id, set())

    if tag_semantic in asset_tags:
      return False, is_recent_updated
    tags_dict.setdefault(asset_id, set()).add(tag_semantic)
    self._save_tags_dict(tags_dict)
    return True, is_recent_updated

  def get_recent_tags(self) -> list[str]:
    return SettingsDict.instance().get(SETTINGS_KEY_RECENT_TAGS, [])

  def get_recent_tags_display(self) -> list[str]:
    recent_semantic_tags = self.get_recent_tags()
    display_tags = []

    for semantic_tag in recent_semantic_tags:
      display_tag = self.get_tag_display_text(semantic_tag)
      display_tags.append(display_tag)

    return display_tags

  def get_asset_tags(self, asset_id: str) -> set[str]:
    return self.get_tags_dict().get(asset_id, set())

  def get_all_tags(self) -> set[str]:
    return {
      tag
      for tags in self.get_tags_dict().values()
      for tag in tags
    }

  def get_tr_all(self) -> str:
    return self._ensure_string(AssetTagType.ALL.translatable)

  def get_tr_background(self) -> str:
    return self._ensure_string(AssetTagType.BACKGROUND.translatable)

  def get_tr_character(self) -> str:
    return self._ensure_string(AssetTagType.CHARACTER_SPRITE.translatable)

  def get_tr_other(self) -> str:
    return self._ensure_string(AssetTagType.OTHER.translatable)

  def get_asset_tag_type_from_semantic(self, semantic: str) -> Optional[AssetTagType]:
    for tag_type in AssetTagType:
      if tag_type.semantic == semantic:
        return tag_type
    return None

  def is_preset_tag(self, semantic: str) -> bool:
    return self.get_asset_tag_type_from_semantic(semantic) is not None

  def update_asset_tags(self, asset_id: str, new_tags: set[str]) -> None:
    tags_dict = self.get_tags_dict()
    tags_dict[asset_id] = new_tags
    self._save_tags_dict(tags_dict)

  def get_sorted_tags(self) -> list[tuple[str, str]]:
    """获取按显示文本升序排列的自定义标签列表

    Returns:
      list: 按显示文本升序排列的(语义标识, 显示文本)元组列表
    """
    custom_tags = []
    for semantic in self.get_all_tags():
      if not self.is_preset_tag(semantic):
        display_text = self.get_tag_display_text(semantic)
        custom_tags.append((semantic, display_text))

    custom_tags.sort(key=lambda x: x[1])
    return custom_tags