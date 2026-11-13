"""The SKIP_AUTH hatch must not come back — by name OR by shape.

Until 1.16.0 this SDK shipped, in the production wheel:

    async def require_tenant(request):
        if os.getenv("SKIP_AUTH", "").lower() == "true":
            return "test-tenant"
        ...

as the FIRST statement of ``require_tenant``, ``optional_tenant`` and
``get_current_user_with_tenant`` — above every credential path. Setting one
environment variable made every route in every consuming service resolve to a
single hardcoded tenant.

It was never set in production. That is precisely why it survived for months:
nothing failed, nothing alerted, and no test would have gone red if it had been
set. Deleting it is a one-line change; keeping it deleted is this file.

WHY THREE RULES AND NOT A GREP
-------------------------------
A grep for "SKIP_AUTH" is defeated by renaming the variable, which is a
plausible thing for someone to do while "restoring the test hook we used to
have". So:

    A  name denylist  — catches the literal return
    B  SHAPE rule     — catches it under ANY name (this is the load-bearing one)
    C  literal rule   — a production auth path must not carry the tenant it hands out
    D  helper hygiene — the sanctioned replacement must stay un-activatable by env

Rule B is what makes A more than decoration, and the mutation table at the
bottom of this docstring is the evidence: mutant M2 renames the variable and
must still die.

⚠️ Rule B must NOT fire on an early-return env gate in general — that is an
ordinary, correct pattern. ``_default_tenant.enforce_default_tenant_configured``
opens with exactly ``if os.getenv("ENVIRONMENT", ...) != "production": return``
and is a standing false-positive control (M7). The rule keys on returning a
truthy IDENTITY-SHAPED constant, not on early-returning.

MUTANTS — each of these was run against this file:

    M1  restore the branch verbatim                     A, B, C fire
    M2  same branch, renamed CODING_TEST_MODE           B, C fire  (A silent)
    M3  renamed AND returning os.getenv("FALLBACK_TENANT", "")
                                                        B fires    (A, C silent)
    M4  point the scan root at an empty directory       non-vacuity fires
    M5  existing trust_tenant_header()/TRUSTED_CIDRS reads   stay GREEN
    M6  "SKIP_AUTH" in a comment explaining its removal      stays GREEN
    M7  _default_tenant.py's bare-return env gate            stays GREEN

If rule B ever proves noisy, NARROW it. Do not weaken it to a name grep — M2
stops being caught and the whole file becomes decorative.
"""

from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

# Resolve the scan root through the IMPORTED package, never a path relative to
# this file. A relative path is how a guard ends up scanning a directory that
# moved, finding nothing, and reporting a pass forever (mutant M4).
_PACKAGE_FILE = importlib.import_module("coding_client").__file__
assert _PACKAGE_FILE is not None, "coding_client has no __file__ — namespace package?"
SRC = pathlib.Path(_PACKAGE_FILE).parent

# The sanctioned test-side replacement. Excluded from rules A-C because its
# entire job is to hand out a test tenant; rule D covers it instead.
TESTING_MODULE = SRC / "testing.py"

DENY_NAMES = {
    "SKIP_AUTH",
    "BYPASS_AUTH",
    "AUTH_BYPASS",
    "DISABLE_AUTH",
    "AUTH_DISABLED",
    "NO_AUTH",
}

# A known env read that must be found, proving the AST walk actually parsed
# something rather than silently walking an empty list.
CONTROL_ENV_NAME = "LICENSE_INTROSPECT_URL"

# Identity-shaped constructors. Returning one of these from an env-gated first
# statement is the hatch, whatever the variable is called.
IDENTITY_CALLS = {"User"}


def _py_files() -> list[pathlib.Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _env_read_names(node: ast.AST) -> list[str | None]:
    """Every environment variable name read anywhere under ``node``.

    ``None`` marks a read whose name is not a literal (e.g. a variable), which
    still counts as "this is an env read" for the shape rule.
    """
    names: list[str | None] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        # os.getenv("X") / os.environ.get("X")
        if isinstance(func, ast.Attribute) and func.attr in {"getenv", "get"}:
            target = func.value
            is_environ = (isinstance(target, ast.Attribute) and target.attr == "environ") or (
                isinstance(target, ast.Name) and target.id == "os"
            )
            if is_environ and sub.args:
                names.append(_literal_str(sub.args[0]))
    # os.environ["X"]
    for sub in ast.walk(node):
        if isinstance(sub, ast.Subscript):
            target = sub.value
            if isinstance(target, ast.Attribute) and target.attr == "environ":
                names.append(_literal_str(sub.slice))
    return names


def _literal_str(node: ast.expr) -> str | None:
    """The str value of a literal node, or None for anything non-literal.

    A non-str constant (or a variable) still counts as "an env read happened",
    which is all the shape rule needs — it just cannot be matched by name.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _returns_identity_constant(stmt: ast.stmt) -> bool:
    """True if ``stmt`` is a Return of a truthy identity-shaped value."""
    if not isinstance(stmt, ast.Return) or stmt.value is None:
        return False
    value = stmt.value
    if isinstance(value, ast.Constant):
        return isinstance(value.value, str) and bool(value.value)
    if isinstance(value, ast.Call):
        func = value.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        return name in IDENTITY_CALLS
    return False


@pytest.fixture(scope="module")
def parsed() -> list[tuple[pathlib.Path, ast.Module]]:
    trees = []
    for path in _py_files():
        trees.append((path, ast.parse(path.read_text(), filename=str(path))))
    return trees


def test_the_scan_is_not_vacuous(parsed):
    """Runs FIRST in spirit: every rule below is worthless if this is wrong.

    Mutant M4 — point SRC at an empty directory — must land here, not sail
    through three green rules that examined nothing.
    """
    files = [p for p, _ in parsed]
    assert len(files) >= 40, f"only {len(files)} source files found under {SRC}"
    assert SRC / "auth" / "tenant.py" in files, "the file the hatch lived in is not in scope"
    assert SRC / "auth" / "middleware.py" in files, "auth/middleware.py is not in scope"

    found = {name for _, tree in parsed for name in _env_read_names(tree)}
    assert CONTROL_ENV_NAME in found, (
        f"POSITIVE CONTROL FAILED: {CONTROL_ENV_NAME} was not found in any env read. "
        "The AST walk is not seeing env reads at all, so rules A and B cannot fire "
        "and a green result here means nothing."
    )


def test_rule_a_no_bypass_variable_is_read_anywhere(parsed):
    """A: no auth-bypass variable name is read in the shipped package."""
    offenders = []
    for path, tree in parsed:
        if path == TESTING_MODULE:
            continue
        for name in _env_read_names(tree):
            if name in DENY_NAMES:
                offenders.append(f"{path.relative_to(SRC)} reads {name}")
    assert not offenders, (
        "An auth-bypass environment variable is read in the production wheel:\n  "
        + "\n  ".join(offenders)
        + "\nSKIP_AUTH was deleted in 1.16.0. If a test suite needs to bypass auth, use "
        "coding_client.testing.override_tenant_auth — it is per-app and cannot be "
        "switched on by the environment."
    )


def test_rule_b_no_env_gated_identity_shortcut(parsed):
    """B: no function opens by returning an identity constant behind an env read.

    Name-independent — this is what survives a rename. Scoped to auth/ because
    that is where returning an identity means bypassing authentication.
    """
    offenders = []
    for path, tree in parsed:
        if path == TESTING_MODULE or "auth" not in path.parts:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            body = [s for s in node.body if not isinstance(s, ast.Expr | ast.Pass)]
            if not body:
                continue
            first = body[0]
            if not isinstance(first, ast.If):
                continue
            if not _env_read_names(first.test):
                continue
            inner = [s for s in first.body if not isinstance(s, ast.Expr | ast.Pass)]
            if len(inner) == 1 and _returns_identity_constant(inner[0]):
                offenders.append(f"{path.relative_to(SRC)}:{first.lineno} in {node.name}()")
    assert not offenders, (
        "A function in auth/ opens with an environment-gated shortcut that returns an "
        "identity:\n  "
        + "\n  ".join(offenders)
        + "\nThat is the SKIP_AUTH shape regardless of what the variable is called: one "
        "env var, and every caller resolves to a constant identity without presenting a "
        "credential. An env-gated EARLY RETURN is fine (see "
        "_default_tenant.enforce_default_tenant_configured) — returning an identity is not."
    )


def test_rule_c_the_package_does_not_carry_the_tenant_it_would_hand_out(parsed):
    """C: the literal "test-tenant" appears nowhere outside the testing helper.

    Independent of A and B: it catches a reintroduction that uses a different
    variable name AND a different control-flow shape, as long as it still hands
    back the same constant.
    """
    offenders = []
    for path, tree in parsed:
        if path == TESTING_MODULE:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == "test-tenant":
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, (
        'The literal "test-tenant" is present in the shipped package at:\n  '
        + "\n  ".join(offenders)
        + "\nA production auth path has no reason to carry the tenant it would hand out. "
        "The only sanctioned home for it is coding_client/testing.py."
    )


def test_rule_d_the_testing_helper_cannot_be_switched_on_by_the_environment():
    """D: the replacement must not become the thing it replaced.

    `override_tenant_auth` is safe *because* reaching it requires an explicit
    call against a specific app object. An env read here would quietly restore
    the ambient, global, one-variable bypass that 1.16.0 removed — and it would
    look like a convenience.
    """
    assert TESTING_MODULE.exists(), "coding_client/testing.py is missing"
    tree = ast.parse(TESTING_MODULE.read_text(), filename=str(TESTING_MODULE))

    env_reads = _env_read_names(tree)
    assert not env_reads, (
        f"coding_client/testing.py reads the environment: {env_reads}. "
        "It must be activatable only by an explicit call — that is the entire "
        "difference between it and the SKIP_AUTH hatch it replaced."
    )

    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
    }
    assert "pytest" not in imports, (
        "coding_client/testing.py imports pytest, making it a hard runtime dependency "
        "of the production wheel."
    )
