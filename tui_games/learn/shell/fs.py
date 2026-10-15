"""An in-memory filesystem for Terminal Caverns. Nothing here ever touches the real disk, network,
or a process - that is a hard safety rule for this repo (missions must be solvable, and safe, offline).
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field


class FSError(Exception):
    """Raised for user-facing filesystem mistakes (not found, not a directory, ...)."""


@dataclass
class Node:
    name: str
    is_dir: bool
    content: str = ""
    mode: int = 0o644
    children: dict[str, "Node"] = field(default_factory=dict)

    def clone(self) -> "Node":
        n = Node(self.name, self.is_dir, self.content, self.mode)
        n.children = {k: v.clone() for k, v in self.children.items()}
        return n


class FS:
    """cwd and paths are lists of path components, rooted at an implicit '/'."""

    def __init__(self) -> None:
        self.root = Node("/", True, mode=0o755)
        self.env: dict[str, str] = {"HOME": "/home/player", "SHELL": "/bin/sh"}
        self._mkdirs(["home", "player"])
        self.cwd: list[str] = ["home", "player"]
        self.env["PWD"] = self.cwd_str()

    # ---- path helpers --------------------------------------------------
    def _mkdirs(self, parts: list[str]) -> Node:
        node = self.root
        for p in parts:
            node = node.children.setdefault(p, Node(p, True, mode=0o755))
        return node

    def cwd_str(self) -> str:
        return self.path_str(self.cwd)

    @staticmethod
    def path_str(parts: list[str]) -> str:
        return "/" + "/".join(parts)

    def resolve_parts(self, path: str) -> list[str]:
        if not path:
            path = "."
        if path == "~" or path.startswith("~/"):
            path = self.env["HOME"] + path[1:]
        parts = [] if path.startswith("/") else list(self.cwd)
        for comp in path.split("/"):
            if comp in ("", "."):
                continue
            if comp == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(comp)
        return parts

    def get(self, path: str) -> Node | None:
        node = self.root
        for p in self.resolve_parts(path):
            if not node.is_dir or p not in node.children:
                return None
            node = node.children[p]
        return node

    def parent_of(self, path: str) -> tuple[Node | None, str]:
        parts = self.resolve_parts(path)
        if not parts:
            return None, ""
        *parent_parts, name = parts
        node = self.root
        for p in parent_parts:
            if not node.is_dir or p not in node.children:
                return None, name
            node = node.children[p]
        return node, name

    # ---- mutating ops used by commands.py ------------------------------
    def chdir(self, path: str) -> None:
        node = self.get(path)
        if node is None:
            raise FSError(f"cd: {path}: No such file or directory")
        if not node.is_dir:
            raise FSError(f"cd: {path}: Not a directory")
        self.cwd = self.resolve_parts(path)
        self.env["PWD"] = self.cwd_str()

    def mkdir(self, path: str, parents: bool) -> None:
        parts = self.resolve_parts(path)
        if not parts:
            raise FSError("mkdir: cannot create /")
        node = self.root
        for i, p in enumerate(parts):
            last = i == len(parts) - 1
            if p in node.children:
                if last and not parents:
                    raise FSError(f"mkdir: cannot create directory '{path}': File exists")
                node = node.children[p]
                if not node.is_dir:
                    raise FSError(f"mkdir: cannot create directory '{path}': Not a directory")
            else:
                if not last and not parents:
                    raise FSError(f"mkdir: cannot create directory '{path}': No such file or directory")
                node = node.children.setdefault(p, Node(p, True, mode=0o755))

    def touch(self, path: str) -> None:
        parent, name = self.parent_of(path)
        if parent is None or not parent.is_dir:
            raise FSError(f"touch: cannot touch '{path}': No such file or directory")
        if name not in parent.children:
            parent.children[name] = Node(name, False, mode=0o644)

    def write(self, path: str, text: str, append: bool) -> None:
        parent, name = self.parent_of(path)
        if parent is None or not parent.is_dir:
            raise FSError(f"{path}: No such file or directory")
        node = parent.children.get(name)
        if node is None:
            node = parent.children[name] = Node(name, False, mode=0o644)
        elif node.is_dir:
            raise FSError(f"{path}: Is a directory")
        node.content = (node.content + text) if append else text

    def remove(self, path: str, recursive: bool) -> None:
        parent, name = self.parent_of(path)
        if parent is None or name not in parent.children:
            raise FSError(f"rm: cannot remove '{path}': No such file or directory")
        node = parent.children[name]
        if node.is_dir and not recursive:
            raise FSError(f"rm: cannot remove '{path}': Is a directory")
        del parent.children[name]

    def copy(self, src: str, dest: str) -> None:
        node = self.get(src)
        if node is None:
            raise FSError(f"cp: cannot stat '{src}': No such file or directory")
        dparent, dname = self.parent_of(dest)
        if dparent is None:
            raise FSError(f"cp: '{dest}': No such file or directory")
        dest_node = dparent.children.get(dname)
        if dest_node is not None and dest_node.is_dir:
            dparent = dest_node
            dname = node.name
        clone = node.clone()
        clone.name = dname
        dparent.children[dname] = clone

    def move(self, src: str, dest: str) -> None:
        sparent, sname = self.parent_of(src)
        if sparent is None or sname not in sparent.children:
            raise FSError(f"mv: cannot stat '{src}': No such file or directory")
        node = sparent.children[sname]
        dparent, dname = self.parent_of(dest)
        if dparent is None:
            raise FSError(f"mv: '{dest}': No such file or directory")
        dest_node = dparent.children.get(dname)
        if dest_node is not None and dest_node.is_dir:
            dparent = dest_node
            dname = node.name
        del sparent.children[sname]
        node.name = dname
        dparent.children[dname] = node

    def chmod(self, mode_octal: str, path: str) -> None:
        node = self.get(path)
        if node is None:
            raise FSError(f"chmod: cannot access '{path}': No such file or directory")
        try:
            node.mode = int(mode_octal, 8)
        except ValueError:
            raise FSError(f"chmod: invalid mode: '{mode_octal}'")

    # ---- globbing -------------------------------------------------------
    def expand_glob(self, pattern: str) -> list[str]:
        if "*" not in pattern and "?" not in pattern:
            return [pattern]
        if "/" in pattern:
            dirpart, leaf = pattern.rsplit("/", 1)
            parent = self.get(dirpart or "/")
        else:
            dirpart, leaf = "", pattern
            parent = self.get(".")
        if parent is None or not parent.is_dir:
            return [pattern]
        names = sorted(n for n in parent.children if fnmatch.fnmatch(n, leaf))
        if not names:
            return [pattern]
        return [f"{dirpart}/{n}" if dirpart else n for n in names]
