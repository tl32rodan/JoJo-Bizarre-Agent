---
name: tdd
description: Test-Driven Development — write tests first, then implement.
---

## TDD Cycle

### Red → Green → Refactor

1. **Red**: Write a failing test that defines the desired behavior
   - Test should be specific and focused on one behavior
   - Run it — confirm it fails for the right reason
   - If it passes without code changes, the test is wrong

2. **Green**: Write the minimum code to make the test pass
   - Don't over-engineer — just enough to pass
   - Don't write code for future requirements
   - Run the test — confirm it passes

3. **Refactor**: Clean up while keeping tests green
   - Remove duplication
   - Improve naming and structure
   - Run all tests after each change — must stay green

### Guidelines

- Tests document behavior, not implementation
- One assertion per test (when practical)
- Test edge cases: empty inputs, boundaries, error conditions
- Test names should describe the scenario: `test_<action>_when_<condition>_then_<expected>`

### read_file — Read existing tests to understand conventions
### run_terminal_command — Run tests to verify red/green cycle
### search — Find existing test patterns to follow
