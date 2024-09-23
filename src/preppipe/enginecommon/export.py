# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from .ast import *
from ..exportcache import CacheableOperationSymbol

# export functions for engine common
def export_assets_and_cacheable(m : BackendProjectModelBase, out_path : str):
  for file in m.assets():
    assetdata = file.get_asset_value()
    assert isinstance(assetdata, AssetData)
    filepath = os.path.join(out_path, file.name)
    parentdir = os.path.dirname(filepath)
    os.makedirs(parentdir, exist_ok=True)
    assetdata.export(filepath)
  if len(m._cacheable_export_region) > 0:
    CacheableOperationSymbol.run_export_all(m._cacheable_export_region, out_path)
