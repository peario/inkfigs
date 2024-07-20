import logging
import os
import platform
import re
import subprocess
import textwrap
import warnings
from pathlib import Path
from shutil import copy

import click
import pyperclip
from appdirs import user_config_dir
from daemonize import Daemonize

from .picker import pick

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
log = logging.getLogger("inkfigs")

DAEMON_PID = "/tmp/inkfigs.pid"


def inkscape(path: Path):
    with warnings.catch_warnings():
        # leaving a subprocess running after interpreter exit raises a
        # warning in Python3.7+
        warnings.simplefilter("ignore", ResourceWarning)
        subprocess.Popen(["inkscape", str(path)])


def indent(text: str, indentation=0):
    lines = text.split("\n")
    return "\n".join(" " * indentation + line for line in lines)


def beautify(name):
    return name.replace("_", " ").replace("-", " ").title()


def latex_template(name, title):
    return "\n".join(
        (
            r"\begin{figure}[ht]",
            r"    \centering",
            rf"    \incfig{{{name}}}",
            rf"    \caption{{{title}}}",
            rf"    \label{{fig:{name}}}",
            r"\end{figure}",
        )
    )


# From https://stackoverflow.com/a/67692
def import_file(name: str, path: Path):
    import importlib.util as util

    spec = util.spec_from_file_location(name, path)

    # Make sure that before trying to run anything
    # that the function actually exists
    if spec and spec.loader is not None:
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    else:
        log.error(f"Attempted to run {name} from {str(path)} which does not exist!")


# Load user config
user_dir = Path(user_config_dir("inkfigs", "Castel"))

if not user_dir.is_dir():
    user_dir.mkdir()

roots_file = user_dir / "roots"
template = user_dir / "template.svg"
config = user_dir / "config.py"

if not roots_file.is_file():
    roots_file.touch()

if not template.is_file():
    source = str(Path(__file__).parent / "template.svg")
    destination = str(template)
    copy(source, destination)

if config.exists():
    config_module = import_file("config", config)

    # Before assigning a function of an external py file,
    # check that both the file and function exists.
    if config_module and config_module.latex_template is not None:
        latex_template = config_module.latex_template


def add_root(path: Path):
    filepath = str(path)
    roots = get_roots()
    if filepath in roots:
        return None

    roots.append(filepath)
    roots_file.write_text("\n".join(roots))


def get_roots():
    return [root for root in roots_file.read_text().split("\n") if root != ""]


@click.group()
def cli():
    pass


@cli.command()
@click.option("--daemon/--no-daemon", default=True, help="Monitor figures as a daemon")
@click.option("--stop", is_flag=True, type=bool, help="Stop running daemon")
def watch(daemon: bool, stop: bool):
    """Monitor figures."""
    if stop and os.path.exists(DAEMON_PID):
        try:
            os.remove(DAEMON_PID)
            log.info("Removed the monitor daemon.")
        except FileNotFoundError:
            log.error(f"`{DAEMON_PID}` not found.")
        except PermissionError:
            log.error(f"Missing permission to delete `{DAEMON_PID}`.")
        return
    elif stop and not os.path.exists(DAEMON_PID):
        log.warn("No daemon is currently active.")

    watcher_cmd = inotify_monitor if platform.system() == "Linux" else fswatch_monitor

    if daemon:
        monitor_d = Daemonize(
            app="inkfigs", pid=DAEMON_PID, action=watcher_cmd, logger=log
        )
        log.info("Monitoring figures.")
        monitor_d.start()
    else:
        log.info("Monitoring figures.")
        watcher_cmd()


def recompile_figure(path: str):
    filepath = Path(path)
    # A file has changed
    if filepath.suffix != ".svg":
        log.debug(f"File changed, but is not of type svg; Type: {filepath.suffix}")
        return

    log.info(f"Recompiling {filepath}")

    pdf_path = filepath.parent / (filepath.stem + ".pdf")
    name = filepath.stem

    inkscape_version = subprocess.check_output(
        ["inkscape", "--version"], universal_newlines=True
    )
    log.debug(inkscape_version)

    # Convert
    # - 'Inkscape 0.92.4 (unknown)' to [0, 92, 4]
    # - 'Inkscape 1.1-dev (3a9df5bcce, 2020-03-18)' to [1, 1]
    # - 'Inkscape 1.0rc1' to [1, 0]
    inkscape_version = re.findall(r"[0-9.]+", inkscape_version)[0]
    inkscape_semver = [int(part) for part in inkscape_version.split(".")]

    # Right-pad the array with zeros (so [1, 1] becomes [1, 1, 0])
    inkscape_semver = inkscape_semver + [0] * (3 - len(inkscape_semver))

    # Tuple comparison is like version comparison
    if inkscape_semver < [1, 0, 0]:
        command = [
            "inkscape",
            "--export-area-page",
            "--export-dpi",
            "300",
            "--export-pdf",
            pdf_path,
            "--export-latex",
            filepath,
        ]
    else:
        command = [
            "inkscape",
            filepath,
            "--export-area-page",
            "--export-dpi",
            "300",
            "--export-type=pdf",
            "--export-latex",
            "--export-filename",
            pdf_path,
        ]

    log.debug("Running command:")
    log.debug(textwrap.indent(" ".join(str(e) for e in command), "    "))

    # Recompile the svg file
    result = subprocess.run(command)

    if result.returncode != 0:
        log.error(f"Return code {result.returncode}")
    else:
        log.debug("Command succeeded")

    # Copy the LaTeX code to include the file to the clipboard
    template = latex_template(name, beautify(name))
    pyperclip.copy(template)
    log.debug("Copying LaTeX template:")
    log.debug(textwrap.indent(template, "    "))


def inotify_monitor():
    import inotify.adapters
    from inotify.constants import IN_CLOSE_WRITE

    while True:
        roots = get_roots()

        # Watch the file with contains the paths to watch
        # When this file changes, we update the watches.
        i = inotify.adapters.Inotify()
        i.add_watch(str(roots_file), mask=IN_CLOSE_WRITE)

        # Watch the actual figure directories
        log.info("Monitoring folders: " + ", ".join(get_roots()))
        for root in roots:
            try:
                i.add_watch(root, mask=IN_CLOSE_WRITE)
            except Exception:
                log.debug(f"Could not add root {root}")

        for event in i.event_gen(yield_nones=False):
            (_, _, path, filename) = event

            # If the file containing figure roots has changes, update the
            # watches
            if path == str(roots_file):
                log.info("The roots file has been updated. Updating monitors.")
                for root in roots:
                    try:
                        i.remove_watch(root)
                        log.debug(f"Removed root {root}")
                    except Exception:
                        log.debug(f"Could not remove root {root}")
                # Break out of the loop, setting up new watches.
                break

            # A file has changed
            path = Path(path) / filename
            recompile_figure(path)


def fswatch_monitor():
    while True:
        roots = get_roots()
        log.info("Monitoring folders: " + ", ".join(roots))

        # Monitor directories containing figures and the config directory.
        #   The config directory contains the roots file where folders to monitor is defined.
        #   If changes in the config directory is detected then restart the monitor.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            p = subprocess.Popen(
                ["fswatch", *roots, str(user_dir)],
                stdout=subprocess.PIPE,
                universal_newlines=True,
            )

        while True:
            # Only attempt recompiling if filepath is not None
            if p.stdout is not None:
                filepath = p.stdout.readline().strip()

                # If the file containing figure roots has changes, update the watches
                if filepath == str(roots_file):
                    log.info("The roots file has been updated. Updating monitors.")
                    p.terminate()
                    log.debug("Removed main monitor %s")
                    break

                recompile_figure(filepath)


@cli.command(
    no_args_is_help=True,
    short_help="Creates a figure.",
    help="Creates a figure at ROOT with the name of TITLE.",
)
@click.argument("title", required=True, type=str)
@click.argument(
    "root",
    default=os.getcwd(),
    required=False,
    type=click.Path(exists=False, file_okay=False, dir_okay=True),
)
def create(title: str, root: Path):
    title = title.strip()
    file_name = title.replace(" ", "-").lower() + ".svg"
    figures = Path(root).absolute()
    if not figures.exists():
        figures.mkdir()

    figure_path = figures / file_name

    # If a file with this name already exists, append a '2'.
    if figure_path.exists():
        print(title + " 2")
        return

    copy(str(template), str(figure_path))
    add_root(figures)
    inkscape(figure_path)

    # Print the code for including the figure to stdout.
    # Copy the indentation of the input.
    leading_spaces = len(title) - len(title.lstrip())
    print(indent(latex_template(figure_path.stem, title), indentation=leading_spaces))


@cli.command(
    short_help="Edits a figure.", help="Opens a picker at ROOT for editing figures."
)
@click.argument(
    "root",
    default=os.getcwd(),
    required=False,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
def edit(root: Path):
    figures = Path(root).absolute()

    # Find svg files and sort them
    files = figures.glob("*.svg")
    files = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

    # Open a selection dialog using a gui picker like rofi
    names = [beautify(f.stem) for f in files]
    _, index, selected = pick(names)
    if selected:
        path = files[index]
        add_root(figures)
        inkscape(path)

        # Copy the LaTeX code to include the file to the clipboard
        template = latex_template(path.stem, beautify(path.stem))
        pyperclip.copy(template)
        log.debug("Copying LaTeX template:")
        log.debug(textwrap.indent(template, "    "))


if __name__ == "__main__":
    cli()
