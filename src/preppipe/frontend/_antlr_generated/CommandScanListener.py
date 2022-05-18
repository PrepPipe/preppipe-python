# Generated from CommandScan.g4 by ANTLR 4.10.1
from antlr4 import *
if __name__ is not None and "." in __name__:
    from .CommandScanParser import CommandScanParser
else:
    from CommandScanParser import CommandScanParser

# This class defines a complete listener for a parse tree produced by CommandScanParser.
class CommandScanListener(ParseTreeListener):

    # Enter a parse tree produced by CommandScanParser#command.
    def enterCommand(self, ctx:CommandScanParser.CommandContext):
        pass

    # Exit a parse tree produced by CommandScanParser#command.
    def exitCommand(self, ctx:CommandScanParser.CommandContext):
        pass


    # Enter a parse tree produced by CommandScanParser#body.
    def enterBody(self, ctx:CommandScanParser.BodyContext):
        pass

    # Exit a parse tree produced by CommandScanParser#body.
    def exitBody(self, ctx:CommandScanParser.BodyContext):
        pass


    # Enter a parse tree produced by CommandScanParser#commands.
    def enterCommands(self, ctx:CommandScanParser.CommandsContext):
        pass

    # Exit a parse tree produced by CommandScanParser#commands.
    def exitCommands(self, ctx:CommandScanParser.CommandsContext):
        pass


    # Enter a parse tree produced by CommandScanParser#line.
    def enterLine(self, ctx:CommandScanParser.LineContext):
        pass

    # Exit a parse tree produced by CommandScanParser#line.
    def exitLine(self, ctx:CommandScanParser.LineContext):
        pass



del CommandScanParser