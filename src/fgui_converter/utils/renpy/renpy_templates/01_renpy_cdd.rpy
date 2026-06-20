python early:

    import math
    import pygame

    class ButtonContainer(renpy.display.behavior.Button):
        """
        按钮容器类，按下后有缩放和改变颜色效果。
        """
        def __init__(self, pressed_scale=1.0, pressed_dark=1.0, *args, **kwargs):
            super(ButtonContainer, self).__init__(**kwargs)
            self.pressed_scale = pressed_scale
            # FGUI中变暗的取值范围为0～1，0完全黑，1完全无效果。(编辑器中允许输入值超过1，但无效果。)
            # 此处使用BrightnessMatrix类，入参取值范围-1～1，-1完全变黑，0完全无效果，1完全变白。
            # 因此需要做一个转换。
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

    # 注册按钮容器类，sl名为button_container。
    renpy.register_sl_displayable("button_container", ButtonContainer, "pressed_button", 1)\
        .add_property("pressed_scale")\
        .add_property("pressed_dark")\
        .add_property_group("button")

    class ElasticViewport(renpy.display.layout.Viewport):
        """
        带边缘回弹效果的viewport类，删除edegscroll相关功能。
        可以指定是否启用水平或垂直拖拽，或者同时启用。
        """

        @staticmethod
        def _parse_draggable_axes(draggable):
            if draggable is True:
                return True, True

            if draggable is False:
                return False, False

            if isinstance(draggable, str):
                if draggable == "horizontal":
                    return True, False
                if draggable == "vertical":
                    return False, True
                return True, True

            if renpy.variant(draggable):
                return True, True

            return False, False

        def __init__(
            self,
            child=None,
            child_size=(None, None),
            offsets=(None, None),
            xadjustment=None,
            yadjustment=None,
            set_adjustments=True,
            mousewheel=False,
            draggable=False,
            style="viewport",
            xinitial=None,
            yinitial=None,
            replaces=None,
            arrowkeys=False,
            pagekeys=False,
            elastic_damping=0.8,
            **properties,
        ):
            drag_x_enabled, drag_y_enabled = ElasticViewport._parse_draggable_axes(draggable)

            super(ElasticViewport, self).__init__(
                child=child,
                child_size=child_size,
                offsets=offsets,
                xadjustment=xadjustment,
                yadjustment=yadjustment,
                set_adjustments=set_adjustments,
                mousewheel=mousewheel,
                draggable=drag_x_enabled or drag_y_enabled,
                edgescroll=None,
                style=style,
                xinitial=xinitial,
                yinitial=yinitial,
                replaces=replaces,
                arrowkeys=arrowkeys,
                pagekeys=pagekeys,
                **properties,
            )

            self.drag_x_enabled = drag_x_enabled
            self.drag_y_enabled = drag_y_enabled

            # 越界拖拽时 dx 的缩放系数，越大越界拉得越远。
            self.elastic_damping = elastic_damping
            # 松手后弹回速度，越大回弹越快。
            self.elastic_stiffness = 150.0
            # 松手后回弹系数，摩擦系数越小回弹后的衰减越大。
            self.elastic_friction_scrollback = 0.0002

            if isinstance(replaces, ElasticViewport):
                self.x_elastic = replaces.x_elastic
                self.y_elastic = replaces.y_elastic
                self.x_elastic_velocity = replaces.x_elastic_velocity
                self.y_elastic_velocity = replaces.y_elastic_velocity
                self.elastic_last_st = replaces.elastic_last_st
                self.drag_x_enabled = replaces.drag_x_enabled
                self.drag_y_enabled = replaces.drag_y_enabled
            else:
                self.x_elastic = 0.0
                self.y_elastic = 0.0
                self.x_elastic_velocity = 0.0
                self.y_elastic_velocity = 0.0
                self.elastic_last_st = None

        def _clear_disabled_axis_elastic(self):
            if not self.drag_x_enabled:
                self.x_elastic = 0.0
                self.x_elastic_velocity = 0.0

            if not self.drag_y_enabled:
                self.y_elastic = 0.0
                self.y_elastic_velocity = 0.0

        def _update_elastic_physics(self, st, dragging):
            if self.elastic_last_st is None:
                dt = 0.0
            else:
                dt = max(0.0, min(0.05, st - self.elastic_last_st))

            self.elastic_last_st = st

            if dragging:
                return False

            need_redraw = False

            for name in ("x", "y"):
                if name == "x" and not self.drag_x_enabled:
                    if self.x_elastic != 0.0 or self.x_elastic_velocity != 0.0:
                        self.x_elastic = 0.0
                        self.x_elastic_velocity = 0.0
                    continue

                if name == "y" and not self.drag_y_enabled:
                    if self.y_elastic != 0.0 or self.y_elastic_velocity != 0.0:
                        self.y_elastic = 0.0
                        self.y_elastic_velocity = 0.0
                    continue

                elastic = getattr(self, name + "_elastic")
                velocity = getattr(self, name + "_elastic_velocity")

                if abs(elastic) > 0.01 or abs(velocity) > 0.1:
                    target = 0.0
                    velocity += (target - elastic) * self.elastic_stiffness * dt
                    velocity *= math.pow(self.elastic_friction_scrollback, dt)
                    elastic += velocity * dt

                    if abs(velocity) < 2.0 and abs(elastic) < 1.0:
                        elastic = 0.0
                        velocity = 0.0

                    setattr(self, name + "_elastic", elastic)
                    setattr(self, name + "_elastic_velocity", velocity)
                    need_redraw = True
                elif elastic != 0.0 or velocity != 0.0:
                    setattr(self, name + "_elastic", 0.0)
                    setattr(self, name + "_elastic_velocity", 0.0)

            return need_redraw

        def update_offsets(self, cw, ch, st):
            cw = int(math.ceil(cw))
            ch = int(math.ceil(ch))

            width = self.width
            height = self.height

            xminimum, yminimum = renpy.display.layout.xyminimums(self.style, width, height)

            if not self.style.xfill:
                width = min(cw, width)

            if not self.style.yfill:
                height = min(ch, height)

            width = max(width, xminimum)
            height = max(height, yminimum)

            if (not renpy.display.render.sizing) and self.set_adjustments:
                xarange = max(cw - width, 0)

                if (self.xadjustment.range != xarange) or (self.xadjustment.page != width):
                    self.xadjustment.range = xarange
                    self.xadjustment.page = width
                    self.xadjustment.update()

                yarange = max(ch - height, 0)

                if (self.yadjustment.range != yarange) or (self.yadjustment.page != height):
                    self.yadjustment.range = yarange
                    self.yadjustment.page = height
                    self.yadjustment.update()

            if self.xoffset is not None:
                if isinstance(self.xoffset, int):
                    value = self.xoffset
                else:
                    value = max(cw - width, 0) * self.xoffset

                self.xadjustment.value = value

            if self.yoffset is not None:
                if isinstance(self.yoffset, int):
                    value = self.yoffset
                else:
                    value = max(ch - height, 0) * self.yoffset

                self.yadjustment.value = value

            dragging = (
                self.drag_position is not None
                and renpy.display.focus.get_grab() == self
            )

            self._clear_disabled_axis_elastic()

            if self._update_elastic_physics(st, dragging):
                renpy.display.render.redraw(self, 0)

            redraw = self.xadjustment.periodic(st)
            if redraw is not None:
                renpy.display.render.redraw(self, redraw)

            redraw = self.yadjustment.periodic(st)
            if redraw is not None:
                renpy.display.render.redraw(self, redraw)

            cxo = -int(self.xadjustment.value) + int(self.x_elastic)
            cyo = -int(self.yadjustment.value) + int(self.y_elastic)

            self.width = width
            self.height = height

            return cxo, cyo, width, height

        def event(self, ev, x, y, st):
            self.xoffset = None
            self.yoffset = None

            if not ((0 <= x < self.width) and (0 <= y <= self.height)):
                inside = False
            else:
                inside = True

            draggable = (self.drag_x_enabled and self.xadjustment.range) or (self.drag_y_enabled and self.yadjustment.range)

            grab = renpy.display.focus.get_grab()

            if (grab is not None) and getattr(grab, "_draggable", False) and (grab is not self):
                self.drag_position = None
            elif draggable:
                if grab is None and renpy.display.behavior.map_event(ev, "viewport_drag_end"):
                    self.drag_position = None
                elif (grab is not self) and ev.type == pygame.MOUSEMOTION and not any(ev.buttons):
                    self.drag_position = None
            else:
                self.drag_position = None

            if inside and draggable and (self.drag_position is not None) and (grab is not self):
                if ev.type == pygame.MOUSEMOTION:
                    oldx, oldy = self.drag_position

                    grabbed = getattr(grab, "_draggable", False) and grab.is_focused()

                    edx = x - oldx if self.drag_x_enabled else 0
                    edy = y - oldy if self.drag_y_enabled else 0

                    if math.hypot(edx, edy) >= renpy.config.viewport_drag_radius and not grabbed:
                        rv = renpy.display.focus.force_focus(self)
                        renpy.display.focus.set_grab(self)
                        self.drag_position = (x, y)
                        self.drag_position_time = st
                        self.drag_speed = (0.0, 0.0)
                        grab = self

                        if rv is not None:
                            return rv

            if renpy.display.focus.get_grab() == self:
                old_xvalue = self.xadjustment.value
                old_yvalue = self.yadjustment.value

                oldx, oldy = self.drag_position
                dx = x - oldx if self.drag_x_enabled else 0
                dy = y - oldy if self.drag_y_enabled else 0

                dt = st - self.drag_position_time
                if dt > 0:
                    old_xspeed, old_yspeed = self.drag_speed
                    new_xspeed = (-dx / dt / 60) if self.drag_x_enabled else 0.0
                    new_yspeed = (-dy / dt / 60) if self.drag_y_enabled else 0.0

                    done = min(1.0, dt / (1 / 60))

                    new_xspeed = old_xspeed + done * (new_xspeed - old_xspeed)
                    new_yspeed = old_yspeed + done * (new_yspeed - old_yspeed)

                    self.drag_speed = (new_xspeed, new_yspeed)

                if ev.type == pygame.MOUSEMOTION and not any(ev.buttons):
                    self.drag_position = None
                    self.drag_position_time = None

                if renpy.display.behavior.map_event(ev, "viewport_drag_end"):
                    renpy.display.focus.set_grab(None)

                    xspeed, yspeed = self.drag_speed

                    if self.drag_x_enabled:
                        if xspeed and renpy.config.viewport_inertia_amplitude and not self.xadjustment.force_step:
                            self.xadjustment.inertia(
                                renpy.config.viewport_inertia_amplitude * xspeed,
                                renpy.config.viewport_inertia_time_constant,
                                st,
                            )
                        elif self.xadjustment.force_step == "release":
                            xvalue = self.xadjustment.round_value(old_xvalue, release=True)
                            self.xadjustment.inertia(
                                xvalue - old_xvalue, self.xadjustment.step / (renpy.config.screen_width * 2), st
                            )
                        else:
                            xvalue = self.xadjustment.round_value(old_xvalue, release=True)
                            self.xadjustment.change(xvalue)

                    if self.drag_y_enabled:
                        if yspeed and renpy.config.viewport_inertia_amplitude and not self.yadjustment.force_step:
                            self.yadjustment.inertia(
                                renpy.config.viewport_inertia_amplitude * yspeed,
                                renpy.config.viewport_inertia_time_constant,
                                st,
                            )
                        elif self.yadjustment.force_step == "release":
                            yvalue = self.yadjustment.round_value(old_yvalue, release=True)
                            self.yadjustment.inertia(
                                yvalue - old_yvalue, self.yadjustment.step / (renpy.config.screen_height * 2), st
                            )
                        else:
                            yvalue = self.yadjustment.round_value(old_yvalue, release=True)
                            self.yadjustment.change(yvalue)

                    self.drag_position = None
                    self.drag_position_time = None

                    if (
                        (self.drag_x_enabled and (abs(self.x_elastic) > 0.01 or abs(self.x_elastic_velocity) > 0.1))
                        or (self.drag_y_enabled and (abs(self.y_elastic) > 0.01 or abs(self.y_elastic_velocity) > 0.1))
                    ):
                        self.elastic_last_st = None
                        renpy.display.render.redraw(self, 0)

                    raise renpy.display.core.IgnoreEvent()

                new_xvalue = self.xadjustment.round_value(old_xvalue - dx, release=False)
                if old_xvalue == new_xvalue:
                    if old_xvalue <= 0 and dx > 0:
                        self.x_elastic += dx * self.elastic_damping
                        self.x_elastic_velocity = dx * 60.0
                        newx = x
                    elif old_xvalue >= self.xadjustment.range and dx < 0:
                        self.x_elastic += dx * self.elastic_damping
                        self.x_elastic_velocity = dx * 60.0
                        newx = x
                    else:
                        newx = oldx
                else:
                    self.xadjustment.change(new_xvalue)
                    if abs(self.x_elastic) > 0.01:
                        self.x_elastic = 0.0
                        self.x_elastic_velocity = 0.0
                    newx = x

                new_yvalue = self.yadjustment.round_value(old_yvalue - dy, release=False)
                if old_yvalue == new_yvalue:
                    if old_yvalue <= 0 and dy > 0:
                        self.y_elastic += dy * self.elastic_damping
                        self.y_elastic_velocity = dy * 60.0
                        newy = y
                    elif old_yvalue >= self.yadjustment.range and dy < 0:
                        self.y_elastic += dy * self.elastic_damping
                        self.y_elastic_velocity = dy * 60.0
                        newy = y
                    else:
                        newy = oldy
                else:
                    self.yadjustment.change(new_yvalue)
                    if abs(self.y_elastic) > 0.01:
                        self.y_elastic = 0.0
                        self.y_elastic_velocity = 0.0
                    newy = y

                self.drag_position = (newx, newy)
                self.drag_position_time = st

                renpy.display.render.redraw(self, 0)

            if inside and self.mousewheel:
                if self.mousewheel == "horizontal-change":
                    adjustment = self.xadjustment
                    change = True
                elif self.mousewheel == "horizontal":
                    adjustment = self.xadjustment
                    change = False
                elif self.mousewheel == "change":
                    adjustment = self.yadjustment
                    change = True
                else:
                    adjustment = self.yadjustment
                    change = False

                if renpy.display.behavior.map_event(ev, "viewport_wheelup"):
                    if change and (adjustment.value == 0):
                        return None

                    rv = adjustment.change(adjustment.value - adjustment.step)
                    if rv is not None:
                        return rv
                    else:
                        raise renpy.display.core.IgnoreEvent()

                if renpy.display.behavior.map_event(ev, "viewport_wheeldown"):
                    if change and (adjustment.value == adjustment.range):
                        return None

                    rv = adjustment.change(adjustment.value + adjustment.step)
                    if rv is not None:
                        return rv
                    else:
                        raise renpy.display.core.IgnoreEvent()

            if self.arrowkeys:
                if renpy.display.behavior.map_event(ev, "viewport_leftarrow"):
                    if self.xadjustment.value == 0:
                        return None

                    rv = self.xadjustment.change(self.xadjustment.value - self.xadjustment.step)
                    if rv is not None:
                        return rv
                    else:
                        raise renpy.display.core.IgnoreEvent()

                if renpy.display.behavior.map_event(ev, "viewport_rightarrow"):
                    if self.xadjustment.value == self.xadjustment.range:
                        return None

                    rv = self.xadjustment.change(self.xadjustment.value + self.xadjustment.step)
                    if rv is not None:
                        return rv
                    else:
                        raise renpy.display.core.IgnoreEvent()

                if renpy.display.behavior.map_event(ev, "viewport_uparrow"):
                    if self.yadjustment.value == 0:
                        return None

                    rv = self.yadjustment.change(self.yadjustment.value - self.yadjustment.step)
                    if rv is not None:
                        return rv
                    else:
                        raise renpy.display.core.IgnoreEvent()

                if renpy.display.behavior.map_event(ev, "viewport_downarrow"):
                    if self.yadjustment.value == self.yadjustment.range:
                        return None

                    rv = self.yadjustment.change(self.yadjustment.value + self.yadjustment.step)
                    if rv is not None:
                        return rv
                    else:
                        raise renpy.display.core.IgnoreEvent()

            if self.pagekeys:
                if renpy.display.behavior.map_event(ev, "viewport_pageup"):
                    rv = self.yadjustment.change(self.yadjustment.value - self.yadjustment.page)
                    if rv is not None:
                        return rv
                    else:
                        raise renpy.display.core.IgnoreEvent()

                if renpy.display.behavior.map_event(ev, "viewport_pagedown"):
                    rv = self.yadjustment.change(self.yadjustment.value + self.yadjustment.page)
                    if rv is not None:
                        return rv
                    else:
                        raise renpy.display.core.IgnoreEvent()

            ignore_event = False

            if inside and draggable:
                if renpy.display.behavior.map_event(ev, "viewport_drag_start"):
                    self.drag_position = (x, y)
                    self.drag_position_time = st
                    self.drag_speed = (0.0, 0.0)

                    if self.drag_x_enabled:
                        self.xadjustment.end_animation(instantly=True)
                    if self.drag_y_enabled:
                        self.yadjustment.end_animation(instantly=True)

                    if not renpy.display.focus.get_focused():
                        renpy.display.focus.set_grab(self)

                    ignore_event = True

            rv = renpy.display.layout.Container.event(self, ev, x, y, st)

            if rv is not None:
                return rv

            if ignore_event:
                raise renpy.display.core.IgnoreEvent()

            return None

    # 注册带边缘回弹效果的viewport类，sl名为elastic_viewport。
    renpy.register_sl_displayable("elastic_viewport", ElasticViewport, "viewport", 1)\
    .add_property("child_size")\
    .add_property("xadjustment")\
    .add_property("yadjustment")\
    .add_property("set_adjustments")\
    .add_property("mousewheel")\
    .add_property("draggable")\
    .add_property("xinitial")\
    .add_property("yinitial")\
    .add_property("arrowkeys")\
    .add_property("pagekeys")\
    .add_property("elastic_damping")\
    .add_property_group("position")\
    .add_property_group("ui")


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
