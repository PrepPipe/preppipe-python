###################
#滚动容器边缘虚化变换
###################

init python:

    # 根据ui.adjustment对象计算边缘虚化值
    def edge_values_for_adjustment(adj, start_edge, end_edge):
        epsilon = 0.5

        if adj is None:
            return 0.0, 0.0
        # 容器尺寸大于可视内容尺寸，不可滚动，边缘虚化为0.
        if adj.range <= epsilon:
            return 0.0, 0.0
        # 滚动到顶部或左端，单侧边缘虚化。
        if adj.value <= epsilon:
            return 0.0, end_edge
        # 滚动到中间，双侧边缘虚化。
        if adj.value > epsilon and adj.value < adj.range - epsilon:
            return start_edge, end_edge
        # 滚动到底部或右端，单侧边缘虚化。
        if adj.value >= adj.range - epsilon:
            return start_edge, 0.0

        return start_edge, end_edge

    # 使用闭包函数创建边缘虚化变换的更新函数
    def make_update_dynamic_edge_virtualization(xadj, yadj, left_edge, right_edge, top_edge, bottom_edge):
        # 更新边缘虚化的函数
        def update_dynamic_edge_virtualization(trans, st, at):
            left, right = edge_values_for_adjustment(xadj, left_edge, right_edge)
            top, bottom = edge_values_for_adjustment(yadj, top_edge, bottom_edge)
            trans.u_edge_left = left
            trans.u_edge_right = right
            trans.u_edge_top = top
            trans.u_edge_bottom = bottom
            return 0.2

        return update_dynamic_edge_virtualization

# 固定边缘虚化值的变换
transform edge_virtualization(left=0.0, right=0.0, top=0.0, bottom=0.0, softness=1.0):
    mesh True
    shader "CursedOctopus.edge_virtualization"
    u_edge_left left
    u_edge_right right
    u_edge_top top
    u_edge_bottom bottom
    u_edge_softness softness

# 可根据滚动容器的滚动位置动态计算边缘虚化值的变换
transform dynamic_edge_virtualization(xadj, yadj, left=0.0, right=0.0, top=0.0, bottom=0.0, softness=1.0):
    mesh True
    shader "CursedOctopus.edge_virtualization"
    u_edge_left left
    u_edge_right right
    u_edge_top top
    u_edge_bottom bottom
    u_edge_softness softness
    function make_update_dynamic_edge_virtualization(xadj, yadj, left, right, top, bottom)
