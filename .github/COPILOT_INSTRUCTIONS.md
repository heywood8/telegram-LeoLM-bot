# Copilot Instructions

- Do not chain commands with pipes (`|`). Execute each command separately to avoid extra approval prompts.
- Prefer direct `grep` without regex patterns when possible; complex regex or piped usage can trigger command approval requests repeatedly.
- When filtering command output, run the primary command first, review the results, and then run a follow-up command for filtering if necessary.
