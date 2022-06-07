#!/usr/bin/env python3

import os
import unittest
import tempfile
import PIL.Image
import pydub

import preppipe
from preppipe.frontend.vnmodel.vnparser import *
from . import util

class TestVNFrontEnd(unittest.TestCase):
  def _add_puretext_paragraph(doc : IMDocument, text: str, styles: typing.Any = None) -> None:
    p = IMParagraphBlock()
    doc.add_block(p)
    p.add_element(IMTextElement(text, styles))
  
  def get_inputmodel():
    ns = IMNamespace(IRNamespaceIdentifier([]), ".")
    im = InputModel()
    im.add_namespace(ns)
    doc = IMDocument("Anon", "anon.odf")
    ns.add_document(doc)
    TestVNFrontEnd._add_puretext_paragraph(doc, "This is a text paragraph of unknown speaker.")
    TestVNFrontEnd._add_puretext_paragraph(doc, "Alice: \"This is Alice speaking!\"")
    TestVNFrontEnd._add_puretext_paragraph(doc, "Bob: \"This is Bob speaking!\"")
    TestVNFrontEnd._add_puretext_paragraph(doc, "[# These text are all comments now and should be ignored]")
    TestVNFrontEnd._add_puretext_paragraph(doc, "[SoundEffect HelloWorld.ogg][SoundEffect hood][Label hoo] # emm")
    return im

  def test_vnmodel_parse(self):
    im = TestVNFrontEnd.get_inputmodel()
    parser = VNParser()
    parser.add(im)
    parser.run()
    result = parser.get_result()
    print("TestVNFrontEnd.test_vnmodel_parse() result:")
    print(result.__str__())
    print("TestVNFrontEnd.test_vnmodel_parse() result finished")

