init python:

    # 圆边矩形
    renpy.register_shader("CursedOctopus.rectangle", variables="""
        uniform vec4 u_rectangle_color;
        uniform vec4 u_stroke_color;
        uniform vec2 u_model_size;
        uniform vec4 u_radius;
        uniform float u_thickness;
        attribute vec4 a_position;
        varying vec2 v_tex_coord;
    """, vertex_300="""
        v_tex_coord = a_position.xy / u_model_size;
    """,fragment_functions="""
    float roundedBoxSDF(vec2 pos, vec2 border, vec4 radius){
        vec4 r = radius;
        r.xy = (pos.x<0.0) ? radius.xz : radius.yw;
        r.x = (pos.y<0.0) ? r.x : r.y;
        vec2 dis = abs(pos) - border + vec2(r.x,r.x);
        return length(max(dis, 0.0)) + min(max(dis.x, dis.y), 0.0) - r.x;
    }
    """,fragment_300="""
        vec2 uv = v_tex_coord - vec2(0.5, 0.5);
        vec2 tex_pos = uv * u_model_size;
        float out_distance = roundedBoxSDF(tex_pos, u_model_size/2, u_radius);
        float border_alpha = (1.0 - step(0.0, out_distance));
        float in_distance = roundedBoxSDF(tex_pos, u_model_size/2-vec2(u_thickness,u_thickness), u_radius);
        float fill_alpha = (1.0 - step(0.0, in_distance));
        vec4 c1 = step(1-fill_alpha, 0) * u_rectangle_color;
        vec4 c2 = step(fill_alpha, 0) * border_alpha * u_stroke_color;
        gl_FragColor = c1 + c2;
    """)

    # 带抗锯齿的圆边矩形
    renpy.register_shader("CursedOctopus.rectangleAA", variables="""
        uniform vec4 u_rectangle_color;
        uniform vec4 u_stroke_color;
        uniform vec2 u_model_size;
        uniform vec4 u_radius;
        uniform float u_thickness;
        uniform float u_edge_softness;
        attribute vec4 a_position;
        varying vec2 v_tex_coord;
    """, vertex_300="""
        v_tex_coord = a_position.xy / u_model_size;
    """,fragment_functions="""
    float roundedBoxSDF(vec2 pos, vec2 border, vec4 radius){
        vec4 r = radius;
        r.xy = (pos.x<0.0) ? radius.xz : radius.yw;
        r.x = (pos.y<0.0) ? r.x : r.y;
        vec2 dis = abs(pos) - border + vec2(r.x,r.x);
        return length(max(dis, 0.0)) + min(max(dis.x, dis.y), 0.0) - r.x;
    }
    """,fragment_300="""
        vec2 uv = v_tex_coord - vec2(0.5, 0.5);
        vec2 tex_pos = uv * u_model_size;
        float out_distance = roundedBoxSDF(tex_pos, u_model_size/2, u_radius);
        float border_alpha = (1.0 - smoothstep(-u_edge_softness, u_edge_softness, out_distance));
        float in_distance = roundedBoxSDF(tex_pos, u_model_size/2-vec2(u_thickness,u_thickness), u_radius);
        float fill_alpha = (1.0 - smoothstep(0, u_edge_softness, in_distance));
        vec4 c1 = fill_alpha * u_rectangle_color;
        vec4 c2 = border_alpha * u_stroke_color;
        gl_FragColor = mix(c2, c1, fill_alpha);
    """)

    # 椭圆
    renpy.register_shader("CursedOctopus.ellipse", variables="""
        uniform vec4 u_ellipse_color;
        uniform vec4 u_stroke_color;
        uniform vec2 u_model_size;
        uniform float u_thickness;
        attribute vec4 a_position;
        varying vec2 v_tex_coord;
    """, vertex_300="""
        v_tex_coord = a_position.xy / u_model_size;
    """,fragment_300="""
        vec2 uv = v_tex_coord - vec2(0.5, 0.5);
        float out_distance = length(uv);
        float border_alpha = step(out_distance, 0.5);
        vec2 tex_pos = uv * u_model_size;
        float in_distance = length((abs(tex_pos+normalize(uv*u_thickness)*u_thickness))/u_model_size);
        float fill_alpha = step(in_distance, 0.5);
        vec4 c1 = step(1-fill_alpha, 0) * u_ellipse_color;
        vec4 c2 = step(fill_alpha, 0) * border_alpha * u_stroke_color;
        gl_FragColor = c1 + c2;
    """)

    # 带抗锯齿的椭圆
    renpy.register_shader("CursedOctopus.ellipseAA", variables="""
        uniform vec4 u_ellipse_color;
        uniform vec4 u_stroke_color;
        uniform vec2 u_model_size;
        uniform float u_thickness;
        uniform float u_edge_softness;
        attribute vec4 a_position;
        varying vec2 v_tex_coord;
    """, vertex_300="""
        v_tex_coord = a_position.xy / u_model_size;
    """,fragment_300="""
        vec2 uv = v_tex_coord - vec2(0.5, 0.5);
        float out_distance = length(uv);
        float border_alpha = smoothstep(out_distance-u_edge_softness, out_distance, 0.5-u_edge_softness);
        vec2 tex_pos = uv * u_model_size;
        float in_distance = length((abs(tex_pos+normalize(uv*u_thickness)*u_thickness))/u_model_size);
        float fill_alpha = smoothstep(in_distance-u_edge_softness, in_distance, 0.5-u_edge_softness);
        vec4 c1 = fill_alpha * u_ellipse_color;
        vec4 c2 = border_alpha * u_stroke_color;
        gl_FragColor = mix(c2, c1, fill_alpha);
    """)

    # 边缘虚化：按左、右、上、下四个方向的距离，边缘逐渐透明。
    renpy.register_shader("CursedOctopus.edge_virtualization",
        variables="""
            uniform sampler2D tex0;
            uniform float u_edge_left;
            uniform float u_edge_right;
            uniform float u_edge_top;
            uniform float u_edge_bottom;
            uniform float u_edge_softness;
            attribute vec2 a_tex_coord;
            varying vec2 v_tex_coord;
        """,
        vertex_300="""
            v_tex_coord = a_tex_coord;
        """,
        fragment_300="""
            vec2 uv = v_tex_coord.xy;
            vec4 color = texture2D(tex0, uv);

            float left = clamp(u_edge_left, 0.0, 0.5);
            float right = clamp(u_edge_right, 0.0, 0.5);
            float top = clamp(u_edge_top, 0.0, 0.5);
            float bottom = clamp(u_edge_bottom, 0.0, 0.5);

            float alpha = 1.0;
            float left_alpha =  left > 0.0 ? smoothstep(0.0, left, uv.x) : 1.0;
            float right_alpha =  right > 0.0 ? smoothstep(0.0, right, 1.0 - uv.x) : 1.0;
            float top_alpha =  top > 0.0 ? smoothstep(0.0, top, uv.y) : 1.0;
            float bottom_alpha =  bottom > 0.0 ? smoothstep(0.0, bottom, 1.0 - uv.y) : 1.0;
            alpha *= pow(left_alpha * right_alpha * top_alpha * bottom_alpha, u_edge_softness);

            gl_FragColor = color * alpha;
        """
    )





