grammar CommandScan;

// must go before NORMALTEXT so that WS has higher priority
WS : [ \t\r\n\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]+ -> skip;

// quoted strings ("text", 'text', “text”)
// https://stackoverflow.com/questions/29800106/how-do-i-escape-an-escape-character-with-antlr-4
// we intentionally NOT supporting escape characters inside string
// consider using environments if the use case cannot be supported
// QUOTEDSTR : '"' (~'"')*? '"' | '\'' (~'\'')*? '\'' | '\u201C' (~'\u201D')*? '\u201D' ;
QUOTEDSTR : '"' (~'"')*? '"' | '\'' (~'\'')*? '\'' | ('\u201C'|'\u201D') (~('\u201C'|'\u201D'))*? ('\u201C'|'\u201D') ;

// non-text elements replaced with unicode null character
ELEMENT : '\u0000' ;

COMMENTSTART : '#' | '\uFF03' ;

COMMANDSTART : '[' | '\u3010' ;
COMMANDEND   : ']' | '\u3011' ;

// normal text start with a non-whitespace and non-quote/hash character, followed by a sequence of non-quote/hash characters (but can have whitespace)
// we will not have leading whitespaces but can have trailing spaces
NORMALTEXT : ~["'\u201C\u201D[\u3010\]\u3011#\uFF03 \t\r\n\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]~["'\u201C\u201D[\u3010\]\u3011#\uFF03]* ;

command : COMMANDSTART COMMENTSTART? body COMMANDEND ;
body : (QUOTEDSTR|ELEMENT|NORMALTEXT)* ;

commands :  command+ ;

line : commands (COMMENTSTART | EOF) ;






