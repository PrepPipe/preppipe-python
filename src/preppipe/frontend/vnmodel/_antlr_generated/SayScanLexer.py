# Generated from SayScan.g4 by ANTLR 4.10.1
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
    from typing import TextIO
else:
    from typing.io import TextIO


def serializedATN():
    return [
        4,0,8,83,6,-1,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,
        6,7,6,2,7,7,7,1,0,4,0,19,8,0,11,0,12,0,20,1,0,1,0,1,1,1,1,5,1,27,
        8,1,10,1,12,1,30,9,1,1,1,1,1,1,1,5,1,35,8,1,10,1,12,1,38,9,1,1,1,
        1,1,1,1,5,1,43,8,1,10,1,12,1,46,9,1,1,1,1,1,1,1,5,1,51,8,1,10,1,
        12,1,54,9,1,1,1,1,1,1,1,5,1,59,8,1,10,1,12,1,62,9,1,1,1,3,1,65,8,
        1,1,2,1,2,1,3,1,3,1,4,1,4,1,5,1,5,1,6,1,6,1,7,1,7,5,7,79,8,7,10,
        7,12,7,82,9,7,5,28,36,44,52,60,0,8,1,1,3,2,5,3,7,4,9,5,11,6,13,7,
        15,8,1,0,13,9,0,9,10,13,13,32,32,160,160,8192,8203,8239,8239,8287,
        8287,12288,12288,65279,65279,1,0,34,34,1,0,39,39,1,0,8220,8221,1,
        0,93,93,1,0,12305,12305,2,0,58,58,65306,65306,2,0,40,40,65288,65288,
        2,0,41,41,65289,65289,2,0,44,44,65292,65292,7,0,33,33,46,46,63,63,
        8230,8230,12290,12290,65281,65281,65311,65311,25,0,9,10,13,13,32,
        34,39,41,44,44,46,46,58,58,63,63,91,91,93,93,160,160,8192,8203,8220,
        8221,8230,8230,8239,8239,8287,8287,12288,12288,12290,12290,12304,
        12305,65279,65279,65281,65281,65288,65289,65292,65292,65306,65306,
        65311,65311,17,0,33,34,39,41,44,44,46,46,58,58,63,63,91,91,93,93,
        8220,8221,8230,8230,12290,12290,12304,12305,65281,65281,65288,65289,
        65292,65292,65306,65306,65311,65311,93,0,1,1,0,0,0,0,3,1,0,0,0,0,
        5,1,0,0,0,0,7,1,0,0,0,0,9,1,0,0,0,0,11,1,0,0,0,0,13,1,0,0,0,0,15,
        1,0,0,0,1,18,1,0,0,0,3,64,1,0,0,0,5,66,1,0,0,0,7,68,1,0,0,0,9,70,
        1,0,0,0,11,72,1,0,0,0,13,74,1,0,0,0,15,76,1,0,0,0,17,19,7,0,0,0,
        18,17,1,0,0,0,19,20,1,0,0,0,20,18,1,0,0,0,20,21,1,0,0,0,21,22,1,
        0,0,0,22,23,6,0,0,0,23,2,1,0,0,0,24,28,5,34,0,0,25,27,8,1,0,0,26,
        25,1,0,0,0,27,30,1,0,0,0,28,29,1,0,0,0,28,26,1,0,0,0,29,31,1,0,0,
        0,30,28,1,0,0,0,31,65,5,34,0,0,32,36,5,39,0,0,33,35,8,2,0,0,34,33,
        1,0,0,0,35,38,1,0,0,0,36,37,1,0,0,0,36,34,1,0,0,0,37,39,1,0,0,0,
        38,36,1,0,0,0,39,65,5,39,0,0,40,44,2,8220,8221,0,41,43,8,3,0,0,42,
        41,1,0,0,0,43,46,1,0,0,0,44,45,1,0,0,0,44,42,1,0,0,0,45,47,1,0,0,
        0,46,44,1,0,0,0,47,65,2,8220,8221,0,48,52,5,91,0,0,49,51,8,4,0,0,
        50,49,1,0,0,0,51,54,1,0,0,0,52,53,1,0,0,0,52,50,1,0,0,0,53,55,1,
        0,0,0,54,52,1,0,0,0,55,65,5,93,0,0,56,60,5,12304,0,0,57,59,8,5,0,
        0,58,57,1,0,0,0,59,62,1,0,0,0,60,61,1,0,0,0,60,58,1,0,0,0,61,63,
        1,0,0,0,62,60,1,0,0,0,63,65,5,12305,0,0,64,24,1,0,0,0,64,32,1,0,
        0,0,64,40,1,0,0,0,64,48,1,0,0,0,64,56,1,0,0,0,65,4,1,0,0,0,66,67,
        7,6,0,0,67,6,1,0,0,0,68,69,7,7,0,0,69,8,1,0,0,0,70,71,7,8,0,0,71,
        10,1,0,0,0,72,73,7,9,0,0,73,12,1,0,0,0,74,75,7,10,0,0,75,14,1,0,
        0,0,76,80,8,11,0,0,77,79,8,12,0,0,78,77,1,0,0,0,79,82,1,0,0,0,80,
        78,1,0,0,0,80,81,1,0,0,0,81,16,1,0,0,0,82,80,1,0,0,0,9,0,20,28,36,
        44,52,60,64,80,1,6,0,0
    ]

class SayScanLexer(Lexer):

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    WS = 1
    QUOTEDSTR = 2
    SAYSEPARATOR = 3
    STATUSSTART = 4
    STATUSEND = 5
    COMMASPLITTER = 6
    SENTENCESPLITTER = 7
    NORMALTEXT = 8

    channelNames = [ u"DEFAULT_TOKEN_CHANNEL", u"HIDDEN" ]

    modeNames = [ "DEFAULT_MODE" ]

    literalNames = [ "<INVALID>",
 ]

    symbolicNames = [ "<INVALID>",
            "WS", "QUOTEDSTR", "SAYSEPARATOR", "STATUSSTART", "STATUSEND", 
            "COMMASPLITTER", "SENTENCESPLITTER", "NORMALTEXT" ]

    ruleNames = [ "WS", "QUOTEDSTR", "SAYSEPARATOR", "STATUSSTART", "STATUSEND", 
                  "COMMASPLITTER", "SENTENCESPLITTER", "NORMALTEXT" ]

    grammarFileName = "SayScan.g4"

    def __init__(self, input=None, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = LexerATNSimulator(self, self.atn, self.decisionsToDFA, PredictionContextCache())
        self._actions = None
        self._predicates = None

