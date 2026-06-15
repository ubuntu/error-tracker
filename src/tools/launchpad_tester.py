#!/usr/bin/python3
"""Tiny interactive wrapper around errortracker.launchpad.

This lets you call any public function of the ``errortracker.launchpad``
module with arbitrary values straight from the command line and inspect what
it returns, so you can eyeball whether the result looks right.

Usage:
    # list the callable functions and their signatures
    python3 tools/launchpad_tester.py --list

    # call a function; arguments are parsed as Python literals when possible,
    # otherwise treated as plain strings
    python3 tools/launchpad_tester.py get_codename_for_version 24.04
    python3 tools/launchpad_tester.py get_versions_for_binary bash 22.04
    python3 tools/launchpad_tester.py binaries_are_most_recent "[('bash', '5.1-6')]"
    python3 tools/launchpad_tester.py bug_is_fixed 1 "Ubuntu 24.04"

Arguments are evaluated with ``ast.literal_eval`` first (so lists, tuples,
ints, ``None``, etc. work as expected). Anything that is not a valid Python
literal is passed through unchanged as a string.

Run from the ``src`` directory (or with ``src`` on PYTHONPATH) so that the
``errortracker`` package is importable, the same as the other tools.
"""

import argparse
import ast
import inspect
import sys

from errortracker import launchpad


def _public_functions():
    """Return {name: function} for every public function in errortracker.launchpad."""
    functions = {}
    for name, obj in inspect.getmembers(launchpad, inspect.isfunction):
        # Skip private helpers (e.g. _get_launchpad) and anything imported
        # from another module.
        if name.startswith("_"):
            continue
        if getattr(obj, "__module__", None) != launchpad.__name__:
            continue
        functions[name] = obj
    return functions


def _parse_arg(value):
    """Best-effort conversion of a CLI string into a Python value."""
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def _list_functions(functions):
    print("Available functions in errortracker.launchpad:\n")
    for name in sorted(functions):
        signature = inspect.signature(functions[name])
        print(f"  {name}{signature}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Call errortracker.launchpad functions with arbitrary values.",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="list the callable functions with their signatures and exit",
    )
    parser.add_argument(
        "function",
        nargs="?",
        help="name of the launchpad function to call",
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="arguments to pass (parsed as Python literals when possible)",
    )
    options = parser.parse_args(argv)

    functions = _public_functions()

    if options.list or not options.function:
        _list_functions(functions)
        return 0 if options.list else 1

    if options.function not in functions:
        print(f"Unknown function: {options.function}\n", file=sys.stderr)
        _list_functions(functions)
        return 2

    func = functions[options.function]
    call_args = [_parse_arg(arg) for arg in options.args]

    printable_args = ", ".join(repr(arg) for arg in call_args)
    print(f"Calling {options.function}({printable_args})")
    try:
        result = func(*call_args)
    except Exception as exc:  # noqa: BLE001 - this is a debugging aid
        print(f"Raised {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Returned ({type(result).__name__}): {result!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
