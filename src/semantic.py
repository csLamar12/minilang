"""
Semantic analyzer for MiniLang.
Performs type checking, scope resolution, and semantic validation.
"""

from ast_nodes import *
from symbol_table import SymbolTable
from error_handler import error_handler

class SemanticAnalyzer:
    """Semantic analyzer that walks the AST and validates semantic rules."""
    
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.current_function = None
        self.loop_depth = 0
        self.in_loop = False
    
    def analyze(self, ast):
        """Analyze the AST for semantic errors."""
        if not ast:
            return False
        
        # Reset symbol table for new analysis
        self.symbol_table = SymbolTable()
        self.loop_depth = 0
        self.in_loop = False
        
        self.visit(ast)
        return not error_handler.has_errors
    
    def visit(self, node):
        """Dispatch to appropriate visit method based on node type."""
        if node is None:
            return None
        
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)
    
    def generic_visit(self, node):
        """Default visitor for nodes with children."""
        for attr_name in dir(node):
            if not attr_name.startswith('_'):
                attr = getattr(node, attr_name)
                if isinstance(attr, ASTNode):
                    self.visit(attr)
                elif isinstance(attr, list):
                    for item in attr:
                        if isinstance(item, ASTNode):
                            self.visit(item)
    
    def visit_Program(self, node):
        """Visit Program node."""
        for stmt in node.statements:
            self.visit(stmt)
    
    def visit_Comment(self, node):
        """Comments have no semantic significance."""
        pass
    
    def visit_Block(self, node):
        """Enter a new scope for blocks."""
        self.symbol_table.enter_scope()
        for stmt in node.statements:
            self.visit(stmt)
        self.symbol_table.exit_scope()
    
    def visit_Declaration(self, node):
        """Check variable declaration semantics."""
        # Check if variable already declared in current scope
        current_scope = self.symbol_table.scopes[-1]
        if node.identifier in current_scope:
            error_handler.semantic_error(
                f"Variable '{node.identifier}' already declared in this scope",
                node.line, node.column
            )
            return
        
        # Evaluate the initializer expression
        self.visit(node.expression)
        
        # Define the variable
        self.symbol_table.define(node.identifier, None)
    
    def visit_Assignment(self, node):
        """Check assignment semantics."""
        # Check if variable is declared
        if not self.symbol_table.is_declared(node.identifier):
            error_handler.semantic_error(
                f"Variable '{node.identifier}' not declared before assignment",
                node.line, node.column
            )
            return
        
        # Evaluate the expression
        self.visit(node.expression)
    
    def visit_Display(self, node):
        """Check display statement semantics."""
        for item in node.items:
            self.visit(item)
    
    def visit_TryCatch(self, node):
        """Check try-catch semantics."""
        self.visit_statements(node.try_statements)
        self.visit_statements(node.catch_statements)
    
    def visit_If(self, node):
        """Check if statement semantics."""
        self.visit(node.condition)
        
        # Then block
        self.symbol_table.enter_scope()
        self.visit_statements(node.then_statements)
        self.symbol_table.exit_scope()
        
        # Else block (if any)
        if node.else_statements:
            self.symbol_table.enter_scope()
            self.visit_statements(node.else_statements)
            self.symbol_table.exit_scope()
    
    def visit_While(self, node):
        """Check while loop semantics."""
        self.visit(node.condition)
        
        self.loop_depth += 1
        old_in_loop = self.in_loop
        self.in_loop = True
        
        self.symbol_table.enter_scope()
        self.visit_statements(node.statements)
        self.symbol_table.exit_scope()
        
        self.in_loop = old_in_loop
        self.loop_depth -= 1
    
    def visit_For(self, node):
        """Check for loop semantics."""
        # Visit the expressions
        self.visit(node.start_expr)
        self.visit(node.end_expr)
        if node.step_expr:
            self.visit(node.step_expr)
        
        # Check if loop variable is already declared in current scope
        current_scope = self.symbol_table.scopes[-1]
        
        # For loop variable is automatically declared in the loop's scope
        # It should not be in the outer scope
        if node.identifier in current_scope:
            # Check if it was declared in this same scope (error)
            error_handler.semantic_error(
                f"Cannot redeclare variable '{node.identifier}' in for loop",
                node.line, node.column
            )
            return
        
        self.loop_depth += 1
        old_in_loop = self.in_loop
        self.in_loop = True
        
        # Enter new scope for loop body
        self.symbol_table.enter_scope()
        
        # Define the loop variable in the loop's scope
        self.symbol_table.define(node.identifier, None)
        
        # Visit loop body statements
        self.visit_statements(node.statements)
        
        # Exit loop scope
        self.symbol_table.exit_scope()
        
        self.in_loop = old_in_loop
        self.loop_depth -= 1
    
    def visit_Break(self, node):
        """Check break statement semantics."""
        if not self.in_loop:
            error_handler.semantic_error(
                "'break' statement outside of loop",
                node.line, node.column
            )
    
    def visit_Expression(self, node):
        """Visit expression statement."""
        self.visit(node.expression)
    
    def visit_BinaryOp(self, node):
        """Visit binary operation."""
        self.visit(node.left)
        self.visit(node.right)
        
        # Type checking for operations
        left_type = self._get_expression_type(node.left)
        right_type = self._get_expression_type(node.right)
        
        # Check for division by zero in constant expressions
        if node.op == '/' and self._is_constant_zero(node.right):
            error_handler.warning(
                "Division by zero in constant expression",
                node.line, node.column
            )
        
        # Check for modulo by zero
        if node.op == '%' and self._is_constant_zero(node.right):
            error_handler.warning(
                "Modulo by zero in constant expression",
                node.line, node.column
            )
    
    def visit_UnaryOp(self, node):
        """Visit unary operation."""
        self.visit(node.expr)
    
    def visit_Identifier(self, node):
        """Check if identifier is declared."""
        if not self.symbol_table.is_declared(node.name):
            error_handler.semantic_error(
                f"Variable '{node.name}' used before declaration",
                node.line, node.column
            )
    
    def visit_IntegerLiteral(self, node):
        """Visit integer literal."""
        pass
    
    def visit_FloatLiteral(self, node):
        """Visit float literal."""
        pass
    
    def visit_StringLiteral(self, node):
        """Visit string literal."""
        pass
    
    def visit_BooleanLiteral(self, node):
        """Visit boolean literal."""
        pass
    
    def visit_statements(self, statements):
        """Visit a list of statements."""
        if statements:
            for stmt in statements:
                self.visit(stmt)
    
    def _get_expression_type(self, node):
        """Determine the type of an expression."""
        if isinstance(node, (IntegerLiteral, FloatLiteral, StringLiteral, BooleanLiteral)):
            return type(node).__name__.replace('Literal', '').lower()
        elif isinstance(node, Identifier):
            symbol = self.symbol_table.lookup(node.name)
            if symbol:
                return symbol.type
        elif isinstance(node, BinaryOp):
            # Simple type inference
            left_type = self._get_expression_type(node.left)
            right_type = self._get_expression_type(node.right)
            if node.op in ['+', '-', '*', '/', '%']:
                if left_type == 'float' or right_type == 'float':
                    return 'float'
                return 'int'
            elif node.op in ['==', '!=', '<', '>', '<=', '>=']:
                return 'boolean'
        return 'any'
    
    def _is_constant_zero(self, node):
        """Check if a node is a constant zero."""
        if isinstance(node, IntegerLiteral):
            return node.value == 0
        elif isinstance(node, FloatLiteral):
            return node.value == 0.0
        return False