# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

class PartialStateMatcher:
  # 当切换角色、场景状态时，状态字符串很可能不全
  # 这个类被用于将这些状态字符串补全为预先设定的完整的状态
  # 比如角色可以有如下状态：
  #   * 站姿
  #       - 正常
  #       - 开心
  #   * 侧身
  #       - 正常
  #       - 愤怒
  # 那么完整状态有 (站姿, 正常), (站姿, 开心), (侧身, 正常), (侧身, 愤怒)
  # 并且有以下切换：(原状态) + (给出的状态) --> (完整的结果状态)
  # (站姿, 正常) + (开心) --> (站姿, 开心) (仅替换最后的表情)
  # (站姿, 正常) + (正常) --> (站姿, 正常) (正确识别无变化的情况)
  # (站姿, 正常) + (侧身) --> (侧身, 正常) (默认第一项为默认状态)
  # (站姿, 开心) + (侧身) --> (侧身, 正常)
  # (站姿, 正常) + (侧身, 愤怒) --> (侧身, 愤怒)
  # (站姿, 正常) + (侧身，开心) --> 报错
  # (站姿, 开心) + (愤怒) --> 报错

  # 以后如果需要加别的、不是基于树的状态（比如戴眼镜、不戴眼镜这样二分的）可以用额外的机制

  _parent_tree : dict[str, list[tuple[str,...]]] # 对每个状态而言，它们有哪些合理的前置状态
  _default_child_dict : dict[tuple[str,...], tuple[str,...]] # 如果当前状态不是子状态，这里存着它们接下来的默认状态

  def __init__(self) -> None:
    self._parent_tree = {}
    self._default_child_dict = {}

  def check_is_prefix(self, state : list[str], prefix : tuple[str, ...]) -> bool:
    if len(prefix) > len(state):
      return False
    for i in range(0, len(prefix)):
      if prefix[i] != state[i]:
        return False
    return True

  def check_is_same(self, state : list[str], prefix : tuple[str, ...]) -> bool:
    return len(state) == len(prefix) and self.check_is_prefix(state, prefix)

  def add_valid_state(self, state : tuple[str, ...]):
    for i in range(0, len(state)):
      # 首先添加子串
      substate = state[i]
      parent_prefix= state[:i]
      substate_parent = None
      if substate in self._parent_tree:
        substate_parent = self._parent_tree[substate]
      else:
        substate_parent = []
        self._parent_tree[substate] = substate_parent
      if parent_prefix not in substate_parent:
        substate_parent.append(parent_prefix)
      # 然后把默认子结点加上
      if parent_prefix not in self._default_child_dict:
        self._default_child_dict[parent_prefix] = state[i:]

  def get_default_state(self):
    curstate = ()
    if curstate in self._default_child_dict:
      curstate = self._default_child_dict[curstate]
    return curstate

  def finish_init(self):
    # 把 _parent_tree 中的所有项排序，长的在前短的在后
    for l in self._parent_tree.values():
      l.sort(key=lambda t : len(t), reverse=True)

  def find_match(self, existing_states : list[str], attached_states : list[str]) -> tuple[str] | None:
    issuccess, resultlist = self._find_match_impl(existing_states, attached_states)
    if issuccess:
      return tuple(resultlist)
    return None

  def find_match_besteffort(self, existing_states : list[str], attached_states : list[str]) -> tuple[bool, tuple[str,...]]:
    is_full_match, result = self._find_match_impl(existing_states, attached_states)
    return (is_full_match, tuple(result))

  def _find_match_impl(self, existing_states : list[str], attached_states : list[str]) -> tuple[bool, list[str]]:
    # 元组第一项是 attached_states 中的状态匹配是否全部成功，全部成功是 True, 中途有失败、结果是折中的就返回 False
    # 元组第二项是当前匹配的最好的状态
    pinned_length = -1
    cur_state = existing_states.copy()
    for newsubstate in attached_states:
      if newsubstate not in self._parent_tree:
        # 这是个没见过的状态，有可能是字打错了或是其他原因
        return (False, cur_state)
      parent_list = self._parent_tree[newsubstate]
      is_prefix_found = False
      for candidate in parent_list:
        # 忽略长度小于确定项的备选前缀
        if len(candidate) < pinned_length:
          continue
        if self.check_is_prefix(cur_state, candidate):
          pinned_length = len(candidate)
          is_prefix_found = True
          break
      if not is_prefix_found:
        # 找不到合适的前缀
        return (False, cur_state)
      # 重新检查 pinned_length 之后的所有项，如果前置条件已经不匹配了就去掉
      oldstates = cur_state[pinned_length:]
      cur_state = cur_state[:pinned_length]
      cur_state.append(newsubstate)
      pinned_length += 1
      for oldsubstate in oldstates:
        for candidate in self._parent_tree[oldsubstate]:
          if self.check_is_same(cur_state, candidate):
            cur_state.append(oldsubstate)
            break
      # 将当前状态补足到一个完整状态
      cur_state_tuple = tuple(cur_state)
      if cur_state_tuple in self._default_child_dict:
        substates = self._default_child_dict[cur_state_tuple]
        cur_state.append(*substates)
    return (True, cur_state)

def _test_main_statematcher():
  matcher = PartialStateMatcher()
  matcher.add_valid_state(('站姿', '正常'))
  matcher.add_valid_state(('站姿', '开心'))
  matcher.add_valid_state(('侧身', '正常'))
  matcher.add_valid_state(('侧身', '愤怒'))
  matcher.finish_init()
  curstate = ['站姿', '正常']
  curstate2 = ['站姿', '开心']
  if (res := matcher.find_match(curstate, ['开心'])) != ('站姿', '开心'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate, ['正常'])) != ('站姿', '正常'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate, ['侧身'])) != ('侧身', '正常'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate2, ['侧身'])) != ('侧身', '正常'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate, ['侧身','愤怒'])) != ('侧身','愤怒'):
    raise PPAssertionError
  if (res := matcher.find_match(curstate, ['侧身','开心'])) is not None:
    raise PPAssertionError
  if (res := matcher.find_match(curstate2, ['愤怒'])) is not None:
    raise PPAssertionError

if __name__ == "__main__":
  _test_main_statematcher()
