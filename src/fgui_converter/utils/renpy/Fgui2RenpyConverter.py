#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import argparse

import shutil

# 添加当前目录到Python路径，以便导入FguiAssetsParseLib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fgui_converter.FguiAssetsParseLib import *

class FguiToRenpyConverter:
    """
    FairyGUI到Ren'Py转换器
    将FairyGUI资源转换为Ren'Py的screen语言
    """

    def __init__(self, fgui_assets):
        self.fgui_assets = fgui_assets
        self.renpy_code = []
        self.screen_code = []
        self.screen_definition_head = []
        self.screen_variable_code = []
        self.screen_function_code = []
        self.screen_ui_code = []
        self.style_code = []
        
        # dismiss用于取消一些组件的focus状态，例如input。
        self.screen_has_dismiss = False
        self.dismiss_action_list = []

        # 文本对齐的转义字典
        self.align_dict = {"left": 0.0, "center": 0.5, "right": 1.0, "top": 0.0, "middle": 0.5, "bottom": 1.0}

        # 字体名称列表。SourceHanSansLite为Ren'Py默认字体。
        self.font_name_list = ["SourceHanSansLite"]

        # 4个空格作为缩进基本单位
        self.indent_unit = '    '
        # 组件缩进级别
        self.root_indent_level = 0
        # 缩进字符串
        self.indent_str = ''

        # 默认背景色，在某些未指定image的情况下用作填充。
        self.default_background = '#fff'

        # 部分模板与预设目录
        # self.renpy_template_dir = 'renpy_templates'
        self.renpy_template_dir = os.environ.get('RENPY_TEMPLATES_DIR', 
                             os.path.join(os.path.dirname(os.path.abspath(__file__)), "renpy_templates"))
        self.font_map_template = 'renpy_font_map_definition.txt'
        self.graph_template_dict = {}
        self.graph_template_dict['rectangle'] = self.get_graph_template('renpy_rectangle_template.txt')
        self.graph_template_dict['ellipse'] = self.get_graph_template('renpy_ellipse_template.txt')

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
        self.renpy_code.extend(image_definitions)

    def generate_screen(self, component):
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
        self.screen_code.clear()
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.screen_has_dismiss = False
        self.dismiss_action_list.clear()

        self.screen_definition_head.append("# 组件Screen")
        self.screen_definition_head.append(f"# 从FairyGUI组件{component.name}转换而来")

        id = component.id
        screen_name = component.name

        self.reset_indent_level()
        self.screen_definition_head.append(f"screen {screen_name}():")
        self.indent_level_up()
        for displayable in component.display_list.displayable_list:
            # 图片组件
            if isinstance(displayable, FguiImage):
                self.screen_ui_code.extend(self.generate_image_displayable(displayable))
            # 图形组件
            elif isinstance(displayable, FguiGraph):
                self.screen_ui_code.extend(self.generate_graph_displayable(displayable))
            # 文本组件
            elif isinstance(displayable, FguiText):
                self.screen_ui_code.extend(self.generate_text_displayable(displayable))
            # 列表
            elif isinstance(displayable, FguiList):
                self.screen_ui_code.extend(self.generate_list_displayable(displayable))
            # 装载器
            elif isinstance(displayable, FguiLoader):
                pass
            # 其他组件
            else:
                # 根据引用源id查找组件
                ref_com = self.fgui_assets.get_component_by_id(displayable.src)
                # 按钮。可设置标题，并根据自定义数据字段设置action。
                if ref_com.extention == "Button" and ref_com.name != None:
                    self.screen_ui_code.append(f"{self.indent_str}fixed:")
                    self.indent_level_up()
                    self.screen_ui_code.append(f"{self.indent_str}pos {displayable.xypos}")
                    parameter_str = self.generate_button_parameter(displayable.button_property.title, displayable.custom_data)
                    self.screen_ui_code.append(f"{self.indent_str}use {ref_com.name}({parameter_str}) id \"{displayable.id}\"")
                    self.indent_level_down()

        self.screen_code.extend(self.screen_definition_head)
        self.screen_code.extend(self.screen_variable_code)
        self.screen_code.append("")
        self.screen_code.extend(self.screen_function_code)
        self.screen_code.append("")
        # 添加只有1个生效的dismiss
        if self.screen_has_dismiss:
            self.screen_ui_code.append(f"{self.indent_str}dismiss:")
            self.indent_level_up()
            self.screen_ui_code.append(f"{self.indent_str}modal False")
            dismiss_action_list = ', '.join(self.dismiss_action_list)
            self.screen_ui_code.append(f"{self.indent_str}action [{dismiss_action_list}]")
            
        self.screen_code.extend(self.screen_ui_code)

    def generate_button_parameter(self, button_title=None, original_actions_str=None):
        parameter_str = ""
        title_str = ""
        actions_str = ""
        if button_title :
            title_str = f"title=\'{button_title}\'".replace("\n", "\\n").replace("\r", "\\n")
        if original_actions_str :
            actions_str = f"actions={original_actions_str}"
        if button_title and original_actions_str:
            parameter_str = f"{title_str}, {actions_str}"
        else:
            parameter_str = title_str if title_str else actions_str

        return parameter_str

    def generate_text_style(self, fgui_text, style_name):
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

        self.style_code.clear()
        # FGUI与Ren'Py中的相同的文本对齐方式渲染效果略有不同，Ren'Py的效果更好。
        if not isinstance(fgui_text, FguiText):
            print("It is not a text displayable.")
            return
        # 样式具有固定一档的缩进
        style_indent = "    "
        default_title = fgui_text.text
        # 定义样式
        self.style_code.append(f"style {style_name}:")
        self.style_code.append(f"{style_indent}xysize {fgui_text.size}")
        # 字体可能为空，改为Ren'Py内置默认字体SourceHanSansLite
        text_font =  fgui_text.font if fgui_text.font else "SourceHanSansLite"
        # 此处的字体名缺少后缀，在Ren'Py中直接使用会报错。
        # 需将字体名添加到font_name_list中，并替换renpy_font_map_definition模板中对应内容。
        if not text_font in self.font_name_list:
            self.font_name_list.append(text_font)
        self.style_code.append(f"{style_indent}font \"{text_font}\"")
        self.style_code.append(f"{style_indent}size {fgui_text.font_size}")
        self.style_code.append(f"{style_indent}color \"{fgui_text.text_color}\"")
        xalign, yalign = self.trans_text_align(fgui_text.align, fgui_text.v_align)
        self.style_code.append(f"{style_indent}align ({xalign}, {yalign})")
        # Ren'Py中使用两层outlines分别实现投影和描边
        # FGUI中的投影包含描边，投影的size等于描边的size，默认值为0；Ren'Py中允许outlines为0，依然有效果
        # Ren'Py中的property outlines可以是列表，先投影后描边
        has_shadow = fgui_text.shadow_color
        shadow_width = fgui_text.stroke_size
        has_outline = fgui_text.stroke_color
        if has_shadow:
            shadow_outline = f"(absolute({shadow_width}), \"{fgui_text.shadow_color}\", absolute({fgui_text.shadow_offset[0]}), absolute({fgui_text.shadow_offset[1]}))"
        if has_outline:
            stroke_outline = f"(absolute({fgui_text.stroke_size}), \"{fgui_text.stroke_color}\", absolute(0), absolute(0))"
        if has_shadow and not has_outline:
            self.style_code.append(f"{style_indent}outlines [{shadow_outline}]")
        if not has_shadow and has_outline:
            self.style_code.append(f"{style_indent}outlines [{stroke_outline}]")
        if has_shadow and has_outline:
            self.style_code.append(f"{style_indent}outlines [{shadow_outline}, {stroke_outline}]")
        # 默认两侧居中对齐
        self.style_code.append(f"{style_indent}textalign 0.5")
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

    def generate_button_screen(self, component):

        """
        生成按钮组件screen。目标样例：

        screen main_menu_button(title='', actions=NullAction()):
            button:
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

        self.screen_code.clear()
        self.screen_definition_head.clear()
        self.screen_variable_code.clear()
        self.screen_function_code.clear()
        self.screen_ui_code.clear()
        self.has_dismiss = False
        self.dismiss_action_list.clear()
        self.style_code.clear()

        if component.extention != 'Button':
            print("组件类型不是按钮")
            return

        # 生成按钮组件screen
        self.screen_definition_head.append("# 按钮组件Screen")
        self.screen_definition_head.append(f"# 从FairyGUI按钮组件{component.name}转换而来")
        # screen_code.append("")

        id = component.id
        button_name = component.name
        xysize = component.size
        background = self.default_background
        default_title = ''
        for displayable in component.display_list.displayable_list:
            # 图片组件
            if isinstance(displayable, FguiImage):
                for image in self.fgui_assets.package_desc.image_list:
                    if displayable.src == image.id:
                        background = image.name
                        break
                    # TODO
                    # 处理不同图片分别用于idle、hover、selected_idle和selected_hover的情况
            # 文本组件
            # FGUI与Ren'Py中的相同的文本对齐方式渲染效果略有不同，Ren'Py的效果更好。
            # if isinstance(displayable, FguiText) and displayable.name == 'title':
            if isinstance(displayable, FguiText):
                # 重置缩进级别
                self.reset_indent_level()
                default_title = displayable.text
                # 定义样式
                self.generate_text_style(displayable, f"{button_name}_text")
                # self.screen_code.extend(self.style_code)

        # 重置缩进级别
        self.reset_indent_level()
        self.screen_definition_head.append(f"screen {button_name}(title='{default_title}', actions=NullAction()):")
        self.indent_level_up()
        # 如果按钮有按下效果，添加自定义组件
        if component.button_down_effect:
            self.screen_ui_code.append(f"{self.indent_str}button_container:")
            self.indent_level_up()
            self.screen_ui_code.append(f"{self.indent_str}pressed_{component.button_down_effect} {component.button_down_effect_value}")
        self.screen_ui_code.append(f"{self.indent_str}button:")
        self.indent_level_up()
        self.screen_ui_code.append(f"{self.indent_str}style_prefix '{button_name}'")
        self.screen_ui_code.append(f"{self.indent_str}xysize ({xysize})")
        self.screen_ui_code.append(f"{self.indent_str}background '{background}'")
        self.screen_ui_code.append(f"{self.indent_str}text title")
        self.screen_ui_code.append(f"{self.indent_str}action actions")
        # 一些按钮特性
        # focus_mask，对应FGUI中的点击“测试”。
        if component.hit_test:
            # 根据引用src查找image名
            image_name = self.fgui_assets.get_componentname_by_id(component.hit_test.src)
            self.screen_ui_code.append(f"{self.indent_str}focus_mask \'{image_name}\' pos {component.hit_test.pos}")

        self.screen_ui_code.append("")

        self.screen_code.extend(self.style_code)
        self.screen_code.extend(self.screen_definition_head)
        self.screen_code.extend(self.screen_ui_code)
        self.renpy_code.extend(self.screen_code)

    def trans_text_align(self, text_horizontal_align="left", text_vertical_align="top"):
        return self.align_dict.get(text_horizontal_align, 0.5), self.align_dict.get(text_vertical_align, 0.5)

    def generate_image_displayable(self, fgui_image):
        """
        生成图片组件。
        前提为image对象的定义已经在generate_image_definitions中生成。
        """
        image_code = []
        if not isinstance(fgui_image, FguiImage):
            print("It is not a image displayable.")
            return image_code

        for image in self.fgui_assets.package_desc.image_list:
            if fgui_image.src == image.id:
                image_name = image.name
                image_code.append(f"{self.indent_str}add \"{image_name}\":")
                self.indent_level_up()
                image_code.append(f"{self.indent_str}pos {fgui_image.xypos}")
                # 必须指定，旋转和缩放都需要使用。
                image_code.append(f"{self.indent_str}anchor {fgui_image.pivot}")
                # FairyGUI中锚点固定为(0,0)或与轴心一致，轴心可指定为任意值。
                # Ren'Py中旋转轴心固定为图片中心(0.5,0.5)或与锚点一致，锚点可指定为任意值。
                # 若要与FairyGUI资源保持一致，需设置offset。
                # size可能为None，需要获取
                if not fgui_image.size:
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
                if fgui_image.scale != (1.0, 1.0):
                    image_code.append(f"{self.indent_str}xzoom {fgui_image.scale[0]} yzoom {fgui_image.scale[1]}")
                # 九宫格或平铺图片需要指定尺寸
                if image.scale:
                    image_code.append(f"{self.indent_str}xysize {size}")
                self.indent_level_down()
                break
        return image_code

    def generate_graph_displayable(self, fgui_graph):
        """
        生成图形组件。图形组件有多种类别：
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

        # 空白直接使用Null。后续可能存在一些relation相关不匹配。
        if fgui_graph.type is None:
            graph_code.append(f"{self.indent_str}null width {fgui_graph.size[0]} height {fgui_graph.size[1]}")
        # 矩形(圆边矩形)。原生组件不支持圆边矩形，使用自定义shader实现。
        elif fgui_graph.type == "rect":
            # renpy_rectangle_template.txt模板已在转换器初始化读取。模板代码 self.self.graph_template_dict['rectangle'] 。
            graph_img_def = self.graph_template_dict['rectangle'].replace('{image_name}', fgui_graph.id)\
                                .replace('{rectangle_color}', str(rgba_normalize(fgui_graph.fill_color)))\
                                .replace('{stroke_color}', str(rgba_normalize(fgui_graph.stroke_color)))\
                                .replace('{image_size}', str(fgui_graph.size))\
                                .replace('{round_radius}', str(fgui_graph.corner_radius))\
                                .replace('{stroke_thickness}', str(fgui_graph.stroke_width))
            # 直接在整个脚本对象中添加graph定义。
            self.renpy_code.append(graph_img_def)
        # 椭圆(圆形)。Ren'Py尚不支持椭圆，使用自定义shader实现。
        elif fgui_graph.type == "eclipse":
            graph_img_def = self.graph_template_dict['ellipse'].replace('{image_name}', fgui_graph.id)\
                                .replace('{ellipse_color}', str(rgba_normalize(fgui_graph.fill_color)))\
                                .replace('{stroke_color}', str(rgba_normalize(fgui_graph.stroke_color)))\
                                .replace('{image_size}', str(fgui_graph.size))\
                                .replace('{stroke_thickness}', str(fgui_graph.stroke_width))
            # 直接在整个脚本对象中添加graph定义。
            self.renpy_code.append(graph_img_def)

        # 生成screen中的部分，带transform。
        graph_code.append(f"{self.indent_str}add \"{fgui_graph.id}\":")
        self.indent_level_up()
        graph_code.append(f"{self.indent_str}xysize {fgui_graph.size}")
        graph_code.append(f"{self.indent_str}pos {fgui_graph.xypos}")
        graph_code.append(f"{self.indent_str}at transform:")
        self.indent_level_up()
        graph_code.append(f"{self.indent_str}anchor {fgui_graph.pivot}")
        if not fgui_graph.pivot_is_anchor:
            size = fgui_graph.size
            xoffset = int(fgui_graph.pivot[0] * size[0])
            yoffset = int(fgui_graph.pivot[1] * size[1])
            graph_code.append(f"{self.indent_str}xoffset {xoffset}")
            graph_code.append(f"{self.indent_str}yoffset {yoffset}")
        graph_code.append(f"{self.indent_str}transform_anchor True")
        if fgui_graph.rotation:
            graph_code.append(f"{self.indent_str}rotate {fgui_graph.rotation}")
        if fgui_graph.alpha != 1.0:
            graph_code.append(f"{self.indent_str}alpha {fgui_graph.alpha}")
        if fgui_graph.scale != (1.0, 1.0):
            graph_code.append(f"{self.indent_str}xzoom {fgui_graph.scale[0]} yzoom {fgui_graph.scale[1]}")
        self.indent_level_down()

        self.indent_level_down()

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

        else:
            text_code.append(f"{self.indent_str}text \"{text_str}\":")
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
                text_code.append(f"{self.indent_str}text \"{prompt_str}\":")
                self.indent_level_up()
                # 暂时使用与input相同样式
                text_font =  fgui_text.font if fgui_text.font else "SourceHanSansLite"
                if not text_font in self.font_name_list:
                    self.font_name_list.append(text_font)
                text_code.append(f"{self.indent_str}font \"{text_font}\"")
                text_code.append(f"{self.indent_str}size {fgui_text.font_size}")
                text_code.append(f"{self.indent_str}color \"{fgui_text.text_color}\"")
                has_shadow = fgui_text.shadow_color
                shadow_width = fgui_text.stroke_size
                has_outline = fgui_text.stroke_color
                if has_shadow:
                    shadow_outline = f"(absolute({shadow_width}), \"{fgui_text.shadow_color}\", absolute({fgui_text.shadow_offset[0]}), absolute({fgui_text.shadow_offset[1]}))"
                if has_outline:
                    stroke_outline = f"(absolute({fgui_text.stroke_size}), \"{fgui_text.stroke_color}\", absolute(0), absolute(0))"
                if has_shadow and not has_outline:
                    text_code.append(f"{self.indent_str}outlines [{shadow_outline}]")
                if not has_shadow and has_outline:
                    text_code.append(f"{self.indent_str}outlines [{stroke_outline}]")
                if has_shadow and has_outline:
                    text_code.append(f"{self.indent_str}outlines [{shadow_outline}, {stroke_outline}]")
                if fgui_text.letter_spacing:
                    text_code.append(f"{self.indent_str}kerning {fgui_text.letter_spacing}")
                if fgui_text.leading:
                    text_code.append(f"{self.indent_str}line_leading {fgui_text.leading}")
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
        text_code.append(f"{self.indent_str}font \"{text_font}\"")
        text_code.append(f"{self.indent_str}size {fgui_text.font_size}")
        text_code.append(f"{self.indent_str}color \"{fgui_text.text_color}\"")
        # Ren'Py中使用两层outlines分别实现投影和描边
        # FGUI中的投影包含描边，投影的size等于描边的size，默认值为0；Ren'Py中允许outlines为0，依然有效果。
        # Ren'Py中的property outlines是列表，先投影后描边。
        has_shadow = fgui_text.shadow_color
        shadow_width = fgui_text.stroke_size
        has_outline = fgui_text.stroke_color
        if has_shadow:
            shadow_outline = f"(absolute({shadow_width}), \"{fgui_text.shadow_color}\", absolute({fgui_text.shadow_offset[0]}), absolute({fgui_text.shadow_offset[1]}))"
        if has_outline:
            stroke_outline = f"(absolute({fgui_text.stroke_size}), \"{fgui_text.stroke_color}\", absolute(0), absolute(0))"
        if has_shadow and not has_outline:
            text_code.append(f"{self.indent_str}outlines [{shadow_outline}]")
        if not has_shadow and has_outline:
            text_code.append(f"{self.indent_str}outlines [{stroke_outline}]")
        if has_shadow and has_outline:
            text_code.append(f"{self.indent_str}outlines [{shadow_outline}, {stroke_outline}]")
        # 字间距与行距
        if fgui_text.letter_spacing:
            text_code.append(f"{self.indent_str}kerning {fgui_text.letter_spacing}")
        if fgui_text.leading:
            text_code.append(f"{self.indent_str}line_leading {fgui_text.leading}")

        # Ren'Py中只有文本宽度小于组件宽度的水平方向对齐设置
        xalign, yalign = self.trans_text_align(fgui_text.align, fgui_text.v_align)
        text_code.append(f"{self.indent_str}textalign {xalign}")
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

        self.indent_level_down()
        return text_code

    def generate_list_displayable(self, fgui_list):
        """
        生成列表。
        """
        list_code = []
        if not isinstance(fgui_list, FguiList):
            print("It is not a list displayable.")
            return list_code

        # 默认引用组件可能是图片或其他组件，后续处理方式不同。
        default_item = self.fgui_assets.get_component_by_id(fgui_list.default_item_id)
        default_item_type = None
        default_item_name = None
        item_number = len(fgui_list.item_list)
        # 若为组件
        if default_item:
            default_item_name = self.fgui_assets.get_componentname_by_id(fgui_list.default_item_id)
            default_item_type = 'component'
        # 若为图片
        else:
            default_item_name = self.fgui_assets.get_componentname_by_id(fgui_list.default_item_id)
            if default_item_name:
                default_item_type = 'image'
            else:
                print("Ref com not found.")
                return list_code

        # 根据“溢出处理”是否可见区分处理。
        # 若“可见”，则使用hbox、vbox和grid。
        if fgui_list.overflow == "visible":
            # 单列竖排，使用vbox
            if fgui_list.layout == "column":
                list_code.append(f"{self.indent_str}vbox:")
            # 单行横排，使用hbox
            elif fgui_list.layout == "row":
                list_code.append(f"{self.indent_str}hbox:")
            # 其他，使用grid
            else:
                list_code.append(f"{self.indent_str}grid {fgui_list.line_item_count} {fgui_list.line_item_count2}:")

        else:
            list_code.append(f"{self.indent_str}vpgrid:")
            self.indent_level_up()

            # 若“隐藏”，使用不可滚动的vpgrid
            if fgui_list.overflow == "hidden":
                list_code.append(f"{self.indent_str}draggable False")
                # 单列竖排
                if fgui_list.layout == "column":
                    cols = 1
                    rows = item_number
                # 单行横排
                elif fgui_list.layout == "row":
                    cols = item_number
                    rows = 1
                # 其他
                else:
                    cols = fgui_list.line_item_count
                    rows = fgui_list.line_item_count2
                list_code.append(f"{self.indent_str}cols {cols}")
                list_code.append(f"{self.indent_str}rows {rows}")
            # 若“滚动”，使用可滚动的vpgrid。但RenPy无法限制某个轴能否滚动。
            elif fgui_list.overflow == "scroll":
                list_code.append(f"{self.indent_str}draggable True")
                # 垂直滚动
                if fgui_list.scroll == "vertical":
                    pass
                # 水平滚动
                elif fgui_list.scroll == "horizontal":
                    pass
                # 自由滚动
                elif fgui_list.scroll == "both":
                    pass
                # 单列竖排，使用vbox
                if fgui_list.layout == "column":
                    cols = 1
                    rows = item_number
                # 单行横排，使用hbox
                elif fgui_list.layout == "row":
                    cols = item_number
                    rows = 1
                # 其他，使用grid
                else:
                    cols = fgui_list.line_item_count
                    rows = fgui_list.line_item_count2
                list_code.append(f"{self.indent_str}cols {cols}")
                list_code.append(f"{self.indent_str}rows {rows}")
                if fgui_list.line_gap:
                    list_code.append(f"{self.indent_str}yspacing {fgui_list.line_gap}")
                if fgui_list.col_gap:
                    list_code.append(f"{self.indent_str}xspacing {fgui_list.col_gap}")
            self.indent_level_down()

        self.indent_level_up()
        list_code.append(f"{self.indent_str}pos {fgui_list.xypos}")
        list_code.append(f"{self.indent_str}xysize {fgui_list.size}")
        if fgui_list.margin:
            list_code.append(f"{self.indent_str}margin {fgui_list.margin}")
        # 添加元素
        for item in fgui_list.item_list:
            # 非默认元素
            if item.item_url:
                pass
            # 默认元素
            else:
                if default_item_type == "image":
                    list_code.append(f"{self.indent_str}add \'{default_item_name}\'")
                elif default_item_type == "component":
                    parameter_str = self.generate_button_parameter(item.item_title)
                    list_code.append(f"{self.indent_str}use {default_item_name}({parameter_str})")

        self.indent_level_down()
        return list_code

    def generate_renpy_code(self):
        """生成完整的Ren'Py代码"""
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
                pass
            elif component.extention == 'Label':
                pass
            elif component.extention == 'Slider':
                pass
            elif component.extention == 'ComboBox':
                pass
            elif component.extention == 'ProgressBar':
                pass
            else:
                self.generate_screen(component)
                self.renpy_code.extend(self.screen_code)

    def save_to_file(self, filename):
        """
        保存Ren'Py代码
        """
        with open(filename, 'w', encoding='utf-8') as f:
            for line in self.renpy_code:
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

    def get_graph_template(self, filename):
        """
        获取graph对应的image对象定义模板
        """
        with open(os.path.join(self.renpy_template_dir, filename), 'r', encoding='utf-8') as file:
            content = file.read()
        return content

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
        print("转换器创建完成")

        # 生成Ren'Py代码
        print("正在生成Ren'Py代码...")
        converter.generate_renpy_code()
        print("Ren'Py代码生成完成")

        # 保存.rpy文件到game目录
        output_file = os.path.join(scripts_dir, "fgui_to_renpy.rpy")
        converter.save_to_file(output_file)

        # 部分预定义模板文件修改参数并保存
        font_map_definition_file = os.path.join(scripts_dir, "font_map.rpy")
        converter.from_templates_to_renpy(font_map_definition_file)

        # 复制预定义cdd和cds文件
        converter.copy_predefine_files(converter.renpy_template_dir, scripts_dir)

        # 复制图集文件到images目录
        print("\n正在复制图集文件...")
        current_dir = os.getcwd()
        atlas_count = converter.copy_atlas_files(fgui_project_path, images_dir)
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