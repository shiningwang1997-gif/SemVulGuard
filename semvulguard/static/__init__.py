"""Static analysis orchestrator.

Coordinates the three evidence backends (CodeQL, Joern, Clang) and normalizes
their output into :class:`StaticAlertRecord` streams. Implementation deferred to
a later phase.
"""
