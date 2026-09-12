# Standalone MSVC-enclave build of aecoLandingC.dll (P4 recon).
#
# USAGE: this scaffold lives in aeco-toolchain but compiles aeco-core SOURCES.
# Copy aeco-core's `aeco/base` and `aeco/vendor` trees beside this file (so the
# repo root — the dir holding this CMakeLists — has `aeco/base/...` under it and
# the in-tree includes "aeco/base/aecoLanding/landingBuilder.h" resolve), then
# run build_msvc.cmd on example-navis. See RECON.md.
#
#
# This is the PRAGMATIC "dev-flavor" wiring: it compiles the aeco source
# closure (the same TU set as the AECO_LANDINGC_BUILD_EMBED stanza in
# aeco-core) directly INTO the DLL and links the prebuilt SHARED OpenUSD on
# example-navis (C:\OpenUSD) via its import libraries. It is NOT the production
# static-embed (usd_m / PXR_STATIC / aecoEmbed_v1) wiring — see the recon
# report for why that is a separate, larger effort. Its job is to prove the
# sources compile under MSVC 14.44 against real pxr headers and that the DLL
# exports resolve to exactly the 19-symbol aeco_landing_* ABI v2 (dumpbin;
# the 19th is aeco_landing_set_mesh, aeco-meta #96).
cmake_minimum_required(VERSION 3.24)
project(aecoLandingC_msvc LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# The prebuilt OpenUSD install root on example-navis (shared, python-on, v0.26.5).
set(OPENUSD_ROOT "C:/OpenUSD" CACHE PATH "Prebuilt OpenUSD install root")

# The prebuilt USD bakes PXR_PYTHON_SUPPORT_ENABLED into pxr/pxr.h, so any TU
# that transitively includes a Tf header pulling boost.python (via
# landingBuilder.h / sdf) needs Python's headers (pyconfig.h). Python 3.11 is
# installed on example-navis; point at its include/libs. (The production static-embed
# build is python-FREE and would not need this — this is a dev-flavor recon
# against the python-on prebuilt.)
set(PYTHON_ROOT "$ENV{PYTHON_ROOT}"
    CACHE PATH "Python 3.11 root providing pyconfig.h")

# find_package(pxr) would pull the full imaging/monolithic target soup and can
# be brittle across the 0.26.5-vs-pin skew; for a bounded recon we wire the
# handful of import libs the closure actually needs, by name.
set(_pxr_inc "${OPENUSD_ROOT}/include")
set(_pxr_lib "${OPENUSD_ROOT}/lib")

# The DLL source closure — identical to aeco-core's embed stanza (source-
# closure audit lives in aecoLandingC/CMakeLists.txt).
add_library(AecoLandingC SHARED
    aeco/base/aecoLandingC/aecoLandingC.cpp
    aeco/base/aecoLanding/landingBuilder.cpp
    aeco/base/aecoLanding/debugCodes.cpp
    aeco/base/aecoBase/identity.cpp
    aeco/base/aecoBase/contentHash.cpp
    aeco/base/aecoBase/profile.cpp
    aeco/base/aecoBase/semantics.cpp
    aeco/base/aecoBase/version.cpp
    aeco/base/aecoBase/debugCodes.cpp
    aeco/vendor/crypto-algorithms/sha256.c
    aeco/vendor/crypto-algorithms/sha1.c
    aeco/base/aecoLandingC/exports.def
)

# AECOLANDINGC_EXPORTS => AECO_LANDING_C_API resolves to __declspec(dllexport)
# for the 19 aeco_landing_* entry points. We do NOT define PXR_STATIC here
# because we link the SHARED USD (its symbols are dllimport'd from usd_*.dll,
# never re-exported from this DLL), so the .def remains the complete export
# story for THIS image. NOMINMAX/WIN32_LEAN_AND_MEAN are the usual USD-on-MSVC
# hygiene. _CRT_SECURE_NO_WARNINGS quiets the vendored C crypto.
target_compile_definitions(AecoLandingC PRIVATE
    AECOLANDINGC_EXPORTS
    NOMINMAX
    WIN32_LEAN_AND_MEAN
    _CRT_SECURE_NO_WARNINGS
    BOOST_ALL_NO_LIB          # USD ships its own boost; don't auto-link
)

# Variant B (AECO_PXR_STATIC=ON): define PXR_STATIC so every pxr ARCH_EXPORT-
# based macro — including the aeco AECOLANDING_API / AECOBASE_API in api.h —
# expands EMPTY. Then no __declspec(dllexport) rides on the compiled-in aeco
# class methods, and exports.def is the COMPLETE export story => exactly the
# 19 aeco_landing_* symbols (the documented MSVC .def-union fix). This is the
# production static-embed compile posture; here we still link SHARED USD import
# libs for the recon, the one deviation from the real usd_m build.
option(AECO_PXR_STATIC "Compile with PXR_STATIC so the .def is the whole export story" OFF)
if (AECO_PXR_STATIC)
    target_compile_definitions(AecoLandingC PRIVATE PXR_STATIC)
endif()

# Repo root on the include path so "aeco/base/..." resolves, then the pxr
# headers.
target_include_directories(AecoLandingC PRIVATE
    ${CMAKE_SOURCE_DIR}
    ${_pxr_inc}
    ${PYTHON_ROOT}/include
)

# USD on MSVC needs a big-object flag for some TUs and the standard exception
# model; /Zc:inline etc. are already USD defaults but harmless to restate.
if (MSVC)
    target_compile_options(AecoLandingC PRIVATE /bigobj /EHsc /Zc:__cplusplus)
endif()

# Link the exact import libs the closure needs (tf/gf/vt/js/sdf/arch) plus the
# transitive USD libs Sdf pulls at link time (plug/ar/trace/work/vt/ts/pegtl).
# Import-lib names on this build are usd_<lib>.lib.
# NOTE (python-on prebuilt): example-navis's OpenUSD bakes PXR_PYTHON_SUPPORT_ENABLED
# into the installed pxr/pxr.h, so TfToken/VtValue inline templates emit
# pxr_boost::python conversion glue that must resolve against usd_python.lib.
# The PRODUCTION static-embed build is python-FREE (PXR_ENABLE_PYTHON_SUPPORT
# =OFF) and never pulls this — usd_python is a dev-prebuilt-only link here.
foreach(_l tf gf vt js sdf arch plug ar trace work ts pegtl kind pcp python)
    set(_p "${_pxr_lib}/usd_${_l}.lib")
    if (EXISTS "${_p}")
        target_link_libraries(AecoLandingC PRIVATE "${_p}")
    endif()
endforeach()
# TBB (USD headers reference it inline in several places).
if (EXISTS "${_pxr_lib}/tbb.lib")
    target_link_libraries(AecoLandingC PRIVATE "${_pxr_lib}/tbb.lib")
endif()
# Python import lib — the boost.python glue pulled by the python-on prebuilt
# may reference Py_* symbols at link time. Harmless if unreferenced.
if (EXISTS "${PYTHON_ROOT}/libs/python311.lib")
    target_link_libraries(AecoLandingC PRIVATE "${PYTHON_ROOT}/libs/python311.lib")
endif()

set_target_properties(AecoLandingC PROPERTIES OUTPUT_NAME AecoLandingC)
