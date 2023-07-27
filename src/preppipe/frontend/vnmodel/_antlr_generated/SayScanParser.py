# Generated from SayScan.g4 by ANTLR 4.10.1
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
        4,1,8,75,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,1,0,1,0,
        1,0,1,0,5,0,17,8,0,10,0,12,0,20,9,0,1,0,1,0,1,1,1,1,1,2,1,2,1,3,
        1,3,5,3,30,8,3,10,3,12,3,33,9,3,1,4,1,4,1,5,3,5,38,8,5,1,5,1,5,3,
        5,42,8,5,1,5,1,5,1,5,1,5,3,5,48,8,5,1,5,3,5,51,8,5,1,5,1,5,1,5,1,
        5,1,5,1,5,3,5,59,8,5,1,5,1,5,1,5,1,5,3,5,65,8,5,1,5,3,5,68,8,5,1,
        5,1,5,1,5,3,5,73,8,5,1,5,2,18,31,0,6,0,2,4,6,8,10,0,3,2,0,2,2,8,
        8,2,0,2,2,7,8,1,0,2,8,80,0,12,1,0,0,0,2,23,1,0,0,0,4,25,1,0,0,0,
        6,27,1,0,0,0,8,34,1,0,0,0,10,72,1,0,0,0,12,13,5,4,0,0,13,18,5,8,
        0,0,14,15,5,6,0,0,15,17,5,8,0,0,16,14,1,0,0,0,17,20,1,0,0,0,18,19,
        1,0,0,0,18,16,1,0,0,0,19,21,1,0,0,0,20,18,1,0,0,0,21,22,5,5,0,0,
        22,1,1,0,0,0,23,24,7,0,0,0,24,3,1,0,0,0,25,26,5,2,0,0,26,5,1,0,0,
        0,27,31,7,1,0,0,28,30,7,2,0,0,29,28,1,0,0,0,30,33,1,0,0,0,31,32,
        1,0,0,0,31,29,1,0,0,0,32,7,1,0,0,0,33,31,1,0,0,0,34,35,5,2,0,0,35,
        9,1,0,0,0,36,38,3,2,1,0,37,36,1,0,0,0,37,38,1,0,0,0,38,39,1,0,0,
        0,39,41,5,3,0,0,40,42,3,0,0,0,41,40,1,0,0,0,41,42,1,0,0,0,42,43,
        1,0,0,0,43,44,3,6,3,0,44,45,5,0,0,1,45,73,1,0,0,0,46,48,3,2,1,0,
        47,46,1,0,0,0,47,48,1,0,0,0,48,50,1,0,0,0,49,51,3,0,0,0,50,49,1,
        0,0,0,50,51,1,0,0,0,51,52,1,0,0,0,52,53,5,3,0,0,53,54,3,6,3,0,54,
        55,5,0,0,1,55,73,1,0,0,0,56,58,3,2,1,0,57,59,3,0,0,0,58,57,1,0,0,
        0,58,59,1,0,0,0,59,60,1,0,0,0,60,61,3,8,4,0,61,62,5,0,0,1,62,73,
        1,0,0,0,63,65,3,4,2,0,64,63,1,0,0,0,64,65,1,0,0,0,65,67,1,0,0,0,
        66,68,3,0,0,0,67,66,1,0,0,0,67,68,1,0,0,0,68,69,1,0,0,0,69,70,3,
        6,3,0,70,71,5,0,0,1,71,73,1,0,0,0,72,37,1,0,0,0,72,47,1,0,0,0,72,
        56,1,0,0,0,72,64,1,0,0,0,73,11,1,0,0,0,10,18,31,37,41,47,50,58,64,
        67,72
    ]

class SayScanParser ( Parser ):

    grammarFileName = "SayScan.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [  ]

    symbolicNames = [ "<INVALID>", "WS", "QUOTEDSTR", "SAYSEPARATOR", "STATUSSTART", 
                      "STATUSEND", "COMMASPLITTER", "SENTENCESPLITTER", 
                      "NORMALTEXT" ]

    RULE_statusexpr = 0
    RULE_nameexpr = 1
    RULE_nameexpr_strong = 2
    RULE_contentexpr = 3
    RULE_contentexpr_strong = 4
    RULE_sayexpr = 5

    ruleNames =  [ "statusexpr", "nameexpr", "nameexpr_strong", "contentexpr", 
                   "contentexpr_strong", "sayexpr" ]

    EOF = Token.EOF
    WS=1
    QUOTEDSTR=2
    SAYSEPARATOR=3
    STATUSSTART=4
    STATUSEND=5
    COMMASPLITTER=6
    SENTENCESPLITTER=7
    NORMALTEXT=8

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.10.1")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class StatusexprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STATUSSTART(self):
            return self.getToken(SayScanParser.STATUSSTART, 0)

        def NORMALTEXT(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.NORMALTEXT)
            else:
                return self.getToken(SayScanParser.NORMALTEXT, i)

        def STATUSEND(self):
            return self.getToken(SayScanParser.STATUSEND, 0)

        def COMMASPLITTER(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.COMMASPLITTER)
            else:
                return self.getToken(SayScanParser.COMMASPLITTER, i)

        def getRuleIndex(self):
            return SayScanParser.RULE_statusexpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitStatusexpr" ):
                return visitor.visitStatusexpr(self)
            else:
                return visitor.visitChildren(self)




    def statusexpr(self):

        localctx = SayScanParser.StatusexprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_statusexpr)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 12
            self.match(SayScanParser.STATUSSTART)
            self.state = 13
            self.match(SayScanParser.NORMALTEXT)
            self.state = 18
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,0,self._ctx)
            while _alt!=1 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1+1:
                    self.state = 14
                    self.match(SayScanParser.COMMASPLITTER)
                    self.state = 15
                    self.match(SayScanParser.NORMALTEXT) 
                self.state = 20
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,0,self._ctx)

            self.state = 21
            self.match(SayScanParser.STATUSEND)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class NameexprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def QUOTEDSTR(self):
            return self.getToken(SayScanParser.QUOTEDSTR, 0)

        def NORMALTEXT(self):
            return self.getToken(SayScanParser.NORMALTEXT, 0)

        def getRuleIndex(self):
            return SayScanParser.RULE_nameexpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitNameexpr" ):
                return visitor.visitNameexpr(self)
            else:
                return visitor.visitChildren(self)




    def nameexpr(self):

        localctx = SayScanParser.NameexprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_nameexpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 23
            _la = self._input.LA(1)
            if not(_la==SayScanParser.QUOTEDSTR or _la==SayScanParser.NORMALTEXT):
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


    class Nameexpr_strongContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def QUOTEDSTR(self):
            return self.getToken(SayScanParser.QUOTEDSTR, 0)

        def getRuleIndex(self):
            return SayScanParser.RULE_nameexpr_strong

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitNameexpr_strong" ):
                return visitor.visitNameexpr_strong(self)
            else:
                return visitor.visitChildren(self)




    def nameexpr_strong(self):

        localctx = SayScanParser.Nameexpr_strongContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_nameexpr_strong)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 25
            self.match(SayScanParser.QUOTEDSTR)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ContentexprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def QUOTEDSTR(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.QUOTEDSTR)
            else:
                return self.getToken(SayScanParser.QUOTEDSTR, i)

        def NORMALTEXT(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.NORMALTEXT)
            else:
                return self.getToken(SayScanParser.NORMALTEXT, i)

        def SENTENCESPLITTER(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.SENTENCESPLITTER)
            else:
                return self.getToken(SayScanParser.SENTENCESPLITTER, i)

        def STATUSSTART(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.STATUSSTART)
            else:
                return self.getToken(SayScanParser.STATUSSTART, i)

        def STATUSEND(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.STATUSEND)
            else:
                return self.getToken(SayScanParser.STATUSEND, i)

        def SAYSEPARATOR(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.SAYSEPARATOR)
            else:
                return self.getToken(SayScanParser.SAYSEPARATOR, i)

        def COMMASPLITTER(self, i:int=None):
            if i is None:
                return self.getTokens(SayScanParser.COMMASPLITTER)
            else:
                return self.getToken(SayScanParser.COMMASPLITTER, i)

        def getRuleIndex(self):
            return SayScanParser.RULE_contentexpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitContentexpr" ):
                return visitor.visitContentexpr(self)
            else:
                return visitor.visitChildren(self)




    def contentexpr(self):

        localctx = SayScanParser.ContentexprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_contentexpr)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 27
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << SayScanParser.QUOTEDSTR) | (1 << SayScanParser.SENTENCESPLITTER) | (1 << SayScanParser.NORMALTEXT))) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
            self.state = 31
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,1,self._ctx)
            while _alt!=1 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1+1:
                    self.state = 28
                    _la = self._input.LA(1)
                    if not((((_la) & ~0x3f) == 0 and ((1 << _la) & ((1 << SayScanParser.QUOTEDSTR) | (1 << SayScanParser.SAYSEPARATOR) | (1 << SayScanParser.STATUSSTART) | (1 << SayScanParser.STATUSEND) | (1 << SayScanParser.COMMASPLITTER) | (1 << SayScanParser.SENTENCESPLITTER) | (1 << SayScanParser.NORMALTEXT))) != 0)):
                        self._errHandler.recoverInline(self)
                    else:
                        self._errHandler.reportMatch(self)
                        self.consume() 
                self.state = 33
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,1,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class Contentexpr_strongContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def QUOTEDSTR(self):
            return self.getToken(SayScanParser.QUOTEDSTR, 0)

        def getRuleIndex(self):
            return SayScanParser.RULE_contentexpr_strong

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitContentexpr_strong" ):
                return visitor.visitContentexpr_strong(self)
            else:
                return visitor.visitChildren(self)




    def contentexpr_strong(self):

        localctx = SayScanParser.Contentexpr_strongContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_contentexpr_strong)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 34
            self.match(SayScanParser.QUOTEDSTR)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SayexprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def SAYSEPARATOR(self):
            return self.getToken(SayScanParser.SAYSEPARATOR, 0)

        def contentexpr(self):
            return self.getTypedRuleContext(SayScanParser.ContentexprContext,0)


        def EOF(self):
            return self.getToken(SayScanParser.EOF, 0)

        def nameexpr(self):
            return self.getTypedRuleContext(SayScanParser.NameexprContext,0)


        def statusexpr(self):
            return self.getTypedRuleContext(SayScanParser.StatusexprContext,0)


        def contentexpr_strong(self):
            return self.getTypedRuleContext(SayScanParser.Contentexpr_strongContext,0)


        def nameexpr_strong(self):
            return self.getTypedRuleContext(SayScanParser.Nameexpr_strongContext,0)


        def getRuleIndex(self):
            return SayScanParser.RULE_sayexpr

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSayexpr" ):
                return visitor.visitSayexpr(self)
            else:
                return visitor.visitChildren(self)




    def sayexpr(self):

        localctx = SayScanParser.SayexprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_sayexpr)
        self._la = 0 # Token type
        try:
            self.state = 72
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,9,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 37
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==SayScanParser.QUOTEDSTR or _la==SayScanParser.NORMALTEXT:
                    self.state = 36
                    self.nameexpr()


                self.state = 39
                self.match(SayScanParser.SAYSEPARATOR)
                self.state = 41
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==SayScanParser.STATUSSTART:
                    self.state = 40
                    self.statusexpr()


                self.state = 43
                self.contentexpr()
                self.state = 44
                self.match(SayScanParser.EOF)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 47
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==SayScanParser.QUOTEDSTR or _la==SayScanParser.NORMALTEXT:
                    self.state = 46
                    self.nameexpr()


                self.state = 50
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==SayScanParser.STATUSSTART:
                    self.state = 49
                    self.statusexpr()


                self.state = 52
                self.match(SayScanParser.SAYSEPARATOR)
                self.state = 53
                self.contentexpr()
                self.state = 54
                self.match(SayScanParser.EOF)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 56
                self.nameexpr()
                self.state = 58
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==SayScanParser.STATUSSTART:
                    self.state = 57
                    self.statusexpr()


                self.state = 60
                self.contentexpr_strong()
                self.state = 61
                self.match(SayScanParser.EOF)
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 64
                self._errHandler.sync(self)
                la_ = self._interp.adaptivePredict(self._input,7,self._ctx)
                if la_ == 1:
                    self.state = 63
                    self.nameexpr_strong()


                self.state = 67
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==SayScanParser.STATUSSTART:
                    self.state = 66
                    self.statusexpr()


                self.state = 69
                self.contentexpr()
                self.state = 70
                self.match(SayScanParser.EOF)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





