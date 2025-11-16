# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, Set, Optional, Any
from ..settingsdict import SettingsDict
from preppipe.language import TranslationDomain, Translatable

TR_gui_util_tagmanager = TranslationDomain("gui_util_tagmanager")

class TagManager:
    """标签管理器，采用单例模式实现

    负责管理素材标签的增删改查、语义映射、标签字典的持久化等功能
    同时管理标签相关的多语言翻译
    """

    # 单例实例 - 在非多线程环境下简化实现
    _instance: Optional['TagManager'] = None

    # 设置字典中存储标签的键
    SETTINGS_KEY_TAGS = "persistent/assetmanager/custom_asset_tags"

    # 翻译域名
    TRANSLATION_DOMAIN = "gui_util_tagmanager"

    # 标签相关翻译常量（类级别定义，符合项目规范）
    _tr_all = TR_gui_util_tagmanager.tr("tagmanager_all",
        en="All",
        zh_cn="全部",
        zh_hk="全部",
    )
    _tr_background = TR_gui_util_tagmanager.tr("tagmanager_background",
        en="Background",
        zh_cn="背景",
        zh_hk="背景",
    )
    _tr_character = TR_gui_util_tagmanager.tr("tagmanager_character",
        en="Character",
        zh_cn="立绘",
        zh_hk="立繪",
    )
    _tr_other = TR_gui_util_tagmanager.tr("tagmanager_other",
        en="Other",
        zh_cn="其他",
        zh_hk="其他",
    )

    def __new__(cls):
        """单例模式的创建方法 - 在非多线程环境下简化实现"""
        if cls._instance is None:
            cls._instance = super(TagManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # 用于存储标签文本与其语义标识的映射
        self.tag_text_to_semantic: Dict[str, str] = {}
        # 用于存储语义标识与其标签文本的映射
        self.semantic_to_tag_text: Dict[str, Any] = {}
        self._initialize_semantic_mappings()

    @classmethod
    def get_instance(cls) -> 'TagManager':
        # 在非多线程环境下，直接调用构造函数即可
        return cls()

    def _ensure_string(self, obj: Any) -> str:
        """确保对象转换为字符串

        Args:
            obj: 任意对象

        Returns:
            str: 转换后的字符串
        """
        return obj.get() if isinstance(obj, Translatable) else str(obj)

    def _add_tag_mapping(self, translatable_obj: Any, semantic: str) -> None:
        """添加标签映射，遍历翻译对象的所有可能翻译"""
        if isinstance(translatable_obj, Translatable):
            for candidate_text in translatable_obj.get_all_candidates():
                self.tag_text_to_semantic[candidate_text] = semantic
        self.semantic_to_tag_text[semantic] = translatable_obj

    def _initialize_semantic_mappings(self):
        """初始化预定义标签的语义映射关系"""
        self.tag_text_to_semantic.clear()
        self.semantic_to_tag_text.clear()
        self._add_tag_mapping(self._tr_all, "all")
        self._add_tag_mapping(self._tr_background, "background")
        self._add_tag_mapping(self._tr_character, "character")
        self._add_tag_mapping(self._tr_other, "other")

    def update_semantic_mappings(self, all_text: str, background_text: str,
                                character_text: str, other_text: str) -> None:
        """更新语义映射关系"""
        self._tr_all = all_text
        self._tr_background = background_text
        self._tr_character = character_text
        self._tr_other = other_text
        self._initialize_semantic_mappings()

    def add_custom_tag_mapping(self, tag_text: str, semantic: str) -> None:
        """添加自定义标签的语义映射

        Args:
            tag_text: 标签的显示文本
            semantic: 标签的语义标识
        """
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
            SettingsDict.instance().get(self.SETTINGS_KEY_TAGS, {})
        )

    def save_tags_dict(self, tags_dict: Dict[str, Set[str]]) -> None:
        """保存标签字典，并确保只保存语义标识"""
        SettingsDict.instance()[self.SETTINGS_KEY_TAGS] = self.clean_and_normalize_tags_dict(tags_dict)

    def clean_and_normalize_tags_dict(self, tags_dict: Dict[str, Any]) -> Dict[str, Set[str]]:
        """清理和规范化标签字典，确保只包含语义标识"""
        cleaned_dict: Dict[str, Set[str]] = {}
        text_to_semantic = self.tag_text_to_semantic

        for asset_id, tags in tags_dict.items():
            # 简化类型转换逻辑
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

    def add_tag_to_asset(self, asset_id: str, tag_semantic: str) -> None:
        """为资产添加标签"""
        tags_dict = self.get_tags_dict()
        tags_dict.setdefault(asset_id, set()).add(tag_semantic)
        self.save_tags_dict(tags_dict)

    def remove_tag_from_asset(self, asset_id: str, tag_semantic: str) -> bool:
        """从资产中移除标签"""
        tags_dict = self.get_tags_dict()
        asset_tags = tags_dict.get(asset_id)
        if asset_tags and tag_semantic in asset_tags:
            asset_tags.remove(tag_semantic)
            # 如果资产没有标签了，移除该资产的条目
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
        return self._ensure_string(self._tr_all)

    def get_tr_background(self) -> str:
        """获取"背景"标签的翻译文本"""
        return self._ensure_string(self._tr_background)

    def get_tr_character(self) -> str:
        """获取"立绘"标签的翻译文本"""
        return self._ensure_string(self._tr_character)

    def get_tr_other(self) -> str:
        """获取"其他"标签的翻译文本"""
        return self._ensure_string(self._tr_other)