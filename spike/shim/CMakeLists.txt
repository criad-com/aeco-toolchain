cmake_minimum_required(VERSION 3.24)
project(aeco_embed_shim LANGUAGES CXX)

find_package(pxr CONFIG REQUIRED)

add_library(aeco_embed_probe SHARED aeco_embed_probe.cpp)
target_compile_features(aeco_embed_probe PRIVATE cxx_std_17)
target_include_directories(aeco_embed_probe
    PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}"
        "${PXR_INCLUDE_DIRS}"
)

# Whole-archive is mandatory for USD registry constructors, including the
# built-in Sdf file formats.  usd_m is PIC in OpenUSD's monolithic static mode.
target_link_libraries(aeco_embed_probe
    PRIVATE
        "$<LINK_LIBRARY:WHOLE_ARCHIVE,usd_m>"
)

set_target_properties(aeco_embed_probe PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
)

# Keep the dylib boundary to the intended C ABI.  The static OpenUSD symbols
# remain present locally, under aecoEmbed_v1, but do not enter the export trie.
if(APPLE)
    target_link_options(aeco_embed_probe PRIVATE
        "LINKER:-exported_symbols_list,${CMAKE_CURRENT_SOURCE_DIR}/exports.txt"
    )
elseif(UNIX)
    target_link_options(aeco_embed_probe PRIVATE
        "LINKER:--version-script=${CMAKE_CURRENT_SOURCE_DIR}/exports.map"
    )
endif()

install(TARGETS aeco_embed_probe
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION lib
)
install(FILES aeco_embed_probe.h DESTINATION include)
