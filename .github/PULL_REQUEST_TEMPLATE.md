## Description

Please include a summary of the changes and the related issue.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test coverage improvement

## Checklist

- [ ] My code follows the style guidelines of this project (runs `ruff check`)
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally (`pytest tests/ --tb=short -q`)
- [ ] I have updated the documentation accordingly
- [ ] I have added an entry to `CHANGELOG.md` (if applicable)

## Testing

Describe the testing you've done:

```bash
# Run linting
ruff check src/ tests/

# Run tests
pytest tests/ --tb=short -q

# Run with coverage
pytest tests/ --cov=dochris --cov-report=term
```

## Additional Context

Any additional information that would help reviewers understand this PR.
