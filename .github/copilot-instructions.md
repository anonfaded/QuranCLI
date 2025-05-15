# QuranCLI Copilot Instructions

- **Never alter unrelated code**: Only modify code directly related to the user’s request.
- **Code quality**: Always write clean, simple, modular, and production-quality Python code.
- **Comments & docstrings**: Add clear comments and docstrings to all functions, classes, and complex logic.
- **File organization**: If a file grows too long, create a new file/module instead of extending it further.
- **Best practices**: Use Python best practices for style, error handling, and design patterns.
- **Change format**: When fixing or updating a method, use this format:

# -------------- Fix Start for this method(method_name)-----------
...changes here...
# -------------- Fix Ended for this method------------------------


- **Ask for clarification**: If requirements are unclear, ask the user before proceeding.
- **No buggy code**: Ensure all code is correct, tested, and free of obvious bugs.
- **Keep responses concise**: Avoid unnecessary explanations or code.
- **Complete**: If methods are not too long then give complete method codeblocks with fixes.
- **Multiplatform Support**: Our app is for windows and linux systems so always handle cases for both together in a very robust way.