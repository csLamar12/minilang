# File        : ast_nodes.py
# Description : AST node class definitions for all NovaScript grammar constructs
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

class ASTNode:
    """Base class for all AST nodes."""
    def __init__(self):
        self.line = 0
        self.column = 0

    def set_position(self, line, column):
        self.line = line
        self.column = column
        return self


class Program(ASTNode):
    """Root node representing the entire program."""
    def __init__(self, statements):
        super().__init__()
        self.statements = statements


class Statement(ASTNode):
    """Base class for all statements."""
    pass


class Comment(Statement):
    """Comment statement (ignored during execution)."""
    def __init__(self, text):
        super().__init__()
        self.text = text


class Block(Statement):
    """Block of statements (begin ... end)."""
    def __init__(self, statements):
        super().__init__()
        self.statements = statements


class Declaration(Statement):
    """Variable declaration (let id = expression)."""
    def __init__(self, identifier, expression):
        super().__init__()
        self.identifier = identifier
        self.expression = expression


class Assignment(Statement):
    """Variable assignment (id = expression)."""
    def __init__(self, identifier, expression):
        super().__init__()
        self.identifier = identifier
        self.expression = expression


class Display(Statement):
    """Display statement (display item1 item2 ...)."""
    def __init__(self, items):
        super().__init__()
        self.items = items


class TryCatch(Statement):
    """Try-catch statement for exception handling."""
    def __init__(self, try_statements, catch_statements):
        super().__init__()
        self.try_statements = try_statements
        self.catch_statements = catch_statements


class If(Statement):
    """If statement with optional else."""
    def __init__(self, condition, then_statements, else_statements=None):
        super().__init__()
        self.condition = condition
        self.then_statements = then_statements
        self.else_statements = else_statements if else_statements else []


class While(Statement):
    """While loop."""
    def __init__(self, condition, statements):
        super().__init__()
        self.condition = condition
        self.statements = statements


class For(Statement):
    """For loop (for id = start to end step value)."""
    def __init__(self, identifier, start_expr, end_expr, step_expr, statements):
        super().__init__()
        self.identifier = identifier
        self.start_expr = start_expr
        self.end_expr = end_expr
        self.step_expr = step_expr
        self.statements = statements


class Break(Statement):
    """Break statement to exit loops."""
    def __init__(self):
        super().__init__()


class Expression(Statement):
    """Expression statement (an expression evaluated for side effects)."""
    def __init__(self, expression):
        super().__init__()
        self.expression = expression


class ExpressionNode(ASTNode):
    """Base class for all expressions."""
    pass


class BinaryOp(ExpressionNode):
    """Binary operation (+, -, *, /, %, relational ops)."""
    def __init__(self, left, op, right):
        super().__init__()
        self.left = left
        self.op = op
        self.right = right


class UnaryOp(ExpressionNode):
    """Unary operation (+, -, not)."""
    def __init__(self, op, expr):
        super().__init__()
        self.op = op
        self.expr = expr


class Identifier(ExpressionNode):
    """Variable identifier."""
    def __init__(self, name):
        super().__init__()
        self.name = name


class Literal(ExpressionNode):
    """Base class for literals."""
    pass


class IntegerLiteral(Literal):
    """Integer literal."""
    def __init__(self, value):
        super().__init__()
        self.value = int(value)


class FloatLiteral(Literal):
    """Float literal."""
    def __init__(self, value):
        super().__init__()
        self.value = float(value)


class StringLiteral(Literal):
    """String literal."""
    def __init__(self, value):
        super().__init__()
        self.value = value.strip('"')


class BooleanLiteral(Literal):
    """Boolean literal."""
    def __init__(self, value):
        super().__init__()
        self.value = value.lower() == 'true'