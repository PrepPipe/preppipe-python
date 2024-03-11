# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# 语涵编译器需要一些内嵌的素材，这些素材需要与程序本体一起分发。
# 但是部分素材的体积较大，在分发时不适合直接放在程序包中。
# 为了解决这个问题，我们使用了一种类似于工具的注册机制，将素材的处理方法注册到主程序中。
# 该文件定义支持自动注册素材处理类的修饰符
# 详细说明请见 AssetManager 类的文档

# 注册的类应该有以下成员：
# 1.  一个静态方法 create_from_asset_archive(path : str) -> AssetClass
#     该方法用于从素材包中创建一个素材处理类的实例
# 2.  一个静态方法 build_asset_archive(destpath : str, **kwargs) -> None
#     该方法用于构建一个素材包，kwargs 可以是任意的构建参数，这些参数会保存在 AssetManager 的 Manifest 中
# 3.  一个成员函数 dump_asset_info_json(self) -> dict
#     该方法用于将素材的信息导出为一个 JSON 对象，将作为 AssetManager 的 dump 输出的一部分

_registered_asset_classes : dict[str, type] = {}

def AssetClassDecl(name : str): # pylint: disable=invalid-name
  def decorator(cls):
    assert name not in _registered_asset_classes, f"Duplicate asset class name {name}"
    # 确认该类有一个叫 create_from_asset_archive(path : str) 的静态方法
    assert hasattr(cls, "create_from_asset_archive"), f"Asset class {name} must have a static method create_from_asset_archive(path : str)"
    # 确认该类有一个叫 build_asset_archive(destpath : str, **kwargs) 的静态方法
    assert hasattr(cls, "build_asset_archive"), f"Asset class {name} must have a static method build_asset_archive(destpath : str, **kwargs)"
    # 确认该类有一个叫 dump_asset_info_json(self) 的成员方法
    assert hasattr(cls, "dump_asset_info_json"), f"Asset class {name} must have a member method dump_asset_info_json(self)"
    _registered_asset_classes[name] = cls
    return cls
  return decorator
