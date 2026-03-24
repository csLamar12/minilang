# File        : parser.py
# Description : LALR(1) parser — builds the Abstract Syntax Tree using PLY
# =============================================================================
# Authors     : Rachjaye Gayle      - 2100400
#             : Rushane  Green      - 2006930
#             : Abbygayle Higgins   - 2106327
#             : Lamar Haye          - 2111690
# -----------------------------------------------------------------------------
# Institution : University of Technology, Jamaica
# Faculty     : School of Computing & Information Technology (FENC)
# Course      : Analysis of Programming Languages | CIT4004
# Tutor       : Dr. David White
# =============================================================================

import ply.yacc as yacc
from lexer import NovaScriptLexer
from ast_nodes import *
from error_handler import error_handler

class NovaScriptParser:
    """Parser for the NovaScript programming language."""
    
    def __init__(self):
        self.lexer = NovaScriptLexer()
        self.lexer.build()
        self.tokens = self.lexer.tokens
        self.parser = None
        self.ast = None
    
    # Precedence rules for operators (lowest to highest)
    precedence = (
        ('left', 'OR'),           # Logical OR (lowest)
        ('left', 'AND'),          # Logical AND
        ('left', 'EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE'),  # Relational
        ('left', 'PLUS', 'MINUS'),                       # Arithmetic
        ('left', 'TIMES', 'DIVIDE', 'MODULO'),           # Arithmetic
        ('right', 'UMINUS', 'UPLUS', 'NOT'),             # Unary
    )
    
    # Grammar rules
    def p_program(self, p):
        '''program : statement_list'''
        p[0] = Program(p[1])
        self.ast = p[0]
    
    def p_statement_list(self, p):
        '''statement_list : statement
                          | statement statement_list'''
        if len(p) == 2:
            p[0] = [p[1]] if p[1] is not None else []
        else:
            p[0] = [p[1]] + p[2] if p[1] is not None else p[2]
    
    def p_statement(self, p):
        '''statement : comment NEWLINE
                    | declaration_stmt NEWLINE
                    | assignment_stmt NEWLINE
                    | display_stmt NEWLINE
                    | try_catch_stmt
                    | if_stmt
                    | while_stmt
                    | for_stmt
                    | break_stmt NEWLINE
                    | expression_stmt NEWLINE
                    | block_stmt
                    | NEWLINE'''
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = p[1]
    
    def p_comment(self, p):
        '''comment : COMMENT'''
        p[0] = Comment(p[1])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_block_stmt(self, p):
        '''block_stmt : BEGIN NEWLINE statement_list END NEWLINE'''
        p[0] = Block(p[3])
        p[0].set_position(p.lineno(1), 0)
    
    def p_declaration_stmt(self, p):
        '''declaration_stmt : LET IDENTIFIER ASSIGN expression'''
        p[0] = Declaration(p[2], p[4])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_assignment_stmt(self, p):
        '''assignment_stmt : IDENTIFIER ASSIGN expression'''
        p[0] = Assignment(p[1], p[3])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_expression_stmt(self, p):
        '''expression_stmt : expression'''
        p[0] = Expression(p[1])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_display_stmt(self, p):
        '''display_stmt : DISPLAY display_list'''
        p[0] = Display(p[2])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_display_list(self, p):
        '''display_list : display_item
                        | display_item display_list'''
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = [p[1]] + p[2]
    
    def p_display_item(self, p):
        '''display_item : STRING
                        | IDENTIFIER
                        | expression'''
        if p.slice[1].type == 'STRING':
            p[0] = StringLiteral(p[1])
        elif p.slice[1].type == 'IDENTIFIER':
            p[0] = Identifier(p[1])
        else:
            p[0] = p[1]
    
    def p_try_catch_stmt(self, p):
        '''try_catch_stmt : TRY NEWLINE statement_list CATCH NEWLINE statement_list END'''
        p[0] = TryCatch(p[3], p[6])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_if_stmt(self, p):
        '''if_stmt : IF condition NEWLINE statement_list else_part END'''
        p[0] = If(p[2], p[4], p[5])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_else_part(self, p):
        '''else_part : ELSE NEWLINE statement_list
                     | empty'''
        if len(p) == 4:
            p[0] = p[3]
        else:
            p[0] = None
    
    def p_while_stmt(self, p):
        '''while_stmt : WHILE condition NEWLINE statement_list END'''
        p[0] = While(p[2], p[4])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_for_stmt(self, p):
        '''for_stmt : FOR IDENTIFIER ASSIGN expression TO expression step_part NEWLINE statement_list END'''
        p[0] = For(p[2], p[4], p[6], p[7], p[9])
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_step_part(self, p):
        '''step_part : STEP expression
                     | empty'''
        if len(p) == 3:
            p[0] = p[2]
        else:
            p[0] = None
    
    def p_break_stmt(self, p):
        '''break_stmt : BREAK'''
        p[0] = Break()
        if hasattr(p.slice[1], 'lineno'):
            p[0].set_position(p.slice[1].lineno, self._find_column(p.slice[1]))
    
    def p_condition(self, p):
        '''condition : expression'''
        p[0] = p[1]
    
    # Expression rules with proper precedence
    def p_expression(self, p):
        '''expression : logical_expr'''
        p[0] = p[1]
    
    def p_logical_expr(self, p):
        '''logical_expr : relational_expr
                        | logical_expr AND relational_expr
                        | logical_expr OR relational_expr'''
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = BinaryOp(p[1], p[2], p[3])
    
    def p_relational_expr(self, p):
        '''relational_expr : additive_expr
                           | relational_expr EQ additive_expr
                           | relational_expr NEQ additive_expr
                           | relational_expr LT additive_expr
                           | relational_expr GT additive_expr
                           | relational_expr LE additive_expr
                           | relational_expr GE additive_expr'''
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = BinaryOp(p[1], p[2], p[3])
    
    def p_additive_expr(self, p):
        '''additive_expr : multiplicative_expr
                         | additive_expr PLUS multiplicative_expr
                         | additive_expr MINUS multiplicative_expr'''
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = BinaryOp(p[1], p[2], p[3])
    
    def p_multiplicative_expr(self, p):
        '''multiplicative_expr : unary_expr
                               | multiplicative_expr TIMES unary_expr
                               | multiplicative_expr DIVIDE unary_expr
                               | multiplicative_expr MODULO unary_expr'''
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = BinaryOp(p[1], p[2], p[3])
    
    def p_unary_expr(self, p):
        '''unary_expr : primary_expr
                      | PLUS unary_expr %prec UPLUS
                      | MINUS unary_expr %prec UMINUS
                      | NOT unary_expr'''
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = UnaryOp(p[1], p[2])
    
    def p_primary_expr(self, p):
        '''primary_expr : IDENTIFIER
                        | literal
                        | LPAREN expression RPAREN
                        | BOOLEAN'''
        if len(p) == 2:
            if p.slice[1].type == 'IDENTIFIER':
                p[0] = Identifier(p[1])
            elif p.slice[1].type == 'BOOLEAN':
                p[0] = BooleanLiteral(p[1])
            else:
                p[0] = p[1]
        else:
            p[0] = p[2]
    
    def p_literal(self, p):
        '''literal : INTEGER
                   | FLOAT
                   | STRING'''
        if p.slice[1].type == 'INTEGER':
            p[0] = IntegerLiteral(p[1])
        elif p.slice[1].type == 'FLOAT':
            p[0] = FloatLiteral(p[1])
        else:
            p[0] = StringLiteral(p[1])
    
    def p_empty(self, p):
        '''empty :'''
        p[0] = None
    
    def p_error(self, p):
        """Handle syntax errors."""
        if p:
            error_handler.syntax_error(
                f"Syntax error at '{p.value}'",
                p.lineno,
                self._find_column(p)
            )
        else:
            error_handler.syntax_error("Syntax error at EOF", 0, 0)
    
    def _find_column(self, token):
        """Find the column position of a token."""
        try:
            if hasattr(self.lexer, 'lexdata') and self.lexer.lexdata:
                last_cr = self.lexer.lexdata.rfind('\n', 0, token.lexpos)
                if last_cr < 0:
                    last_cr = 0
                return (token.lexpos - last_cr)
        except:
            pass
        return 0
    
    def build(self, **kwargs):
        """Build the parser."""
        self.parser = yacc.yacc(module=self, **kwargs)
        return self.parser
    
    def parse(self, data):
        """Parse input data and return AST."""
        if not self.parser:
            self.build()
        
        # Store data in lexer for column calculation
        self.lexer.lexdata = data
        
        # Reset error handler for new parse
        error_handler.errors = []
        error_handler.warnings = []
        error_handler.has_errors = False
        
        try:
            result = self.parser.parse(data, lexer=self.lexer.lexer)
            return result
        except Exception as e:
            error_handler.syntax_error(f"Parse error: {str(e)}", 0, 0)
            return None


# For testing
if __name__ == '__main__':
    parser = NovaScriptParser()
    parser.build()
    
    test_code = """
    let x = 10
    let y = 20
    
    if x > 5 and y < 30
        display "Both conditions are true"
    end
    
    for i = 1 to 5
        display i
    end
    """
    
    ast = parser.parse(test_code)
    if ast and not error_handler.has_errors:
        print("Parsing successful!")
    else:
        print("Parsing failed.")