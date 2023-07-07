grammar CommandParse;

// must go before NORMALTEXT so that WS has higher priority
WS : [ \t\r\n\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]+ -> skip;

// non-text elements replaced with unicode null character
ELEMENT : '\u0000' ;

COMMENTSTART : '#' | '\uFF03' ;

COMMANDSTART : '[' | '\u3010' ;
COMMANDEND   : ']' | '\u3011' ;
COMMANDSEP   : ':' | '\uFF1A' ;

ASSIGNMENTOP : '=' | '\uFF1D' ;
COMMAOP      : ',' | '\uFF0C' ;

CALLSTART    : '(' | '\uff08' ;
CALLEND      : ')' | '\uff09' ;

// quoted strings ("text", 'text', “text”)
// https://stackoverflow.com/questions/29800106/how-do-i-escape-an-escape-character-with-antlr-4
// we intentionally NOT supporting escape characters inside string
// consider using environments if the use case cannot be supported
// When using full-width quote (should be '\u201C' (~'\u201D')*? '\u201D'),
// sometimes it is not very clear if the start and end quotation signs are correct
// (so we can have both '\u201D' for start and end or '\u201C' or reversed)
// therefore, here we do not distinguish them
QUOTEDSTR : '"' (~'"')*? '"' | '\'' (~'\'')*? '\'' | ('\u201C'|'\u201D') (~('\u201C'|'\u201D'))*? ('\u201C'|'\u201D') ;

// NATURALTEXT excludes whitespaces, ',', '"', '\'', '=', '[', ']', '(', ')', ':', '#', and their unicode variants
NATURALTEXT : (~[ \t\r\n\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF,\uFF0C"'\u201C\u201D=\uFF1D[\u3010\]\u3011(\uff08)\uff09:\uFF1A#\uFF03])+ ;

// elementary value
evalue : NATURALTEXT | QUOTEDSTR | ELEMENT ;

// call expression as value
callexpr : name CALLSTART arguments CALLEND ;

value  : evalue | callexpr ;
name   : NATURALTEXT | QUOTEDSTR ;

kwvalue : name ASSIGNMENTOP value ;

positionals : (value COMMAOP?)+ ;
kwargs : (kwvalue COMMAOP?)+ ;

arguments : positionals? kwargs? ;
argumentlist : arguments EOF ;


// we place EOF in the rule of argumentlist so that if the argument list cannot be properly parsed, we still get a valid command node with command name available
command : name COMMANDSEP? argumentlist? ;
