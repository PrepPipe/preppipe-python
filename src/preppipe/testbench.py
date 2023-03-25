# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from .pipeline import *
from .irbase import *
from .vnmodel_v4 import *

@FrontendDecl('test-vnmodel-build', input_decl=IODecl(description='<No Input>', nargs=0), output_decl=VNModel)
class _TestVNModelBuild(TransformBase):
  def run(self) -> VNModel:
    model = VNModel.create(self.context, "TestModel")
    ns = model.add_namespace(VNNamespace.create('/', self.context.null_location))
    VNDeviceRecord.create_standard_device_tree(ns)
    narrator = VNCharacterRecord.create_narrator(self.context)
    ns.add_record(narrator)
    func = ns.add_function(VNFunction.create(self.context, "Test1"))
    b = func.create_block('Entry')
    ib = VNInstructionBuilder(self.context.null_location, b)
    # dev_say_name = ns.get_device_record(VNStandardDeviceKind.O_SAY_NAME_TEXT_DNAME.value + '_adv')
    dev_say_text = ns.get_device_record(VNStandardDeviceKind.O_SAY_TEXT_TEXT_DNAME.value + '_adv')
    _, say_builder = ib.createSayInstructionGroup(narrator)
    say_builder.createPut(StringLiteral.get("Test1", self.context), dev_say_text)
    ib.createWait()
    _, say_builder = ib.createSayInstructionGroup(narrator)
    say_builder.createPut(StringLiteral.get("Test2", self.context), dev_say_text)
    ib.createWait()
    return model
