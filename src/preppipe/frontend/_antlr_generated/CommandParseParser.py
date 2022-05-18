# Generated from CommandParse.g4 by ANTLR 4.10.1
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
        4,1,10,61,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,1,0,1,0,1,1,1,1,1,2,1,2,1,2,1,2,1,3,1,3,3,3,25,8,3,1,3,5,3,28,
        8,3,10,3,12,3,31,9,3,1,4,1,4,3,4,35,8,4,1,4,5,4,38,8,4,10,4,12,4,
        41,9,4,1,5,3,5,44,8,5,1,5,3,5,47,8,5,1,5,3,5,50,8,5,1,5,1,5,1,6,
        1,6,3,6,56,8,6,1,6,3,6,59,8,6,1,6,0,0,7,0,2,4,6,8,10,12,0,2,2,0,
        2,2,9,10,1,0,9,10,62,0,14,1,0,0,0,2,16,1,0,0,0,4,18,1,0,0,0,6,22,
        1,0,0,0,8,32,1,0,0,0,10,43,1,0,0,0,12,53,1,0,0,0,14,15,7,0,0,0,15,
        1,1,0,0,0,16,17,7,1,0,0,17,3,1,0,0,0,18,19,3,2,1,0,19,20,5,7,0,0,
        20,21,3,0,0,0,21,5,1,0,0,0,22,29,3,0,0,0,23,25,5,8,0,0,24,23,1,0,
        0,0,24,25,1,0,0,0,25,26,1,0,0,0,26,28,3,0,0,0,27,24,1,0,0,0,28,31,
        1,0,0,0,29,27,1,0,0,0,29,30,1,0,0,0,30,7,1,0,0,0,31,29,1,0,0,0,32,
        39,3,4,2,0,33,35,5,8,0,0,34,33,1,0,0,0,34,35,1,0,0,0,35,36,1,0,0,
        0,36,38,3,4,2,0,37,34,1,0,0,0,38,41,1,0,0,0,39,37,1,0,0,0,39,40,
        1,0,0,0,40,9,1,0,0,0,41,39,1,0,0,0,42,44,3,6,3,0,43,42,1,0,0,0,43,
        44,1,0,0,0,44,46,1,0,0,0,45,47,5,8,0,0,46,45,1,0,0,0,46,47,1,0,0,
        0,47,49,1,0,0,0,48,50,3,8,4,0,49,48,1,0,0,0,49,50,1,0,0,0,50,51,
        1,0,0,0,51,52,5,0,0,1,52,11,1,0,0,0,53,55,3,2,1,0,54,56,5,6,0,0,
        55,54,1,0,0,0,55,56,1,0,0,0,56,58,1,0,0,0,57,59,3,10,5,0,58,57,1,
        0,0,0,58,59,1,0,0,0,59,13,1,0,0,0,9,24,29,34,39,43,46,49,55,58
    ]

class CommandParseParser ( Parser ):

    grammarFileName = "CommandParse.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "'\\u0000'" ]

    symbolicNames = [ "<INVALID>", "WS", "ELEMENT", "COMMENTSTART", "COMMANDSTART", 
                      "COMMANDEND", "COMMANDSEP", "ASSIGNMENTOP", "COMMAOP", 
                      "QUOTEDSTR", "NATURALTEXT" ]

    RULE_value = 0
    RULE_name = 1
    RULE_kwvalue = 2
    RULE_positionals = 3
    RULE_kwargs = 4
    RULE_argumentlist = 5
    RULE_command = 6

    ruleNames =  [ "value", "name", "kwvalue", "positionals", "kwargs", 
                   "argumentlist", "command" ]

    EOF = Token.EOF
    WS=1
    ELEMENT=2
    COMMENTSTART=3
    COMMANDSTART=4
    COMMANDEND=5
    COMMANDSEP=6
    ASSIGNMENTOP=7
    COMMAOP=8
    QUOTEDSTR=9
    NATURALTEXT=10

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ValueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NATURALTEXT(self):
            return self.getToken(CommandParseParser.NATURALTEXT, 0)

        def QUOTEDSTR(self):
            return self.getToken(CommandParseParser.QUOTEDSTR, 0)

        def ELEMENT(self):
            return self.getToken(CommandParseParser.ELEMENT, 0)

        def getRuleIndex(self):
            return CommandParseParser.RULE_value

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterValue" ):
                listener.enterValue(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitValue" ):
                listener.exitValue(self)




    def value(self):

        localctx = CommandParseParser.ValueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_value)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 14
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << CommandParseParser.ELEMENT) | (1 << CommandParseParser.QUOTEDSTR) | (1 << CommandParseParser.NATURALTEXT))) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NameContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NATURALTEXT(self):
            return self.getToken(CommandParseParser.NATURALTEXT, 0)

        def QUOTEDSTR(self):
            return self.getToken(CommandParseParser.QUOTEDSTR, 0)

        def getRuleIndex(self):
            return CommandParseParser.RULE_name

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterName" ):
                listener.enterName(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitName" ):
                listener.exitName(self)




    def name(self):

        localctx = CommandParseParser.NameContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_name)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 16
            _la = self._input.LA(1)
            if not(_la==CommandParseParser.QUOTEDSTR or _la==CommandParseParser.NATURALTEXT):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class KwvalueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name(self):
            return self.getTypedRuleContext(CommandParseParser.NameContext,0)


        def ASSIGNMENTOP(self):
            return self.getToken(CommandParseParser.ASSIGNMENTOP, 0)

        def value(self):
            return self.getTypedRuleContext(CommandParseParser.ValueContext,0)


        def getRuleIndex(self):
            return CommandParseParser.RULE_kwvalue

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterKwvalue" ):
                listener.enterKwvalue(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitKwvalue" ):
                listener.exitKwvalue(self)




    def kwvalue(self):

        localctx = CommandParseParser.KwvalueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_kwvalue)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 18
            self.name()
            self.state = 19
            self.match(CommandParseParser.ASSIGNMENTOP)
            self.state = 20
            self.value()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PositionalsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def value(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(CommandParseParser.ValueContext)
            else:
                return self.getTypedRuleContext(CommandParseParser.ValueContext,i)


        def COMMAOP(self, i:int=None):
            if i is None:
                return self.getTokens(CommandParseParser.COMMAOP)
            else:
                return self.getToken(CommandParseParser.COMMAOP, i)

        def getRuleIndex(self):
            return CommandParseParser.RULE_positionals

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterPositionals" ):
                listener.enterPositionals(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitPositionals" ):
                listener.exitPositionals(self)




    def positionals(self):

        localctx = CommandParseParser.PositionalsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_positionals)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 22
            self.value()
            self.state = 29
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,1,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    self.state = 24
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==CommandParseParser.COMMAOP:
                        self.state = 23
                        self.match(CommandParseParser.COMMAOP)


                    self.state = 26
                    self.value() 
                self.state = 31
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,1,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class KwargsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def kwvalue(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(CommandParseParser.KwvalueContext)
            else:
                return self.getTypedRuleContext(CommandParseParser.KwvalueContext,i)


        def COMMAOP(self, i:int=None):
            if i is None:
                return self.getTokens(CommandParseParser.COMMAOP)
            else:
                return self.getToken(CommandParseParser.COMMAOP, i)

        def getRuleIndex(self):
            return CommandParseParser.RULE_kwargs

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterKwargs" ):
                listener.enterKwargs(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitKwargs" ):
                listener.exitKwargs(self)




    def kwargs(self):

        localctx = CommandParseParser.KwargsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_kwargs)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 32
            self.kwvalue()
            self.state = 39
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while (((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << CommandParseParser.COMMAOP) | (1 << CommandParseParser.QUOTEDSTR) | (1 << CommandParseParser.NATURALTEXT))) != 0):
                self.state = 34
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==CommandParseParser.COMMAOP:
                    self.state = 33
                    self.match(CommandParseParser.COMMAOP)


                self.state = 36
                self.kwvalue()
                self.state = 41
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArgumentlistContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def EOF(self):
            return self.getToken(CommandParseParser.EOF, 0)

        def positionals(self):
            return self.getTypedRuleContext(CommandParseParser.PositionalsContext,0)


        def COMMAOP(self):
            return self.getToken(CommandParseParser.COMMAOP, 0)

        def kwargs(self):
            return self.getTypedRuleContext(CommandParseParser.KwargsContext,0)


        def getRuleIndex(self):
            return CommandParseParser.RULE_argumentlist

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArgumentlist" ):
                listener.enterArgumentlist(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArgumentlist" ):
                listener.exitArgumentlist(self)




    def argumentlist(self):

        localctx = CommandParseParser.ArgumentlistContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_argumentlist)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 43
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,4,self._ctx)
            if la_ == 1:
                self.state = 42
                self.positionals()


            self.state = 46
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==CommandParseParser.COMMAOP:
                self.state = 45
                self.match(CommandParseParser.COMMAOP)


            self.state = 49
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==CommandParseParser.QUOTEDSTR or _la==CommandParseParser.NATURALTEXT:
                self.state = 48
                self.kwargs()


            self.state = 51
            self.match(CommandParseParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class CommandContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name(self):
            return self.getTypedRuleContext(CommandParseParser.NameContext,0)


        def COMMANDSEP(self):
            return self.getToken(CommandParseParser.COMMANDSEP, 0)

        def argumentlist(self):
            return self.getTypedRuleContext(CommandParseParser.ArgumentlistContext,0)


        def getRuleIndex(self):
            return CommandParseParser.RULE_command

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterCommand" ):
                listener.enterCommand(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitCommand" ):
                listener.exitCommand(self)




    def command(self):

        localctx = CommandParseParser.CommandContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_command)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 53
            self.name()
            self.state = 55
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==CommandParseParser.COMMANDSEP:
                self.state = 54
                self.match(CommandParseParser.COMMANDSEP)


            self.state = 58
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,8,self._ctx)
            if la_ == 1:
                self.state = 57
                self.argumentlist()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





