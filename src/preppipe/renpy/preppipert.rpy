# This is the runtime library for Ren'Py engine.
# 立绘入场/离场 ATL：只作用当前 show 的那张图（避免 show/hide with 整屏转场）

transform preppipe_sprite_fade_in(duration=0.5):
    alpha 0.0
    linear duration alpha 1.0

transform preppipe_sprite_dissolve_in(duration=0.5):
    alpha 0.0
    linear duration alpha 1.0

transform preppipe_sprite_slide_in(duration=0.5, ox=0.0, oy=0.0):
    offset (ox, oy)
    linear duration offset (0, 0)

transform preppipe_sprite_slide_out(duration=0.5, ox=0.0, oy=0.0):
    offset (0, 0)
    linear duration offset (ox, oy)

# 缩放枢轴用 xanchor/yanchor（相对立绘自身 0~1）；勿用 xalign/yalign（会按整屏对齐）
transform preppipe_sprite_zoom_in(duration=0.5, xa=0.5, ya=0.5):
    subpixel True
    xanchor xa
    yanchor ya
    zoom 0.0
    linear duration zoom 1.0

# 退场只改 zoom，不改 anchor/pos，避免重置位置；枢轴保持当前 Transform 状态
transform preppipe_sprite_zoom_out(duration=0.5):
    subpixel True
    linear duration zoom 0.01

transform preppipe_sprite_fade_out(duration=0.5):
    alpha 1.0
    linear duration alpha 0.0

# 角色立绘震动：Ren'Py 8.5.2 下 ATL repeat + xoffset/yoffset 在 pause 渲染时易触发 atl.py「infinite loop」；
# 实现放在 init python 的 _preppipe_char_shake_transform（Transform function），波形与原 4×0.05s/周期一致。

transform preppipe_at_char_flash(fi, hld, fo, col):
    matrixcolor IdentityMatrix()
    linear fi matrixcolor TintMatrix(col) * BrightnessMatrix(0.35)
    pause hld
    linear fo matrixcolor IdentityMatrix()

# 跳动：与角色震动相同，Ren'Py 8.5.2 下 ATL repeat+yoffset 易 infinite loop，见 _preppipe_bounce_transform。

transform preppipe_move_lin(sx, sy, ex, ey, d):
    subpixel True
    pos (int(sx), int(sy))
    linear d pos (int(ex), int(ey))

transform preppipe_move_ease(sx, sy, ex, ey, d):
    subpixel True
    pos (int(sx), int(sy))
    ease d pos (int(ex), int(ey))

transform preppipe_move_easein(sx, sy, ex, ey, d):
    subpixel True
    pos (int(sx), int(sy))
    easein d pos (int(ex), int(ey))

transform preppipe_move_easeout(sx, sy, ex, ey, d):
    subpixel True
    pos (int(sx), int(sy))
    easeout d pos (int(ex), int(ey))

transform preppipe_at_scale_to(z1, d, xa, ya):
    subpixel True
    zoom 1.0
    xalign xa
    yalign ya
    linear d zoom z1

transform preppipe_rotate_to(a, d, xa, ya):
    subpixel True
    rotate 0.0
    xalign xa
    yalign ya
    linear d rotate a

transform preppipe_at_char_tremble_loop(amp, period):
    subpixel True
    block:
        linear (period / 2.0) xoffset amp
        linear (period / 2.0) xoffset (-amp)
        repeat

# halfp 为半周期秒数（Python 已 max(0.001, period/2)）；n 为循环次数
transform preppipe_at_char_tremble_cycles(amp, halfp, n):
    subpixel True
    block:
        repeat n
            linear halfp xoffset amp
            linear halfp xoffset (-amp)
    # 从末帧 -amp 回到 0，须带时长；勿写零耗时 xoffset 0
    linear 0.02 xoffset 0

# 滤镜（场景/立绘）：命令「时长」为过渡到目标状态的秒数；SaturationMatrix 参数 0=全灰、1=原饱和度
transform preppipe_at_fx_grayscale(s, dur):
    matrixcolor IdentityMatrix()
    linear max(0.001, dur) matrixcolor SaturationMatrix(1.0 - s)

transform preppipe_at_fx_grayscale_snap(s):
    matrixcolor SaturationMatrix(1.0 - s)

transform preppipe_at_fx_opacity(target_a, dur):
    alpha 1.0
    linear max(0.001, dur) alpha target_a

transform preppipe_at_fx_opacity_snap(a):
    alpha a

transform preppipe_at_fx_tint(col, s, dur):
    matrixcolor IdentityMatrix()
    linear max(0.001, dur) matrixcolor (TintMatrix(col) * SaturationMatrix(max(0.05, 1.0 - 0.4 * s)))

transform preppipe_at_fx_tint_snap(col, s):
    matrixcolor (TintMatrix(col) * SaturationMatrix(max(0.05, 1.0 - 0.4 * s)))

transform preppipe_at_fx_blur(b, dur):
    blur 0.0
    linear max(0.001, dur) blur b

transform preppipe_at_fx_blur_snap(b):
    blur b

# 结束场景层滤镜：show_layer_at 后须用显式复位覆盖，单靠 hide_layer_at 在部分版本下仍会残留灰化/模糊
transform preppipe_master_layer_reset:
    matrixcolor IdentityMatrix()
    alpha 1.0
    blur 0.0

transform preppipe_weather_overlay_fade(overlay_fi):
    alpha 0.0
    linear overlay_fi alpha 1.0

screen preppipe_weather_screen():
    modal False
    zorder 100
    fixed:
        xfill True
        yfill True
        add renpy.store._preppipe_weather_displayable at preppipe_weather_overlay_fade(renpy.store._preppipe_weather_overlay_fi)

screen preppipe_flash_screen(color, fi, h, fo):
    modal True
    zorder 9998
    add Solid(color):
        at transform:
            alpha 0.0
            linear fi alpha 1.0
            pause h
            linear fo alpha 0.0
    timer (fi + h + fo) action Return()

# 全屏缩放转场（scene / 整层）
init offset = -2

init python:
    import re
    import unicodedata

    from renpy.display.motion import Transform as _PreppipeShakeMotionTransform

    _preppipe_float_num_re = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
    _preppipe_shake_seg_s = 0.05
    _preppipe_shake_cycle_s = 0.2

    def _preppipe_coerce_float(x):
        """任意来源（表格引号、Revertable、Ren'Py 包装类型）统一为 float；永不抛错，避免引擎报「无法解析为浮点数」。"""
        try:
            if isinstance(x, bool):
                return float(x)
            if isinstance(x, (int, float)):
                r = float(x)
                if r != r:  # NaN
                    return 0.0
                return r
            if x is None:
                return 0.0
            if isinstance(x, str):
                raw = x
            else:
                try:
                    r = float(x)
                    if r != r:
                        return 0.0
                    return r
                except Exception:
                    try:
                        raw = str(x)
                    except Exception:
                        return 0.0
            s = unicodedata.normalize("NFKC", raw).strip().replace("\ufeff", "")
            for _ in range(8):
                if len(s) < 2:
                    break
                if s[0] == s[-1] and s[0] in "'\"":
                    s = s[1:-1].strip()
                    continue
                if s[0] in "\u201c\u2018" and s[-1] in "\u201d\u2019":
                    s = s[1:-1].strip()
                    continue
                break
            if s == "" or s in ("-", "+"):
                return 0.0
            try:
                r = float(s)
                if r != r:
                    return 0.0
                return r
            except Exception:
                m = _preppipe_float_num_re.search(s)
                if m:
                    try:
                        r = float(m.group(0))
                        if r != r:
                            return 0.0
                        return r
                    except Exception:
                        pass
                return 0.0
        except Exception:
            return 0.0

    def _preppipe_shake_offset_in_cycle(t_local, amp):
        """单周期 [0,0.2) 内与旧 ATL 一致：0→a→-a→0.45a→0，每段 0.05s。"""
        if abs(amp) < 1e-12:
            return 0.0
        c = _preppipe_shake_cycle_s
        s = _preppipe_shake_seg_s
        t_local = max(0.0, min(float(t_local), c - 1e-12))
        si = min(3, int(t_local // s))
        frac = (t_local - si * s) / s
        a = float(amp)
        if si == 0:
            return frac * a
        if si == 1:
            return a + frac * (-2.0 * a)
        if si == 2:
            return -a + frac * (a * 0.45 + a)
        return a * 0.45 * (1.0 - frac)

    def _preppipe_char_shake_transform(duration, ax, ay):
        d = max(0.0, float(duration))
        ax = float(ax)
        ay = float(ay)

        def shake_fn(trans, st, at):
            if st >= d:
                trans.xoffset = 0
                trans.yoffset = 0
                return None
            t_eff = min(float(st), d - 1e-12)
            tl = t_eff % _preppipe_shake_cycle_s
            trans.xoffset = _preppipe_shake_offset_in_cycle(tl, ax)
            trans.yoffset = _preppipe_shake_offset_in_cycle(tl, ay)
            return 1.0 / 120.0

        return _PreppipeShakeMotionTransform(function=shake_fn, subpixel=True)

    def _preppipe_bounce_transform(duration, hpx, cnt):
        """cnt 次弹跳在 duration 内均匀分配；每跳前半程 0→-hpx、后半程 -hpx→0（等价于 seg=d/(2*cnt) 且 seg≥0.001 时的 ATL）。"""
        d = max(0.0, float(duration))
        h = float(hpx)
        n = max(1, int(cnt))

        def bounce_fn(trans, st, at):
            if d <= 0 or st >= d:
                trans.yoffset = 0
                return None
            t = min(float(st), d - 1e-12)
            fb = ((t / d) * n) % 1.0
            if fb < 0.5:
                trans.yoffset = -h * (fb * 2.0)
            else:
                trans.yoffset = -h * (2.0 - 2.0 * fb)
            return 1.0 / 120.0

        return _PreppipeShakeMotionTransform(function=bounce_fn, subpixel=True)

    try:
        from renpy.ui import Hide as _preppipe_screen_Hide
    except Exception:
        _preppipe_screen_Hide = None

    renpy.store.preppipe_char_sustained_fx = set()
    renpy.store.preppipe_scene_layer_filter_active = False
    renpy.store._preppipe_scene_filter_snapshot = None
    renpy.store.preppipe_weather_active = False
    renpy.store._preppipe_weather_displayable = None
    renpy.store._preppipe_weather_overlay_fi = 0.8
    renpy.store._preppipe_weather_fo = 0.45

    # Avoid polluting store with 'layout'/'transform' (Ren'Py 00compat expects store.layout).
    # 9 points: top_left, top_center, top_right, center_left, center, center_right, bottom_left, bottom_center, bottom_right
    # 缩放支点 (xalign, yalign)，0=左/上 0.5=中 1=右/下
    _ZOOM_POINT_ALIGN = {
        "top_left": (0.0, 0.0), "top_center": (0.5, 0.0), "top_right": (1.0, 0.0),
        "center_left": (0.0, 0.5), "center": (0.5, 0.5), "center_right": (1.0, 0.5),
        "bottom_left": (0.0, 1.0), "bottom_center": (0.5, 1.0), "bottom_right": (1.0, 1.0),
    }

    class _PreppipeZoomTransition(renpy.display.displayable.Displayable):
        def __init__(self, old_widget, new_widget, duration, zoom_in, point="center", **kwargs):
            super(_PreppipeZoomTransition, self).__init__(**kwargs)
            self.old_widget = old_widget
            self.new_widget = new_widget
            self.duration = duration
            self.zoom_in = zoom_in
            self.point = (point or "center").strip().lower()
            self.delay = duration

        def _align(self):
            key = self.point.replace(" ", "_") if self.point else "center"
            xa, ya = _ZOOM_POINT_ALIGN.get(key, (0.5, 0.5))
            return float(xa), float(ya)

        def render(self, width, height, st, at):
            progress = min(1.0, st / self.duration) if self.duration > 0 else 1.0
            if progress < 1.0:
                renpy.redraw(self, 0)
            xa, ya = self._align()
            Transform = renpy.display.transform.Transform
            # Ren'Py 的 zoom 以显示区左上 (0,0) 为缩放中心；要让 (xa,ya) 固定，需把缩放后图像放在
            # 像素位置 (xa*width*(1-zoom), ya*height*(1-zoom))，并设 anchor=(0,0)
            def make_zoom_transform(child, zoom_val):
                if zoom_val <= 0:
                    zoom_val = 1e-6
                return Transform(child=child, zoom=zoom_val, xanchor=0, yanchor=0)
            if self.zoom_in:
                bottom = self.old_widget
                top = make_zoom_transform(self.new_widget, progress)
                zoom_val = progress
            else:
                zoom_val = 1.0 - progress
                bottom = self.new_widget
                top = make_zoom_transform(self.old_widget, zoom_val)
            if zoom_val <= 0:
                zoom_val = 1e-6
            px = int(round(xa * width * (1.0 - zoom_val)))
            py = int(round(ya * height * (1.0 - zoom_val)))
            bottom_render = renpy.render(bottom, width, height, st, at)
            top_render = renpy.render(top, width, height, st, at)
            render = renpy.Render(width, height)
            render.blit(bottom_render, (0, 0))
            # Transform 的 render 可能是缩放后内容的尺寸，需在 (px,py) 处 blit 才能使支点 (xa,ya) 固定
            render.blit(top_render, (px, py))
            return render

    def preppipe_zoomin(duration=0.5, point="center"):
        duration = _preppipe_coerce_float(duration)

        def _transition(old_widget=None, new_widget=None):
            return _PreppipeZoomTransition(old_widget, new_widget, duration, zoom_in=True, point=point)
        _transition.delay = duration
        return _transition

    def preppipe_zoomout(duration=0.5, point="center"):
        duration = _preppipe_coerce_float(duration)

        def _transition(old_widget=None, new_widget=None):
            return _PreppipeZoomTransition(old_widget, new_widget, duration, zoom_in=False, point=point)
        _transition.delay = duration
        return _transition

    def preppipe_scene_shake(duration=0.5, amplitude=12.0, decay=0.0, direction=""):
        duration = _preppipe_coerce_float(duration)
        amplitude = _preppipe_coerce_float(amplitude)
        decay = _preppipe_coerce_float(decay)
        steps = max(2, min(20, int(duration * 7)))
        per = duration / float(steps) if steps else 0.05
        for _ in range(steps):
            if direction == "horizontal":
                renpy.with_statement(renpy.store.hpunch)
            elif direction == "vertical":
                renpy.with_statement(renpy.store.vpunch)
            else:
                renpy.with_statement(renpy.store.hpunch)
                renpy.with_statement(renpy.store.vpunch)
            renpy.pause(per * 0.45)

    def preppipe_scene_flash(color, fi, h, fo):
        fi = _preppipe_coerce_float(fi)
        h = _preppipe_coerce_float(h)
        fo = _preppipe_coerce_float(fo)
        renpy.call_screen("preppipe_flash_screen", color=color, fi=fi, h=h, fo=fo)

    def preppipe_weather_start(kind, intensity, inner_fi, inner_fo, overlay_fi, vx, vy, sustain=-1.0):
        """全屏天气：SnowBlossom + 独立 screen；sustain 预留（当前均持续至 preppipe_weather_stop / 结束场景特效）。"""
        from renpy.display.particle import SnowBlossom

        kind = (kind or "").strip().lower()
        intensity = _preppipe_coerce_float(intensity)
        inner_fi = max(0.0, _preppipe_coerce_float(inner_fi))
        inner_fo = max(0.05, _preppipe_coerce_float(inner_fo))
        overlay_fi = max(0.001, _preppipe_coerce_float(overlay_fi))
        vx = _preppipe_coerce_float(vx)
        vy = _preppipe_coerce_float(vy)

        if renpy.store.preppipe_weather_active:
            renpy.hide_screen("preppipe_weather_screen")
            renpy.store.preppipe_weather_active = False

        cnt = max(6, min(220, int(intensity / 2)))
        renpy.store._preppipe_weather_fo = inner_fo
        renpy.store._preppipe_weather_overlay_fi = overlay_fi

        if kind == "snow":
            flake = Solid("#ffffff", xsize=3, ysize=3)
            d = SnowBlossom(
                flake,
                count=cnt,
                border=100,
                xspeed=(-35, 35),
                yspeed=(70, 150),
                start=inner_fi,
                fast=False,
                animation=True,
            )
        elif kind == "rain":
            drop = Solid("#aabdd8", xsize=2, ysize=18)
            ax = sorted((vx * 0.88, vx * 1.12))
            ay = sorted((vy * 0.92, vy * 1.08))
            d = SnowBlossom(
                drop,
                count=cnt,
                border=140,
                xspeed=(ax[0], ax[1]),
                yspeed=(ay[0], ay[1]),
                start=inner_fi,
                fast=False,
                animation=True,
            )
        else:
            return

        renpy.store._preppipe_weather_displayable = d
        renpy.store.preppipe_weather_active = True
        renpy.show_screen("preppipe_weather_screen")
        _preppipe_reapply_master_scene_filter_if_active()

    def preppipe_weather_stop():
        if not renpy.store.preppipe_weather_active:
            return
        fo = max(0.001, _preppipe_coerce_float(renpy.store._preppipe_weather_fo))
        tr = renpy.store.Dissolve(fo)
        # renpy.store.Hide 在部分工程未注入；用 renpy.ui.Hide + renpy.run 与「hide screen … with」一致
        if _preppipe_screen_Hide is not None:
            renpy.run(_preppipe_screen_Hide("preppipe_weather_screen", transition=tr))
        else:
            renpy.hide_screen("preppipe_weather_screen")
        renpy.store.preppipe_weather_active = False
        renpy.store._preppipe_weather_displayable = None

    def preppipe_char_shake(imspec, x, y, w, h, duration, amplitude, decay, direction):
        duration = _preppipe_coerce_float(duration)
        amplitude = _preppipe_coerce_float(amplitude)
        decay = _preppipe_coerce_float(decay)
        dkey = str(direction or "").strip().lower()
        xh = 0 if dkey in ("vertical", "v", "y", "垂直") else 1
        yh = 0 if dkey in ("horizontal", "h", "x", "水平") else 1
        ax = amplitude * xh
        ay = amplitude * yh
        st = renpy.store
        if abs(ax) < 1e-9 and abs(ay) < 1e-9:
            tr = None
        else:
            tr = _preppipe_char_shake_transform(duration, ax, ay)
        base = st.screen2d_abs(x, y, w, h)
        if tr is None:
            renpy.show(imspec, at_list=[base])
        else:
            renpy.show(imspec, at_list=[base, tr])
        renpy.pause(duration)
        renpy.show(imspec, at_list=[base])

    def preppipe_char_flash(imspec, x, y, w, h, color, fi, hld, fo):
        fi = _preppipe_coerce_float(fi)
        hld = _preppipe_coerce_float(hld)
        fo = _preppipe_coerce_float(fo)
        renpy.show(imspec, at_list=[renpy.store.screen2d_abs(x, y, w, h), renpy.store.preppipe_at_char_flash(fi, hld, fo, color)])
        renpy.pause(fi + hld + fo)

    def _preppipe_fx_pick_tr(fk, s, dur, col):
        fk = (fk or "").strip().lower()
        s = _preppipe_coerce_float(s)
        dur = _preppipe_coerce_float(dur)
        col = col or "#ffffff"
        snap = dur <= 0
        d = max(0.001, dur) if not snap else 0.001
        st = renpy.store
        if fk == "grayscale":
            return st.preppipe_at_fx_grayscale_snap(s) if snap else st.preppipe_at_fx_grayscale(s, d)
        if fk == "opacity":
            return st.preppipe_at_fx_opacity_snap(s) if snap else st.preppipe_at_fx_opacity(s, d)
        if fk == "tint":
            return st.preppipe_at_fx_tint_snap(col, s) if snap else st.preppipe_at_fx_tint(col, s, d)
        if fk == "blur":
            return st.preppipe_at_fx_blur_snap(s) if snap else st.preppipe_at_fx_blur(s, d)
        return None

    def _preppipe_reapply_master_scene_filter_if_active():
        """Ren'Py 在 show_screen 等之后常会丢掉 master 的 show_layer_at；若仍有场景滤镜标记则按快照补回（如先模糊再下雪）。"""
        if not getattr(renpy.store, "preppipe_scene_layer_filter_active", False):
            return
        snap = getattr(renpy.store, "_preppipe_scene_filter_snapshot", None)
        if snap is None:
            return
        fk, s, col = snap
        tr = _preppipe_fx_pick_tr(fk, s, 0.0, col)
        if tr is None:
            return
        sla = getattr(renpy, "show_layer_at", None)
        if sla is not None:
            sla([tr], layer="master")

    def preppipe_char_filter(imspec, x, y, w, h, fk, strength, dur, col):
        x, y, w, h = int(x), int(y), int(w), int(h)
        base = renpy.store.screen2d_abs(x, y, w, h)
        fk = (fk or "").strip().lower()
        dur = _preppipe_coerce_float(dur)
        k = (_preppipe_char_fx_key(imspec), x, y, w, h)
        tr = _preppipe_fx_pick_tr(fk, strength, dur, col)
        if tr is None:
            return
        if dur < 0:
            renpy.show(imspec, at_list=[base, tr])
            renpy.store.preppipe_char_sustained_fx.add(k)
            return
        renpy.show(imspec, at_list=[base, tr])
        if dur > 0:
            renpy.pause(dur)

    def preppipe_scene_filter(fk, strength, dur, col):
        fk = (fk or "").strip().lower()
        dur = _preppipe_coerce_float(dur)
        tr = _preppipe_fx_pick_tr(fk, strength, dur, col)
        if tr is None:
            return
        sla = getattr(renpy, "show_layer_at", None)
        if sla is None:
            return
        sla([tr], layer="master")
        renpy.store.preppipe_scene_layer_filter_active = True
        renpy.store._preppipe_scene_filter_snapshot = (fk, _preppipe_coerce_float(strength), col)
        if dur > 0:
            renpy.pause(dur)

    def _preppipe_char_fx_key(imspec):
        if isinstance(imspec, tuple):
            return imspec
        return (imspec,)

    def preppipe_char_tremble(imspec, x, y, w, h, amp, period, duration):
        x, y, w, h = int(x), int(y), int(w), int(h)
        base = renpy.store.screen2d_abs(x, y, w, h)
        amp = _preppipe_coerce_float(amp)
        period = max(0.04, _preppipe_coerce_float(period))
        duration = _preppipe_coerce_float(duration)
        k = (_preppipe_char_fx_key(imspec), x, y, w, h)
        if duration < 0:
            tr = renpy.store.preppipe_at_char_tremble_loop(amp, period)
            renpy.show(imspec, at_list=[base, tr])
            renpy.store.preppipe_char_sustained_fx.add(k)
        else:
            dur = max(period, duration)
            n = max(1, int(dur / period))
            halfp = max(0.001, period / 2.0)
            tr = renpy.store.preppipe_at_char_tremble_cycles(amp, halfp, n)
            renpy.show(imspec, at_list=[base, tr])
            renpy.pause(float(n * period))
            renpy.show(imspec, at_list=[base])
            renpy.store.preppipe_char_sustained_fx.discard(k)

    def preppipe_end_char_effect(imspec, x, y, w, h):
        x, y, w, h = int(x), int(y), int(w), int(h)
        base = renpy.store.screen2d_abs(x, y, w, h)
        k = (_preppipe_char_fx_key(imspec), x, y, w, h)
        renpy.store.preppipe_char_sustained_fx.discard(k)
        renpy.show(imspec, at_list=[base])

    def preppipe_end_scene_effect():
        """结束挂在 master 层上的场景滤镜（show_layer_at）、全屏天气 screen 及预留的持续特效。"""
        preppipe_weather_stop()
        if getattr(renpy.store, "preppipe_scene_layer_filter_active", False):
            hla = getattr(renpy, "hide_layer_at", None)
            if hla is not None:
                hla(layer="master")
            sla = getattr(renpy, "show_layer_at", None)
            if sla is not None:
                sla([renpy.store.preppipe_master_layer_reset], layer="master")
            renpy.store.preppipe_scene_layer_filter_active = False
            renpy.store._preppipe_scene_filter_snapshot = None

    def _preppipe_move_tr(sx, sy, ex, ey, d, sty):
        sx, sy, ex, ey = int(sx), int(sy), int(ex), int(ey)
        d = _preppipe_coerce_float(d)
        e = (sty or "linear").strip().lower()
        if e == "ease":
            return renpy.store.preppipe_move_ease(sx, sy, ex, ey, d)
        if e == "easein":
            return renpy.store.preppipe_move_easein(sx, sy, ex, ey, d)
        if e == "easeout":
            return renpy.store.preppipe_move_easeout(sx, sy, ex, ey, d)
        return renpy.store.preppipe_move_lin(sx, sy, ex, ey, d)

    def preppipe_char_sprite_anim(imspec, x, y, w, h, kind, duration, n1, n2, n3, n4, style):
        x, y, w, h = int(x), int(y), int(w), int(h)
        base = renpy.store.screen2d_abs(x, y, w, h)
        k = (kind or "").strip().lower()
        d = _preppipe_coerce_float(duration)
        sty = (style or "linear").strip().lower()
        n1 = _preppipe_coerce_float(n1)
        n2 = _preppipe_coerce_float(n2)
        n3 = _preppipe_coerce_float(n3)
        n4 = _preppipe_coerce_float(n4)
        sw = float(renpy.config.screen_width)
        sh = float(renpy.config.screen_height)
        if k == "bounce":
            cnt = int(max(1, n2))
            hpx = n1 * sh
            tr = _preppipe_bounce_transform(d, hpx, cnt)
            renpy.show(imspec, at_list=[base, tr])
            renpy.pause(d)
            renpy.show(imspec, at_list=[base])
        elif k == "move":
            ex = int(round(n1 * sw))
            ey = int(round(n2 * sh))
            tr = _preppipe_move_tr(x, y, ex, ey, d, sty)
            renpy.show(imspec, at_list=[base, tr])
            renpy.pause(d)
        elif k == "scale":
            tr = renpy.store.preppipe_at_scale_to(n1, d, 0.5, 0.5)
            renpy.show(imspec, at_list=[base, tr])
            renpy.pause(d)
            renpy.show(imspec, at_list=[base])
        elif k == "rotate":
            tr = renpy.store.preppipe_rotate_to(n1, d, 0.5, 0.5)
            renpy.show(imspec, at_list=[base, tr])
            renpy.pause(d)
            renpy.show(imspec, at_list=[base])

init offset = -1

screen preppipe_error_screen(who, what):
  modal False
  zorder 1
  window id "window":
    xpos 0.6
    ypos 0.2
    text what id "what"


init offset = 0

define preppipe_error_sayer = Character("PrepPipe Error", who_color="#ff0000", what_color="#ff0000", interact=False, mode="screen", screen="preppipe_error_screen")
define preppipe_error_sayer_en = preppipe_error_sayer
define preppipe_error_sayer_zh_cn = Character("语涵编译器错误", kind=preppipe_error_sayer)
define preppipe_error_sayer_zh_hk = Character("語涵編譯器錯誤", kind=preppipe_error_sayer)

transform screen2d_abs(x,y,w,h):
  pos (x,y)
  xysize (w, h)

transform screen2d_rel(xr,yr,w,h):
  pos (x,y)
  xysize (w, h)

label __preppipe_ending__(ending_name=''):
  $ MainMenu(confirm=False)