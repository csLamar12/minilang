"""
cloud_app.py — MiniLang Compiler  (Streamlit Cloud Edition)
CIT4004 · University of Technology, Jamaica

Deployable for FREE at https://streamlit.io/cloud
Run locally:  streamlit run cloud_app.py

This web interface exposes the full MiniLang compiler pipeline
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
from lexer        import MiniLangLexer
from parser       import MiniLangParser
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
    page_title="MiniLang Compiler",
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
        "-- Comprehensive MiniLang demo\n"
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

# ── Compiler helper ────────────────────────────────────────────────────────────
def run_minilang(source: str) -> dict:
    """
    Run *source* through all four compiler phases.
    Returns a dict with keys: tokens, ast, errors, warnings,
                               output, symbol_table, success.
    """
    error_handler.reset()

    lexer     = MiniLangLexer();  lexer.build()
    parser    = MiniLangParser(); parser.build()
    semantic  = SemanticAnalyzer()
    interp    = Interpreter()

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
        error_handler.reset()
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
        # Also grab interpreter's internal buffer (display statements)
        captured = buf.getvalue()
        internal = interp.get_output() if hasattr(interp, "get_output") else ""
        # Merge both (avoid duplicates when interpreter also calls print)
        result["output"] = captured if captured.strip() else internal
        result["symbol_table"] = dict(interp.symbol_table) if hasattr(
            interp, "symbol_table") else {}
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


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🖥️ MiniLang")
    st.caption("CIT4004 · University of Technology, Jamaica")
    st.markdown("---")

    # Example loader
    st.subheader("📂 Load Example")
    example_choice = st.selectbox("Choose an example", ["— select —"] + list(EXAMPLES))
    load_example = st.button("Load", use_container_width=True)

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
    st.caption("**MiniLang Compiler v1.0**")
    st.caption("Lexer → Parser → Semantic → Interpreter")
    st.caption("AI powered by Google Gemini (free tier)")

# ── Main layout ───────────────────────────────────────────────────────────────
st.title("🖥️ MiniLang Compiler — Cloud Edition")
st.caption("Type MiniLang code below, then press **▶ Run** to compile and execute.")

# Initialise session state
if "code" not in st.session_state:
    st.session_state.code = '-- Welcome to MiniLang!\ndisplay "Hello, World!"'
if "result" not in st.session_state:
    st.session_state.result = None

# Load example if requested
if load_example and example_choice != "— select —":
    st.session_state.code = EXAMPLES[example_choice]
    st.session_state.result = None
    st.rerun()

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
    run_clicked   = st.button("▶  Run",   use_container_width=True, type="primary")
    clear_clicked = st.button("🗑  Clear", use_container_width=True)

if clear_clicked:
    st.session_state.code   = ""
    st.session_state.result = None
    st.rerun()

if run_clicked:
    st.session_state.code   = code_input
    st.session_state.result = run_minilang(code_input)

# ── Results tabs ──────────────────────────────────────────────────────────────
result = st.session_state.result

if result is not None:
    tab_out, tab_err, tab_tok, tab_sym, tab_ai = st.tabs(
        ["📤 Output", "❌ Errors", "🔤 Tokens", "📋 Symbol Table", "🤖 AI Assistant"]
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
                "Ask a question about MiniLang or your code:",
                placeholder="e.g. How do I use a for loop in MiniLang?",
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
                    st.warning("Write some MiniLang code first, then press Run.")
                else:
                    prompt_to_send = (
                        "Explain what this MiniLang program does, step by step. "
                        "Aim for a first-year student audience."
                    )
            elif error_clicked:
                if not q_error:
                    st.warning("No errors found — run the program first (▶ Run).")
                else:
                    prompt_to_send = (
                        "Explain each of these MiniLang errors in plain language "
                        "and tell me exactly how to fix them."
                    )
            elif fix_clicked:
                if not q_error:
                    st.warning("No errors detected — run the program first (▶ Run).")
                else:
                    prompt_to_send = (
                        "Fix all the errors in this MiniLang code. "
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
        "👆  Type or load MiniLang code above, then press **▶ Run** to compile and execute.",
        icon="💡",
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "MiniLang Compiler · CIT4004 Analysis of Programming Languages · "
    "University of Technology, Jamaica · "
    "AI powered by Google Gemini free tier"
)
