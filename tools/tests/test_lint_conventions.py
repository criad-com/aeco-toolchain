#!/usr/bin/env python3
#
# Copyright 2026 AECO
#
# © AECO — all rights reserved. See the NOTICE file.
#
"""Unit tests for aecoLintConventions.

Strategy: ``tools/tests/fixtures/clean`` is a fully-canonical library that
passes every rule. Each red test builds a *red fixture* by copying that clean
tree into a temp dir and applying exactly ONE planted violation (the mutation
table below), then asserts the linter reds with that violation's rule id —
and with *only* that rule — and that the finding's message carries the
expected substring (so near-miss findings cannot masquerade).

A review round constructed six evasions; each of those
constructions is reproduced here verbatim as a red or clean-side case, so the
evasion corpus is permanent:

  1. ``PXR_LIBRARY(...)`` case evasion + silent discovery drop-out
  2. DIAG line-splitting (``printf\\n(...)``, ``fprintf(\\nstderr``, spliced
     identifiers)
  3. lexer mis-lexing (raw strings both directions, backslash-continued
     comments, allow-marker inside a string)
  4. dead ``#if 0`` guard satisfying a present-anywhere check
  5. missing ``pxr/pxr.h`` include / commented-out scope tokens
  6. one-directional "iff" enforcement + fused api.h fixture

A final battery asserts the clean tree passes, and, when the reviewed consumer
checkout is present, that aeco-core (packet/2) passes as-is.

Run: ``python3 tools/tests/test_lint_conventions.py`` (stdlib unittest), or via
``nix flake check`` (checks.lintConventions).
"""

import os
import shutil
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.dirname(_HERE)
_REPO = os.path.dirname(_TOOLS)
_CLEAN = os.path.join(_HERE, "fixtures", "clean")
_LIBREL = os.path.join("aeco", "base", "fixBase")

sys.path.insert(0, _TOOLS)
import aecoLintConventions as lint  # noqa: E402


# --------------------------------------------------------------------------
# Planted-violation helpers — each returns nothing, mutating the fixture in
# place. One mutation == one red fixture == one planted violation.
# --------------------------------------------------------------------------

def _p(root, *parts):
    return os.path.join(root, _LIBREL, *parts)


def _make_writable(root):
    import stat
    # The root itself too — planters may create entries directly under it.
    try:
        os.chmod(root, os.stat(root).st_mode | stat.S_IWUSR)
    except OSError:
        pass
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            try:
                mode = os.stat(p).st_mode
                os.chmod(p, mode | stat.S_IWUSR)
            except OSError:
                pass


def _sub(path, old, new, count=-1):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    assert old in text, "planned substring not found in {}: {!r}".format(path, old)
    text = text.replace(old, new) if count < 0 else text.replace(old, new, count)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _inject_widget_cpp(root, snippet):
    """Insert ``snippet`` (plus the original return) at the body of
    AecoWidget::GetLabel in the fixture's widget.cpp."""
    _sub(_p(root, "widget.cpp"),
         'return "fixBase-widget";',
         snippet + '\n    return "fixBase-widget";')


# --- LIB-CANON: missing / malformed canon files ---------------------------

def plant_libcanon_missing_overview(root):
    os.remove(_p(root, "overview.dox"))


def plant_libcanon_missing_init(root):
    os.remove(_p(root, "__init__.py"))


def plant_libcanon_missing_module(root):
    os.remove(_p(root, "module.cpp"))


def plant_libcanon_missing_testenv(root):
    shutil.rmtree(_p(root, "testenv"))


def plant_libcanon_bad_init_idiom(root):
    with open(_p(root, "__init__.py"), "w", encoding="utf-8") as f:
        f.write('"""Python bindings for libFixBase"""\n'
                "import sys\n"  # no PreparePythonModule idiom
                "del sys\n")


# --- LIB-CANON: api.h invariants, each planted ALONE (review item 6) ------

def plant_api_no_pxr_static(root):
    # The PXR_STATIC branch guard disappears; everything else stays intact.
    _sub(_p(root, "api.h"), "defined(PXR_STATIC)", "defined(FIXBASE_STATIC)")


def plant_api_no_macro_define(root):
    # <LIB>_API is never defined (its #define lines renamed); the include
    # guard (AECO_BASE_FIXBASE_API_H, which contains the substring), the
    # PXR_STATIC guard and ARCH_EXPORT/IMPORT all remain intact.
    _sub(_p(root, "api.h"), "define FIXBASE_API", "define FIXBASE_XAPI")


def plant_api_no_arch_export(root):
    _sub(_p(root, "api.h"),
         "#       define FIXBASE_API ARCH_EXPORT\n",
         "#       define FIXBASE_API\n")


def plant_api_no_arch_import(root):
    _sub(_p(root, "api.h"),
         "#       define FIXBASE_API ARCH_IMPORT\n",
         "#       define FIXBASE_API\n")


# --- LIB-CANON: the "iff" in both directions (review item 6) --------------

def plant_libcanon_stray_module(root):
    # module.cpp remains on disk; the CMakeLists stops declaring the python
    # surface. One direction of the iff the review found unenforced.
    _sub(_p(root, "CMakeLists.txt"),
         "    PYMODULE_CPPFILES\n        module.cpp\n        wrapWidget.cpp\n\n",
         "")


def plant_libcanon_stray_init(root):
    _sub(_p(root, "CMakeLists.txt"),
         "    PYMODULE_FILES\n        __init__.py\n\n",
         "")


def plant_libcanon_overview_unlisted(root):
    # overview.dox exists but the DOXYGEN_FILES section is omitted entirely.
    _sub(_p(root, "CMakeLists.txt"),
         "    DOXYGEN_FILES\n        overview.dox\n",
         "")


# --- LIB-CANON: discovery loudness (review item 1) ------------------------

def plant_discovery_uppercase_call(root):
    # CMake command names are case-insensitive: the library must still be
    # discovered, proven by a planted violation being found.
    _sub(_p(root, "CMakeLists.txt"), "pxr_library(fixBase",
         "PXR_LIBRARY(fixBase")
    shutil.rmtree(_p(root, "testenv"))


def plant_discovery_undiscoverable(root):
    # Library-shaped dir (api.h/wrap*.cpp/testenv all present) whose
    # CMakeLists has no pxr_library call at all: silence would drop it out of
    # every per-library rule — must be a loud finding instead.
    with open(_p(root, "CMakeLists.txt"), "w", encoding="utf-8") as f:
        f.write("add_library(fixBase widget.cpp)\n")


_NESTED_API_H = """\
#ifndef AECO_BASE_CMAKE_FIXNESTED_API_H
#define AECO_BASE_CMAKE_FIXNESTED_API_H

#include "pxr/base/arch/export.h"

#if defined(PXR_STATIC)
#   define FIXNESTED_API
#   define FIXNESTED_LOCAL
#else
#   if defined(FIXNESTED_EXPORTS)
#       define FIXNESTED_API ARCH_EXPORT
#   else
#       define FIXNESTED_API ARCH_IMPORT
#   endif
#   define FIXNESTED_LOCAL ARCH_HIDDEN
#endif

#endif // AECO_BASE_CMAKE_FIXNESTED_API_H
"""


def plant_discovery_nested_under_cmake(root):
    # A library nested beneath a dir named "cmake" under aeco/ must still be
    # discovered (the review flagged the old prune list). Its planted
    # violations (no overview.dox, no testenv/) prove discovery happened —
    # a pruned walk would report nothing at all.
    d = os.path.join(root, "aeco", "base", "cmake", "fixNested")
    os.makedirs(d)
    with open(os.path.join(d, "CMakeLists.txt"), "w", encoding="utf-8") as f:
        f.write("set(PXR_PREFIX aeco/base/cmake)\n"
                "set(PXR_PACKAGE fixNested)\n\n"
                "pxr_library(fixNested\n"
                "    LIBRARIES\n"
                "        tf\n"
                ")\n")
    with open(os.path.join(d, "api.h"), "w", encoding="utf-8") as f:
        f.write(_NESTED_API_H)


# --- NAMING ---------------------------------------------------------------

def plant_naming_bad_guard(root):
    _sub(_p(root, "widget.h"),
         "AECO_BASE_FIXBASE_WIDGET_H", "AECO_FIXBASE_WIDGET_H", count=2)


def plant_naming_dead_outer_guard(root):
    # Review item 4's construction: a WRONG outer guard, with the expected
    # #ifndef/#define pair buried in a dead #if 0 block. Present-anywhere
    # passed this; the structural outer-frame check must red it.
    _sub(_p(root, "widget.h"),
         "#ifndef AECO_BASE_FIXBASE_WIDGET_H\n"
         "#define AECO_BASE_FIXBASE_WIDGET_H\n",
         "#ifndef WRONG_FIXBASE_WIDGET_H\n"
         "#define WRONG_FIXBASE_WIDGET_H\n"
         "#if 0\n"
         "#ifndef AECO_BASE_FIXBASE_WIDGET_H\n"
         "#define AECO_BASE_FIXBASE_WIDGET_H\n"
         "#endif\n"
         "#endif\n")


def plant_naming_degenerate_guard(root):
    # Rev-2 review's novel construction, verbatim: the correct #ifndef/#define
    # pair immediately closed by #endif, with the ENTIRE body after it. The
    # first-two-directives check passed this; the guard-encloses-the-file
    # check (conditional-nesting walk) must red it.
    _sub(_p(root, "widget.h"),
         "#ifndef AECO_BASE_FIXBASE_WIDGET_H\n"
         "#define AECO_BASE_FIXBASE_WIDGET_H\n",
         "#ifndef AECO_BASE_FIXBASE_WIDGET_H\n"
         "#define AECO_BASE_FIXBASE_WIDGET_H\n"
         "#endif\n")
    _sub(_p(root, "widget.h"),
         "\n#endif // AECO_BASE_FIXBASE_WIDGET_H\n", "\n")


def plant_naming_guard_never_closed(root):
    # The guard's #endif is missing entirely.
    _sub(_p(root, "widget.h"),
         "\n#endif // AECO_BASE_FIXBASE_WIDGET_H\n", "\n")


def plant_naming_bad_class_prefix(root):
    _sub(_p(root, "widget.h"), "class AecoWidget", "class Widget")


# --- SCOPE ----------------------------------------------------------------

def plant_scope_unpaired(root):
    _sub(_p(root, "widget.cpp"), "PXR_NAMESPACE_CLOSE_SCOPE\n", "", count=1)


def plant_scope_commented_close(root):
    # Review item 5's construction: the CLOSE token survives only inside a
    # comment. Raw-substring presence passed this; the stripped-buffer
    # pairing must red it.
    _sub(_p(root, "widget.cpp"),
         "PXR_NAMESPACE_CLOSE_SCOPE", "// PXR_NAMESPACE_CLOSE_SCOPE")


def plant_scope_header_no_namespace(root):
    _sub(_p(root, "widget.h"), "PXR_NAMESPACE_OPEN_SCOPE\n", "")
    _sub(_p(root, "widget.h"), "PXR_NAMESPACE_CLOSE_SCOPE\n", "")


def plant_scope_missing_pxr_include(root):
    # Review item 5: deleting the include entirely must be a finding, not a
    # skipped ordering check.
    _sub(_p(root, "widget.h"), '#include "pxr/pxr.h"\n', "")


def plant_scope_pxr_not_first(root):
    _sub(_p(root, "widget.cpp"),
         '#include "pxr/pxr.h"\n#include "aeco/base/fixBase/widget.h"',
         '#include "aeco/base/fixBase/widget.h"\n#include "pxr/pxr.h"')


# --- B16 ------------------------------------------------------------------

def plant_b16_schema_registration(root):
    import json
    p = _p(root, "plugInfo.json")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    data["Plugins"][0]["Info"]["Types"] = {
        "UsdFixBaseWidgetAPI": {
            "alias": {"UsdSchemaBase": "FixBaseWidgetAPI"},
            "autoGenerated": True,
            "bases": ["UsdAPISchemaBase"],
            "schemaIdentifier": "FixBaseWidgetAPI",
            "schemaKind": "singleApplyAPI",
        }
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def plant_b16_schema(root):
    with open(_p(root, "schema.usda"), "w", encoding="utf-8") as f:
        f.write("#usda 1.0\n")


# --- DIAG -----------------------------------------------------------------

def plant_diag_fprintf(root):
    _inject_widget_cpp(root, 'fprintf(stderr, "boom\\n");')


def plant_diag_printf(root):
    _inject_widget_cpp(root, 'printf("boom\\n");')


def plant_diag_cerr(root):
    _inject_widget_cpp(root, 'std::cerr << "boom\\n";')


def plant_diag_printf_split_paren(root):
    # Review item 2: the call parenthesis on the next physical line.
    _inject_widget_cpp(root, 'printf\n        ("boom\\n");')


def plant_diag_fprintf_split_stderr(root):
    # Review item 2: stderr on the next physical line.
    _inject_widget_cpp(root, 'fprintf(\n        stderr, "boom\\n");')


def plant_diag_spliced_identifier(root):
    # Review item 2: the identifier itself split by a backslash-newline
    # splice — the compiler sees `printf(`.
    _inject_widget_cpp(root, 'pri\\\nntf("boom\\n");')


def plant_diag_after_raw_string(root):
    # Review item 3's hiding construction: R"x(")x" left the old lexer in a
    # bogus string state that swallowed the real call after it.
    _inject_widget_cpp(root,
                       'const char *r = R"x(")x"; printf("boom\\n"); (void)r;')


def plant_diag_marker_inside_string(root):
    # Review item 3: the allow marker inside an ordinary STRING must not
    # suppress — only a genuine comment is a sanctioned exception.
    _inject_widget_cpp(root,
                       'const char *mk = "aeco-lint: allow-raw-output";\n'
                       '    std::cerr << mk;')


# --- PLUGINFO -------------------------------------------------------------

def plant_pluginfo_bad_json(root):
    _sub(_p(root, "plugInfo.json"),
         '"Type": "library"', '"Type": "library",,')


def plant_pluginfo_structural(root):
    # 'bases' must be a list; make it a string.
    import json
    p = _p(root, "plugInfo.json")
    with open(p) as f:
        d = json.load(f)
    d["Plugins"][0]["Info"]["Types"] = {"AecoFoo": {"bases": "NotAList"}}
    with open(p, "w") as f:
        json.dump(d, f, indent=4)


# --------------------------------------------------------------------------
# The mutation table: (test-name, planter, expected-rule-id, message-substr).
# One row == one red fixture with one planted violation. The substring pins
# WHICH finding fired, not merely which rule.
# --------------------------------------------------------------------------

REDS = [
    # LIB-CANON: canon file set
    ("libcanon_missing_overview", plant_libcanon_missing_overview,
     "LIB-CANON", "missing overview.dox"),
    ("libcanon_missing_init", plant_libcanon_missing_init,
     "LIB-CANON", "__init__.py but the file is missing"),
    ("libcanon_missing_module", plant_libcanon_missing_module,
     "LIB-CANON", "module.cpp but the file is missing"),
    ("libcanon_missing_testenv", plant_libcanon_missing_testenv,
     "LIB-CANON", "missing testenv/"),
    ("libcanon_bad_init_idiom", plant_libcanon_bad_init_idiom,
     "LIB-CANON", "PreparePythonModule"),
    # LIB-CANON: api.h invariants, one per fixture (review item 6)
    ("api_no_pxr_static", plant_api_no_pxr_static,
     "LIB-CANON", "PXR_STATIC"),
    ("api_no_macro_define", plant_api_no_macro_define,
     "LIB-CANON", "does not define FIXBASE_API"),
    ("api_no_arch_export", plant_api_no_arch_export,
     "LIB-CANON", "no ARCH_EXPORT"),
    ("api_no_arch_import", plant_api_no_arch_import,
     "LIB-CANON", "no ARCH_IMPORT"),
    # LIB-CANON: iff in both directions (review item 6)
    ("libcanon_stray_module", plant_libcanon_stray_module,
     "LIB-CANON", "module.cpp is present but PYMODULE_CPPFILES is not used"),
    ("libcanon_stray_init", plant_libcanon_stray_init,
     "LIB-CANON", "__init__.py is present but PYMODULE_FILES is not used"),
    ("libcanon_overview_unlisted", plant_libcanon_overview_unlisted,
     "LIB-CANON", "not listed in DOXYGEN_FILES"),
    # LIB-CANON: discovery loudness (review item 1)
    ("discovery_uppercase_call", plant_discovery_uppercase_call,
     "LIB-CANON", "missing testenv/"),
    ("discovery_undiscoverable", plant_discovery_undiscoverable,
     "LIB-CANON", "no parseable pxr_library"),
    ("discovery_nested_under_cmake", plant_discovery_nested_under_cmake,
     "LIB-CANON", "missing testenv/"),
    # NAMING
    ("naming_bad_guard", plant_naming_bad_guard,
     "NAMING", "include guard is AECO_FIXBASE_WIDGET_H"),
    ("naming_dead_outer_guard", plant_naming_dead_outer_guard,
     "NAMING", "include guard is WRONG_FIXBASE_WIDGET_H"),
    ("naming_degenerate_guard", plant_naming_degenerate_guard,
     "NAMING", "guards nothing"),
    ("naming_guard_never_closed", plant_naming_guard_never_closed,
     "NAMING", "never closed"),
    ("naming_bad_class_prefix", plant_naming_bad_class_prefix,
     "NAMING", "lacks the capitalized library prefix"),
    # SCOPE
    ("scope_unpaired", plant_scope_unpaired,
     "SCOPE", "OPEN_SCOPE without a matching"),
    ("scope_commented_close", plant_scope_commented_close,
     "SCOPE", "OPEN_SCOPE without a matching"),
    ("scope_header_no_namespace", plant_scope_header_no_namespace,
     "SCOPE", "does not open the pxr namespace"),
    ("scope_missing_pxr_include", plant_scope_missing_pxr_include,
     "SCOPE", "does not include pxr/pxr.h"),
    ("scope_pxr_not_first", plant_scope_pxr_not_first,
     "SCOPE", "must be the first project include"),
    # B16
    ("b16_schema_registration", plant_b16_schema_registration,
     "B16", "registers schema type(s) UsdFixBaseWidgetAPI"),
    ("b16_schema", plant_b16_schema,
     "B16", "'schema.usda'"),
    # DIAG
    ("diag_fprintf", plant_diag_fprintf, "DIAG", "fprintf(stderr"),
    ("diag_printf", plant_diag_printf, "DIAG", "printf(...)"),
    ("diag_cerr", plant_diag_cerr, "DIAG", "std::cerr"),
    # DIAG: review item 2 constructions (legal formatting)
    ("diag_printf_split_paren", plant_diag_printf_split_paren,
     "DIAG", "printf(...)"),
    ("diag_fprintf_split_stderr", plant_diag_fprintf_split_stderr,
     "DIAG", "fprintf(stderr"),
    ("diag_spliced_identifier", plant_diag_spliced_identifier,
     "DIAG", "printf(...)"),
    # DIAG: review item 3 constructions (lexer honesty)
    ("diag_after_raw_string", plant_diag_after_raw_string,
     "DIAG", "printf(...)"),
    ("diag_marker_inside_string", plant_diag_marker_inside_string,
     "DIAG", "std::cerr"),
    # PLUGINFO
    ("pluginfo_bad_json", plant_pluginfo_bad_json,
     "PLUGINFO", "does not parse as JSON"),
    ("pluginfo_structural", plant_pluginfo_structural,
     "PLUGINFO", "must be a list"),
]


class _TmpTreeCase(unittest.TestCase):
    """Shared fixture factory; carries no tests of its own."""

    def _make_repo(self, planter=None):
        tmp = tempfile.mkdtemp(prefix="aecolint-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        dst = os.path.join(tmp, "repo")
        shutil.copytree(_CLEAN, dst)
        # copytree preserves mode bits; when the fixture source is read-only
        # (e.g. served from the nix store during `nix flake check`), make the
        # working copy writable so planters can mutate it.
        _make_writable(dst)
        if planter is not None:
            planter(dst)
        return dst


class _FixtureCase(_TmpTreeCase):
    """Host for the generated one-planted-violation red tests."""


def _make_red_test(planter, expected_rule, expected_substr):
    def test(self):
        repo = self._make_repo(planter)
        findings = lint.lint(repo)
        rules = sorted({f.rule for f in findings})
        listing = "\n".join(f.format(repo) for f in findings)
        self.assertTrue(
            findings,
            "expected a {} finding, got a clean run".format(expected_rule))
        # The planted violation is the ONLY rule that fires.
        self.assertEqual(
            rules, [expected_rule],
            "planted a single {} violation but rules fired: {}\n{}".format(
                expected_rule, rules, listing))
        # And the finding is the RIGHT one, by message.
        messages = " | ".join(
            f.message for f in findings if f.rule == expected_rule)
        self.assertIn(
            expected_substr, messages,
            "expected a {} finding whose message contains {!r}; got:\n{}"
            .format(expected_rule, expected_substr, listing))
    return test


# Attach one test method per red fixture.
for _name, _planter, _rule, _substr in REDS:
    setattr(_FixtureCase, "test_red_" + _name,
            _make_red_test(_planter, _rule, _substr))


class CleanSideCase(_TmpTreeCase):
    """Constructions that must stay CLEAN — the false-positive half of the
    review's evasion corpus, plus the sanctioned escape hatch."""

    def _assert_clean(self, planter, why):
        repo = self._make_repo(planter)
        findings = lint.lint(repo)
        self.assertEqual(
            findings, [],
            why + "; findings:\n" +
            "\n".join(f.format(repo) for f in findings))

    def test_uppercase_pxr_library_is_discovered_and_clean(self):
        # Case-only spelling of the command with an intact tree: discovered
        # (no undiscoverable finding) and canon-clean.
        def planter(root):
            _sub(_p(root, "CMakeLists.txt"),
                 "pxr_library(fixBase", "PXR_LIBRARY(fixBase")
        self._assert_clean(
            planter, "a case-only pxr_library spelling must lint clean")

    def test_generated_schema_consumer_artifact_is_clean(self):
        def planter(root):
            with open(_p(root, "generatedSchema.usda"), "w",
                      encoding="utf-8") as f:
                f.write("#usda 1.0\n")
        self._assert_clean(
            planter,
            "a consumed generatedSchema.usda is not schema authorship")

    def test_non_schema_type_registration_is_clean(self):
        def planter(root):
            import json
            p = _p(root, "plugInfo.json")
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            data["Plugins"][0]["Info"]["Types"] = {
                "FixBaseFileFormat": {
                    "bases": ["SdfFileFormat"],
                    "extensions": ["fix"],
                }
            }
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        self._assert_clean(
            planter,
            "a processing plugin Type is not a schema type registration")

    def test_raw_string_containing_printf_is_clean(self):
        # Review item 3's false-positive construction: `" printf(` INSIDE a
        # raw string is data, not a call.
        def planter(root):
            _inject_widget_cpp(
                root,
                'const char *t = R"( " printf("boom") )"; (void)t;')
        self._assert_clean(
            planter, "printf text inside a raw string literal must not fire")

    def test_backslash_continued_comment_is_clean(self):
        # Review item 3: a `//` comment ending in a backslash swallows the
        # next physical line (C++ splices before comment removal); the
        # swallowed printf is commentary, not code.
        def planter(root):
            _inject_widget_cpp(
                root,
                '// the next physical line is part of this comment \\\n'
                '    printf("boom\\n");')
        self._assert_clean(
            planter,
            "a printf swallowed by a backslash-continued comment is not code")

    def test_allow_marker_in_comment_is_honored(self):
        # The sanctioned escape hatch: a genuine comment marker on the line
        # above suppresses the finding on the next line.
        def planter(root):
            _inject_widget_cpp(
                root,
                '// aeco-lint: allow-raw-output\n'
                '    fprintf(stderr, "sanctioned\\n");')
        self._assert_clean(
            planter, "the allow marker in a genuine comment must suppress")

    def test_inner_conditional_block_inside_guard_is_clean(self):
        # Rev-2 counter-case: legitimate inner #if/#endif blocks inside the
        # guard nest and unwind without touching depth 0 — the guard's own
        # #endif still closes the file, so this must stay clean (api.h's
        # PXR_STATIC ladder is the canonical real instance).
        def planter(root):
            _sub(_p(root, "widget.h"),
                 "#include <string>\n",
                 "#include <string>\n\n"
                 "#if defined(FIXBASE_EXTRA_FEATURE)\n"
                 "#include <vector>\n"
                 "#endif\n")
        self._assert_clean(
            planter,
            "an inner conditional block inside the guard must not red the "
            "guard-encloses-the-file check")

    def test_digit_separator_is_not_a_char_literal(self):
        # C++14 digit separators must not open a bogus char-literal region
        # that hides following code from the rules.
        def planter(root):
            _inject_widget_cpp(
                root,
                'const long big = 1\'000\'000; std::cerr << big;')
        repo = self._make_repo(planter)
        findings = lint.lint(repo)
        rules = sorted({f.rule for f in findings})
        self.assertEqual(rules, ["DIAG"],
                         "the cerr after digit separators must still fire:\n" +
                         "\n".join(f.format(repo) for f in findings))


class CleanAndConsumerCase(unittest.TestCase):
    def test_clean_fixture_passes(self):
        findings = lint.lint(_CLEAN)
        self.assertEqual(
            findings, [],
            "the clean fixture must lint clean; findings:\n{}".format(
                "\n".join(f.format(_CLEAN) for f in findings)))

    def test_toolchain_repo_passes(self):
        # This repo carries no aeco/*/ library, but B16/PLUGINFO still walk it.
        findings = lint.lint(_REPO)
        self.assertEqual(
            findings, [],
            "the toolchain repo must lint clean; findings:\n{}".format(
                "\n".join(f.format(_REPO) for f in findings)))

    def test_consumer_core_passes_if_present(self):
        # The reviewed consumer skeleton (aeco-core packet/2) must pass as-is.
        # Located as a sibling of the toolchain checkout; skipped if absent so
        # the suite stays hermetic in CI/Nix where only this repo is checked
        # out. Do not probe a fixed host path from a sandboxed flake check.
        candidates = [
            os.path.normpath(os.path.join(_REPO, "..", "core")),
        ]
        core = next((c for c in candidates
                     if os.path.isdir(os.path.join(c, "aeco"))), None)
        if core is None:
            self.skipTest("aeco-core checkout not present beside toolchain")
        findings = lint.lint(core)
        self.assertEqual(
            findings, [],
            "aeco-core (the reviewed skeleton) must lint clean; findings:\n{}"
            .format("\n".join(f.format(core) for f in findings)))


class HarnessScopeCase(unittest.TestCase):
    """Pins the DIAG scope decision (P0-9): the linter governs the library
    canon — pxr_library dirs under aeco/. Standalone harness code (spike/probe
    executables, like the toolchain's spike/) prints by contract and must NOT
    be flagged; widening DIAG onto it must be a deliberate, reviewed change
    that updates this test."""

    def test_spike_like_harness_code_is_exempt(self):
        tmp = tempfile.mkdtemp(prefix="aecolint-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        repo = os.path.join(tmp, "repo")
        shutil.copytree(_CLEAN, repo)
        _make_writable(repo)
        # A spike-shaped standalone executable outside aeco/: raw stdio is its
        # interface (the flake check greps its stdout), plain CMake, no
        # pxr_library — the canon does not govern it.
        spike = os.path.join(repo, "spike", "host")
        os.makedirs(spike)
        with open(os.path.join(spike, "main.cpp"), "w", encoding="utf-8") as f:
            f.write("#include <iostream>\n"
                    "int main() {\n"
                    "    std::cerr << \"usage: probe SHIM OUT\\n\";\n"
                    "    std::cout << \"embed coexistence spike OK\\n\";\n"
                    "    return 0;\n"
                    "}\n")
        with open(os.path.join(spike, "CMakeLists.txt"), "w",
                  encoding="utf-8") as f:
            f.write("add_executable(probe main.cpp)\n")
        findings = lint.lint(repo)
        self.assertEqual(
            findings, [],
            "spike-like harness code must be exempt (DIAG scope decision); "
            "findings:\n{}".format(
                "\n".join(f.format(repo) for f in findings)))


class GuardDerivationCase(unittest.TestCase):
    """The RATIFIED guard scheme, pinned to the exemplars and the skeleton."""

    def test_expected_guard(self):
        root = "/repo"
        cases = {
            "aeco/base/aecoBase/version.h": "AECO_BASE_AECOBASE_VERSION_H",
            "aeco/base/aecoBase/api.h": "AECO_BASE_AECOBASE_API_H",
            "aeco/base/aecoBase/debugCodes.h": "AECO_BASE_AECOBASE_DEBUG_CODES_H",
            "aeco/usd/aecoValidators/validatorTokens.h":
                "AECO_USD_AECOVALIDATORS_VALIDATOR_TOKENS_H",
        }
        for path, want in cases.items():
            got = lint.expected_guard(root, os.path.join(root, path))
            self.assertEqual(got, want, path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
