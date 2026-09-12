cmake_minimum_required(VERSION 3.21)
project(aeco_ifcparse_smoke LANGUAGES CXX)

find_package(IfcOpenShell CONFIG REQUIRED)

add_executable(aeco-ifcparse-smoke main.cpp)
target_compile_features(aeco-ifcparse-smoke PRIVATE cxx_std_17)
target_link_libraries(aeco-ifcparse-smoke PRIVATE IfcOpenShell::IfcParse)
