#!/usr/bin/env python3

import os
import unittest
import tempfile
import PIL.Image
import pydub

#import preppipe
#import preppipe.enginesupport.renpy
import preppipe
from preppipe.irbase import *
from preppipe.vnmodel import *

from . import util

class TestVNModel(unittest.TestCase):
  def get_vnmodel():
    ctx = Context()
    top = vnnamespace.VNNamespace(name = '', loc = Location.getNullLocation(ctx), parent = None)

    #vnmodel = preppipe.VNModel(name = "dut", entry = "start")
    assetdir = os.path.dirname(os.path.realpath(__file__)) + "/assets/"
    # manually add assets
    image_list = [
      ("classroom", "images/classroom.png"),
      ("female",    "images/female.png"),
      ("male",      "images/male.png")
    ]
    audio_list = [
      ("bgm4",      "audio/bgm4.m4a"),
      ("test1",     "audio/test1.m4a"),
      ("test2",     "audio/test2.m4a")
    ]
    for image_tuple in image_list:
      name, path = image_tuple
      top.add_image_asset_from_file(path, name)
    for audio_tuple in audio_list:
      name, path = audio_tuple
      top.add_audio_asset_from_file(path, name)
    # declare sayer
    sayer1 = top.add_character("甲")
    sayer2 = top.add_character("乙")
    narrator = top.add_character("旁白")

    #alice = vnmodel.add_character(preppipe.VNCharacterIdentity("Person_Alice"))
    #bob =   vnmodel.add_character(preppipe.VNCharacterIdentity("Person_Bob"))
    #alice_sayer = vnmodel.add_sayer(preppipe.VNSayerInfo(alice))
    #alice_sayer.set_name_text(preppipe.VNTextBlock("Alice"))
    #bob_sayer = vnmodel.add_sayer(preppipe.VNSayerInfo(bob))
    #bob_sayer.set_name_text(preppipe.VNTextBlock("Bob"))
    #alice_sayer.set_character_sprite("", vnmodel.get_asset("female"))
    #bob_sayer.set_character_sprite("", vnmodel.get_asset("male"))
    #narrator = vnmodel.add_character(preppipe.VNCharacterIdentity(""))
    #narrator_sayer = vnmodel.add_sayer(preppipe.VNSayerInfo(narrator))
    
    # add data
    # stub start function, calling test_main and do nothing else
    # eventually our test_main should be like:
    # test_main: diamond shape:
    #   - entry: set bg, select option 1/2: block 1 or block 2
    #   - block 1: male, test1, go to exit
    #   - block 2: female, test2, go to exit
    #   - exit: return
    # However, because the variable system (and therefore branching) is not implemented yet, we just use the same basic block for now
    func_start = top.add_function("入口")
    func_test = top.add_function("主线")
    #func_start = vnmodel.add_function(preppipe.VNFunction("start"))
    #func_test = vnmodel.add_function(preppipe.VNFunction("test_main"))

    func_start_entry_bb = func_start.body.add_block("开始")
    #func_start_entry_bb = func_start.add_basicblock(preppipe.VNBasicBlock("entry"))
    func_start_entry_builder = vnbuilder.VNBlockBuilder(top, insert_at_block_end=func_start_entry_bb)
    func_start_entry_builder.create_call(func_test)
    func_start_entry_builder.create_return()
    #func_start_entry_bb.add_instruction(preppipe.VNCallInst(func_test))
    #func_start_entry_bb.add_instruction(preppipe.VNReturnInst())
    func_test_entry_bb = func_test.body.add_block("开始")
    func_test_entry_builder = vnbuilder.VNBlockBuilder(top, insert_at_block_end=func_test_entry_bb)

    entry_step = func_test_entry_builder.create_step_builder()
    #test_entry_bb = func_test.add_basicblock(preppipe.VNBasicBlock("entry"))
    # TODO
    test_entry_bb.add_instruction(preppipe.VNUpdateBackgroundInst(vnmodel.get_asset("classroom")))
    test_entry_bb.add_instruction(preppipe.VNUpdateBGMInst(vnmodel.get_asset("bgm4")))
    test_entry_bb.add_instruction(preppipe.VNSayInst(narrator_sayer, preppipe.VNTextBlock("Silence")))
    
    bob_decl = test_entry_bb.add_instruction(preppipe.VNSayerDeclInst(bob_sayer))
    bob_say = test_entry_bb.add_instruction(preppipe.VNSayInst(bob_decl, preppipe.VNTextBlock("Test1"), vnmodel.get_asset("test1")))
    alice_decl = test_entry_bb.add_instruction(preppipe.VNSayerDeclInst(alice_sayer))
    alice_say = test_entry_bb.add_instruction(preppipe.VNSayInst(alice_decl, preppipe.VNTextBlock("Test2"), vnmodel.get_asset("test2")))
    test_entry_bb.add_instruction(preppipe.VNReturnInst())
    vnmodel.finalize()
    return vnmodel
    
    
  def test_renpy_export(self):
    vnmodel = TestVNModel.get_vnmodel()
    with tempfile.TemporaryDirectory() as project_dir:
      print("TestVNModel.test_renpy_export(): export directory at "+ project_dir)
      export_obj = preppipe.enginesupport.RenpySupport.get().start_export(project_dir)
      export_obj.add(vnmodel)
      export_obj.set_option("entryfunction", "start")
      export_obj.do_export()
      print(util.collectDirectoryDataAsText(project_dir))
      util.copyTestDirIfRequested(project_dir, "TestVNModel.test_renpy_export")
    