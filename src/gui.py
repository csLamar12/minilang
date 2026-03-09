#!/usr/bin/env python3
"""
MiniLang Compiler - Graphical User Interface
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys
import os
import re
from threading import Thread
import queue

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lexer import MiniLangLexer
from parser import MiniLangParser
from semantic import SemanticAnalyzer
from interpreter import Interpreter
from error_handler import error_handler
from ast_nodes import ASTNode, Comment
import config_manager


# ============================================================================
# Error help database
# ============================================================================
_ERROR_HELP = {
    'LEXICAL': {
        'default': (
            "A lexical error means the scanner found a character or sequence "
            "that is not part of the MiniLang alphabet.",
            "Check for typos, unsupported symbols, or unclosed string literals."
        ),
        'Illegal character': (
            "The character you used is not recognised as part of MiniLang's character set.",
            "Remove or replace the character. MiniLang supports letters, digits, "
            "standard operators, parentheses, and double-quoted strings."
        ),
    },
    'SYNTAX': {
        'default': (
            "A syntax error means the program's structure does not match MiniLang's grammar.",
            "Check that every 'if', 'while', 'for', 'try', and 'begin' block "
            "is closed with 'end', and each statement is on its own line."
        ),
        "Syntax error at '": (
            "The parser found an unexpected token where a different token was expected.",
            "Review the highlighted line. Ensure keywords are spelled correctly "
            "and the code follows MiniLang grammar."
        ),
        'Syntax error at EOF': (
            "The program ended unexpectedly — most likely a missing 'end' keyword.",
            "Count your 'if / while / for / try / begin' blocks and make sure "
            "each one has a matching 'end'."
        ),
    },
    'SEMANTIC': {
        'default': (
            "A semantic error means the code is grammatically correct but "
            "logically invalid.",
            "Check variable declarations and usages carefully."
        ),
        'used before declaration': (
            "You are using a variable that has not been declared yet.",
            "Add  let variableName = value  before the first use of the variable."
        ),
        'not declared before assignment': (
            "You are trying to assign to a variable that was never declared.",
            "Declare it first:  let variableName = initialValue"
        ),
        'already declared': (
            "A variable with the same name was already declared in this scope.",
            "Use plain assignment  x = newValue  instead of 'let' to update "
            "an existing variable."
        ),
        "outside of loop": (
            "The 'break' statement can only appear inside a 'while' or 'for' loop.",
            "Move the 'break' statement into the body of a loop."
        ),
        'Cannot redeclare': (
            "The for-loop variable name conflicts with an existing declaration.",
            "Rename either the for-loop variable or the existing variable."
        ),
    },
    'RUNTIME': {
        'default': (
            "A runtime error occurred while the program was executing.",
            "Wrap risky operations in a try / catch block to handle errors gracefully."
        ),
        'Division by zero': (
            "The program tried to divide a number by zero, which is undefined.",
            "Wrap the division in a try/catch, or add a guard:\n"
            "  if divisor != 0\n      let result = value / divisor\n  end"
        ),
        'Modulo by zero': (
            "The program tried to compute the remainder when dividing by zero.",
            "Check that the right-hand side of '%' is non-zero before the operation."
        ),
        'undeclared variable': (
            "A variable was referenced in an expression but was never declared.",
            "Add  let variableName = value  before the line that uses it."
        ),
        'Maximum loop iterations': (
            "The loop exceeded the maximum allowed iterations (10,000). "
            "It may be an infinite loop.",
            "Ensure the loop condition will eventually become false, and that "
            "the loop variable is updated inside the loop body."
        ),
        'Step value cannot be zero': (
            "A for-loop was given a step of zero, which would loop forever.",
            "Change the 'step' value to a non-zero number."
        ),
    },
    'WARNING': {
        'default': (
            "A warning is a potential issue that does not prevent execution.",
            "Review the warning and make sure the code behaves as intended."
        ),
        'Division by zero in constant': (
            "The compiler detected a constant division by zero. "
            "The program will raise a runtime error on this line.",
            "Change the divisor or wrap the expression in a try/catch block."
        ),
        'Modulo by zero in constant': (
            "The compiler detected a constant modulo by zero.",
            "Change the divisor in the '%' expression to a non-zero value."
        ),
    },
}


def _lookup_error_help(error_type: str, message: str):
    bucket = _ERROR_HELP.get(error_type) or _ERROR_HELP.get('RUNTIME', {})
    for key, (defn, hint) in bucket.items():
        if key != 'default' and key.lower() in message.lower():
            return defn, hint
    defn, hint = bucket.get('default', ("An error occurred.", "Review the code at the indicated line."))
    return defn, hint


# ============================================================================
# Canvas tree drawing helpers
# ============================================================================

# Visual style
_TREE_UNIT_W   = 130   # minimum horizontal pixels per leaf "slot"
_TREE_LEVEL_H  = 92    # vertical pixels between depth levels
_TREE_MARGIN   = 65    # canvas edge padding

_NODE_FONT_INT = ('Arial', 10, 'bold')   # internal / parent nodes
_NODE_FONT_LEAF= ('Arial',  9)           # leaf / terminal nodes

# Internal (parent) node colours
_NODE_FG      = '#7A3500'   # dark-brown text for readability on cream
_NODE_FILL    = '#FFF0D0'   # warm cream background
_NODE_OUTLINE = '#FF8C00'   # orange border

# Leaf / terminal node colours
_LEAF_FG      = '#333333'   # near-black text
_LEAF_FILL    = '#F0F0F0'   # light grey background
_LEAF_OUTLINE = '#999999'   # medium grey border

# Connecting lines
_LINE_COLOR   = '#777777'   # medium grey

# Node box geometry
_BOX_PADX     = 12   # extra pixels left+right of text in each box
_BOX_INT_HH   = 13   # half-height of internal-node box  (bold-10 ≈ 14 px tall)
_BOX_LEAF_HH  = 11   # half-height of leaf-node box      (reg-9  ≈ 12 px tall)
_BOX_CHAR_W   =  6   # approximate pixel-width per character (used for hw calc)


class _TNode:
    """Lightweight tree node used only for canvas rendering."""
    __slots__ = ('label', 'is_leaf', 'children', 'x', 'y', 'width')

    def __init__(self, label: str, is_leaf: bool = False):
        self.label    = label
        self.is_leaf  = is_leaf
        self.children = []
        self.x = self.y = self.width = 0


def _compute_width(node: _TNode) -> int:
    if not node.children:
        node.width = 1
        return 1
    node.width = sum(_compute_width(c) for c in node.children)
    return node.width


def _assign_positions(node: _TNode, left: float, depth: int, unit_w: int):
    node.x = left + node.width * unit_w / 2
    node.y = _TREE_MARGIN + depth * _TREE_LEVEL_H
    cursor = left
    for child in node.children:
        _assign_positions(child, cursor, depth + 1, unit_w)
        cursor += child.width * unit_w


def _max_depth(node: _TNode) -> int:
    if not node.children:
        return 0
    return 1 + max(_max_depth(c) for c in node.children)


def _max_label_hw(node: _TNode) -> int:
    """Return the largest box half-width (px) needed by any node in the subtree."""
    hw = len(node.label) * _BOX_CHAR_W + _BOX_PADX
    for c in node.children:
        hw = max(hw, _max_label_hw(c))
    return hw


def _draw_on_canvas(canvas: tk.Canvas, node: _TNode):
    """Draw the tree: lines behind everything, then filled node boxes, then text."""
    nhh = _BOX_LEAF_HH if node.is_leaf else _BOX_INT_HH
    for child in node.children:
        chh = _BOX_LEAF_HH if child.is_leaf else _BOX_INT_HH
        # Line connects bottom-centre of parent box → top-centre of child box
        canvas.create_line(
            node.x,  node.y + nhh,
            child.x, child.y - chh,
            fill=_LINE_COLOR, width=1.5,
        )
        _draw_on_canvas(canvas, child)

    # Pill-shaped box (rectangle) behind label
    hw = max(len(node.label) * _BOX_CHAR_W + _BOX_PADX, 22)
    if node.is_leaf:
        fill, outline, fg, font = _LEAF_FILL, _LEAF_OUTLINE, _LEAF_FG, _NODE_FONT_LEAF
    else:
        fill, outline, fg, font = _NODE_FILL, _NODE_OUTLINE, _NODE_FG, _NODE_FONT_INT
    canvas.create_rectangle(
        node.x - hw, node.y - nhh,
        node.x + hw, node.y + nhh,
        fill=fill, outline=outline, width=1.5,
    )
    canvas.create_text(node.x, node.y, text=node.label, fill=fg, font=font)


def _render_tree(canvas: tk.Canvas, root: _TNode):
    """Compute layout then draw the _TNode tree on the given canvas."""
    canvas.delete('all')
    if root is None:
        canvas.create_text(80, 40, text="(empty)", fill='gray', font=('Arial', 10))
        return
    _compute_width(root)
    # Adaptive unit width: guarantee no two neighbouring boxes overlap
    max_hw  = _max_label_hw(root)
    unit_w  = max(_TREE_UNIT_W, max_hw * 2 + 24)
    _assign_positions(root, _TREE_MARGIN, 0, unit_w)
    depth   = _max_depth(root)
    total_w = root.width * unit_w + 2 * _TREE_MARGIN
    total_h = (depth + 1) * _TREE_LEVEL_H + 2 * _TREE_MARGIN
    canvas.config(scrollregion=(0, 0, max(total_w, 600), max(total_h, 300)))
    _draw_on_canvas(canvas, root)


# ── AST → _TNode ────────────────────────────────────────────────────────────

def _ast_to_tnode(node) -> _TNode:
    """Convert an AST node to a _TNode for the AST visual view."""
    if node is None or isinstance(node, Comment):
        return None

    nt = type(node).__name__

    # Label helpers
    if nt == 'Declaration':  label = f"let {node.identifier} ="
    elif nt == 'Assignment': label = f"{node.identifier} ="
    elif nt == 'BinaryOp':   label = node.op
    elif nt == 'UnaryOp':    label = f"unary {node.op}"
    elif nt == 'Identifier': return _TNode(node.name, is_leaf=True)
    elif nt == 'IntegerLiteral': return _TNode(str(node.value), is_leaf=True)
    elif nt == 'FloatLiteral':   return _TNode(str(node.value), is_leaf=True)
    elif nt == 'StringLiteral':
        v = node.value if len(node.value) <= 12 else node.value[:10] + '..'
        return _TNode(f'"{v}"', is_leaf=True)
    elif nt == 'BooleanLiteral': return _TNode(str(node.value), is_leaf=True)
    elif nt == 'Break':     return _TNode('break', is_leaf=True)
    elif nt == 'For':       label = f"for {node.identifier}"
    elif nt == 'While':     label = 'while'
    elif nt == 'If':        label = 'if'
    elif nt == 'TryCatch':  label = 'try/catch'
    elif nt == 'Display':   label = 'display'
    elif nt == 'Block':     label = 'block'
    elif nt == 'Program':   label = 'Program'
    elif nt == 'Expression':
        return _ast_to_tnode(node.expression)
    else:                   label = nt

    tnode = _TNode(label)
    for child in _ast_children(node):
        ct = _ast_to_tnode(child)
        if ct:
            tnode.children.append(ct)
    return tnode


def _ast_children(node) -> list:
    """Return meaningful child ASTNodes, skipping Comments and None."""
    nt = type(node).__name__
    raw = []
    if nt == 'Program':
        raw = node.statements or []
    elif nt == 'Declaration':
        raw = [node.expression]
    elif nt == 'Assignment':
        raw = [node.expression]
    elif nt == 'Display':
        raw = node.items or []
    elif nt == 'If':
        raw = ([node.condition]
               + (node.then_statements or [])
               + (node.else_statements or []))
    elif nt == 'While':
        raw = [node.condition] + (node.statements or [])
    elif nt == 'For':
        raw = ([node.start_expr, node.end_expr]
               + ([node.step_expr] if node.step_expr else [])
               + (node.statements or []))
    elif nt == 'TryCatch':
        raw = (node.try_statements or []) + (node.catch_statements or [])
    elif nt == 'Block':
        raw = node.statements or []
    elif nt == 'BinaryOp':
        raw = [node.left, node.right]
    elif nt == 'UnaryOp':
        raw = [node.expr]
    elif nt == 'Expression':
        raw = [node.expression]
    return [c for c in raw
            if c is not None and isinstance(c, ASTNode) and not isinstance(c, Comment)]


# ── Parse Tree → _TNode ─────────────────────────────────────────────────────

def _pt_to_tnode(node) -> _TNode:
    """
    Convert an AST node to a _TNode for the Parse Tree visual view.
    Shows grammar-level structure including terminal keywords as leaf nodes.
    """
    if node is None or isinstance(node, Comment):
        return None

    nt = type(node).__name__

    def leaf(text):  return _TNode(text, is_leaf=True)
    def stmts(lst):
        """Build child tnodes from a statement list, filtering comments/strs."""
        out = []
        for s in (lst or []):
            if s is None or not isinstance(s, ASTNode) or isinstance(s, Comment):
                continue
            c = _pt_to_tnode(s)
            if c:
                out.append(c)
        return out

    if nt == 'Program':
        root = _TNode('Program')
        root.children = stmts(node.statements)
        return root

    elif nt == 'Declaration':
        root = _TNode('Declaration')
        root.children = [leaf('let'), leaf(node.identifier), leaf('=')]
        e = _pt_to_tnode(node.expression)
        if e: root.children.append(e)
        return root

    elif nt == 'Assignment':
        root = _TNode('Assign')
        root.children = [leaf(node.identifier), leaf('=')]
        e = _pt_to_tnode(node.expression)
        if e: root.children.append(e)
        return root

    elif nt == 'Display':
        root = _TNode('Display')
        root.children = []
        for item in (node.items or []):
            c = _pt_to_tnode(item)
            if c: root.children.append(c)
        return root

    elif nt == 'BinaryOp':
        root = _TNode('BinOp')
        l = _pt_to_tnode(node.left)
        if l: root.children.append(l)
        root.children.append(leaf(node.op))
        r = _pt_to_tnode(node.right)
        if r: root.children.append(r)
        return root

    elif nt == 'UnaryOp':
        root = _TNode('UnaryOp')
        root.children = [leaf(node.op)]
        e = _pt_to_tnode(node.expr)
        if e: root.children.append(e)
        return root

    elif nt == 'Identifier':  return leaf(f"id:{node.name}")
    elif nt == 'IntegerLiteral': return leaf(str(node.value))
    elif nt == 'FloatLiteral':   return leaf(str(node.value))
    elif nt == 'StringLiteral':
        v = node.value if len(node.value) <= 10 else node.value[:8] + '..'
        return leaf(f'"{v}"')
    elif nt == 'BooleanLiteral': return leaf(str(node.value))
    elif nt == 'Break':          return leaf('break')

    elif nt == 'If':
        root = _TNode('If')
        root.children = []
        cond = _pt_to_tnode(node.condition)
        if cond: root.children.append(cond)
        then_n = _TNode('then')
        then_n.children = stmts(node.then_statements)
        root.children.append(then_n)
        if node.else_statements:
            else_n = _TNode('else')
            else_n.children = stmts(node.else_statements)
            root.children.append(else_n)
        root.children.append(leaf('end'))
        return root

    elif nt == 'While':
        root = _TNode('While')
        root.children = []
        cond = _pt_to_tnode(node.condition)
        if cond: root.children.append(cond)
        body = _TNode('body')
        body.children = stmts(node.statements)
        root.children.append(body)
        root.children.append(leaf('end'))
        return root

    elif nt == 'For':
        root = _TNode(f"for {node.identifier}")
        root.children = []
        s = _pt_to_tnode(node.start_expr)
        if s: root.children.append(s)
        root.children.append(leaf('to'))
        e = _pt_to_tnode(node.end_expr)
        if e: root.children.append(e)
        if node.step_expr:
            root.children.append(leaf('step'))
            st = _pt_to_tnode(node.step_expr)
            if st: root.children.append(st)
        body = _TNode('body')
        body.children = stmts(node.statements)
        root.children.append(body)
        root.children.append(leaf('end'))
        return root

    elif nt == 'TryCatch':
        root = _TNode('TryCatch')
        root.children = []
        tb = _TNode('try_body')
        tb.children = stmts(node.try_statements)
        root.children.append(tb)
        root.children.append(leaf('catch'))
        cb = _TNode('catch_body')
        cb.children = stmts(node.catch_statements)
        root.children.append(cb)
        root.children.append(leaf('end'))
        return root

    elif nt == 'Block':
        root = _TNode('Block')
        root.children = stmts(node.statements)
        return root

    elif nt == 'Expression':
        return _pt_to_tnode(node.expression)

    else:
        return _TNode(nt)


# ============================================================================
# GUI class
# ============================================================================

class MiniLangGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("MiniLang Compiler v1.0")
        self.root.geometry("1200x800")

        self.current_file   = None
        self.file_modified  = False
        self.output_queue   = queue.Queue()
        self.current_ast    = None
        self.running        = False

        self.reset_compiler()
        config_manager.apply_api_key()   # load saved API key into env at startup
        self.setup_menu()
        self.setup_toolbar()
        self.setup_main_area()
        self.setup_status_bar()
        self.setup_bindings()
        self.process_output_queue()
        self.show_welcome()
        self.update_line_numbers_periodically()

    # -------------------------------------------------------------------------
    def reset_compiler(self):
        self.lexer       = MiniLangLexer();  self.lexer.build()
        self.parser      = MiniLangParser(); self.parser.build()
        self.semantic    = SemanticAnalyzer()
        self.interpreter = Interpreter()
        self.current_ast = None
        self.pt_tnode    = None   # cached for pop-out
        self.ast_tnode   = None   # cached for pop-out
        error_handler.errors   = []
        error_handler.warnings = []
        error_handler.has_errors = False

    # =========================================================================
    # Menu
    # =========================================================================
    def setup_menu(self):
        mb = tk.Menu(self.root); self.root.config(menu=mb)

        fm = tk.Menu(mb, tearoff=0); mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="New",       command=self.new_file,     accelerator="Ctrl+N")
        fm.add_command(label="Open...",   command=self.open_file,    accelerator="Ctrl+O")
        fm.add_command(label="Save",      command=self.save_file,    accelerator="Ctrl+S")
        fm.add_command(label="Save As...",command=self.save_file_as, accelerator="Ctrl+Shift+S")
        fm.add_separator()
        fm.add_command(label="Exit", command=self.exit_app)

        em = tk.Menu(mb, tearoff=0); mb.add_cascade(label="Edit", menu=em)
        em.add_command(label="Undo",  command=self.undo,  accelerator="Ctrl+Z")
        em.add_command(label="Redo",  command=self.redo,  accelerator="Ctrl+Y")
        em.add_separator()
        em.add_command(label="Cut",   command=self.cut,   accelerator="Ctrl+X")
        em.add_command(label="Copy",  command=self.copy,  accelerator="Ctrl+C")
        em.add_command(label="Paste", command=self.paste, accelerator="Ctrl+V")
        em.add_separator()
        em.add_command(label="Find...", command=self.find, accelerator="Ctrl+F")

        rm = tk.Menu(mb, tearoff=0); mb.add_cascade(label="Run", menu=rm)
        rm.add_command(label="Run Program", command=self.run_program,  accelerator="F5")
        rm.add_command(label="Stop",        command=self.stop_program, accelerator="F8")
        rm.add_separator()
        rm.add_command(label="Clear Output", command=self.clear_output)

        tm = tk.Menu(mb, tearoff=0); mb.add_cascade(label="Tools", menu=tm)
        tm.add_command(label="Show Tokens",       command=self.show_tokens)
        tm.add_command(label="Show Parse Tree",   command=self.show_parse_tree)
        tm.add_command(label="Show AST",          command=self.show_ast)
        tm.add_command(label="Show Symbol Table", command=self.show_symbol_table)
        tm.add_separator()
        tm.add_command(label="Reset Compiler", command=self.reset_compiler)
        tm.add_separator()
        tm.add_command(label="⚙  Settings…",  command=self.open_settings)

        xm = tk.Menu(mb, tearoff=0); mb.add_cascade(label="Examples", menu=xm)
        xm.add_command(label="Hello World",        command=lambda: self.load_example("hello"))
        xm.add_command(label="If Statement",       command=lambda: self.load_example("if"))
        xm.add_command(label="If-Else Chain",      command=lambda: self.load_example("if_chain"))
        xm.add_command(label="While Loop",         command=lambda: self.load_example("while"))
        xm.add_command(label="For Loop",           command=lambda: self.load_example("for"))
        xm.add_command(label="Exception Handling", command=lambda: self.load_example("try_catch"))
        xm.add_command(label="Comprehensive",      command=lambda: self.load_example("comprehensive"))

        vm = tk.Menu(mb, tearoff=0); mb.add_cascade(label="View", menu=vm)
        for i, lbl in enumerate(["Output","Errors","Tokens","Parse Tree","AST","Symbol Table","🤖 AI Assistant"]):
            vm.add_command(label=lbl, command=lambda n=i: self.notebook.select(n))

        hm = tk.Menu(mb, tearoff=0); mb.add_cascade(label="Help", menu=hm)
        hm.add_command(label="Quick Reference", command=self.show_quick_ref)
        hm.add_separator()
        hm.add_command(label="About", command=self.show_about)

        self.root.bind_all("<Control-n>",       lambda e: self.new_file())
        self.root.bind_all("<Control-o>",       lambda e: self.open_file())
        self.root.bind_all("<Control-s>",       lambda e: self.save_file())
        self.root.bind_all("<Control-Shift-S>", lambda e: self.save_file_as())
        self.root.bind_all("<F5>",              lambda e: self.run_program())
        self.root.bind_all("<F8>",              lambda e: self.stop_program())

    # =========================================================================
    # Toolbar
    # =========================================================================
    def setup_toolbar(self):
        tb = ttk.Frame(self.root); tb.pack(side=tk.TOP, fill=tk.X)
        for text, cmd in [
            ("New", self.new_file), ("Open", self.open_file), ("Save", self.save_file),
            ("|", None),
            ("▶  Run", self.run_program), ("■  Stop", self.stop_program),
            ("|", None),
            ("Clear", self.clear_output),
            ("|", None),
            ("Tokens", self.show_tokens), ("Parse Tree", self.show_parse_tree),
            ("AST", self.show_ast), ("Values", self.show_runtime_values),
            ("|", None),
            ("🤖 AI", lambda: self.notebook.select(6)),
            ("|", None),
            ("⚙ Settings", self.open_settings),
        ]:
            if text == "|":
                ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)
            else:
                ttk.Button(tb, text=text, command=cmd).pack(side=tk.LEFT, padx=2, pady=2)
        self.run_status = ttk.Label(tb, text="● Ready", foreground="green")
        self.run_status.pack(side=tk.RIGHT, padx=10)

    def show_runtime_values(self):
        self.show_symbol_table_in_tab(self.interpreter.symbol_table, "RUNTIME VALUES")
        self.notebook.select(5)

    # =========================================================================
    # Main area
    # =========================================================================
    def setup_main_area(self):
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        lf = ttk.Frame(paned); paned.add(lf, weight=2)
        self.create_editor(lf)

        rf = ttk.Frame(paned); paned.add(rf, weight=1)
        self.notebook = ttk.Notebook(rf)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        for (text, builder) in [
            ("Output",       self.create_output_area),
            ("Errors",       self.create_error_area),
            ("Tokens",       self.create_tokens_area),
            ("Parse Tree",   self.create_parse_tree_area),
            ("AST",          self.create_ast_area),
            ("Symbol Table", self.create_symbol_area),
            ("🤖 AI",        self.create_ai_area),
        ]:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=text)
            builder(frame)

    # =========================================================================
    # Editor
    # =========================================================================
    def create_editor(self, parent):
        ef = ttk.Frame(parent); ef.pack(fill=tk.BOTH, expand=True)
        self.line_numbers = tk.Text(
            ef, width=4, padx=5, takefocus=0, border=0,
            background='#f0f0f0', foreground='#666666',
            state='disabled', font=('Courier New', 10), wrap=tk.NONE,
        )
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        self.editor = scrolledtext.ScrolledText(
            ef, wrap=tk.NONE, font=('Courier New', 10), undo=True,
            background='white', foreground='black', insertbackground='black',
            selectbackground='#c0c0c0', width=80, height=30,
        )
        self.editor.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self._setup_syntax_tags()
        self.editor.bind('<KeyRelease>', self.on_editor_change)
        self.editor.bind('<MouseWheel>', self.on_editor_scroll)
        self.editor.bind('<Button-1>',   self.on_editor_click)
        self.editor.bind('<Configure>',  self.on_editor_resize)
        self.editor.vbar.bind('<B1-Motion>',      self.on_editor_scroll)
        self.editor.vbar.bind('<ButtonRelease-1>', self.on_editor_scroll)

    def _setup_syntax_tags(self):
        self.editor.tag_configure("keyword",  foreground="#0000FF", font=('Courier New', 10, 'bold'))
        self.editor.tag_configure("string",   foreground="#008000")
        self.editor.tag_configure("comment",  foreground="#808080", font=('Courier New', 10, 'italic'))
        self.editor.tag_configure("number",   foreground="#FF00FF")
        self.editor.tag_configure("operator", foreground="#FF0000")
        self.editor.tag_configure("boolean",  foreground="#FF8C00", font=('Courier New', 10, 'bold'))

    # =========================================================================
    # Output
    # =========================================================================
    def create_output_area(self, parent):
        self.output_text = scrolledtext.ScrolledText(
            parent, wrap=tk.WORD, font=('Consolas', 10),
            background='black', foreground='white',
        )
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.tag_configure("error",   foreground="#FF5555")
        self.output_text.tag_configure("success", foreground="#55FF55")
        self.output_text.tag_configure("info",    foreground="#5555FF")
        self.output_text.tag_configure("output",  foreground="#FFFFFF")

    # =========================================================================
    # Errors — split panel with click-to-detail
    # =========================================================================
    def create_error_area(self, parent):
        list_lf = ttk.LabelFrame(parent, text="Errors & Warnings  —  click a row to see details")
        list_lf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))

        self.error_text = scrolledtext.ScrolledText(
            list_lf, wrap=tk.WORD, font=('Consolas', 10),
            background='#1e1e1e', foreground='#d4d4d4', height=10,
        )
        self.error_text.pack(fill=tk.BOTH, expand=True)

        for tag, fg, bold in [
            ('header',  '#888888', False),
            ('LEXICAL', '#f4a261', True),
            ('SYNTAX',  '#e63946', True),
            ('SEMANTIC','#ffd166', True),
            ('RUNTIME', '#ff6b6b', True),
            ('WARNING', '#a8e6a3', True),
            ('normal',  '#d4d4d4', False),
        ]:
            self.error_text.tag_configure(
                tag,
                foreground=fg,
                font=('Consolas', 10, 'bold') if bold else ('Consolas', 10),
            )
        # highlight on hover
        self.error_text.tag_configure('hover', background='#2a2a2a')

        detail_lf = ttk.LabelFrame(parent, text="Error Details")
        detail_lf.pack(fill=tk.X, padx=4, pady=(2, 4))

        self.error_detail = scrolledtext.ScrolledText(
            detail_lf, wrap=tk.WORD, font=('Consolas', 10),
            background='#252526', foreground='#cccccc',
            height=7, state='disabled',
        )
        self.error_detail.pack(fill=tk.BOTH, expand=True)
        self.error_detail.tag_configure('type_lbl',  foreground='#9cdcfe', font=('Consolas', 10, 'bold'))
        self.error_detail.tag_configure('body',      foreground='#cccccc')
        self.error_detail.tag_configure('what_lbl',  foreground='#dcdcaa', font=('Consolas', 10, 'bold'))
        self.error_detail.tag_configure('how_lbl',   foreground='#4ec9b0', font=('Consolas', 10, 'bold'))
        self.error_detail.tag_configure('how_body',  foreground='#ce9178')
        self.error_detail.tag_configure('ok',        foreground='#6a9955', font=('Consolas', 11, 'bold'))

        # AI quick-action button below the detail panel
        ttk.Button(
            detail_lf,
            text="🤖  Ask AI to explain & fix this error",
            command=self.ai_explain_error,
        ).pack(side=tk.LEFT, padx=6, pady=(0, 6))

        # We use tag-bound click events — see show_errors()

    def _show_error_detail(self, entry):
        etype = entry.get('type', 'RUNTIME')
        msg   = entry.get('message', '')
        defn, hint = _lookup_error_help(etype, msg)

        self.error_detail.config(state='normal')
        self.error_detail.delete('1.0', tk.END)
        self.error_detail.insert(tk.END, f"  [{etype}]  Line {entry.get('line', '?')}:  ", 'type_lbl')
        self.error_detail.insert(tk.END, f"{msg}\n\n", 'body')
        self.error_detail.insert(tk.END, "  What this means:\n", 'what_lbl')
        self.error_detail.insert(tk.END, f"    {defn}\n\n", 'body')
        self.error_detail.insert(tk.END, "  How to fix it:\n", 'how_lbl')
        for line in hint.splitlines():
            self.error_detail.insert(tk.END, f"    {line}\n", 'how_body')
        self.error_detail.config(state='disabled')

    def show_errors(self):
        self.error_text.config(state='normal')
        self.error_text.delete('1.0', tk.END)

        # Remove any previously-bound error tags
        for t in self.error_text.tag_names():
            if t.startswith('_err_'):
                self.error_text.tag_delete(t)

        all_entries = (
            [dict(e) for e in error_handler.errors] +
            [dict(w, type='WARNING') for w in error_handler.warnings]
        )

        if not all_entries:
            self.error_text.insert(tk.END, "  No errors or warnings.\n", 'header')
            self.error_detail.config(state='normal')
            self.error_detail.delete('1.0', tk.END)
            self.error_detail.insert(tk.END, "  ✅  Program compiled without errors.", 'ok')
            self.error_detail.config(state='disabled')
            return

        nerr  = len(error_handler.errors)
        nwarn = len(error_handler.warnings)
        self.error_text.insert(tk.END,
            f"  {nerr} error{'s' if nerr!=1 else ''}   ·   "
            f"{nwarn} warning{'s' if nwarn!=1 else ''}\n\n", 'header')

        icons = {'LEXICAL':'⚠ ','SYNTAX':'✖ ','SEMANTIC':'⚑ ','RUNTIME':'✖ ','WARNING':'△ '}

        for idx, entry in enumerate(all_entries):
            etype = entry.get('type', 'RUNTIME')
            icon  = icons.get(etype, '• ')

            # Unique tag for this row — bind click to it
            row_tag = f'_err_{idx}'
            self.error_text.tag_configure(row_tag)  # no visual style needed
            entry_snap = dict(entry)                  # snapshot for the closure

            row_start = self.error_text.index(tk.END)

            self.error_text.insert(tk.END,
                f"  {icon}[{etype}]  Line {entry.get('line','?')}:  {entry.get('message','')}\n",
                (etype, row_tag))
            self.error_text.insert(tk.END,
                "  " + "─" * 48 + "\n",
                ('header', row_tag))

            # Hover highlight
            self.error_text.tag_bind(row_tag, '<Enter>',
                lambda e, t=row_tag: self.error_text.tag_configure(t, background='#2a2a2a'))
            self.error_text.tag_bind(row_tag, '<Leave>',
                lambda e, t=row_tag: self.error_text.tag_configure(t, background=''))

            # ← THE FIX: bind click on this row's unique tag directly
            self.error_text.tag_bind(row_tag, '<ButtonRelease-1>',
                lambda e, ent=entry_snap: self._show_error_detail(ent))

        # Auto-show first entry
        if all_entries:
            self._show_error_detail(all_entries[0])

        self.notebook.select(1)

    # =========================================================================
    # Tokens — Treeview with categories + "All tokens in order"
    # =========================================================================
    def create_tokens_area(self, parent):
        self.tokens_summary = ttk.Label(parent, text="", font=('Consolas', 9))
        self.tokens_summary.pack(side=tk.TOP, anchor='w', padx=6, pady=(4, 1))

        tf = ttk.Frame(parent); tf.pack(fill=tk.BOTH, expand=True)

        self.tokens_tree = ttk.Treeview(
            tf, columns=('type', 'value', 'line'),
            show='tree headings', selectmode='browse',
        )
        self.tokens_tree.heading('#0',    text='Category / Token', anchor='w')
        self.tokens_tree.heading('type',  text='Token Type',        anchor='w')
        self.tokens_tree.heading('value', text='Value',             anchor='w')
        self.tokens_tree.heading('line',  text='Line',              anchor='center')
        self.tokens_tree.column('#0',    width=200, minwidth=140)
        self.tokens_tree.column('type',  width=130, minwidth=100)
        self.tokens_tree.column('value', width=160, minwidth=100)
        self.tokens_tree.column('line',  width=55,  minwidth=40, anchor='center')

        ysb = ttk.Scrollbar(tf, orient=tk.VERTICAL,   command=self.tokens_tree.yview)
        xsb = ttk.Scrollbar(tf, orient=tk.HORIZONTAL, command=self.tokens_tree.xview)
        self.tokens_tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        ysb.pack(side=tk.RIGHT,  fill=tk.Y)
        xsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tokens_tree.pack(fill=tk.BOTH, expand=True)

        self.tokens_tree.tag_configure('cat',        font=('Consolas', 9, 'bold'))
        self.tokens_tree.tag_configure('keyword',    background='#e8f0fe', foreground='#0d47a1')
        self.tokens_tree.tag_configure('identifier', background='#e8f5e9', foreground='#1b5e20')
        self.tokens_tree.tag_configure('literal',    background='#fffde7', foreground='#827717')
        self.tokens_tree.tag_configure('operator',   background='#fce4ec', foreground='#880e4f')
        self.tokens_tree.tag_configure('structural', background='#f5f5f5', foreground='#9e9e9e')

    _KW  = {'LET','DISPLAY','TRY','CATCH','IF','ELSE','WHILE','FOR',
             'TO','STEP','BEGIN','END','BREAK','NOT','AND','OR'}
    _OP  = {'PLUS','MINUS','TIMES','DIVIDE','MODULO','ASSIGN',
             'EQ','NEQ','LT','GT','LE','GE'}
    _LIT = {'INTEGER','FLOAT','STRING','BOOLEAN'}
    _ID  = {'IDENTIFIER'}
    _STR = {'NEWLINE', 'COMMENT'}

    def _tok_tag(self, tok_type):
        if tok_type in self._KW:  return 'keyword'
        if tok_type in self._ID:  return 'identifier'
        if tok_type in self._LIT: return 'literal'
        if tok_type in self._OP:  return 'operator'
        if tok_type in self._STR: return 'structural'
        return 'identifier'

    def _tok_val(self, tok):
        if tok.type == 'NEWLINE': return '\\n'
        v = str(tok.value)
        return v[:38] + '..' if len(v) > 40 else v

    def show_tokens_in_tab(self, tokens):
        for item in self.tokens_tree.get_children():
            self.tokens_tree.delete(item)

        meaningful = sum(1 for t in tokens if t.type not in self._STR)
        structural  = len(tokens) - meaningful
        self.tokens_summary.config(
            text=f"  {meaningful} meaningful   ·   {structural} structural (NEWLINE / COMMENT)"
                 f"   ·   {len(tokens)} total"
        )

        # ── Section 1: All tokens in order (collapsible, collapsed by default) ──
        all_id = self.tokens_tree.insert(
            '', 'end',
            text=f"  All Tokens in order  ({len(tokens)})",
            values=('', '', ''),
            tags=('cat',),
            open=False,
        )
        for tok in tokens:
            self.tokens_tree.insert(
                all_id, 'end', text='',
                values=(tok.type, self._tok_val(tok), tok.lineno),
                tags=(self._tok_tag(tok.type),),
            )

        # ── Section 2: By category ───────────────────────────────────────────
        CATS = [
            ('Keywords',    'keyword',    self._KW),
            ('Identifiers', 'identifier', self._ID),
            ('Literals',    'literal',    self._LIT),
            ('Operators',   'operator',   self._OP),
            ('Structural',  'structural', self._STR),
        ]
        for name, tag, type_set in CATS:
            items = [t for t in tokens if t.type in type_set]
            if not items:
                continue
            p = self.tokens_tree.insert(
                '', 'end',
                text=f"  {name}  ({len(items)})",
                values=('', '', ''),
                tags=('cat',),
                open=(name != 'Structural'),
            )
            for tok in items:
                self.tokens_tree.insert(
                    p, 'end', text='',
                    values=(tok.type, self._tok_val(tok), tok.lineno),
                    tags=(tag,),
                )

        self.tokens_tree.update_idletasks()

    # =========================================================================
    # Parse Tree — Text View + Canvas Visual Tree
    # =========================================================================
    def create_parse_tree_area(self, parent):
        self.pt_sub = ttk.Notebook(parent)
        self.pt_sub.pack(fill=tk.BOTH, expand=True)

        # Text view
        tf = ttk.Frame(self.pt_sub); self.pt_sub.add(tf, text="Text View")
        self.parse_tree_text = scrolledtext.ScrolledText(
            tf, wrap=tk.NONE, font=('Consolas', 10),
            background='#f8f8f8', foreground='#000000',
        )
        self.parse_tree_text.pack(fill=tk.BOTH, expand=True)
        self.parse_tree_text.tag_configure("node",  foreground="#000080", font=('Consolas', 10, 'bold'))
        self.parse_tree_text.tag_configure("leaf",  foreground="#008000")
        self.parse_tree_text.tag_configure("value", foreground="#FF00FF")
        self.parse_tree_text.tag_configure("line",  foreground="#808080")

        # Canvas visual tree
        vf = ttk.Frame(self.pt_sub); self.pt_sub.add(vf, text="Visual Tree")
        self.pt_canvas = self._make_tree_canvas(
            vf, get_root=lambda: self.pt_tnode, popout_title="Parse Tree — Visual"
        )

    # =========================================================================
    # AST — Text View + Canvas Visual Tree
    # =========================================================================
    def create_ast_area(self, parent):
        self.ast_sub = ttk.Notebook(parent)
        self.ast_sub.pack(fill=tk.BOTH, expand=True)

        # Text view
        tf = ttk.Frame(self.ast_sub); self.ast_sub.add(tf, text="Text View")
        self.ast_text = scrolledtext.ScrolledText(
            tf, wrap=tk.NONE, font=('Consolas', 10),
        )
        self.ast_text.pack(fill=tk.BOTH, expand=True)

        # Canvas visual tree
        vf = ttk.Frame(self.ast_sub); self.ast_sub.add(vf, text="Visual Tree")
        self.ast_canvas = self._make_tree_canvas(
            vf, get_root=lambda: self.ast_tnode, popout_title="AST — Visual"
        )

    def _make_tree_canvas(self, parent, *, get_root=None,
                          popout_title="Visual Tree") -> tk.Canvas:
        """Create a scrollable Canvas for tree drawing.

        Args:
            get_root: optional callable returning the current _TNode root.
                      When supplied a '⤢ Pop Out' button appears in the toolbar.
            popout_title: window title for the pop-out Toplevel.
        """
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True)

        # ── toolbar ──────────────────────────────────────────────────────────
        tb = ttk.Frame(outer)
        tb.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))

        ttk.Label(
            tb,
            text="  ↕ mouse-wheel   ↔ Shift+wheel",
            font=('Consolas', 8), foreground='gray',
        ).pack(side=tk.LEFT, padx=8)

        if get_root is not None:
            def _do_popout():
                tnode = get_root()
                if tnode is None:
                    messagebox.showinfo(
                        "No Tree",
                        "Run the program first to generate a tree.",
                        parent=self.root,
                    )
                    return
                self._open_tree_popout(tnode, title=popout_title)

            ttk.Button(
                tb, text="⤢  Pop Out", command=_do_popout,
            ).pack(side=tk.RIGHT, padx=6, pady=2)

        # ── canvas + scrollbars ───────────────────────────────────────────────
        frame = ttk.Frame(outer)
        frame.pack(fill=tk.BOTH, expand=True)

        c = tk.Canvas(frame, background='white', scrollregion=(0, 0, 800, 600))
        ysb = ttk.Scrollbar(frame, orient=tk.VERTICAL,   command=c.yview)
        xsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=c.xview)
        c.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        ysb.pack(side=tk.RIGHT,  fill=tk.Y)
        xsb.pack(side=tk.BOTTOM, fill=tk.X)
        c.pack(fill=tk.BOTH, expand=True)

        c.bind('<MouseWheel>',       lambda e: c.yview_scroll(int(-1*(e.delta/120)), 'units'))
        c.bind('<Button-4>',         lambda e: c.yview_scroll(-1, 'units'))
        c.bind('<Button-5>',         lambda e: c.yview_scroll( 1, 'units'))
        c.bind('<Shift-MouseWheel>', lambda e: c.xview_scroll(int(-1*(e.delta/120)), 'units'))
        return c

    def _open_tree_popout(self, tnode: '_TNode', title: str = "Visual Tree"):
        """Open a maximised Toplevel and render *tnode* on a fresh canvas."""
        win = tk.Toplevel(self.root)
        win.title(title)

        # Platform-aware maximise
        try:
            if sys.platform == 'win32':
                win.state('zoomed')
            elif sys.platform == 'darwin':
                # macOS: full-screen toggle via the native API
                win.attributes('-fullscreen', False)  # ensure not already full
                win.geometry('1440x900')
            else:
                win.attributes('-zoomed', True)       # Linux / X11
        except Exception:
            win.geometry('1400x900')

        # Fresh canvas inside the pop-out — no get_root so no nested pop-out btn
        canvas = self._make_tree_canvas(win)
        _render_tree(canvas, tnode)

    # =========================================================================
    # AI Assistant tab
    # =========================================================================
    def create_ai_area(self, parent):
        # ── Quick-action buttons ──────────────────────────────────────────────
        qf = ttk.LabelFrame(parent, text="Quick Actions")
        qf.pack(fill=tk.X, padx=4, pady=(4, 2))

        for label, cmd in [
            ("🔍  Explain Code",        self.ai_explain_code),
            ("⚠   Explain Last Error",  self.ai_explain_error),
            ("✏   Suggest Fix",         self.ai_suggest_fix),
        ]:
            ttk.Button(qf, text=label, command=cmd).pack(side=tk.LEFT, padx=4, pady=4)

        # Settings button (right-aligned) and status chip
        ttk.Button(qf, text="⚙  Set API Key", command=self.open_settings).pack(
            side=tk.RIGHT, padx=4, pady=4)
        self.ai_status_lbl = ttk.Label(qf, text="", font=('Consolas', 8))
        self.ai_status_lbl.pack(side=tk.RIGHT, padx=8)
        self._refresh_ai_status()

        # ── Free-text question ────────────────────────────────────────────────
        qif = ttk.LabelFrame(parent, text="Ask a question  (Enter to send)")
        qif.pack(fill=tk.X, padx=4, pady=2)

        row = ttk.Frame(qif); row.pack(fill=tk.X, padx=4, pady=4)
        self.ai_input = ttk.Entry(row, font=('Consolas', 10))
        self.ai_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.ai_input.bind('<Return>', lambda _e: self.ai_ask())
        ttk.Button(row, text="Ask ↵", command=self.ai_ask).pack(side=tk.RIGHT)

        # ── Response display ──────────────────────────────────────────────────
        rf = ttk.LabelFrame(parent, text="🤖  AI Response")
        rf.pack(fill=tk.BOTH, expand=True, padx=4, pady=(2, 4))

        self.ai_response = scrolledtext.ScrolledText(
            rf, wrap=tk.WORD, font=('Consolas', 10),
            background='#1a1a2e', foreground='#e8e8e8',
            state='disabled',
        )
        self.ai_response.pack(fill=tk.BOTH, expand=True)
        self.ai_response.tag_configure('thinking', foreground='#888888',
                                       font=('Consolas', 10, 'italic'))
        self.ai_response.tag_configure('response', foreground='#e8e8e8')
        self.ai_response.tag_configure('error_msg', foreground='#ff6b6b')
        self.ai_response.tag_configure('header',   foreground='#a8d8ea',
                                       font=('Consolas', 10, 'bold'))

        # Prompt user to set key if missing
        self._refresh_ai_status()

    # ── AI helper methods ─────────────────────────────────────────────────────

    def _refresh_ai_status(self):
        """Update the status chip in the AI tab toolbar."""
        try:
            from llm_runner import api_available
            if api_available():
                self.ai_status_lbl.config(
                    text="● API key active", foreground='green')
            else:
                self.ai_status_lbl.config(
                    text="● No API key — click ⚙ Set API Key", foreground='orange')
        except Exception:
            self.ai_status_lbl.config(text="● llm_runner not found", foreground='red')

    # ── Settings dialog ───────────────────────────────────────────────────────

    def open_settings(self):
        """
        Open the Settings dialog where the user can enter / update their
        Anthropic API key.  The key is saved to ~/.minilang_config.json so it
        persists across sessions and machines — no environment variable setup
        required after the first time.
        """
        dlg = tk.Toplevel(self.root)
        dlg.title("Settings — MiniLang Compiler")
        dlg.geometry("560x300")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        # ── Header ──────────────────────────────────────────────────────────
        hdr = ttk.Frame(dlg, padding=12)
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text="⚙  MiniLang Settings",
                  font=('Helvetica', 13, 'bold')).pack(anchor=tk.W)
        ttk.Separator(dlg, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12)

        # ── API key section ──────────────────────────────────────────────────
        body = ttk.Frame(dlg, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="Anthropic API Key",
                  font=('Helvetica', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))

        # Current stored key (masked)
        current_key = config_manager.get_api_key()
        ttk.Label(body, text="Current key:",
                  foreground='gray').grid(row=1, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Label(body, text=config_manager.mask_key(current_key),
                  font=('Consolas', 9), foreground='#444444').grid(
            row=1, column=1, sticky=tk.W)

        ttk.Label(body, text="New key:").grid(
            row=2, column=0, sticky=tk.W, padx=(0, 8), pady=(10, 0))

        key_var = tk.StringVar()
        key_entry = ttk.Entry(body, textvariable=key_var, width=46,
                              show='*', font=('Consolas', 10))
        key_entry.grid(row=2, column=1, sticky=tk.EW, pady=(10, 0))
        body.columnconfigure(1, weight=1)

        # Toggle show/hide
        show_var = tk.BooleanVar(value=False)
        def _toggle_show():
            key_entry.config(show='' if show_var.get() else '*')
        ttk.Checkbutton(body, text="Show key", variable=show_var,
                        command=_toggle_show).grid(
            row=3, column=1, sticky=tk.W, pady=(4, 0))

        # Hint
        ttk.Label(
            body,
            text="Get a FREE key at: https://aistudio.google.com/app/apikey",
            foreground='#0066cc', font=('Helvetica', 9),
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(12, 0))

        # ── Buttons ──────────────────────────────────────────────────────────
        ttk.Separator(dlg, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=12, pady=(8, 0))
        btn_row = ttk.Frame(dlg, padding=(12, 8))
        btn_row.pack(fill=tk.X)

        def _save():
            new_key = key_var.get().strip()
            if not new_key:
                messagebox.showwarning(
                    "No key entered",
                    "Please paste your API key in the 'New key' field.",
                    parent=dlg)
                return
            # Google API keys typically start with "AIza"
            if not new_key.startswith("AIza"):
                if not messagebox.askyesno(
                    "Unusual key format",
                    "Google API keys usually start with 'AIza'.\n"
                    "Are you sure this key is correct?",
                    parent=dlg,
                ):
                    return
            config_manager.set_api_key(new_key)
            self._refresh_ai_status()
            messagebox.showinfo(
                "Saved",
                "Google API key saved!  The AI Assistant is now active.\n\n"
                "Your key is stored in  ~/.minilang_config.json\n"
                "and will be loaded automatically every time you open the app.\n\n"
                "Free tier: 1,500 requests/day — no credit card needed.",
                parent=dlg)
            dlg.destroy()

        def _clear():
            if messagebox.askyesno(
                "Clear key",
                "Remove the saved API key?  AI features will be disabled "
                "until you set a new key.",
                parent=dlg,
            ):
                config_manager.set_api_key("")
                self._refresh_ai_status()
                dlg.destroy()

        ttk.Button(btn_row, text="💾  Save Key",  command=_save).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_row, text="🗑  Clear Key", command=_clear).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Cancel",        command=dlg.destroy).pack(side=tk.RIGHT)

        key_entry.focus_set()
        dlg.bind('<Return>', lambda _e: _save())
        dlg.bind('<Escape>', lambda _e: dlg.destroy())

    # ─────────────────────────────────────────────────────────────────────────

    def _ai_display(self, text: str, tag: str = 'response'):
        """Replace the AI response pane content."""
        self.ai_response.config(state='normal')
        self.ai_response.delete('1.0', tk.END)
        self.ai_response.insert(tk.END, text, tag)
        self.ai_response.config(state='disabled')

    def _ai_run_async(self, prompt: str, code: str = "", error: str = ""):
        """Start an LLM call in a background thread; show result when done."""
        self._ai_display("  ⏳  Thinking…", 'thinking')
        self.notebook.select(6)   # switch to AI tab

        def _worker():
            try:
                from llm_runner import get_ai_response
                result = get_ai_response(prompt, code=code, error=error)
            except Exception as exc:
                result = f"❌  Error calling LLM: {exc}"
            self.root.after(0, lambda: self._ai_display(result))

        t = Thread(target=_worker); t.daemon = True; t.start()

    def ai_explain_code(self):
        code = self.editor.get('1.0', tk.END).strip()
        if not code:
            self._ai_display("  No code in editor. Write some MiniLang and try again.", 'error_msg')
            self.notebook.select(6); return
        self._ai_run_async(
            "Explain what this MiniLang program does, step by step. "
            "Aim for a first-year student audience.",
            code=code,
        )

    def ai_explain_error(self):
        code  = self.editor.get('1.0', tk.END).strip()
        errs  = error_handler.errors + error_handler.warnings
        if not errs:
            self._ai_display("  No errors found. Run the program first (F5).", 'error_msg')
            self.notebook.select(6); return
        err_text = "\n".join(
            f"{e['type']} at line {e['line']}: {e['message']}" for e in errs
        )
        self._ai_run_async(
            "Explain each of these MiniLang errors in plain language "
            "and tell me exactly how to fix them.",
            code=code, error=err_text,
        )

    def ai_suggest_fix(self):
        code = self.editor.get('1.0', tk.END).strip()
        errs = error_handler.errors
        if not errs:
            self._ai_display("  No errors detected. Run the program first (F5).", 'error_msg')
            self.notebook.select(6); return
        err_text = "\n".join(
            f"{e['type']} at line {e['line']}: {e['message']}" for e in errs
        )
        self._ai_run_async(
            "Fix all the errors in this MiniLang code. "
            "Show the complete corrected program and briefly explain every change.",
            code=code, error=err_text,
        )

    def ai_ask(self):
        question = self.ai_input.get().strip()
        if not question:
            return
        code = self.editor.get('1.0', tk.END).strip()
        self.ai_input.delete(0, tk.END)
        self._ai_run_async(question, code=code)

    # =========================================================================
    # Symbol Table
    # =========================================================================
    def create_symbol_area(self, parent):
        self.symbol_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, font=('Consolas', 10))
        self.symbol_text.pack(fill=tk.BOTH, expand=True)

    # =========================================================================
    # Status bar
    # =========================================================================
    def setup_status_bar(self):
        sb = ttk.Frame(self.root); sb.pack(side=tk.BOTTOM, fill=tk.X)
        self.cursor_pos  = ttk.Label(sb, text="Ln 1, Col 1"); self.cursor_pos.pack(side=tk.LEFT, padx=5)
        self.file_status = ttk.Label(sb, text="No file");     self.file_status.pack(side=tk.LEFT, padx=20)
        ttk.Label(sb, text="MiniLang").pack(side=tk.RIGHT, padx=5)

    def setup_bindings(self):
        self.editor.bind('<<Modified>>', self.on_modified)
        self.editor.bind('<KeyRelease>', self.update_cursor_position)
        self.editor.bind('<Button-1>',   self.update_cursor_position)

    def on_modified(self, event):
        if self.editor.edit_modified():
            self.file_modified = True
            self.update_title()
            self.editor.edit_modified(False)

    def update_cursor_position(self, event=None):
        try:
            l, c = self.editor.index(tk.INSERT).split('.')
            self.cursor_pos.config(text=f"Ln {l}, Col {int(c)+1}")
        except: pass

    # =========================================================================
    # Line numbers
    # =========================================================================
    def update_line_numbers(self):
        try:
            self.line_numbers.config(state='normal')
            self.line_numbers.delete('1.0', tk.END)
            lines = self.editor.get('1.0', tk.END).split('\n')
            self.line_numbers.insert('1.0', '\n'.join(str(i) for i in range(1, len(lines))))
            self.line_numbers.config(state='disabled')
            self.sync_scroll()
        except: pass

    def sync_scroll(self, *a):
        try: self.line_numbers.yview_moveto(self.editor.yview()[0])
        except: pass

    def on_editor_change(self, e=None): self.update_line_numbers(); self.highlight_syntax()
    def on_editor_scroll(self, e=None): self.sync_scroll()
    def on_editor_resize(self, e=None): self.update_line_numbers()
    def on_editor_click(self,  e=None): self.update_cursor_position()

    def update_line_numbers_periodically(self):
        self.update_line_numbers()
        self.root.after(500, self.update_line_numbers_periodically)

    # =========================================================================
    # Syntax highlighting
    # =========================================================================
    def highlight_syntax(self):
        for tag in ["keyword","string","comment","number","operator","boolean"]:
            self.editor.tag_remove(tag, "1.0", tk.END)

        for kw in ['let','display','if','else','while','for','to','step',
                   'try','catch','begin','end','break','not','and','or']:
            s = "1.0"
            while True:
                p = self.editor.search(r'\m'+kw+r'\M', s, tk.END, regexp=True)
                if not p: break
                e = f"{p}+{len(kw)}c"
                self.editor.tag_add("keyword", p, e); s = e

        for bl in ['true','false']:
            s = "1.0"
            while True:
                p = self.editor.search(r'\m'+bl+r'\M', s, tk.END, regexp=True)
                if not p: break
                e = f"{p}+{len(bl)}c"
                self.editor.tag_add("boolean", p, e); s = e

        s = "1.0"
        while True:
            p = self.editor.search(r'--', s, tk.END)
            if not p: break
            self.editor.tag_add("comment", p, f"{p} lineend"); s = f"{p} lineend"

        s = "1.0"; in_str = False
        while True:
            p = self.editor.search(r'"', s, tk.END)
            if not p: break
            if not in_str: ss = p; in_str = True; s = f"{p}+1c"
            else:
                self.editor.tag_add("string", ss, f"{p}+1c")
                in_str = False; s = f"{p}+1c"

        s = "1.0"
        while True:
            p = self.editor.search(r'\m\d+\.?\d*\M', s, tk.END, regexp=True)
            if not p: break
            e = f"{p} wordend"
            self.editor.tag_add("number", p, e); s = e

        for op in ['+','-','*','/','%','=','==','!=','<','>','<=','>=']:
            s = "1.0"
            while True:
                p = self.editor.search(re.escape(op), s, tk.END)
                if not p: break
                e = f"{p}+{len(op)}c"
                self.editor.tag_add("operator", p, e); s = e

    # =========================================================================
    # Title / welcome
    # =========================================================================
    def update_title(self):
        t = "MiniLang Compiler"
        if self.current_file:
            t += f" - {os.path.basename(self.current_file)}"
            if self.file_modified: t += " *"
        self.root.title(t)

    def show_welcome(self):
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", """-- MiniLang Programming Language
-- Welcome to the MiniLang Compiler!

-- Example program:
let name = "World"
display "Hello, " name

let x = 10
let y = 20
let z = x + y
display "x + y = " z

-- Try running this program (F5)
""")
        self.file_modified = False
        self.update_title(); self.update_line_numbers(); self.highlight_syntax()

    # =========================================================================
    # File operations
    # =========================================================================
    def new_file(self):
        if self.file_modified:
            if not messagebox.askyesno("Unsaved Changes", "Discard changes?"): return
        self.editor.delete("1.0", tk.END)
        self.current_file = None; self.file_modified = False
        self.update_title(); self.file_status.config(text="No file")
        self.show_welcome(); self.reset_compiler()

    def open_file(self):
        if self.file_modified:
            if not messagebox.askyesno("Unsaved Changes", "Discard changes?"): return
        fn = filedialog.askopenfilename(
            title="Open MiniLang File",
            filetypes=[("MiniLang files","*.mini"),("All files","*.*")])
        if fn:
            try:
                with open(fn, 'r', encoding='utf-8') as f: content = f.read()
                self.editor.delete("1.0", tk.END); self.editor.insert("1.0", content)
                self.current_file = fn; self.file_modified = False
                self.update_title(); self.file_status.config(text=os.path.basename(fn))
                self.reset_compiler(); self.update_line_numbers(); self.highlight_syntax()
            except Exception as e: messagebox.showerror("Error", str(e))

    def save_file(self):
        if self.current_file:
            try:
                with open(self.current_file, 'w', encoding='utf-8') as f:
                    f.write(self.editor.get("1.0", tk.END))
                self.file_modified = False; self.update_title(); return True
            except Exception as e: messagebox.showerror("Error", str(e)); return False
        return self.save_file_as()

    def save_file_as(self):
        fn = filedialog.asksaveasfilename(
            title="Save MiniLang File", defaultextension=".mini",
            filetypes=[("MiniLang files","*.mini"),("All files","*.*")])
        if fn:
            self.current_file = fn
            self.file_status.config(text=os.path.basename(fn))
            return self.save_file()
        return False

    def undo(self):
        try: self.editor.edit_undo()
        except: pass

    def redo(self):
        try: self.editor.edit_redo()
        except: pass

    def cut(self):   self.editor.event_generate("<<Cut>>")
    def copy(self):  self.editor.event_generate("<<Copy>>")
    def paste(self): self.editor.event_generate("<<Paste>>")

    def find(self):
        dlg = tk.Toplevel(self.root); dlg.title("Find"); dlg.geometry("300x100")
        ttk.Label(dlg, text="Find:").pack(pady=5)
        e = ttk.Entry(dlg, width=30); e.pack(pady=5)
        def go():
            txt = e.get()
            if not txt: return
            self.editor.tag_remove("sel","1.0",tk.END); s="1.0"
            while True:
                p = self.editor.search(txt, s, tk.END)
                if not p: break
                end = f"{p}+{len(txt)}c"; self.editor.tag_add("sel", p, end); s = end
        ttk.Button(dlg, text="Find", command=go).pack()

    # =========================================================================
    # Run pipeline
    # =========================================================================
    def run_program(self):
        if self.file_modified:
            if not self.save_file(): return
        self.clear_output()
        self.reset_compiler()
        self.run_status.config(text="● Running", foreground="orange")
        self.root.update()
        self.running = True
        t = Thread(target=self._run_thread); t.daemon = True; t.start()

    def _run_thread(self):
        try:
            src = self.editor.get("1.0", tk.END)

            self.queue_output("Phase 1: Lexical Analysis...\n", "info")
            tokens = self.lexer.tokenize(src)
            if error_handler.has_errors:
                self.show_errors(); self.queue_output("❌ Lexical analysis failed!\n", "error")
                self.run_status.config(text="● Error", foreground="red"); return
            self.queue_output(f"✅ {len(tokens)} tokens\n", "success")
            self.show_tokens_in_tab(tokens)

            self.queue_output("Phase 2: Syntax Analysis...\n", "info")
            ast = self.parser.parse(src)
            if error_handler.has_errors or not ast:
                self.show_errors(); self.queue_output("❌ Syntax analysis failed!\n", "error")
                self.run_status.config(text="● Error", foreground="red"); return
            self.queue_output("✅ Parse successful\n", "success")
            self.current_ast = ast
            self.generate_parse_tree(ast)
            self.show_ast_in_tab(ast)

            self.queue_output("Phase 3: Semantic Analysis...\n", "info")
            if not self.semantic.analyze(ast):
                self.show_errors(); self.queue_output("❌ Semantic analysis failed!\n", "error")
                self.run_status.config(text="● Error", foreground="red"); return
            self.queue_output("✅ Semantic analysis OK\n", "success")
            self.show_symbol_table_in_tab(self.semantic.symbol_table,
                                          "SEMANTIC SYMBOL TABLE (Before Execution)")

            self.queue_output("Phase 4: Execution...\n", "info")
            self.queue_output("-" * 40 + "\n", "info")

            import io
            old = sys.stdout; sys.stdout = io.StringIO()
            try:
                if not self.interpreter.interpret(ast):
                    self.show_errors(); self.queue_output("❌ Execution failed!\n", "error")
                    self.run_status.config(text="● Error", foreground="red"); return
                self.queue_output(sys.stdout.getvalue(), "output")
                self.show_symbol_table_in_tab(self.interpreter.symbol_table,
                                              "RUNTIME SYMBOL TABLE (After Execution)")
            finally:
                sys.stdout = old

            self.queue_output("-" * 40 + "\n", "info")
            self.queue_output("✅ Execution completed\n", "success")
            self.run_status.config(text="● Completed", foreground="green")

        except Exception as e:
            self.queue_output(f"❌ {e}\n", "error")
            self.run_status.config(text="● Error", foreground="red")
            import traceback; traceback.print_exc()

    # =========================================================================
    # Parse Tree — text view  (Comments + stray strings filtered)
    # =========================================================================
    def generate_parse_tree(self, ast):
        self.parse_tree_text.delete("1.0", tk.END)
        hdr = "=" * 60 + "\nPARSE TREE  (comments excluded)\n" + "=" * 60 + "\n\n"
        self.parse_tree_text.insert(tk.END, hdr, "line")

        if ast:
            self.parse_tree_text.insert(tk.END, "Program\n", "node")
            self.parse_tree_text.insert(tk.END, "│\n", "line")
            self.parse_tree_text.insert(tk.END, "└─ Statement List\n", "node")
            self.parse_tree_text.insert(tk.END, "   │\n", "line")

            # ← filter stray strings AND Comment nodes
            visible = [s for s in ast.statements
                       if isinstance(s, ASTNode) and not isinstance(s, Comment)]
            for i, stmt in enumerate(visible):
                last   = (i == len(visible) - 1)
                prefix = "   └─" if last else "   ├─"
                cont   = "   " + ("   " if last else "│  ")
                self._add_pt_node(stmt, prefix, cont)

        # Draw canvas visual tree (store root for pop-out)
        self.pt_tnode = _pt_to_tnode(ast)
        _render_tree(self.pt_canvas, self.pt_tnode)

    def _add_pt_node(self, node, prefix, indent, is_last=True):
        if node is None or not isinstance(node, ASTNode) or isinstance(node, Comment):
            return
        nt = type(node).__name__

        def ins(text, tag=""):  self.parse_tree_text.insert(tk.END, text, tag)

        if nt == "Declaration":
            ins(f"{prefix} Declaration Statement\n", "node")
            ni = indent + ("   " if is_last else "│  ")
            ins(f"{ni}├─ Keyword: let\n", "leaf")
            ins(f"{ni}├─ Identifier: ", "leaf"); ins(f"{node.identifier}\n", "value")
            ins(f"{ni}├─ Operator: =\n", "leaf")
            ins(f"{ni}└─ Expression\n", "node")
            self._add_expr_tree(node.expression, ni + "   ", True)

        elif nt == "Assignment":
            ins(f"{prefix} Assignment Statement\n", "node")
            ni = indent + ("   " if is_last else "│  ")
            ins(f"{ni}├─ Identifier: ", "leaf"); ins(f"{node.identifier}\n", "value")
            ins(f"{ni}├─ Operator: =\n", "leaf")
            ins(f"{ni}└─ Expression\n", "node")
            self._add_expr_tree(node.expression, ni + "   ", True)

        elif nt == "Display":
            ins(f"{prefix} Display Statement\n", "node")
            ni = indent + ("   " if is_last else "│  ")
            ins(f"{ni}├─ Keyword: display\n", "leaf")
            ins(f"{ni}└─ Display List\n", "node")
            for i, item in enumerate(node.items):
                il = (i == len(node.items) - 1)
                ins(f"{ni}   {'└─' if il else '├─'} Display Item: ", "node")
                if hasattr(item,'value') and isinstance(item.value, str):
                    ins(f'"{item.value}"\n', "value")
                elif hasattr(item,'name'):
                    ins("Identifier: ","leaf"); ins(f"{item.name}\n","value")
                else:
                    ins("Expression\n"); self._add_expr_tree(item, ni+"      ", il)

        elif nt == "If":
            ins(f"{prefix} If Statement\n", "node")
            ni = indent + ("   " if is_last else "│  ")
            ins(f"{ni}├─ Keyword: if\n","leaf")
            ins(f"{ni}├─ Condition\n","node"); self._add_expr_tree(node.condition, ni+"│  ", False)
            ins(f"{ni}├─ Then Block\n","node"); self._add_stmt_block(node.then_statements, ni+"│  ", False)
            if node.else_statements:
                ins(f"{ni}├─ Keyword: else\n","leaf")
                ins(f"{ni}└─ Else Block\n","node"); self._add_stmt_block(node.else_statements, ni+"   ", True)
            else:
                ins(f"{ni}└─ Keyword: end\n","leaf")

        elif nt == "While":
            ins(f"{prefix} While Loop\n","node")
            ni = indent + ("   " if is_last else "│  ")
            ins(f"{ni}├─ Keyword: while\n","leaf")
            ins(f"{ni}├─ Condition\n","node"); self._add_expr_tree(node.condition, ni+"│  ", False)
            ins(f"{ni}└─ Loop Block\n","node"); self._add_stmt_block(node.statements, ni+"   ", True)

        elif nt == "For":
            ins(f"{prefix} For Loop\n","node")
            ni = indent + ("   " if is_last else "│  ")
            ins(f"{ni}├─ Keyword: for\n","leaf")
            ins(f"{ni}├─ Identifier: ","leaf"); ins(f"{node.identifier}\n","value")
            ins(f"{ni}├─ Start\n","node"); self._add_expr_tree(node.start_expr, ni+"│  ", False)
            ins(f"{ni}├─ Keyword: to\n","leaf")
            ins(f"{ni}├─ End\n","node");   self._add_expr_tree(node.end_expr, ni+"│  ", False)
            if node.step_expr:
                ins(f"{ni}├─ Keyword: step\n","leaf")
                ins(f"{ni}├─ Step\n","node"); self._add_expr_tree(node.step_expr, ni+"│  ", False)
            ins(f"{ni}└─ Loop Block\n","node"); self._add_stmt_block(node.statements, ni+"   ", True)

        elif nt == "TryCatch":
            ins(f"{prefix} Try-Catch Statement\n","node")
            ni = indent + ("   " if is_last else "│  ")
            ins(f"{ni}├─ Keyword: try\n","leaf")
            ins(f"{ni}├─ Try Block\n","node");   self._add_stmt_block(node.try_statements,   ni+"│  ", False)
            ins(f"{ni}├─ Keyword: catch\n","leaf")
            ins(f"{ni}└─ Catch Block\n","node"); self._add_stmt_block(node.catch_statements, ni+"   ", True)

        elif nt == "Block":
            ins(f"{prefix} Block\n","node")
            ni = indent + ("   " if is_last else "│  ")
            self._add_stmt_block(node.statements, ni, True)

        elif nt == "Break":
            ins(f"{prefix} Break Statement\n","node")
            ins(f"{indent}   └─ Keyword: break\n","leaf")

        else:
            ins(f"{prefix} {nt}\n")

    def _add_expr_tree(self, expr, indent, is_last):
        if expr is None: return
        def ins(text, tag=""): self.parse_tree_text.insert(tk.END, text, tag)
        et = type(expr).__name__
        if et == "BinaryOp":
            ins(f"{indent}├─ Binary Operation\n","node")
            ins(f"{indent}│  ├─ Left\n","node");      self._add_expr_tree(expr.left,  indent+"│  │  ", False)
            ins(f"{indent}│  ├─ Operator: ","leaf");  ins(f"{expr.op}\n","value")
            ins(f"{indent}│  └─ Right\n","node");     self._add_expr_tree(expr.right, indent+"│     ", True)
        elif et == "UnaryOp":
            ins(f"{indent}├─ Unary Operation\n","node")
            ins(f"{indent}│  ├─ Operator: ","leaf");  ins(f"{expr.op}\n","value")
            ins(f"{indent}│  └─ Operand\n","node");   self._add_expr_tree(expr.expr,  indent+"│     ", True)
        elif et == "Identifier":
            ins(f"{indent}└─ Identifier: ","leaf"); ins(f"{expr.name}\n","value")
        elif et == "IntegerLiteral":
            ins(f"{indent}└─ Integer: ","leaf");  ins(f"{expr.value}\n","value")
        elif et == "FloatLiteral":
            ins(f"{indent}└─ Float: ","leaf");    ins(f"{expr.value}\n","value")
        elif et == "StringLiteral":
            ins(f"{indent}└─ String: ","leaf");   ins(f'"{expr.value}"\n',"value")
        elif et == "BooleanLiteral":
            ins(f"{indent}└─ Boolean: ","leaf");  ins(f"{expr.value}\n","value")
        else:
            ins(f"{indent}└─ {et}\n")

    def _add_stmt_block(self, statements, indent, is_last):
        if not statements: return
        # ← filter stray strings AND Comment nodes
        visible = [s for s in statements
                   if isinstance(s, ASTNode) and not isinstance(s, Comment)]
        for i, stmt in enumerate(visible):
            sl = (i == len(visible) - 1)
            self._add_pt_node(stmt, f"{indent}{'└─' if sl else '├─'}", indent, sl)

    # =========================================================================
    # AST text view
    # =========================================================================
    def show_ast_in_tab(self, ast, node=None, indent=0, prefix="├─"):
        if node is None:
            self.ast_text.delete("1.0", tk.END)
            hdr = "=" * 60 + "\nABSTRACT SYNTAX TREE  (comments excluded)\n" + "=" * 60 + "\n\n"
            self.ast_text.insert(tk.END, hdr)
            if ast:
                self.show_ast_in_tab(ast, ast, 0, "└─")
            # Draw canvas (store root for pop-out)
            self.ast_tnode = _ast_to_tnode(ast)
            _render_tree(self.ast_canvas, self.ast_tnode)
            return

        if not isinstance(node, ASTNode) or isinstance(node, Comment):
            return

        pad = "   " * indent
        nt  = type(node).__name__
        details = []
        if hasattr(node,'identifier') and not callable(getattr(node,'identifier',None)):
            details.append(f"id={node.identifier}")
        if hasattr(node,'value') and not callable(getattr(node,'value',None)):
            details.append(f"val={node.value}")
        if hasattr(node,'op') and not callable(getattr(node,'op',None)):
            details.append(f"op={node.op}")
        if hasattr(node,'name') and not callable(getattr(node,'name',None)):
            details.append(f"name={node.name}")

        dstr = f" [{', '.join(details)}]" if details else ""
        self.ast_text.insert(tk.END, f"{pad}{prefix} {nt}{dstr}\n")

        # Collect real ASTNode children only (fixes the "str" bug)
        children = [c for c in _ast_children(node)
                    if isinstance(c, ASTNode) and not isinstance(c, Comment)]
        for i, child in enumerate(children):
            cp = "└─" if i == len(children)-1 else "├─"
            self.show_ast_in_tab(ast, child, indent+1, cp)

    # =========================================================================
    # Symbol table
    # =========================================================================
    def show_symbol_table(self):
        self.show_symbol_table_in_tab(); self.notebook.select(5)

    def show_symbol_table_in_tab(self, st=None, title="SYMBOL TABLE"):
        if st is None: st = self.semantic.symbol_table
        self.symbol_text.delete("1.0", tk.END)
        self.symbol_text.insert(tk.END, "=" * 60 + "\n" + title + "\n" + "=" * 60 + "\n\n")
        out = []
        for i, scope in enumerate(st.scopes):
            out.append(f"Scope {i}:")
            for name, sym in scope.items():
                out.append(f"  {name} = {sym.value}  (declared: {sym.declared})")
            out.append("")
        self.symbol_text.insert(tk.END, "\n".join(out))

    # =========================================================================
    # Queue / output helpers
    # =========================================================================
    def queue_output(self, text, tag="output"):
        self.output_queue.put((text, tag))

    def process_output_queue(self):
        try:
            while True:
                text, tag = self.output_queue.get_nowait()
                self.output_text.insert(tk.END, text, tag)
                self.output_text.see(tk.END)
        except: pass
        finally: self.root.after(100, self.process_output_queue)

    def clear_output(self):
        self.output_text.delete("1.0", tk.END)

        self.error_text.config(state='normal')
        self.error_text.delete("1.0", tk.END)
        self.error_detail.config(state='normal')
        self.error_detail.delete("1.0", tk.END)
        self.error_detail.config(state='disabled')

        for item in self.tokens_tree.get_children():
            self.tokens_tree.delete(item)
        self.tokens_summary.config(text="")

        self.parse_tree_text.delete("1.0", tk.END)
        self.pt_canvas.delete('all')

        self.ast_text.delete("1.0", tk.END)
        self.ast_canvas.delete('all')

        self.symbol_text.delete("1.0", tk.END)

    def stop_program(self):
        self.running = False
        self.run_status.config(text="● Stopped", foreground="gray")
        self.queue_output("\n⚠ Program stopped by user\n", "error")

    # =========================================================================
    # Toolbar quick-actions
    # =========================================================================
    def show_tokens(self):
        src = self.editor.get("1.0", tk.END)
        self.show_tokens_in_tab(self.lexer.tokenize(src))
        self.notebook.select(2)

    def show_parse_tree(self):
        if not self.current_ast:
            self.current_ast = self.parser.parse(self.editor.get("1.0", tk.END))
        if self.current_ast:
            self.generate_parse_tree(self.current_ast)
        self.notebook.select(3)

    def show_ast(self):
        ast = self.parser.parse(self.editor.get("1.0", tk.END))
        if ast:
            self.current_ast = ast
            self.show_ast_in_tab(ast)
        self.notebook.select(4)

    # =========================================================================
    # Examples
    # =========================================================================
    def load_example(self, name):
        ex = {
            "hello": '-- Hello World\nlet name = "World"\ndisplay "Hello, " name\n\nlet x = 10\nlet y = 20\nlet z = x + y\ndisplay "x + y = " z\n',
            "if": '-- If statement\nlet score = 85\n\nif score >= 90\n    display "Grade: A"\nend\n\nif score >= 80 and score < 90\n    display "Grade: B"\nend\n',
            "if_chain": '-- If-else chain\nlet score = 85\n\nif score >= 90\n    display "Grade: A"\nelse\n    if score >= 80\n        display "Grade: B"\n    else\n        display "Grade: C or below"\n    end\nend\n',
            "while": '-- While loop\nlet counter = 1\nlet sum = 0\n\nwhile counter <= 10\n    sum = sum + counter\n    display "Sum = " sum\n    counter = counter + 1\nend\n\ndisplay "Final sum: " sum\n',
            "for": '-- For loop\ndisplay "Counting:"\nfor i = 1 to 5\n    display i\nend\n\ndisplay "Even numbers:"\nfor i = 0 to 10 step 2\n    display i\nend\n',
            "try_catch": '-- Exception handling\ntry\n    let x = 10\n    let y = 0\n    let result = x / y\ncatch\n    display "Error: Division by zero caught!"\nend\n\ndisplay "Program continues..."\n',
            "comprehensive": '-- Comprehensive test\nlet x = 10\nlet y = 20\nlet z = 30\n\nlet result1 = x + y * z\nlet result2 = (x + y) * z\ndisplay "x + y * z = " result1\ndisplay "(x + y) * z = " result2\n\nif x < y and y < z\n    display "All ordered"\nend\n\nlet counter = 1\nwhile counter <= 5\n    display "Count: " counter\n    counter = counter + 1\nend\n\ntry\n    let a = 10\n    let b = 0\n    let c = a / b\ncatch\n    display "Caught division by zero"\nend\n\ndisplay "Done!"\n',
        }
        if name not in ex: return
        if self.file_modified:
            if not messagebox.askyesno("Unsaved Changes", "Discard changes?"): return
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", ex[name])
        self.current_file = None; self.file_modified = False
        self.file_status.config(text=f"Example: {name}")
        self.update_title(); self.reset_compiler()
        self.update_line_numbers(); self.highlight_syntax()

    # =========================================================================
    # Help
    # =========================================================================
    def show_quick_ref(self):
        self.show_info("Quick Reference", """
MINILANG QUICK REFERENCE
========================

VARIABLES:
    let name = value       Declare + initialise
    name = new_value       Reassign

OUTPUT:
    display item1 item2 ...

CONDITIONALS:
    if condition
        statements
    else
        statements
    end

LOOPS:
    while condition
        statements
    end

    for var = start to end step value
        statements
    end

EXCEPTION HANDLING:
    try
        statements
    catch
        statements
    end

BLOCKS:
    begin
        statements
    end

COMMENTS:
    -- This is a comment

OPERATORS:
    Arithmetic : + - * / %
    Relational : == != < > <= >=
    Logical    : and  or  not
""")

    def show_about(self):
        self.show_info("About MiniLang", """
MiniLang Compiler v1.0
======================

CIT4004 - Analysis of Programming Languages
University of Technology, Jamaica

Features:
  Arithmetic with PEMDAS precedence
  Variables and scoped symbol table
  Control structures (if / while / for)
  Exception handling (try / catch)
  Logical operators
  Canvas-drawn parse tree + AST
  Error definitions and fix hints
  Token breakdown by category

Created: March 2026
""")

    def show_info(self, title, message):
        dlg = tk.Toplevel(self.root); dlg.title(title); dlg.geometry("520x420")
        t = scrolledtext.ScrolledText(dlg, wrap=tk.WORD, font=('Courier', 10))
        t.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        t.insert("1.0", message); t.config(state='disabled')
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=8)

    def exit_app(self):
        if self.file_modified:
            if not messagebox.askyesno("Unsaved Changes", "Exit anyway?"): return
        self.root.quit()


# ============================================================================
def main():
    root = tk.Tk()
    ttk.Style().theme_use('clam')
    app = MiniLangGUI(root)
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    root.geometry(f"{w}x{h}+{(root.winfo_screenwidth()-w)//2}+{(root.winfo_screenheight()-h)//2}")
    root.mainloop()


if __name__ == "__main__":
    main()
