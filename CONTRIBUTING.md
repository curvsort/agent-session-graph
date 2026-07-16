# Contributing to Agent Session Graph

Thanks for your interest in contributing! We welcome bug reports, feature proposals, new anomaly detectors, and documentation improvements.

Please note that this project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Dev Environment Setup

1. **Clone and activate the virtual environment:**
   ```bash
   git clone <repo-url>
   cd agent-session-graph
   source venv/bin/activate
   ```

2. **Install dependencies** (if adding new ones):
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables** (copy `.env.example` to `.env` and fill in values)

## Running Tests

We have **83 comprehensive tests** covering all major functionality. See [TEST_SUMMARY.md](TEST_SUMMARY.md) for detailed coverage.

```bash
# Run all tests (no AWS needed - uses in-memory storage)
cd agent-session-graph
make test-verbose

# Or with pytest directly
python3 -m pytest tests/ -v

# Run specific test category
python3 -m pytest tests/test_context_tracking.py -v    # Context tracking
python3 -m pytest tests/test_advanced_features.py -v   # Advanced features
python3 -m pytest tests/test_edge_cases.py -v          # Edge cases
python3 -m pytest tests/test_detection_integration.py -v  # Detector tests
python3 -m pytest tests/test_integration.py -v         # Integration tests
python3 -m pytest tests/test_storage.py -v             # Storage backends

# Run with coverage report
make test-coverage
```

**Test Coverage:**
- Context tracking (10 tests) - ContextDiffEngine, instruction loss detection
- Advanced features (8 tests) - Session boundaries, profile switches, deep delegation
- Integration tests (11 tests) - Full pipeline scenarios
- Reference detectors (7 tests) - Anomaly detection with positive/negative cases
- Edge cases (13 tests) - Malformed inputs, missing data
- Storage backends (18 tests) - NullStorage and InMemoryStorage
- Examples (4 tests) - Verify all examples run without errors
- Schemas (4 tests) - Pydantic model validation
- Session builder (3 tests) - State management
- Session reconstructor (4 tests) - High-level API

## Code Style

- **Formatting:** Run `black .` before committing
- **Type hints:** Required for all function signatures
- **Imports:** Pydantic v2 models live in `shared/schemas/`
- **Docs:** Add docstrings for non-obvious logic

## Proposing Changes

- **Bug reports:** Open an issue with steps to reproduce
- **New features:** Describe the use case and proposed approach in an issue first
- **New anomaly detectors:** See `analysis/anomaly_detector.py` for the pattern — detection rules should be cheap (hash-based), LLM reasoning runs only on confirmed findings
- **Pull requests:** Keep them focused. Reference any related issues.

Questions? Open an issue — we're happy to help!
