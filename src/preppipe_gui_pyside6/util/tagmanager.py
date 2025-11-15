# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, Set, Optional
from ..settingsdict import SettingsDict
from preppipe.language import TranslationDomain, Translatable

TR_gui_util_tagmanager = TranslationDomain("gui_util_tagmanager")

class TagManager:
    """标签管理器，采用单例模式实现

    负责管理素材标签的增删改查、语义映射、标签字典的持久化等功能
    同时管理标签相关的多语言翻译
    """

    # 单例实例
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
    _tr_tag_edit_current_hint = TR_gui_util_tagmanager.tr("tagmanager_tag_edit_current_hint",
        en="Current tags:",
        zh_cn="当前标签：",
        zh_hk="當前標籤：",
    )
    _tr_select_tag = TR_gui_util_tagmanager.tr("tagmanager_select_tag",
        en="Select tag",
        zh_cn="选择标签",
        zh_hk="選擇標籤",
    )


    def __new__(cls):
        """单例模式的创建方法"""
        if cls._instance is None:
            cls._instance = super(TagManager, cls).__new__(cls)
            # 初始化实例变量
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化标签管理器"""
        # 用于存储标签文本与其语义标识的映射
        self.tag_text_to_semantic: Dict[str, str] = {}
        # 用于存储语义标识与其标签文本的映射
        self.semantic_to_tag_text: Dict[str, str] = {}
        # 初始化语义映射关系
        self._initialize_semantic_mappings()

    @classmethod
    def get_instance(cls) -> 'TagManager':
        """获取标签管理器单例实例

        Returns:
            TagManager: 标签管理器的单例实例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

        # 翻译已在类级别初始化

    def _add_tag_mapping(self, translatable_obj, semantic):
        """
        添加标签映射，遍历翻译对象的所有可能翻译

        Args:
            translatable_obj: Translatable类型的翻译对象
            semantic: 对应的语义标识
        """
        # 使用get_all_candidates()方法获取所有可能的翻译字符串
        if isinstance(translatable_obj, Translatable):
            # 遍历所有可能的翻译字符串，为每个翻译都建立映射
            for candidate_text in translatable_obj.get_all_candidates():
                self.tag_text_to_semantic[candidate_text] = semantic

        # 保留原始翻译对象以便正确显示
        self.semantic_to_tag_text[semantic] = translatable_obj

    def _initialize_semantic_mappings(self):
        """初始化预定义标签的语义映射关系"""
        self.tag_text_to_semantic.clear()
        self.semantic_to_tag_text.clear()

        # 使用_add_tag_mapping方法遍历翻译对象，为每个翻译都建立映射
        self._add_tag_mapping(self._tr_all, "all")
        self._add_tag_mapping(self._tr_background, "background")
        self._add_tag_mapping(self._tr_character, "character")
        self._add_tag_mapping(self._tr_other, "other")

    def update_semantic_mappings(self, all_text: str, background_text: str,
                                character_text: str, other_text: str):
        """更新语义映射关系

        Args:
            all_text: "全部"标签的显示文本
            background_text: "背景"标签的显示文本
            character_text: "立绘"标签的显示文本
            other_text: "其他"标签的显示文本
        """
        # 更新翻译属性
        self._tr_all = all_text
        self._tr_background = background_text
        self._tr_character = character_text
        self._tr_other = other_text
        self._initialize_semantic_mappings()  # 重新初始化，会处理字符串转换

    def add_custom_tag_mapping(self, tag_text: str, semantic: str):
        """添加自定义标签的语义映射

        Args:
            tag_text: 标签的显示文本
            semantic: 标签的语义标识
        """
        self.tag_text_to_semantic[tag_text] = semantic
        self.semantic_to_tag_text[semantic] = tag_text

    def get_tag_semantic(self, tag_text: str) -> str:
        """获取标签显示文本对应的语义标识

        Args:
            tag_text: 标签的显示文本

        Returns:
            str: 标签的语义标识，如果不存在则返回原显示文本
        """
        # 直接在字典中查找，因为初始化时已经将Translatable对象转换为字符串
        return self.tag_text_to_semantic.get(tag_text, tag_text)

    def get_tag_display_text(self, semantic: str) -> str:
        """获取语义标识对应的标签显示文本

        Args:
            semantic: 标签的语义标识

        Returns:
            str: 标签的显示文本，如果不存在则返回原语义标识
        """
        tag_text = self.semantic_to_tag_text.get(semantic, semantic)
        # 确保返回字符串而不是Translatable对象
        return tag_text.get() if isinstance(tag_text, Translatable) else tag_text

    def get_tags_dict(self) -> Dict[str, Set[str]]:
        """获取标签字典，并确保只包含语义标识

        Returns:
            Dict[str, Set[str]]: 标签字典，格式为{asset_id: set_of_semantic_tags}
        """
        settings = SettingsDict.instance()
        tags_dict = settings.get(self.SETTINGS_KEY_TAGS, {})
        # 使用通用函数清理和规范化标签字典
        return self.clean_and_normalize_tags_dict(tags_dict)

    def save_tags_dict(self, tags_dict: Dict[str, Set[str]]):
        """保存标签字典，并确保只保存语义标识

        Args:
            tags_dict: 要保存的标签字典，格式为{asset_id: tags}
        """
        # 使用通用函数清理和规范化标签字典
        cleaned_dict = self.clean_and_normalize_tags_dict(tags_dict)
        settings = SettingsDict.instance()
        settings[self.SETTINGS_KEY_TAGS] = cleaned_dict

    def clean_and_normalize_tags_dict(self, tags_dict: Dict) -> Dict[str, Set[str]]:
        """清理和规范化标签字典，确保只包含语义标识

        Args:
            tags_dict: 待清理的标签字典，格式为{asset_id: tags}

        Returns:
            Dict[str, Set[str]]: 清理后的标签字典，格式为{asset_id: set[str]}
        """
        cleaned_dict: Dict[str, Set[str]] = {}

        for asset_id, tags in tags_dict.items():
            # 确保是集合类型
            if isinstance(tags, set):
                tag_set = tags
            else:
                tag_set = set(tags) if isinstance(tags, (list, set)) else {tags}

            cleaned_tags: Set[str] = set()
            for tag in tag_set:
                # 如果标签是显示文本，转换为语义标识
                if tag in self.tag_text_to_semantic:
                    cleaned_tags.add(self.tag_text_to_semantic[tag])
                else:
                    # 已经是语义标识或自定义标签，直接使用
                    cleaned_tags.add(tag)

            if cleaned_tags:
                cleaned_dict[asset_id] = cleaned_tags

        return cleaned_dict

    def translate_tags(self, tags: Set[str]) -> Set[str]:
        """将语义标识转换为当前语言的显示文本

        Args:
            tags: 语义标识集合

        Returns:
            Set[str]: 翻译后的标签显示文本集合
        """
        translated_tags: Set[str] = set()

        for tag in sorted(tags):
            # 优先检查是否是语义标识
            if tag in self.semantic_to_tag_text:
                # 使用当前语言的翻译文本，并确保转换为字符串
                tag_text = self.semantic_to_tag_text[tag]
                translated_tags.add(tag_text.get() if isinstance(tag_text, Translatable) else tag_text)
            else:
                # 自定义标签保持原样
                translated_tags.add(tag)

        return translated_tags

    def get_asset_tags_display(self, asset_id: str) -> Set[str]:
        """获取资产的显示标签文本集合

        Args:
            asset_id: 资产ID

        Returns:
            Set[str]: 资产的显示标签文本集合
        """
        # 获取资产的语义标签
        semantic_tags = self.get_asset_tags(asset_id)
        # 转换为显示文本
        return self.translate_tags(semantic_tags)

    def add_tag_to_asset(self, asset_id: str, tag_semantic: str):
        """为资产添加标签

        Args:
            asset_id: 资产ID
            tag_semantic: 标签的语义标识
        """
        tags_dict = self.get_tags_dict()
        if asset_id not in tags_dict:
            tags_dict[asset_id] = set()
        tags_dict[asset_id].add(tag_semantic)
        self.save_tags_dict(tags_dict)

    def remove_tag_from_asset(self, asset_id: str, tag_semantic: str) -> bool:
        """从资产中移除标签

        Args:
            asset_id: 资产ID
            tag_semantic: 标签的语义标识

        Returns:
            bool: 如果标签成功移除，返回True，否则返回False
        """
        tags_dict = self.get_tags_dict()
        if asset_id in tags_dict and tag_semantic in tags_dict[asset_id]:
            tags_dict[asset_id].remove(tag_semantic)
            # 如果资产没有标签了，移除该资产的条目
            if not tags_dict[asset_id]:
                del tags_dict[asset_id]
            self.save_tags_dict(tags_dict)
            return True
        return False

    def get_asset_tags(self, asset_id: str) -> Set[str]:
        """获取资产的标签集合

        Args:
            asset_id: 资产ID

        Returns:
            Set[str]: 资产的标签集合（语义标识）
        """
        tags_dict = self.get_tags_dict()
        return tags_dict.get(asset_id, set())

    def get_all_tags(self) -> Set[str]:
        """获取所有标签（语义标识）

        Returns:
            Set[str]: 所有标签的集合
        """
        tags_dict = self.get_tags_dict()
        all_tags: Set[str] = set()
        for tags in tags_dict.values():
            all_tags.update(tags)
        return all_tags

    # 以下是获取翻译文本的方法
    def get_tr_all(self) -> str:
        """获取"全部"标签的翻译文本"""
        return self._tr_all.get() if isinstance(self._tr_all, Translatable) else self._tr_all

    def get_tr_background(self) -> str:
        """获取"背景"标签的翻译文本"""
        return self._tr_background.get() if isinstance(self._tr_background, Translatable) else self._tr_background

    def get_tr_character(self) -> str:
        """获取"立绘"标签的翻译文本"""
        return self._tr_character.get() if isinstance(self._tr_character, Translatable) else self._tr_character

    def get_tr_other(self) -> str:
        """获取"其他"标签的翻译文本"""
        return self._tr_other.get() if isinstance(self._tr_other, Translatable) else self._tr_other





    def get_tr_tag_edit_current_hint(self) -> str:
        """获取当前标签提示的翻译文本"""
        return self._tr_tag_edit_current_hint.get() if isinstance(self._tr_tag_edit_current_hint, Translatable) else self._tr_tag_edit_current_hint

    def get_tr_select_tag(self) -> str:
        """获取"选择标签"的翻译文本"""
        return self._tr_select_tag.get() if isinstance(self._tr_select_tag, Translatable) else self._tr_select_tag