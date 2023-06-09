# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

import sys
import inspect
import dataclasses
import typing
import types
import collections
import collections.abc
import decimal

from . import irbase

_FIELDS = "_irop_dataclass_fields_"
_PARAMS = "_irop_dataclass_params_"
_HELPER = "_irop_dataclass_helper_"
_POST_INIT_NAME = "_custom_postinit_"

# pylint: disable=invalid-name,too-few-public-methods
class _MISSING_TYPE:
  pass

MISSING = _MISSING_TYPE()

@dataclasses.dataclass(slots=True, kw_only=True)
class OpField:
  # filled after construction
  name : str = MISSING # type: ignore
  # if we have
  # _test_operand : OpOperand[IntLiteral]
  # then base_type is OpOperand, and value_annotation is IntLiteral
  base_type : type = MISSING # type: ignore
  value_annotation : type | None = MISSING # type: ignore
  value_annotation_params : tuple[type,...] | None = MISSING # type: ignore

  # either specified or filled afterwards
  # name of operand / region, as well as accessor (e.g., "XXX" in "get_XXX()")
  lookup_name : str = MISSING  # type: ignore
  stored : bool = True # Whether this field is backed in storage (which means no save/restore/copy, and no setter/getter)

  # field-specific info
  # fields for OpOperand
  default : typing.Any = MISSING # type: ignore
  default_factory : typing.Callable = MISSING # type: ignore
  # fields for OpResult
  res_valuetype : type | None = MISSING # type: ignore
  res_gettypefrom : str | None = MISSING # type: ignore
  # fields for Region
  r_create_entry_block : bool = MISSING # type: ignore
  # fields for block
  # if specified, "lookup_name" is the name of this block and this block is created in the region specified by this name
  b_parent : str | None = MISSING # type: ignore

# NOTE: the return types are only to make the type checker happy when we use them on dataop field declarations

def operand_field(*, lookup_name = MISSING, default=MISSING, default_factory=MISSING) -> irbase.OpOperand:
  return OpField(lookup_name=lookup_name, base_type=irbase.OpOperand, default=default, default_factory=default_factory) # type: ignore

def result_field(*, lookup_name = MISSING, valuetype : type = MISSING, gettypefrom : str = MISSING) -> irbase.OpResult:
  # gettypefrom: the name of an OpOperand field that determines the type of this result
  return OpField(lookup_name=lookup_name, base_type=irbase.OpResult, res_valuetype=valuetype, res_gettypefrom=gettypefrom) # type: ignore

def region_field(*, lookup_name = MISSING, create_entry_block : bool = False) -> irbase.Region:
  return OpField(lookup_name=lookup_name, base_type=irbase.Region, r_create_entry_block=create_entry_block) # type: ignore

def symtable_field(*, lookup_name = MISSING) -> irbase.SymbolTableRegion:
  return OpField(lookup_name=lookup_name, base_type=irbase.SymbolTableRegion,) # type: ignore

def block_field(*, lookup_name = MISSING, parent = MISSING) -> irbase.Block:
  return OpField(lookup_name=lookup_name, base_type=irbase.Block, b_parent = parent) # type: ignore

_T = typing.TypeVar('_T')
def temp_field(*, default : _T =MISSING, default_factory=MISSING) -> _T:
  return OpField(stored=False, default=default, default_factory=default_factory) # type: ignore

_OperationVT = typing.TypeVar('_OperationVT', bound=irbase.Operation)
def IROperationDataclassWithValue(vty : type):
  def wrap(cls : type[_OperationVT]) -> type[_OperationVT]:
    return _process_class(cls, vty)
  return wrap

def IROperationDataclass(cls : type[_OperationVT]) -> type[_OperationVT]:
  return _process_class(cls, None)

# ==========================================================
# implementation details below
# ==========================================================

class _DataOpHelper:
  instcls : type
  def __init__(self, instcls : type) -> None:
    self.instcls = instcls

  # pylint: disable=protected-access,too-many-branches
  def help_construct_init(self, inst : irbase.Operation, **kwargs):
    assert isinstance(inst, irbase.Operation)
    if isinstance(inst, irbase.Value):
      if 'ty' not in kwargs:
        vty = getattr(type(inst), _PARAMS)["vty"]
        assert issubclass(vty, irbase.StatelessType)
        kwargs['ty'] = vty.get(kwargs['context'])
    super(self.instcls, inst).construct_init(**kwargs)
    cls_fields : typing.OrderedDict[str, OpField] = getattr(self.instcls, _FIELDS)
    for name, f in cls_fields.items():
      assert f.name == name
      if not f.stored:
        if f.default is MISSING and f.default_factory is MISSING:
          value = kwargs[f.name]
        else:
          value = f.default if f.default is not MISSING else f.default_factory()
        object.__setattr__(inst, name, value)
        continue
      match f.base_type:
        case irbase.OpOperand:
          if f.name in kwargs:
            value = kwargs[f.name]
          else:
            assert f.default_factory is MISSING
            value = f.default if f.default is not MISSING else None
          # replace the value by the literal type
          # if the value is an iterable that is not a string, we loop over them and handle each one
          def convert_value(v) -> irbase.Value | None:
            if v is not None and not isinstance(v, irbase.Value):
              if converted := irbase.convert_literal(v, inst.context, f.value_annotation, f.value_annotation_params):
                v = converted
              else:
                raise RuntimeError("Unexpected initializer value type")
            if v is not None:
              assert isinstance(v, irbase.Value)
            return v
          if isinstance(value, collections.abc.Iterable) and not isinstance(value, str):
            initializer = []
            for v in value:
              if v is not None:
                if converted := convert_value(v):
                  initializer.append(converted)
            value = inst._add_operand_with_value(f.lookup_name, initializer)
          else:
            initializer = convert_value(value)
            value = inst._add_operand_with_value(f.lookup_name, initializer)
        case irbase.OpResult:
          if f.name in kwargs:
            vty = kwargs[f.name]
            assert isinstance(vty, irbase.ValueType)
          else:
            vty = None
            if f.res_gettypefrom is not None:
              if curvalue := inst.get_operand_inst(f.res_gettypefrom).try_get_value():
                vty = curvalue.valuetype
            if vty is None and f.res_valuetype is not None:
              assert issubclass(f.res_valuetype, irbase.StatelessType)
              vty = f.res_valuetype.get(ctx=inst.context)
            if vty is None:
              raise RuntimeError("Missing value type for " + f.name + " (either specify in construction or in field declaration)")
          value = inst._add_result(f.lookup_name, vty)
        case irbase.SymbolTableRegion:
          value = inst._add_symbol_table(f.lookup_name)
        case irbase.Region:
          value = inst._add_region(f.lookup_name)
          if f.r_create_entry_block:
            value.create_block()
        case irbase.Block:
          if f.b_parent is None:
            value = inst._add_region(f.lookup_name).create_block()
          else:
            value = inst.get_or_create_region(f.b_parent).create_block(f.lookup_name)
        case _:
          raise RuntimeError("Unexpected member type")
      object.__setattr__(inst, name, value)

  def help_post_init(self, inst : irbase.Operation):
    super(self.instcls, inst).post_init()
    cls_fields : typing.OrderedDict[str, OpField] = getattr(self.instcls, _FIELDS)
    for f in cls_fields.values():
      value = None
      if f.default is not MISSING:
        value = f.default
      elif f.default_factory is not MISSING:
        value = (f.default_factory)()
      else:
        match f.base_type:
          # we have to use the dot '.' here, otherwise the name (e.g., "OpOperand") will be treated as dest variable
          # https://stackoverflow.com/questions/71441761/how-to-use-match-case-with-a-class-type
          case irbase.OpOperand:
            value = inst.get_operand_inst(f.lookup_name)
          case irbase.OpResult:
            value = inst.get_result(f.lookup_name)
          case irbase.Region:
            value = inst.get_region(f.lookup_name)
          case irbase.SymbolTableRegion:
            value = inst.get_symbol_table(f.lookup_name)
          case irbase.Block:
            if f.b_parent is None:
              value = inst.get_region(f.lookup_name).entry_block
            else:
              for b in inst.get_region(f.b_parent).blocks:
                if b.name == f.lookup_name:
                  value = b
                  break
              if value is None:
                raise RuntimeError("Cannot find block \"" + f.lookup_name + "\" in region \"" + f.b_parent + '"')
          case _:
            raise RuntimeError("Cannot initialize field")
      super(self.instcls, inst).__setattr__(f.name, value)
    if hasattr(inst, _POST_INIT_NAME):
      getattr(inst, _POST_INIT_NAME)()

  def help_setattr(self, inst : irbase.Operation, name : str, value : typing.Any):
    # check if any field is being written
    cls_fields : typing.OrderedDict[str, OpField] = getattr(self.instcls, _FIELDS)
    if name in cls_fields:
      f = cls_fields[name]
      if f.stored:
        raise AttributeError("Cannot assign to dataop member \"" + name + '"')
    return super(self.instcls, inst).__setattr__(name, value)

def _get_fixed_value_type(cls):
  return getattr(cls, _PARAMS)["vty"]

def _process_class(cls : type[_OperationVT], vty : type | None) -> type[_OperationVT]:
  # reference: _process_class() in cpython/Lib/dataclasses.py
  # https://github.com/python/cpython/blob/6d97e521169b07851cbbf7fccbf9bef3f41e3ce0/Lib/dataclasses.py#L898
  # it is hard to get dynamically added members working with auto-completion
  # therefore, besides construct_init() and post_init(), we only create getters with the same name as the declared fields
  assert issubclass(cls, irbase.Operation)

  if vty is not None:
    if not issubclass(cls, irbase.Value):
      raise RuntimeError('class ' + cls.__name__ + " annotated with @IROperationDataclassWithValue must inherit from Value")
    if not issubclass(vty, irbase.StatelessType):
      raise RuntimeError("Only stateless type can be used for op value (value type passed in: " + vty.__name__ + '"')
    setattr(cls, 'get_fixed_value_type', classmethod(_get_fixed_value_type))
  else:
    # We may have subclasses proving value type during construction
    pass
    #if issubclass(cls, irbase.Value):
    #  raise RuntimeError("Subclass of Value must provide the value type")

  for special_methods in ('construct_init', 'post_init', '__setattr__'):
    if special_methods in cls.__dict__:
      raise RuntimeError(cls.__name__ + " should not provide custom " + special_methods + "()")

  helper = _DataOpHelper(cls)
  setattr(cls, _PARAMS, {"vty": vty})
  setattr(cls, _HELPER, helper)
  setattr(cls, 'construct_init',  lambda inst, __DATAOP_HELPER__=helper, **kwargs     : __DATAOP_HELPER__.help_construct_init(inst, **kwargs))
  setattr(cls, 'post_init',       lambda inst, __DATAOP_HELPER__=helper               : __DATAOP_HELPER__.help_post_init(inst))
  setattr(cls, '__setattr__',     lambda inst, name, value, __DATAOP_HELPER__=helper  : __DATAOP_HELPER__.help_setattr(inst, name, value))

  if cls.__module__ in sys.modules:
    globals = sys.modules[cls.__module__].__dict__
  else:
    # Theoretically this can happen if someone writes
    # a custom string to cls.__module__.  In which case
    # such dataclass won't be fully introspectable
    # (w.r.t. typing.get_type_hints) but will still function
    # correctly.
    globals = {}

  cls_annotations = inspect.get_annotations(cls, globals=globals, eval_str=True)
  cls_fields : collections.OrderedDict[str, OpField] = collections.OrderedDict()

  # for checking duplicated regions
  region_dict : dict[str, str] = {}

  for name, annotation in cls_annotations.items():
    # make sure there is no name conflict
    if hasattr(irbase.Operation, name):
      raise RuntimeError("cannot override Operation's existing attribute \"" + name + '"')
    default = getattr(cls, name, MISSING)
    if isinstance(default, types.MemberDescriptorType):
      # This is a field in __slots__, so it has no default value.
      # (Copied from Lib/dataclasses.py, should not happen but just in case)
      default = MISSING
    # analyze the types
    base_type = annotation
    value_annotation = None
    value_annotation_params = None
    if isinstance(annotation, (types.GenericAlias, typing._GenericAlias)):
      if len(annotation.__args__) != 1:
        raise RuntimeError("Expecting exactly one argument for types.GenericAlias (did you specify more than one type in the square bracket [] ?)")
      base_type = annotation.__origin__
      value_annotation = annotation.__args__[0]
      if base_type is typing.ClassVar:
        # classvar annotations are not instance members and we exclude them
        continue
    assert isinstance(base_type, type)
    if value_annotation is not None:
      if not isinstance(value_annotation, type):
        assert isinstance(value_annotation, (types.GenericAlias, typing._GenericAlias))
        value_annotation_params = value_annotation.__args__
        value_annotation = value_annotation.__origin__
        assert value_annotation is irbase.EnumLiteral
    if isinstance(default, OpField):
      f = default
    else:
      match base_type:
        case irbase.OpOperand:
          f = operand_field(default=default)
        case irbase.OpResult:
          raise RuntimeError("OpResult requires field declaration")
        case irbase.Region:
          if default is not MISSING:
            raise RuntimeError("Please do not set initializer for " + str(base_type))
          f = region_field()
        case irbase.SymbolTableRegion:
          if default is not MISSING:
            raise RuntimeError("Please do not set initializer for " + str(base_type))
          f = symtable_field()
        case irbase.Block:
          if default is not MISSING:
            raise RuntimeError("Please do not set initializer for " + str(base_type))
          f = block_field()
        case _:
          raise RuntimeError("Invalid type for operation dataclass")
    assert isinstance(f, OpField)
    f.name = name
    if f.stored:
      if f.base_type is not base_type:
        raise RuntimeError("Mismatching field specifier: specifying " + type(base_type).__name__ + " field as type " + type(f.base_type).__name__)
    else:
      f.base_type = base_type
    f.value_annotation = value_annotation
    f.value_annotation_params = value_annotation_params
    if f.lookup_name is MISSING:
      f.lookup_name = name
    if len(f.lookup_name) == 0:
      raise RuntimeError("lookup name cannot be empty for field \"" + name + '"')
    cls_fields[f.name] = f

    # early exit for non-state data (e.g., cache) that does not go to storage
    if not f.stored:
      continue

    # now do the field validation
    def check_dup_region_name(lookup_name : str, field_name : str):
      if lookup_name in region_dict:
        raise RuntimeError("Field \"" + field_name + "\": cannot use lookup name \"" + lookup_name + "\" because there is already a region with given name created by field \"" + region_dict[lookup_name] + '"')
      region_dict[lookup_name] = field_name

    match base_type:
      case irbase.OpOperand:
        # if a default value is provided, check whether the types match
        if f.default is not MISSING and f.default is not None:
          if not irbase.convert_literal(value=f.default, ctx=None, type_hint=f.value_annotation, type_hint_params=f.value_annotation_params):
            raise RuntimeError("Field \"" + f.name + "\": initializer " + str(f.default) + " cannot be converted to " + f.value_annotation.__name__ if f.value_annotation is not None else "Value")
      case irbase.OpResult:
        if f.res_gettypefrom is not MISSING:
          assert isinstance(f.res_gettypefrom, str)
          if not f.res_gettypefrom in cls_fields:
            raise RuntimeError("Field \"" + f.name + "\": gettypefrom \"" + f.res_gettypefrom + "\" must be declared before this result field")
          src = cls_fields[f.res_gettypefrom]
          if src.base_type is not irbase.OpOperand:
            raise RuntimeError("Field \"" + f.name + "\": gettypefrom \"" + f.res_gettypefrom + "\" must be an OpOperand field")
        else:
          f.res_gettypefrom = None
        if f.res_valuetype is not MISSING:
          assert isinstance(f.res_valuetype, type)
          if not issubclass(f.res_valuetype, irbase.StatelessType):
            raise RuntimeError("Field \"" + f.name + "\": cannot use type " + f.res_valuetype.__name__ + " because it is not stateless")
        else:
          f.res_valuetype = None
        if f.res_gettypefrom is None and f.res_valuetype is None:
          raise RuntimeError("Field \"" + f.name + "\": must specify either valuetype or gettypefrom")
      case irbase.Region:
        assert isinstance(f.r_create_entry_block, bool)
        check_dup_region_name(f.lookup_name, f.name)
      case irbase.SymbolTableRegion:
        check_dup_region_name(f.lookup_name, f.name)
      case irbase.Block:
        if f.b_parent is MISSING:
          f.b_parent = None
          check_dup_region_name(f.lookup_name, f.name)
        else:
          assert isinstance(f.b_parent, str)
          check_dup_region_name(f.b_parent, f.name)
      case _:
        raise RuntimeError("Invalid type for operation dataclass")
    # Done for this field
  # register the fields and we are done here
  setattr(cls, _FIELDS, cls_fields)
  return cls

# @IROperationDataclass()
class MyOp(irbase.Operation):
  _value_operand : irbase.OpOperand
  _cnt_operand : irbase.OpOperand[irbase.IntLiteral]
  _body_region : irbase.Region
  _lut_region : irbase.SymbolTableRegion

  def dump(self):
    print("Dump is called!")


#@IROperationDataclass(vty = VoidType)
class MyValue(irbase.Operation, irbase.Value):
  pass