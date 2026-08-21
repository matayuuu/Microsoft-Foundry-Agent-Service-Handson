"""Application use cases orchestrating the pure domain rules.

This layer has no HTTP concerns. It exists so the FastAPI adapter stays thin
(request/response translation only) and so the domain rules can be unit
tested and reused without importing FastAPI at all.
"""
