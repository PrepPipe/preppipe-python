# Generated from CommandParse.g4 by ANTLR 4.10.1
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .CommandParseParser import CommandParseParser
else:
    from CommandParseParser import CommandParseParser

# This class defines a complete generic visitor for a parse tree produced by CommandParseParser.

class CommandParseVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by CommandParseParser#evalue.
    def visitEvalue(self, ctx:CommandParseParser.EvalueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#callexpr.
    def visitCallexpr(self, ctx:CommandParseParser.CallexprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#value.
    def visitValue(self, ctx:CommandParseParser.ValueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#name.
    def visitName(self, ctx:CommandParseParser.NameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#kwvalue.
    def visitKwvalue(self, ctx:CommandParseParser.KwvalueContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#positionals.
    def visitPositionals(self, ctx:CommandParseParser.PositionalsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#kwargs.
    def visitKwargs(self, ctx:CommandParseParser.KwargsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#arguments.
    def visitArguments(self, ctx:CommandParseParser.ArgumentsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#argumentlist.
    def visitArgumentlist(self, ctx:CommandParseParser.ArgumentlistContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by CommandParseParser#command.
    def visitCommand(self, ctx:CommandParseParser.CommandContext):
        return self.visitChildren(ctx)



del CommandParseParser