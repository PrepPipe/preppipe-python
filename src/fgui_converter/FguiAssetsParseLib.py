# -*- coding: utf-8 -*-

from re import M
import sys
import os
from lxml import etree

class FguiPackage():
    """
    FairyGUI资源包中的Package描述内容。
    包含component列表、image列表和atlas列表。
    """
    desc_id = ''
    name = ''
    component_list = []
    image_list = []
    atlas_list = []

    class brief_component:
        id = ''
        name = ''
        path = ''
        size = ()
        exported = True
        def __init__(self, id, name, path, size, exported=True):
            self.id = id
            self.name = name
            self.path = path
            size_list = size.split(",")
            self.size = (int(size_list[0]), int(size_list[1]))
            self.exported = exported

    class brief_image:
        id = ''
        name = ''
        path = ''
        size = ()
        scale = ''  # 九宫格：9grid；平铺：tile
        scale9grid = []
        exported = True
        def __init__(self, id, name, path, size, scale=None, scale9grid=[], exported=True):
            self.id = id
            self.name = name
            self.path = path
            size_list = size.split(",")
            self.size = (int(size_list[0]), int(size_list[1]))
            self.scale = scale
            if self.scale == '9grid':
                self.scale9grid = scale9grid.split(",")
            self.exported = exported

    class brief_atlas:
        id = ''
        size = ()
        file = ''
        def __init__(self, id, size, file):
            self.id = id
            size_list = size.split(",")
            self.size = (int(size_list[0]), int(size_list[1]))
            self.file = file

    def __init__(self, package_etree):
        self.package_etree = package_etree
        self.id = package_etree.get("id")
        self.name = package_etree.get("name")
        self.resource = package_etree[0]
        self.id_name_mapping = {}
        if (self.resource.tag != 'resources'):
            raise ValueError('packageDescription child is not resources.')
        for child in self.resource:
            # component类 id, name, path, size, exported=True
            if (child.tag == 'component'):
                self.component_list.append(self.brief_component(
                                                            child.get('id'),
                                                            child.get('name'),
                                                            child.get('path'),
                                                            child.get('size'),
                                                            exported=TransStrToBoolean(child.get('exported'))))
                self.id_name_mapping[child.get('id')] = child.get('name')
            # image类 name, path, size, scale=None, scale9grid=[], exported=True
            if (child.tag == 'image'):
                self.image_list.append(self.brief_image(
                                                    child.get('id'),
                                                    child.get('name'),
                                                    child.get('path'),
                                                    child.get('size'),
                                                    child.get('scale'),
                                                    child.get('scale9grid'),
                                                    exported=TransStrToBoolean(child.get('exported'))))
                self.id_name_mapping[child.get('id')] = child.get('name')
            # atlas类 id, size, file
            if (child.tag == 'atlas'):
                self.atlas_list.append(self.brief_atlas(
                                                child.get('id'),
                                                child.get('size'),
                                                child.get('file')))

    def clear(self):
        self.component_list.clear()
        self.image_list.clear()
        self.atlas_list.clear()
        self.id_name_mapping.clear()

def TransStrToBoolean(str):
    if (str == 'true' or str == 'True'):
        return True
    else:
        return False

class FguiSpriteInfo:
    """
    FairyGUI资源包中的Sprite描述内容。
    总计11个字段，包括image id、图集编号、在图集中的x坐标、在图集中的y坐标、image宽度、image高度、rotate、
    原图相对image的x偏移、原图相对image的y偏移、原图宽度、原图高度。
    """
    def __init__(self, image_id, atlas_index, x, y, width, height, rotate, offset_x, offset_y, source_width, source_height):
        self.image_id = image_id
        self.atlas_index = int(atlas_index)
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)
        self.rotate = int(rotate)
        self.offset_x = int(offset_x)
        self.offset_y = int(offset_y)
        self.source_width = int(source_width)
        self.source_height = int(source_height)

    def __repr__(self):
        return f"FguiSpriteInfo({self.image_id}, {self.atlas_index}, {self.x}, {self.y}, {self.width}, {self.height}, {self.rotate}, {self.offset_x}, {self.offset_y}, {self.source_width}, {self.source_height})"

# 解析纹理集描述文件。文件名通常为“项目名称@sprites.bytes”
def ParseFguiSpriteDescFile(sprite_desc_file):
    fgui_image_sets = []
    with open(sprite_desc_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 11:  # 确保每行有11个字段
                obj = FguiSpriteInfo(*parts)
                fgui_image_sets.append(obj)
    return fgui_image_sets

# 从xml字符串创建lxml的etree对象
def GetXmlTree(xml_str):
    root = etree.fromstring(xml_str.encode('utf-8'))
    return root

# 解析发布资源描述文件。文件名通常为“项目名称.bytes”
def ParseFguiPackageDescFile(file_name):
    #f = open("Package1.bytes", "r", encoding='utf-8')
    with open(file_name, "r", encoding='utf-8') as f:
        ori_str = f.read()
    xml_flag_str = '.xml'
    split_flag_str = '|'
    xml_length = 0
    cursor = 0
    index = 0
    xml_string = ''
    xml_name = ''
    object_dict = {}
    index = ori_str.find(xml_flag_str)

    while index != -1:
        xml_name = ori_str[cursor:index]
        cursor= index+len(xml_flag_str)
        index = ori_str.find(split_flag_str, cursor, -1)
        cursor = index + len(split_flag_str)
        index = ori_str.find(split_flag_str, cursor, -1)
        xml_length = int(ori_str[cursor:index])
        cursor = index + len(split_flag_str)
        index = cursor + xml_length
        xml_string = ori_str[cursor: index]
        object_dict[xml_name] = GetXmlTree(xml_string)
        cursor = index
        index = ori_str.find(xml_flag_str, cursor)

    return object_dict


class OriImage:
    """
    图像类。
    结合两个描述文件信息的原始image类。
    为后续生成目标引擎图像定义的基础数据结构。
    svg生成的图片可能会带有@2x、@3x等后缀，导致图片尺寸有异，此处暂时忽略。
    """
    def __init__(self, image_id, name, atlas_name, atlas_pos_x, atlas_pos_y, width, height):
        self.image_id = image_id
        self.name = name
        self.atlas_name = atlas_name
        self.atlas_pos_x = atlas_pos_x
        self.atlas_pos_y = atlas_pos_y
        self.width = width
        self.height = height

    def __repr__(self):
        return f"OriImage({self.image_id}, {self.name}, {self.atlas_name}, {self.atlas_pos_x}, {self.atlas_pos_y}, {self.width}, {self.height})"


def GetOriImage(image_id, package_desc, fgui_image_sets, fgui_atlas_dicts):
    image_set = None
    for item in fgui_image_sets:
        if (item.image_id == image_id):
            image_set = item
    atlas_name = fgui_atlas_dicts["atlas"+str(item.atlas_index)]
    for image in package_desc.image_list:
        if (image.id == image_id):
            name =image.name
    return OriImage(image_id, name, atlas_name, image_set.x, image_set.y, image_set.width, image_set.height)


class FguiController:
    """
     FairyGUI控制器类
     name：控制器名称，字符串，样例"button"
     page：索引、索引名，字符串，样例"0,up,1,down,2,over,3,selectedOver"
     selected：初始索引号，字符串 ，样例"0"
    """
    def __init__(self, name, page, selected):
        self.name = name
        self.page_index_dict = {}
        page_list = page.split(',')
        page_num = len(page_list)
        i = 0
        while i < page_num:
            self.page_index_dict[int(page_list[i])] = page_list[i+1]
            i += 2
        self.selected = int(selected) if selected else 0

    def __repr__(self):
        return f"FguiController({self.name}, {self.page_index_dict}, {self.selected})"

class FguiHitTest:
    """
    点击测试区域类。
    """
    def __init__(self, hit_test_str):
        self.src = None
        self.pos = (0, 0)
        if hit_test_str:
            src, xpos, ypos = hit_test_str.split(",")
            self.src = src
            self.pos = (int(xpos), int(ypos))

class FguiComponent:
    """
    FairyGUI组件对应的基类。
    id、name、path和size属性与package中brief_component的对应组件信息保持一致
    """

    def __init__(self, component_etree, id, name, package_desc_id=None):
        self.component_etree = component_etree
        self.id = id
        self.name = name
        self.package_desc_id = package_desc_id
        size = component_etree.get("size")
        self.size = tuple(map(int, size.split(","))) if size else (0,0)
        self.extention = component_etree.get("extention")
        self.mask = component_etree.get("mask")
        # 轴心。默认值为(0.0, 0.0)。
        pivot = component_etree.get("pivot", "0.0,0.0")
        self.pivot = tuple(map(float, pivot.split(",")))
        # 点击测试区域，包含3个字段，分别为引用源src和组件内相对坐标x、y。
        hit_test = component_etree.get("hitTest")
        self.hit_test = FguiHitTest(hit_test) if hit_test else None
        # 自定义数据。实际使用时，相同id的FguiDisplayable中的自定义数据优先。
        self.custom_data = component_etree.get("customData")

        # 控制器，一般不超过1个。
        self.controller_list = []
        # 显示内容列表，通常为image、text、graph。
        self.display_list = None
        # 一级子对象
        self.child_num = len(self.component_etree)

        for i in range(self.child_num):
            # 控制器
            if (self.component_etree[i].tag == "controller"):
                self.controller_list.append(FguiController(self.component_etree[i].get("name"), self.component_etree[i].get("pages"), self.component_etree[i].get("selected")))
            # 显示内容
            elif (self.component_etree[i].tag == "displayList"):
                self.display_list = FguiDisplayList(self.component_etree[i], self.package_desc_id)

    def __repr__(self):
        return f"FguiComponent({self.id}, {self.name}, {self.size}, {self.extention}, {self.mask})"

class FguiButton(FguiComponent):
    """
    FairyGUI中的按钮button。
    相比其他component，多一个Button标签
    """
    def __init__(self, component_etree, id, name, package_desc_id=None):
        super().__init__(component_etree, id, name, package_desc_id=None)
        button = component_etree.find("Button")
        self.button_mode = button.get("mode")
        self.button_down_effect = button.get("downEffect")
        self.button_down_effect_value = button.get("downEffectValue")

class FguiScrollBar(FguiComponent):
    """
    FairyGUI中的滚动条scrollbar。
    相比其他component，多一个ScrollBar标签，大部分情况为空。
    通常滚动条都会有以个对应的其他组件，为同名带后缀“_grip”的按钮。
    """
    def __init__(self, component_etree, id, name, package_desc_id=None):
        super().__init__(component_etree, id, name, package_desc_id=None)
        scrollbar = component_etree.find("ScrollBar")

class FguiLabel(FguiComponent):
    """
    FairyGUI中的标签lablel。
    目前与FguiComponent完全相同，甚至不具有单独的Label标签。
    """
    def __init__(self, component_etree, id, name, package_desc_id=None):
        super().__init__(component_etree, id, name, package_desc_id=None)


class FguiComboBox(FguiComponent):
    """
    FairyGUI中的下拉框。
    相比其他component，多一个ComboBox标签，属性dropdown对应点击后显示的选项列表。
    通常下拉框都会有两个对应的其他组件，分别为同名带后缀“_item”的按钮和同名带后缀“_popup”的组件
    """
    def __init__(self, component_etree, id, name, package_desc_id=None):
        super().__init__(component_etree, id, name, package_desc_id=None)
        combobox = component_etree.find("ComboBox")
        self.dropdown = combobox.get("dropdown")

class FguiProgressBar(FguiComponent):
    """
    FairyGUI中的进度条。
    相比其他component，多一个ProgressBar标签，大部分情况为空。
    """
    def __init__(self, component_etree, id, name, package_desc_id=None):
        super().__init__(component_etree, id, name, package_desc_id=None)
        self.progressbar = component_etree.find("ProgressBar")

class FguiSlider(FguiComponent):
    """
    FairyGUI中的滑动条。
    相比其他component，多一个Slider标签，大部分情况为空。
    滑动条会有一个相应的其他组件，同名带后缀“_grip”的按钮。
    """
    def __init__(self, component_etree, id, name, package_desc_id=None):
        super().__init__(component_etree, id, name, package_desc_id=None)
        self.slider = component_etree.find("Slider")
        self.title_type = self.slider.get("titleType")

class FguiWindow(FguiComponent):
    """
    FairyGUI中的可拖拽窗口。
    没有extention类型，也没有特殊标签，仅从扩展类型无法区分Label和Window。

    FairyGUI中的Window子组件有一些非硬性命名约定(约束)：
        1. 名称为frame的组件，作为Window的背景。该子组件通常扩展类型为“Label”。
        2. frame的组件内部，一个名称为closeButton的按钮将自动作为窗口的关闭按钮。
        3. frame的组件内部，一个名称为dragArea的图形(类型设置为空白)将自动作为窗口的检测拖动区域。
        4. frame的组件内部，一个名称为contentArea的图形(类型设置为空白)将作为窗口的主要内容区域。
    根据以上约定制作的Window，由各引擎内部的FairyGUI的相关包负责动态创建、渲染和事件响应。

    Ren'Py中没有FairyGUI的包体处理以上内容，且通常不需要动态创建组件。
    暂定按默认Component处理。可拖拽功能再议。
    """
    def __init__(self, component_etree, id, name, package_desc_id=None):
        super().__init__(component_etree, id, name, package_desc_id=None)


class FguiDisplayList:
    """
    FairyGUI组件内部显示列表，xml中displayList标签内容。
    只要一个组件不为空组件，必定会有displayList。
    """
    def __init__(self, display_list_etree, package_desc_id=None):
        self.display_list_etree = display_list_etree
        self.package_desc_id = package_desc_id
        # print(f"package_desc_id: {package_desc_id}")
        self.displayable_list = []
        for displayable in self.display_list_etree:
            # print(displayable.tag)
            # 根据标签类型创建相应的FguiDisplayable对象
            if displayable.tag == "graph":
                self.displayable_list.append(FguiGraph(displayable))
            elif displayable.tag == "text":
                self.displayable_list.append(FguiText(displayable))
            elif displayable.tag == "image":
                self.displayable_list.append(FguiImage(displayable))
            elif displayable.tag == "list":
                self.displayable_list.append(FguiList(displayable, self.package_desc_id))
            elif displayable.tag == "loader":
                self.displayable_list.append(FguiLoader(displayable))
            else:
                # 对于未知类型，创建基础的FguiDisplayable对象
                self.displayable_list.append(FguiDisplayable(displayable))

def hex_aarrggbb_to_rgba(hex_color):
    """
    将一个8位的十六进制颜色字符串(AARRGGBB)或6位的十六进制颜色字符串(RRGGBB)转换为一个 RGBA 元组。
    """
    # 移除字符串头部的 '#'
    clean_hex = hex_color.lstrip('#').lower()
    hex_str_len = len(clean_hex)

    # 检查处理后的字符串长度是否为8或6
    if hex_str_len != 8 and hex_str_len != 6:
        raise ValueError("输入的十六进制字符串必须是8位(AARRGGBB)或6位(RRGGBB)")

    # 6位字符则加上alpha通道的默认值 ff
    if hex_str_len ==6:
        clean_hex = 'ff' + clean_hex

    # 按 AARRGGBB 的顺序提取，并从16进制转换为10进制整数
    try:
        a = int(clean_hex[0:2], 16)
        r = int(clean_hex[2:4], 16)
        g = int(clean_hex[4:6], 16)
        b = int(clean_hex[6:8], 16)
    except ValueError:
        raise ValueError("字符串包含无效的十六进制字符")

    return (r, g, b, a)

def rgba_normalize(rgba_tuple):
    r = float(rgba_tuple[0]/255)
    g = float(rgba_tuple[1]/255)
    b = float(rgba_tuple[2]/255)
    a = float(rgba_tuple[3]/255)
    return (r, g, b, a)

class ColorFilterData:
    """
    颜色滤镜数据，总共4项，分别为亮度、对比度、饱和度、色相。
    """
    def __init__(self, data_string):
        if not data_string:
            raise ValueError("Color Filter Data is Null.")
        self.brightness, self.contrast, self.saturation, self.hue = map(float, data_string.split(","))


class FguiDisplayable:
    """
    FairyGUI组件内显示对象。
    可能的类型包括：graph(图形)、image(图片)、text(文字)、component(组件)、list(列表)、loader(装载器)。
    基本属性：id、名称、引用源、位置、尺寸、缩放、倾斜、轴心、锚点、不透明度、旋转、是否可见、是否变灰、是否可触摸。

    此外，fgui中的“效果”与“其他”配置也放在属性中。

    支持多种子项。其中Button项仅限按钮作为子组件时才可能存在。
    relation(暂未处理)和FGUI自身gearBase的派生类。
    在一个FguiDisplayable对象中，以下各类gear均至多只存在一个。
    除了 *是否显示* 可以由至多两个控制器决定，其他属性均只能由单一控制器决定。
    gearBase的派生类如下：
    gearDisplay-根据控制器决定是否显示；
    gearDisplay2-协同另一个控制器决定是否显示；
    gearLook-根据控制器决定外观transform，包括alpha、rotation、grayed、touchable等；
    gearXY-根据控制器决定坐标；
    gearSize-根据控制器决定尺寸，包括size和scale；
    gearColor-根据控制器决定“图片-颜色”；
    gearText-根据控制器决定文本组件显示的文本内容；
    gearIcon-根据控制器决定装载器显示内容。
    """
    def __init__(self, display_item_tree, package_description_id=None):
        self.display_item_tree = display_item_tree
        # id
        self.id = self.display_item_tree.get("id")
        # 名称
        self.name = self.display_item_tree.get("name")
        # 引用源，通常是id。若为图片可在FguiAssets的package_desc.image_list中根据id查找图片名。若为组件可在FguiAssets的package_desc.component_list中根据id查找组件。
        self.src = self.display_item_tree.get("src")
        # 位置
        xy = self.display_item_tree.get("xy", "0,0")
        self.xypos = tuple(map(int, xy.split(",")))
        # 尺寸。若为None：image的size默认与image对象一致。
        size = self.display_item_tree.get("size")
        self.size = tuple(map(int, size.split(","))) if size else (0,0)
        # 保持比例。若为None，则将宽和高分别缩放到size。
        self.aspect = (self.display_item_tree.get("aspect") == "true")
        # 缩放。默认值为(1.0, 1.0)。
        scale = self.display_item_tree.get("scale", "1.0,1.0")
        self.scale = tuple(map(float, scale.split(",")))
        # 倾斜。默认值为(0, 0)。
        skew = self.display_item_tree.get("skew", "0,0")
        self.skew = tuple(map(int, skew.split(",")))
        # 轴心。默认值为(0.0, 0.0)。
        pivot = self.display_item_tree.get("pivot", "0.0,0.0")
        self.pivot = tuple(map(float, pivot.split(",")))
        # 是否将轴心作为锚点。否认为False。
        self.pivot_is_anchor = (self.display_item_tree.get("anchor") == "true")
        # 不透明度。默认为1.0。
        alpha = self.display_item_tree.get("alpha", "1.0")
        self.alpha = float(alpha)
        # 旋转。默认值为0。
        rotation = self.display_item_tree.get("rotation", "0")
        self.rotation = int(rotation)
        # 未明确为不可见则默认可见
        self.visible = not (self.display_item_tree.get("visible") == "false")
        # 未明确是否变灰则默认不变灰
        self.grayed = (self.display_item_tree.get("grayed") == "true")
        # 未明确是否可触摸则默认可以触摸
        self.touchable = not (self.display_item_tree.get("touchable") == "false")
        # 资源包描述id，部分组件需要
        self.package_description_id = package_description_id
        # BlendMode
        self.blend_mode = self.display_item_tree.get("blend", "normal")
        # 滤镜
        self.color_filter = self.display_item_tree.get("filter")
        # 滤镜颜色变换
        self.color_filter_values = ColorFilterData(self.display_item_tree.get("filterData", "1,1,1,1"))
        # Tooltips，一般指指针悬垂在组件上时显示的说明文本。
        self.tooltips = self.display_item_tree.get("tooltips")
        # 自定义数据
        self.custom_data = self.display_item_tree.get("customData")

        # Button，按钮专有属性
        self.button_property = None

        # Slider，滑动条专有属性
        self.slider_property = None

        # gear属性
        self.gear_display = None
        self.gear_display_2 = None
        self.gear_pos = None
        self.gear_look = None
        self.gear_size = None
        self.gear_color = None
        self.gear_text = None
        self.gear_icon = None

        # relation
        self.relations = None

        # 一级子对象
        self.child_num = len(self.display_item_tree)
        # 控制器gear子组件和relation关联项
        for i in range(self.child_num):
            if self.display_item_tree[i].tag == "gearDisplay" :
                self.gear_display = FguiGearDisplay(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "gearDisplay2" :
                self.gear_display_2 = FguiGearDisplay(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "gearXY" :
                self.gear_pos = FguiGearPos(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "gearSize" :
                self.gear_size = FguiGearSize(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "gearLook" :
                self.gear_look = FguiGearLook(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "gearColor" :
                self.gear_color = FguiGearColor(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "gearText" :
                self.gear_text = FguiGearText(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "gearIcon" :
                self.gear_icon = FguiGearIcon(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "Button" :
                self.button_property = FguiButtonProperty(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "relation" :
                self.relations = FguiRelation(self.display_item_tree[i])
            elif self.display_item_tree[i].tag == "Slider" :
                self.slider_property = FguiSliderProperty(self.display_item_tree[i])
            else:
                print(f"Tag not parse: {self.display_item_tree[i].tag}.")

    def __repr__(self):
        return f"FguiDisplayable({self.id}, {self.name}, {self.xypos}, {self.size}, \
{self.scale}, {self.skew}, {self.pivot}, {self.pivot_is_anchor}, {self.alpha}, \
{self.rotation}, {self.visible}, {self.grayed}, {self.touchable})"

class FguiComponentPropertyBase:
    """
    组件子属性信息基类
    """
    def __init__(self, component_property_tree):
        self.component_property_tree = component_property_tree
        self.property_name = self.component_property_tree.tag

class FguiButtonProperty(FguiComponentPropertyBase):
    """
    组件子属性中的Button信息。
    通常包括title和icon，分别表示标题(文本)和图标(装载器)
    """
    def __init__(self, component_property_tree):
        super().__init__(component_property_tree)
        if self.property_name != "Button" :
            raise ValueError("xml tag is not Button")
        self.title = self.component_property_tree.get("title")
        self.selected_title = self.component_property_tree.get("selectedTitle")
        self.icon = self.component_property_tree.get("icon")
        self.selected_icon = self.component_property_tree.get("selectedIcon")


class FguiGraph(FguiDisplayable):
    """
    FairyGUI中的图形。包括空白、矩形(圆边矩形)、圆形(椭圆)、多边形等。
    """
    def __init__(self, display_item_tree):
        if display_item_tree.tag != "graph" :
            raise ValueError("xml tag is not graph.")
        super().__init__(display_item_tree)
        # None: 空白  rect: 矩形(可带圆角) eclipse: 椭圆(包括圆形)  regular_polygon: 正多边形  polygon: 多边形
        self.type = self.display_item_tree.get("type", None)
        self.stroke_width = int(self.display_item_tree.get("lineSize", "1"))
        stroke_color= self.display_item_tree.get("lineColor", "#ff000000") # 描边默认为黑色
        self.stroke_color  = hex_aarrggbb_to_rgba(stroke_color)
        fill_color = self.display_item_tree.get("fillColor", "#ffffffff") # 描边默认为白色
        self.fill_color = hex_aarrggbb_to_rgba(fill_color)
        # 矩形可能存在圆角
        self.corner_radius = int(self.display_item_tree.get("corner", "0"))
        # 正多边形需要记录边数和顶点位置。
        # 顶点位置使用一个数组表示，数组长度等于顶点数(边数)。
        # 顶点只能存在于标准正多边形顶点到图形中心的连线上。
        # 每个数字表示对应顶点到图形中心的距离，最大值为1.0，最小值为0.0。
        if (self.type == "regular_polygon"):
            self.sides =  int(self.display_item_tree.get("sides", "3"))
            distances = self.display_item_tree.get("distances", "1.0,"*(self.sides-1)+"1.0")
            distances_list = distances.split(",")
            for i in range(len(distances_list)):
                if distances_list[i] == '':
                    distances_list[i] = "1.0"
        # 多边形只记录顶点坐标。
        # points为顺序连接的一组xy坐标，例如"5,4,12,-2,20.78191,5.746792,14,16,3,14"。
        # 虽然发布的资源xml中坐标是浮点，但FairyGUI编辑器却显示为整型。可考虑转换时也缩小精度为整型。
        if (self.type == "polygon"):
            point_list = self.display_item_tree.get("points", "0.0,0.0").split(",")
            iteration = iter(point_list)
            self.points = tuple((float(x), float(y)) for x, y in zip(iteration, iteration))

class FguiText(FguiDisplayable):
    """
    FairyGUI中的文本。
    """
    def __init__(self, display_item_tree):
        if display_item_tree.tag != "text" :
            raise ValueError("xml tag is not text.")
        super().__init__(display_item_tree)
        # FairyGUI编辑器未设置全局字体的情况下，默认渲染使用Arial，与Ren'Py默认字体SourceHanSansLite不同。
        # 此处的字体与FairyGUI编辑器中的字体属性不同，为字体名称。编辑器中的xml则记录引用项。
        # 另外，FairyGUI发布的资源文件中并不包含字体文件，需要手工放置到游戏引擎对应目录。
        self.text = self.display_item_tree.get("text", "")
        self.font = self.display_item_tree.get("font")
        self.font_size = int(self.display_item_tree.get("fontSize", 24) )
        self.text_color = self.display_item_tree.get("color", "#000000")
        self.align = self.display_item_tree.get("align", "left") # 共有left、center、right三种
        self.v_align = self.display_item_tree.get("vAlign", "top") # 共有top、middle、bottom三种
        self.ubb = (self.display_item_tree.get("ubb") == "true") # UBB语法暂不考虑
        self.auto_size = self.display_item_tree.get("autoSize")
        self.letter_spacing = self.display_item_tree.get("letterSpacing", 0) # 字间距
        self.leading = self.display_item_tree.get("leading", 3) # 行间距
        self.underline = (self.display_item_tree.get("underline") == "true")
        self.bold = (self.display_item_tree.get("bold") == "true")
        self.italic = (self.display_item_tree.get("italic") == "true")
        self.strike = (self.display_item_tree.get("strike") == "true")
        self.single_line = (self.display_item_tree.get("singleLine") == "true")
        self.stroke_color = self.display_item_tree.get("strokeColor")
        self.stroke_size = self.display_item_tree.get("strokeSize", 1)
        self.shadow_color = self.display_item_tree.get("shadowColor")
        shadow_offset = self.display_item_tree.get("shadowOffset")
        if shadow_offset:
            self.shadow_offset = tuple(map(int, shadow_offset.split(",")))
        else:
            self.shadow_offset = (0, 0)
        # 下面几项仅限输入框
        self.is_input = (self.display_item_tree.get("input") == "true")
        self.prompt = self.display_item_tree.get("prompt")
        self.max_length = int(self.display_item_tree.get("maxLength", 0))
        self.restrict = self.display_item_tree.get("restrict") #输入文本规则，正则表达式字符串
        self.is_password = (self.display_item_tree.get("password") == "true")
        


class FguiImage(FguiDisplayable):
    """
    FairyGUI中的图片。
    tag为image。
    属性如下：
    color-颜色：一个6位Hex字符串，表示显示时所有像素的RGA都要乘以该值
    flip-翻转类型："hz"-水平、"vt"-垂直、"both"-水平+垂直。
    fillMethod-填充方式："hz"-水平、"vt"-垂直、"radial90"-90度、"radial180"-180度、"radial360"-360度
    fillOrigin-填充原点：0(默认值)、1、2、3。该值根据不同的填充方式有不同的含义。
    fillAmount-填充比例：100(默认值)，一个介于0到100之间的整数。
    样例：
    <image id="n9_z1bv" name="n9" src="ndicp" xy="210,169" alpha="0.67" color="#000000" flip="both" fillMethod="hz" fillOrigin="1" fillAmount="55"/>
    """
    def __init__(self, display_item_tree):
        if display_item_tree.tag != "image" :
            raise ValueError("xml tag is not image.")
        super().__init__(display_item_tree)
        self.multiply_color = self.display_item_tree.get("color", "#ffffff")
        self.flip_type = self.display_item_tree.get("flip")
        self.fill_method = self.display_item_tree.get("fillMethod")
        self.fill_origin = self.display_item_tree.get("fillOrigin")
        self.fill_amount = self.display_item_tree.get("fillAmount")

class FguiListItem():
    """
    列表元素，仅会在list内部。
    tag为item。
    属性如下：
    url-引用资源url，格式为“ui://”+“packageDescription id” + “component id”。若为空表示使用列表默认元素。
    title：标题，通常用于按钮。
    icon：图标，通常用于按钮。
    name：名称，没用。
    样例：
    <item url="ui://jlqvyvtyspct6" title="开坑" icon="ui://jlqvyvty9m682" name="buttonname"/>
    """
    def __init__(self, list_item_tree, package_description_id=None):
        if list_item_tree.tag != "item":
            raise ValueError("xml tag is not item.")
        self.list_item_tree = list_item_tree
        self.package_description_id = package_description_id
        self.item_url = self.list_item_tree.get("url")
        self.item_title = self.list_item_tree.get("title")
        self.item_icon = self.list_item_tree.get("icon")
        self.item_name = self.list_item_tree.get("name")
    def __repr__(self):
        return f"FguiListItem({self.item_url}, {self.item_title}, {self.item_icon}, {self.item_name})"


class FguiList(FguiDisplayable):
    """
    FairyGUI中的列表。
    列表存在“树视图”，暂不考虑。
    列表的属性如下：
    layout-列表布局：(column)默认-单列竖排，row-单行横排，flow_hz-横向流动，flow_vt-纵向流动、pagination-分页
    overflow-溢出处理：(visible)默认-可见，hidden-隐藏，scroll-滚动
    scroll-滚动条方向：(vertical)默认-垂直滚动，horizontal-水平滚动，both-自由滚动(同时允许垂直滚动和水平滚动)
    scrollBar-显示滚动条：visible-可见，hidden-隐藏，auto-滚动时显示
    scrollBarFlags：一系列滚动条标识位，可能是一个12bit整数。从低位到高位分别为：
        0-bit：垂直滚动条显示在左边
        1-bit：滚动位置自动贴近元件
        2-bit：仅在内容溢出时才显示滚动条
        3-bit：页面模式
        4-bit 5-bit：触摸滚动效果，00默认、01启用、10关闭
        6-bit 7-bit：边缘回弹效果，00默认、01启用、10关闭
        8-bit：禁用惯性
        9-bit：禁用剪裁
        10-bit：浮动显示
        11-bit：禁用剪裁边缘
    当列表允许滚动时，有一大堆特性暂不处理，例如“边缘回弹”、指定滚动条组件、自动贴近元件等。
    margin：边缘留空，4个整数，分别对应上下左右。
    clipSoftness：边缘虚化，xy分辨对应水平与垂直方向的虚化程度。
    lineItemCount：列表布局为横向流动或分页时，表示列数。列表布局为竖向流动时，表示行数。其他布局中，该参数无效果。
    lineItemCount2：列表布局为分页时，表示行数。其他布局中，该参数无效果。
    lineGap：行距。
    colGap：列距。
    defaultItem：默认元素，通常是一个资源url，格式为“ui://”+“packageDescription id” + “component id”。
    """
    def __init__(self, display_item_tree, package_description_id=None):
        if display_item_tree.tag != "list" :
            raise ValueError("xml tag is not list.")
        super().__init__(display_item_tree)
        self.layout = self.display_item_tree.get("layout", "column")
        self.overflow = self.display_item_tree.get("overflow", "visible")
        self.scroll = self.display_item_tree.get("scroll", "vertical")
        self.scroll_bar_flags = int(self.display_item_tree.get("scrollBarFlags", "256"))
        margin = self.display_item_tree.get("margin")
        self.margin = tuple(map(int, margin.split(","))) if margin else None
        self.clip_softness = self.display_item_tree.get("clipSoftness", "0,0")
        self.line_item_count = int(self.display_item_tree.get("lineItemCount", "1"))
        self.line_item_count2 = int(self.display_item_tree.get("lineItemCount2", "1"))
        self.line_gap = int(self.display_item_tree.get("lineGap", "0"))
        self.col_gap = int(self.display_item_tree.get("colGap", "0"))
        self.default_item_url = self.display_item_tree.get("defaultItem")
        self.default_item_id = None
        self.package_description_id = package_description_id
        if package_description_id:
            self.get_default_item(package_description_id)
        self.item_list = []
        for item_tree in display_item_tree:
            item = FguiListItem(item_tree, self.package_description_id)
            self.item_list.append(item)

    def get_default_item(self, packageDescription_id):
        self.default_item_id = self.default_item_url[self.default_item_url.find(packageDescription_id)+len(packageDescription_id):]


class FguiLoader(FguiDisplayable):
    """
    FairyGUI中的装载器。
    包含属性url：表示引用的组件url，通常是一个资源url，格式为“ui://”+“packageDescription id” + “component id”。
    """
    def __init__(self, display_item_tree, package_description_id=None):
        if display_item_tree.tag != "loader" :
            raise ValueError("xml tag is not loader.")
        super().__init__(display_item_tree)
        self.url = self.display_item_tree.get("url")
        self.item_url = None
        if package_description_id:
            self.package_description_id = package_description_id
            self.get_item_id(package_description_id)

    def get_item_id(self, packageDescription_id):
        self.item_url = self.url[self.url.find(packageDescription_id)+len(packageDescription_id):]

class FguiRelation:
    """
    组件关联属性对象。表示与其他组件的相对关系。
    通常是一个target：“关联对象”-sidePair“关联方式”的类字典结构。
    """
    def __init__(self, relation_item_tree):
        if relation_item_tree.tag != "relation":
            raise ValueError("xml tag is not relation.")
        self.relation_item_tree = relation_item_tree
        self.relation_dict = {}
        key = self.relation_item_tree.get("target")
        value = self.relation_item_tree.get("sidePair")
        self.relation_dict[key] = value
        # print(self.relation_dict)

class FguiSliderProperty:
    """
    滑块的数值属性。分别包含最小值、最大值与当前值。
    如果某一项属性未出现则等于默认值0。
    """
    def __init__(self, slider_property_tree):
        if slider_property_tree.tag != "Slider":
            raise ValueError("xml tag is not Slider.")
        self.slider_property_tree = slider_property_tree
        self.current_value = self.slider_property_tree.get("value", 0)
        self.min_value = self.slider_property_tree.get("min", 0)
        self.max_value = self.slider_property_tree.get("max", 0)

class FguiGearBase:
    """
    Displayable控制器设置相关的基类。
    必定包含controller属性。
    可能包含page、value、default、tween属性。
    controller: 相关控制器名。
    page: 相关控制器索引。可能存在多个索引值，使用逗号分隔。
    value：与控制器索引对应的值，具体格式和作用根据Gear类型决定。若存在多个值则使用“|”分割。
    default：默认值。page属性未列出的控制器索引使用该默认值。
    tween：是否启用缓动。
    """
    def __init__(self, gear_item_tree):
        self.gear_item_tree = gear_item_tree
        self.controller_name = gear_item_tree.get("controller")
        self.controller_index = None
        controller_index = gear_item_tree.get("pages")
        values = gear_item_tree.get("values")
        if controller_index:
            self.controller_index = controller_index.split(",")
        self.values = None
        if values:
            self.values = values.split("|")
        self.default = gear_item_tree.get("default")
        self.tween = True if (gear_item_tree.get("tween") == "true") else False


class FguiGearDisplay(FguiGearBase):
    """
    Displayable中控制器与显示相关的设置。
    只在指定控制器的索引等于指定索引时才会显示displayable。
    唯一至多存在2个的gear，tag名称分别为gearDisplay、gearDisplay2。
    可由两个控制器同时控制是否显示。
    两个控制器的控制逻辑可以是“与”，或者“或”。
    例：
    <gearDisplay controller="button" pages="0"/>
    <gearDisplay2 controller="button2" pages="0" condition="0"/>
    """
    def __init__(self, gear_item_tree):
        if gear_item_tree.tag != "gearDisplay" and gear_item_tree.tag != "gearDisplay2":
            raise ValueError(f"xml tag is {gear_item_tree.tag}, not gearDisplay.")
        super().__init__(gear_item_tree)
        # condition=0——“与”逻辑；condition=1——“或”逻辑
        condition = gear_item_tree.get("condition")
        self.condition = 0
        if condition:
            self.condition = int(condition)

class FguiGearPos(FguiGearBase):
    """
    Displayable中控制器与位置相关的设置。
    属性values的值与属性pages有关。
    若pages只有一个控制值索引，value是一个使用竖线 ‘|’ 连接的 ‘x,y’形式坐标列表。
    若pages包含多个控制器索引，values则是多个固定长度2列表，使用竖线 ‘|’ 连接。
    例：
    <gearXY controller="ClassController" pages="0,1" values="807,241|823,241"/>
    <gearXY controller="button" default="60,50" tween="true"/>
    """
    def __init__(self, gear_item_tree):
        if gear_item_tree.tag != "gearXY" :
            raise ValueError("xml tag is not gearXY.")
        super().__init__(gear_item_tree)
        value = gear_item_tree.get("value")
        self.index_value_dict = {} # 该字典存放控制器索引与坐标
        if self.values:
            for i in range(len(self.values)):
                xypos = tuple(map(int, self.values[i].split(",")))
                self.index_value_dict[self.controller_index[i]] = xypos
        if self.default:
            xypos = tuple(map(int, self.default.split(",")))
            self.index_value_dict["default"] = xypos

class FguiGearLook(FguiGearBase):
    """
    Displayable中控制器与外观相关的设置。
    属性values的值与属性pages有关。
    若pages只有一个控制值索引，values是一个使用逗号连接的固定长度4列表，分别对应透明度、旋转、变灰、不可触摸。
    若pages包含多个控制器索引，values则是多个固定长度4列表，使用竖线 ‘|’ 连接。
    """
    def __init__(self, gear_item_tree):
        if gear_item_tree.tag != "gearLook" :
            raise ValueError("xml tag is not gearLook.")
        super().__init__(gear_item_tree)
        self.index_value_dict = {} # 该字典存放控制器索引与对应透明度、旋转、变灰、不可触摸
        if self.values:
            for i in range(len(self.values)):
                item = self.values[i].split(",")
                alpha = float(item[0])
                rotation = int(item[1])
                grayed = False if (item[2] != '0') else True
                touchable = True if (item[3] == '1') else False
                self.index_value_dict[self.controller_index[i]] = (alpha, rotation, grayed, touchable)
        if self.default:
            item = self.default.split(",")
            alpha = float(item[0])
            rotation = int(item[1])
            grayed = False if (item[2] != '0') else True
            touchable = True if (item[3] == '1') else False
            self.index_value_dict["default"] = (alpha, rotation, grayed, touchable)

class FguiGearSize(FguiGearBase):
    """
    Displayable中控制器与尺寸相关的设置。
    属性values的值与属性pages有关。
    若pages只有一个控制值索引，values是一个使用逗号连接的固定长度4列表，分别对应宽度、高度、宽度缩放系数、高度缩放系数。
    若pages包含多个控制器索引，values则是多个固定长度4列表，使用竖线 ‘|’ 连接。
    例：
    <gearSize controller="button" default="36,19,1,1"/>
    """
    def __init__(self, gear_item_tree):
        if gear_item_tree.tag != "gearSize" :
            raise ValueError("xml tag is not gearSize.")
        super().__init__(gear_item_tree)
        self.index_value_dict = {} # 该字典存放控制器索引与对应尺寸
        index_values = self.values
        if self.values:
            for i in range(len(self.values)):
                item = index_values[i].split(",")
                width = int(item[0])
                height = int(item[1])
                xscale = float(item[2])
                yscale = float(item[3])
                self.index_value_dict[self.controller_index[i]] = (width, height, xscale, yscale)
        if self.default:
            item = self.default.split(",")
            width = int(item[0])
            height = int(item[1])
            xscale = float(item[2])
            yscale = float(item[3])
            self.index_value_dict["default"] = item

class FguiGearColor(FguiGearBase):
    """
    Displayable中控制器与一个与图像颜色相乘的颜色设置。默认为“#ffffff”，白色，相乘后无视觉变化。
    属性values的值与属性pages有关。
    若pages只有一个控制值索引，values是一个24位的十六进制颜色值。
    若pages包含多个控制器索引，values则是多个十六进制颜色值，使用竖线 ‘|’ 连接。
    例:
    <gearColor controller="button" pages="1,2,3" values="#cccccc|#999999|#333333" default="#ffffff"/>
    """
    def __init__(self, gear_item_tree):
        if gear_item_tree.tag != "gearColor" :
            raise ValueError("xml tag is not gearColor.")
        super().__init__(gear_item_tree)
        self.index_value_dict = {} # 该字典存放控制器索引与对应颜色
        if self.values:
            for i in range(len(self.values)):
                self.index_value_dict[self.controller_index[i]] = self.values[i]
        if self.default:
            self.index_value_dict["default"] = self.default

class FguiGearText(FguiGearBase):
    """
    只会出现在文本组件中才生效的控制属性。
    属性values的值与属性pages有关。
    若pages只有一个控制值索引，values是一个字符串。
    若pages包含多个控制器索引，values则是字符串，使用竖线 ‘|’ 连接。
    例:
    <gearText controller="ClassController" pages="0,1" values="软骨鱼纲|辐鳍鱼纲"/>
    """
    def __init__(self, gear_item_tree):
        if gear_item_tree.tag != "gearText" :
            raise ValueError("xml tag is not gearText.")
        super().__init__(gear_item_tree)
        self.index_value_dict = {} # 该字典存放控制器索引与对应文本
        if self.values:
            for i in range(len(self.values)):
                self.index_value_dict[self.controller_index[i]] = self.values[i]
        if self.default:
            self.index_value_dict["default"] = self.default

class FguiGearIcon(FguiGearBase):
    """
    只会出现在装载器组件中才生效的控制属性。
    属性values的值与属性pages有关。
    若pages只有一个控制值索引，values是一个资源url，格式为“ui://”+“packageDescription id” + “component id”。
    若pages包含多个控制器索引，values是多个资源url，使用竖线 ‘|’ 连接。
    例:
    <gearIcon controller="button" pages="1" values="ui://gs4t1m2tno2rz" default="ui://gs4t1m2tno2r10"/>
    """
    def __init__(self, gear_item_tree):
        if gear_item_tree.tag != "gearIcon" :
            raise ValueError("xml tag is not gearIcon.")
        super().__init__(gear_item_tree)
        self.index_value_dict = {} # 该字典存放控制器索引与显示内容
        if self.values:
            for i in range(len(self.values)):
                self.index_value_dict[self.controller_index[i]] = self.values[i]
        if self.default:
            self.index_value_dict["default"] = self.default

class FguiAssets():
    """
    资源解析入口。
    """
    def __init__(self, fgui_project_path):
        if not fgui_project_path:
            raise ValueError("Project path is illegal.")
        self.fgui_project_name = os.path.basename(fgui_project_path)
        self.package_desc_file = os.path.join(fgui_project_path, f"{self.fgui_project_name}.bytes")
        # 发布的描述文件
        self.package_desc = None
        self.object_dict = ParseFguiPackageDescFile(self.package_desc_file)
        # 图集和图像描述文件
        self.sprite_desc_file = os.path.join(fgui_project_path, f"{self.fgui_project_name}@sprites.bytes")
        self.fgui_image_set = []
        self.fgui_atlas_dicts = {}
        # 组件信息
        self.fgui_component_set = []

        # 先找到packageDescription，解析出component、image和atlas列表
        package_key = 'package'
        if (not self.object_dict.__contains__(package_key)):
            raise ValueError('Could not find package description.')
        package_value = self.object_dict.get(package_key)
        if self.package_desc:
            self.package_desc.clear()
        self.package_desc = FguiPackage(package_value)
        print("This package includes", len(self.package_desc.component_list), "component(s).")
        for component in self.package_desc.component_list:
            if (not self.object_dict.__contains__(component.id)):
                raise ValueError('Could not find component info.')
            extention_type = self.object_dict[component.id].get("extention")
            # 根据extention构造不同对象
            if extention_type == "Button":
                component = FguiButton(self.object_dict[component.id], component.id, component.name, package_desc_id=self.package_desc.id)
            elif extention_type == "ScrollBar":
                component = FguiScrollBar(self.object_dict[component.id], component.id, component.name, package_desc_id=self.package_desc.id)
            elif extention_type == "Label":
                component = FguiLabel(self.object_dict[component.id], component.id, component.name, package_desc_id=self.package_desc.id)
            elif extention_type == "Slider":
                component = FguiSlider(self.object_dict[component.id], component.id, component.name, package_desc_id=self.package_desc.id)
            else:
                component = FguiComponent(self.object_dict[component.id], component.id, component.name, package_desc_id=self.package_desc.id)
            self.fgui_component_set.append(component)
        # 根据atlas_list建立altas_id与实际图集文件间的映射关系
        for atlas in self.package_desc.atlas_list:
            atlas_file_name = self.fgui_project_name + '@' + atlas.file
            self.fgui_atlas_dicts[atlas.id] = atlas_file_name
        # 若不需要从atlas切割出单个图片，可以结合 *@sprites.bytes文件，获取每个image对象
        self.fgui_image_set = ParseFguiSpriteDescFile(self.sprite_desc_file)

    def clear(self):
        self.fgui_project_name = ''
        self.package_desc_file = ''
        self.sprite_desc_file = ''
        self.package_desc.clear()
        self.object_dict.clear()
        self.fgui_atlas_dicts.clear()
        self.fgui_component_set.clear()
        self.fgui_image_set.clear()
        self.fgui_atlas_dicts.clear()

    def get_componentname_by_id(self, id):
        return self.package_desc.id_name_mapping[id]

    def get_component_by_id(self, id):
        for component in self.fgui_component_set:
            if component.id == id:
                return component
        return None

    def get_image_size_by_id(self, id):
        for image in self.fgui_image_set:
            if image.image_id == id:
                return (image.width, image.height)

    def __del__(self):
        self.clear()
