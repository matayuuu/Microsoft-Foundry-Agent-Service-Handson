"""Pure domain rules for the Travel Ops API.

Everything in this package is framework-agnostic: no FastAPI, no I/O, no
randomness, no wall-clock reads. Given the same inputs it always produces the
same outputs, which is what lets the workshop treat this API as a
deterministic fixture rather than a real backend.
"""
