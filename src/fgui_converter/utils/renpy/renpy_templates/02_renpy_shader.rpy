init python:

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
