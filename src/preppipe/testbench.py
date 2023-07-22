# SPDX-FileCopyrightText: 2022-2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

from .pipeline import *
from .irbase import *
from .vnmodel import *
from .imageexpr import *
from .analysis.icfg import *
from .analysis.vnmodel.timemodel import *
from .analysis.vnmodel.assetusage import AssetUsage

@FrontendDecl('test-vnmodel-build', input_decl=IODecl(description='<No Input>', nargs=0), output_decl=VNModel)
class _TestVNModelBuild(TransformBase):
  def run(self) -> VNModel:
    model = VNModel.create(self.context, "TestModel")
    ns = model.add_namespace(VNNamespace.create('/', self.context.null_location))
    VNDeviceSymbol.create_standard_device_tree(ns)
    dev_bg = ns.get_device(VNStandardDeviceKind.O_BACKGROUND_DISPLAY_DNAME.value)
    narrator = VNCharacterSymbol.create_narrator(self.context)
    ns.add_character(narrator)
    sayer1 = VNCharacterSymbol.create_normal_sayer(self.context, name="发言者", codename="sayer1")
    ns.add_character(sayer1)
    scene1 = VNSceneSymbol.create(self.context, name="默认背景", codename='bg')
    ns.add_scene(scene1)
    dummyfunc = ns.add_function(VNFunction.create(self.context, "dummy"))
    dummyentry = dummyfunc.create_block('Entry')
    dummyentry.body.push_back(VNReturnInst.create(self.context, start_time=dummyentry.get_argument('start')))
    func = ns.add_function(VNFunction.create(self.context, "Test1"))
    func.set_as_entry_point(VNFunction.ATTRVAL_ENTRYPOINT_MAIN)
    b = func.create_block('Entry')
    ib = VNInstructionBuilder(self.context.null_location, b)
    _, sceneswitch_builder = ib.createSceneSwitchInstructionGroup(scene1)
    bgcontent = PlaceholderImageLiteralExpr.get(self.context, dest=ImageExprPlaceholderDest.DEST_SCENE_BACKGROUND, desc=StringLiteral.get('Dummy BG', self.context), size=IntTupleLiteral.get((1920,1080), self.context))
    bghandle = sceneswitch_builder.createCreate(content=bgcontent, device=dev_bg)
    # dev_say_name = ns.get_device_record(VNStandardDeviceKind.O_SAY_NAME_TEXT_DNAME.value + '_adv')
    dev_say_text = ns.get_device(VNStandardDeviceKind.O_SAY_TEXT_TEXT_DNAME.value + '_adv')
    _, say_builder = ib.createSayInstructionGroup(narrator)
    say_builder.createPut(StringLiteral.get("Test1", self.context), dev_say_text, update_time=True)
    ib.createWait()
    _, say_builder = ib.createSayInstructionGroup(sayer1)
    say_builder.createPut(StringLiteral.get("Test2", self.context), dev_say_text, update_time=True)
    ib.createWait()
    # create a branch
    ifdest = func.create_block('if.end')
    branch = ib.createBranch(ifdest)
    thenblk = func.create_block('if.then')
    branch.add_branch(BoolLiteral.get(True, self.context), thenblk)
    thenib = VNInstructionBuilder(self.context.null_location, thenblk)
    thenib.createCall(dummyfunc, destroyed_handle_list=(bghandle,))
    thenib.createBranch(ifdest)
    ib.createReturn()
    graph = ICFG.build(model)
    graph.dump_graphviz_dot()
    tm = SayCountTimeModel()
    usage = AssetUsage.build(model, graph, tm)
    print(str(usage))
    return model
