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

    background_dev = top.get_or_create_predefined_device("语涵/图形/背景")
    character_dev = top.get_or_create_predefined_device("语涵/图形/前景")
    bgm_dev = top.get_or_create_predefined_device("语涵/音频/音乐")
    voice_dev = top.get_or_create_predefined_device("语涵/音频/语音")
    text_name_dev = top.get_or_create_predefined_device("语涵/ADV/发言者")
    text_content_dev = top.get_or_create_predefined_device("语涵/ADV/文本")

    def get_constant_text(text : str):
      nonlocal top
      string = vnconstant.VNConstantString.get(text, top.context)
      fragment = vnconstant.VNConstantTextFragment.get(top.context, string, {})
      ctext = vnconstant.VNConstantText.get(top.context, [fragment])
      return ctext
    
    classroom_image = top.get_asset('classroom')
    assert isinstance(classroom_image, vnasset.VNImageAsset)
    classroom_displayable = vnrecord.VNDisplayableRecord('教室', top.location, background_dev)
    classroom_variant = classroom_displayable.add_variant('', classroom_image)
    classroom_position = vnconstant.VNConstantScreenCoordinate.get(top.context, (0, 0))
    classroom_position = classroom_displayable.add_position('', classroom_position)

    sayer1_image = top.get_asset('female')
    assert isinstance(sayer1_image, vnasset.VNImageAsset)
    sayer1_position = vnconstant.VNConstantScreenCoordinate.get(top.context, (100, 100))
    sayer1_dict = vnrecord.VNDisplayableRecord.create_simple_displayable_record('甲', top.location, character_dev, sayer1_image, sayer1_position)
    #sayer1_displayable = vnrecord.VNDisplayableRecord('甲', top.location, character_dev)

    sayer2_image = top.get_asset('male')
    assert isinstance(sayer2_image, vnasset.VNImageAsset)
    sayer2_position = vnconstant.VNConstantScreenCoordinate.get(top.context, (200, 200))
    sayer2_dict = vnrecord.VNDisplayableRecord.create_simple_displayable_record('乙', top.location, character_dev, sayer2_image, sayer2_position)

    bgm_music = top.get_asset('bgm4')
    assert isinstance(bgm_music, vnasset.VNAudioAsset)
    bgm_audio = vnrecord.VNAudioRecord('背景音乐', top.location, bgm_dev)
    bgm_variant = bgm_audio.add_variant('', bgm_music)

    classroom_bg_inst = entry_step.create_create_displayable_inst(entry_step.start_time, content = classroom_displayable, variant = classroom_variant, position = classroom_position)
    bgm_inst = entry_step.create_create_audio_inst(entry_step.start_time, bgm_audio, bgm_variant)

    #bgm_inst = entry_step.create_create_audio_inst(entry_step.insertion_block_start_time, content = )
    #test_entry_bb = func_test.add_basicblock(preppipe.VNBasicBlock("entry"))
    #test_entry_bb.add_instruction(preppipe.VNUpdateBackgroundInst(vnmodel.get_asset("classroom")))
    #test_entry_bb.add_instruction(preppipe.VNUpdateBGMInst(vnmodel.get_asset("bgm4")))
    # TODO

    
    #test_entry_bb.add_instruction(preppipe.VNSayInst(narrator_sayer, preppipe.VNTextBlock("Silence")))
    narrator_say_group = entry_step.create_say_instruction_group(classroom_bg_inst.finish_time, narrator)
    narrator_say_builder = entry_step.create_instruction_group_builder(narrator_say_group)
    narrator_say_builder.create_put_text_inst(narrator_say_group.start_time, *vnrecord.VNTextRecord.create_simple_text_record('旁白发言', top.location, text_content_dev, get_constant_text('Silence')))
    narrator_say_builder.create_wait_user_inst(narrator_say_group.start_time)
    entry_step.create_finish_step_inst(narrator_say_group.finish_time)

    sayer1_say_name_record_dict = vnrecord.VNTextRecord.create_simple_text_record('甲发言名', top.location, text_name_dev, get_constant_text('甲'))
    sayer1_say_text_record_dict = vnrecord.VNTextRecord.create_simple_text_record('甲发言', top.location, text_content_dev, get_constant_text('测试1'))
    sayer1_say_voice_record_dict = vnrecord.VNAudioRecord.create_simple_audio_record('甲语音', top.location, voice_dev, top.get_asset('test1'))

    sayer1_step = func_test_entry_builder.create_step_builder()
    sayer1_show_inst = sayer1_step.create_create_displayable_inst(sayer1_step.start_time, *sayer1_dict)
    sayer1_say_group = sayer1_step.create_say_instruction_group(sayer1_show_inst.finish_time, sayer1)
    sayer1_say_group_builder = sayer1_step.create_instruction_group_builder(sayer1_say_group)
    sayer1_say_group_builder.create_put_text_inst(sayer1_say_group_builder.start_time, *sayer1_say_name_record_dict)
    sayer1_say_group_builder.create_put_text_inst(sayer1_say_group_builder.start_time, *sayer1_say_text_record_dict)
    sayer1_say_group_builder.create_put_audio_inst(sayer1_say_group_builder.start_time, *sayer1_say_voice_record_dict)
    sayer1_say_group_builder.create_wait_user_inst(sayer1_say_group_builder.start_time)
    sayer1_step.create_finish_step_inst(sayer1_say_group.finish_time)

    sayer2_say_name_record_dict = vnrecord.VNTextRecord.create_simple_text_record('乙发言名', top.location, text_name_dev, get_constant_text('乙'))
    sayer2_say_text_record_dict = vnrecord.VNTextRecord.create_simple_text_record('乙发言', top.location, text_content_dev, get_constant_text('测试2'))
    sayer2_say_voice_record_dict = vnrecord.VNAudioRecord.create_simple_audio_record('乙语音', top.location, voice_dev, top.get_asset('test2'))

    sayer2_step = func_test_entry_builder.create_step_builder()
    sayer2_show_inst = sayer2_step.create_create_displayable_inst(sayer2_step.start_time, *sayer2_dict)
    sayer2_say_group = sayer2_step.create_say_instruction_group(sayer2_show_inst.finish_time, sayer1)
    sayer2_say_group_builder = sayer2_step.create_instruction_group_builder(sayer2_say_group)
    sayer2_say_group_builder.create_put_text_inst(sayer2_say_group_builder.start_time, *sayer2_say_name_record_dict)
    sayer2_say_group_builder.create_put_text_inst(sayer2_say_group_builder.start_time, *sayer2_say_text_record_dict)
    sayer2_say_group_builder.create_put_audio_inst(sayer2_say_group_builder.start_time, *sayer2_say_voice_record_dict)
    sayer2_say_group_builder.create_wait_user_inst(sayer2_say_group_builder.start_time)
    sayer2_step.create_finish_step_inst(sayer2_say_group.finish_time)

    #bob_decl = test_entry_bb.add_instruction(preppipe.VNSayerDeclInst(bob_sayer))
    #bob_say = test_entry_bb.add_instruction(preppipe.VNSayInst(bob_decl, preppipe.VNTextBlock("Test1"), vnmodel.get_asset("test1")))
    #alice_decl = test_entry_bb.add_instruction(preppipe.VNSayerDeclInst(alice_sayer))
    #alice_say = test_entry_bb.add_instruction(preppipe.VNSayInst(alice_decl, preppipe.VNTextBlock("Test2"), vnmodel.get_asset("test2")))

    func_test_entry_builder.create_return()
    return top
    
    
  #def test_renpy_export(self):
  #  vnmodel = TestVNModel.get_vnmodel()
  #  with tempfile.TemporaryDirectory() as project_dir:
  #    print("TestVNModel.test_renpy_export(): export directory at "+ project_dir)
  #    export_obj = preppipe.enginesupport.RenpySupport.get().start_export(project_dir)
  #    export_obj.add(vnmodel)
  #    export_obj.set_option("entryfunction", "start")
  #    export_obj.do_export()
  #    print(util.collectDirectoryDataAsText(project_dir))
  #    util.copyTestDirIfRequested(project_dir, "TestVNModel.test_renpy_export")
    