"""
Error handling for lexical, syntax, and semantic errors.
"""

class ErrorHandler:
    """Centralized error handling with colored output."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.has_errors = False
    
    def lexical_error(self, message, line, column):
        """Report a lexical error."""
        self._add_error('LEXICAL', message, line, column)
    
    def syntax_error(self, message, line, column):
        """Report a syntax error."""
        self._add_error('SYNTAX', message, line, column)
    
    def semantic_error(self, message, line, column):
        """Report a semantic error."""
        self._add_error('SEMANTIC', message, line, column)
    
    def runtime_error(self, message, line, column):
        """Report a runtime error."""
        self._add_error('RUNTIME', message, line, column)
    
    def warning(self, message, line, column):
        """Report a warning."""
        self.warnings.append({
            'type': 'WARNING',
            'message': message,
            'line': line,
            'column': column
        })
        print(f"\033[93mWARNING at line {line}, column {column}: {message}\033[0m")
    
    def _add_error(self, error_type, message, line, column):
        """Internal method to add an error."""
        self.errors.append({
            'type': error_type,
            'message': message,
            'line': line,
            'column': column
        })
        self.has_errors = True
        print(f"\033[91m{error_type} ERROR at line {line}, column {column}: {message}\033[0m")
    
    def has_errors(self):
        """Check if any errors have been reported."""
        return self.has_errors
    
    def reset(self):
        """Clear all errors and warnings — call before each new compilation."""
        self.errors = []
        self.warnings = []
        self.has_errors = False

    def print_summary(self):
        """Print a summary of all errors and warnings."""
        if not self.errors and not self.warnings:
            print("\033[92mNo errors or warnings.\033[0m")
            return
        
        print("\n" + "="*50)
        print("ERROR SUMMARY")
        print("="*50)
        
        for error in self.errors:
            print(f"\033[91m{error['type']}: {error['message']} [line {error['line']}]\033[0m")
        
        for warning in self.warnings:
            print(f"\033[93mWARNING: {warning['message']} [line {warning['line']}]\033[0m")
        
        print(f"\nTotal: {len(self.errors)} errors, {len(self.warnings)} warnings")


# Global error handler instance
error_handler = ErrorHandler()