#!/usr/bin/env python3

import os
import unittest
import preppipe.documentimport.opendocument

class TestOpenDocumentImport(unittest.TestCase):
  def test_load_puretext(self):
    filename = os.path.dirname(os.path.realpath(__file__)) + "/opendocument_puretext.odt"
    filedata = open(filename, "rb")
    docmodel = preppipe.documentimport.opendocument.import_odf(filedata, filename)
    filedata.close()
    expected_str = """Test1

_This_ is a **TEST**!!!This 
This is <#c9211e>Another</#c9211e> <B#ffff00>Test e</B#ffff00>
Centralized text


"""
    self.assertEqual(docmodel.__str__(), expected_str)

if __name__ == '__main__':
  unittest.main()
