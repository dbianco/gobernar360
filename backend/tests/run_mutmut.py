"""mutmut, including what it leaves out by itself: decorated functions.

    GOBERNAR360_TEST_DATABASES=5 uv run python -m tests.run_mutmut run --max-children 4
    uv run python -m tests.run_mutmut results

It takes mutmut's own arguments. Plain `mutmut run` never mutates a function that has a
decorator, and in this app those are every API route, every command, every validator and
every property: about a third of the code, and the part that checks who may do what.

Here they are mutated too. The decorator stays on mutmut's trampoline, so each route is
registered once, and the copies that it switches between have none. Only bodies are mutated:
the framework reads the decorator's arguments and the parameters' defaults when the module is
imported, before any mutant is active.

Still left out: functions cached for the whole process (`lru_cache`, `cache`), setters (they
share their name with the getter) and the routes nested in `build_router`, which are made
while importing.
"""

import sys
from collections.abc import Iterator

import libcst as cst
from mutmut.mutation import file_mutation

# The last part of the decorators whose functions are mutated, called or not.
DECORATORS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "command",
    "property",
    "contextmanager",
    "model_validator",
}

_skip = file_mutation.MutationVisitor._skip_node_and_children
_arrange = file_mutation.function_trampoline_arrangement


def _name(decorator: cst.Decorator) -> str:
    node = decorator.decorator
    if isinstance(node, cst.Call):
        node = node.func
    return node.attr.value if isinstance(node, cst.Attribute) else node.value


def _mutated_here(function: cst.FunctionDef) -> bool:
    names = [_name(decorator) for decorator in function.decorators]
    return bool(names) and names[0] in DECORATORS and set(names[1:]) <= {"classmethod"}


def _functions_in(node: cst.CSTNode) -> Iterator[cst.FunctionDef]:
    for child in node.children:
        if isinstance(child, cst.FunctionDef):
            yield child
        yield from _functions_in(child)


def skip_node_and_children(visitor, node: cst.CSTNode) -> bool:
    nested = visitor.__dict__.setdefault("_nested", set())
    left_alone = visitor.__dict__.setdefault("_left_alone", set())
    if isinstance(node, cst.FunctionDef) and node not in nested:
        nested.update(_functions_in(node))
        # The name a property shares with its setter would be mutated twice.
        if _mutated_here(node) and node.name.value != "subject":
            left_alone.add(node.params)
            return False
    if node in left_alone:
        return True
    return _skip(visitor, node)


def arrange(function: cst.FunctionDef, mutants, class_name):
    if not _mutated_here(function):
        return _arrange(function, mutants, class_name)
    plain = function.with_changes(decorators=[])
    declaration, nodes, assignment, names = _arrange(plain, mutants, class_name)
    trampoline = nodes[0]
    nodes[0] = trampoline.with_changes(decorators=[*function.decorators, *trampoline.decorators])
    return declaration, nodes, assignment, names


file_mutation.MutationVisitor._skip_node_and_children = skip_node_and_children
file_mutation.function_trampoline_arrangement = arrange

if __name__ == "__main__":
    from mutmut.__main__ import cli

    # `-m` has imported these tests; pytest has to import the copy next to the mutants.
    sys.modules.pop("tests", None)
    sys.exit(cli())
