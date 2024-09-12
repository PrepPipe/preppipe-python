# Generated from CommandScan.g4 by ANTLR 4.10.1
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,6,27,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,1,0,1,0,1,0,1,0,1,1,5,1,
        14,8,1,10,1,12,1,17,9,1,1,2,4,2,20,8,2,11,2,12,2,21,1,3,1,3,1,3,
        1,3,0,0,4,0,2,4,6,0,1,2,0,2,3,6,6,24,0,8,1,0,0,0,2,15,1,0,0,0,4,
        19,1,0,0,0,6,23,1,0,0,0,8,9,5,4,0,0,9,10,3,2,1,0,10,11,5,5,0,0,11,
        1,1,0,0,0,12,14,7,0,0,0,13,12,1,0,0,0,14,17,1,0,0,0,15,13,1,0,0,
        0,15,16,1,0,0,0,16,3,1,0,0,0,17,15,1,0,0,0,18,20,3,0,0,0,19,18,1,
        0,0,0,20,21,1,0,0,0,21,19,1,0,0,0,21,22,1,0,0,0,22,5,1,0,0,0,23,
        24,3,4,2,0,24,25,5,0,0,1,25,7,1,0,0,0,2,15,21
    ]

class CommandScanParser ( Parser ):

    grammarFileName = "CommandScan.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "'\\u0000'" ]

    symbolicNames = [ "<INVALID>", "WS", "QUOTEDSTR", "ELEMENT", "COMMANDSTART", 
                      "COMMANDEND", "NORMALTEXT" ]

    RULE_command = 0
    RULE_body = 1
    RULE_commands = 2
    RULE_line = 3

    ruleNames =  [ "command", "body", "commands", "line" ]

    EOF = Token.EOF
    WS=1
    QUOTEDSTR=2
    ELEMENT=3
    COMMANDSTART=4
    COMMANDEND=5
    NORMALTEXT=6

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class CommandContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def COMMANDSTART(self):
            return self.getToken(CommandScanParser.COMMANDSTART, 0)

        def body(self):
            return self.getTypedRuleContext(CommandScanParser.BodyContext,0)


        def COMMANDEND(self):
            return self.getToken(CommandScanParser.COMMANDEND, 0)

        def getRuleIndex(self):
            return CommandScanParser.RULE_command

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterCommand" ):
                listener.enterCommand(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitCommand" ):
                listener.exitCommand(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCommand" ):
                return visitor.visitCommand(self)
            else:
                return visitor.visitChildren(self)




    def command(self):

        localctx = CommandScanParser.CommandContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_command)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 8
            self.match(CommandScanParser.COMMANDSTART)
            self.state = 9
            self.body()
            self.state = 10
            self.match(CommandScanParser.COMMANDEND)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class BodyContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def QUOTEDSTR(self, i:int=None):
            if i is None:
                return self.getTokens(CommandScanParser.QUOTEDSTR)
            else:
                return self.getToken(CommandScanParser.QUOTEDSTR, i)

        def ELEMENT(self, i:int=None):
            if i is None:
                return self.getTokens(CommandScanParser.ELEMENT)
            else:
                return self.getToken(CommandScanParser.ELEMENT, i)

        def NORMALTEXT(self, i:int=None):
            if i is None:
                return self.getTokens(CommandScanParser.NORMALTEXT)
            else:
                return self.getToken(CommandScanParser.NORMALTEXT, i)

        def getRuleIndex(self):
            return CommandScanParser.RULE_body

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBody" ):
                listener.enterBody(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBody" ):
                listener.exitBody(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitBody" ):
                return visitor.visitBody(self)
            else:
                return visitor.visitChildren(self)




    def body(self):

        localctx = CommandScanParser.BodyContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_body)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 15
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << CommandScanParser.QUOTEDSTR) | (1 << CommandScanParser.ELEMENT) | (1 << CommandScanParser.NORMALTEXT))) != 0):
                self.state = 12
                _la = self._input.LA(1)
                if not((((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << CommandScanParser.QUOTEDSTR) | (1 << CommandScanParser.ELEMENT) | (1 << CommandScanParser.NORMALTEXT))) != 0)):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 17
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CommandsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def command(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(CommandScanParser.CommandContext)
            else:
                return self.getTypedRuleContext(CommandScanParser.CommandContext,i)


        def getRuleIndex(self):
            return CommandScanParser.RULE_commands

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterCommands" ):
                listener.enterCommands(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitCommands" ):
                listener.exitCommands(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCommands" ):
                return visitor.visitCommands(self)
            else:
                return visitor.visitChildren(self)




    def commands(self):

        localctx = CommandScanParser.CommandsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_commands)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 19 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 18
                self.command()
                self.state = 21 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==CommandScanParser.COMMANDSTART):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LineContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def commands(self):
            return self.getTypedRuleContext(CommandScanParser.CommandsContext,0)


        def EOF(self):
            return self.getToken(CommandScanParser.EOF, 0)

        def getRuleIndex(self):
            return CommandScanParser.RULE_line

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterLine" ):
                listener.enterLine(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitLine" ):
                listener.exitLine(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLine" ):
                return visitor.visitLine(self)
            else:
                return visitor.visitChildren(self)




    def line(self):

        localctx = CommandScanParser.LineContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_line)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 23
            self.commands()
            self.state = 24
            self.match(CommandScanParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





