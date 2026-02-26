# Code Stats (# code-stats)

Run code-size and static-analysis tools and report the results. Execute from the workspace root.

---

## Commands to run (in order)

1. **Lines of code (cloc)**  
   ```bash
   cloc .
   ```

2. **Cyclomatic complexity (radon)**  
   ```bash
   radon cc src/ -s -a
   ```

3. **Maintainability index (radon)**  
   ```bash
   radon mi src/
   ```

4. **Dead code (vulture)**  
   ```bash
   vulture src/
   ```

5. **Complexity & metrics (lizard)**  
   ```bash
   lizard src/ -l python
   ```

6. **Static analysis (prospector)**  
   ```bash
   prospector src/
   ```

---

## Report back

- Paste or summarize the output of each command.
- Note any high-complexity or low-maintainability modules, vulture findings, lizard complexity/loc highlights, and prospector issues worth addressing.
- Do not modify the codebase unless the user asks; this is a reporting-only command.
