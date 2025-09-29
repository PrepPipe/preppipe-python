python early:

    import pygame
    import math

    class ButtonContainer(renpy.display.behavior.Button):
        """
        按钮容器类，按下后有缩放和改变颜色(未实现)效果。
        """
        def __init__(self, pressed_scale=1.0, pressed_dark=1.0, *args, **kwargs):
            super(ButtonContainer, self).__init__(**kwargs)
            self.pressed_scale = pressed_scale
            # FGUI中变暗的取值范围为0～1，0完全黑，1完全无效果。(编辑器中允许输入值超过1，但无效果。)
            # 此处使用BrightnessMatrix类，入参取值范围-1～1，-1完全变黑，0完全无效果，1完全变白。
            # 因此需要做一个转换
            self.pressed_dark = min(pressed_dark, 1.0) - 1.0
            self.brightness_matrix = BrightnessMatrix(value=self.pressed_dark)
            self.button_pressed = False
            self.width = 0
            self.height = 0
            self.blit_pos = (0, 0)

        def render(self, width, height, st, at):
            if self.button_pressed and self.pressed_dark != 0:
                t = Transform(child=self.child, anchor=(0.5, 0.5), matrixcolor=self.brightness_matrix)
            else:
                t = Transform(child=self.child, anchor=(0.5, 0.5), matrixcolor=None)
            child_render = renpy.render(t, width, height, st, at)
            self.width, self.height = child_render.get_size()
            self.size = (self.width, self.height)
            render = renpy.Render(self.width, self.height)
            if self.button_pressed:
                if self.pressed_scale != 1.0:
                    child_render.zoom(self.pressed_scale, self.pressed_scale)
                    # 为了居中，重新计算blit坐标
                    self.blit_pos = ((int)(self.width*(1-self.pressed_scale)/2), (int)(self.height*(1-self.pressed_scale)/2))
            else:
                self.blit_pos = (0, 0)
            render.blit(child_render, self.blit_pos)
            return render

        def event(self, ev, x, y, st):
            if renpy.map_event(ev, "mousedown_1") and renpy.is_pixel_opaque(self.child, self.width, self.height, st=st, at=0, x=x, y=y) and not self.button_pressed:
                self.button_pressed = True
                renpy.redraw(self, 0)
                return self.child.event(ev, x, y, st)
            if self.button_pressed:
                if renpy.map_event(ev, "mouseup_1"):
                    self.button_pressed = False
                    renpy.redraw(self, 0)
                elif  ev.type == pygame.MOUSEMOTION and ev.buttons[0] != 1 :
                    self.button_pressed = False
                    renpy.redraw(self, 0)
            return self.child.event(ev, x, y, st)

        def visit(self):
            return [ self.child ]

python early:
    renpy.register_sl_displayable("button_container", ButtonContainer, "pressed_button", 1)\
        .add_property("pressed_scale")\
        .add_property("pressed_dark")\
        .add_property_group("button")
    
init python:
    class SquenceAnimator(renpy.Displayable):
        """
        多图序列帧动画组件。
        """
        def __init__(self, prefix, separator, begin_index, end_index, interval, loop=True, **kwargs):
            super(SquenceAnimator, self).__init__(**kwargs)
            self.prefix = prefix
            self.separator = separator
            self.begin_index = begin_index
            self.end_index = end_index
            self.length = end_index - begin_index + 1


            self.sequence = []
            for i in range(begin_index, end_index+1):
                self.sequence.append(renpy.displayable(self.prefix + self.separator + str(i)))

            self.current_index = 0
            self.show_timebase = 0

            self.interval = interval
            self.loop = loop

        def render(self, width, height, st, at):
            ## st为0时，表示组件重新显示
            if st == 0:
                self.show_timebase = 0
                self.current_index = 0
            if (st >= (self.show_timebase + self.interval)):
                self.show_timebase = st
                self.current_index += 1
                if self.current_index >= self.length:
                    if self.loop:
                        self.current_index = 0
                    else:
                        self.current_index = self.length - 1
                        
            render = renpy.render(self.sequence[self.current_index], width, height, st, at)
            renpy.redraw(self, 0)

            return render

        # 重置序列帧
        def reset_sequence_index(self):
            self.current_index = 0

        def get_frame_image(self, index):
            return self.sequence[index]

    class SquenceAnimator2(renpy.Displayable):
        """
        单图序列帧动画组件。
        """
        def __init__(self, img, row, column, interval, loop=True, **kwargs):

            super(SquenceAnimator2, self).__init__(**kwargs)
            # im入参是字符串，需要转为Image对象，获取尺寸信息
            self.img = Image(img)
            self.size = renpy.image_size(self.img)
            # 行数
            self.row = row
            # 列数
            self.column = column
            # 单帧宽度
            self.frame_width = int(self.size[0] / column)
            # 单帧高度
            self.frame_height = int(self.size[1] / row)
            # 序列帧长度
            self.length = row * column

            self.sequence = []
            # 循环嵌套切割单帧图像
            for i in range(row):
                for j in range(column):
                    # im.Crop()已被标记为deprecated，但剪裁边缘正确。
                    # Crop()方法在右、低两边会有错误。
                    # 参考 https://github.com/renpy/renpy/issues/6376
                    self.sequence.append(im.Crop(self.img, (self.frame_width*j, self.frame_height*i, self.frame_width, self.frame_height)))

            self.current_index = 0
            self.show_timebase = 0

            self.interval = interval
            self.loop = loop

        def render(self, width, height, st, at):
            ## st为0时，表示组件重新显示
            if st == 0:
                self.show_timebase = 0
                self.current_index = 0
            if (st >= (self.show_timebase + self.interval)):
                self.show_timebase = st
                self.current_index += 1
                if self.current_index >= self.length:
                    if self.loop:
                        self.current_index = 0
                    else:
                        self.current_index = self.length - 1

            render = renpy.render(self.sequence[self.current_index], width, height, st, at)
            renpy.redraw(self, 0)

            return render

        # 重置序列帧
        def reset_sequence_index(self):
            self.current_index = 0

        def get_frame_image(self, index):
            return self.sequence[index]
