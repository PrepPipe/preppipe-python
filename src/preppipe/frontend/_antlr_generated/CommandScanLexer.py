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
        4,0,7,63,6,-1,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,
        6,7,6,1,0,4,0,17,8,0,11,0,12,0,18,1,0,1,0,1,1,1,1,5,1,25,8,1,10,
        1,12,1,28,9,1,1,1,1,1,1,1,5,1,33,8,1,10,1,12,1,36,9,1,1,1,1,1,1,
        1,5,1,41,8,1,10,1,12,1,44,9,1,1,1,3,1,47,8,1,1,2,1,2,1,3,1,3,1,4,
        1,4,1,5,1,5,1,6,1,6,5,6,59,8,6,10,6,12,6,62,9,6,3,26,34,42,0,7,1,
        1,3,2,5,3,7,4,9,5,11,6,13,7,1,0,9,9,0,9,10,13,13,32,32,160,160,8192,
        8203,8239,8239,8287,8287,12288,12288,65279,65279,1,0,34,34,1,0,39,
        39,1,0,8220,8221,2,0,35,35,65283,65283,2,0,91,91,12304,12304,2,0,
        93,93,12305,12305,16,0,9,10,13,13,32,32,34,35,39,39,91,91,93,93,
        160,160,8192,8203,8220,8221,8239,8239,8287,8287,12288,12288,12304,
        12305,65279,65279,65283,65283,7,0,34,35,39,39,91,91,93,93,8220,8221,
        12304,12305,65283,65283,69,0,1,1,0,0,0,0,3,1,0,0,0,0,5,1,0,0,0,0,
        7,1,0,0,0,0,9,1,0,0,0,0,11,1,0,0,0,0,13,1,0,0,0,1,16,1,0,0,0,3,46,
        1,0,0,0,5,48,1,0,0,0,7,50,1,0,0,0,9,52,1,0,0,0,11,54,1,0,0,0,13,
        56,1,0,0,0,15,17,7,0,0,0,16,15,1,0,0,0,17,18,1,0,0,0,18,16,1,0,0,
        0,18,19,1,0,0,0,19,20,1,0,0,0,20,21,6,0,0,0,21,2,1,0,0,0,22,26,5,
        34,0,0,23,25,8,1,0,0,24,23,1,0,0,0,25,28,1,0,0,0,26,27,1,0,0,0,26,
        24,1,0,0,0,27,29,1,0,0,0,28,26,1,0,0,0,29,47,5,34,0,0,30,34,5,39,
        0,0,31,33,8,2,0,0,32,31,1,0,0,0,33,36,1,0,0,0,34,35,1,0,0,0,34,32,
        1,0,0,0,35,37,1,0,0,0,36,34,1,0,0,0,37,47,5,39,0,0,38,42,2,8220,
        8221,0,39,41,8,3,0,0,40,39,1,0,0,0,41,44,1,0,0,0,42,43,1,0,0,0,42,
        40,1,0,0,0,43,45,1,0,0,0,44,42,1,0,0,0,45,47,2,8220,8221,0,46,22,
        1,0,0,0,46,30,1,0,0,0,46,38,1,0,0,0,47,4,1,0,0,0,48,49,5,0,0,0,49,
        6,1,0,0,0,50,51,7,4,0,0,51,8,1,0,0,0,52,53,7,5,0,0,53,10,1,0,0,0,
        54,55,7,6,0,0,55,12,1,0,0,0,56,60,8,7,0,0,57,59,8,8,0,0,58,57,1,
        0,0,0,59,62,1,0,0,0,60,58,1,0,0,0,60,61,1,0,0,0,61,14,1,0,0,0,62,
        60,1,0,0,0,7,0,18,26,34,42,46,60,1,6,0,0
    ]

class CommandScanLexer(Lexer):

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    WS = 1
    QUOTEDSTR = 2
    ELEMENT = 3
    COMMENTSTART = 4
    COMMANDSTART = 5
    COMMANDEND = 6
    NORMALTEXT = 7

    channelNames = [ u"DEFAULT_TOKEN_CHANNEL", u"HIDDEN" ]

    modeNames = [ "DEFAULT_MODE" ]

    literalNames = [ "<INVALID>",
            "'\\u0000'" ]

    symbolicNames = [ "<INVALID>",
            "WS", "QUOTEDSTR", "ELEMENT", "COMMENTSTART", "COMMANDSTART", 
            "COMMANDEND", "NORMALTEXT" ]

    ruleNames = [ "WS", "QUOTEDSTR", "ELEMENT", "COMMENTSTART", "COMMANDSTART", 
                  "COMMANDEND", "NORMALTEXT" ]

    grammarFileName = "CommandScan.g4"

    def __init__(self, input=None, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = LexerATNSimulator(self, self.atn, self.decisionsToDFA, PredictionContextCache())
        self._actions = None
        self._predicates = None


