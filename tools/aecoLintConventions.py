#!/usr/bin/env python3
#
# Copyright 2026 AECO
#
# © AECO — all rights reserved. See the NOTICE file.
#
"""aecoLintConventions — hold the OpenUSD library canon by CI, not by discipline.

This linter enforces, mechanically, the "house style" the AECO processing stack
adopts from OpenUSD (plan §3, design §4.8): every aeco library is the
``kind``/``trace`` exemplar shape, its public headers follow pxr naming and
namespace conventions, and processing repos never author schemas or bare
error-path output. Practices held by will decay; these are held here.

Usage::

    aecoLintConventions.py <repo-root> [--lib <path>]*

``<repo-root>`` is the root of a repo to lint (this toolchain repo, or a
consumer such as aeco-core). Without ``--lib`` the linter discovers every
library under ``aeco/`` by walking for ``CMakeLists.txt`` files that invoke
``pxr_library(...)`` (case-insensitively — CMake command names are).
Discovery failures are loud: a library-shaped dir that yields no parse is a
LIB-CANON finding, never silence. ``--lib`` restricts the run to the given
library directories (each relative to the repo root or absolute); repeatable.

Grep-class C++ rules (DIAG, SCOPE, the class scan) run on a buffer lexed in
the compiler's translation-phase order — backslash-newline splicing first,
then comment/string/raw-string removal — so legal formatting (split calls,
spliced identifiers, raw literals) can neither evade nor false-positive them.

Exit status: ``0`` if clean, ``1`` if any finding was reported. Findings print
one per line as ``<file>:<line>: <RULE-ID>: <message>`` (``<line>`` is ``0``
when the finding is about a missing file rather than a line).

Standard library only — this must run on any runner with a bare python3, inside
``nix flake check`` and in the unit tests, with no third-party imports.

Rules (each has a stable id, documented at its implementation):

    LIB-CANON   the exemplar file set is present and correctly shaped
    NAMING      pxr-style include guards + Aeco* class prefix in public headers
    SCOPE       PXR_NAMESPACE_OPEN/CLOSE_SCOPE paired; pxr/pxr.h included first-ish
    B16         no schema.usda or schema-type plugInfo registration
    DIAG        no bare printf/fprintf(stderr)/std::cerr on error paths
    PLUGINFO    plugInfo.json parses and carries the keys its registries need
"""

import argparse
import json
import os
import re
import sys


# --------------------------------------------------------------------------
# Finding model
# --------------------------------------------------------------------------

class Finding:
    """One rule violation, at a file:line (line 0 == "missing file / repo-level")."""

    __slots__ = ("path", "line", "rule", "message")

    def __init__(self, path, line, rule, message):
        self.path = path
        self.line = line
        self.rule = rule
        self.message = message

    def format(self, root):
        # Report repo-relative paths so output is stable across checkout dirs.
        try:
            rel = os.path.relpath(self.path, root)
        except ValueError:
            rel = self.path
        return "{}:{}: {}: {}".format(rel, self.line, self.rule, self.message)


# --------------------------------------------------------------------------
# Small file helpers
# --------------------------------------------------------------------------

def _read(path):
    """Read a text file; return "" on any error (missing/binary handled by caller)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


_ALLOW_COMMENT = "aeco-lint: allow-raw-output"

_RAW_DELIM_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    "!\"#%&'*+,-./:;<=>?[]^{|}~$@`")  # anything but space/paren/backslash


def _preprocess_cpp(text, blank_strings=True):
    """Lex a C++ source in translation-phase order for the grep-class rules.

    Phase 2 first (line splicing): a backslash immediately followed by a
    newline joins physical lines, exactly as the compiler does — so a spliced
    identifier (``pri\\<newline>ntf``) or a backslash-continued ``//`` comment
    is seen the way the compiler sees it. Phase 3 second (lexing): ``//`` and
    ``/* */`` comments are blanked; ordinary/char literals and raw string
    literals (``R"delim(...)delim"``, with encoding prefixes) are blanked when
    ``blank_strings`` (kept verbatim otherwise, for ``#include`` argument
    extraction). Newlines inside blanked regions are preserved 1:1 so offsets
    stay line-mappable.

    Returns ``(stripped, linemap, allowed_lines)``:

      * ``stripped`` — the spliced, lexed buffer;
      * ``linemap``  — for each char of ``stripped``, its 1-based line in the
        ORIGINAL (unspliced) text, so findings report real lines;
      * ``allowed_lines`` — original lines sanctioned by an
        ``aeco-lint: allow-raw-output`` marker occurring inside a *genuine
        comment* (the comment's own lines plus the line after it). A marker
        inside a string literal is deliberately NOT honored.
    """
    # --- phase 2: splice, keeping a per-char original-line map -------------
    chars = []
    lmap = []
    i = 0
    n = len(text)
    line = 1
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n and text[i + 1] == "\n":
            i += 2
            line += 1
            continue
        if (c == "\\" and i + 2 < n and
                text[i + 1] == "\r" and text[i + 2] == "\n"):
            i += 3
            line += 1
            continue
        chars.append(c)
        lmap.append(line)
        if c == "\n":
            line += 1
        i += 1

    # --- phase 3: lex ------------------------------------------------------
    out = []
    allowed = set()
    m = len(chars)
    j = 0
    state = "code"
    comment_text = []
    comment_start = 0

    def _blank(c):
        return "\n" if c == "\n" else " "

    def _finish_comment(end_index):
        if _ALLOW_COMMENT in "".join(comment_text):
            start_line = lmap[comment_start]
            end_line = lmap[min(end_index, m - 1)] if m else start_line
            allowed.update(range(start_line, end_line + 2))
        comment_text.clear()

    while j < m:
        c = chars[j]
        nxt = chars[j + 1] if j + 1 < m else ""
        if state == "code":
            if c == "/" and nxt == "/":
                state = "line_comment"
                comment_start = j
                out.append("  ")
                j += 2
                continue
            if c == "/" and nxt == "*":
                state = "block_comment"
                comment_start = j
                out.append("  ")
                j += 2
                continue
            if c == '"':
                # Raw string?  R"delim( ... )delim"  with optional encoding
                # prefix (u8R, uR, UR, LR). The char before the quote must be
                # R, and the char before THAT must not extend an identifier
                # (so BUFFER"..." is not mistaken for a raw literal).
                is_raw = False
                if j >= 1 and chars[j - 1] == "R":
                    before = chars[j - 2] if j >= 2 else ""
                    if (not (before.isalnum() or before == "_") or
                            before in "uUL8"):
                        is_raw = True
                if is_raw:
                    # collect the delimiter up to '('
                    k = j + 1
                    delim = []
                    ok = True
                    while k < m and chars[k] != "(":
                        if chars[k] not in _RAW_DELIM_CHARS or len(delim) > 16:
                            ok = False
                            break
                        delim.append(chars[k])
                        k += 1
                    if ok and k < m:
                        closer = ")" + "".join(delim) + '"'
                        # scan for the closer from k+1
                        end = j
                        p = k + 1
                        found = False
                        while p < m:
                            if chars[p] == closer[0]:
                                cand = "".join(chars[p:p + len(closer)])
                                if cand == closer:
                                    end = p + len(closer) - 1
                                    found = True
                                    break
                            p += 1
                        if not found:
                            end = m - 1
                        for q in range(j, end + 1):
                            out.append(chars[q] if not blank_strings
                                       else _blank(chars[q]))
                        j = end + 1
                        continue
                    # malformed raw intro: fall through as ordinary string
                state = "string"
                out.append('"' if not blank_strings else " ")
                j += 1
                continue
            if c == "'":
                # C++14 digit separator: 1'000'000 — a quote directly after a
                # digit is punctuation, not a char literal.
                if j >= 1 and chars[j - 1].isdigit():
                    out.append(c)
                    j += 1
                    continue
                state = "char"
                out.append("'" if not blank_strings else " ")
                j += 1
                continue
            out.append(c)
            j += 1
        elif state == "line_comment":
            if c == "\n":
                state = "code"
                _finish_comment(j)
                out.append(c)
            else:
                comment_text.append(c)
                out.append(" ")
            j += 1
        elif state == "block_comment":
            if c == "*" and nxt == "/":
                state = "code"
                _finish_comment(j + 1)
                out.append("  ")
                j += 2
            else:
                comment_text.append(c)
                out.append(_blank(c))
                j += 1
        elif state == "string":
            if c == "\\" and j + 1 < m:
                if not blank_strings:
                    out.append(c)
                    out.append(chars[j + 1])
                else:
                    out.append(" ")
                    out.append(_blank(chars[j + 1]))
                j += 2
                continue
            if c == '"':
                state = "code"
            out.append(c if not blank_strings else _blank(c))
            j += 1
        elif state == "char":
            if c == "\\" and j + 1 < m:
                if not blank_strings:
                    out.append(c)
                    out.append(chars[j + 1])
                else:
                    out.append(" ")
                    out.append(_blank(chars[j + 1]))
                j += 2
                continue
            if c == "'":
                state = "code"
            out.append(c if not blank_strings else _blank(c))
            j += 1
    if state in ("line_comment", "block_comment"):
        _finish_comment(m - 1)

    return "".join(out), lmap, allowed


def _offset_line(lmap, offset):
    """Map an offset in a _preprocess_cpp buffer back to the original line."""
    if not lmap:
        return 1
    return lmap[min(offset, len(lmap) - 1)]


# --------------------------------------------------------------------------
# CMake parsing — just enough to read a pxr_library() invocation
# --------------------------------------------------------------------------

# Keywords that open a value section inside pxr_library(...). A bare word that
# is one of these starts a new list; anything else is a value for the open list.
_PXR_LIBRARY_KEYWORDS = {
    "TYPE", "PRECOMPILED_HEADER_NAME",
    "PUBLIC_CLASSES", "PUBLIC_HEADERS", "PRIVATE_CLASSES", "PRIVATE_HEADERS",
    "CPPFILES", "LIBRARIES", "INCLUDE_DIRS", "DOXYGEN_FILES", "RESOURCE_FILES",
    "PYTHON_PUBLIC_CLASSES", "PYTHON_PRIVATE_CLASSES",
    "PYTHON_PUBLIC_HEADERS", "PYTHON_PRIVATE_HEADERS",
    "PYTHON_CPPFILES", "PYMODULE_CPPFILES", "PYMODULE_FILES",
    "PYSIDE_UI_FILES", "DISABLE_PRECOMPILED_HEADERS", "INCLUDE_SCHEMA_FILES",
    "LIB_INSTALL_PREFIX_RESULT",
}


def _extract_call_body(text, func):
    """Return the argument text inside the first ``func(...)`` call, with matched
    parens, or None. Comments are stripped first (CMake uses ``#``).

    CMake command names are case-INsensitive (``PXR_LIBRARY(...)`` is the same
    command), so the match is case-insensitive; a case-only spelling change
    must not make a library invisible to the linter. Section keywords, by
    contrast, are ordinary case-sensitive arguments parsed by
    cmake_parse_arguments and stay exact-match."""
    # Strip CMake # comments (not inside the argument strings we care about;
    # the canon has none there).
    lines = []
    for ln in text.splitlines():
        h = ln.find("#")
        lines.append(ln if h < 0 else ln[:h])
    clean = "\n".join(lines)

    m = re.search(r"\b" + re.escape(func) + r"\s*\(", clean, re.IGNORECASE)
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    while i < len(clean) and depth > 0:
        c = clean[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return clean[start:i]
        i += 1
    return None  # unbalanced


def parse_pxr_library(cmake_text):
    """Parse a ``pxr_library(NAME ...)`` call into a dict of section -> [values].

    Returns None if the file has no pxr_library call. The library NAME is stored
    under key ``"NAME"`` as a single-element list. Section keywords with no
    values (e.g. flags) map to an empty list."""
    body = _extract_call_body(cmake_text, "pxr_library")
    if body is None:
        return None

    tokens = body.split()
    if not tokens:
        return {"NAME": []}

    result = {"NAME": [tokens[0]]}
    current = None
    for tok in tokens[1:]:
        if tok in _PXR_LIBRARY_KEYWORDS:
            current = tok
            result.setdefault(current, [])
        elif current is not None:
            result[current].append(tok)
        # tokens before any keyword (there should be none) are ignored
    return result


# --------------------------------------------------------------------------
# Include-guard derivation (the RATIFIED aeco convention)
# --------------------------------------------------------------------------

def _split_camel(word):
    """Split a camelCase / PascalCase identifier into its words.

    ``debugCodes`` -> ['debug', 'Codes']; ``version`` -> ['version'];
    ``bbox3d`` -> ['bbox3d']. A word boundary is a lowercase-or-digit followed
    by an uppercase letter (pxr's own scheme, e.g. layerStateDelegate ->
    LAYER_STATE_DELEGATE, staticTokens -> STATIC_TOKENS)."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", word).split()


def expected_guard(repo_root, header_path):
    """Derive the pxr-style include guard aeco ratified for a public header.

    Scheme (evidenced by the reviewed aeco-core skeleton — see NAMING docs):

      * take the header path relative to the repo root, e.g.
        ``aeco/base/aecoBase/version.h``;
      * split into path segments and drop the ``.h`` from the filename;
      * DIRECTORY segments are uppercased verbatim, camelCase NOT split, so the
        package dir ``aecoBase`` -> ``AECOBASE`` (this is the one deliberate
        divergence from pxr, which would split it to ``AECO_BASE``; the aeco
        skeleton keeps the package token whole — ``AECO_BASE_AECOBASE_...``);
      * the FILENAME segment is camelCase-split then uppercased, so
        ``debugCodes`` -> ``DEBUG_CODES`` (matching pxr and the skeleton's
        ``AECO_BASE_AECOBASE_DEBUG_CODES_H``);
      * join everything with ``_`` and append ``_H``.

    Worked: ``aeco/base/aecoBase/version.h`` -> ``AECO_BASE_AECOBASE_VERSION_H``;
    ``.../debugCodes.h`` -> ``AECO_BASE_AECOBASE_DEBUG_CODES_H``;
    ``.../api.h`` -> ``AECO_BASE_AECOBASE_API_H``."""
    rel = os.path.relpath(header_path, repo_root)
    parts = rel.replace(os.sep, "/").split("/")
    if not parts:
        return None
    fname = parts[-1]
    dirs = parts[:-1]
    if fname.endswith(".h"):
        stem = fname[:-2]
    else:
        stem = fname

    tokens = []
    for d in dirs:
        tokens.append(d.upper())
    # filename: split camelCase into words
    for w in _split_camel(stem):
        tokens.append(w.upper())
    return "_".join(tokens) + "_H"


# --------------------------------------------------------------------------
# Library discovery
# --------------------------------------------------------------------------

class Library:
    def __init__(self, directory, cmake_path, pxr_library):
        self.dir = directory
        self.cmake = cmake_path
        self.lib = pxr_library  # parsed dict
        self.name = pxr_library.get("NAME", ["?"])[0]

    def public_headers(self):
        """Header filenames that are part of the public surface: PUBLIC_HEADERS
        entries (verbatim, e.g. api.h) plus PUBLIC_CLASSES as ``<name>.h``."""
        headers = []
        for h in self.lib.get("PUBLIC_HEADERS", []):
            headers.append(h)
        for c in self.lib.get("PUBLIC_CLASSES", []):
            headers.append(c + ".h")
        return headers

    def public_class_headers(self):
        """Public *class* headers only (PUBLIC_CLASSES -> ``<name>.h``); these
        carry an Aeco* class declaration and namespace scope. Excludes api.h and
        bare PUBLIC_HEADERS, which are export-macro / token headers."""
        return [c + ".h" for c in self.lib.get("PUBLIC_CLASSES", [])]

    def all_class_stems(self):
        return (self.lib.get("PUBLIC_CLASSES", []) +
                self.lib.get("PRIVATE_CLASSES", []))


def _looks_library_shaped(directory):
    """A directory "looks library-shaped" when it carries any of the canon's
    unmistakable markers: an ``api.h``, a ``wrap*.cpp`` binding file, or a
    ``testenv/`` directory. Used to make discovery failures LOUD: such a dir
    that yields no pxr_library parse is a finding, never silence."""
    if os.path.isfile(os.path.join(directory, "api.h")):
        return True
    if os.path.isdir(os.path.join(directory, "testenv")):
        return True
    try:
        for name in os.listdir(directory):
            if name.startswith("wrap") and name.endswith(".cpp"):
                return True
    except OSError:
        pass
    return False


def discover_libraries(repo_root, lib_filter=None):
    """Find every library dir under ``aeco/`` whose CMakeLists invokes
    pxr_library (case-insensitively — CMake command names are). Returns
    ``(libs, findings)``.

    Discovery failures are loud, not silent: a directory that looks
    library-shaped (api.h / wrap*.cpp / testenv/) but yields no parseable
    pxr_library call — missing CMakeLists, renamed call, unbalanced parens —
    would otherwise silently drop out of every per-library rule, so it is
    reported as a LIB-CANON finding instead. Explicit ``--lib`` targets that
    fail to parse are always reported (they were named on purpose).

    Walk pruning is minimal and deliberate: ``.git`` (VCS), ``build``
    (generated), and ``testenv`` (test scaffolding may contain arbitrary
    fixture files that would false-positive the shape check; a library's own
    testenv/ presence is checked from the library dir itself). Nothing else —
    in particular NOT ``cmake`` or ``result*`` — is pruned under ``aeco/``, so
    a library nested beneath such a name cannot evade discovery."""
    libs = []
    findings = []

    if lib_filter:
        for lf in lib_filter:
            d = lf if os.path.isabs(lf) else os.path.join(repo_root, lf)
            d = os.path.normpath(d)
            cmake = os.path.join(d, "CMakeLists.txt")
            if not os.path.isfile(cmake):
                findings.append(Finding(cmake, 0, "LIB-CANON",
                                        "--lib target has no CMakeLists.txt"))
                continue
            parsed = parse_pxr_library(_read(cmake))
            if parsed is None:
                findings.append(Finding(
                    cmake, 0, "LIB-CANON",
                    "--lib target's CMakeLists.txt has no parseable "
                    "pxr_library(...) call — the directory evades every "
                    "per-library rule"))
                continue
            libs.append(Library(d, cmake, parsed))
        return libs, findings

    aeco_root = os.path.join(repo_root, "aeco")
    if not os.path.isdir(aeco_root):
        return libs, findings

    lib_dirs = []
    for dirpath, dirnames, filenames in os.walk(aeco_root):
        dirnames[:] = [dd for dd in dirnames
                       if dd not in (".git", "build", "testenv")]
        # Inside an already-discovered library, nested helper dirs are that
        # library's business, not new discovery candidates.
        if any(dirpath.startswith(ld + os.sep) for ld in lib_dirs):
            continue
        cmake = os.path.join(dirpath, "CMakeLists.txt")
        parsed = (parse_pxr_library(_read(cmake))
                  if "CMakeLists.txt" in filenames else None)
        if parsed is not None:
            libs.append(Library(dirpath, cmake, parsed))
            lib_dirs.append(dirpath)
        elif _looks_library_shaped(dirpath):
            findings.append(Finding(
                cmake, 0, "LIB-CANON",
                "directory looks library-shaped (api.h / wrap*.cpp / "
                "testenv/) but has no parseable pxr_library(...) call in a "
                "CMakeLists.txt — it silently evades every per-library rule"
                if os.path.isfile(cmake) else
                "directory looks library-shaped (api.h / wrap*.cpp / "
                "testenv/) but has no CMakeLists.txt — it silently evades "
                "every per-library rule"))
    return libs, findings


# --------------------------------------------------------------------------
# Rule: LIB-CANON — the exemplar file set
# --------------------------------------------------------------------------

_API_EXPORT_RE = re.compile(r"ARCH_EXPORT\b")
_API_IMPORT_RE = re.compile(r"ARCH_IMPORT\b")
_PXR_STATIC_RE = re.compile(r"defined\s*\(\s*PXR_STATIC\s*\)")


def rule_lib_canon(lib, repo_root):
    """LIB-CANON — every library dir carries the canonical exemplar files, each
    correctly shaped:

      * ``api.h`` present, defining ``<LIB>_API`` guarded by ``PXR_STATIC`` and
        using the ARCH_EXPORT / ARCH_IMPORT pattern (kind/trace api.h);
      * ``overview.dox`` present AND listed in DOXYGEN_FILES;
      * ``module.cpp`` present IFF PYMODULE_CPPFILES is used — both directions:
        a declared python surface must ship its TF_WRAP_MODULE unit, and a
        stray module.cpp with no declaration is a finding too;
      * ``__init__.py`` present with the Tf.PreparePythonModule / PrepareModule
        idiom IFF PYMODULE_FILES is used — both directions likewise;
      * ``testenv/`` directory present beside the code.

    A missing or malformed canonical file is the classic "stray file layout"
    redness of §3."""
    findings = []
    d = lib.dir

    # --- api.h ---
    api_path = os.path.join(d, "api.h")
    if not os.path.isfile(api_path):
        findings.append(Finding(api_path, 0, "LIB-CANON",
                                 "missing api.h (the export-macro header every "
                                 "library carries)"))
    else:
        text = _read(api_path)
        macro = lib.name.upper() + "_API"
        problems = []
        if not _PXR_STATIC_RE.search(text):
            problems.append("no `defined(PXR_STATIC)` guard")
        if ("#   define " + macro not in text and
                "#define " + macro not in text and
                re.search(r"#\s*define\s+" + re.escape(macro) + r"\b", text) is None):
            problems.append("does not define {}".format(macro))
        if not _API_EXPORT_RE.search(text):
            problems.append("no ARCH_EXPORT")
        if not _API_IMPORT_RE.search(text):
            problems.append("no ARCH_IMPORT")
        if problems:
            findings.append(Finding(api_path, 1, "LIB-CANON",
                                     "api.h not in the <LIB>_API export pattern: "
                                     + "; ".join(problems)))

    # --- overview.dox ---
    # overview.dox must exist AND be listed in DOXYGEN_FILES (an omitted
    # DOXYGEN_FILES section is the same defect as an unlisted file: the doc
    # never installs).
    dox_files = lib.lib.get("DOXYGEN_FILES", [])
    overview = os.path.join(d, "overview.dox")
    if not os.path.isfile(overview):
        findings.append(Finding(overview, 0, "LIB-CANON",
                                 "missing overview.dox (the per-library doc)"))
    elif "overview.dox" not in dox_files:
        findings.append(Finding(lib.cmake, 0, "LIB-CANON",
                                 "overview.dox present but not listed in "
                                 "DOXYGEN_FILES (it never installs)"))

    # --- module.cpp iff PYMODULE_CPPFILES ---
    has_pymodule_cpp = "PYMODULE_CPPFILES" in lib.lib
    module_cpp = os.path.join(d, "module.cpp")
    if has_pymodule_cpp:
        listed = lib.lib.get("PYMODULE_CPPFILES", [])
        if "module.cpp" not in listed:
            findings.append(Finding(lib.cmake, 0, "LIB-CANON",
                                     "PYMODULE_CPPFILES is used but module.cpp is "
                                     "not among its entries (the TF_WRAP_MODULE "
                                     "translation unit)"))
        elif not os.path.isfile(module_cpp):
            findings.append(Finding(module_cpp, 0, "LIB-CANON",
                                     "PYMODULE_CPPFILES lists module.cpp but the "
                                     "file is missing"))
        else:
            if "TF_WRAP_MODULE" not in _read(module_cpp):
                findings.append(Finding(module_cpp, 1, "LIB-CANON",
                                         "module.cpp does not contain "
                                         "TF_WRAP_MODULE"))
    else:
        # The reverse direction of the iff: no python surface declared, so a
        # module.cpp lying around is a stray — it never compiles, and the
        # library quietly ships without the bindings the file promises.
        if os.path.isfile(module_cpp):
            findings.append(Finding(module_cpp, 0, "LIB-CANON",
                                     "module.cpp is present but "
                                     "PYMODULE_CPPFILES is not used — declare "
                                     "the python surface to pxr_library or "
                                     "remove the file"))

    # --- __init__.py iff PYMODULE_FILES ---
    has_pymodule_files = "PYMODULE_FILES" in lib.lib
    init_path = os.path.join(d, "__init__.py")
    if has_pymodule_files:
        listed = lib.lib.get("PYMODULE_FILES", [])
        if "__init__.py" not in listed:
            findings.append(Finding(lib.cmake, 0, "LIB-CANON",
                                     "PYMODULE_FILES is used but __init__.py is "
                                     "not among its entries"))
        elif not os.path.isfile(init_path):
            findings.append(Finding(init_path, 0, "LIB-CANON",
                                     "PYMODULE_FILES lists __init__.py but the "
                                     "file is missing"))
        else:
            itext = _read(init_path)
            if ("PreparePythonModule" not in itext and
                    "PrepareModule" not in itext):
                findings.append(Finding(init_path, 1, "LIB-CANON",
                                         "__init__.py lacks the "
                                         "Tf.PreparePythonModule()/PrepareModule() "
                                         "idiom"))
    else:
        # Reverse direction: a stray __init__.py with no PYMODULE_FILES never
        # installs — the python package the file promises does not exist.
        if os.path.isfile(init_path):
            findings.append(Finding(init_path, 0, "LIB-CANON",
                                     "__init__.py is present but PYMODULE_FILES "
                                     "is not used — declare it to pxr_library "
                                     "or remove the file"))

    # --- testenv/ ---
    testenv = os.path.join(d, "testenv")
    if not os.path.isdir(testenv):
        findings.append(Finding(testenv, 0, "LIB-CANON",
                                 "missing testenv/ directory (tests live beside "
                                 "the code)"))

    return findings


# --------------------------------------------------------------------------
# Rule: NAMING — include guards + class prefix
# --------------------------------------------------------------------------

# A class/struct *declaration* (not a forward decl, not a use). Matches
# `class Foo {`, `class FOO_API Foo :`, `struct Foo\n{`.
_CLASS_DECL_RE = re.compile(
    r"^\s*(?:class|struct)\s+"
    r"(?:[A-Z][A-Z0-9_]*_API\s+)?"        # optional export macro
    r"([A-Za-z_]\w*)"                      # the type name
    r"\s*(?::[^;{]*)?\{",                  # optional base list, then a body brace
    re.MULTILINE)


def rule_naming(lib, repo_root):
    """NAMING — public headers follow pxr naming (RATIFIED aeco convention):

      * path-derived include guard: the ``#ifndef``/``#define`` guard equals the
        guard derived from the header's path (see ``expected_guard``);
      * every class/struct *declaration* in a public class header carries the
        capitalized library prefix (``Aeco*``) — the pxr rule "class prefix =
        library name".

    api.h is checked for its guard but exempt from the class-prefix rule (it
    declares no classes). Private headers are not part of the public naming
    surface and are not checked here."""
    findings = []
    d = lib.dir

    # Guard check: all public headers (incl. api.h). The guard is verified
    # STRUCTURALLY as the file's outer frame, not by mere presence anywhere:
    # a wrong outer guard with the expected pair buried in a dead `#if 0`
    # block must red.
    for hname in lib.public_headers():
        hpath = os.path.join(d, hname)
        if not os.path.isfile(hpath):
            continue  # LIB-CANON / missing-file territory
        want = expected_guard(repo_root, hpath)
        findings.extend(_check_outer_guard(hpath, want))

    # Class-prefix check: public *class* headers only.
    for hname in lib.public_class_headers():
        hpath = os.path.join(d, hname)
        if not os.path.isfile(hpath):
            continue
        code, lmap, _ = _preprocess_cpp(_read(hpath), blank_strings=True)
        for m in _CLASS_DECL_RE.finditer(code):
            typename = m.group(1)
            # Only require the prefix for the library's own public types. A
            # bare-word nested helper is fine; the rule targets top-level Aeco*
            # types. We flag any declared type that neither starts with the
            # library prefix's leading capitalized token (Aeco) nor is clearly
            # a private detail (leading underscore).
            if typename.startswith("_"):
                continue
            if not typename.startswith("Aeco"):
                line = _offset_line(lmap, m.start())
                findings.append(Finding(hpath, line, "NAMING",
                                         "class '{}' in a public header lacks the "
                                         "capitalized library prefix (Aeco*)"
                                         .format(typename)))
    return findings


_DIRECTIVE_RE = re.compile(r"^\s*#\s*(\w+)[ \t]*(\S*)")


def _check_outer_guard(hpath, want):
    """Verify ``want`` is the file's OUTER include guard, structurally:

      * nothing but comments/blank lines precedes the guard;
      * the FIRST preprocessor directive is ``#ifndef <want>``;
      * the next preprocessor directive is ``#define <want>``;
      * the guard actually ENCLOSES the file: tracking conditional nesting
        (#if/#ifdef/#ifndef increment, #endif decrement), the #endif that
        closes the outer guard must be the LAST directive, with no
        substantive content after it (trailing comments/whitespace fine).

    Present-anywhere is not enough — a dead ``#if 0`` block containing the
    expected pair, behind a wrong real guard, must red; and a *degenerate*
    guard (``#ifndef``/``#define``/``#endif`` up front with the whole body
    after it — the rev-2 review construction) must red too: it guards
    nothing. The check runs on the spliced, comment-stripped buffer (strings
    kept: directive args are not strings), so commented-out directives cannot
    satisfy or confuse it. Legitimate inner conditional blocks (api.h's
    ``#if defined(PXR_STATIC)`` ladder) nest and unwind without touching
    depth 0, so they pass."""
    findings = []
    text = _read(hpath)
    code, lmap, _ = _preprocess_cpp(text, blank_strings=False)

    directives = []  # (original_line, name, arg, end_offset_of_line)
    code_before_guard_line = None
    offset = 0
    for logical in code.split("\n"):
        stripped_line = logical.strip()
        if stripped_line:
            m = _DIRECTIVE_RE.match(logical)
            if m:
                first = offset + (len(logical) - len(logical.lstrip()))
                directives.append(
                    (_offset_line(lmap, first), m.group(1), m.group(2),
                     offset + len(logical)))
            elif not directives and code_before_guard_line is None:
                first = offset + (len(logical) - len(logical.lstrip()))
                code_before_guard_line = _offset_line(lmap, first)
        offset += len(logical) + 1

    if not directives:
        findings.append(Finding(hpath, 1, "NAMING",
                                 "no include guard; pxr-derived path guard "
                                 "should be #ifndef {}".format(want)))
        return findings

    line0, name0, arg0 = directives[0][:3]
    if code_before_guard_line is not None:
        findings.append(Finding(hpath, code_before_guard_line, "NAMING",
                                 "code precedes the include guard — #ifndef {} "
                                 "must be the file's outer frame".format(want)))
        return findings
    if name0 != "ifndef" or arg0 != want:
        if name0 == "ifndef":
            findings.append(Finding(hpath, line0, "NAMING",
                                     "include guard is {}; pxr-derived path "
                                     "guard should be {}".format(
                                         arg0 or "(empty)", want)))
        else:
            findings.append(Finding(hpath, line0, "NAMING",
                                     "first preprocessor directive is #{}; the "
                                     "outer include guard #ifndef {} must come "
                                     "first".format(name0, want)))
        return findings
    if len(directives) < 2 or directives[1][1] != "define" or \
            directives[1][2] != want:
        findings.append(Finding(hpath, line0, "NAMING",
                                 "#ifndef {0} is not followed by its "
                                 "#define {0}".format(want)))
        return findings

    # The guard must enclose the file: walk conditional nesting and find the
    # #endif that returns the outer level to depth 0 (rev-2 review evasion:
    # a degenerate guard closing right after its #define passed before).
    depth = 0
    close_idx = None
    for idx, (dline, dname, _darg, _dend) in enumerate(directives):
        if dname in ("if", "ifdef", "ifndef"):
            depth += 1
        elif dname == "endif":
            depth -= 1
            if depth == 0:
                close_idx = idx
                break
            if depth < 0:
                findings.append(Finding(hpath, dline, "NAMING",
                                         "unbalanced #endif before the include "
                                         "guard #ifndef {} is closed"
                                         .format(want)))
                return findings

    if close_idx is None:
        findings.append(Finding(hpath, line0, "NAMING",
                                 "#ifndef {} is never closed — its #endif is "
                                 "missing".format(want)))
        return findings

    guard_close = directives[close_idx]
    if close_idx != len(directives) - 1:
        after = directives[close_idx + 1]
        findings.append(Finding(hpath, after[0], "NAMING",
                                 "the include guard's #endif (line {}) does not "
                                 "enclose the file — directives follow it, so "
                                 "#ifndef {} guards nothing"
                                 .format(guard_close[0], want)))
        return findings
    tail = code[guard_close[3]:]
    if tail.strip():
        rel = len(tail) - len(tail.lstrip())
        findings.append(Finding(hpath,
                                 _offset_line(lmap, guard_close[3] + rel),
                                 "NAMING",
                                 "the include guard's #endif (line {}) does not "
                                 "enclose the file — content follows it, so "
                                 "#ifndef {} guards nothing"
                                 .format(guard_close[0], want)))
    return findings


def _lib_class_prefix(libname):
    """aecoBase -> AecoBase, aecoValidators -> AecoValidators."""
    if not libname:
        return "Aeco"
    return libname[0].upper() + libname[1:]


# --------------------------------------------------------------------------
# Rule: SCOPE — namespace pairing + pxr/pxr.h first-ish
# --------------------------------------------------------------------------

_OPEN_SCOPE = "PXR_NAMESPACE_OPEN_SCOPE"
_CLOSE_SCOPE = "PXR_NAMESPACE_CLOSE_SCOPE"
_USING_DIRECTIVE = "PXR_NAMESPACE_USING_DIRECTIVE"

_GENERATED_MARKER_RE = re.compile(r"THIS FILE IS GENERATED", re.IGNORECASE)
_INCLUDE_RE = re.compile(r'^\s*#\s*include\s+[<"]([^>"]+)[>"]', re.MULTILINE)


def _iter_scope_files(lib):
    """Yield (path, kind) for the C++ files SCOPE reasons about:
    public class headers ('public_header'), and their implementation .cpp
    ('cpp'). wrap*.cpp / module.cpp / pch.h / api.h are handled specially by the
    caller (they use USING_DIRECTIVE or no scope)."""
    d = lib.dir
    for hname in lib.public_class_headers():
        p = os.path.join(d, hname)
        if os.path.isfile(p):
            yield p, "public_header"
    for stem in lib.all_class_stems():
        p = os.path.join(d, stem + ".cpp")
        if os.path.isfile(p):
            yield p, "cpp"


def rule_scope(lib, repo_root):
    """SCOPE — namespace and include hygiene:

      * OPEN_SCOPE / CLOSE_SCOPE are *paired*: any file with one must have the
        other (an unbalanced macro is a compile-or-lint error either way).
        Pairing is evaluated on the comment/string-STRIPPED buffer, so a
        commented-out token can neither satisfy nor trip the check;
      * every public *class* header must open and close the pxr namespace (a
        public type declared outside PXR_NS is a defect) — api.h and generated
        headers excepted;
      * every public *class* header must INCLUDE ``pxr/pxr.h`` — the namespace
        macros it uses are defined there; deleting the include is a defect,
        not a pass;
      * ``pxr/pxr.h`` is included first-ish: among the ``pxr/...`` /
        ``aeco/...`` project includes it must be the first, so the namespace
        macros are defined before use (pxr house rule). System/library headers
        before it are fine. Include extraction runs on the comment-stripped
        buffer, so a commented-out #include does not count.

    Files that legitimately use PXR_NAMESPACE_USING_DIRECTIVE instead (module.cpp,
    wrap*.cpp, tests) are not required to open/close a scope; they are only held
    to the pairing rule (which they trivially pass)."""
    findings = []
    d = lib.dir

    checked = set()

    def check_one(path, must_scope):
        checked.add(os.path.normpath(path))
        text = _read(path)
        if _GENERATED_MARKER_RE.search(text):
            return  # generated (pch.h, moduleDeps.cpp): not ours to shape
        # Token presence on the fully stripped buffer (comments AND strings
        # blanked): a commented-out CLOSE_SCOPE must not balance a real OPEN.
        code, lmap, _ = _preprocess_cpp(text, blank_strings=True)
        has_open = _OPEN_SCOPE in code
        has_close = _CLOSE_SCOPE in code
        has_using = _USING_DIRECTIVE in code

        def _tok_line(token):
            return _offset_line(lmap, code.find(token))

        # Pairing
        if has_open and not has_close:
            findings.append(Finding(path, _tok_line(_OPEN_SCOPE), "SCOPE",
                                     "PXR_NAMESPACE_OPEN_SCOPE without a matching "
                                     "PXR_NAMESPACE_CLOSE_SCOPE"))
        if has_close and not has_open:
            findings.append(Finding(path, _tok_line(_CLOSE_SCOPE), "SCOPE",
                                     "PXR_NAMESPACE_CLOSE_SCOPE without a matching "
                                     "PXR_NAMESPACE_OPEN_SCOPE"))

        # Mandatory scope for public class headers.
        if must_scope and not has_open and not has_using:
            findings.append(Finding(path, 1, "SCOPE",
                                     "public header does not open the pxr "
                                     "namespace (PXR_NAMESPACE_OPEN_SCOPE)"))

        # Includes, from the comment-stripped buffer with string content kept
        # (the include argument is the "string").
        inc_code, inc_lmap, _ = _preprocess_cpp(text, blank_strings=False)
        includes = _INCLUDE_RE.findall(inc_code)

        # Public class headers must actually include pxr/pxr.h.
        if must_scope and "pxr/pxr.h" not in includes:
            findings.append(Finding(path, 1, "SCOPE",
                                     "public header does not include pxr/pxr.h "
                                     "(the namespace macros' home)"))

        # pxr/pxr.h first-ish among project includes.
        project_includes = [
            inc for inc in includes
            if inc == "pxr/pxr.h" or inc.startswith("aeco/") or
            (inc.startswith("pxr/") and inc != "pxr/pxr.h")
        ]
        if project_includes and "pxr/pxr.h" in includes:
            if project_includes[0] != "pxr/pxr.h":
                findings.append(Finding(path,
                                         _offset_line(
                                             inc_lmap,
                                             inc_code.find(project_includes[0])),
                                         "SCOPE",
                                         "pxr/pxr.h must be the first project "
                                         "include (before {}) so the namespace "
                                         "macros are defined".format(
                                             project_includes[0])))

    for path, kind in _iter_scope_files(lib):
        check_one(path, must_scope=(kind == "public_header"))

    # Also apply the pairing rule to wrap*.cpp and module.cpp so a stray
    # unbalanced macro there is caught, but never require them to open a scope.
    for extra in _list_cpp_like(d):
        np = os.path.normpath(extra)
        if np in checked:
            continue
        base = os.path.basename(extra)
        if base == "module.cpp" or base.startswith("wrap"):
            check_one(extra, must_scope=False)

    return findings


def _list_cpp_like(directory):
    out = []
    try:
        for name in sorted(os.listdir(directory)):
            if name.endswith(".cpp"):
                out.append(os.path.join(directory, name))
    except OSError:
        pass
    return out


# --------------------------------------------------------------------------
# Rule: B16 — processing repositories consume schemas; they do not author them
# --------------------------------------------------------------------------

_SCHEMA_FILE = "schema.usda"
_SCHEMA_TYPE_KEYS = frozenset((
    "schemaKind",
    "schemaIdentifier",
    "apiSchemaAutoApplyTo",
    "apiSchemaCanOnlyApplyTo",
    "apiSchemaAllowedInstanceNames",
))


def _b16_registered_schema_types(path):
    """Return schema type names registered by a parseable plugInfo.json.

    usdGenSchema registrations identify themselves through schema metadata,
    an UsdSchemaBase alias, or autoGenerated=true. Other Plug ``Types`` such
    as SdfFileFormat and ArResolver registrations remain valid processing
    plugins. Malformed plugInfo is left to the PLUGINFO rule.
    """
    raw = _read(path)
    # usdGenSchema writes leading #-comments; Plug accepts those as well as
    # JSONC comments and @VAR@ substitutions.
    normalized = re.sub(r"(?m)^[ \t]*#[^\n]*(?:\n|$)", "\n", raw)
    normalized = _strip_jsonc_comments(normalized)
    normalized = re.sub(r'"@[^"]*@"', '"__SUBST__"', normalized)
    try:
        data = json.loads(normalized)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, dict) or not isinstance(data.get("Plugins"), list):
        return []

    registered = set()
    for plugin in data["Plugins"]:
        if not isinstance(plugin, dict):
            continue
        info = plugin.get("Info")
        if not isinstance(info, dict) or not isinstance(info.get("Types"), dict):
            continue
        for type_name, type_info in info["Types"].items():
            if not isinstance(type_info, dict):
                continue
            alias = type_info.get("alias")
            schema_alias = isinstance(alias, dict) and "UsdSchemaBase" in alias
            if (_SCHEMA_TYPE_KEYS.intersection(type_info) or schema_alias or
                    type_info.get("autoGenerated") is True):
                registered.add(type_name)
    return sorted(registered)


def rule_b16(repo_root):
    """B16 — processing repos consume the codeless model but never author it.

    A ``schema.usda`` source or a ``plugInfo.json`` that registers schema types
    is a violation anywhere under the repo (outside .git / build / result).
    Generated schema resources may be visible through a flake input, and a
    ``generatedSchema.usda`` consumer artifact is not authorship. This is a
    repo-level rule, run once, not per library.
    """
    findings = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [dd for dd in dirnames
                       if dd not in (".git", "build") and
                       not dd.startswith("result")]
        for fn in filenames:
            if fn == _SCHEMA_FILE:
                p = os.path.join(dirpath, fn)
                findings.append(Finding(p, 0, "B16",
                                         "schema source '{}' must not exist in a "
                                         "processing repo (B16 — processing "
                                         "consumes schemas but never authors them)"
                                         .format(fn)))
            elif fn == "plugInfo.json":
                p = os.path.join(dirpath, fn)
                registered = _b16_registered_schema_types(p)
                if registered:
                    findings.append(Finding(
                        p, 0, "B16",
                        "plugInfo.json registers schema type(s) {} in a "
                        "processing repo (B16 — processing consumes schemas "
                        "but never authors them)".format(", ".join(registered))))
    return findings


# --------------------------------------------------------------------------
# Rule: DIAG — error-path output hygiene
# --------------------------------------------------------------------------

# printf(...  |  fprintf(stderr, ...  |  std::cerr / cerr <<
_PRINTF_RE = re.compile(r"\bprintf\s*\(")
_FPRINTF_STDERR_RE = re.compile(r"\bfprintf\s*\(\s*stderr\b")
_CERR_RE = re.compile(r"\b(?:std\s*::\s*)?cerr\b")


def rule_diag(repo_root, libs):
    """DIAG — diagnostics go through Tf, not bare stdio. In any ``.cpp`` under a
    library dir but *outside* ``testenv/``, flag ``printf(``,
    ``fprintf(stderr,`` and ``std::cerr`` — the sanctioned error surface is
    TF_ERROR / TF_WARN / TF_STATUS / TF_CODING_ERROR et al. A line (or the line
    above) carrying the comment ``// aeco-lint: allow-raw-output`` is honored as
    an explicit, reviewed exception.

    Comments and string literals are stripped before matching, so a printf named
    in a doc comment or a format string does not fire. testenv/ is exempt: test
    drivers legitimately print ``>>> Test SUCCEEDED``.

    Scope decision (recorded 2026-08-10, P0-9): DIAG governs *library* code —
    the dirs the canon governs, i.e. ``pxr_library`` dirs under ``aeco/``.
    Harness code outside that scope (``testenv/`` drivers, and standalone
    spike/probe executables such as the toolchain's ``spike/``) is exempt by
    construction: its stdout/stderr IS its interface (the embed-spike check
    greps its report line from stdout; test wrappers diff theirs), it is not
    installable library surface, and forcing Tf onto it would break those
    contracts. The Tf-only rule exists so library diagnostics reach
    TfDiagnosticMgr delegates; that rationale does not apply to rung-2 harness
    executables. Pinned by test_spike_like_harness_code_is_exempt."""
    findings = []
    for lib in libs:
        for dirpath, dirnames, filenames in os.walk(lib.dir):
            # Skip testenv anywhere below the library.
            dirnames[:] = [dd for dd in dirnames if dd != "testenv"]
            for fn in filenames:
                if not fn.endswith(".cpp"):
                    continue
                p = os.path.join(dirpath, fn)
                findings.extend(_diag_scan_file(p))
    return findings


def _diag_scan_file(path):
    """Scan one .cpp on the C++-phase-ordered buffer (splice → strip), so:

      * ``printf`` split across physical lines (``printf\\n(...)``), an
        identifier spliced by backslash-newline (``pri\\<nl>ntf(``) and
        ``fprintf(\\n stderr, ...)`` all match — the regexes run over the WHOLE
        stripped buffer, where ``\\s`` crosses newlines and splices are joined;
      * text inside comments, string literals and raw string literals never
        matches, and a backslash-continued ``//`` comment swallows its
        continuation line exactly as the compiler does;
      * the allow marker is honored only from a genuine comment
        (_preprocess_cpp collects it during comment lexing) — a marker inside
        a string literal does not suppress anything.

    One finding per original line, priority fprintf(stderr) > printf > cerr."""
    findings = []
    code, lmap, allowed = _preprocess_cpp(_read(path), blank_strings=True)
    seen_lines = set()
    for hit, rx in (("fprintf(stderr, ...)", _FPRINTF_STDERR_RE),
                    ("printf(...)", _PRINTF_RE),
                    ("std::cerr", _CERR_RE)):
        for m in rx.finditer(code):
            lineno = _offset_line(lmap, m.start())
            if lineno in allowed or lineno in seen_lines:
                continue
            seen_lines.add(lineno)
            findings.append(Finding(path, lineno, "DIAG",
                                     "{} on an error path — use TF_ERROR/"
                                     "TF_WARN/TF_STATUS (or add `// {}` to "
                                     "allow)".format(hit, _ALLOW_COMMENT)))
    return findings


# --------------------------------------------------------------------------
# Rule: PLUGINFO — plugInfo.json well-formedness
# --------------------------------------------------------------------------

def rule_pluginfo(repo_root):
    """PLUGINFO — every ``plugInfo.json`` parses as JSON, and if it declares a
    known registry section it carries the structural keys that registry needs.

    Studied against pxr/usd/ar/plugInfo.json (``Types``) and
    pxr/usdValidation/usdGeomValidators/plugInfo.json (``Validators``):

      * top level is an object with a ``Plugins`` array;
      * each plugin entry declaring ``Info`` may carry ``Types`` / ``Validators``
        / ``Exec`` maps; when it does, each entry keeps to the registry's shape:
          - Types: a map of type-name -> object (``bases`` optional, a list);
          - Validators: a map of validator-name -> object (``schemaTypes`` /
            ``keywords`` optional, lists) — the special ``keywords`` key at the
            map level is allowed (a list);
          - Exec: a map of plugin-name -> object.

    Malformed JSON is always a finding. This is a repo-level walk."""
    findings = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [dd for dd in dirnames
                       if dd not in (".git", "build") and
                       not dd.startswith("result")]
        for fn in filenames:
            if fn != "plugInfo.json":
                continue
            p = os.path.join(dirpath, fn)
            findings.extend(_pluginfo_scan(p))
    return findings


def _pluginfo_scan(path):
    findings = []
    raw = _read(path)
    # plugInfo.json in-source often carries @VAR@ substitution tokens and
    # // comments (Plug's JSON reader tolerates both). Normalise before parse.
    normalized = _strip_jsonc_comments(raw)
    normalized = re.sub(r'"@[^"]*@"', '"__SUBST__"', normalized)
    try:
        data = json.loads(normalized)
    except (json.JSONDecodeError, ValueError) as e:
        findings.append(Finding(path, getattr(e, "lineno", 0) or 0, "PLUGINFO",
                                 "plugInfo.json does not parse as JSON: {}"
                                 .format(e)))
        return findings

    if not isinstance(data, dict):
        findings.append(Finding(path, 0, "PLUGINFO",
                                 "plugInfo.json top level must be an object"))
        return findings
    plugins = data.get("Plugins")
    if plugins is None:
        findings.append(Finding(path, 0, "PLUGINFO",
                                 "plugInfo.json has no 'Plugins' array"))
        return findings
    if not isinstance(plugins, list):
        findings.append(Finding(path, 0, "PLUGINFO",
                                 "'Plugins' must be an array"))
        return findings

    for plugin in plugins:
        if not isinstance(plugin, dict):
            findings.append(Finding(path, 0, "PLUGINFO",
                                     "each 'Plugins' entry must be an object"))
            continue
        info = plugin.get("Info")
        if info is None:
            continue
        if not isinstance(info, dict):
            findings.append(Finding(path, 0, "PLUGINFO",
                                     "'Info' must be an object"))
            continue

        if "Types" in info:
            findings.extend(_check_registry_map(path, info["Types"], "Types",
                                                 list_keys=("bases",)))
        if "Validators" in info:
            findings.extend(_check_registry_map(path, info["Validators"],
                                                 "Validators",
                                                 list_keys=("schemaTypes",
                                                            "keywords"),
                                                 allow_toplevel_keywords=True))
        if "Exec" in info:
            findings.extend(_check_registry_map(path, info["Exec"], "Exec",
                                                 list_keys=()))
    return findings


def _check_registry_map(path, section, name, list_keys, allow_toplevel_keywords=False):
    findings = []
    if not isinstance(section, dict):
        findings.append(Finding(path, 0, "PLUGINFO",
                                 "'{}' must be a map of name -> object"
                                 .format(name)))
        return findings
    for key, val in section.items():
        # Validators permits a map-level "keywords" list beside the entries
        # (see the usdGeomValidators exemplar).
        if allow_toplevel_keywords and key == "keywords":
            if not isinstance(val, list):
                findings.append(Finding(path, 0, "PLUGINFO",
                                         "'{}.keywords' must be a list"
                                         .format(name)))
            continue
        if not isinstance(val, dict):
            findings.append(Finding(path, 0, "PLUGINFO",
                                     "'{}.{}' must be an object (the registry "
                                     "entry's attributes)".format(name, key)))
            continue
        for lk in list_keys:
            if lk in val and not isinstance(val[lk], list):
                findings.append(Finding(path, 0, "PLUGINFO",
                                         "'{}.{}.{}' must be a list"
                                         .format(name, key, lk)))
    return findings


def _strip_jsonc_comments(text):
    """Strip //-line and /* */ comments from JSON-with-comments, preserving
    string contents. Plug's reader tolerates these; strict json does not."""
    out = []
    i = 0
    n = len(text)
    state = "code"
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == "/" and nxt == "/":
                state = "line"
                i += 2
                continue
            if c == "/" and nxt == "*":
                state = "block"
                i += 2
                continue
            if c == '"':
                state = "string"
                out.append(c)
                i += 1
                continue
            out.append(c)
            i += 1
        elif state == "line":
            if c == "\n":
                state = "code"
                out.append(c)
            i += 1
        elif state == "block":
            if c == "*" and nxt == "/":
                state = "code"
                i += 2
            else:
                if c == "\n":
                    out.append(c)
                i += 1
        elif state == "string":
            if c == "\\":
                out.append(c)
                out.append(nxt)
                i += 2
                continue
            if c == '"':
                state = "code"
            out.append(c)
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def lint(repo_root, lib_filter=None):
    """Run every rule over the repo. Returns a list of Findings (sorted)."""
    repo_root = os.path.abspath(repo_root)
    libs, findings = discover_libraries(repo_root, lib_filter)

    # Per-library rules.
    for lib in libs:
        findings.extend(rule_lib_canon(lib, repo_root))
        findings.extend(rule_naming(lib, repo_root))
        findings.extend(rule_scope(lib, repo_root))
    # Repo-level rules.
    findings.extend(rule_b16(repo_root))
    findings.extend(rule_diag(repo_root, libs))
    findings.extend(rule_pluginfo(repo_root))

    findings.sort(key=lambda f: (os.path.abspath(f.path), f.line, f.rule))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="aecoLintConventions.py",
        description="Hold the OpenUSD library canon for aeco processing repos.")
    parser.add_argument("repo_root",
                        help="root of the repo to lint")
    parser.add_argument("--lib", action="append", dest="libs", default=None,
                        metavar="PATH",
                        help="restrict to this library dir (repeatable)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.repo_root):
        sys.stderr.write("error: not a directory: {}\n".format(args.repo_root))
        return 2

    findings = lint(args.repo_root, args.libs)
    root = os.path.abspath(args.repo_root)
    for f in findings:
        print(f.format(root))
    if findings:
        print("aecoLintConventions: {} finding(s)".format(len(findings)),
              file=sys.stderr)
        return 1
    print("aecoLintConventions: clean", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
