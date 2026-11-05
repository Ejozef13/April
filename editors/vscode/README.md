# APRIL VS Code companion preview

This dependency-free extension checks syntax using APRIL's local Python parser,
opens a deeper file review in the existing UI, and offers an explicit IDE debug
command. It never accepts arbitrary model-generated launch commands.

For a development preview, open this folder in VS Code and run
`code --extensionDevelopmentPath=/absolute/path/to/April/editors/vscode`.
Start APRIL separately. Use the command palette:

- **APRIL: Check Python Syntax** — actual saved-file parse errors appear as
  diagnostics at their line/column.
- **APRIL: Review Current Python File** — opens deeper local-model review.
- **APRIL: Run Current Python File in Debugger** — requires the Python Debugger
  extension (ms-python.debugpy), shows the actual file for explicit confirmation,
  then invokes VS Code's debug API. This uses your normal desktop permissions.
  It is distinct from APRIL's constrained Docker execution option.

Only saved Python files inside Documents/aprilfiles are accepted by default.
Symlinks resolving outside the root are rejected. If you change the extension's
approvedRoot, update APRIL's debug_project_root to match. Optional checkOnSave is
off by default. No screen is captured or shared by this extension.

JavaScript syntax was checked in the cloud. Actual VS Code diagnostics/debugger
integration must be accepted on the desktop; it is not claimed as IDE-tested.
The initial supported language is Python. Runtime errors are not inferred from a
successful syntax check, and code changes are never applied automatically.
