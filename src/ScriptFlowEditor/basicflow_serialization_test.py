# 基础流程及序列化保存测试

from ScriptFlowEditor import *

# flag变量
first_choice = FlagVariable(name='choice_1', flag_type=FlagType.BOOL, initial_value=True, comment='The 1st choice flag.')
second_choice = FlagVariable(name='choice_2', flag_type=FlagType.BOOL, initial_value=False, comment='The 2nd choice flag.')

# start，整个流程入口
start_node = StorySegment(name='start', content='This is start label.', is_ending_segment=False, id=None)

# 分支段落1
branch_seg_1 = StorySegment(name='branch_seg_1', content='This is 1st branch segment label.', is_ending_segment=False, id=None)
# 分支段落2
branch_seg_2 = StorySegment(name='branch_seg_2', content='This is 2nd branch segment label.', is_ending_segment=False, id=None)

# 结局1。从branch_seg_1跳转到该结局。
ending_1 = StorySegment(name='ending_1', content='This is ending 1.', is_ending_segment=True)
# 结局2。在second_choice为True时，从branch_seg_2跳转到该结局。
ending_2 = StorySegment(name='ending_2', content='This is ending 2.', is_ending_segment=True)
# 结局3。在first_choice为False时，从branch_seg_2跳转到该结局。
ending_3 = StorySegment(name='ending_3', content='This is ending 3.', is_ending_segment=True)

# 路径1。在start_node结尾，若first_choice为True则进入branch_seg_1。
path_1 = SegmentPath(prev_segment_id=start_node.id, next_segment_id=branch_seg_1.id, condition_expression="choice_1 == True")
# 路径2。在start_node结尾，若first_choice为False则进入branch_seg_2。
path_2 = SegmentPath(prev_segment_id=start_node.id, next_segment_id=branch_seg_2.id, condition_expression="choice_1 == False")
# 路径3。在branch_seg_1结尾，无条件进入ending_1。
path_3 = SegmentPath(prev_segment_id=branch_seg_1.id, next_segment_id=ending_1.id, condition_expression=None)
# 路径4。在branch_seg_2结尾，若second_choice为True则进入ending_2。
path_4 = SegmentPath(prev_segment_id=branch_seg_2.id, next_segment_id=ending_2.id, condition_expression="choice_2 == True")
# 路径5。在branch_seg_2结尾，若second_choice为False则进入ending_3。
path_5 = SegmentPath(prev_segment_id=branch_seg_2.id, next_segment_id=ending_3.id, condition_expression="choice_2 == False")

flow = GameScriptFlow(name="Demo Flow", segments=[start_node, branch_seg_1, branch_seg_2, ending_1, ending_2, ending_3], paths=[path_1, path_2, path_3, path_4, path_5], flags=[first_choice, second_choice])

flow.save_as_json()
