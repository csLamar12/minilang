"""
Lexical analyzer for MiniLang using PLY.
Fixed version with proper line number reset.
"""

import ply.lex as lex
from error_handler import error_handler

class MiniLangLexer:
    """Lexical analyzer for the MiniLang programming language."""
    
    # List of token names
    tokens = (
        'LET', 'DISPLAY', 'TRY', 'CATCH', 'IF', 'ELSE', 'WHILE', 'FOR',
        'TO', 'STEP', 'BEGIN', 'END', 'BREAK', 'NOT', 'AND', 'OR',
        'IDENTIFIER', 'INTEGER', 'FLOAT', 'STRING', 'BOOLEAN',
        'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MODULO',
        'EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE',
        'ASSIGN', 'LPAREN', 'RPAREN', 'COMMENT', 'NEWLINE',
    )
    
    # Regular expressions for simple tokens
    t_PLUS = r'\+'
    t_MINUS = r'-'
    t_TIMES = r'\*'
    t_DIVIDE = r'/'
    t_MODULO = r'%'
    t_ASSIGN = r'='
    t_LPAREN = r'\('
    t_RPAREN = r'\)'
    t_LT = r'<'
    t_GT = r'>'
    
    # Complex tokens with specific rules
    t_LE = r'<='
    t_GE = r'>='
    t_EQ = r'=='
    t_NEQ = r'!='
    
    # Reserved words mapping
    reserved = {
        'let': 'LET',
        'display': 'DISPLAY',
        'try': 'TRY',
        'catch': 'CATCH',
        'if': 'IF',
        'else': 'ELSE',
        'while': 'WHILE',
        'for': 'FOR',
        'to': 'TO',
        'step': 'STEP',
        'begin': 'BEGIN',
        'end': 'END',
        'break': 'BREAK',
        'not': 'NOT',
        'and': 'AND',
        'or': 'OR',
        'true': 'BOOLEAN',
        'false': 'BOOLEAN',
    }
    
    def __init__(self):
        self.lexer = None
        self.lexdata = ""
        self.current_line = 1  # Track current line number
        
    def build(self, **kwargs):
        """Build the lexer."""
        self.lexer = lex.lex(module=self, **kwargs)
        return self.lexer
    
    def reset(self):
        """Reset the lexer state completely."""
        self.current_line = 1
        if self.lexer:
            self.lexer.lineno = 1
            self.lexer.lexpos = 0
    
    def t_COMMENT(self, t):
        r'--.*'
        # Comments are ignored (no token returned)
        pass
    
    def t_BOOLEAN(self, t):
        r'true|false'
        # Keep as string to avoid type confusion
        t.value = t.value  # Keep as string
        return t
    
    def t_FLOAT(self, t):
        r'\d+\.\d+'
        t.value = float(t.value)
        return t
    
    def t_INTEGER(self, t):
        r'\d+'
        t.value = int(t.value)
        return t
    
    def t_STRING(self, t):
        r'"[^"\n]*"'
        return t
    
    def t_IDENTIFIER(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_]*'
        # Check if it's a reserved word
        t.type = self.reserved.get(t.value, 'IDENTIFIER')
        return t
    
    # Track line numbers
    def t_NEWLINE(self, t):
        r'\n+'
        self.current_line += len(t.value)
        t.lexer.lineno = self.current_line
        return t
    
    # Skip spaces and tabs
    t_ignore = ' \t'
    
    def t_error(self, t):
        """Handle lexical errors."""
        error_handler.lexical_error(
            f"Illegal character '{t.value[0]}'",
            self.current_line,
            self._find_column(t)
        )
        t.lexer.skip(1)
    
    def _find_column(self, token):
        """Find the column position of a token."""
        try:
            last_cr = self.lexdata.rfind('\n', 0, token.lexpos)
            if last_cr < 0:
                last_cr = 0
            return (token.lexpos - last_cr)
        except:
            return 0
    
    def tokenize(self, data):
        """Tokenize input data and return list of tokens."""
        if not self.lexer:
            self.build()
        
        # Reset lexer state before tokenizing new input
        self.reset()
        
        # Store the input data for column calculation
        self.lexdata = data
        
        # Set the lexer input
        self.lexer.input(data)
        
        # Collect tokens
        tokens = []
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            # Override line number with our tracked value
            tok.lineno = self.current_line
            # Add column information
            tok.column = self._find_column(tok)
            tokens.append(tok)
        
        return tokens


# For testing
if __name__ == '__main__':
    lexer = MiniLangLexer()
    lexer.build()
    
    test_code = """
    -- This is a comment
    let x = 10
    let y = 3.14
    """
    
    tokens = lexer.tokenize(test_code)
    for token in tokens:
        print(f'Token: {token.type}, Value: {token.value}, Line: {token.lineno}')
    
    print("\nTokenizing again...")
    tokens = lexer.tokenize(test_code)
    for token in tokens:
        print(f'Token: {token.type}, Value: {token.value}, Line: {token.lineno}')