# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import editdistance
import typing

class TypoSuggestion:
  _input : str # the input string that is likely wrong
  _min_dist : typing.Any
  _best_candidates : typing.List[str]
  
  def __init__(self, input : str) -> None:
    self._input = input
    self._min_dist = None
    self._best_candidates = []
  
  def _test(self, candidate : str) -> None:
    dist = editdistance.eval(candidate, self._input)
    if self._min_dist is None or self._min_dist > dist:
      self._best_candidates = [candidate]
      self._min_dist = dist
    elif self._min_dist == dist:
      if candidate not in self._best_candidates:
        self._best_candidates.append(candidate)
  
  def add_candidate(self, candidate) -> None:
    if isinstance(candidate, str):
      self._test(candidate)
    else:
      for item in candidate:
        self.add_candidate(item)
  
  def get_result(self) -> typing.List[str]:
    return self._best_candidates
