#!/usr/bin/env python3
"""
NovaScript Compiler and Interpreter
Main entry point for the NovaScript programming language.
"""

import sys
import os
import argparse
from lexer import NovaScriptLexer
from parser import NovaScriptParser
from semantic import SemanticAnalyzer
from interpreter import Interpreter
from error_handler import error_handler

class NovaScriptCompiler:
    """Main compiler class that orchestrates all phases."""
    
    def __init__(self):
        self.lexer = NovaScriptLexer()
        self.parser = NovaScriptParser()
        self.semantic = SemanticAnalyzer()
        self.interpreter = Interpreter()
    
    def compile_and_run(self, source_code, filename="<stdin>"):
        """
        Compile and run NovaScript source code.
        
        Args:
            source_code: String containing the source code
            filename: Source filename for error reporting
        
        Returns:
            True if execution succeeded, False otherwise
        """
        error_handler.reset()          # always start clean
        print(f"\n{'='*60}")
        print(f"COMPILING: {filename}")
        print(f"{'='*60}\n")

        # Phase 1: Lexical Analysis
        print("Phase 1: Lexical Analysis...")
        try:
            tokens = self.lexer.tokenize(source_code)
            if error_handler.has_errors:
                print("❌ Lexical analysis failed!")
                error_handler.print_summary()
                return False
            print(f"✅ Lexical analysis successful. Found {len(tokens)} tokens.")
            if len(tokens) > 0:
                print(f"   First few tokens: {[f'{t.type}({t.value})' for t in tokens[:5]]}")
        except Exception as e:
            print(f"❌ Lexical analysis error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Phase 2: Syntax Analysis (Parsing)
        print("\nPhase 2: Syntax Analysis...")
        try:
            ast = self.parser.parse(source_code)
            if error_handler.has_errors or not ast:
                print("❌ Syntax analysis failed!")
                error_handler.print_summary()
                return False
            print("✅ Syntax analysis successful. AST generated.")
        except Exception as e:
            print(f"❌ Syntax analysis error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Phase 3: Semantic Analysis
        print("\nPhase 3: Semantic Analysis...")
        try:
            if not self.semantic.analyze(ast):
                print("❌ Semantic analysis failed!")
                error_handler.print_summary()
                return False
            print("✅ Semantic analysis successful.")
        except Exception as e:
            print(f"❌ Semantic analysis error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        # Phase 4: Interpretation (Code Generation/Execution)
        print("\nPhase 4: Execution...")
        print("-" * 40)
        
        try:
            if not self.interpreter.interpret(ast):
                print("❌ Execution failed!")
                error_handler.print_summary()
                return False
        except Exception as e:
            print(f"❌ Execution error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
        print("-" * 40)
        print("✅ Execution completed successfully.")
        
        # Print final symbol table if no errors and verbose mode
        if not error_handler.has_errors:
            print("\nFinal Symbol Table:")
            print(self.semantic.symbol_table)
        
        error_handler.print_summary()
        return True
    
    def run_file(self, filename):
        """Read and compile a source file."""
        try:
            # Check if file exists
            if not os.path.exists(filename):
                print(f"❌ Error: File '{filename}' not found.")
                return False
            
            # Read file with proper encoding
            with open(filename, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
            print(f"📄 File loaded: {filename}")
            print(f"   Size: {len(source_code)} characters")
            print(f"   Lines: {len(source_code.splitlines())}")
            
            return self.compile_and_run(source_code, filename)
            
        except UnicodeDecodeError:
            print(f"❌ Error: File '{filename}' has invalid encoding. Please use UTF-8.")
            return False
        except PermissionError:
            print(f"❌ Error: Permission denied reading file '{filename}'.")
            return False
        except Exception as e:
            print(f"❌ Error reading file: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_repl(self):
        """Run the interactive REPL (Read-Eval-Print Loop)."""
        print("\n" + "="*60)
        print("NovaScript REPL v1.0")
        print("Type 'exit()' to quit, 'clear()' to clear screen")
        print("Use '\\' at end of a line to continue on the next line")
        print("="*60)

        while True:
            try:
                # ── read one complete statement (support '\' line continuation) ──
                lines = []
                while True:
                    prompt = "\n>>> " if not lines else "... "
                    line   = input(prompt)

                    stripped = line.strip()

                    if stripped == 'exit()':
                        print("Goodbye!")
                        return

                    if stripped == 'clear()':
                        os.system('cls' if os.name == 'nt' else 'clear')
                        lines = []
                        continue

                    # Line continuation: user ended the line with '\'
                    if stripped.endswith('\\'):
                        lines.append(stripped[:-1])   # drop the trailing '\'
                        continue

                    lines.append(line)

                    # A non-empty line with no continuation → statement complete
                    if stripped:
                        source = '\n'.join(lines)
                        break
                    # empty line → keep prompting (allow blank lines inside blocks)

                # ── reset ALL state before each run (fixes error accumulation) ──
                error_handler.reset()
                self.lexer       = NovaScriptLexer();  self.lexer.build()
                self.parser      = NovaScriptParser(); self.parser.build()
                self.semantic    = SemanticAnalyzer()
                self.interpreter = Interpreter()

                self.compile_and_run(source)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'exit()' to quit.")
                continue
            except EOFError:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='NovaScript Compiler and Interpreter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py examples/if_example.nova    # Run a file
  python main.py -i                          # Start interactive REPL
  python main.py -v examples/loop_examples.nova  # Run with verbose output
        """
    )
    
    parser.add_argument(
        'file',
        nargs='?',
        help='Source file to compile and run'
    )
    
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Start interactive REPL'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Create compiler instance
    compiler = NovaScriptCompiler()
    
    # Run in appropriate mode
    if args.interactive or not args.file:
        compiler.run_repl()
    else:
        success = compiler.run_file(args.file)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()