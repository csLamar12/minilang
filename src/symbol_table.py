"""
Symbol table for variable management with scope handling.
"""

class Symbol:
    """Represents a variable in the symbol table."""
    def __init__(self, name, value=None, type_name='any', declared=False):
        self.name = name
        self.value = value
        self.type = type_name
        self.declared = declared  # True if declared with 'let'


class SymbolTable:
    """Symbol table with nested scope support."""
    
    def __init__(self):
        self.scopes = [{}]  # Stack of scopes (current scope is last)
        self.loop_depth = 0  # Track nested loop depth for break statements
    
    def enter_scope(self):
        """Enter a new nested scope."""
        self.scopes.append({})
    
    def exit_scope(self):
        """Exit the current scope."""
        if len(self.scopes) > 1:
            self.scopes.pop()
    
    def enter_loop(self):
        """Enter a loop (increment loop depth)."""
        self.loop_depth += 1
    
    def exit_loop(self):
        """Exit a loop (decrement loop depth)."""
        if self.loop_depth > 0:
            self.loop_depth -= 1
    
    def in_loop(self):
        """Check if currently inside a loop."""
        return self.loop_depth > 0
    
    def define(self, name, value=None, type_name='any'):
        """Define a new variable in the current scope."""
        self.scopes[-1][name] = Symbol(name, value, type_name, declared=True)
    
    def assign(self, name, value):
        """Assign to an existing variable (search all scopes)."""
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name].value = value
                return True
        return False
    
    def lookup(self, name):
        """Look up a variable in all scopes."""
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None
    
    def is_declared(self, name):
        """Check if a variable has been declared with 'let'."""
        symbol = self.lookup(name)
        return symbol is not None and symbol.declared
    
    def get_value(self, name):
        """Get the value of a variable."""
        symbol = self.lookup(name)
        if symbol:
            return symbol.value
        return None
    
    def __str__(self):
        """String representation of the symbol table."""
        result = "Symbol Table:\n"
        for i, scope in enumerate(self.scopes):
            result += f"  Scope {i}:\n"
            for name, symbol in scope.items():
                result += f"    {name} = {symbol.value} (declared: {symbol.declared})\n"
        return result