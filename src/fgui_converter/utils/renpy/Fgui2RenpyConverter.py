#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dis
import sys
import os
import re
import argparse
import math
import shutil
import ast
from enum import IntEnum

# 复合型组件的子组件枚举类型
class DisplayableChildType(IntEnum):
    NULL = 0
    IMAGE = 1
    GRAPH = 2
    TEXT = 3
    COMPONENT = 4
    OTHER = 5

# bar、scrollbar、slider等组件的方向枚举类型
class BarOrientationType(IntEnum):
    HORIZONTAL = 0
    VERTICAL = 1

# 添加当前目录到Python路径，以便导入FguiAssetsParseLib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fgui_converter.FguiAssetsParseLib import *

class FguiToRenpyConverter:
    """
    FairyGUI到Ren'Py转换器
    将FairyGUI资源转换为Ren'Py的screen语言
    """

    # 静态变量
    # 文本对齐的转义字典
    align_dict = {"left": 0.0, "center": 0.5, "right": 1.0, "top": 0.0, "middle": 0.5, "bottom": 1.0}
    # 4个空格作为缩进基本单位
    indent_unit = '    '

    # 默认背景色，在某些未指定image的情况下用作填充。
    default_background = '#fff'

    # 滚动条默认样式。empty 的效果为不显示。
    default_scrollbar_style = 'empty'

    # 菜单类界面名称，需要添加 tag menu。
    menu_screen_name_list = ['main_menu', 'game_menu', 'save', 'load', 'preferences', 'history', 'help', 'about']

    # 模态类界面名称，需要添加 Modal True。
    modal_screen_name_list = ['confirm']

    # 选项分支界面。
    choice_screen_name_list = ['choice']

    # 对话界面
    say_screen_name_list = ['say']

    # 存档相关界面
    save_load_screen_name_list = ['save', 'load']

    # 历史界面
    history_screen_name_list = ['history']
    history_item_screen_name_list = ['history_item']
    
    # 图鉴类界面
    gallery_screen_name_list = ['gallery', 'music_room']

    # 所以特殊界面名
    special_screen_name_list = []

    # 主管线提供的gallery数据文件
    ui_helper_file_name = '01_ui_helper.rpy'

    def __init__(self, fgui_assets):
        self.fgui_assets = fgui_assets
        self.renpy_code = []
        self.screen_code = []
        self.screen_definition_head = []
        self.screen_variable_code = []
        self.screen_function_code = []
        self.screen_ui_code = []
        self.style_code = []
        self.image_definition_code = []
        self.graph_definition_code = []
        self.game_global_variables_code = []
        self.gallery_screen_code = []
        self.music_room_screen_code = []

        # 所有特殊界面名
        self.special_screen_name_list = self.menu_screen_name_list + self.modal_screen_name_list + self.choice_screen_name_list + self.say_screen_name_list + self.save_load_screen_name_list + self.history_screen_name_list + self.gallery_screen_name_list
        
        # dismiss用于取消一些组件的focus状态，例如input。
        self.screen_has_dismiss = False
        self.dismiss_action_list = []
        self.current_component_name = None

        # 字体名称列表。SourceHanSansLite为Ren'Py默认字体。
        self.font_name_list = ["SourceHanSansLite"]

        # 组件缩进级别
        self.root_indent_level = 0
        # 缩进字符串
        self.indent_str = ''

        # 部分模板与预设目录
        # self.renpy_template_dir = 'renpy_templates'
        self.renpy_template_dir = os.environ.get('RENPY_TEMPLATES_DIR', 
                             os.path.join(os.path.dirname(os.path.abspath(__file__)), "renpy_templates"))
        self.font_map_template = 'renpy_font_map_definition.txt'
        self.graph_template_dict = {}
        self.graph_template_dict['null'] = self.get_template_content('renpy_null_template.txt')
        self.graph_template_dict['rectangle'] = self.get_template_content('renpy_rectangle_template.txt')
        self.graph_template_dict['ellipse'] = self.get_template_content('renpy_ellipse_template.txt')
        self.gallery_template_dict = {}
        self.gallery_template_dict['gallery'] = self.get_template_content('renpy_gallery_template.txt')
        self.gallery_template_dict['music_room'] = self.get_template_content('renpy_music_room_template.txt')
        self.style_preset = ''
        self.style_preset_template = 'renpy_style_preset_template.txt'
        self.style_preset = self.get_template_content(self.style_preset_template)
        self.list_screen_template = self.get_template_content('renpy_list_screen_template.txt')

        # 输出游戏目录
        self.game_dir = None
        self.scripts_dir = None
        self.images_dir = None

        # gallery相关数据
        self.gallery_data = {}

        # 一些样式预设，用于覆盖Ren'Py默认样式。
        self.style_code.append(self.style_preset)

    def set_game_global_variables(self, variable_name, variable_value):
        variable_str = f"define {variable_name} = {variable_value}"
        self.game_global_variables_code.append(variable_str)
        self.game_global_variables_code.append('')

    def calculate_indent(self):
        self.indent_str = self.indent_unit * self.root_indent_level
        return self.indent_str

    def indent_level_up(self, levelup=1):
        self.root_indent_level += levelup
        self.indent_str = self.indent_unit * self.root_indent_level

    def indent_level_down(self, leveldown=1):
        self.root_indent_level = max(self.root_indent_level-leveldown, 0)
        self.indent_str = self.indent_unit * self.root_indent_level

    def reset_indent_level(self, indent_level=0):
        self.root_indent_level = indent_level
        self.indent_str = ''

    def generate_image_definitions(self):
        """生成图像定义"""
        image_definitions = []
        image_definitions.append("# 图像定义")
        image_definitions.append("# 从FairyGUI图集中提取的图像")

        if not self.fgui_assets.fgui_image_set:
            print("Image set is Null.")

        for sprite in self.fgui_assets.fgui_image_set:
            # 找到对应的图像信息
            image_info = None
            image_name = ''
            image_scale = None
            image_scale9grid = None
            for img in self.fgui_assets.package_desc.image_list:
                if img.id == sprite.image_id:
                    image_info = sprite
                    image_name = img.name
                    image_scale = img.scale
                    image_scale9grid = img.scale9grid
                    break

            # GetOriImage(image_id, package_desc, fgui_image_sets, fgui_atlas_dicts)

            if image_info:
                atlas_index = image_info.atlas_index
                atlas_key = f"atlas{atlas_index}"
                atlas_file = self.fgui_assets.fgui_atlas_dicts[atlas_key]
                # 计算在图集中的位置
                x, y = sprite.x, sprite.y
                width, height = sprite.width, sprite.height

                # 生成Ren'Py图像定义
                # 由于Ren'Py中文件名带 @ 表示过采样，替换为下划线 _
                atlas_file = atlas_file.replace('@', '_').lower()
                image_name = image_name.replace('@', '_')
                # 九宫格
                if image_scale == "9grid":
                    ima_str = f'im.Crop("{atlas_file}", ({x}, {y}, {width}, {height}))'
                    # FGUI中的border是相对x轴和y轴的偏移量，需要根据尺寸再计算为宽度或高度
                    left = int(image_scale9grid[0])
                    top = int(image_scale9grid[1])
                    right = width - left - int(image_scale9grid[2])
                    bottom = height - top - int(image_scale9grid[3])
                    border_str = f"{left}, {top}, {right}, {bottom}"
                    image_definitions.append(f'image {image_name} = Frame({ima_str}, {border_str})')
                # 平铺
                elif image_scale == "tile":
                    # image bg tile = Tile("bg.png")
                    ima_str = f'im.Crop("{atlas_file}", ({x}, {y}, {width}, {height}))'
                    image_definitions.append(f'image {image_name} = Tile({ima_str})')
                # 无拉伸普通图片
                else:
                    image_definitions.append(f'image {image_name} = im.Crop("{atlas_file}", ({x}, {y}, {width}, {height}))')

        image_definitions.append("")
        self.image_definition_code.extend(image_definitions)

    def generate_graph_definitions(self, fgui_graph : FguiGraph, component_name : str) -> list:
        """
        生成图形组件定义。返回字符串用于非screen定义。
        图形组件有多种类别：
        None: 空白
        rect: 矩形(可带圆角)
        eclipse: 椭圆(包括圆形)
        regular_polygon: 正多边形
        polygon: 多边形
        """
        graph_code = []
        graph_img_def = ''

        if not isinstance(fgui_graph, FguiGraph):
            print("It is not a graph displayable.")
            return graph_code

        xoffset = 0
        yoffset = 0
        if not fgui_graph.pivot_is_anchor:
            size = fgui_graph.size
            xoffset = int(fgui_graph.pivot[0] * size[0])
            yoffset = int(fgui_graph.pivot[1] * size[1])

        # 空白使用Null。
        if fgui_graph.type is None:
            # graph_code.append(f"{self.indent_str}null width {fgui_graph.size[0]} height {fgui_graph.size[1]}")
            self.graph_template_dict['null'].replace('{image_name}', f"{component_name}_{fgui_graph.id}")\
                                .replace('{width}', str(fgui_graph.size[0]))\
                                .replace('{height}', str(fgui_graph.size[1]))
        # 矩形(圆边矩形)。原生组件不支持圆边矩形，使用自定义shader实现。
        elif fgui_graph.type == "rect":
            # renpy_rectangle_template.txt模板已在转换器初始化读取。模板代码 self.self.graph_template_dict['rectangle'] 。
            graph_img_def = self.graph_template_dict['rectangle'].replace('{image_name}', f"{component_name}_{fgui_graph.id}")\
                                .replace('{rectangle_color}', str(rgba_normalize(fgui_graph.fill_color)))\
                                .replace('{stroke_color}', str(rgba_normalize(fgui_graph.stroke_color)))\
                                .replace('{image_size}', str(fgui_graph.size))\
                                .replace('{round_radius}', str(fgui_graph.corner_radius))\
                                .replace('{stroke_thickness}', str(fgui_graph.stroke_width))\
                                .replace('{xysize}', str(fgui_graph.size))\
                                .replace('{pos}', str(fgui_graph.xypos))\
                                .replace('{anchor}', str(fgui_graph.pivot))\
                                .replace('{xoffset}', str(xoffset))\
                                .replace('{yoffset}', str(yoffset))\
                                .replace('{transform_anchor}', str(True)) \
                                .replace('{rotate}', str(fgui_graph.rotation))\
                                .replace('{alpha}', str(fgui_graph.alpha))\
                                .replace('{xzoom}', str(fgui_graph.scale[0]))\
                                .replace('{yzoom}', str(fgui_graph.scale[1]))
        # 椭圆(圆形)。Ren'Py尚不支持椭圆，使用自定义shader实现。
        elif fgui_graph.type == "eclipse":
            graph_img_def = self.graph_template_dict['ellipse'].replace('{image_name}', f"{component_name}_{fgui_graph.id}")\
                                .replace('{ellipse_color}', str(rgba_normalize(fgui_graph.fill_color)))\
                                .replace('{stroke_color}', str(rgba_normalize(fgui_graph.stroke_color)))\
                                .replace('{image_size}', str(fgui_graph.size))\
                                .replace('{stroke_thickness}', str(fgui_graph.stroke_width))\
                                .replace('{xysize}', str(fgui_graph.size))\
                                .replace('{pos}', str(fgui_graph.xypos))\
                                .replace('{anchor}', str(fgui_graph.pivot))\
                                .replace('{xoffset}', str(xoffset))\
                                .replace('{yoffset}', str(yoffset))\
                                .replace('{transform_anchor}', str(True)) \
                                .replace('{rotate}', str(fgui_graph.rotation))\
                                .replace('{alpha}', str(fgui_graph.alpha))\
                                .replace('{xzoom}', str(fgui_graph.scale[0]))\
                                .replace('{yzoom}', str(fgui_graph.scale[1]))
        elif fgui_graph.type == "regular_polygon":
            print("regular_polygon not implemented.")
            pass
        # 在整个脚本对象中添加graph定义。
        graph_code.append(graph_img_def)

        return graph_code

    def generate_slider_style(self, fgui_slider : FguiSlider) -> None:
        """
        生成滑块样式。
        Ren'Py生成的滑动条效果与FGUI略有不同。
        FGUI的左侧激活状态bar会在水平方向随滑块缩放，Ren'Py不会缩放。
        目标样例：
        image horizontal_idle_thumb_image:
            "horizontal_thumb_base"

        image horizontal_hover_thumb_image:
            "horizontal_thumb_active"

        image horizontal_idle_bar_image:
            "horizontal_bar_base"

        image horizontal_hover_bar_image:
            "horizontal_bar_active"

        style horizontal_slider:
            bar_vertical False
            xsize 540
            ysize 3
            thumb_offset 24
            left_bar "horizontal_hover_bar_image"
            right_bar "horizontal_idle_bar_image"
            thumb Fixed(Frame("horizontal_[prefix_]thumb_image",xsize=48,ysize=54,ypos=-22))
        """
        bar_image_definition_code = []
        style_definition_code = []
        slider_style_code = []
        if not isinstance(fgui_slider, FguiSlider):
            print("It is not a slider.")
            return

        # 默认为水平滑块。实际需要根据grip中relation的sidePair属性来确定。
        slider_type = BarOrientationType.HORIZONTAL
        # bar的第一段，水平方向为right_bar，垂直方向为top_bar
        first_bar_name = ''
        # bar的第二段，水平方向为left_bar，垂直方向为bottom_bar
        second_bar_name = ''
        # 滑块图片名
        thumb_idle_name = ''
        thumb_hover_name = ''

        # bar id，在grip的relation_dict中作为key查找值
        bar_id = ''
        grip_com = None
        # 滑块位置，用做偏移
        thumb_xpos, thumb_ypos = 0, 0

        # slider 组件固定由两张图片(图形)和一个按钮构成，可能还有一个文本组件。
        # 图片(图形)固定名称为n0和bar，按钮固定名称grip，文本组件固定名称title。
        # 其他组件暂不处理。
        for displayable in fgui_slider.display_list.displayable_list:
            # FGUI中滑动条的背景
            if displayable.name == 'n0':
                if isinstance(displayable, FguiImage):
                    second_bar_name = self.fgui_assets.get_componentname_by_id(displayable.src)
                elif isinstance(displayable, FguiGraph):
                    bar_image_definition_code.extend(self.generate_graph_definitions(displayable, fgui_slider.name))
                    second_bar_name = f"{fgui_slider.name}_{displayable.id}"
                else:
                    print("Slider base is neither image nor graph.")
                    return
            # FGUI中滑动条的可变bar部分
            if displayable.name == 'bar':
                if isinstance(displayable, FguiImage):
                    first_bar_name = self.fgui_assets.get_componentname_by_id(displayable.src)
                elif isinstance(displayable, FguiGraph):
                    bar_image_definition_code.extend(self.generate_graph_definitions(displayable, fgui_slider.name))
                    first_bar_name = f"{fgui_slider.name}_{displayable.id}"
                else:
                    print("Slider bar is neither image nor graph.")
                    return
                bar_id = displayable.id
            # FGUI中滑动条的标题类型文本
            if displayable.name == 'title':
                if isinstance(displayable, FguiText):
                    style_name = f"slider_{fgui_slider.id}_title"
                    self.generate_text_style(displayable, style_name)
                else:
                    print("Slider title is not text.")
                    return
            # FGUI中滑动条的滑块按钮
            if displayable.name == 'grip':
                grip_com = self.fgui_assets.get_component_by_id(displayable.src)
                if isinstance(grip_com, FguiButton):
                    # grip是按钮，会生成对应的image对象
                    thumb_idle_name = f"{fgui_slider.name}_grip_idle_background"
                    thumb_hover_name = f"{fgui_slider.name}_grip_hover_background"
                    thumb_xpos, thumb_ypos = displayable.xypos
                    # 根据grip中relation的sidePair属性来确定方向
                    side_pair_str = displayable.relations.relation_dict[bar_id]
                    # 只有该值表示垂直滑动条
                    if side_pair_str == "bottom-bottom":
                        slider_type = BarOrientationType.VERTICAL
                else:
                    print("Slider grp is not button.")
                    return

        # 生成bar和thumb的image
        bar_image_definition_code.append(f"image {fgui_slider.name}_base_bar_image:")
        bar_image_definition_code.append(f"{self.indent_unit}'{second_bar_name}'")
        bar_image_definition_code.append(f"image {fgui_slider.name}_active_bar_image:")
        bar_image_definition_code.append(f"{self.indent_unit}'{first_bar_name}'")
        bar_image_definition_code.append(f"image {fgui_slider.name}_idle_thumb_image:")
        bar_image_definition_code.append(f"{self.indent_unit}'{thumb_idle_name}'")
        bar_image_definition_code.append(f"image {fgui_slider.name}_hover_thumb_image:")
        bar_image_definition_code.append(f"{self.indent_unit}'{thumb_hover_name}'")
        bar_image_definition_code.append("")

        is_vertical = (slider_type==BarOrientationType.VERTICAL)
        thumb_offset = int(grip_com.size[1]/2) if is_vertical else int(grip_com.size[0]/2)
        style_definition_code.append(f"style {fgui_slider.name}:")
        style_definition_code.append(f"{self.indent_unit}bar_vertical {is_vertical}")
        style_definition_code.append(f"{self.indent_unit}xysize {fgui_slider.size}")
        style_definition_code.append(f"{self.indent_unit}thumb_offset {thumb_offset}")
        if is_vertical:
            style_definition_code.append(f"{self.indent_unit}top_bar '{second_bar_name}'")
            style_definition_code.append(f"{self.indent_unit}bottom_bar '{first_bar_name}'")
            thumb_ypos = 0
        else:
            style_definition_code.append(f"{self.indent_unit}left_bar '{first_bar_name}'")
            style_definition_code.append(f"{self.indent_unit}right_bar '{second_bar_name}'")
            thumb_xpos = 0
        style_definition_code.append(f"{self.indent_unit}thumb Fixed(Frame('{fgui_slider.name}_[prefix_]thumb_image',xysize={grip_com.size},pos=({thumb_xpos},{thumb_ypos})))")
        style_definition_code.append("")

        # 添加头部注释
        slider_style_code.extend(bar_image_definition_code)
        slider_style_code.append("# 滑动条样式定义")
        slider_style_code.extend(style_definition_code)

        self.style_code.extend(slider_style_code)

    def generate_scroll_bar_style(self, fgui_scrollbar : FguiScrollBar) -> None:
        """
        生成滚动条样式。
        目标样例：
        style vertical_scrollbar:
            bar_vertical True
            bar_invert True
            xsize 12
            base_bar Frame("vertical_scrollbar_bar")
            thumb Frame("vertical_scrollbar_grip_[prefix_]background")
        """
        # scrollbar_image_definition_code = []
        style_definition_code = []
        scrollbar_style_code = []
        if not isinstance(fgui_scrollbar, FguiScrollBar):
            print("It is not a scrollbar.")
            return

        # 滚动条组件固定由至少两张图片(图形)和一个按钮构成。
        # 固定包含名为bar的空组件，用于判断滚动条方向。
        # 按钮固定名称grip，其内部图片用于Ren'Py滚动条的thumb。
        # 其他图片组件用于Ren'Py滚动条的bar。
        bar_displayable_list = []
        grip_displayable = None
        is_vertical = False
        for displayable in fgui_scrollbar.display_list.displayable_list:
            # FGUI中滚动条的bar部分。只包含图片组件。暂存到bar_displayable_list。
            if displayable.name != 'bar' and displayable.name != 'grip':
                if isinstance(displayable, FguiImage):
                    bar_displayable_list.append((displayable, DisplayableChildType.IMAGE))
                elif isinstance(displayable, FguiGraph):
                    bar_displayable_list.append((displayable, DisplayableChildType.GRAPH))
                elif isinstance(displayable, FguiText):
                    bar_displayable_list.append((displayable, DisplayableChildType.TEXT))
                else:
                    print("Scrollbar bar has non-image, graph or text component.")
                    return
            # FGUI中滚动条的按钮
            if displayable.name == 'grip':
                grip_displayable = displayable
            # 根据bar部分判断滚动条方向
            if displayable.name == 'bar' and isinstance(displayable, FguiGraph):
                # 根据relation中的sidePair属性判断滚动条方向
                side_pair_str = displayable.relations.relation_dict['']
                if side_pair_str == "height-height":
                    is_vertical = True
                else:
                    is_vertical = False

        # 检查bar_displayable_list是否为空
        if len(bar_displayable_list) == 0:
            print("Scrollbar has no bar.")
            return scrollbar_style_code
        # 检查按钮
        if grip_displayable is None:
            print("Scrollbar has no grip.")
            return

        # 生成bar和thumb的image定义
        # 滚动条的bar部分为复合图片对象，包含所有bar_displayable_list中的图片。
        # 暂时不处理图片的transform。
        self.generate_composite_image_object(f"{fgui_scrollbar.name}_idle_bar", bar_displayable_list, fgui_scrollbar.name, fgui_scrollbar.size)

        # 获取按钮的实际引用组件
        grip_com = self.fgui_assets.get_component_by_id(grip_displayable.src)
        if isinstance(grip_com, FguiButton):
            # grip按钮的图片定义已在其他地方生成，此处指需要获取其图片名。
            thumb_image_name = f"{fgui_scrollbar.name}_grip_[prefix_]background"
        else:
            print("Scrollbar grip is not button.")
            return
            
        # 生成scrollbar样式
        scrollbar_style_code.append(f"style {fgui_scrollbar.name}:")
        scrollbar_style_code.append(f"{self.indent_unit}bar_vertical {is_vertical}")
        scrollbar_style_code.append(f"{self.indent_unit}bar_invert {is_vertical}")
        scrollbar_style_code.append(f"{self.indent_unit}xysize {fgui_scrollbar.size}")
        scrollbar_style_code.append(f"{self.indent_unit}base_bar Frame('{fgui_scrollbar.name}_[prefix_]bar')")
        scrollbar_style_code.append(f"{self.indent_unit}thumb Frame('{thumb_image_name}')")
        scrollbar_style_code.append("")

        # 添加头部注释
        # scrollbar_style_code.extend(scrollbar_image_definition_code)
        scrollbar_style_code.append("# 滚动条样式定义")
        scrollbar_style_code.extend(style_definition_code)

        self.style_code.extend(scrollbar_style_code)

    @staticmethod
    def is_menu_screen(screen_name : str):
        return screen_name in FguiToRenpyConverter.menu_screen_name_list
    
    @staticmethod
    def is_modal_screen(screen_name : str):
        return screen_name in FguiToRenpyConverter.modal_screen_name_list

    @staticmethod
    def is_choice_screen(screen_name : str):
        return screen_name in FguiToRenpyConverter.choice_screen_name_list

    @staticmethod
    def is_say_screen(screen_name : str):
        return screen_name in FguiToRenpyConverter.say_screen_name_list

    @staticmethod
    def is_save_load_screen(screen_name : str):
        return screen_name in FguiToRenpyConverter.save_load_screen_name_list

    @staticmethod
    def is_history_screen(screen_name : str):
        return screen_name in FguiToRenpyConverter.history_screen_name_list

    @staticmethod
    def is_history_item(screen_name : str):
        return screen_name in FguiToRenpyConverter.history_item_screen_name_list

    @staticmethod
    def is_gallery_screen(screen_name : str):
        return screen_name == 'gallery'

    @staticmethod
    def is_music_room_screen(screen_name : str):
        return screen_name == 'music_room'

    def convert_component_display_list(self, component: FguiComponent, list_begin_index=0, list_end_index=-1) -> list:
        screen_ui_code = []
        # print(f"list_begin_index: {list_begin_index}, list_end_index: {list_end_index}")
        end_index = len(component.display_list.displayable_list) if (list_end_index == -1) else list_end_index
        for displayable in component.display_list.displayable_list[list_begin_index:end_index]:
            # print(displayable.name)
            # 图片组件
            if isinstance(displayable, FguiImage):
                screen_ui_code.extend(self.generate_image_displayable(displayable))
            # 图形组件
            elif isinstance(displayable, FguiGraph):
                screen_ui_code.extend(self.generate_graph_displayable(displayable))
            # 文本组件
            elif isinstance(displayable, FguiText):
                screen_ui_code.extend(self.generate_text_displayable(displayable))
            # 列表
            elif isinstance(displayable, FguiList):
                screen_ui_code.extend(self.generate_list_displayable(displayable))
            # 装载器
            elif isinstance(displayable, FguiLoader):
                pass
            # 其他组件
            else:
                end_indent_level = 1

                # 根据显示控制器gearDisplay设置显示条件
                if displayable.gear_display:
                    condition_str = f"showif {displayable.gear_display.controller_name} in {displayable.gear_display.controller_index}:"
                    screen_ui_code.append(f"{self.indent_str}{condition_str}")
                    self.indent_level_up()
                    end_indent_level = 2
                
                # 根据引用源id查找组件
                ref_com = self.fgui_assets.get_component_by_id(displayable.src)
                # 按钮。可设置标题，并根据自定义数据字段设置action。
                if ref_com.extention == "Button" and ref_com.name != None:
                    screen_ui_code.append(f"{self.indent_str}fixed:")
                    self.indent_level_up()
                    screen_ui_code.append(f"{self.indent_str}pos {displayable.xypos}")
                    # 取FguiComponent和FguiDisplayable对象的自定义数据作为action。FguiDisplayable对象中的自定义数据优先。
                    actions = displayable.custom_data if displayable.custom_data else ref_com.custom_data
                    action_list = []
                    if actions:
                        action_list.append(actions)
                    # 此处仅处理了title，而未处理selected_title。后续可能需要添加。
                    if displayable.button_property:
                        if displayable.button_property.controller_name:
                            button_controller_action = f"SetScreenVariable('{displayable.button_property.controller_name}', {displayable.button_property.controller_index})"
                            action_list.append(button_controller_action)
                            actions = f"[{', '.join(action_list)}]"
                        parameter_str = self.generate_button_parameter(displayable.button_property.title, actions)
                    else:
                        parameter_str = self.generate_button_parameter(None, actions)
                    screen_ui_code.append(f"{self.indent_str}use {ref_com.name}({parameter_str}) id '{component.name}_{displayable.id}'")
                    self.indent_level_down(end_indent_level)
                    continue
                # 滑动条
                if ref_com.extention == "Slider" and ref_com.name != None:
                    screen_ui_code.append(f"{self.indent_str}fixed:")
                    self.indent_level_up()
                    screen_ui_code.append(f"{self.indent_str}pos {displayable.xypos}")
                    # 若在自定义数据中指定了关联数据对象，则直接使用。
                    if displayable.custom_data:
                        bar_value = displayable.custom_data
                    # 否则再查找引用源对象的自定义数据
                    elif ref_com.custom_data:
                        bar_value = ref_com.custom_data
                    # 若未指定则在screen中生成一个临时变量
                    else:
                        variable_name = f"{component.name}_{displayable.name}_barvalue"
                        screen_ui_code.append(f"{self.indent_str}{self.generate_variable_definition_str(variable_name, current_value=displayable.slider_property.current_value)}")
                        bar_value = self.generate_barvalue_definition_str(variable_name, min_value=displayable.slider_property.min_value, max_value=displayable.slider_property.max_value)
                    screen_ui_code.append(f"{self.indent_str}bar value {bar_value} style '{ref_com.name}' id '{component.name}_{displayable.id}'")
                    self.indent_level_down(end_indent_level)
                    continue
                # 其他组件
                screen_ui_code.append(f"{self.indent_str}fixed:")
                self.indent_level_up()
                screen_ui_code.append(f"{self.indent_str}pos {displayable.xypos}")
                screen_ui_code.append(f"{self.indent_str}use {ref_com.name} id '{component.name}_{displayable.id}'")
                self.indent_level_down(end_indent_level)

        return screen_ui_code

    def generate_screen(self, component : FguiComponent):
        """
        生成screen定义。目标样例：

        screen test_main_menu():
            add 'menu_bg':
                pos (0, 0)

            fixed:
                pos (1007, 178)
                use main_menu_button(title='开坑', actions=ShowMenu("save"))
            fixed:
                pos (1007, 239)
                use main_menu_button(title='填坑', actions=ShowMenu("load"))
            fixed:
                pos (1007, 300)
                use main_menu_button(title='设置', actions=ShowMenu("preferences"))
            fixed:
                pos (1007, 361)
                use main_menu_button(title='关于', actions=ShowMenu("about"))
            fixed:
                pos (1007, 422)
                use main_menu_button(title='帮助', actions=ShowMenu("help"))
            fixed:
                pos (1007, 483)
                use main_menu_button(title='放弃', actions=Quit())
        """
        # self.screen_code.clear()
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()
        choice_screen_code = []

        self.screen_definition_head.append("# 界面定义")
        self.screen_definition_head.append(f"# 从FairyGUI组件{component.name}转换而来")

        id = component.id
        screen_name = component.name
        self.current_component_name = screen_name

        # 界面入参列表
        screen_params = ''

        # choice界面的特殊处理
        if self.is_choice_screen(screen_name):
            self.generate_choice_screen(component)
            return

        # say界面的特殊处理
        if self.is_say_screen(screen_name):
            self.generate_say_screen(component)
            return

        # save和load界面的特殊处理
        if self.is_save_load_screen(screen_name):
            self.generate_save_load_screen(component)
            return

        # history_item和history界面的特殊处理
        if self.is_history_item(screen_name):
            self.generate_history_item(component)
            return
        if self.is_history_screen(screen_name):
            self.generate_history_screen(component)
            return

        # gallery和music_room界面的特殊处理
        if self.is_gallery_screen(screen_name):
            self.generate_gallery_screen(component)
            return
        if self.is_music_room_screen(screen_name):
            self.generate_music_room_screen(component)
            return

        # confirm 界面固定入参
        if screen_name == 'confirm':
            screen_params = 'message, yes_action, no_action'

        self.reset_indent_level()
        self.screen_definition_head.append(f"screen {screen_name}({screen_params}):")
        self.indent_level_up()
        if self.is_menu_screen(screen_name):
            self.screen_ui_code.append(f"{self.indent_str}tag menu\n")
            # 若自定义了game_menu，则修改默认游戏内菜单显示的控制变量。
            if screen_name == "game_menu":
                self.set_game_global_variables('_game_menu_screen', str("\"game_menu\""))
        if self.is_modal_screen(screen_name):
            self.screen_ui_code.append(f"{self.indent_str}modal True")
            self.screen_ui_code.append(f"{self.indent_str}zorder 200\n")

        # 根据控制器列表定义界面内变量
        if component.controller_list:
            self.screen_variable_code.append(f"{self.indent_str}# 由组件控制器生成的界面内控制变量：") 
        for controller in component.controller_list:
            if not isinstance(controller, FguiController):
                print("Component controller object type is wrong.")
                break
            self.screen_variable_code.append(f"{self.indent_str}default {controller.name} = {controller.selected}")            

        # 根据组件的可见区域性质，决定是否加一层viewport。
        if component.overflow == "hidden":
            self.screen_ui_code.append(f"{self.indent_str}viewport:")
            self.indent_level_up()
            self.screen_ui_code.append(f"{self.indent_str}xysize {component.size}")
        elif component.overflow == "scroll":
            self.screen_ui_code.append(f"{self.indent_str}viewport:")
            self.indent_level_up()
            self.screen_ui_code.append(f"{self.indent_str}xysize {component.size}")
            self.screen_ui_code.append(f"{self.indent_str}draggable True") 
            # 在Ren'Py中实际可能无法滚动。
            # 需要添加一个fixed组件，并设置一个合适的xysize。该xysize应为容纳所有子组件的包围框。
            self.screen_ui_code.append(f"{self.indent_str}fixed:")
            self.indent_level_up()
            self.screen_ui_code.append(f"{self.indent_str}xysize ({component.bbox_width}, {component.bbox_height})")

        self.screen_ui_code.extend(self.convert_component_display_list(component))

        self.screen_code.extend(self.screen_definition_head)
        if self.screen_variable_code:
            self.screen_code.extend(self.screen_variable_code)
            self.screen_code.append("")
        if self.screen_function_code:
            self.screen_code.extend(self.screen_function_code)
            self.screen_code.append("")
        # 添加只有1个生效的dismiss
        if self.screen_has_dismiss:
            self.screen_ui_code.append(f"{self.indent_str}dismiss:")
            self.indent_level_up()
            self.screen_ui_code.append(f"{self.indent_str}modal False")
            dismiss_action_list = ', '.join(self.dismiss_action_list)
            self.screen_ui_code.append(f"{self.indent_str}action [{dismiss_action_list}]")

        self.screen_ui_code.append("")
        self.screen_code.extend(self.screen_ui_code)

    def generate_choice_screen(self, component : FguiComponent):
        print("This is choice screen.")
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()
        caption_text = None
        choice_button = None
        choice_list = None

        for displayable in component.display_list.displayable_list:
            # 生成标题文本样式
            if displayable.name == 'caption' and isinstance(displayable, FguiText):
                self.generate_text_style(displayable, "choice_caption_text_style")
                caption_text = displayable
            # 查找第一个列表
            if isinstance(displayable, FguiList) and choice_list == None:
                choice_list = displayable
                choice_button = self.fgui_assets.get_component_by_id(displayable.default_item_id)

        # 检查查找结果
        if choice_list == None:
            print("Lack of choice button list.")
            return
        if not isinstance(choice_button, FguiButton):
            print("Choice button list's item is not Button.")
            return

        choice_screen_code = []
        screen_params = 'items'
        choice_screen_code.append(f"# 选项界面")
        choice_screen_code.append(f"screen {component.name}({screen_params}):")

        # vbox的行距
        vbox_spacing = choice_list.line_gap if choice_list else 0
        self.reset_indent_level()
        self.indent_level_up()
        # 选项菜单标题
        choice_screen_code.append(f"{self.indent_str}fixed:")
        self.indent_level_up()
        choice_screen_code.append(f"{self.indent_str}pos {caption_text.xypos}")
        choice_screen_code.append(f"{self.indent_str}for i in items:")
        self.indent_level_up()
        choice_screen_code.append(f"{self.indent_str}if not i.action:")
        self.indent_level_up()
        choice_screen_code.append(f"{self.indent_str}text i.caption style 'choice_caption_text_style'")
        self.indent_level_down(3)
        # 选项菜单按钮列表
        choice_screen_code.append(f"{self.indent_str}vbox:")
        self.indent_level_up()
        choice_screen_code.append(f"{self.indent_str}spacing {vbox_spacing}")
        choice_screen_code.append(f"{self.indent_str}pos {choice_list.xypos}")
        choice_screen_code.append(f"{self.indent_str}for i in items:")
        self.indent_level_up()
        choice_screen_code.append(f"{self.indent_str}if i.action:")
        self.indent_level_up()
        parameter_str = f"title=i.caption, actions=i.action"
        choice_screen_code.append(f"{self.indent_str}use {choice_button.name}({parameter_str})")
        self.reset_indent_level()

        choice_screen_code.append("")
        self.screen_code.extend(choice_screen_code)
        return

    def generate_save_load_screen(self, component : FguiComponent):
        print(f"This is {component.name} screen.")
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()
        slot_list = None
        slot_list_index = -1
        default_slot_button = None
        save_slot_list_id = None
        if component.display_list.displayable_list == None:
            print(f"{component.name} contains no displayable.")
            return
        for i in range(len(component.display_list.displayable_list)):
            displayable = component.display_list.displayable_list[i]
            # 搜索名为 save_slot_list 的列表组件
            if displayable.name == 'save_slot_list' and isinstance(displayable, FguiList):
                slot_list = displayable
                slot_list_index = i
                # 确认默认引用组件类型。
                default_slot_button = self.fgui_assets.get_component_by_id(slot_list.default_item_id)
                break
        if not slot_list:
            print(f"{component.name} contains no slot list.")
            return
        # 检查slot_list默认引用组件类型是否为button
        if not isinstance(default_slot_button, FguiButton):
            print(f"{component.name} slot list item is not Button.")
            return
        
        comment_screen_name = "存档" if component.name == "save" else "读档"
        self.screen_definition_head.append(f"# {comment_screen_name} 界面")
        self.screen_definition_head.append(f"screen {component.name}():")

        # 菜单标签
        self.screen_definition_head.append(f"{self.indent_str}tag menu")
        # save_slot_list 之前的组件
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=0, list_end_index=slot_list_index))

        # save_slot_list的处理
        slot_list_code = []

        list_length = len(slot_list.item_list)

        screen_params = self.generate_list_screen_params(slot_list)
        if not screen_params:
            print("Failed to generate slot list screen.")
            return
        # 引用列表组件的screen。
        component_name = component.name
        slot_list_code.append(f"{self.indent_str}use {component_name}_{slot_list.name}({screen_params}):")
        # 添加元素
        self.indent_level_up()
        for i in range(list_length):
            # 值根据列表长度添加对应数量的默认元素，即存档按钮
            parameter_str = self.generate_button_callable_parameter(f"FileTime({i+1}, format=_(\"{{#file_time}}%Y-%m-%d %H:%M\"), empty=_(''))", f"FileAction({i+1})", f"FileScreenshot({i+1})")
            slot_list_code.append(f"{self.indent_str}use {default_slot_button.name}({parameter_str})")
        self.indent_level_down()
        self.screen_ui_code.extend(slot_list_code)

        # save_slot_list 之后的组件
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=slot_list_index+1))
        self.screen_ui_code.append("")

        self.screen_code.extend(self.screen_definition_head)
        self.screen_code.extend(self.screen_ui_code)
        return

    def generate_list_screen_params(self, fgui_list : FguiList) -> str:
        """
        生成列表组件screen，并返回引用该screen的参数字符串。
        """
        if not isinstance(fgui_list, FguiList):
            print("It is not a list displayable.")
            return ''
        component_name = self.current_component_name

        list_result = self.generate_list_screen(fgui_list, component_name)
        if not list_result:
            print(f"Failed to generate {component_name}_{fgui_list.name} list screen.")
            return ''

        list_length = fgui_list.get_item_list_length()
        default_item = self.fgui_assets.get_component_by_id(fgui_list.default_item_id)
        default_item_type = None
        default_item_name = None
        default_item_size = (0, 0)
        if default_item:
            default_item_name = default_item.name
            default_item_type = default_item.extention
            default_item_size = default_item.size
        else:
            default_item_name = self.fgui_assets.get_componentname_by_id(fgui_list.default_item_id)
            if default_item_name:
                default_item_type = 'image'
                default_item_size = self.fgui_assets.get_image_size_by_id(fgui_list.default_item_id)
            else:
                print("Ref com not found.")
                return ''
        

        overflow = None
        layout = fgui_list.layout
        row_num = 1
        column_num = 1
        transpose = False
        xspacing = 0
        yspacing = 0
        margin = (0, 0, 0, 0)
        xysize = (0, 0)
        pos = (0, 0)

        # 根据列表布局计算行数与列数。
        # layout-列表布局：(column)默认-单列竖排，row-单行横排，flow_hz-横向流动，flow_vt-纵向流动、pagination-分页
        # lineItemCount：列表布局为横向流动或分页时，表示列数。列表布局为竖向流动时，表示行数。其他布局中，该参数无效果。
        # lineItemCount2：列表布局为分页时，表示行数。其他布局中，该参数无效果。
        if fgui_list.layout == "column":
            column_num = 1
            row_num = list_length
        elif fgui_list.layout == "row":
            row_num = 1
            column_num = list_length
        elif fgui_list.layout == 'flow_hz':
            # column_num可能为0，需要根据列表尺寸与元素尺寸计算实际的列数。
            if fgui_list.line_item_count == 0:
                column_num = math.floor(fgui_list.size[0] / (default_item_size[0] + fgui_list.col_gap) + 1)
            else:
                column_num = fgui_list.line_item_count
            row_num = math.ceil(list_length / column_num)
        elif fgui_list.layout == 'flow_vt':
            # row_num可能为0，需要根据列表尺寸与元素尺寸计算实际的行数。
            if fgui_list.line_item_count == 0:
                row_num = math.floor(fgui_list.size[1] / (default_item_size[1] + fgui_list.line_gap) + 1)
            else:
                row_num = fgui_list.line_item_count
            column_num = math.ceil(list_length / row_num)
        else:
            row_num = fgui_list.line_item_count
            column_num = fgui_list.line_item_count2 + 1

        xspacing = fgui_list.col_gap
        yspacing = fgui_list.line_gap
        transpose = (fgui_list.layout == 'flow_vt')
        xysize = fgui_list.size
        pos = fgui_list.xypos
        margin = fgui_list.margin
        screen_params = f"overflow='{overflow}', layout='{layout}', row_num={row_num}, column_num={column_num}, transpose={transpose}, xspacing={xspacing}, yspacing={yspacing}, xysize={xysize}, pos={pos}, margin={margin}"

        return screen_params

    def get_scrollbar_style(self, scrollbar_res : tuple[str, str]) -> tuple[str, str]:
        """
        根据滚动条配置，返回两个滚动条组件的样式。
        """
        if not scrollbar_res:
            return (None, None)
        vertical_scrollbar_component = self.fgui_assets.get_component_by_id(scrollbar_res[0]) if scrollbar_res[0] else None
        horizontal_scrollbar_component = self.fgui_assets.get_component_by_id(scrollbar_res[1]) if scrollbar_res[1] else None

        return (vertical_scrollbar_component, horizontal_scrollbar_component)

    def get_side_parts_and_scrollbars(self, scrollbar_res : tuple[str, str]) -> tuple[str, FguiComponent, FguiComponent]:
        """
        根据滚动条配置，返回可视组件side的属性和两个滚动条组件。
        若没有滚动条，可视组件side的属性 'c'。
        若滚动条为水平方向，可视组件side的属性 'c,b'。
        若滚动条为垂直方向，可视组件side的属性 'c,r'。
        若两者皆有，可视组件side的属性 'c,b,r'。
        """
        if not scrollbar_res:
            return (None, None, None)
        vertical_scrollbar_component = None
        horizontal_scrollbar_component = None
        if scrollbar_res[0]:
            vertical_scrollbar_component = self.fgui_assets.get_component_by_id(scrollbar_res[0])
        if scrollbar_res[1]:
            horizontal_scrollbar_component = self.fgui_assets.get_component_by_id(scrollbar_res[1])
        side_parts = 'c'
        if vertical_scrollbar_component:
            side_parts += ' r'
        if horizontal_scrollbar_component:
            side_parts += ' b'
        return (side_parts, vertical_scrollbar_component, horizontal_scrollbar_component)


    def generate_history_screen(self, component :FguiComponent):
        print("This is history screen.")
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()
        history_item = None
        displayable_list_len = len(component.display_list.displayable_list)
        history_list = None
        history_list_index = -1

        if component.display_list.displayable_list == None:
            print(f"{component.name} contains no displayable.")
            return

        for i in range(displayable_list_len):
            displayable = component.display_list.displayable_list[i]
            # 搜索名为 history_list 的列表组件
            if displayable.name == 'history_list' and isinstance(displayable, FguiList):
                history_list = displayable
                history_list_index = i
                # 确认默认引用组件类型。
                history_item = self.fgui_assets.get_component_by_id(history_list.default_item_id)
                break
        if not history_list:
            print(f"{component.name} contains no history list.")
            return
        # 检查history_list默认引用组件类型是否为component
        if not isinstance(history_item, FguiComponent):
            print(f"{component.name} history list item is not Component.")
            return

        self.reset_indent_level()
        self.screen_definition_head.append("# 对话历史界面")
        self.screen_definition_head.append(f"screen {component.name}():")
        self.indent_level_up()
        self.screen_definition_head.append(f"{self.indent_str}tag menu")
        self.screen_definition_head.append(f"{self.indent_str}predict False")
        
        # history_list 之前的组件
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=0, list_end_index=history_list_index))

        # history_list的处理
        history_list_code = []
        screen_params = self.generate_list_screen_params(history_list)
        if not screen_params:
            print("Failed to generate history list screen.")
            return
        # 引用列表组件的screen。
        component_name = component.name
        history_list_code.append(f"{self.indent_str}use {component_name}_{history_list.name}({screen_params}):")
        # 添加元素
        self.indent_level_up()
        history_list_code.append(f"{self.indent_str}for h in _history_list:")
        self.indent_level_up()
        # item组件可能包含多个子组件，直接引用会出现grid overfull错误
        history_list_code.append(f"{self.indent_str}fixed:")
        self.indent_level_up()
        history_list_code.append(f"{self.indent_str}xysize {history_item.size}")
        history_list_code.append(f"{self.indent_str}use {history_item.name}(h.who, h.what)")
        self.indent_level_down(3)
        self.screen_ui_code.extend(history_list_code)

        # history_list 之后的组件
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=history_list_index+1))
        self.screen_ui_code.append("")
        self.reset_indent_level()

        self.screen_code.extend(self.screen_definition_head)
        self.screen_code.extend(self.screen_ui_code)
        return

    def generate_history_item(self, component : FguiComponent):
        print("This is history item.")
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()
        who_text = None
        what_text = None
        # namebox = None
        # textbox = None
        # namebox_pos = (0, 0)
        # textbox_pos = (0, 0)
        who_index = 0
        what_index = 0
        
        display_list_len = len(component.display_list.displayable_list)
        for i in range(display_list_len):
            displayable = component.display_list.displayable_list[i]
            # 生成发言角色名的文本样式
            if displayable.name == 'who' and isinstance(displayable, FguiText):
                self.generate_text_style(displayable, "history_who_text_style")
                who_text = displayable
                who_index = i
            # 生成发言内容的文本样式
            if displayable.name == 'what' and isinstance(displayable, FguiText):
                self.generate_text_style(displayable, "history_what_text_style")
                what_text = displayable
                what_index = i

        # 检查查找结果
        if who_text == None:
            print("Lack of who text component.")
            return
        if what_text == None:
            print("Lack of what text component.")
            return

        # who_text_str = f"{who_text.text}".replace("\n", "\\n").replace("\r", "\\n")
        # what_text_str = f"{what_text.text}".replace("\n", "\\n").replace("\r", "\\n")
        who_text_str = ''
        what_text_str = '无对话记录。'
        screen_params = f"who='{who_text_str}', what='{what_text_str}'"
        self.reset_indent_level()
        # say界面需要覆盖默认gui设置
        self.screen_definition_head.append("# history_item界面，用于显示一条对话记录。")
        self.screen_definition_head.append(f"screen {component.name}({screen_params}):")
        self.indent_level_up()

        # 不包含who和what的displayList部分按顺序放在前面
        index_min = min(what_index, who_index)
        index_max = max(what_index, who_index)
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=0, list_end_index=index_min))
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=index_min+1, list_end_index=index_max))
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=index_max+1))

        # who和what固定放在后面，显示在其他组件之上。
        self.screen_ui_code.append(f"{self.indent_str}text _(who) style 'history_who_text_style':")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}pos {who_text.xypos}")
        self.indent_level_down()
        self.screen_ui_code.append(f"{self.indent_str}text _(what) style 'history_what_text_style':")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}pos {what_text.xypos}")
        self.reset_indent_level()

        self.screen_ui_code.append("")
        self.screen_code.extend(self.screen_definition_head)
        self.screen_code.extend(self.screen_ui_code)

    def generate_gallery_screen(self, component : FguiComponent):
        print("This is gallery screen.")
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()
        self.gallery_screen_code.clear()

        if not self.gallery_template_dict['gallery']:
            print("Gallery template is empty.")
            return
        
        gallery_button_list = None
        gallery_button_list_item = None
        gallery_button_list_index = -1
        displayable_list_len = len(component.display_list.displayable_list)
        gallery_button_list_len = 1
        gallery_button_list_column =  1
        gallery_button_list_row = 1
        ui_helper_exists = False
        # 检查 gallery_data 是否存在gallery_image_list
        if 'gallery_image_list' in self.gallery_data:
            ui_helper_exists = True
        else:
            print(f"Gallery image list is not defined in {self.ui_helper_file_name}.")

        for i in range(displayable_list_len):
            displayable = component.display_list.displayable_list[i]
            # 搜索名为 gallery_button_list 的列表组件
            if displayable.name == 'gallery_button_list' and isinstance(displayable, FguiList):
                gallery_button_list = displayable
                # 确认默认引用组件类型。
                gallery_button_list_item = self.fgui_assets.get_component_by_id(gallery_button_list.default_item_id)
                gallery_button_list_index = i
                break
        if not gallery_button_list:
            print(f"{component.name} contains no gallery button list.")
            return
        # 检查gallery_button_list_item是否为按钮
        if not isinstance(gallery_button_list_item, FguiButton):
            print(f"{component.name} gallery button list item is not Button.")
            return

        self.reset_indent_level()
        self.screen_definition_head.append("# CG图鉴界面")
        self.screen_definition_head.append(f"screen {component.name}():")
        self.indent_level_up()
        self.screen_definition_head.append(f"{self.indent_str}tag menu")
        self.screen_definition_head.append(f"{self.indent_str}")

        # gallery_button_list 之前的组件
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=0, list_end_index=gallery_button_list_index))

        # 若ui_helper.rpy存在，修改 gallery_button_list 的长度。
        if ui_helper_exists:
            gallery_button_list_len = len(self.gallery_data['gallery_image_list'])
            gallery_button_list.set_item_list_length(gallery_button_list_len)
        # gallery_button_list 的处理
        gallery_button_list_code = []
        screen_params = self.generate_list_screen_params(gallery_button_list)
        if not screen_params:
            print("Failed to generate list screen.")
            return
        # 引用列表组件的screen。
        component_name = component.name
        gallery_button_list_code.append(f"{self.indent_str}use {component_name}_{gallery_button_list.name}({screen_params}):")
        self.indent_level_up()

        # 若ui_helper.rpy不存在，根据列表长度添加对应数量的默认按钮。
        if not ui_helper_exists:
            for i in range(len(gallery_button_list.item_list)):
                gallery_button_list_code.append(f"{self.indent_str}use {gallery_button_list_item.name}()")
        # 若ui_helper.rpy存在，则使用固定脚本定义的按钮。
        else:
            gallery_button_list_code.append(f"{self.indent_str}for i in range(gallery_button_num):")
            self.indent_level_up()
            gallery_button_list_code.append(f"{self.indent_str}python:")
            self.indent_level_up()
            gallery_button_list_code.append(f"{self.indent_str}gallery_image = gallery_image_list[i]")
            gallery_button_list_code.append(f"{self.indent_str}if isinstance(gallery_image, list):")            
            self.indent_level_up()
            gallery_button_list_code.append(f"{self.indent_str}gallery_image = gallery_image[0]")
            self.indent_level_down(2)
            # 暂时用按钮的第一个display作为locked状态的显示内容。
            locked_image = self.fgui_assets.get_componentname_by_id(gallery_button_list_item.display_list.displayable_list[0].src)
            gallery_button_list_code.append(f"{self.indent_str}add g.make_button(gallery_image, gallery_image, locked='{locked_image}') xysize {gallery_button_list_item.size}")
            self.indent_level_down()
        self.screen_ui_code.extend(gallery_button_list_code)

        self.indent_level_down()
        # gallery_button_list 之后的组件
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=gallery_button_list_index+1))
        self.screen_ui_code.append("")
        self.reset_indent_level()

        self.gallery_screen_code.extend(self.screen_definition_head)
        self.gallery_screen_code.extend(self.screen_ui_code)
        # 读取 templates/renpy_gallery_template.txt 模板内容，并替换 {gallery_screen_code} 为 self.gallery_screen_code
        gallery_template_content = self.get_template_content('renpy_gallery_template.txt')
        gallery_template_content = gallery_template_content.replace('{gallery_screen_code}', '\n'.join(self.gallery_screen_code))
        gallery_template_content = gallery_template_content.replace('{gallery_button_list_len}', str(gallery_button_list_len))
        gallery_template_content = gallery_template_content.replace('{gallery_button_list_column}', str(gallery_button_list_column))
        gallery_template_content = gallery_template_content.replace('{gallery_button_list_row}', str(gallery_button_list_row))
        self.gallery_screen_code = gallery_template_content.split('\n')


        # 将内容保存在 game/scripts/gallery_screen.rpy 文件中
        gallery_screen_file = os.path.join(self.game_dir, 'scripts', 'gallery_screen.rpy')
        self.save_code_to_file(gallery_screen_file, self.gallery_screen_code)
        print(f"Gallery screen code has been saved to {gallery_screen_file}.")
        return

    def generate_music_room_screen(self, component : FguiComponent):
        print("This is music room screen.")
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()
        self.music_room_screen_code.clear()

        musicroom_button_list = None
        musicroom_button_list_item = None
        musicroom_button_list_index = -1
        displayable_list_len = len(component.display_list.displayable_list)
        musicroom_button_list_len = 1
        musicroom_button_list_column =  1
        musicroom_button_list_row = 1
        ui_helper_exists = False
        # 检查 gallery_data 是否存在gallery_image_list
        if 'gallery_music_list' in self.gallery_data:
            ui_helper_exists = True
        else:
            print(f"Gallery music list is not defined in {self.ui_helper_file_name}.")

        for i in range(displayable_list_len):
            displayable = component.display_list.displayable_list[i]
            # 搜索名为 musicroom_button_list 的列表组件
            if displayable.name == 'musicroom_button_list' and isinstance(displayable, FguiList):
                musicroom_button_list = displayable
                # 确认默认引用组件类型。
                musicroom_button_list_item = self.fgui_assets.get_component_by_id(musicroom_button_list.default_item_id)
                musicroom_button_list_index = i
                break
        if not musicroom_button_list:
            print(f"{component.name} contains no musicroom button list.")
            return
        # 检查musicroom_button_list_item是否为按钮
        if not isinstance(musicroom_button_list_item, FguiButton):
            print(f"{component.name} musicroom button list item is not Button.")
            return

        self.reset_indent_level()
        self.screen_definition_head.append("# 音乐室界面")
        self.screen_definition_head.append(f"screen {component.name}():")
        self.indent_level_up()
        self.screen_definition_head.append(f"{self.indent_str}tag menu")
        self.screen_definition_head.append(f"{self.indent_str}")

        # musicroom_button_list 之前的组件
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=0, list_end_index=musicroom_button_list_index))

        # 若ui_helper.rpy存在，修改 musicroom_button_list 的长度。
        if ui_helper_exists:
            musicroom_button_list_len = len(self.gallery_data['gallery_music_list'])
            musicroom_button_list.set_item_list_length(musicroom_button_list_len)

        # musicroom_button_list 的处理
        musicroom_button_list_code = []
        screen_params = self.generate_list_screen_params(musicroom_button_list)
        if not screen_params:
            print("Failed to generate music room list screen.")
            return
        component_name = component.name
        musicroom_button_list_code.append(f"{self.indent_str}use {component_name}_{musicroom_button_list.name}({screen_params}):")
        self.indent_level_up()
        # 若ui_helper.rpy不存在，则根据列表长度添加对应数量的默认按钮
        if not ui_helper_exists:
            for i in range(musicroom_button_list.get_item_list_length()):
                musicroom_button_list_code.append(f"{self.indent_str}use {musicroom_button_list_item.name}()")
        # 若ui_helper.rpy存在，则使用固定脚本定义的按钮
        else:
            musicroom_button_list_code.append(f"{self.indent_str}for i in range(musicroom_button_num):")
            self.indent_level_up()
            musicroom_button_list_code.append(f"{self.indent_str}$ name, file = gallery_music_list[i]")
            musicroom_button_list_code.append(f"{self.indent_str}use {musicroom_button_list_item.name}(title=name, actions=SwitchMusicRoomPlay(file))")
            self.indent_level_down()
        self.screen_ui_code.extend(musicroom_button_list_code)
        self.indent_level_down()
        # musicroom_button_list 之后的组件
        self.screen_ui_code.extend(self.convert_component_display_list(component, list_begin_index=musicroom_button_list_index+1))
        self.screen_ui_code.append("")
        self.reset_indent_level()

        self.music_room_screen_code.extend(self.screen_definition_head)
        self.music_room_screen_code.extend(self.screen_ui_code)
        # 读取 templates/renpy_music_room_template.txt 模板内容，并替换 {music_room_screen_code} 为 self.music_room_screen_code
        music_room_template_content = self.get_template_content('renpy_music_room_template.txt')
        music_room_template_content = music_room_template_content.replace('{music_room_screen_code}', '\n'.join(self.music_room_screen_code))
        music_room_template_content = music_room_template_content.replace('{musicroom_button_list_len}', str(musicroom_button_list_len))
        music_room_template_content = music_room_template_content.replace('{musicroom_button_list_column}', str(musicroom_button_list_column))
        music_room_template_content = music_room_template_content.replace('{musicroom_button_list_row}', str(musicroom_button_list_row))
        self.music_room_screen_code = music_room_template_content.split('\n')

        # 将内容保存在 game/scripts/music_room_screen.rpy 文件中
        music_room_screen_file = os.path.join(self.game_dir, 'scripts', 'music_room_screen.rpy')
        self.save_code_to_file(music_room_screen_file, self.music_room_screen_code)
        print(f"Music room screen code has been saved to {music_room_screen_file}.")
        return


    def generate_say_screen(self, component : FguiComponent):
        print("This is say screen.")
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()
        who_text = None
        what_text = None
        namebox = None
        textbox = None
        namebox_image = 'Null()'
        textbox_image = 'Null()'
        namebox_pos = (0, 0)
        textbox_pos = (0, 0)

        for displayable in component.display_list.displayable_list:
            # 生成发言角色名的文本样式
            if displayable.name == 'who' and isinstance(displayable, FguiText):
                self.generate_text_style(displayable, "say_who_text_style")
                self.generate_text_style(displayable, "say_label")
                who_text = displayable
            # 生成发言内容的文本样式
            if displayable.name == 'what' and isinstance(displayable, FguiText):
                self.generate_text_style(displayable, "say_what_text_style")
                what_text = displayable
            # 角色名的背景
            if displayable.name == 'namebox' and isinstance(displayable, FguiImage):
                namebox = self.fgui_assets.get_component_by_id(displayable.src)
                namebox_pos = displayable.xypos
                namebox_image = f"'{self.get_image_name(displayable)}'"

            # 发言内容的背景
            if displayable.name == 'textbox' and isinstance(displayable, FguiImage):
                textbox = self.fgui_assets.get_component_by_id(displayable.src)
                textbox_pos = displayable.xypos
                textbox_image = f"'{self.get_image_name(displayable)}'"

        # 检查查找结果
        if who_text == None:
            print("Lack of who text component.")
            return
        if what_text == None:
            print("Lack of what text component.")
            return
        if namebox:
            print("Namebox background is Null.")
        if textbox:
            print("Textbox background is Null.")

        screen_params = 'who, what'
        self.reset_indent_level()
        # say界面需要覆盖默认gui设置
        self.screen_definition_head.append("# say界面")
        self.screen_definition_head.append("style say_label is say_who_text_style")
        self.screen_definition_head.append("style say_dialogue is say_what_text_style")
        self.screen_definition_head.append(f"screen {component.name}({screen_params}):")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}if who is not None:")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}add {namebox_image}:")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}pos {namebox_pos}")
        self.indent_level_down()
        self.screen_ui_code.append(f"{self.indent_str}text who id 'who' style 'say_who_text_style':")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}pos {who_text.xypos}")
        self.indent_level_down(2)
        self.screen_ui_code.append(f"{self.indent_str}add {textbox_image}:")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}pos {textbox_pos}")
        self.indent_level_down()
        self.screen_ui_code.append(f"{self.indent_str}text what id 'what' style 'say_what_text_style':")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}pos {what_text.xypos}")
        self.reset_indent_level()

        self.screen_ui_code.append("")
        self.screen_code.extend(self.screen_definition_head)
        self.screen_code.extend(self.screen_ui_code)
        return

    # 根据图片组件对象获取图片名
    def get_image_name(self, fgui_image):
        if not isinstance(fgui_image, FguiImage):
            print("It is not a Image object.")
            return None
        for image in self.fgui_assets.package_desc.image_list:
            if fgui_image.src == image.id:
                return image.name

    @staticmethod
    def generate_variable_definition_str(variable_name, current_value=None):
        return f"default {variable_name} = {current_value}"

    @staticmethod
    def generate_barvalue_definition_str(barvalue_name, min_value=0, max_value=100, current_value=0, scope='local'):
        barvalue_str = ''
        barvalue_scope_str = ''
        if scope in ('local', 'screen'):
            barvalue_scope_str = scope.capitalize()
        barvalue_str = f"{barvalue_scope_str}VariableValue('{barvalue_name}',min={min_value},max={max_value})"
        return barvalue_str

    @staticmethod
    def generate_button_parameter(button_title=None, original_actions_str=None, icon=None):
        parameter_str = ""
        title_str = "title=''"
        actions_str = "actions=NullAction()"
        icon_str = "icon=Null()"
        if button_title :
            title_str = f"title=\"{button_title}\"".replace("\n", "\\n").replace("\r", "\\n")
        if original_actions_str :
            actions_str = f"actions={original_actions_str}"
        if icon:
            icon_str = f"icon={icon}"

        parameter_str = f"{title_str}, {actions_str}, {icon_str}"
        return parameter_str

    @staticmethod
    def generate_button_callable_parameter(button_title=None, actions=None, icon=None):
        parameter_str = ""
        title_str = "title=''"
        actions_str = "actions=NullAction()"
        icon_str = "icon=Null()"
        if button_title :
            title_str = f"title={button_title}".replace("\n", "\\n").replace("\r", "\\n")
        if actions:
            actions_str = f"actions={actions}"
        if icon:
            icon_str = f"icon={icon}"

        parameter_str = f"{title_str}, {actions_str}, {icon_str}"
        return parameter_str

    def generate_text_style(self, fgui_text : FguiText, style_name : str):
        """
        生成文本样式，专用于按钮标题，因为按钮中通常只有一个文本组件。
        目标样例：

        style main_menu_button_text:
            align (0.5, 0.5)
            font "hyzjhj.ttf"
            color "#FEDAAA"
            size 32
            outlines [(absolute(1), "#C0C0C0", absolute(3), absolute(3)), (absolute(1), "#FAB5A4", absolute(0), absolute(0))]
            textalign 0.5
        """

        # self.style_code.clear()
        # FGUI与Ren'Py中的相同的文本对齐方式渲染效果略有不同，Ren'Py的效果更好。
        if not isinstance(fgui_text, FguiText):
            print("It is not a text displayable.")
            return
        # 样式具有固定一档的缩进
        style_indent = "    "
        self.style_code.append(f"# 文本{fgui_text.name}样式定义")
        # 定义样式
        self.style_code.append(f"style {style_name}:")
        self.style_code.append(f"{style_indent}anchor {fgui_text.pivot}")
        self.style_code.append(f"{style_indent}xysize {fgui_text.size}")
        # 字体可能为空，改为Ren'Py内置默认字体SourceHanSansLite
        text_font =  fgui_text.font if fgui_text.font else "SourceHanSansLite"
        # 此处的字体名缺少后缀，在Ren'Py中直接使用会报错。
        # 需将字体名添加到font_name_list中，并替换renpy_font_map_definition模板中对应内容。
        if not text_font in self.font_name_list:
            self.font_name_list.append(text_font)
        self.style_code.append(f"{style_indent}font '{text_font}'")
        self.style_code.append(f"{style_indent}size {fgui_text.font_size}")
        self.style_code.append(f"{style_indent}color '{fgui_text.text_color}'")
        # xalign, yalign = self.trans_text_align(fgui_text.align, fgui_text.v_align)
        # self.style_code.append(f"{style_indent}align ({xalign}, {yalign})")

        text_outline_string = self.generate_text_outline_string(fgui_text)
        self.style_code.append(f"{style_indent}outlines {text_outline_string}")


        #设置最小宽度才能使text_align生效
        self.style_code.append(f"{style_indent}min_width {fgui_text.size[0]}")
        xalign, yalign = self.trans_text_align(fgui_text.align, fgui_text.v_align)
        # 默认两侧居中对齐
        self.style_code.append(f"{style_indent}textalign {xalign}")
        # 粗体、斜体、下划线、删除线
        if fgui_text.bold:
            self.style_code.append(f"{style_indent}bold {fgui_text.bold}")
        if fgui_text.italic:
            self.style_code.append(f"{style_indent}italic {fgui_text.italic}")
        if fgui_text.underline:
            self.style_code.append(f"{style_indent}underline {fgui_text.underline}")
        if fgui_text.strike:
            self.style_code.append(f"{style_indent}strikethrough {fgui_text.strike}")
        self.style_code.append("")

    @staticmethod
    def get_child_type(displayable):
        if isinstance(displayable, FguiImage):
            return DisplayableChildType.IMAGE
        elif isinstance(displayable, FguiText):
            return DisplayableChildType.TEXT
        elif isinstance(displayable, FguiGraph):
            return DisplayableChildType.GRAPH
        elif isinstance(displayable, FguiComponent):
            return DisplayableChildType.COMPONENT
        else:
            return DisplayableChildType.OTHER

    def generate_button_children(self, fgui_button : FguiButton):
        """
        生成按钮各状态的子组件。
        """

        # 4种状态的子组件列表
        idle_child_list = []
        hover_child_list = []
        selected_child_list = []
        selected_hover_child_list = []
        # 非激活状体子组件列表
        insensitive_child_list = []
        # 始终显示的子组件列表
        always_show_child_list = []
        # 5种类型的子组件字典
        state_children_dict = {
            'idle': idle_child_list,
            'hover': hover_child_list,
            'selected': selected_child_list,
            'selected_hover': selected_hover_child_list,
            'insensitive': insensitive_child_list,
            'always_show': always_show_child_list
        }
        state_index_name_dict = {
            0: 'idle',
            1: 'hover',
            2: 'selected',
            3: 'selected_hover',
            4: 'insensitive',
            None: 'always_show'
        }
        # 默认按钮控制器为button，并且必定有4种状态，顺序分别为idle、hover、selected、selected_hover。
        # 检查按钮控制器名称
        if fgui_button.controller_list[0].name != 'button':
            print("按钮控制器名不是button。")
            return state_children_dict
        # 检查按钮控制器的状态列表
        state_list = fgui_button.controller_list[0].page_index_dict.keys()
        state_number = min(len(state_list), 5) #暂时不处理5种以上的控制器状态
        if state_number < 4:
            print("按钮控制器状态总数小于4。")
            return state_children_dict

        # 将displayable_list中的子组件按状态分别添加到对应列表中
        for displayable in fgui_button.display_list.displayable_list:
            displayable_id = ''
            if isinstance(displayable, FguiGraph):
                displayable_id = f"{fgui_button.name}_{displayable.id}"
            else:
                displayable_id = displayable.id
            if displayable.gear_display is None:
                state_children_dict['always_show'].append((displayable_id, FguiToRenpyConverter.get_child_type(displayable)))
                break
            for i in range(0, state_number):
                if displayable.gear_display and str(i) in displayable.gear_display.controller_index:
                    state_children_dict[state_index_name_dict[i]].append((displayable_id, FguiToRenpyConverter.get_child_type(displayable)))
                    continue
        # print(state_children_dict)

        return state_children_dict

    @staticmethod
    def is_bar_grip(component : FguiComponent) -> bool:
        """
        判断是否为滚动条的grip组件。
        """
        if not isinstance(component, FguiComponent):
            return False
        if component.name is None:
            return False
        if not isinstance(component.name, str):
            return False
        return component.name.endswith('_grip')

    def generate_button_screen(self, component : FguiComponent):

        """
        生成按钮组件screen。目标样例：

        screen main_menu_button(title='', actions=NullAction()):
            button:
                padding (0, 0, 0, 0)
                xysize (273, 61)
                style_prefix 'main_menu_button'
                background 'main_menu_button_bg'
                text title:
                    align (0.5, 0.5)
                action actions

        style main_menu_button_text:
            align (0.5, 0.5)
            font "hyzjhj.ttf"
            color "#FEDAAA"
            size 32
            outlines [(absolute(1), "#C0C0C0", absolute(3), absolute(3)), (absolute(1), "#FAB5A4", absolute(0), absolute(0))]
            textalign 0.5
        """

        # self.screen_code.clear()
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.has_dismiss = False
        self.dismiss_action_list.clear()

        # 4种状态的子组件列表
        idle_child_list = []
        hover_child_list = []
        selected_child_list = []
        selected_hover_child_list = []
        # 非激活状体子组件列表
        insensitive_child_list = []
        # 始终显示的子组件列表
        always_show_child_list = []
        # 5种类型的子组件字典
        state_children_dict = {
            'idle': idle_child_list,
            'selected': selected_child_list,
            'hover': hover_child_list,
            'selected_hover': selected_hover_child_list,
            'insensitive': insensitive_child_list,
            'always_show': always_show_child_list
        }

        state_index_name_dict = {
            0: 'idle',
            1: 'selected',
            2: 'hover',
            3: 'selected_hover',
            4: 'insensitive',
            None: 'always_show'
        }
        
        # 图片id与name映射关系
        image_id_name_mapping = {}

        if component.extention != 'Button':
            print("组件类型不是按钮")
            return

        # 默认按钮控制器为button，并且必定有4种状态，顺序分别为idle、hover、selected、selected_hover。
        # 可扩展为5种，第5种必需为insensitive，表示按钮不激活状态。
        if component.controller_list[0].name != 'button':
            print("按钮控制器名不是button。")
            return
        # 检查按钮控制器的状态列表
        state_list = component.controller_list[0].page_index_dict.keys()
        state_number = min(len(state_list), 5) #暂时不处理5种以上的控制器状态
        if state_number < 4:
            print("按钮控制器状态总数小于4。")
            return

        # 生成按钮组件screen
        self.screen_definition_head.append("# 按钮screen定义")
        self.screen_definition_head.append(f"# 从FairyGUI按钮组件{component.name}转换而来")

        id = component.id
        button_name = component.name
        xysize = component.size
        background = self.default_background

        default_title = ''
        title_displayable = None
        text_xalign, text_yalign = 0, 0
        title_pos = (0, 0)
        title_anchor = (0, 0)

        icon_pos = (0, 0)
        icon_size = (0, 0)
        icon_image = None

        for displayable in component.display_list.displayable_list:
            # 不带显示控制器表示始终显示
            if displayable.gear_display is None:
                # state_children_dict['always_show'].append((displayable, FguiToRenpyConverter.get_child_type(displayable)))
                # 加入到所有状态显示列表中
                if displayable.name != 'title':
                    for state_list in state_children_dict.values():
                        state_list.append((displayable, FguiToRenpyConverter.get_child_type(displayable)))
                else:
                    pass
            # 其他状态根据枚举值加入各列表
            else:
                for i in range(0, state_number):
                    if i in displayable.gear_display.controller_index:
                        state_children_dict[state_index_name_dict[i]].append((displayable, FguiToRenpyConverter.get_child_type(displayable)))
                        continue
            # 图片组件
            if isinstance(displayable, FguiImage):
                for image in self.fgui_assets.package_desc.image_list:
                    if displayable.src == image.id:
                        image_id_name_mapping[displayable.id] = image.name
                        break
            elif isinstance(displayable, FguiGraph):
                self.graph_definition_code.extend(self.generate_graph_definitions(displayable, button_name))
            # 文本组件。只处理名为title的文本组件。其他的文本待后续增加。
            # FGUI与Ren'Py中的相同的文本对齐方式渲染效果略有不同，Ren'Py的效果更好。
            elif isinstance(displayable, FguiText) and displayable.name == 'title':
                # 重置缩进级别
                self.reset_indent_level()
                default_title = displayable.text
                title_displayable = displayable
                text_xalign, text_yalign = self.trans_text_align(displayable.align, displayable.v_align)
                title_pos = displayable.xypos
                title_anchor = displayable.pivot
                # 定义样式
                self.generate_text_style(displayable, f"{button_name}_text")
            # icon组件仅作为一个可从按钮外部传入额外可视组件的入口。
            elif isinstance(displayable, FguiLoader) and displayable.name == 'icon':
                icon_pos = displayable.xypos
                icon_size = displayable.size
                icon_image = displayable.item_url
                pass

        # 根据state_children_dict生成各种对应状态的background
        is_bar_grip = self.is_bar_grip(component)
        # self.generate_image_object(f"{button_name}_idle_background", state_children_dict['idle'], button_name)
        self.generate_composite_image_object(f"{button_name}_idle_background", state_children_dict['idle'], button_name, xysize, is_frame=is_bar_grip)
        # selected_background
        # self.generate_image_object(f"{button_name}_selected_background", state_children_dict['selected'], button_name)
        self.generate_composite_image_object(f"{button_name}_selected_background", state_children_dict['selected'], button_name, xysize, is_frame=is_bar_grip)
        # hover_background
        # self.generate_image_object(f"{button_name}_hover_background", state_children_dict['hover'], button_name)
        self.generate_composite_image_object(f"{button_name}_hover_background", state_children_dict['hover'], button_name, xysize, is_frame=is_bar_grip)
        # selected_hover_background
        # self.generate_image_object(f"{button_name}_selected_hover_background", state_children_dict['selected_hover'], button_name)
        self.generate_composite_image_object(f"{button_name}_selected_hover_background", state_children_dict['selected_hover'], button_name, xysize, is_frame=is_bar_grip)
        # insensitive_background
        # self.generate_image_object(f"{button_name}_insensitive_background", state_children_dict['insensitive'], button_name)
        self.generate_composite_image_object(f"{button_name}_insensitive_background", state_children_dict['insensitive'], button_name, xysize, is_frame=is_bar_grip)


        # 重置缩进级别
        self.reset_indent_level()
        default_actions = component.custom_data if component.custom_data else 'NullAction()'
        param_str = self.generate_button_parameter(default_title, default_actions, icon_image)
        self.screen_definition_head.append(f"screen {button_name}({param_str}):")
        # self.screen_definition_head.append(f"screen {button_name}(title='{default_title}', actions={default_actions}, icon=Null()):")

        self.indent_level_up()
        # 如果按钮有按下效果，添加自定义组件
        if component.button_down_effect:
            self.screen_ui_code.append(f"{self.indent_str}button_container:")
            self.indent_level_up()
            self.screen_ui_code.append(f"{self.indent_str}pressed_{component.button_down_effect} {component.button_down_effect_value}")
        self.screen_ui_code.append(f"{self.indent_str}button:")
        self.indent_level_up()
        # 默认button样式的padding为(6,6,6,6)，可能导致部分子组件位置变化。
        self.screen_ui_code.append(f"{self.indent_str}padding (0, 0, 0, 0)")
        self.screen_ui_code.append(f"{self.indent_str}style_prefix '{button_name}'")
        self.screen_ui_code.append(f"{self.indent_str}xysize {xysize}")
        self.screen_ui_code.append(f"{self.indent_str}background '{button_name}_[prefix_]background'")
        # if state_children_dict['idle']:
        #     self.screen_ui_code.append(f"{self.indent_str}idle_background '{button_name}_idle_background'")
        # if state_children_dict['selected']:
        #     self.screen_ui_code.append(f"{self.indent_str}selected_background '{button_name}_selected_background'")
        # if state_children_dict['hover']:
        #     self.screen_ui_code.append(f"{self.indent_str}hover_background '{button_name}_hover_background'")
        # if state_children_dict['selected_hover']:
        #     self.screen_ui_code.append(f"{self.indent_str}selected_hover_background '{button_name}_selected_hover_background'")
        # if state_children_dict['insensitive']:
        #     self.screen_ui_code.append(f"{self.indent_str}insensitive_background '{button_name}_insensitive_background'")
        self.screen_ui_code.append(f"{self.indent_str}text title:")
        # Ren'Py中没有文本相对自身组件的垂直对齐方式，尝试用整个文本组件的对齐来凑合。
        self.indent_level_up()
        # self.screen_ui_code.append(f"{self.indent_str}align ({text_xalign},{text_yalign})")
        self.screen_ui_code.append(f"{self.indent_str}pos {title_pos}")
        self.screen_ui_code.append(f"{self.indent_str}anchor {title_anchor}")
        self.indent_level_down()
        self.screen_ui_code.append(f"{self.indent_str}action actions")
        # 在最上层加上icon
        self.screen_ui_code.append(f"{self.indent_str}add icon:")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}pos {icon_pos}")
        self.screen_ui_code.append(f"{self.indent_str}size {icon_size}")
        self.indent_level_down()
        # 一些按钮特性
        # focus_mask，对应FGUI中的点击“测试”。
        if component.hit_test:
            # 根据引用src查找image名
            image_name = self.fgui_assets.get_componentname_by_id(component.hit_test.src)
            self.screen_ui_code.append(f"{self.indent_str}focus_mask \'{image_name}\' pos {component.hit_test.pos}")

        self.screen_ui_code.append("")

        self.screen_code.extend(self.screen_definition_head)
        self.screen_code.extend(self.screen_ui_code)
        # self.renpy_code.extend(self.screen_code)

    def trans_text_align(self, text_horizontal_align="left", text_vertical_align="top"):
        return self.align_dict.get(text_horizontal_align, 0.5), self.align_dict.get(text_vertical_align, 0.5)

    def generate_composite_image_object(self, composite_name : str, displayable_list : list, component_name: str, size : tuple[int, int], is_frame : bool = False):
        """
        生成合成图片对象。
        """
        image_definitions = []
        image_definitions.append("# image对象定义")
        image_definitions.append("# 使用其他image对象的合成")
        indent_level = self.root_indent_level
        self.reset_indent_level()
        image_definitions.append(f"image {composite_name}:")
        self.indent_level_up()
        image_definitions.append(f"{self.indent_str}Composite({size},")
        self.indent_level_up()
        for displayable, displayalbe_type in displayable_list:
            image_definitions.append(f"{self.indent_str}{displayable.xypos},")
            if displayalbe_type == DisplayableChildType.IMAGE:
                name = self.fgui_assets.get_componentname_by_id(displayable.src)
                if is_frame:
                    image_definitions.append(f"{self.indent_str}Frame('{name}'),")
                else:
                    image_definitions.append(f"{self.indent_str}'{name}',")
            elif displayalbe_type == DisplayableChildType.GRAPH:
                image_definitions.append(f"{self.indent_str}'{component_name}_{displayable.id}',")
            elif displayalbe_type == DisplayableChildType.TEXT:
                text_displayable_string = self.generate_text_displayable_string(displayable)
                image_definitions.append(f"{self.indent_str}{text_displayable_string},")
            # 其他类型暂时用空对象占位
            else:
                image_definitions.append(f"{self.indent_str}Null()")

        image_definitions.append(")")
        image_definitions.append("")

        self.image_definition_code.extend(image_definitions)
        self.root_indent_level = indent_level

    def generate_image_object(self, image_name : str, displayable_list : list, component_name: str):
        """
        生成image对象，入参为一些子组件列表，自带transform。
        暂时不考虑允许列表中的子组件添加额外transform，只单纯堆叠。
        """
        if len(displayable_list) <= 0:
            return
        image_definitions = []
        image_definitions.append("# image对象定义")
        image_definitions.append("# 使用其他image对象的组合")
        indent_level = self.root_indent_level
        self.reset_indent_level()
        image_definitions.append(f"image {image_name}:")
        self.indent_level_up()
        for displayable, displayalbe_type in displayable_list:
            image_definitions.append(f"{self.indent_str}contains:")
            self.indent_level_up()
            if displayalbe_type == DisplayableChildType.IMAGE:
                name = self.fgui_assets.get_componentname_by_id(displayable.src)
                image_definitions.append(f"{self.indent_str}'{name}'")
            elif displayalbe_type == DisplayableChildType.GRAPH:
                image_definitions.append(f"{self.indent_str}'{component_name}_{displayable.id}'")
            elif displayalbe_type == DisplayableChildType.TEXT:
                # image_definitions.append(f"{self.indent_str}Text({displayable.text})")
                text_displayable_string = self.generate_text_displayable_string(displayable)
                image_definitions.append(f"{self.indent_str}{text_displayable_string}")
            # 其他类型暂时用空对象占位
            else:
                image_definitions.append(f"{self.indent_str}Null()")
            image_definitions.append(f"{self.indent_str}pos {displayable.xypos}")
            # TODO 其他transform property还待添加
            # 也可考虑检查displayList中的子组件，将非默认值值生成在一个额外的容器中，便于用循环生成脚本。
            self.indent_level_down()

        image_definitions.append("")

        self.image_definition_code.extend(image_definitions)
        self.root_indent_level = indent_level

    @staticmethod
    def generate_text_outline_string(fgui_text):
        outline_string = '[]'
        if not isinstance(fgui_text, FguiText):
            print("It is not a text Displayable.")
            return outline_string
        has_shadow = fgui_text.shadow_color
        has_outline = fgui_text.stroke_color
        if has_shadow:
            shadow_outline = f"(absolute(0), \"{fgui_text.shadow_color}\", absolute({fgui_text.shadow_offset[0]}), absolute({fgui_text.shadow_offset[1]}))"
        if has_outline:
            stroke_outline = f"(absolute({fgui_text.stroke_size}), \"{fgui_text.stroke_color}\", absolute(0), absolute(0))"
        if has_shadow and not has_outline:
            outline_string = f"[{shadow_outline}]"
        if not has_shadow and has_outline:
            outline_string = f"[{stroke_outline}]"
        # Ren'Py中的投影不包含其他描边。为保持与FGUI效果一直，需要添加一层，宽度与描边一致，颜色、偏移与投影一致。
        if has_shadow and has_outline:
            extra_shadow = f"(absolute({fgui_text.stroke_size}), \"{fgui_text.shadow_color}\", absolute({fgui_text.shadow_offset[0]}), absolute({fgui_text.shadow_offset[1]}))"
            outline_string = f"[{shadow_outline}, {extra_shadow}, {stroke_outline}]"
        return outline_string


    def generate_text_displayable_string(self, fgui_text):
        text_displayable_string = ''
        if not isinstance(fgui_text, FguiText):
            print("It is not a text displayable.")
            return text_displayable_string
        text_anchor_param = f"anchor={fgui_text.pivot}"
        text_transformanchor = f"transform_anchor=True"
        text_pos_param = f"pos={fgui_text.xypos}"
        text_size_param = f"xysize={fgui_text.size}"
        text_font =  fgui_text.font if fgui_text.font else "SourceHanSansLite"
        if not text_font in self.font_name_list:
            self.font_name_list.append(text_font)
        text_font_param = f"font='{text_font}'"
        text_font_size_param = f"size={fgui_text.font_size}"
        text_font_color_param = f"color='{fgui_text.text_color}'"
        text_min_width_param = f"min_width={fgui_text.size[0]}"
        xalign, yalign = self.trans_text_align(fgui_text.align, fgui_text.v_align)
        text_textalign_param = f"textalign={xalign}"
        text_bold_param = f"bold={fgui_text.bold}"
        text_italic_param = f"italic={fgui_text.italic}"
        text_underline_param = f"underline={fgui_text.underline}"
        text_strike_param = f"strike={fgui_text.strike}"

        text_outline_string = self.generate_text_outline_string(fgui_text)
        text_outlines_parame = 'outlines={text_outline_string}'

        text_displayable_string = f"Text(text='{fgui_text.text}',{text_anchor_param},{text_transformanchor},{text_pos_param},{text_size_param},{text_font_param},{text_font_size_param},{text_font_color_param},{text_min_width_param},{text_textalign_param},{text_bold_param},{text_italic_param},{text_underline_param},{text_strike_param},{text_outlines_parame})"
        return text_displayable_string

    def generate_image_displayable(self, fgui_image : FguiImage) -> list:
        """
        生成图片组件。
        前提为image对象的定义已经在generate_image_definitions中生成。
        """
        image_code = []
        if not isinstance(fgui_image, FguiImage):
            print("It is not a image displayable.")
            return image_code

        end_indent_level = 0

        # 根据显示控制器gearDisplay设置显示条件
        if fgui_image.gear_display:
            condition_str = f"showif {fgui_image.gear_display.controller_name} in {fgui_image.gear_display.controller_index}:"
            image_code.append(f"{self.indent_str}{condition_str}")
            self.indent_level_up()
            end_indent_level = 1

        for image in self.fgui_assets.package_desc.image_list:
            if fgui_image.src == image.id:
                image_name = image.name
                image_code.append(f"{self.indent_str}add '{image_name}':")
                self.indent_level_up()
                image_code.append(f"{self.indent_str}pos {fgui_image.xypos}")
                # 必须指定，旋转和缩放都需要使用。
                image_code.append(f"{self.indent_str}anchor {fgui_image.pivot}")
                # FairyGUI中锚点固定为(0,0)或与轴心一致，轴心可指定为任意值。
                # Ren'Py中旋转轴心固定为图片中心(0.5,0.5)或与锚点一致，锚点可指定为任意值。
                # 若要与FairyGUI资源保持一致，需设置offset。
                # size可能为None，需要获取
                if (not fgui_image.size) or (fgui_image.size == (0, 0)):
                    size = self.fgui_assets.get_image_size_by_id(fgui_image.src)
                else:
                    size = fgui_image.size
                if not fgui_image.pivot_is_anchor:
                    xoffset = int(fgui_image.pivot[0] * size[0])
                    yoffset = int(fgui_image.pivot[1] * size[1])
                    image_code.append(f"{self.indent_str}xoffset {xoffset}")
                    image_code.append(f"{self.indent_str}yoffset {yoffset}")
                else:
                    image_code.append(f"{self.indent_str}transform_anchor {fgui_image.pivot_is_anchor}")

                if fgui_image.rotation:
                    image_code.append(f"{self.indent_str}rotate {fgui_image.rotation}")
                if fgui_image.alpha != 1.0:
                    image_code.append(f"{self.indent_str}alpha {fgui_image.alpha}")
                if fgui_image.multiply_color != "#ffffff":
                    image_code.append(f"{self.indent_str}matrixcolor TintMatrix('{fgui_image.multiply_color}')")
                if fgui_image.scale != (1.0, 1.0):
                    image_code.append(f"{self.indent_str}xzoom {fgui_image.scale[0]} yzoom {fgui_image.scale[1]}")
                # 九宫格或平铺图片需要指定尺寸
                if image.scale:
                    image_code.append(f"{self.indent_str}xysize {size}")
                self.indent_level_down()
                break
        self.indent_level_down(end_indent_level)
        return image_code

    def generate_graph_displayable(self, fgui_graph : FguiGraph) -> list:
        """
        生成图形组件。用于screen中。
        图形组件有多种类别：
        None: 空白
        rect: 矩形(可带圆角)
        eclipse: 椭圆(包括圆形)
        regular_polygon: 正多边形
        polygon: 多边形
        """
        graph_code = []

        if not isinstance(fgui_graph, FguiGraph):
            print("It is not a graph displayable.")
            return graph_code
        component_name = self.current_component_name

        self.graph_definition_code.extend(self.generate_graph_definitions(fgui_graph, component_name))
        graph_code.append(f"{self.indent_str}add '{component_name}_{fgui_graph.id}'")

        return graph_code

    def generate_text_displayable(self, fgui_text):
        """
        生成文本组件。非按钮的组件可能存在多个不同文本，不单独生成样式。
        """
        text_code = []

        # FGUI与Ren'Py中的相同的文本对齐方式渲染效果略有不同，Ren'Py的效果更好。
        if not isinstance(fgui_text, FguiText):
            print("It is not a text displayable.")
            return text_code


        end_indent_level = 1

        # 根据显示控制器gearDisplay设置显示条件
        if fgui_text.gear_display:
            condition_str = f"showif {fgui_text.gear_display.controller_name} in {fgui_text.gear_display.controller_index}:"
            text_code.append(f"{self.indent_str}{condition_str}")
            self.indent_level_up()
            end_indent_level = 2

        # 直接定义text组件。
        # 处理换行符
        text_str = fgui_text.text.replace("\n", "\\n").replace("\r", "\\n")
        # 需要根据is_input区分文本组件与输入框
        if fgui_text.is_input:
            # Ren'Py中的直接使用input组件无法在多个输入框的情况下切换焦点，也无法点击空白区域让所有输入框失去焦点。
            # 需要使用button作为父组件，与InputValue关联。整个界面添加一个dismiss，空白区域点击事件让输入框失去焦点。
            # pass
            # 添加InputValue变量。
            self.screen_variable_code.append(f"{self.indent_str}default {fgui_text.name} = '{fgui_text.text}'")
            self.screen_variable_code.append(f"{self.indent_str}default {fgui_text.name}_input_value = ScreenVariableInputValue('{fgui_text.name}', default=False)")
            if self.screen_has_dismiss == False:
                self.screen_has_dismiss = True
                # 若prompt不为空，需要在screen中添加一个输入检测函数
                if fgui_text.prompt:
                    self.screen_function_code.append("    python:\n        def check_input_length(input_value_object):\n            str_length = len(input_value_object.get_text())\n            current, editable = renpy.get_editable_input_value()\n            return (not editable or current!=input_value_object) and str_length == 0\n")
            self.dismiss_action_list.append(f"{fgui_text.name}_input_value.Disable()")
            # 用按钮装载input
            text_code.append(f"{self.indent_str}button:")
            self.indent_level_up()
            text_code.append(f"{self.indent_str}action {fgui_text.name}_input_value.Enable()")
            self.indent_level_down()
        # message 表示可能需要接收Ren'Py的提示语
        elif fgui_text.name == 'message':
            text_code.append(f"{self.indent_str}text message:")
            print("Detected a 'message' text displayable. Please ensure it was used in confirm screen.")
        else:
            text_code.append(f"{self.indent_str}text '{text_str}':")
        self.indent_level_up()
        text_code.append(f"{self.indent_str}xysize {fgui_text.size}")
        text_code.append(f"{self.indent_str}pos {fgui_text.xypos}")
        text_code.append(f"{self.indent_str}at transform:")
        self.indent_level_up()
        text_code.append(f"{self.indent_str}anchor {fgui_text.pivot}")
        if not fgui_text.pivot_is_anchor:
            size = fgui_text.size
            xoffset = int(fgui_text.pivot[0] * size[0])
            yoffset = int(fgui_text.pivot[1] * size[1])
            text_code.append(f"{self.indent_str}xoffset {xoffset}")
            text_code.append(f"{self.indent_str}yoffset {yoffset}")
        text_code.append(f"{self.indent_str}transform_anchor True")
        if fgui_text.rotation:
            text_code.append(f"{self.indent_str}rotate {fgui_text.rotation}")
        if fgui_text.alpha != 1.0:
            text_code.append(f"{self.indent_str}alpha {fgui_text.alpha}")
        if fgui_text.scale != (1.0, 1.0):
            text_code.append(f"{self.indent_str}xzoom {fgui_text.scale[0]} yzoom {fgui_text.scale[1]}")
        self.indent_level_down()

        # input组件额外内容
        if fgui_text.is_input:
            # 若有prompt，添加一个带显示条件的text。
            if fgui_text.prompt:
                prompt_str = fgui_text.prompt.replace("\n", "\\n").replace("\r", "\\n")
                text_code.append(f"{self.indent_str}showif check_input_length({fgui_text.name}_input_value):")
                self.indent_level_up()
                text_code.append(f"{self.indent_str}text '{prompt_str}':")
                self.indent_level_up()
                # 暂时使用与input相同样式
                text_font =  fgui_text.font if fgui_text.font else "SourceHanSansLite"
                if not text_font in self.font_name_list:
                    self.font_name_list.append(text_font)
                text_code.append(f"{self.indent_str}font '{text_font}'")
                text_code.append(f"{self.indent_str}size {fgui_text.font_size}")
                text_code.append(f"{self.indent_str}color '{fgui_text.text_color}'")
                text_outline_string = self.generate_text_outline_string(fgui_text)
                text_code.append(f"{self.indent_str}outlines {text_outline_string}")

                if fgui_text.letter_spacing:
                    text_code.append(f"{self.indent_str}kerning {fgui_text.letter_spacing}")
                if fgui_text.leading:
                    text_code.append(f"{self.indent_str}line_leading {fgui_text.leading}")
                text_code.append(f"{self.indent_str}min_width {fgui_text.size[0]}")
                xalign, yalign = self.trans_text_align(fgui_text.align, fgui_text.v_align)
                text_code.append(f"{self.indent_str}textalign {xalign}")
                if fgui_text.bold:
                    text_code.append(f"{self.indent_str}bold {fgui_text.bold}")
                if fgui_text.italic:
                    text_code.append(f"{self.indent_str}italic {fgui_text.italic}")
                if fgui_text.underline:
                    text_code.append(f"{self.indent_str}underline {fgui_text.underline}")
                if fgui_text.strike:
                    text_code.append(f"{self.indent_str}strikethrough {fgui_text.strike}")
                self.indent_level_down(leveldown=2)


            text_code.append(f"{self.indent_str}input:")
            self.indent_level_up()
            text_code.append(f"{self.indent_str}value {fgui_text.name}_input_value")

        # 字体可能为空，改为Ren'Py内置默认字体SourceHanSansLite
        text_font =  fgui_text.font if fgui_text.font else "SourceHanSansLite"
        # 此处的字体名缺少后缀，在Ren'Py中直接使用会报错。
        # 需将字体名添加到font_name_list中，并替换renpy_font_map_definition模板中对应内容。
        if not text_font in self.font_name_list:
            self.font_name_list.append(text_font)
        text_code.append(f"{self.indent_str}font '{text_font}'")
        text_code.append(f"{self.indent_str}size {fgui_text.font_size}")
        text_code.append(f"{self.indent_str}color '{fgui_text.text_color}'")

        text_outline_string = self.generate_text_outline_string(fgui_text)
        text_code.append(f"{self.indent_str}outlines {text_outline_string}")

        # 字间距与行距
        if fgui_text.letter_spacing:
            text_code.append(f"{self.indent_str}kerning {fgui_text.letter_spacing}")
        if fgui_text.leading:
            text_code.append(f"{self.indent_str}line_leading {fgui_text.leading}")

        #设置最小宽度才能使text_align生效
        text_code.append(f"{self.indent_str}min_width {fgui_text.size[0]}")
        # Ren'Py中只有文本宽度小于组件宽度的水平方向对齐设置
        xalign, yalign = self.trans_text_align(fgui_text.align, fgui_text.v_align)
        text_code.append(f"{self.indent_str}textalign {xalign}")
        # 不自动换行
        text_code.append(f"{self.indent_str}layout 'nobreak'")
            

        # 粗体、斜体、下划线、删除线
        if fgui_text.bold:
            text_code.append(f"{self.indent_str}bold {fgui_text.bold}")
        if fgui_text.italic:
            text_code.append(f"{self.indent_str}italic {fgui_text.italic}")
        if fgui_text.underline:
            text_code.append(f"{self.indent_str}underline {fgui_text.underline}")
        if fgui_text.strike:
            text_code.append(f"{self.indent_str}strikethrough {fgui_text.strike}")
        # 输入框特有properties
        if fgui_text.is_input:
            text_code.append(f"{self.indent_str}pixel_width {fgui_text.size[0]}")
            if not fgui_text.single_line:
                text_code.append(f"{self.indent_str}multiline True")
            if fgui_text.max_length:
                text_code.append(f"{self.indent_str}length {fgui_text.max_length}")
            if fgui_text.is_password:
                text_code.append(f"{self.indent_str}mask '*'")
            # FGUI的输入限制使用正则表达式。在Ren'Py中使用字符串。此处仅为占位，无效果。
            text_code.append(f"{self.indent_str}allow {{}}")
            text_code.append(f"{self.indent_str}exclude {{}}")
        if fgui_text.is_input:
            self.indent_level_down()

        self.indent_level_down(end_indent_level)
        return text_code

    def generate_list_displayable(self, fgui_list : FguiList) -> list[str]:
        """
        生成列表。
        """
        list_code = []
        if not isinstance(fgui_list, FguiList):
            print("It is not a list displayable.")
            return list_code
        component_name = self.current_component_name

        # 默认引用组件可能是图片或其他组件，后续处理方式不同。
        default_item = self.fgui_assets.get_component_by_id(fgui_list.default_item_id)
        default_item_type = None
        default_item_name = None
        # 若为组件
        if default_item:
            default_item_name = default_item.name
            default_item_type = default_item.extention
        # 若非组件
        else:
            default_item_name = self.fgui_assets.get_componentname_by_id(fgui_list.default_item_id)
            if default_item_name:
                default_item_type = 'image'
            else:
                print("Ref com not found.")
                return list_code

        list_length = fgui_list.get_item_list_length()

        # 生成列表组件的screen。
        list_result = self.generate_list_screen(fgui_list, component_name)
        if not list_result:
            print(f"Failed to generate {component_name}_{fgui_list.name} list screen.")
            return list_code
        
        # 计算screen入参。
        overflow = None
        layout = 'row'
        row_num = 1
        column_num = 1
        transpose = False
        xspacing = 0
        yspacing = 0
        margin = (0, 0, 0, 0)
        xysize = (0, 0)
        pos = (0, 0)

        # 根据列表布局计算行数与列数。
        # layout-列表布局：(column)默认-单列竖排，row-单行横排，flow_hz-横向流动，flow_vt-纵向流动、pagination-分页
        # lineItemCount：列表布局为横向流动或分页时，表示列数。列表布局为竖向流动时，表示行数。其他布局中，该参数无效果。
        # lineItemCount2：列表布局为分页时，表示行数。其他布局中，该参数无效果。
        if fgui_list.layout == "column":
            column_num = 1
            row_num = list_length
        elif fgui_list.layout == "row":
            row_num = 1
            column_num = list_length
        elif fgui_list.layout == 'flow_hz':
            column_num = fgui_list.line_item_count
            row_num = math.ceil(list_length / column_num)
        elif fgui_list.layout == 'flow_vt':
            row_num = fgui_list.line_item_count
            column_num = math.ceil(list_length / row_num)
        else:
            row_num = fgui_list.line_item_count
            column_num = fgui_list.line_item_count2

        xspacing = fgui_list.col_gap
        yspacing = fgui_list.line_gap
        transpose = (fgui_list.layout == 'flow_vt')
        xysize = fgui_list.size
        pos = fgui_list.xypos
        margin = fgui_list.margin
        screen_params = f"overflow='{overflow}', layout='{layout}', row_num={row_num}, column_num={column_num}, transpose={transpose}, xspacing={xspacing}, yspacing={yspacing}, xysize={xysize}, pos={pos}, margin={margin}"
        # 引用列表组件的screen。
        list_code.append(f"{self.indent_str}use {component_name}_{fgui_list.name}({screen_params}):")
        # 添加元素
        self.indent_level_up()
        for item in fgui_list.item_list:
            # 非默认元素
            if item.item_url:
                # TODO 非默认元素待处理
                pass
            # 默认元素
            else:
                if default_item_type == "image":
                    list_code.append(f"{self.indent_str}add '{default_item_name}'")
                elif default_item_type == "Button":
                    parameter_str = self.generate_button_parameter(item.item_title)
                    list_code.append(f"{self.indent_str}use {default_item_name}({parameter_str})")
                else:
                    # 非按钮组件可能包含多个子组件，直接引用会出现vpgrid overfull错误
                    list_code.append(f"{self.indent_str}fixed:")
                    self.indent_level_up()
                    list_code.append(f"{self.indent_str}xysize {default_item.size}")
                    list_code.append(f"{self.indent_str}use {default_item_name}()")
                    self.indent_level_down()

        return list_code

    def generate_list_screen(self, fgui_list : FguiList, component_name : str) -> bool:
        """
        生成列表组件的screen。于其他screen中使用use语句引用。
        """
        if not isinstance(fgui_list, FguiList):
            print("It is not a list displayable.")
            return False

        # 根据模板内容替换部分字符串
        list_screen_template_content = self.list_screen_template
        list_screen_template_content = list_screen_template_content.replace('{component_name}', f"{component_name}")
        list_screen_template_content = list_screen_template_content.replace('{list_name}', f"{fgui_list.name}")
        list_screen_template_content = list_screen_template_content.replace('{list_screen_name}', f"{component_name}_{fgui_list.name}")
        vertical_scrollbar_component, horizontal_scrollbar_component = self.get_scrollbar_style(fgui_list.scrollbar_res)
        vscrollbar_style = vertical_scrollbar_component.name if vertical_scrollbar_component else self.default_scrollbar_style
        hscrollbar_style = horizontal_scrollbar_component.name if horizontal_scrollbar_component else self.default_scrollbar_style
        list_screen_template_content = list_screen_template_content.replace('{vscrollbar_style}', f"'{vscrollbar_style}'")
        list_screen_template_content = list_screen_template_content.replace('{hscrollbar_style}', f"'{hscrollbar_style}'")

        self.screen_code.append(list_screen_template_content)

        return True

    def generate_renpy_code(self):
        """生成完整的Ren'Py代码"""


        # 读取01_ui_helper.rpy文件
        self.gallery_data = self.get_gallery_data_from_ui_helper(os.path.join(self.game_dir, self.ui_helper_file_name))
        # print(f"gallery_data: {self.gallery_data}")
        self.renpy_code = []

        # 添加文件头注释
        self.renpy_code.append("# -*- coding: utf-8 -*-")
        self.renpy_code.append("#")
        self.renpy_code.append("# 从FairyGUI项目转换的Ren'Py界面代码")
        self.renpy_code.append(f"# 资源包名: {self.fgui_assets.fgui_project_name}")
        self.renpy_code.append("#")
        self.renpy_code.append("")

        # 生成图像定义
        self.generate_image_definitions()

        for component in self.fgui_assets.fgui_component_set:
            if component.extention == 'Button':
                self.generate_button_screen(component)
            elif component.extention == 'ScrollBar':
                self.generate_scroll_bar_style(component)
            elif component.extention == 'Label':
                pass
            elif component.extention == 'Slider':
                self.generate_slider_style(component)
            elif component.extention == 'ComboBox':
                pass
            elif component.extention == 'ProgressBar':
                pass
            else:
                self.generate_screen(component)
        
        self.renpy_code.extend(self.game_global_variables_code)
        self.renpy_code.extend(self.image_definition_code)
        self.renpy_code.extend(self.graph_definition_code)
        self.renpy_code.extend(self.style_code)
        self.renpy_code.extend(self.screen_code)

    def save_to_file(self, filename):
        """
        保存Ren'Py代码
        """
        with open(filename, 'w', encoding='utf-8') as f:
            for line in self.renpy_code:
                f.write(line + '\n')

        print(f"Ren'Py代码已保存到: {filename}")

    def save_code_to_file(self, filename : str, code : list[str]) -> None:
        """
        保存Ren'Py代码
        """
        with open(filename, 'w', encoding='utf-8') as f:
            for line in code:
                f.write(line + '\n')

        print(f"Ren'Py代码已保存到: {filename}")

    def from_templates_to_renpy(self, filename):
        """
        读取模板替换字符串并保存至Ren'Py目录
        """
        # 字体字典
        with open(os.path.join(self.renpy_template_dir, self.font_map_template), 'r', encoding='utf-8') as file:
            content = file.read()
        font_name_list_str = ','.join(f'"{i}"' for i in self.font_name_list)
        content = content.replace("{font_name_list}", font_name_list_str)

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

    def get_template_content(self, filename : str, path : str = None) -> str:
        """
        获取模板内容
        """
        template_path = self.renpy_template_dir if path is None else path

        with open(os.path.join(template_path, filename), 'r', encoding='utf-8') as file:
            content = file.read()
        return content

    def get_gallery_data_from_ui_helper(self, file_path: str) -> dict:
        """
        从01_ui_helper.rpy文件中读取以"define"开头的列表
        """
        result = {}
        
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return result
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用正则表达式匹配 define 语句
            # 匹配格式: define variable_name = [...]
            # 需要处理多行列表，通过匹配括号来找到完整的列表
            pattern = r'define\s+(\w+)\s*=\s*(\[)'
            
            matches = list(re.finditer(pattern, content))
            
            for match in matches:
                var_name = match.group(1)
                list_start_pos = match.end() - 1  # '[' 的位置
                
                # 从 '[' 开始，找到匹配的 ']'
                bracket_count = 0
                i = list_start_pos
                list_end_pos = -1
                
                while i < len(content):
                    if content[i] == '[':
                        bracket_count += 1
                    elif content[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            list_end_pos = i
                            break
                    i += 1
                
                if list_end_pos == -1:
                    print(f"无法找到 {var_name} 列表的结束位置")
                    continue
                
                # 提取列表字符串
                list_str = content[list_start_pos:list_end_pos + 1]
                
                try:
                    # 使用ast.literal_eval安全地解析列表
                    list_value = ast.literal_eval(list_str)
                    result[var_name] = list_value
                    print(f"成功读取 define {var_name}: {len(list_value)} 个元素")
                except (ValueError, SyntaxError) as e:
                    print(f"解析 {var_name} 时出错: {e}")
                    continue
                    
        except Exception as e:
            print(f"读取文件时出错: {e}")
        
        return result

    def cleanup(self):
        """
        清理转换器资源
        清理内存中的数据结构、模板缓存等资源
        """
        try:
            self.fgui_assets = None
            # 清理代码生成相关的列表
            self.renpy_code.clear()
            self.screen_code.clear()
            self.screen_definition_head.clear()
            self.screen_variable_code.clear()
            self.screen_function_code.clear()
            self.screen_ui_code.clear()
            self.style_code.clear()
            self.dismiss_action_list.clear()
            self.graph_definition_code.clear()
            self.image_definition_code.clear()
            self.game_global_variables_code.clear()
            
            # 重置缩进相关状态
            self.root_indent_level = 0
            self.indent_str = ''
            self.screen_has_dismiss = False
            
        except Exception as e:
            print(f"清理资源时出现错误: {e}")

    def __del__(self):
        self.cleanup()



    def copy_predefine_files(self, source_dir, target_dir):
        """
        复制预定义cdd和cds的文件
        """
        print(f"source_dir: {source_dir}")
        # 所有rpy文件
        all_files = os.listdir(source_dir)
        for file in all_files:
            if file.endswith('.rpy'):
                filename = os.path.basename(file)
                source_file_path = os.path.join(source_dir, filename)
                target_file_path = os.path.join(target_dir, filename)
                shutil.copy2(source_file_path,target_file_path)


    def copy_atlas_files(self, source_dir, target_dir):
        """复制图集文件到目标目录，并将@替换为_"""

        # 所有图集文件
        atlas_files = self.fgui_assets.fgui_atlas_dicts.values()

        # 复制文件并重命名
        for atlas_file in atlas_files:
            # 将@替换为_
            new_filename = atlas_file.replace('@', '_')
            source_path = os.path.join(source_dir, atlas_file)
            target_path = os.path.join(target_dir, new_filename)
            shutil.copy2(source_path, target_path)
            print(f"✓ 复制并重命名图集文件: {atlas_file} -> {new_filename}")

        return len(atlas_files)

def convert(argv):
    """
    主函数：解析FguiDemoPackage并转换为Ren'Py代码
    """
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='FairyGUI资源到Ren\'Py界面脚本的转换器',
                                   epilog='使用示例:\n'
                                          '  python Fgui2RenpyConverter.py -i "F:\\FguiDemoPackage" -o "F:\\RenpyProjects\\MyGame"\n'
                                          '  python Fgui2RenpyConverter.py --input "MyFGUIAssetPackage" --output "/path/renpy/project"',
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-i', '--input', type=str, 
                        help='输入FairyGUI资源文件所在目录名 (目录中需存在同名 .bytes 文件)')
    parser.add_argument('-o', '--output', type=str, 
                        help='输出Ren\'Py项目基目录路径 (即Ren\'Py项目根目录)')
    
    # 解析命令行参数
    args = parser.parse_args(argv[1:] if argv and len(argv) > 1 else [])
    
    # 检查必需的参数
    if not args.input:
        print("错误: 必须指定输入目录 (-i 或 --input)")
        parser.print_help()
        return
    
    if not args.output:
        print("错误: 必须指定输出目录 (-o 或 --output)")
        parser.print_help()
        return
    
    fgui_project_path = args.input
    if os.path.exists(fgui_project_path) and os.path.isdir(fgui_project_path):
        fgui_project_name = os.path.basename(fgui_project_path)
    else:
        print(f"错误: 目录 {fgui_project_path} 不存在或不是有效目录")
        return
    
    renpy_base_dir = args.output

    print("开始将FairyGUI资源文件转换为Ren'Py脚本...")
    print("=" * 50)

    try:

        # 检查文件是否存在
        package_file = f"{fgui_project_path}/{fgui_project_name}.bytes"
        sprite_file = f"{fgui_project_path}/{fgui_project_name}@sprites.bytes"

        if not os.path.exists(package_file):
            print(f"错误: 找不到文件 {package_file}")
            return

        if not os.path.exists(sprite_file):
            print(f"错误: 找不到文件 {sprite_file}")
            return

        # 创建Ren'Py游戏基础目录结构
        game_dir = os.path.join(renpy_base_dir, "game")
        images_dir = os.path.join(game_dir, "images")
        scripts_dir = os.path.join(game_dir, "scripts")

        # 创建目录
        os.makedirs(game_dir, exist_ok=True)
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(scripts_dir, exist_ok=True)
        print(f"创建目录结构: {renpy_base_dir}/")
        print(f"├── game/")
        print(f"└── game/images/")
        print(f"└── game/scripts/")

        # 创建FguiAssets对象
        print("\n正在解析FairyGUI资源...")
        fgui_assets = FguiAssets(fgui_project_path)
        print("FairyGUI资源解析完成")

        # 创建转换器
        print("正在创建转换器...")
        converter = FguiToRenpyConverter(fgui_assets)
        converter.game_dir = game_dir
        converter.scripts_dir = scripts_dir
        converter.images_dir = images_dir
        print("转换器创建完成")

        # 生成Ren'Py代码
        print("正在生成Ren'Py代码...")
        converter.generate_renpy_code()
        print("Ren'Py代码生成完成")

        # 保存.rpy文件到game目录
        global_variables_output_file = os.path.join(converter.scripts_dir, "preppipe_global_variables.rpy")
        image_definition_output_file = os.path.join(converter.scripts_dir, "preppipe_image_definition.rpy")
        style_output_file = os.path.join(converter.scripts_dir, "preppipe_styles.rpy")
        screen_output_file = os.path.join(converter.scripts_dir, "preppipe_screens.rpy")

        converter.save_code_to_file(global_variables_output_file, converter.game_global_variables_code)
        converter.image_definition_code.extend(converter.graph_definition_code)
        converter.save_code_to_file(image_definition_output_file, converter.image_definition_code)
        converter.save_code_to_file(style_output_file, converter.style_code)
        converter.save_code_to_file(screen_output_file, converter.screen_code)

        # 部分预定义模板文件修改参数并保存
        font_map_definition_file = os.path.join(converter.scripts_dir, "01_font_map.rpy")
        converter.from_templates_to_renpy(font_map_definition_file)

        # 复制预定义cdd和cds文件
        converter.copy_predefine_files(converter.renpy_template_dir, converter.scripts_dir)

        # 复制图集文件到images目录
        print("\n正在复制图集文件...")
        current_dir = os.getcwd()
        atlas_count = converter.copy_atlas_files(fgui_project_path, converter.images_dir)
        print(f"复制了 {atlas_count} 个图集文件")

        # 一些清理
        fgui_assets.clear()
        converter.cleanup()

    except Exception as e:
        print(f"❌ 转换过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    convert(sys.argv)