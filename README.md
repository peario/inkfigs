# Inkfigs

> An Inkscape figure manager
>
> Manage figures for LaTeX a bit easier with this script.

_This project is a fork and an attempt to update and revamp [gillescastel/inkscape-figures](https://github.com/gillescastel/inkscape-figures)._

## Requirements

You need Python >= 3.12, as well as a picker. Current supported pickers are:

- [rofi](https://github.com/davatorium/rofi) on Linux systems
- [choose](https://github.com/chipsenkbeil/choose) on MacOS

## Installation

As of right now during the initial reconstruction, no install instructions will be written.
They will be added once the planned features have been implemented, or most of them at least.

This package currently works on Linux and MacOS.
If you're interested in porting it to Windows, feel free to make a pull request.

## Setup

Add the following code to the preamble of your LaTeX document.

```tex
\usepackage{import}
\usepackage{pdfpages}
\usepackage{transparent}
\usepackage{xcolor}

\newcommand{\incfig}[2][1]{%
    \def\svgwidth{#1\columnwidth}
    \import{./figures/}{#2.pdf_tex}
}

\pdfsuppresswarningpagegroup=1
```

This defines a command `\incfig` which can be used to include Inkscape figures.
By default, `\incfig{figure-name}` make the figure as wide as the page.
But it's also possible to change the width by providing an optional argument: `\incfig[0.3]{figure-name}`.

The settings above assume the following LaTeX project structure:

```bash
root/
 ├──figures/
 │   ├──figure1.pdf_tex
 │   ├──figure1.svg
 │   ├──figure1.pdf
 │   ├──figure2.pdf_tex
 │   ├──figure2.svg
 │   └──figure2.pdf
 └──master.tex
```

## Usage

- Watch for figures: `inkfigs watch`.
- Creating a figure: `inkfigs create 'title'`.
  This uses `~/.config/inkscape-figures/template.svg` as a template.
- Creating a figure in a specific directory: `inkfigs create 'title' path/to/figures/`.
- Select figure and edit it: `inkfigs edit`.
- Select figure in a specific directory and edit it: `inkfigs edit path/to/figures/`.

## Vim mappings

This assumes that you use [VimTeX](https://github.com/lervag/vimtex).

```vim
inoremap <C-f> <Esc>: silent exec '.!inkfigs create "'.getline('.').'" "'.b:vimtex.root.'/figures/"'<CR><CR>:w<CR>
nnoremap <C-f> : silent exec '!inkfigs edit "'.b:vimtex.root.'/figures/" > /dev/null 2>&1 &'<CR><CR>:redraw!<CR>
```

First, run `inkfigs watch` in a terminal to setup the file watcher.
Now, to add a figure, type the title on a new line, and press <kbd>Ctrl+F</kbd> in insert mode.
This does the following:

1. Find the directory where figures should be saved depending on which file you're editing and where the main LaTeX file is located, using `b:vimtex.root`.
2. Check if there exists a figure with the same name. If there exists one, do nothing; if not, go on.
3. Copy the figure template to the directory containing the figures.
4. In Vim: replace the current line – the line containing figure title – with the LaTeX code for including the figure.
5. Open the newly created figure in Inkscape.
6. Set up a file watcher such that whenever the figure is saved as an svg file by pressing <kbd>Ctrl + S</kbd>, it also gets saved as pdf+LaTeX.

To edit figures, press <kbd>Ctrl+F</kbd> in command mode, and a fuzzy search selection dialog will appear allowing you to select the figure you want to edit.

## Configuration

You can change the default LaTeX template by creating `~/.config/inkfigs/config.py` and adding something along the lines of the following:

```python
def latex_template(name, title):
    return '\n'.join((r"\begin{figure}[ht]",
                      r"    This is a custom LaTeX template!",
                      r"    \centering",
                      rf"    \incfig[1]{{{name}}}",
                      rf"    \caption{{{title}}}",
                      rf"    \label{{fig:{name}}}",
                      r"\end{figure}"))
```

## Planned features

While most (if not all) of the original features should be functional.
Some additional features or aspects of the project that's being considered:

- [ ] Affecting everyone
  - [ ] Rewrite and reformat README.md
  - [ ] Add proper setup instructions for both Vim and Neovim (using Lua)
  - [ ] Setup Nix for installing
  - [ ] Create template for issues/bugs
- [ ] Affecting developers
  - [ ] Add a CONTRIBUTE.md ?
  - [ ] Setup Nix for shell env ?
  - [ ] Create tests, especially for the daemon
  - [ ] Setup Git Actions or somehow automate dependency updates
  - [ ] Create template for PR
- [ ] Affecting users
  - [ ] Write better descriptions of commands, flags and options
  - [ ] For daemon (watch), implement a hot reload menu?
        (like Node.js Nodemon or Vite)
