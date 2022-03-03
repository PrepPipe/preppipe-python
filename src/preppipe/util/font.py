# SPDX-FileCopyrightText: 2022 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import numpy as np
import typing

class FontSizeConverter:
  # latex default font sizes (default = 10pt)
  _default_font_size_dict : typing.ClassVar[typing.Dict[int, float]] = {
    -4: 5,  # \tiny
    -3: 7,  # \scriptsize
    -2: 8,  # \footnotesize
    -1: 9,  # \small
     0: 10, # \normalsize
     1: 12, # \large
     2: 14.4,  # \Large
     3: 17.28, # \LARGE
     4: 20.74, # \huge
     5: 24.88  # \Huge
  }
  _poly : np.polynomial.Polynomial
  
  def __init__(self, baseSize = 10) -> None:
    # step 1: create lists of x and y for later polynomial fitting
    xData = []
    yData = []
    if (baseSize != FontSizeConverter._default_font_size_dict[0]):
      # need scaling
      ratio = baseSize / FontSizeConverter._default_font_size_dict[0];
      for k, v in FontSizeConverter._default_font_size_dict.items():
        xData.append(k)
        yData.append(v * ratio)
    else:
      for k, v in FontSizeConverter._default_font_size_dict.items():
        xData.append(k)
        yData.append(v)
      
    self._poly = np.polynomial.polynomial.Polynomial.fit(xData, yData, deg=3).convert();
  
  def getPointsFromSize(self, size : int) -> float:
    result = np.polynomial.polynomial.polyval(size, self._poly.coef);
    # minimum value for points are 1.0
    return max(result, 1.0)
  
  def getSizeFromPoints(self, points : float) -> int:
    coef = self._poly.coef.copy()
    coef[0] -= points # c0 is at [0]
    roots = np.polynomial.polynomial.polyroots(coef)
    # find the real solution and round it
    for candidate in roots:
      if np.isreal(candidate):
        return round(candidate.real)
    # should not happen but just in case
    return 0
    