# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from .pipeline import *
from .irbase import *
from .vnmodel_v4 import *
from .imageexpr import *

@FrontendDecl('test-vnmodel-build', input_decl=IODecl(description='<No Input>', nargs=0), output_decl=VNModel)
class _TestVNModelBuild(TransformBase):
  def run(self) -> VNModel:
    model = VNModel.create(self.context, "TestModel")
    ns = model.add_namespace(VNNamespace.create('/', self.context.null_location))
    VNDeviceSymbol.create_standard_device_tree(ns)
    dev_bg = ns.get_device_record(VNStandardDeviceKind.O_BACKGROUND_DISPLAY_DNAME.value)
    narrator = VNCharacterSymbol.create_narrator(self.context)
    ns.add_record(narrator)
    sayer1 = VNCharacterSymbol.create_normal_sayer(self.context, name="发言者", codename="sayer1")
    ns.add_record(sayer1)
    scene1 = VNSceneSymbol.create(self.context, name="默认背景", codename='bg')
    ns.add_record(scene1)
    dummyfunc = ns.add_function(VNFunction.create(self.context, "dummy"))
    dummyentry = dummyfunc.create_block('Entry')
    dummyentry.body.push_back(VNReturnInst.create(self.context, start_time=dummyentry.get_argument('start')))
    func = ns.add_function(VNFunction.create(self.context, "Test1"))
    func.set_as_entry_point(VNFunction.ATTRVAL_ENTRYPOINT_MAIN)
    b = func.create_block('Entry')
    ib = VNInstructionBuilder(self.context.null_location, b)
    _, sceneswitch_builder = ib.createSceneSwitchInstructionGroup(scene1)
    bgcontent = PlaceholderImageLiteralExpr.get(self.context, desc=StringLiteral.get('Dummy BG', self.context), size=IntTupleLiteral.get((1920,1080), self.context), anchor=FloatTupleLiteral.get((decimal.Decimal(0.0), decimal.Decimal(0.0)), self.context))
    sceneswitch_builder.createCreate(content=bgcontent, device=dev_bg)
    # dev_say_name = ns.get_device_record(VNStandardDeviceKind.O_SAY_NAME_TEXT_DNAME.value + '_adv')
    dev_say_text = ns.get_device_record(VNStandardDeviceKind.O_SAY_TEXT_TEXT_DNAME.value + '_adv')
    _, say_builder = ib.createSayInstructionGroup(narrator)
    say_builder.createPut(StringLiteral.get("Test1", self.context), dev_say_text, update_time=True)
    ib.createWait()
    _, say_builder = ib.createSayInstructionGroup(narrator)
    say_builder.createPut(StringLiteral.get("Test2", self.context), dev_say_text, update_time=True)
    ib.createWait()
    return model
