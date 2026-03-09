"""
cloud_app.py — NovaScript Compiler  (Streamlit Cloud Edition)
CIT4004 · University of Technology, Jamaica

Deployable for FREE at https://streamlit.io/cloud
Run locally:  streamlit run cloud_app.py

This web interface exposes the full NovaScript compiler pipeline
(lexer → parser → semantic analyser → interpreter) plus the
Gemini-powered AI Assistant, all inside a browser — no installation
required by end-users.
"""

import sys
import os
import io
from contextlib import redirect_stdout

import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
# Allow imports from ./src/ regardless of where Streamlit is launched from
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# ── Import compiler pipeline ──────────────────────────────────────────────────
from lexer        import NovaScriptLexer
from parser       import NovaScriptParser
from semantic     import SemanticAnalyzer
from interpreter  import Interpreter
from error_handler import error_handler

# ── Inject API key from Streamlit Secrets (cloud) or environment (local) ──────
def _load_google_key():
    """Pull GOOGLE_API_KEY from st.secrets (Streamlit Cloud) or os.environ."""
    try:
        key = st.secrets.get("GOOGLE_API_KEY", "")
        if key:
            os.environ["GOOGLE_API_KEY"] = key
            return
    except Exception:
        pass
    # Fall back to env var (local dev)
    # Key already in os.environ — nothing to do.

_load_google_key()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NovaScript Compiler",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Editor font */
    .stTextArea textarea { font-family: 'Consolas', monospace; font-size: 14px; }
    /* Output blocks */
    .output-box  { background:#0e1117; color:#e8e8e8; padding:12px;
                   border-radius:6px; font-family:monospace; white-space:pre-wrap; }
    .error-box   { background:#2d0000; color:#ff9999; padding:12px;
                   border-radius:6px; font-family:monospace; white-space:pre-wrap; }
    .success-box { background:#002d00; color:#99ff99; padding:12px;
                   border-radius:6px; font-family:monospace; white-space:pre-wrap; }
    .ai-box      { background:#1a1a2e; color:#e8e8e8; padding:14px;
                   border-radius:6px; font-family:monospace; white-space:pre-wrap; }
    .token-chip  { display:inline-block; background:#1e3a5f; color:#a8d8ea;
                   padding:2px 8px; margin:2px; border-radius:4px;
                   font-family:monospace; font-size:12px; }
</style>
""", unsafe_allow_html=True)

# ── Example programs ──────────────────────────────────────────────────────────
EXAMPLES = {
    "Hello World": '-- Hello World\ndisplay "Hello, World!"',
    "If Statement": (
        "let score = 75\n\n"
        "if score >= 90\n"
        '    display "Grade: A"\n'
        "else\n"
        '    display "Grade: B or below"\n'
        "end"
    ),
    "While Loop": (
        "let i = 1\n"
        "while i <= 5\n"
        '    display "Count:" i\n'
        "    i = i + 1\n"
        "end"
    ),
    "For Loop": (
        "for n = 1 to 10 step 1\n"
        '    display "n =" n\n'
        "end"
    ),
    "Exception Handling": (
        "let x = 10\n"
        "let y = 0\n"
        "try\n"
        "    let result = x / y\n"
        '    display "Result:" result\n'
        "catch\n"
        '    display "Caught: division by zero!"\n'
        "end"
    ),
    "Comprehensive": (
        "-- Comprehensive NovaScript demo\n"
        "let x = 10\n"
        "let y = 20\n"
        'display "Sum:" x + y\n\n'
        "-- Conditional\n"
        "if x < y\n"
        '    display "x is smaller"\n'
        "end\n\n"
        "-- Loop with break\n"
        "let count = 1\n"
        "while count <= 10\n"
        "    if count > 3\n"
        "        break\n"
        "    end\n"
        '    display "count:" count\n'
        "    count = count + 1\n"
        "end\n\n"
        "-- For loop\n"
        "for i = 0 to 6 step 2\n"
        '    display "even:" i\n'
        "end\n\n"
        "-- Try/catch\n"
        "try\n"
        "    let bad = 5 / 0\n"
        "catch\n"
        '    display "Error caught!"\n'
        "end"
    ),
}

# ── Tree visualisation helpers ────────────────────────────────────────────────
import itertools

# Import AST node types (already on sys.path via _SRC)
import ast_nodes as _AN


def _escape_dot(s: str) -> str:
    """Escape a string for use inside a Graphviz double-quoted label."""
    return (str(s)
            .replace("\\", "\\\\")
            .replace('"',  '\\"')
            .replace("\n", "\\n")
            .replace("<",  "\\<")
            .replace(">",  "\\>")
            .replace("{",  "\\{")
            .replace("}",  "\\}"))


def _ast_to_dot(root, mode: str = "ast") -> str:
    """
    Convert an AST root node to a Graphviz DOT string.

    mode='ast'   → clean semantic tree (structural nodes only)
    mode='parse' → grammar-level tree (adds keyword terminal children)
    """
    counter   = itertools.count()
    node_defs : list[str] = []
    edge_defs : list[str] = []

    # Node colour palette
    _COLORS = {
        "internal": ("#e07b00", "white",   "box"),       # orange  — structural
        "expr":     ("#1a6b8a", "white",   "diamond"),   # blue    — operators
        "literal":  ("#2d7d46", "white",   "ellipse"),   # green   — values
        "leaf":     ("#5a5a7a", "white",   "ellipse"),   # grey    — terminals
    }

    def _node(nid: int, label: str, kind: str = "internal"):
        color, font, shape = _COLORS.get(kind, _COLORS["internal"])
        node_defs.append(
            f'  n{nid} [label="{_escape_dot(label)}" shape={shape} '
            f'style=filled fillcolor="{color}" fontcolor="{font}"];'
        )

    def _leaf(parent: int, text: str):
        nid = next(counter)
        _node(nid, text, "leaf")
        edge_defs.append(f"  n{parent} -> n{nid};")

    def _edge(parent: int, child):
        if child is not None:
            edge_defs.append(f"  n{parent} -> n{child};")

    def _body(parent: int, stmts, label: str = "body"):
        bid = next(counter)
        _node(bid, label, "internal")
        edge_defs.append(f"  n{parent} -> n{bid};")
        for s in (stmts or []):
            _edge(bid, _visit(s))
        return bid

    def _visit(node) -> "int | None":
        if node is None:
            return None
        nid = next(counter)

        # ── Structural nodes ────────────────────────────────────────────
        if isinstance(node, _AN.Program):
            _node(nid, "Program")
            for s in (node.statements or []):
                if isinstance(s, _AN.ASTNode):    # skip stray non-AST items
                    _edge(nid, _visit(s))

        elif isinstance(node, _AN.Comment):
            _node(nid, f"-- {str(node.text)[:30]}", "leaf")

        elif isinstance(node, _AN.Block):
            _node(nid, "begin…end")
            if mode == "parse": _leaf(nid, "begin")
            for s in (node.statements or []):
                _edge(nid, _visit(s))
            if mode == "parse": _leaf(nid, "end")

        elif isinstance(node, _AN.Declaration):
            _node(nid, f"let {node.identifier}")
            if mode == "parse":
                _leaf(nid, "let"); _leaf(nid, node.identifier); _leaf(nid, "=")
            _edge(nid, _visit(node.expression))

        elif isinstance(node, _AN.Assignment):
            _node(nid, f"{node.identifier} =")
            if mode == "parse":
                _leaf(nid, node.identifier); _leaf(nid, "=")
            _edge(nid, _visit(node.expression))

        elif isinstance(node, _AN.Display):
            _node(nid, "display")
            if mode == "parse": _leaf(nid, "display")
            for item in (node.items or []):
                _edge(nid, _visit(item))

        elif isinstance(node, _AN.If):
            _node(nid, "if")
            if mode == "parse": _leaf(nid, "if")
            _edge(nid, _visit(node.condition))
            _body(nid, node.then_statements, "then")
            if node.else_statements:
                if mode == "parse": _leaf(nid, "else")
                _body(nid, node.else_statements, "else")
            if mode == "parse": _leaf(nid, "end")

        elif isinstance(node, _AN.While):
            _node(nid, "while")
            if mode == "parse": _leaf(nid, "while")
            _edge(nid, _visit(node.condition))
            _body(nid, node.statements)
            if mode == "parse": _leaf(nid, "end")

        elif isinstance(node, _AN.For):
            _node(nid, f"for {node.identifier}")
            if mode == "parse":
                _leaf(nid, "for"); _leaf(nid, node.identifier); _leaf(nid, "=")
            _edge(nid, _visit(node.start_expr))
            if mode == "parse": _leaf(nid, "to")
            _edge(nid, _visit(node.end_expr))
            if node.step_expr is not None:
                if mode == "parse": _leaf(nid, "step")
                _edge(nid, _visit(node.step_expr))
            _body(nid, node.statements)
            if mode == "parse": _leaf(nid, "end")

        elif isinstance(node, _AN.TryCatch):
            _node(nid, "try/catch")
            if mode == "parse": _leaf(nid, "try")
            _body(nid, node.try_statements,   "try-body")
            if mode == "parse": _leaf(nid, "catch")
            _body(nid, node.catch_statements, "catch-body")
            if mode == "parse": _leaf(nid, "end")

        elif isinstance(node, _AN.Break):
            _node(nid, "break", "leaf")

        elif isinstance(node, _AN.Expression):
            return _visit(node.expression)   # transparent wrapper

        # ── Expression nodes ────────────────────────────────────────────
        elif isinstance(node, _AN.BinaryOp):
            _node(nid, node.op, "expr")
            _edge(nid, _visit(node.left))
            _edge(nid, _visit(node.right))

        elif isinstance(node, _AN.UnaryOp):
            _node(nid, f"unary {node.op}", "expr")
            _edge(nid, _visit(node.expr))

        # ── Leaf / value nodes ──────────────────────────────────────────
        elif isinstance(node, _AN.Identifier):
            _node(nid, f"id: {node.name}", "literal")

        elif isinstance(node, _AN.IntegerLiteral):
            _node(nid, str(node.value), "literal")

        elif isinstance(node, _AN.FloatLiteral):
            _node(nid, str(node.value), "literal")

        elif isinstance(node, _AN.StringLiteral):
            v = node.value[:20] + ("…" if len(node.value) > 20 else "")
            _node(nid, f'"{v}"', "literal")

        elif isinstance(node, _AN.BooleanLiteral):
            _node(nid, str(node.value).lower(), "literal")

        else:
            _node(nid, type(node).__name__)

        return nid

    _visit(root)

    return (
        "digraph G {\n"
        "  rankdir=TB;\n"
        "  node [fontname=\"Courier\" fontsize=10];\n"
        "  edge [arrowsize=0.7];\n"
        + "\n".join(node_defs) + "\n"
        + "\n".join(edge_defs) + "\n"
        "}"
    )


def _ast_to_text(root, mode: str = "ast") -> str:
    """
    Return a Unicode-art indented text representation of the AST.
    mode: 'ast' = clean, 'parse' = shows grammar keyword children.
    """
    PAD = "  "
    lines: list[str] = []

    def _kw(parent_lines, ind, text):
        if mode == "parse":
            parent_lines.append(PAD * ind + f"  ⬡ {text}")

    def _visit(node, ind: int):
        if node is None:
            return
        p = PAD * ind

        if isinstance(node, _AN.Program):
            lines.append(p + "📦 Program")
            for s in (node.statements or []):
                if isinstance(s, _AN.ASTNode):    # skip stray non-AST items
                    _visit(s, ind + 1)

        elif isinstance(node, _AN.Comment):
            lines.append(p + f"💬 Comment: {str(node.text)[:50]}")

        elif isinstance(node, _AN.Block):
            lines.append(p + "🔷 Block (begin…end)")
            _kw(lines, ind, "begin")
            for s in (node.statements or []):
                _visit(s, ind + 1)
            _kw(lines, ind, "end")

        elif isinstance(node, _AN.Declaration):
            lines.append(p + f"📝 Declaration  let {node.identifier}")
            _kw(lines, ind, "let"); _kw(lines, ind, node.identifier)
            _kw(lines, ind, "=")
            _visit(node.expression, ind + 1)

        elif isinstance(node, _AN.Assignment):
            lines.append(p + f"✏️  Assignment  {node.identifier} =")
            _kw(lines, ind, node.identifier); _kw(lines, ind, "=")
            _visit(node.expression, ind + 1)

        elif isinstance(node, _AN.Display):
            lines.append(p + "🖨  Display")
            _kw(lines, ind, "display")
            for item in (node.items or []):
                _visit(item, ind + 1)

        elif isinstance(node, _AN.If):
            lines.append(p + "🔀 If")
            _kw(lines, ind, "if")
            lines.append(PAD * (ind + 1) + "▸ condition")
            _visit(node.condition, ind + 2)
            lines.append(PAD * (ind + 1) + "▸ then")
            for s in (node.then_statements or []):
                _visit(s, ind + 2)
            if node.else_statements:
                _kw(lines, ind, "else")
                lines.append(PAD * (ind + 1) + "▸ else")
                for s in node.else_statements:
                    _visit(s, ind + 2)
            _kw(lines, ind, "end")

        elif isinstance(node, _AN.While):
            lines.append(p + "🔁 While")
            _kw(lines, ind, "while")
            lines.append(PAD * (ind + 1) + "▸ condition")
            _visit(node.condition, ind + 2)
            lines.append(PAD * (ind + 1) + "▸ body")
            for s in (node.statements or []):
                _visit(s, ind + 2)
            _kw(lines, ind, "end")

        elif isinstance(node, _AN.For):
            lines.append(p + f"🔂 For  {node.identifier}")
            _kw(lines, ind, "for"); _kw(lines, ind, node.identifier)
            _kw(lines, ind, "=")
            lines.append(PAD * (ind + 1) + "▸ start"); _visit(node.start_expr, ind + 2)
            _kw(lines, ind, "to")
            lines.append(PAD * (ind + 1) + "▸ end");   _visit(node.end_expr,   ind + 2)
            if node.step_expr is not None:
                _kw(lines, ind, "step")
                lines.append(PAD * (ind + 1) + "▸ step"); _visit(node.step_expr, ind + 2)
            lines.append(PAD * (ind + 1) + "▸ body")
            for s in (node.statements or []):
                _visit(s, ind + 2)
            _kw(lines, ind, "end")

        elif isinstance(node, _AN.TryCatch):
            lines.append(p + "🛡  TryCatch")
            _kw(lines, ind, "try")
            lines.append(PAD * (ind + 1) + "▸ try-body")
            for s in (node.try_statements or []):
                _visit(s, ind + 2)
            _kw(lines, ind, "catch")
            lines.append(PAD * (ind + 1) + "▸ catch-body")
            for s in (node.catch_statements or []):
                _visit(s, ind + 2)
            _kw(lines, ind, "end")

        elif isinstance(node, _AN.Break):
            lines.append(p + "⛔ Break")

        elif isinstance(node, _AN.Expression):
            _visit(node.expression, ind)   # transparent wrapper

        elif isinstance(node, _AN.BinaryOp):
            lines.append(p + f"⚙  BinaryOp  {node.op}")
            _visit(node.left,  ind + 1)
            _visit(node.right, ind + 1)

        elif isinstance(node, _AN.UnaryOp):
            lines.append(p + f"⚙  UnaryOp  {node.op}")
            _visit(node.expr, ind + 1)

        elif isinstance(node, _AN.Identifier):
            lines.append(p + f"🔑 id: {node.name}")

        elif isinstance(node, _AN.IntegerLiteral):
            lines.append(p + f"🔢 int: {node.value}")

        elif isinstance(node, _AN.FloatLiteral):
            lines.append(p + f"🔢 float: {node.value}")

        elif isinstance(node, _AN.StringLiteral):
            v = node.value[:40] + ("…" if len(node.value) > 40 else "")
            lines.append(p + f'🔤 str: "{v}"')

        elif isinstance(node, _AN.BooleanLiteral):
            lines.append(p + f"🔵 bool: {node.value}")

        else:
            lines.append(p + f"? {type(node).__name__}")

    _visit(root, 0)
    return "\n".join(lines)


def _render_tree_tab(ast_root, tab_label: str):
    """
    Render a Parse Tree or AST tab with Visual / Text view toggle.
    tab_label: 'parse' or 'ast'  (controls which DOT/text mode is used)
    """
    if ast_root is None:
        st.info("Tree not available — run the program first (▶ Run).")
        return

    view = st.radio(
        "View",
        ["🌲 Visual (diagram)", "📝 Text (indented)"],
        horizontal=True,
        label_visibility="collapsed",
        key=f"view_mode_{tab_label}",
    )

    mode = "parse" if tab_label == "parse" else "ast"

    if view == "🌲 Visual (diagram)":
        try:
            dot_src = _ast_to_dot(ast_root, mode=mode)
            st.graphviz_chart(dot_src, use_container_width=True)
        except Exception as exc:
            st.error(f"Could not render diagram: {exc}")
            st.code(_ast_to_text(ast_root, mode=mode), language="text")

        # Legend
        st.caption(
            "🟧 Orange = structural node  |  "
            "🔷 Blue = operator  |  "
            "🟩 Green = value/identifier  |  "
            + ("🔘 Grey = grammar terminal" if mode == "parse" else "")
        )
    else:
        txt = _ast_to_text(ast_root, mode=mode)
        st.code(txt, language="text")


# ── Compiler helper ────────────────────────────────────────────────────────────
def _extract_symbol_table(interp) -> dict:
    """
    Convert the interpreter's SymbolTable object into a plain dict.
    SymbolTable stores variables in a list of scope dicts; we flatten
    them all (inner scopes shadow outer ones, matching runtime behaviour).
    """
    sym = {}
    if not hasattr(interp, "symbol_table"):
        return sym
    st = interp.symbol_table
    if hasattr(st, "scopes"):                 # SymbolTable with scope stack
        for scope in st.scopes:
            for name, symbol in scope.items():
                sym[name] = symbol.value if hasattr(symbol, "value") else symbol
    elif isinstance(st, dict):                # plain dict fallback
        sym = {k: v for k, v in st.items()}
    return sym


def run_novascript(source: str) -> dict:
    """
    Run *source* through all four compiler phases.
    Returns a dict with keys: tokens, ast, errors, warnings,
                               output, symbol_table, success.
    """
    # NovaScript grammar requires a NEWLINE token after every statement.
    # Streamlit's text_area may strip the trailing newline, so we restore it.
    if not source.endswith("\n"):
        source += "\n"

    error_handler.reset()

    lexer    = NovaScriptLexer();  lexer.build()
    # write_tables=False / debug=False: don't touch the filesystem on cloud
    parser   = NovaScriptParser(); parser.build(write_tables=False, debug=False)
    semantic = SemanticAnalyzer()
    interp   = Interpreter()

    result = {
        "tokens":       [],
        "ast":          None,
        "errors":       [],
        "warnings":     [],
        "output":       "",
        "symbol_table": {},
        "success":      False,
    }

    # Phase 1 — Lexical analysis
    try:
        result["tokens"] = lexer.tokenize(source)
    except Exception as exc:
        result["errors"].append({"type": "LEXICAL", "line": 0,
                                  "message": str(exc)})
        result["errors"] += error_handler.errors
        return result

    if error_handler.has_errors:
        result["errors"] = error_handler.errors[:]
        return result

    # Phase 2 — Parsing
    try:
        ast = parser.parse(source)
    except Exception as exc:
        result["errors"].append({"type": "SYNTAX", "line": 0,
                                  "message": str(exc)})
        return result

    if error_handler.has_errors or not ast:
        result["errors"] = error_handler.errors[:]
        return result
    result["ast"] = ast

    # Phase 3 — Semantic analysis
    try:
        semantic.analyze(ast)
    except Exception as exc:
        result["errors"].append({"type": "SEMANTIC", "line": 0,
                                  "message": str(exc)})
        result["errors"] += error_handler.errors
        return result

    if error_handler.has_errors:
        result["errors"] = error_handler.errors[:]
        result["warnings"] = error_handler.warnings[:]
        return result

    result["warnings"] = error_handler.warnings[:]

    # Phase 4 — Interpretation
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            interp.interpret(ast)
        # Grab interpreter's internal output_buffer (display statements)
        captured = buf.getvalue()
        internal = interp.get_output() if hasattr(interp, "get_output") else ""
        # Use whichever has content (they may overlap — prefer captured stdout)
        result["output"] = captured if captured.strip() else internal
        result["symbol_table"] = _extract_symbol_table(interp)
    except Exception as exc:
        result["errors"].append({"type": "RUNTIME", "line": 0,
                                  "message": str(exc)})
        result["errors"] += error_handler.errors
        return result

    if error_handler.has_errors:
        result["errors"] = error_handler.errors[:]
    else:
        result["success"] = True

    return result


# ── Editor callbacks (must be defined before any widget that uses them) ────────
def _clear_editor():
    st.session_state.code           = ""
    st.session_state["code_editor"] = ""
    st.session_state.result         = None

def _load_example():
    choice = st.session_state.get("example_sel", "— select —")
    if choice != "— select —" and choice in EXAMPLES:
        st.session_state.code           = EXAMPLES[choice]
        st.session_state["code_editor"] = EXAMPLES[choice]
        st.session_state.result         = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🖥️ NovaScript")
    st.caption("CIT4004 · University of Technology, Jamaica")
    st.markdown("---")

    # Example loader
    st.subheader("📂 Load Example")
    st.selectbox("Choose an example", ["— select —"] + list(EXAMPLES), key="example_sel")
    st.button("Load", use_container_width=True, on_click=_load_example)

    st.markdown("---")

    # API key input (for cloud deployments without secrets)
    st.subheader("🤖 AI Assistant")
    env_key = os.environ.get("GOOGLE_API_KEY", "")
    if env_key:
        st.success("● Google API key active", icon="✅")
    else:
        st.warning("No API key set", icon="⚠️")
        manual_key = st.text_input(
            "Paste your Google API key",
            type="password",
            placeholder="AIza...",
            help="Get a FREE key at https://aistudio.google.com/app/apikey",
        )
        if manual_key:
            os.environ["GOOGLE_API_KEY"] = manual_key.strip()
            st.success("Key applied for this session!", icon="✅")

    st.markdown("---")
    st.caption("**NovaScript Compiler v1.0**")
    st.caption("Lexer → Parser → Semantic → Interpreter")
    st.caption("AI powered by Google Gemini (free tier)")

# ── Main layout ───────────────────────────────────────────────────────────────
st.title("🖥️ NovaScript Compiler — Cloud Edition")
st.caption("Type NovaScript code below, then press **▶ Run** to compile and execute.")

# Initialise session state
if "code" not in st.session_state:
    st.session_state.code = '-- Welcome to NovaScript!\ndisplay "Hello, World!"'
if "result" not in st.session_state:
    st.session_state.result = None

# ── Editor row ────────────────────────────────────────────────────────────────
col_editor, col_run = st.columns([5, 1])

with col_editor:
    code_input = st.text_area(
        "Code editor",
        value=st.session_state.code,
        height=280,
        label_visibility="collapsed",
        key="code_editor",
    )

with col_run:
    st.write("")   # vertical spacer
    st.write("")
    run_clicked = st.button("▶  Run",   use_container_width=True, type="primary")
    st.button("🗑  Clear", use_container_width=True, on_click=_clear_editor)

if run_clicked:
    st.session_state.code   = code_input
    st.session_state.result = run_novascript(code_input)

# ── Results tabs ──────────────────────────────────────────────────────────────
result = st.session_state.result

if result is not None:
    tab_out, tab_err, tab_tok, tab_pt, tab_ast, tab_sym, tab_ai = st.tabs(
        ["📤 Output", "❌ Errors", "🔤 Tokens",
         "🌳 Parse Tree", "🌿 AST",
         "📋 Symbol Table", "🤖 AI Assistant"]
    )

    # ── Output ────────────────────────────────────────────────────────────────
    with tab_out:
        if result["success"]:
            st.success("✅ Compiled and executed successfully.", icon="✅")
        output_text = result["output"].strip() if result["output"] else ""
        if output_text:
            st.markdown(
                f'<div class="output-box">{output_text}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No output produced.")

    # ── Errors ────────────────────────────────────────────────────────────────
    with tab_err:
        errors   = result.get("errors",   [])
        warnings = result.get("warnings", [])
        if not errors and not warnings:
            st.success("No errors or warnings! ✅")
        else:
            for e in errors:
                with st.expander(
                    f"❌  [{e.get('type','ERROR')}] Line {e.get('line','-')} — "
                    f"{e.get('message','')}",
                    expanded=True,
                ):
                    st.code(e.get("message", ""), language="text")
            for w in warnings:
                with st.expander(
                    f"⚠️  [{w.get('type','WARNING')}] Line {w.get('line','-')} — "
                    f"{w.get('message','')}",
                    expanded=False,
                ):
                    st.code(w.get("message", ""), language="text")

    # ── Tokens ────────────────────────────────────────────────────────────────
    with tab_tok:
        tokens = result.get("tokens", [])
        if not tokens:
            st.info("No tokens — run the program first.")
        else:
            st.caption(f"{len(tokens)} token(s) found")
            # Render as coloured chips
            chips_html = "".join(
                f'<span class="token-chip">{t.type}<br><small>{str(t.value)[:20]}</small></span>'
                for t in tokens
            )
            st.markdown(chips_html, unsafe_allow_html=True)
            st.markdown("---")
            # Also offer a table view
            with st.expander("Table view"):
                import pandas as pd
                rows = [{"#": i+1, "Type": t.type, "Value": str(t.value),
                         "Line": getattr(t, "lineno", "-")}
                        for i, t in enumerate(tokens)]
                st.dataframe(pd.DataFrame(rows), use_container_width=True,
                             hide_index=True)

    # ── Parse Tree ────────────────────────────────────────────────────────────
    with tab_pt:
        st.caption(
            "The **Parse Tree** shows the grammar-level structure of the program, "
            "including keyword terminals (grey nodes) that appear in the NovaScript grammar."
        )
        _render_tree_tab(result.get("ast"), "parse")

    # ── AST ───────────────────────────────────────────────────────────────────
    with tab_ast:
        st.caption(
            "The **Abstract Syntax Tree** is a clean, simplified view of the program "
            "structure — redundant grammar symbols are removed, leaving only semantically "
            "meaningful nodes."
        )
        _render_tree_tab(result.get("ast"), "ast")

    # ── Symbol Table ──────────────────────────────────────────────────────────
    with tab_sym:
        sym = result.get("symbol_table", {})
        if not sym:
            st.info("Symbol table is empty — run the program first.")
        else:
            import pandas as pd
            rows = [{"Variable": k, "Value": str(v),
                     "Type": type(v).__name__}
                    for k, v in sym.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True,
                         hide_index=True)

    # ── AI Assistant ──────────────────────────────────────────────────────────
    with tab_ai:
        st.subheader("🤖 AI Teaching Assistant  (Google Gemini)")

        api_ready = bool(os.environ.get("GOOGLE_API_KEY", "").strip())

        if not api_ready:
            st.warning(
                "No Google API key found.  "
                "Paste your key in the **sidebar** to enable the AI assistant.\n\n"
                "Get a **free** key at https://aistudio.google.com/app/apikey",
                icon="⚠️",
            )
        else:
            # Quick action buttons
            col1, col2, col3 = st.columns(3)
            explain_clicked  = col1.button("🔍 Explain Code",       use_container_width=True)
            error_clicked    = col2.button("⚠️  Explain Errors",    use_container_width=True)
            fix_clicked      = col3.button("✏️  Suggest Fix",       use_container_width=True)

            # Free-text question
            question = st.text_input(
                "Ask a question about NovaScript or your code:",
                placeholder="e.g. How do I use a for loop in NovaScript?",
            )
            ask_clicked = st.button("Ask ↵", type="primary")

            # Determine prompt
            prompt_to_send = None
            q_code  = code_input.strip()
            q_error = ""
            if result.get("errors"):
                q_error = "\n".join(
                    f"{e.get('type')} at line {e.get('line')}: {e.get('message')}"
                    for e in result["errors"]
                )

            if explain_clicked:
                if not q_code:
                    st.warning("Write some NovaScript code first, then press Run.")
                else:
                    prompt_to_send = (
                        "Explain what this NovaScript program does, step by step. "
                        "Aim for a first-year student audience."
                    )
            elif error_clicked:
                if not q_error:
                    st.warning("No errors found — run the program first (▶ Run).")
                else:
                    prompt_to_send = (
                        "Explain each of these NovaScript errors in plain language "
                        "and tell me exactly how to fix them."
                    )
            elif fix_clicked:
                if not q_error:
                    st.warning("No errors detected — run the program first (▶ Run).")
                else:
                    prompt_to_send = (
                        "Fix all the errors in this NovaScript code. "
                        "Show the complete corrected program and briefly explain every change."
                    )
            elif ask_clicked and question.strip():
                prompt_to_send = question.strip()

            if prompt_to_send:
                with st.spinner("Thinking…"):
                    try:
                        from llm_runner import get_ai_response
                        ai_reply = get_ai_response(
                            prompt_to_send, code=q_code, error=q_error
                        )
                    except Exception as exc:
                        ai_reply = f"❌  Error: {exc}"

                st.markdown("**AI Response:**")
                st.markdown(
                    f'<div class="ai-box">{ai_reply}</div>',
                    unsafe_allow_html=True,
                )

else:
    # No result yet — show a tip
    st.info(
        "👆  Type or load NovaScript code above, then press **▶ Run** to compile and execute.",
        icon="💡",
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "NovaScript Compiler · CIT4004 Analysis of Programming Languages · "
    "University of Technology, Jamaica · "
    "AI powered by Google Gemini free tier"
)
