#!/usr/bin/env python3

import os
import unittest
import tempfile
import PIL.Image
import pydub

import preppipe.vnmodel
import preppipe.enginesupport.renpy
from . import util

class TestVNModel(unittest.TestCase):
  def get_vnmodel():
    vnmodel = preppipe.vnmodel.VNModel(name = "dut", entry = "start")
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
      image = PIL.Image.open(assetdir + path)
      ia = preppipe.vnmodel.VNImageAsset(image)
      ia.set_name(name)
      vnmodel.add_asset(ia)
    for audio_tuple in audio_list:
      name, path = audio_tuple
      aa = preppipe.vnmodel.VNAudioAsset(assetdir + path)
      aa.set_name(name)
      vnmodel.add_asset(aa)
    # declare sayer
    alice = vnmodel.add_character(preppipe.vnmodel.VNCharacterIdentity("Person_Alice"))
    bob =   vnmodel.add_character(preppipe.vnmodel.VNCharacterIdentity("Person_Bob"))
    alice_sayer = vnmodel.add_sayer(preppipe.vnmodel.VNSayerInfo(alice))
    alice_sayer.set_name_text(preppipe.vnmodel.VNTextBlock("Alice"))
    bob_sayer = vnmodel.add_sayer(preppipe.vnmodel.VNSayerInfo(bob))
    bob_sayer.set_name_text(preppipe.vnmodel.VNTextBlock("Bob"))
    alice_sayer.set_character_sprite("", vnmodel.get_asset("female"))
    bob_sayer.set_character_sprite("", vnmodel.get_asset("male"))
    narrator = vnmodel.add_character(preppipe.vnmodel.VNCharacterIdentity(""))
    narrator_sayer = vnmodel.add_sayer(preppipe.vnmodel.VNSayerInfo(narrator))
    
    # add data
    # stub start function, calling test_main and do nothing else
    # eventually our test_main should be like:
    # test_main: diamond shape:
    #   - entry: set bg, select option 1/2: block 1 or block 2
    #   - block 1: male, test1, go to exit
    #   - block 2: female, test2, go to exit
    #   - exit: return
    # However, because the variable system (and therefore branching) is not implemented yet, we just use the same basic block for now
    func_start = vnmodel.add_function(preppipe.vnmodel.VNFunction("start"))
    func_start_entry_bb = func_start.add_basicblock(preppipe.vnmodel.VNBasicBlock("entry"))
    func_start_entry_bb.add_instruction(preppipe.vnmodel.VNCallInst("test_main"))
    func_start_entry_bb.add_instruction(preppipe.vnmodel.VNReturnInst())
    
    func_test = vnmodel.add_function(preppipe.vnmodel.VNFunction("test_main"))
    test_entry_bb = func_test.add_basicblock(preppipe.vnmodel.VNBasicBlock("entry"))
    test_entry_bb.add_instruction(preppipe.vnmodel.VNUpdateBackground(vnmodel.get_asset("classroom")))
    test_entry_bb.add_instruction(preppipe.vnmodel.VNUpdateBGMInstr(vnmodel.get_asset("bgm4")))
    test_entry_bb.add_instruction(preppipe.vnmodel.VNSayInst(narrator_sayer, preppipe.vnmodel.VNTextBlock("Silence")))
    
    bob_decl = test_entry_bb.add_instruction(preppipe.vnmodel.VNSayerDeclInstr(bob_sayer))
    bob_say = test_entry_bb.add_instruction(preppipe.vnmodel.VNSayInst(bob_decl, preppipe.vnmodel.VNTextBlock("Test1"), vnmodel.get_asset("test1")))
    alice_decl = test_entry_bb.add_instruction(preppipe.vnmodel.VNSayerDeclInstr(alice_sayer))
    alice_say = test_entry_bb.add_instruction(preppipe.vnmodel.VNSayInst(alice_decl, preppipe.vnmodel.VNTextBlock("Test2"), vnmodel.get_asset("test2")))
    test_entry_bb.add_instruction(preppipe.vnmodel.VNReturnInst())
    vnmodel.finalize()
    return vnmodel
    
    
  def test_renpy_export(self):
    vnmodel = TestVNModel.get_vnmodel()
    with tempfile.TemporaryDirectory() as project_dir:
      print("TestVNModel.test_renpy_export(): export directory at "+ project_dir)
      preppipe.enginesupport.renpy.RenpySupport.export(vnmodel, project_dir)
      print(util.collectDirectoryDataAsText(project_dir))
      util.copyTestDirIfRequested(project_dir, "TestVNModel.test_renpy_export")
    