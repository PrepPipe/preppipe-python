# SPDX-FileCopyrightText: 2024 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import enum

from preppipe.irbase import AssetData, Literal, ValueType

from .irbase import *
from .language import TranslationDomain

# 此文件定义了关于算术、逻辑表达式的类型
# 我们需要这些来实现各类表达式，或者在部分输出（如位置坐标等）用表达式来代替一些字面值，以便于用户理解、修改
# (目前还没有用上。。)

@IRWrappedStatelessClassJsonName("vardecl_ty_e")
class VariableDeclType(enum.Enum):
  INT = enum.auto()
  FLOAT = enum.auto()
  BOOL = enum.auto()

class VariableRefExpr(LiteralExpr):
  # 该表达式是一个变量的引用
  # 参数1是变量名，参数2是变量类型
  # 为了使所有表达式都能作为 LiteralExpr，该变量绑至哪个变量由环境决定

  def construct_init(self, *, context : Context, value_tuple: tuple[StringLiteral, EnumLiteral[VariableDeclType]], **kwargs) -> None:
    varname, varty = value_tuple
    assert isinstance(varname, StringLiteral) and isinstance(varty, EnumLiteral) and isinstance(varty.value, VariableDeclType)
    match varty.value:
      case VariableDeclType.INT:
        ty = IntType.get(context)
      case VariableDeclType.FLOAT:
        ty = FloatType.get(context)
      case VariableDeclType.BOOL:
        ty = BoolType.get(context)
      case _:
        raise PPInternalError("Unreachable")
    return super().construct_init(ty=ty, value_tuple=value_tuple, **kwargs)

  @staticmethod
  def get(context : Context, varname : StringLiteral | str, ty : type[ValueType]) -> VariableRefExpr:
    if isinstance(varname, str):
      varname = StringLiteral.get(varname, context=context)
    if isinstance(ty, IntType):
      varty = EnumLiteral.get(context=context, value=VariableDeclType.INT)
    elif isinstance(ty, FloatType):
      varty = EnumLiteral.get(context=context, value=VariableDeclType.FLOAT)
    elif isinstance(ty, BoolType):
      varty = EnumLiteral.get(context=context, value=VariableDeclType.BOOL)
    else:
      raise PPInternalError("Unreachable")
    return VariableRefExpr._get_literalexpr_impl((varname, varty), context)

@IRWrappedStatelessClassJsonName("op_e")
class ArithmeticLogicOperationType(enum.Enum):
  # 算术、逻辑表达式中的运算类型
  ADD = enum.auto()
  SUB = enum.auto()
  MUL = enum.auto()
  DIV = enum.auto()
  #MOD = enum.auto()
  #POW = enum.auto()
  NEG = enum.auto()
  LT = enum.auto()
  GT = enum.auto()
  LE = enum.auto()
  GE = enum.auto()
  EQ = enum.auto()
  NE = enum.auto()
  AND = enum.auto()
  OR = enum.auto()
  NOT = enum.auto()
  #XOR = enum.auto()

class OperationExpr(LiteralExpr):
  # 算术、逻辑表达式
  # 参数1是运算符，参数2是左操作数，参数3是右操作数（如果有的话）
  # 为了使所有表达式都能作为 LiteralExpr，该运算的结果由环境决定

  def construct_init(self, *,
                     context : Context,
                     value_tuple: tuple[EnumLiteral[ArithmeticLogicOperationType], LiteralExpr | Literal]
                                | tuple[EnumLiteral[ArithmeticLogicOperationType], LiteralExpr | Literal, LiteralExpr | Literal],
                     **kwargs) -> None:
    op = value_tuple[0]
    lhs = value_tuple[1]
    rhs = value_tuple[2] if len(value_tuple) > 2 else None # type: ignore
    assert isinstance(op, EnumLiteral) and isinstance(op.value, ArithmeticLogicOperationType)
    # 检查类型并决定该表达式的类型
    lhsTy = lhs.valuetype
    commonTy = lhsTy
    if rhs is not None:
      rhsTy = rhs.valuetype
      if lhsTy != rhsTy:
        # 如果左右操作数类型不同，那么我们可能需要进行类型转换
        # 唯一允许的情况是一个操作数是整数，另一个是浮点数
        # 其他情况均为错误
        if isinstance(lhsTy, IntType) and isinstance(rhsTy, FloatType):
          commonTy = rhsTy
        elif isinstance(lhsTy, FloatType) and isinstance(rhsTy, IntType):
          commonTy = lhsTy
        else:
          raise PPInternalError("Type mismatch")
    match op.value:
      case ArithmeticLogicOperationType.ADD | ArithmeticLogicOperationType.SUB | ArithmeticLogicOperationType.MUL | ArithmeticLogicOperationType.DIV:
        assert isinstance(commonTy, (IntType, FloatType))
        assert rhs is not None
        ty = commonTy
      case ArithmeticLogicOperationType.NEG:
        assert isinstance(commonTy, (IntType, FloatType))
        assert rhs is None
        ty = commonTy
      case ArithmeticLogicOperationType.LT | ArithmeticLogicOperationType.GT | ArithmeticLogicOperationType.LE | ArithmeticLogicOperationType.GE:
        assert isinstance(commonTy, (IntType, FloatType))
        assert rhs is not None
        ty = BoolType.get(context)
      case ArithmeticLogicOperationType.EQ | ArithmeticLogicOperationType.NE:
        assert isinstance(commonTy, (IntType, FloatType, BoolType))
        assert rhs is not None
        ty = BoolType.get(context)
      case ArithmeticLogicOperationType.AND, ArithmeticLogicOperationType.OR:
        assert isinstance(commonTy, BoolType)
        assert rhs is not None
        ty = commonTy
      case ArithmeticLogicOperationType.NOT:
        assert isinstance(commonTy, BoolType)
        assert rhs is None
        ty = commonTy
      case _:
        raise PPInternalError("Unreachable")
    return super().construct_init(ty=ty, value_tuple=value_tuple, **kwargs)

  @staticmethod
  def get_add(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.ADD), lhs, rhs), context)

  @staticmethod
  def get_sub(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.SUB), lhs, rhs), context)

  @staticmethod
  def get_mul(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.MUL), lhs, rhs), context)

  @staticmethod
  def get_div(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.DIV), lhs, rhs), context)

  @staticmethod
  def get_neg(context : Context, lhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.NEG), lhs), context)

  @staticmethod
  def get_lt(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.LT), lhs, rhs), context)

  @staticmethod
  def get_gt(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.GT), lhs, rhs), context)

  @staticmethod
  def get_le(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.LE), lhs, rhs), context)

  @staticmethod
  def get_ge(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.GE), lhs, rhs), context)

  @staticmethod
  def get_eq(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.EQ), lhs, rhs), context)

  @staticmethod
  def get_ne(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.NE), lhs, rhs), context)

  @staticmethod
  def get_and(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.AND), lhs, rhs), context)

  @staticmethod
  def get_or(context : Context, lhs : LiteralExpr | Literal, rhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.OR), lhs, rhs), context)

  @staticmethod
  def get_not(context : Context, lhs : LiteralExpr | Literal) -> OperationExpr:
    return OperationExpr._get_literalexpr_impl((EnumLiteral.get(context=context, value=ArithmeticLogicOperationType.NOT), lhs), context)

class ValueExpr(LiteralExpr):
  pass