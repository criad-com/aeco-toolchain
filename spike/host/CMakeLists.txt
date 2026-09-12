cmake_minimum_required(VERSION 3.24)
project(aeco_embed_host LANGUAGES CXX)

find_package(pxr CONFIG REQUIRED)

add_executable(aeco-embed-host main.cpp)
target_compile_features(aeco-embed-host PRIVATE cxx_std_17)
target_include_directories(aeco-embed-host PRIVATE "${PXR_INCLUDE_DIRS}")
target_link_libraries(aeco-embed-host PRIVATE sdf ${CMAKE_DL_LIBS})

install(TARGETS aeco-embed-host RUNTIME DESTINATION bin)
