grammar SayScan;

// must go before NORMALTEXT so that WS has higher priority
WS : [ \t\r\n\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]+ -> skip;

// quoted strings ("text", 'text', “text”, [text], 【Text】)
// https://stackoverflow.com/questions/29800106/how-do-i-escape-an-escape-character-with-antlr-4
// we intentionally NOT supporting escape characters inside string
QUOTEDSTR : '"' (~'"')*? '"' | '\'' (~'\'')*? '\'' | ('\u201C'|'\u201D') (~('\u201C'|'\u201D'))*? ('\u201C'|'\u201D') | '[' (~']')*? ']' | '\u3010' (~'\u3011')*? '\u3011' ;

SAYSEPARATOR : ':' | '\uFF1A' ;
STATUSSTART  : '(' | '\uFF08' ;
STATUSEND    : ')' | '\uFF09' ;

COMMASPLITTER : ',' | '\uFF0C' ;

SENTENCESPLITTER :  '.' | '\u3002'
                  | '?' | '\uFF1F'
                  | '!' | '\uFF01'
                  | '\u2026' // zh_cn '...'
                  ;

// normal text start with a non-whitespace and non-quote/special character, followed by a sequence of non-quote/special characters (but can have whitespace)
// We also exclude '(', ')' and the full-width versions in the normal text
// we will not have leading whitespaces but can have trailing spaces
NORMALTEXT : ~["'\u201C\u201D[\u3010\]\u3011:\uFF1A(\uFF08)\uFF09,\uFF0C.\u3002?\uFF1F!\uFF01\u2026 \t\r\n\u00A0\u2000-\u200B\u202F\u205F\u3000\uFEFF]~["'\u201C\u201D[\u3010\]\u3011:\uFF1A(\uFF08)\uFF09,\uFF0C.\u3002?\uFF1F!\uFF01\u2026]* ;

statusexpr : STATUSSTART NORMALTEXT (COMMASPLITTER NORMALTEXT)*? STATUSEND ;

nameexpr : (QUOTEDSTR|NORMALTEXT) ;

nameexpr_strong : QUOTEDSTR ;

contentexpr : (QUOTEDSTR|NORMALTEXT|SENTENCESPLITTER) (QUOTEDSTR|NORMALTEXT|STATUSSTART|STATUSEND|SAYSEPARATOR|COMMASPLITTER|SENTENCESPLITTER)*? ;

contentexpr_strong : QUOTEDSTR ;

sayexpr : nameexpr? SAYSEPARATOR statusexpr? contentexpr EOF
        | nameexpr? statusexpr? SAYSEPARATOR contentexpr EOF
        | nameexpr  statusexpr? contentexpr_strong EOF
        | nameexpr_strong? statusexpr? contentexpr EOF

        ;

