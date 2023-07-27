# Generated from SayScan.g4 by ANTLR 4.10.1
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .SayScanParser import SayScanParser
else:
    from SayScanParser import SayScanParser

# This class defines a complete generic visitor for a parse tree produced by SayScanParser.

class SayScanVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by SayScanParser#statusexpr.
    def visitStatusexpr(self, ctx:SayScanParser.StatusexprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SayScanParser#nameexpr.
    def visitNameexpr(self, ctx:SayScanParser.NameexprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SayScanParser#nameexpr_strong.
    def visitNameexpr_strong(self, ctx:SayScanParser.Nameexpr_strongContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SayScanParser#contentexpr.
    def visitContentexpr(self, ctx:SayScanParser.ContentexprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SayScanParser#contentexpr_strong.
    def visitContentexpr_strong(self, ctx:SayScanParser.Contentexpr_strongContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SayScanParser#sayexpr.
    def visitSayexpr(self, ctx:SayScanParser.SayexprContext):
        return self.visitChildren(ctx)



del SayScanParser