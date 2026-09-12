set(PXR_PREFIX aeco/base)
set(PXR_PACKAGE fixBase)

pxr_library(fixBase
    LIBRARIES
        tf

    PUBLIC_CLASSES
        widget

    PUBLIC_HEADERS
        api.h

    PRIVATE_CLASSES
        debugCodes

    PYMODULE_CPPFILES
        module.cpp
        wrapWidget.cpp

    PYMODULE_FILES
        __init__.py

    DOXYGEN_FILES
        overview.dox
)

pxr_test_scripts(
    testenv/testFixBaseWidget.py
)

pxr_register_test(testFixBaseWidget
    PYTHON
    COMMAND "${CMAKE_INSTALL_PREFIX}/tests/testFixBaseWidget"
    EXPECTED_RETURN_CODE 0
)
