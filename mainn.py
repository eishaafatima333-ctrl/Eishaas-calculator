import ast
import math
import operator as op
import re

import streamlit as st
import streamlit.components.v1 as components

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Scientific Calculator by Eishaa Fatima", page_icon="🧮", layout="centered")

# =====================================================================
#  CALCULATOR ENGINE
# =====================================================================
FUNC_NAMES = "sin⁻¹|cos⁻¹|tan⁻¹|sin|cos|tan|log|ln|√"

# What each function button inserts into the expression
FUNCS = {
    "sin": "sin(", "cos": "cos(", "tan": "tan(",
    "sin⁻¹": "sin⁻¹(", "cos⁻¹": "cos⁻¹(", "tan⁻¹": "tan⁻¹(",
    "log": "log(", "ln": "ln(", "√": "√(",
}
FUNC_TOKENS = sorted(set(FUNCS.values()), key=len, reverse=True)

BINARY = ["+", "-", "×", "÷", "^"]
ERRORS = {"Error", "Math Error", "Can't divide by 0"}

# "sin(30" / "√(9" / "cos(-45" / "tan(π"  -> a function with a simple argument.
# When you press + - × ÷ ^ x² after it, the bracket is closed automatically,
# so  sin30+5  means  sin(30)+5  (no need to type the bracket yourself).
SIMPLE_ARG = re.compile(rf"(?:{FUNC_NAMES})\(-?(?:[0-9]+\.?[0-9]*|\.[0-9]+|π|e)$")

BIN_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
}
CONSTANTS = {"pi": math.pi, "e": math.e}


def clean(x):
    """Remove floating point noise (e.g. 6.1e-17 -> 0, 0.49999999999999994 -> 0.5)."""
    return round(x, 12) + 0.0


MODES = ["DEG", "RAD", "GRAD"]


def make_functions(mode):
    """Math functions. Trig functions respect Degree / Radian / Gradian mode."""

    def to_rad(x):
        if mode == "DEG":
            return math.radians(x)
        if mode == "GRAD":
            return x * math.pi / 200
        return x

    def from_rad(x):
        if mode == "DEG":
            return math.degrees(x)
        if mode == "GRAD":
            return x * 200 / math.pi
        return x

    def sin(x):
        return clean(math.sin(to_rad(x)))

    def cos(x):
        return clean(math.cos(to_rad(x)))

    def tan(x):
        # tan is undefined at 90°, 270° ... (π/2 rad, 100 grad)
        if abs(math.cos(to_rad(x))) < 1e-12:
            raise ValueError("tan undefined")
        return clean(math.tan(to_rad(x)))

    def asin(x):
        return clean(from_rad(math.asin(x)))

    def acos(x):
        return clean(from_rad(math.acos(x)))

    def atan(x):
        return clean(from_rad(math.atan(x)))

    def fact(x):
        if x < 0 or x != int(x) or x > 170:
            raise ValueError("bad factorial")
        return float(math.factorial(int(x)))

    return {
        "sin": sin, "cos": cos, "tan": tan,
        "asin": asin, "acos": acos, "atan": atan,
        "log": math.log10, "ln": math.log, "sqrt": math.sqrt,
        "fact": fact,
    }


def evaluate(expression, mode="DEG"):
    """Safely evaluate an already-prepared expression (no eval())."""
    funcs = make_functions(mode)

    def solve(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in CONSTANTS:
            return CONSTANTS[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
            left, right = solve(node.left), solve(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10000:
                raise OverflowError
            result = BIN_OPS[type(node.op)](left, right)
            if isinstance(result, complex):
                raise ValueError("complex result")
            return result
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = solve(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in funcs and len(node.args) == 1 and not node.keywords):
            return funcs[node.func.id](solve(node.args[0]))
        raise SyntaxError("invalid expression")

    result = solve(ast.parse(expression, mode="eval").body)
    if not math.isfinite(result):
        raise OverflowError
    return clean(result)


def expand_factorials(e):
    """Turn 5!  /  (2+3)!  /  pi!  into fact(5) / fact((2+3)) / fact(pi)."""
    while "!" in e:
        i = e.index("!")
        j = i
        if i == 0:
            raise SyntaxError("nothing before !")
        prev = e[i - 1]
        if prev == ")":
            depth = 0
            j = i - 1
            while j >= 0:
                if e[j] == ")":
                    depth += 1
                elif e[j] == "(":
                    depth -= 1
                    if depth == 0:
                        break
                j -= 1
            if j < 0:
                raise SyntaxError("unbalanced")
            while j > 0 and e[j - 1].isalpha():  # include function name, e.g. sin(...)
                j -= 1
        elif prev.isdigit() or prev == ".":
            j = i - 1
            while j > 0 and (e[j - 1].isdigit() or e[j - 1] == "."):
                j -= 1
        elif prev.isalpha():
            j = i - 1
            while j > 0 and e[j - 1].isalpha():
                j -= 1
        else:
            raise SyntaxError("bad factorial")
        e = e[:j] + "fact(" + e[j:i] + ")" + e[i + 1:]
    return e


def prepare(expr):
    """Convert what the user typed into something the evaluator understands."""
    e = expr
    # 1) auto-close any open brackets  ->  sin(30  becomes  sin(30)
    e += ")" * max(e.count("(") - e.count(")"), 0)
    # 2) implicit multiplication:  2π  2(3)  (2)(3)  3sin(30)  (2)3  π2
    e = re.sub(r"([0-9.)πe!%])(?=\(|π|e|√|[a-z])", r"\1×", e)
    e = re.sub(r"([)πe!%])(?=[0-9.])", r"\1×", e)
    # 3) symbols -> python
    for a, b in (("sin⁻¹(", "asin("), ("cos⁻¹(", "acos("), ("tan⁻¹(", "atan("),
                 ("√(", "sqrt("), ("×", "*"), ("÷", "/"), ("^", "**"),
                 ("π", "pi"), ("%", "/100")):
        e = e.replace(a, b)
    # 4) factorials
    return expand_factorials(e)


def fmt(number):
    number = clean(number)
    if abs(number) < 1e15 and number == int(number):
        return str(int(number))
    text = f"{number:.12g}"
    if "e" in text:  # 1e+20  ->  1×10^20  (still a valid expression)
        mantissa, exponent = text.split("e")
        return f"{mantissa}×10^{int(exponent)}"
    return text


# =====================================================================
#  SESSION STATE
# =====================================================================
st.session_state.setdefault("expr", "")       # what the user typed
st.session_state.setdefault("answer", "")     # result after pressing =
st.session_state.setdefault("done", False)    # True right after pressing =
st.session_state.setdefault("mode", "DEG")    # DEG, RAD or GRAD


def reset(s):
    s.expr, s.answer, s.done = "", "", False


def continue_from_answer(s):
    """After '=', operators keep going with the previous answer."""
    if s.done:
        s.expr, s.answer, s.done = s.answer, "", False


def compute(s, expr):
    try:
        s.answer = fmt(evaluate(prepare(expr), s.mode))
    except ZeroDivisionError:
        s.answer = "Can't divide by 0"
    except (ValueError, OverflowError):
        s.answer = "Math Error"
    except Exception:
        s.answer = "Error"
    s.done = True


def close_simple_function(s):
    if SIMPLE_ARG.search(s.expr):
        s.expr += ")"


# =====================================================================
#  BUTTON LOGIC
# =====================================================================
def press_button(b):
    s = st.session_state

    # After an error: backspace lets you edit, anything else starts fresh
    if s.answer in ERRORS:
        if b == "⌫":
            s.answer, s.done = "", False
        elif b != "AC" and b not in MODES:
            reset(s)

    if b == "AC":
        reset(s)
        return

    if b in MODES:
        s.mode = b
        if s.done and s.answer not in ERRORS:      # re-calculate in the new mode
            compute(s, s.expr.rstrip("+-×÷^"))
        return

    if b == "⌫":
        if s.done:
            s.done, s.answer = False, ""
        for token in FUNC_TOKENS:
            if s.expr.endswith(token):
                s.expr = s.expr[: -len(token)]
                return
        s.expr = s.expr[:-1]
        return

    if b == "=":
        if s.done:
            return
        expr = s.expr.rstrip("+-×÷^")
        if not expr:
            return
        compute(s, expr)
        return

    # ---- numbers ----
    if b in "0123456789" and len(b) == 1:
        if s.done:
            reset(s)
        if re.search(r"(?<![0-9.])0$", s.expr):  # avoid 05, 007
            s.expr = s.expr[:-1] + b
        else:
            s.expr += b
        return

    if b == ".":
        if s.done:
            reset(s)
        m = re.search(r"[0-9.]+$", s.expr)
        if m:
            if "." not in m.group():
                s.expr += "."
        else:
            s.expr += "0."
        return

    # ---- constants, functions, brackets ----
    if b in ("π", "e") or b in FUNCS or b == "(":
        if s.done:
            reset(s)
        s.expr += FUNCS.get(b, b)
        return

    if b == ")":
        depth = s.expr.count("(") - s.expr.count(")")
        if depth > 0 and s.expr and s.expr[-1] not in "(+-×÷^":
            s.expr += ")"
        return

    # ---- postfix: % and n! ----
    if b in ("%", "n!"):
        continue_from_answer(s)
        if s.expr and s.expr[-1] in "0123456789.)πe!%":
            s.expr += "%" if b == "%" else "!"
        return

    # ---- x² ----
    if b == "x²":
        continue_from_answer(s)
        if s.expr and s.expr[-1] not in "+-×÷^(":
            close_simple_function(s)
            s.expr += "^2"
        return

    # ---- binary operators ----
    if b in BINARY:
        continue_from_answer(s)
        if not s.expr:
            if b == "-":
                s.expr = "-"
            return
        close_simple_function(s)
        last = s.expr[-1]
        if last in "+-×÷^":
            if b == "-" and last in "×÷^":
                s.expr += "-"          # e.g. 5×-3
            else:
                stripped = s.expr.rstrip("+-×÷^")  # replace previous operator
                s.expr = (stripped + b) if stripped else ("-" if b == "-" else "")
        elif last == "(":
            if b == "-":
                s.expr += "-"
        else:
            s.expr += b


def live_preview(s):
    """Result shown (muted) while the user is still typing."""
    expr = s.expr.rstrip("+-×÷^")
    if not expr or re.fullmatch(r"-?[0-9.]+", expr):
        return ""
    try:
        return fmt(evaluate(prepare(expr), s.mode))
    except Exception:
        return ""


# =====================================================================
#  CSS  (white buttons on a blue calculator)
# =====================================================================
# NOTE: HTML passed to st.markdown must NOT be indented by 4+ spaces,
# otherwise Markdown treats it as a code block.
CSS = """
<style>
.stApp { background: linear-gradient(135deg, #dbeafe, #93c5fd); }
#MainMenu, footer, header { visibility: hidden; }
.block-container { max-width: 520px !important; padding-top: 1.2rem !important; }

/* Calculator body */
.st-key-calc {
    padding: 20px;
    background: linear-gradient(160deg, #2563eb, #1d4ed8 55%, #1e3a8a);
    border: 3px solid #bfdbfe;
    border-radius: 30px;
    box-shadow: 0 18px 40px rgba(30,64,175,0.40), inset 0 0 22px rgba(255,255,255,0.18);
    gap: 0.5rem;
}

/* Keep the button grid in rows, even on phones */
.st-key-calc [data-testid="stHorizontalBlock"] {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0.45rem !important;
}
.st-key-calc [data-testid="stColumn"],
.st-key-calc [data-testid="column"] {
    min-width: 0 !important;
    width: auto !important;
    flex: 1 1 0 !important;
}

/* Header */
.calc-header { text-align:center; line-height:1.25; padding-bottom:2px; }
.calc-title  { color:#ffffff; font-size:24px; font-weight:800; letter-spacing:.5px; }
.calc-author { color:#dbeafe; font-size:15px; font-weight:500; }
.calc-author b { color:#ffffff; font-weight:700; }

/* Display */
.display {
    background: rgba(15,35,110,0.55);
    border: 2px solid rgba(191,219,254,0.85);
    border-radius: 20px;
    padding: 10px 18px;
    text-align: right;
    box-shadow: inset 0 3px 12px rgba(0,0,0,0.25);
}
.expression { color:#bfdbfe; font-size:20px; min-height:28px; word-break:break-all; }
.result     { color:#ffffff; font-weight:600; min-height:50px; line-height:50px;
              word-break:break-all; }
.result.preview { color:#bfdbfe; }

/* Buttons: white by default */
.st-key-calc div.stButton > button {
    width: 100%;
    height: 58px;
    padding: 0;
    border-radius: 18px;
    border: none;
    background: #ffffff;
    box-shadow: 0 4px 10px rgba(10,30,100,0.35);
    transition: all 0.12s ease;
}
.st-key-calc div.stButton > button p {
    color: #1d4ed8;
    font-size: 23px;
    font-weight: 600;
    margin: 0;
}
.st-key-calc div.stButton > button:hover  { transform: translateY(-2px); background:#eff6ff; }
.st-key-calc div.stButton > button:active { transform: scale(0.94); }

/* Scientific function buttons (smaller, light-blue tint) */
[class*="st-key-fn_"] div.stButton > button { height: 44px !important; background:#eaf2ff !important; }
[class*="st-key-fn_"] div.stButton > button p { font-size: 16px !important; }

/* Angle mode buttons (DEG / RAD / GRAD) */
[class*="st-key-mode"] div.stButton > button { height: 36px !important; border-radius: 12px !important; }
[class*="st-key-mode"] div.stButton > button p { font-size: 14px !important; letter-spacing: 1px; }
[class*="st-key-modeon_"] div.stButton > button {
    background: #0f2a7a !important; border: 2px solid #ffffff !important;
}
[class*="st-key-modeon_"] div.stButton > button p { color: #ffffff !important; }

/* Operator buttons */
[class*="st-key-op_"] div.stButton > button { background:#dbeafe !important; }
[class*="st-key-op_"] div.stButton > button p { font-weight: 800 !important; }

/* Equals button */
[class*="st-key-eq_"] div.stButton > button {
    background: linear-gradient(145deg, #60a5fa, #3b82f6) !important;
}
[class*="st-key-eq_"] div.stButton > button p { color:#ffffff !important; }

.calc-footer { text-align:center; color:#dbeafe; font-size:11px; line-height:1.5; opacity:.9; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# =====================================================================
#  UI
# =====================================================================
SCI_ROWS = [
    ["sin", "cos", "tan", "log", "ln"],
    ["sin⁻¹", "cos⁻¹", "tan⁻¹", "√", "x²"],
    ["π", "e", "n!", "%", "^"],
]
NUM_ROWS_TOP = [["(", ")", "AC", "⌫"]]
NUM_ROWS = [
    ["7", "8", "9", "÷"],
    ["4", "5", "6", "×"],
    ["1", "2", "3", "-"],
    ["0", ".", "=", "+"],
]
OP_LABELS = {"AC", "⌫", "÷", "×", "-", "+", "^", "%", "(", ")"}


def button_kind(label):
    if label == "=":
        return "eq"
    if label in OP_LABELS:
        return "op"
    if label in FUNCS or label in ("π", "e", "x²", "n!"):
        return "fn"
    return "num"


s = st.session_state

# ---- display text ----
if s.done:
    line1, line2, muted = s.expr, s.answer, False
else:
    preview = live_preview(s)
    if preview:
        line1, line2, muted = s.expr, preview, True
    else:
        line1, line2, muted = "", (s.expr or "0"), False
size = 42 if len(line2) <= 12 else 32 if len(line2) <= 18 else 24

with st.container(key="calc"):
    st.markdown(
        f"""<div class="calc-header">
<div class="calc-title">Scientific Calculator</div>
<div class="calc-author">by <b>Eishaa Fatima</b></div>
</div>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""<div class="display">
<div class="expression">{line1 or "&nbsp;"}</div>
<div class="result{" preview" if muted else ""}" style="font-size:{size}px;">{line2}</div>
</div>""",
        unsafe_allow_html=True,
    )

    mode_cols = st.columns(3, gap="small")
    for c, name in enumerate(MODES):
        mode_cols[c].button(
            name,
            key=f"{'modeon' if s.mode == name else 'modeoff'}_{c}",
            use_container_width=True,
            on_click=press_button,
            args=(name,),
        )

    for r, row in enumerate(SCI_ROWS + NUM_ROWS_TOP + NUM_ROWS):
        cols = st.columns(len(row), gap="small")
        for c, label in enumerate(row):
            # Streamlit reads button labels as Markdown, and a lone "+" or "-" is
            # a list marker (renders as nothing). Escaping it makes the sign visible.
            shown = {"+": "\\+", "-": "\\-"}.get(label, label)
            cols[c].button(
                shown,
                key=f"{button_kind(label)}_{r}_{c}",
                use_container_width=True,
                on_click=press_button,
                args=(label,),
            )

    st.markdown(
        '<div class="calc-footer">Keyboard: 0-9 &nbsp;+ − * / ( ) . ^ ! % &nbsp;·&nbsp; '
        "Enter = &nbsp;·&nbsp; Backspace ⌫ &nbsp;·&nbsp; Esc / Delete AC<br>"
        "s sin · o cos · t tan · l log · n ln · q √ · p π · e e · d DEG · r RAD · g GRAD "
        "&nbsp;·&nbsp; Shift+S/O/T = inverse trig</div>",
        unsafe_allow_html=True,
    )

# =====================================================================
#  KEYBOARD SUPPORT
#  Streamlit can't read the keyboard directly, so a tiny script listens
#  for key presses on the page and "clicks" the matching on-screen button.
# =====================================================================
components.html(
    """
<script>
(function () {
  const parent = window.parent;
  const doc = parent.document;

  // remove an older listener (Streamlit re-runs the script)
  if (parent.__calcKeyHandler) {
    doc.removeEventListener("keydown", parent.__calcKeyHandler, true);
  }

  const MAP = {
    "0":"0","1":"1","2":"2","3":"3","4":"4","5":"5","6":"6","7":"7","8":"8","9":"9",
    ".":".", ",":".",
    "+":"+", "-":"-", "*":"×", "x":"×", "X":"×", "/":"÷",
    "(":"(", ")":")", "^":"^", "!":"n!", "%":"%",
    "Enter":"=", "=":"=", "Backspace":"⌫", "Delete":"AC", "Escape":"AC",
    "s":"sin", "o":"cos", "t":"tan", "l":"log", "n":"ln", "q":"√",
    "S":"sin⁻¹", "O":"cos⁻¹", "T":"tan⁻¹",
    "p":"π", "e":"e", "d":"DEG", "r":"RAD", "g":"GRAD"
  };

  function findButton(label) {
    const wanted = [label];
    const buttons = doc.querySelectorAll(".st-key-calc button");
    for (const b of buttons) {
      if (wanted.includes(b.innerText.trim())) return b;
    }
    return null;
  }

  function handler(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const tag = (e.target && e.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return;

    const label = MAP[e.key];
    if (!label) return;
    const btn = findButton(label);
    if (!btn) return;

    e.preventDefault();
    e.stopPropagation();   // stops Streamlit shortcuts (r, c ...) from interfering
    btn.click();
    if (doc.activeElement && doc.activeElement.blur) doc.activeElement.blur();
  }

  parent.__calcKeyHandler = handler;
  doc.addEventListener("keydown", handler, true);
})();
</script>
""",
    height=0,
)