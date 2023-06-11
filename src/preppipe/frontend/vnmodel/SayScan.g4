grammar SayScan;

// must go before NORMALTEXT so that WS has higher priority
WS : [ \t\r\n\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]+ -> skip;

// quoted strings ("text", 'text', “text”, [text], 【Text】)
// https://stackoverflow.com/questions/29800106/how-do-i-escape-an-escape-character-with-antlr-4
// we intentionally NOT supporting escape characters inside string
// consider using environments if the use case cannot be supported
QUOTEDSTR : '"' (~'"')*? '"' | '\'' (~'\'')*? '\'' | '\u201C' (~'\u201D')*? '\u201D' | '[' (~']')*? ']' | '\u3010' (~'\u3011')*? '\u3011' ;

SAYSEPARATOR : ':' | '\uFF1A' ;
STATUSSTART  : '(' | '\uFF08' ;
STATUSEND    : ')' | '\uFF09' ;

// normal text start with a non-whitespace and non-quote/hash/column character, followed by a sequence of non-quote/hash/column characters (but can have whitespace)
// We also exclude '(', ')' and the full-width versions in the normal text
// we will not have leading whitespaces but can have trailing spaces
NORMALTEXT : ~["'\u201C\u201D[\u3010\]\u3011:\uFF1A(\uFF08)\uFF09 \t\r\n\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]~["'\u201C\u201D[\u3010\]\u3011:\uFF1A(\uFF08)\uFF09]* ;

statusexpr : STATUSSTART NORMALTEXT STATUSEND ;

nameexpr : (QUOTEDSTR|NORMALTEXT) ;

contentexpr : (QUOTEDSTR|NORMALTEXT) (QUOTEDSTR|NORMALTEXT|STATUSSTART|STATUSEND|SAYSEPARATOR)*? ;

sayexpr : nameexpr? SAYSEPARATOR? statusexpr? SAYSEPARATOR? contentexpr EOF ;
