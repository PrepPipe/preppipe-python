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
        4,1,12,70,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,1,0,1,0,1,1,1,1,1,1,1,1,1,1,1,2,1,2,3,
        2,30,8,2,1,3,1,3,1,4,1,4,1,4,1,4,1,5,1,5,3,5,40,8,5,4,5,42,8,5,11,
        5,12,5,43,1,6,1,6,3,6,48,8,6,4,6,50,8,6,11,6,12,6,51,1,7,3,7,55,
        8,7,1,7,3,7,58,8,7,1,8,1,8,1,8,1,9,1,9,3,9,65,8,9,1,9,3,9,68,8,9,
        1,9,0,0,10,0,2,4,6,8,10,12,14,16,18,0,2,2,0,2,2,11,12,1,0,11,12,
        68,0,20,1,0,0,0,2,22,1,0,0,0,4,29,1,0,0,0,6,31,1,0,0,0,8,33,1,0,
        0,0,10,41,1,0,0,0,12,49,1,0,0,0,14,54,1,0,0,0,16,59,1,0,0,0,18,62,
        1,0,0,0,20,21,7,0,0,0,21,1,1,0,0,0,22,23,3,6,3,0,23,24,5,9,0,0,24,
        25,3,14,7,0,25,26,5,10,0,0,26,3,1,0,0,0,27,30,3,0,0,0,28,30,3,2,
        1,0,29,27,1,0,0,0,29,28,1,0,0,0,30,5,1,0,0,0,31,32,7,1,0,0,32,7,
        1,0,0,0,33,34,3,6,3,0,34,35,5,7,0,0,35,36,3,4,2,0,36,9,1,0,0,0,37,
        39,3,4,2,0,38,40,5,8,0,0,39,38,1,0,0,0,39,40,1,0,0,0,40,42,1,0,0,
        0,41,37,1,0,0,0,42,43,1,0,0,0,43,41,1,0,0,0,43,44,1,0,0,0,44,11,
        1,0,0,0,45,47,3,8,4,0,46,48,5,8,0,0,47,46,1,0,0,0,47,48,1,0,0,0,
        48,50,1,0,0,0,49,45,1,0,0,0,50,51,1,0,0,0,51,49,1,0,0,0,51,52,1,
        0,0,0,52,13,1,0,0,0,53,55,3,10,5,0,54,53,1,0,0,0,54,55,1,0,0,0,55,
        57,1,0,0,0,56,58,3,12,6,0,57,56,1,0,0,0,57,58,1,0,0,0,58,15,1,0,
        0,0,59,60,3,14,7,0,60,61,5,0,0,1,61,17,1,0,0,0,62,64,3,6,3,0,63,
        65,5,6,0,0,64,63,1,0,0,0,64,65,1,0,0,0,65,67,1,0,0,0,66,68,3,16,
        8,0,67,66,1,0,0,0,67,68,1,0,0,0,68,19,1,0,0,0,9,29,39,43,47,51,54,
        57,64,67
    ]

class CommandParseParser ( Parser ):

    grammarFileName = "CommandParse.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "'\\u0000'" ]

    symbolicNames = [ "<INVALID>", "WS", "ELEMENT", "COMMENTSTART", "COMMANDSTART", 
                      "COMMANDEND", "COMMANDSEP", "ASSIGNMENTOP", "COMMAOP", 
                      "CALLSTART", "CALLEND", "QUOTEDSTR", "NATURALTEXT" ]

    RULE_evalue = 0
    RULE_callexpr = 1
    RULE_value = 2
    RULE_name = 3
    RULE_kwvalue = 4
    RULE_positionals = 5
    RULE_kwargs = 6
    RULE_arguments = 7
    RULE_argumentlist = 8
    RULE_command = 9

    ruleNames =  [ "evalue", "callexpr", "value", "name", "kwvalue", "positionals", 
                   "kwargs", "arguments", "argumentlist", "command" ]

    EOF = Token.EOF
    WS=1
    ELEMENT=2
    COMMENTSTART=3
    COMMANDSTART=4
    COMMANDEND=5
    COMMANDSEP=6
    ASSIGNMENTOP=7
    COMMAOP=8
    CALLSTART=9
    CALLEND=10
    QUOTEDSTR=11
    NATURALTEXT=12

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class EvalueContext(ParserRuleContext):
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
            return CommandParseParser.RULE_evalue

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterEvalue" ):
                listener.enterEvalue(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitEvalue" ):
                listener.exitEvalue(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitEvalue" ):
                return visitor.visitEvalue(self)
            else:
                return visitor.visitChildren(self)




    def evalue(self):

        localctx = CommandParseParser.EvalueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_evalue)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 20
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


    class CallexprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def name(self):
            return self.getTypedRuleContext(CommandParseParser.NameContext,0)


        def CALLSTART(self):
            return self.getToken(CommandParseParser.CALLSTART, 0)

        def arguments(self):
            return self.getTypedRuleContext(CommandParseParser.ArgumentsContext,0)


        def CALLEND(self):
            return self.getToken(CommandParseParser.CALLEND, 0)

        def getRuleIndex(self):
            return CommandParseParser.RULE_callexpr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterCallexpr" ):
                listener.enterCallexpr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitCallexpr" ):
                listener.exitCallexpr(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCallexpr" ):
                return visitor.visitCallexpr(self)
            else:
                return visitor.visitChildren(self)




    def callexpr(self):

        localctx = CommandParseParser.CallexprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_callexpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 22
            self.name()
            self.state = 23
            self.match(CommandParseParser.CALLSTART)
            self.state = 24
            self.arguments()
            self.state = 25
            self.match(CommandParseParser.CALLEND)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ValueContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def evalue(self):
            return self.getTypedRuleContext(CommandParseParser.EvalueContext,0)


        def callexpr(self):
            return self.getTypedRuleContext(CommandParseParser.CallexprContext,0)


        def getRuleIndex(self):
            return CommandParseParser.RULE_value

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterValue" ):
                listener.enterValue(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitValue" ):
                listener.exitValue(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitValue" ):
                return visitor.visitValue(self)
            else:
                return visitor.visitChildren(self)




    def value(self):

        localctx = CommandParseParser.ValueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_value)
        try:
            self.state = 29
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,0,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 27
                self.evalue()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 28
                self.callexpr()
                pass


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

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitName" ):
                return visitor.visitName(self)
            else:
                return visitor.visitChildren(self)




    def name(self):

        localctx = CommandParseParser.NameContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_name)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 31
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

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitKwvalue" ):
                return visitor.visitKwvalue(self)
            else:
                return visitor.visitChildren(self)




    def kwvalue(self):

        localctx = CommandParseParser.KwvalueContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_kwvalue)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 33
            self.name()
            self.state = 34
            self.match(CommandParseParser.ASSIGNMENTOP)
            self.state = 35
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

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPositionals" ):
                return visitor.visitPositionals(self)
            else:
                return visitor.visitChildren(self)




    def positionals(self):

        localctx = CommandParseParser.PositionalsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_positionals)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 41 
            self._errHandler.sync(self)
            _alt = 1
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt == 1:
                    self.state = 37
                    self.value()
                    self.state = 39
                    self._errHandler.sync(self)
                    _la = self._input.LA(1)
                    if _la==CommandParseParser.COMMAOP:
                        self.state = 38
                        self.match(CommandParseParser.COMMAOP)



                else:
                    raise NoViableAltException(self)
                self.state = 43 
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,2,self._ctx)

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

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitKwargs" ):
                return visitor.visitKwargs(self)
            else:
                return visitor.visitChildren(self)




    def kwargs(self):

        localctx = CommandParseParser.KwargsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_kwargs)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 49 
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while True:
                self.state = 45
                self.kwvalue()
                self.state = 47
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==CommandParseParser.COMMAOP:
                    self.state = 46
                    self.match(CommandParseParser.COMMAOP)


                self.state = 51 
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if not (_la==CommandParseParser.QUOTEDSTR or _la==CommandParseParser.NATURALTEXT):
                    break

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArgumentsContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def positionals(self):
            return self.getTypedRuleContext(CommandParseParser.PositionalsContext,0)


        def kwargs(self):
            return self.getTypedRuleContext(CommandParseParser.KwargsContext,0)


        def getRuleIndex(self):
            return CommandParseParser.RULE_arguments

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArguments" ):
                listener.enterArguments(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArguments" ):
                listener.exitArguments(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArguments" ):
                return visitor.visitArguments(self)
            else:
                return visitor.visitChildren(self)




    def arguments(self):

        localctx = CommandParseParser.ArgumentsContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_arguments)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 54
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,5,self._ctx)
            if la_ == 1:
                self.state = 53
                self.positionals()


            self.state = 57
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==CommandParseParser.QUOTEDSTR or _la==CommandParseParser.NATURALTEXT:
                self.state = 56
                self.kwargs()


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

        def arguments(self):
            return self.getTypedRuleContext(CommandParseParser.ArgumentsContext,0)


        def EOF(self):
            return self.getToken(CommandParseParser.EOF, 0)

        def getRuleIndex(self):
            return CommandParseParser.RULE_argumentlist

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterArgumentlist" ):
                listener.enterArgumentlist(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitArgumentlist" ):
                listener.exitArgumentlist(self)

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArgumentlist" ):
                return visitor.visitArgumentlist(self)
            else:
                return visitor.visitChildren(self)




    def argumentlist(self):

        localctx = CommandParseParser.ArgumentlistContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_argumentlist)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 59
            self.arguments()
            self.state = 60
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

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitCommand" ):
                return visitor.visitCommand(self)
            else:
                return visitor.visitChildren(self)




    def command(self):

        localctx = CommandParseParser.CommandContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_command)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 62
            self.name()
            self.state = 64
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==CommandParseParser.COMMANDSEP:
                self.state = 63
                self.match(CommandParseParser.COMMANDSEP)


            self.state = 67
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,8,self._ctx)
            if la_ == 1:
                self.state = 66
                self.argumentlist()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





