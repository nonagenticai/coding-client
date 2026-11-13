"""AST debugging utilities.

TODO: Implement AST debugging helpers for development.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ASTDebugMixin:
    """Mixin class providing AST debugging utilities.

    TODO: Implement AST visualization and debugging methods.
    """

    def debug_ast_node(self, node: Any, depth: int = 0) -> str:
        """Generate debug representation of an AST node (stub)."""
        return repr(node)

    def dump_ast(self, node: Any, indent: int = 2) -> str:
        """Dump AST tree as formatted string (stub)."""
        import ast

        if isinstance(node, ast.AST):
            return ast.dump(node, indent=indent)
        return repr(node)


def log_ast_for_development(
    node: Any,
    message: str = "AST node",
    level: int = logging.DEBUG,
) -> None:
    """Log an AST node for development/debugging purposes (stub).

    Args:
        node: The AST node to log.
        message: Description to include in the log.
        level: Logging level.
    """
    logger.log(level, "%s: %s", message, repr(node))
