# Generated from CommandParse.g4 by ANTLR 4.10.1
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
    from typing import TextIO
else:
    from typing.io import TextIO


def serializedATN():
    return [
        4,0,12,81,6,-1,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,
        6,7,6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,1,0,4,0,27,8,0,
        11,0,12,0,28,1,0,1,0,1,1,1,1,1,2,1,2,1,3,1,3,1,4,1,4,1,5,1,5,1,6,
        1,6,1,7,1,7,1,8,1,8,1,9,1,9,1,10,1,10,5,10,53,8,10,10,10,12,10,56,
        9,10,1,10,1,10,1,10,5,10,61,8,10,10,10,12,10,64,9,10,1,10,1,10,1,
        10,5,10,69,8,10,10,10,12,10,72,9,10,1,10,3,10,75,8,10,1,11,4,11,
        78,8,11,11,11,12,11,79,3,54,62,70,0,12,1,1,3,2,5,3,7,4,9,5,11,6,
        13,7,15,8,17,9,19,10,21,11,23,12,1,0,13,9,0,9,10,13,13,32,32,160,
        160,8192,8203,8239,8239,8287,8287,12288,12288,65279,65279,2,0,35,
        35,65283,65283,2,0,91,91,12304,12304,2,0,93,93,12305,12305,2,0,58,
        58,65306,65306,2,0,61,61,65309,65309,2,0,44,44,65292,65292,2,0,40,
        40,65288,65288,2,0,41,41,65289,65289,1,0,34,34,1,0,39,39,1,0,8220,
        8221,23,0,9,10,13,13,32,32,34,35,39,41,44,44,58,58,61,61,91,91,93,
        93,160,160,8192,8203,8220,8221,8239,8239,8287,8287,12288,12288,12304,
        12305,65279,65279,65283,65283,65288,65289,65292,65292,65306,65306,
        65309,65309,87,0,1,1,0,0,0,0,3,1,0,0,0,0,5,1,0,0,0,0,7,1,0,0,0,0,
        9,1,0,0,0,0,11,1,0,0,0,0,13,1,0,0,0,0,15,1,0,0,0,0,17,1,0,0,0,0,
        19,1,0,0,0,0,21,1,0,0,0,0,23,1,0,0,0,1,26,1,0,0,0,3,32,1,0,0,0,5,
        34,1,0,0,0,7,36,1,0,0,0,9,38,1,0,0,0,11,40,1,0,0,0,13,42,1,0,0,0,
        15,44,1,0,0,0,17,46,1,0,0,0,19,48,1,0,0,0,21,74,1,0,0,0,23,77,1,
        0,0,0,25,27,7,0,0,0,26,25,1,0,0,0,27,28,1,0,0,0,28,26,1,0,0,0,28,
        29,1,0,0,0,29,30,1,0,0,0,30,31,6,0,0,0,31,2,1,0,0,0,32,33,5,0,0,
        0,33,4,1,0,0,0,34,35,7,1,0,0,35,6,1,0,0,0,36,37,7,2,0,0,37,8,1,0,
        0,0,38,39,7,3,0,0,39,10,1,0,0,0,40,41,7,4,0,0,41,12,1,0,0,0,42,43,
        7,5,0,0,43,14,1,0,0,0,44,45,7,6,0,0,45,16,1,0,0,0,46,47,7,7,0,0,
        47,18,1,0,0,0,48,49,7,8,0,0,49,20,1,0,0,0,50,54,5,34,0,0,51,53,8,
        9,0,0,52,51,1,0,0,0,53,56,1,0,0,0,54,55,1,0,0,0,54,52,1,0,0,0,55,
        57,1,0,0,0,56,54,1,0,0,0,57,75,5,34,0,0,58,62,5,39,0,0,59,61,8,10,
        0,0,60,59,1,0,0,0,61,64,1,0,0,0,62,63,1,0,0,0,62,60,1,0,0,0,63,65,
        1,0,0,0,64,62,1,0,0,0,65,75,5,39,0,0,66,70,2,8220,8221,0,67,69,8,
        11,0,0,68,67,1,0,0,0,69,72,1,0,0,0,70,71,1,0,0,0,70,68,1,0,0,0,71,
        73,1,0,0,0,72,70,1,0,0,0,73,75,2,8220,8221,0,74,50,1,0,0,0,74,58,
        1,0,0,0,74,66,1,0,0,0,75,22,1,0,0,0,76,78,8,12,0,0,77,76,1,0,0,0,
        78,79,1,0,0,0,79,77,1,0,0,0,79,80,1,0,0,0,80,24,1,0,0,0,7,0,28,54,
        62,70,74,79,1,6,0,0
    ]

class CommandParseLexer(Lexer):

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    WS = 1
    ELEMENT = 2
    COMMENTSTART = 3
    COMMANDSTART = 4
    COMMANDEND = 5
    COMMANDSEP = 6
    ASSIGNMENTOP = 7
    COMMAOP = 8
    CALLSTART = 9
    CALLEND = 10
    QUOTEDSTR = 11
    NATURALTEXT = 12

    channelNames = [ u"DEFAULT_TOKEN_CHANNEL", u"HIDDEN" ]

    modeNames = [ "DEFAULT_MODE" ]

    literalNames = [ "<INVALID>",
            "'\\u0000'" ]

    symbolicNames = [ "<INVALID>",
            "WS", "ELEMENT", "COMMENTSTART", "COMMANDSTART", "COMMANDEND", 
            "COMMANDSEP", "ASSIGNMENTOP", "COMMAOP", "CALLSTART", "CALLEND", 
            "QUOTEDSTR", "NATURALTEXT" ]

    ruleNames = [ "WS", "ELEMENT", "COMMENTSTART", "COMMANDSTART", "COMMANDEND", 
                  "COMMANDSEP", "ASSIGNMENTOP", "COMMAOP", "CALLSTART", 
                  "CALLEND", "QUOTEDSTR", "NATURALTEXT" ]

    grammarFileName = "CommandParse.g4"

    def __init__(self, input=None, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = LexerATNSimulator(self, self.atn, self.decisionsToDFA, PredictionContextCache())
        self._actions = None
        self._predicates = None


