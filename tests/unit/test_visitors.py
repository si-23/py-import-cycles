#!/usr/bin/env python3
import ast

import pytest

from py_import_cycles import visitors


@pytest.mark.parametrize(
    ["content", "count", "skip"],
    [
        ("", 0, True),
        ("from foo import bar", 1, True),
        ("import foo\nimport bar", 2, True),
        ("import typing\nif typing.TYPE_CHECKING: from foo import bar", 1, True),
        ("import typing\nif typing.TYPE_CHECKING: from foo import bar", 2, False),
        ("import typing\nif typing.TYPE_CHECKING: import foo", 1, True),
        ("import typing\nif typing.TYPE_CHECKING: import foo", 2, False),
        ("import typing as t\nif t.TYPE_CHECKING: from foo import bar", 1, True),
        ("import typing as t\nif t.TYPE_CHECKING: from foo import bar", 2, False),
        ("import typing as t\nif t.TYPE_CHECKING: import foo", 1, True),
        ("import typing as t\nif t.TYPE_CHECKING: import foo", 2, False),
        ("from typing import TYPE_CHECKING\nif TYPE_CHECKING: from foo import bar", 1, True),
        ("from typing import TYPE_CHECKING\nif TYPE_CHECKING: from foo import bar", 2, False),
        ("from typing import TYPE_CHECKING\nif TYPE_CHECKING: import foo", 1, True),
        ("from typing import TYPE_CHECKING\nif TYPE_CHECKING: import foo", 2, False),
        (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:"
            "\n if 1:\n  import foo\n  import bar",
            1,
            True,
        ),
        (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:"
            "\n if 1:\n  import foo\n  import bar",
            3,
            False,
        ),
    ],
)
def test_visit_python_file(content: str, count: int, skip: bool) -> None:
    tree = ast.parse(content)
    visitor = visitors.NodeVisitorImports(skip_type_checking=skip)
    visitor.visit(tree)
    assert len(visitor.import_stmts) == count
