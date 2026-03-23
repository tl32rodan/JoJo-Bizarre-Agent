---
name: design_review
description: Code and architecture review using SOLID and clean design principles.
---

## Design Review Checklist

### SOLID Principles

- **S — Single Responsibility**: Does each class/module have one reason to change?
- **O — Open/Closed**: Can behavior be extended without modifying existing code?
- **L — Liskov Substitution**: Can subtypes replace their base types transparently?
- **I — Interface Segregation**: Are interfaces focused (no unused methods)?
- **D — Dependency Inversion**: Do modules depend on abstractions, not concretions?

### Clean Code

- **Naming**: Are names descriptive and consistent?
- **Functions**: Are they short, focused, and at one level of abstraction?
- **DRY**: Is there unnecessary duplication?
- **Error handling**: Are errors handled explicitly, not silently swallowed?
- **Comments**: Does the code need comments, or is it self-explanatory?

### Architecture

- **Separation of concerns**: Are layers distinct (I/O, business logic, data)?
- **Coupling**: Can components change independently?
- **Cohesion**: Do related things live together?
- **Testability**: Can each component be tested in isolation?

### Security

- **Input validation**: Is user input validated at boundaries?
- **Injection**: Are queries parameterized? Are commands escaped?
- **Secrets**: Are credentials in env vars, not in code?
- **Dependencies**: Are third-party packages up to date?

### read_file — Read code under review
### search — Search for patterns and anti-patterns across the codebase
### run_terminal_command — Run linters, type checkers, security scanners
