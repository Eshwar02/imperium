# Attributions

## Design reference: Visual Studio Code

The Imperium IDE frontend reimplements a VS Code-style workbench (activity bar, side bar,
editor tabs, panels, command palette, status bar, context menus, etc.) in React.

The **look and interaction behaviour** are inspired by Microsoft Visual Studio Code
(https://github.com/microsoft/vscode), which is available under the MIT License.

**No VS Code source code is copied into this project.** Every component here is an
independent React/TypeScript implementation. VS Code is used solely as a design reference.
No VS Code trademarks, logos, or branding are used.

## Monaco Editor

The code editor uses [`monaco-editor`](https://github.com/microsoft/monaco-editor) and
[`@monaco-editor/react`](https://github.com/suren-atoyan/monaco-react), both under the
MIT License. See their respective license files distributed with the npm packages.

## Microsoft VS Code — MIT License (for reference)

> Copyright (c) 2015 - present Microsoft Corporation
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this
> software and associated documentation files (the "Software"), to deal in the Software
> without restriction, including without limitation the rights to use, copy, modify, merge,
> publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
> to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or
> substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
> INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
> PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
> FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
> OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
> DEALINGS IN THE SOFTWARE.
