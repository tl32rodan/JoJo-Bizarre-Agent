---
name: debugging
description: Systematic debugging methodology — reproduce, isolate, fix, verify.
---

## Debugging Playbook

Follow these steps in order:

### 1. Reproduce
- Confirm the bug exists with a concrete reproduction case
- Document exact steps, inputs, and observed vs expected behavior
- If intermittent, identify conditions that increase likelihood

### 2. Isolate
- Narrow down the scope: which module, function, or line?
- Use binary search (comment out halves) to find the source
- Check recent changes (git log/diff) for likely culprits
- Read error messages and stack traces carefully

### 3. Fix
- Understand the root cause before changing code
- Make the minimal change that fixes the issue
- Avoid "shotgun debugging" (random changes hoping something works)
- Consider if the fix introduces new edge cases

### 4. Verify
- Run the original reproduction case — does it pass?
- Run the full test suite — no regressions?
- Add a test for this specific bug to prevent recurrence
- Review the fix for clarity and correctness

### read_file — Read source code to understand the buggy area
### search — Search for related code patterns and usages
### run_terminal_command — Run tests to reproduce and verify the fix
