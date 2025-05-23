# Instructions

### ✅ General Guidelines
- **Only modify related code**: Never alter unrelated code. Keep changes scoped to the specific user request.
- **Code quality**: Write clean, modular, and production-grade Python code using industry best practices.
- **Object-Oriented Design**: Use OOP principles where applicable to ensure encapsulation, modularity, and reusability.
- **Type hints**: Use Python type hints for all function arguments and return types.
- **Error handling**: Add robust error handling with meaningful debug prints to help trace issues.
- **Cross-platform compatibility**: Ensure code works consistently on both Windows and Linux platforms.

### 🧱 Code Structure & Best Practices
- **Component-based design**: Break the application into logical components. Don’t put unrelated logic in the same file.
- **Organized project hierarchy**: Maintain a clean project structure with appropriate folders like `core/`, `utils/`, `cli/`, `gui/`, `services/`, `models/`, etc.
- **Multifile organization**: If a file becomes too long or holds unrelated logic, split it into smaller, focused modules.
- **Proper indentation**: Match indentation with the surrounding code (e.g., methods inside classes should follow class indentation).
- **Avoid duplication**: Reuse existing code wherever possible; don’t rewrite or duplicate logic.
- **Imports**: Keep all import statements at the top of each file—never place them inside functions or methods.

### 📃 Comments & Documentation
- **Docstrings**: Add clear docstrings to all functions and classes explaining their purpose, parameters, and return values.
- **Inline comments**: Use comments to explain complex or non-obvious logic.

### 🛠️ Fixing / Updating Code
- **Change format**: Wrap all code changes using the following format:
  ```python
  # -------------- Fix Start for this method(method_name)-----------
  ...updated code...
  # -------------- Fix Ended for this method(method_name)-----------
  ```

### 🧠 Communication
- **Ask when unsure**: If requirements are unclear or ambiguous, ask for clarification before proceeding.
- **Concise responses**: Keep responses short and focused. Avoid unnecessary explanations or code unless requested.
- **Complete solutions**: If the fix/update is small, provide the full method/function code block.

### 🧑‍💻 Industry Best Practices
- Follow **PEP8** for formatting and naming conventions.
- Apply **OOP**, **type hints**, **context managers**, and **design patterns** where appropriate.
- Gracefully handle **exceptions**, never silently ignore them.
- Validate all **user inputs** and external system interactions.
- Prefer **logging** over print statements for debugging and maintainability.
- Ensure code is **scalable**, **testable**, and **maintainable** by design.
