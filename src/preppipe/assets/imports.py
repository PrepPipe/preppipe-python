# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 此文件只包含对所有带了 @AssetClassDecl 修饰符的类的引用，以便在其他地方引用这些类时不需要直接引用这些类的模块。
# 该文件不应该包含任何其他代码。

from .assetmanager import AssetManager
from ..util.imagepack import ImagePack
