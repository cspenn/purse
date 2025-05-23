**Sparse Priming Representation (SPR): Python 3.11+ Best Practices**

1. **Core Mastery**:  
   - Data types, control flow, functions, OOP, functional paradigms (decorators, generators, comprehensions).  
   - Context managers (`with`), exception handling, algorithmic efficiency (time/space complexity).  
   - Standard libraries: `os`, `subprocess`, `re`, `tomllib`, `contextlib.chdir`, `collections.abc`.

2. **Performance Optimization**:  
   - Profiling (cProfile, line_profiler), Cython/Numba acceleration, memory-efficient structures (`dataclass(slots=True)`).  
   - Lazy loading, connection caching (`lru_cache`), recursion inlining (Python 3.11 zero-cost exceptions).

3. **Code Quality**:  
   - PEP 8 compliance, type hints (mandatory), linters (Ruff, pylint), formatters (black).  
   - Pre-commit hooks, docstrings, DRY refactoring, dead code removal.

4. **Frameworks & Libraries**:  
   - Web: FastAPI (async, type-driven), Django (ORM), Flask (microservices).  
   - Data Science: NumPy (NDArray typing), Pandas, TensorFlow/Keras, Scikit-learn.  
   - Async I/O: HTTPX, asyncio (TaskGroup, timeout).

5. **Domain-Specific Practices**:  
   - Serverless: AWS Lambda (layers, memory config, async I/O), least-privilege IAM.  
   - ML Pipelines: Tensor shape annotations, GPU memory isolation, reproducible environments (Poetry, Conda-lock).  
   - Security: HTTPS enforcement, input sanitization, FIPS crypto, SAST scanning (Bandit).

6. **Python 3.11+ Features**:  
   - Structural pattern matching (`match-case`), exception groups (`except*`), TOML parsing.  
   - Faster CPython (inlined calls, adaptive interpreter), frozen imports, strict var typing.

7. **Anti-Patterns**:  
   - Mutable defaults, bare `except`, circular imports, global overuse, magic numbers.  
   - Spaghetti code, hardcoded secrets, unvalidated inputs, debugger remnants in prod.

8. **Tooling**:  
   - IDE: VS Code + Pylance (type-checking, isort).  
   - CI/CD: GitHub Actions matrix builds, Poetry/PDM dependency isolation.  
   - Static Analysis: mypy (type), Bandit (security), pytest coverage.

9. **Design Principles**:  
   - Resource safety (`with`, `finally`), lazy evaluation, stateless serverless functions.  
   - Least surprise (explicit over implicit), reproducibility (dependency pinning).

10. **Evolution**:  
    - Migrate from "dead batteries" (deprecated modules), adopt C11 toolchains for extensions.  
    - Leverage adaptive interpreter (PEP 659), specialize bytecode optimizations.

**Associations**:  
- Type hints → robustness, static analysis, FastAPI auto-docs.  
- Asyncio → serverless cost reduction, parallel I/O.  
- Dataclasses → memory efficiency → high-throughput systems.  
- Structural pattern matching → cleaner state machines.  
- Zero-cost exceptions → performance-critical error handling.