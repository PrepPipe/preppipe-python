# Generated from CommandParse.g4 by ANTLR 4.10.1
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .CommandParseParser import CommandParseParser
else:
    from CommandParseParser import CommandParseParser

# This class defines a complete listener for a parse tree produced by CommandParseParser.
class CommandParseListener(ParseTreeListener):

    # Enter a parse tree produced by CommandParseParser#evalue.
    def enterEvalue(self, ctx:CommandParseParser.EvalueContext):
        pass

    # Exit a parse tree produced by CommandParseParser#evalue.
    def exitEvalue(self, ctx:CommandParseParser.EvalueContext):
        pass


    # Enter a parse tree produced by CommandParseParser#callexpr.
    def enterCallexpr(self, ctx:CommandParseParser.CallexprContext):
        pass

    # Exit a parse tree produced by CommandParseParser#callexpr.
    def exitCallexpr(self, ctx:CommandParseParser.CallexprContext):
        pass


    # Enter a parse tree produced by CommandParseParser#value.
    def enterValue(self, ctx:CommandParseParser.ValueContext):
        pass

    # Exit a parse tree produced by CommandParseParser#value.
    def exitValue(self, ctx:CommandParseParser.ValueContext):
        pass


    # Enter a parse tree produced by CommandParseParser#name.
    def enterName(self, ctx:CommandParseParser.NameContext):
        pass

    # Exit a parse tree produced by CommandParseParser#name.
    def exitName(self, ctx:CommandParseParser.NameContext):
        pass


    # Enter a parse tree produced by CommandParseParser#kwvalue.
    def enterKwvalue(self, ctx:CommandParseParser.KwvalueContext):
        pass

    # Exit a parse tree produced by CommandParseParser#kwvalue.
    def exitKwvalue(self, ctx:CommandParseParser.KwvalueContext):
        pass


    # Enter a parse tree produced by CommandParseParser#positionals.
    def enterPositionals(self, ctx:CommandParseParser.PositionalsContext):
        pass

    # Exit a parse tree produced by CommandParseParser#positionals.
    def exitPositionals(self, ctx:CommandParseParser.PositionalsContext):
        pass


    # Enter a parse tree produced by CommandParseParser#kwargs.
    def enterKwargs(self, ctx:CommandParseParser.KwargsContext):
        pass

    # Exit a parse tree produced by CommandParseParser#kwargs.
    def exitKwargs(self, ctx:CommandParseParser.KwargsContext):
        pass


    # Enter a parse tree produced by CommandParseParser#arguments.
    def enterArguments(self, ctx:CommandParseParser.ArgumentsContext):
        pass

    # Exit a parse tree produced by CommandParseParser#arguments.
    def exitArguments(self, ctx:CommandParseParser.ArgumentsContext):
        pass


    # Enter a parse tree produced by CommandParseParser#argumentlist.
    def enterArgumentlist(self, ctx:CommandParseParser.ArgumentlistContext):
        pass

    # Exit a parse tree produced by CommandParseParser#argumentlist.
    def exitArgumentlist(self, ctx:CommandParseParser.ArgumentlistContext):
        pass


    # Enter a parse tree produced by CommandParseParser#command.
    def enterCommand(self, ctx:CommandParseParser.CommandContext):
        pass

    # Exit a parse tree produced by CommandParseParser#command.
    def exitCommand(self, ctx:CommandParseParser.CommandContext):
        pass



del CommandParseParser