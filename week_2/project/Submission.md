### Submission Info -

## Agent Features

- **Split-Panel TUI and great UI**: Has split panel TUI, one for chat and other for AI thinking.

- **Hallucinations Countered**: Hallucinations from web searching or web fetching have been countered by giving special instructions to the AI to prevent hallucination.

- **Summary Generation**: Summarizes messages when they reach the memory limit or if the user instructs using summary shortcut.

- **Response Interuptions Handling**: Responses by AI if interrupted in between by user by giving another prompt are automatically stopped and next response is generated.

- **Error Handling**: Error handling is applied everywhere in the code using try-except blocks to prevent unwanted crashes and multiple testings were done to help.

- **Clean Exit**: The agent properly writes an exit message when the user uses exit shortcut.

- **Shortcuts**: Agent has four custom shortcuts-

    1) **Ctrl + q**: Exit.

    2) **Ctrl + l**: `Clear User-Ai Chat Panel.

    3) **Ctrl + k**: to Clear AI Thinking Panel.

    4) **Ctrl + s**: Generate Summary.