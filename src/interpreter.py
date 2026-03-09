"""
Interpreter for MiniLang.
Executes the AST and produces output.
"""

from ast_nodes import *
from symbol_table import SymbolTable
from error_handler import error_handler
import sys

class Interpreter:
    """Interpreter that walks the AST and executes the program."""
    
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.output_buffer = []
        self.in_try_block = False
        self.catch_block = None
        self.loop_break = False
        self.in_loop = False
    
    def interpret(self, ast):
        """Interpret the AST and execute the program."""
        if not ast:
            return False
        
        # Reset state
        self.symbol_table = SymbolTable()
        self.output_buffer = []
        self.in_try_block = False
        self.catch_block = None
        self.loop_break = False
        self.in_loop = False
        
        try:
            self.visit(ast)
            return not error_handler.has_errors
        except Exception as e:
            error_handler.runtime_error(str(e), 0, 0)
            return False
    
    def visit(self, node):
        """Dispatch to appropriate visit method based on node type."""
        if node is None:
            return None
        
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)
    
    def generic_visit(self, node):
        """Default visitor for nodes with children."""
        result = None
        for attr_name in dir(node):
            if not attr_name.startswith('_'):
                attr = getattr(node, attr_name)
                if isinstance(attr, ASTNode):
                    result = self.visit(attr)
                elif isinstance(attr, list):
                    for item in attr:
                        if isinstance(item, ASTNode):
                            self.visit(item)
        return result
    
    def visit_Program(self, node):
        """Execute program statements."""
        for stmt in node.statements:
            if self.loop_break and not isinstance(stmt, (While, For)):
                continue
            self.visit(stmt)
    
    def visit_Comment(self, node):
        """Comments are ignored."""
        pass
    
    def visit_Block(self, node):
        """Execute a block of statements with new scope."""
        self.symbol_table.enter_scope()
        for stmt in node.statements:
            if self.loop_break:
                break
            self.visit(stmt)
        self.symbol_table.exit_scope()
    
    def visit_Declaration(self, node):
        """Declare and initialize a variable."""
        value = self.visit(node.expression)
        self.symbol_table.define(node.identifier, value)
    
    def visit_Assignment(self, node):
        """Assign a new value to a variable."""
        value = self.visit(node.expression)
        if not self.symbol_table.assign(node.identifier, value):
            error_handler.runtime_error(
                f"Cannot assign to undeclared variable '{node.identifier}'",
                node.line, node.column
            )
    
    def visit_Display(self, node):
        """Display output to console."""
        output = ""
        for item in node.items:
            value = self.visit(item)
            if value is None:
                output += "None"
            elif isinstance(value, (int, float, bool)):
                output += str(value)
            elif isinstance(value, str):
                # Handle special characters in strings
                output += value.replace('\\n', '\n')
            else:
                output += str(value)
        
        # Print without extra newline if the output ends with newline
        if output.endswith('\n'):
            print(output, end='')
        else:
            print(output)
        self.output_buffer.append(output)
    
    def visit_TryCatch(self, node):
        """Execute try-catch for exception handling."""
        old_in_try = self.in_try_block
        self.in_try_block = True
        
        try:
            for stmt in node.try_statements:
                self.visit(stmt)
        except Exception as e:
            # Execute catch block on exception
            print(f"Caught exception: {e}")
            self.symbol_table.enter_scope()
            for stmt in node.catch_statements:
                self.visit(stmt)
            self.symbol_table.exit_scope()
        finally:
            self.in_try_block = old_in_try
    
    def visit_If(self, node):
        """Execute if statement."""
        condition = self.visit(node.condition)
        
        # Convert condition to boolean
        if condition:
            self.symbol_table.enter_scope()
            for stmt in node.then_statements:
                if self.loop_break:
                    break
                self.visit(stmt)
            self.symbol_table.exit_scope()
        elif node.else_statements:
            self.symbol_table.enter_scope()
            for stmt in node.else_statements:
                if self.loop_break:
                    break
                self.visit(stmt)
            self.symbol_table.exit_scope()
    
    def visit_While(self, node):
        """Execute while loop."""
        old_in_loop = self.in_loop
        self.in_loop = True
        self.symbol_table.enter_loop()
        
        max_iterations = 10000  # Prevent infinite loops
        iterations = 0
        
        condition = self.visit(node.condition)
        while condition and iterations < max_iterations:
            iterations += 1
            self.symbol_table.enter_scope()
            
            for stmt in node.statements:
                if self.loop_break:
                    break
                self.visit(stmt)
            
            self.symbol_table.exit_scope()
            
            if self.loop_break:
                self.loop_break = False
                break
            
            condition = self.visit(node.condition)
        
        if iterations >= max_iterations:
            error_handler.runtime_error(
                "Maximum loop iterations exceeded (possible infinite loop)",
                node.line, node.column
            )
        
        self.symbol_table.exit_loop()
        self.in_loop = old_in_loop
    
    def visit_For(self, node):
        """Execute for loop."""
        old_in_loop = self.in_loop
        self.in_loop = True
        
        # Evaluate start, end, and step
        start = self.visit(node.start_expr)
        end = self.visit(node.end_expr)
        step = self.visit(node.step_expr) if node.step_expr else 1
        
        if step == 0:
            error_handler.runtime_error("Step value cannot be zero", node.line, node.column)
            return
        
        # Enter new scope for loop
        self.symbol_table.enter_scope()
        self.symbol_table.enter_loop()
        
        # Define loop variable in this scope
        self.symbol_table.define(node.identifier, start)
        
        max_iterations = 10000
        iterations = 0
        current = start
        
        while (step > 0 and current <= end) or (step < 0 and current >= end):
            if iterations >= max_iterations:
                error_handler.runtime_error(
                    "Maximum loop iterations exceeded (possible infinite loop)",
                    node.line, node.column
                )
                break
            
            iterations += 1
            
            # Enter another scope for loop body
            self.symbol_table.enter_scope()
            
            for stmt in node.statements:
                if self.loop_break:
                    break
                self.visit(stmt)
            
            self.symbol_table.exit_scope()
            
            if self.loop_break:
                self.loop_break = False
                break
            
            current += step
            self.symbol_table.assign(node.identifier, current)
        
        self.symbol_table.exit_loop()
        self.symbol_table.exit_scope()
        self.in_loop = old_in_loop
    
    def visit_Break(self, node):
        """Execute break statement."""
        if self.in_loop:
            self.loop_break = True
        else:
            error_handler.runtime_error(
                "'break' outside of loop",
                node.line, node.column
            )
    
    def visit_Expression(self, node):
        """Evaluate expression statement."""
        return self.visit(node.expression)
    
    def visit_BinaryOp(self, node):
        """Evaluate binary operation."""
        left = self.visit(node.left)
        right = self.visit(node.right)
        
        if left is None or right is None:
            return None
        
        try:
            if node.op == '+':
                # String concatenation if either operand is string
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                return left + right
            elif node.op == '-':
                return left - right
            elif node.op == '*':
                return left * right
            elif node.op == '/':
                if right == 0:
                    if self.in_try_block:
                        raise ZeroDivisionError("Division by zero")
                    else:
                        error_handler.runtime_error(
                            "Division by zero",
                            node.line, node.column
                        )
                        return None
                return left / right
            elif node.op == '%':
                if right == 0:
                    if self.in_try_block:
                        raise ZeroDivisionError("Modulo by zero")
                    else:
                        error_handler.runtime_error(
                            "Modulo by zero",
                            node.line, node.column
                        )
                        return None
                return left % right
            elif node.op == '==':
                return left == right
            elif node.op == '!=':
                return left != right
            elif node.op == '<':
                return left < right
            elif node.op == '>':
                return left > right
            elif node.op == '<=':
                return left <= right
            elif node.op == '>=':
                return left >= right
            elif node.op == 'and':
                return bool(left) and bool(right)
            elif node.op == 'or':
                return bool(left) or bool(right)
            else:
                return None
        except Exception as e:
            if self.in_try_block:
                raise e
            else:
                error_handler.runtime_error(str(e), node.line, node.column)
                return None
    
    def visit_UnaryOp(self, node):
        """Evaluate unary operation."""
        value = self.visit(node.expr)
        
        if value is None:
            return None
        
        if node.op == '+':
            return +value
        elif node.op == '-':
            return -value
        elif node.op == 'not':
            return not value
        else:
            return value
    
    def visit_Identifier(self, node):
        """Get variable value."""
        value = self.symbol_table.get_value(node.name)
        if value is None:
            # Check if variable exists but has no value
            symbol = self.symbol_table.lookup(node.name)
            if symbol and not symbol.value and symbol.value != 0:
                # It's declared but not initialized
                return None
        return value
    
    def visit_IntegerLiteral(self, node):
        return node.value
    
    def visit_FloatLiteral(self, node):
        return node.value
    
    def visit_StringLiteral(self, node):
        return node.value
    
    def visit_BooleanLiteral(self, node):
        return node.value
    
    def get_output(self):
        """Get the output buffer as a string."""
        return '\n'.join(self.output_buffer)
    
    def get_symbol_table_with_values(self):
        """Return the symbol table with current values after execution."""
        result = "Symbol Table (with values):\n"
        result += "=" * 50 + "\n"
        
        for i, scope in enumerate(self.symbol_table.scopes):
            result += f"Scope {i}:\n"
            for name, symbol in scope.items():
                value_str = str(symbol.value) if symbol.value is not None else "None"
                result += f"  {name} = {value_str} (declared: {symbol.declared})\n"
        
        return result