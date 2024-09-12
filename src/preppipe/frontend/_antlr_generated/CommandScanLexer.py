# Generated from CommandScan.g4 by ANTLR 4.10.1
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
    from typing import TextIO
else:
    from typing.io import TextIO


def serializedATN():
    return [
        4,0,6,59,6,-1,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,1,
        0,4,0,15,8,0,11,0,12,0,16,1,0,1,0,1,1,1,1,5,1,23,8,1,10,1,12,1,26,
        9,1,1,1,1,1,1,1,5,1,31,8,1,10,1,12,1,34,9,1,1,1,1,1,1,1,5,1,39,8,
        1,10,1,12,1,42,9,1,1,1,3,1,45,8,1,1,2,1,2,1,3,1,3,1,4,1,4,1,5,1,
        5,5,5,55,8,5,10,5,12,5,58,9,5,3,24,32,40,0,6,1,1,3,2,5,3,7,4,9,5,
        11,6,1,0,8,9,0,9,10,13,13,32,32,160,160,8192,8203,8239,8239,8287,
        8287,12288,12288,65279,65279,1,0,34,34,1,0,39,39,1,0,8220,8221,2,
        0,91,91,12304,12304,2,0,93,93,12305,12305,15,0,9,10,13,13,32,32,
        34,34,39,39,91,91,93,93,160,160,8192,8203,8220,8221,8239,8239,8287,
        8287,12288,12288,12304,12305,65279,65279,6,0,34,34,39,39,91,91,93,
        93,8220,8221,12304,12305,65,0,1,1,0,0,0,0,3,1,0,0,0,0,5,1,0,0,0,
        0,7,1,0,0,0,0,9,1,0,0,0,0,11,1,0,0,0,1,14,1,0,0,0,3,44,1,0,0,0,5,
        46,1,0,0,0,7,48,1,0,0,0,9,50,1,0,0,0,11,52,1,0,0,0,13,15,7,0,0,0,
        14,13,1,0,0,0,15,16,1,0,0,0,16,14,1,0,0,0,16,17,1,0,0,0,17,18,1,
        0,0,0,18,19,6,0,0,0,19,2,1,0,0,0,20,24,5,34,0,0,21,23,8,1,0,0,22,
        21,1,0,0,0,23,26,1,0,0,0,24,25,1,0,0,0,24,22,1,0,0,0,25,27,1,0,0,
        0,26,24,1,0,0,0,27,45,5,34,0,0,28,32,5,39,0,0,29,31,8,2,0,0,30,29,
        1,0,0,0,31,34,1,0,0,0,32,33,1,0,0,0,32,30,1,0,0,0,33,35,1,0,0,0,
        34,32,1,0,0,0,35,45,5,39,0,0,36,40,2,8220,8221,0,37,39,8,3,0,0,38,
        37,1,0,0,0,39,42,1,0,0,0,40,41,1,0,0,0,40,38,1,0,0,0,41,43,1,0,0,
        0,42,40,1,0,0,0,43,45,2,8220,8221,0,44,20,1,0,0,0,44,28,1,0,0,0,
        44,36,1,0,0,0,45,4,1,0,0,0,46,47,5,0,0,0,47,6,1,0,0,0,48,49,7,4,
        0,0,49,8,1,0,0,0,50,51,7,5,0,0,51,10,1,0,0,0,52,56,8,6,0,0,53,55,
        8,7,0,0,54,53,1,0,0,0,55,58,1,0,0,0,56,54,1,0,0,0,56,57,1,0,0,0,
        57,12,1,0,0,0,58,56,1,0,0,0,7,0,16,24,32,40,44,56,1,6,0,0
    ]

class CommandScanLexer(Lexer):

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    WS = 1
    QUOTEDSTR = 2
    ELEMENT = 3
    COMMANDSTART = 4
    COMMANDEND = 5
    NORMALTEXT = 6

    channelNames = [ u"DEFAULT_TOKEN_CHANNEL", u"HIDDEN" ]

    modeNames = [ "DEFAULT_MODE" ]

    literalNames = [ "<INVALID>",
            "'\\u0000'" ]

    symbolicNames = [ "<INVALID>",
            "WS", "QUOTEDSTR", "ELEMENT", "COMMANDSTART", "COMMANDEND", 
            "NORMALTEXT" ]

    ruleNames = [ "WS", "QUOTEDSTR", "ELEMENT", "COMMANDSTART", "COMMANDEND", 
                  "NORMALTEXT" ]

    grammarFileName = "CommandScan.g4"

    def __init__(self, input=None, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = LexerATNSimulator(self, self.atn, self.decisionsToDFA, PredictionContextCache())
        self._actions = None
        self._predicates = None


