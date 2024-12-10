# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import typing
from ..irbase import *
from .. import irdataop
from ..language import TranslationDomain, Translatable
from ..util.imagepackexportop import ImagePackExportOpSymbol

TR_EngineCommon = TranslationDomain("enginecommon")

@irdataop.IROperationDataclass
class BackendASTNodeBase(Operation):
  def accept(self, visitor):
    visitfuncname = "visit" + self.__class__.__name__
    if hasattr(visitor, visitfuncname):
      return getattr(visitor, visitfuncname)(self)
    return visitor.visitChildren(self)

class BackendASTVisitorBase:
  # 如果我们把 ErrorOp 导出为发言提示的话，这是发言者的名称
  tr_error = TR_EngineCommon.tr("pp_error",
    en="PrepPipe Error",
    zh_cn="语涵编译器错误",
    zh_hk="語涵編譯器錯誤",
  )

  def visitChildren(self, v : Operation):
    for r in v.regions:
      for b in r.blocks:
        for op in b.body:
          if isinstance(op, BackendASTNodeBase):
            op.accept(self)

@irdataop.IROperationDataclass
class BackendFileAssetOp(Symbol):
  ref : OpOperand # AssetData
  export_format : OpOperand[StringLiteral] # 如果非空，我们在导出时需要进行另存为

  def get_asset_value(self) -> Value:
    return self.ref.get()

  @staticmethod
  def create(context : Context, assetref : Value, path : str, export_format : StringLiteral | str | None = None, loc : Location | None = None):
    return BackendFileAssetOp(init_mode=IRObjectInitMode.CONSTRUCT, context=context, ref=assetref, export_format=export_format, name=path, loc=loc)

_ScriptFileTypeVar = typing.TypeVar('_ScriptFileTypeVar', bound='Symbol')

@irdataop.IROperationDataclass
class BackendProjectModelBase(Operation, typing.Generic[_ScriptFileTypeVar]):
  _script_region : SymbolTableRegion = irdataop.symtable_field(lookup_name="script") # _ScriptFileTypeVar
  _asset_region : SymbolTableRegion = irdataop.symtable_field(lookup_name="asset") # BackendFileAssetOp
  _cacheable_export_region : SymbolTableRegion = irdataop.symtable_field(lookup_name="cacheable_export") # ImagePackExportOpSymbol

  def get_script(self, scriptname : str) -> _ScriptFileTypeVar:
    return self._script_region.get(scriptname)

  def add_script(self, script : _ScriptFileTypeVar):
    self._script_region.add(script)

  def get_asset(self, name : str) -> BackendFileAssetOp:
    return self._asset_region.get(name)

  def add_asset(self, asset : BackendFileAssetOp):
    self._asset_region.add(asset)

  def add_cacheable_export(self, export : ImagePackExportOpSymbol):
    self._cacheable_export_region.add(export)

  def scripts(self) -> typing.Iterable[_ScriptFileTypeVar]:
    return self._script_region

  def assets(self) -> typing.Iterable[BackendFileAssetOp]:
    return self._asset_region

  def cacheable_exports(self) -> typing.Iterable[ImagePackExportOpSymbol]:
    return self._cacheable_export_region

