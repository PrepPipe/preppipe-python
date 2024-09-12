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
        4,0,11,77,6,-1,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,
        6,7,6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,1,0,4,0,25,8,0,11,0,12,0,
        26,1,0,1,0,1,1,1,1,1,2,1,2,1,3,1,3,1,4,1,4,1,5,1,5,1,6,1,6,1,7,1,
        7,1,8,1,8,1,9,1,9,5,9,49,8,9,10,9,12,9,52,9,9,1,9,1,9,1,9,5,9,57,
        8,9,10,9,12,9,60,9,9,1,9,1,9,1,9,5,9,65,8,9,10,9,12,9,68,9,9,1,9,
        3,9,71,8,9,1,10,4,10,74,8,10,11,10,12,10,75,3,50,58,66,0,11,1,1,
        3,2,5,3,7,4,9,5,11,6,13,7,15,8,17,9,19,10,21,11,1,0,12,9,0,9,10,
        13,13,32,32,160,160,8192,8203,8239,8239,8287,8287,12288,12288,65279,
        65279,2,0,91,91,12304,12304,2,0,93,93,12305,12305,2,0,58,58,65306,
        65306,2,0,61,61,65309,65309,2,0,44,44,65292,65292,2,0,40,40,65288,
        65288,2,0,41,41,65289,65289,1,0,34,34,1,0,39,39,1,0,8220,8221,22,
        0,9,10,13,13,32,32,34,34,39,41,44,44,58,58,61,61,91,91,93,93,160,
        160,8192,8203,8220,8221,8239,8239,8287,8287,12288,12288,12304,12305,
        65279,65279,65288,65289,65292,65292,65306,65306,65309,65309,83,0,
        1,1,0,0,0,0,3,1,0,0,0,0,5,1,0,0,0,0,7,1,0,0,0,0,9,1,0,0,0,0,11,1,
        0,0,0,0,13,1,0,0,0,0,15,1,0,0,0,0,17,1,0,0,0,0,19,1,0,0,0,0,21,1,
        0,0,0,1,24,1,0,0,0,3,30,1,0,0,0,5,32,1,0,0,0,7,34,1,0,0,0,9,36,1,
        0,0,0,11,38,1,0,0,0,13,40,1,0,0,0,15,42,1,0,0,0,17,44,1,0,0,0,19,
        70,1,0,0,0,21,73,1,0,0,0,23,25,7,0,0,0,24,23,1,0,0,0,25,26,1,0,0,
        0,26,24,1,0,0,0,26,27,1,0,0,0,27,28,1,0,0,0,28,29,6,0,0,0,29,2,1,
        0,0,0,30,31,5,0,0,0,31,4,1,0,0,0,32,33,7,1,0,0,33,6,1,0,0,0,34,35,
        7,2,0,0,35,8,1,0,0,0,36,37,7,3,0,0,37,10,1,0,0,0,38,39,7,4,0,0,39,
        12,1,0,0,0,40,41,7,5,0,0,41,14,1,0,0,0,42,43,7,6,0,0,43,16,1,0,0,
        0,44,45,7,7,0,0,45,18,1,0,0,0,46,50,5,34,0,0,47,49,8,8,0,0,48,47,
        1,0,0,0,49,52,1,0,0,0,50,51,1,0,0,0,50,48,1,0,0,0,51,53,1,0,0,0,
        52,50,1,0,0,0,53,71,5,34,0,0,54,58,5,39,0,0,55,57,8,9,0,0,56,55,
        1,0,0,0,57,60,1,0,0,0,58,59,1,0,0,0,58,56,1,0,0,0,59,61,1,0,0,0,
        60,58,1,0,0,0,61,71,5,39,0,0,62,66,2,8220,8221,0,63,65,8,10,0,0,
        64,63,1,0,0,0,65,68,1,0,0,0,66,67,1,0,0,0,66,64,1,0,0,0,67,69,1,
        0,0,0,68,66,1,0,0,0,69,71,2,8220,8221,0,70,46,1,0,0,0,70,54,1,0,
        0,0,70,62,1,0,0,0,71,20,1,0,0,0,72,74,8,11,0,0,73,72,1,0,0,0,74,
        75,1,0,0,0,75,73,1,0,0,0,75,76,1,0,0,0,76,22,1,0,0,0,7,0,26,50,58,
        66,70,75,1,6,0,0
    ]

class CommandParseLexer(Lexer):

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    WS = 1
    ELEMENT = 2
    COMMANDSTART = 3
    COMMANDEND = 4
    COMMANDSEP = 5
    ASSIGNMENTOP = 6
    COMMAOP = 7
    CALLSTART = 8
    CALLEND = 9
    QUOTEDSTR = 10
    NATURALTEXT = 11

    channelNames = [ u"DEFAULT_TOKEN_CHANNEL", u"HIDDEN" ]

    modeNames = [ "DEFAULT_MODE" ]

    literalNames = [ "<INVALID>",
            "'\\u0000'" ]

    symbolicNames = [ "<INVALID>",
            "WS", "ELEMENT", "COMMANDSTART", "COMMANDEND", "COMMANDSEP", 
            "ASSIGNMENTOP", "COMMAOP", "CALLSTART", "CALLEND", "QUOTEDSTR", 
            "NATURALTEXT" ]

    ruleNames = [ "WS", "ELEMENT", "COMMANDSTART", "COMMANDEND", "COMMANDSEP", 
                  "ASSIGNMENTOP", "COMMAOP", "CALLSTART", "CALLEND", "QUOTEDSTR", 
                  "NATURALTEXT" ]

    grammarFileName = "CommandParse.g4"

    def __init__(self, input=None, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = LexerATNSimulator(self, self.atn, self.decisionsToDFA, PredictionContextCache())
        self._actions = None
        self._predicates = None


