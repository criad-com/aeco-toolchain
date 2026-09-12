# Optional shared geometry stack; the parsing-only derivation is unchanged.
{ lib, ifcopenshell-cpp, occt, eigen }:
ifcopenshell-cpp.overrideAttrs (old: {
  pname = "ifcopenshell-cpp-geom";
  propagatedBuildInputs = old.propagatedBuildInputs ++ [ occt eigen ];
  cmakeFlags = builtins.filter (flag: !(builtins.elem flag [
    "-DBUILD_IFCGEOM=OFF" "-DWITH_OPENCASCADE=OFF"
  ])) old.cmakeFlags ++ [
    "-DBUILD_IFCGEOM=ON"
    "-DWITH_OPENCASCADE=ON"
  ];
  postPatch = old.postPatch + ''
    substituteInPlace cmake/IfcOpenShellConfig.cmake.in \
      --replace-fail '# IfcParse-only builds do not export or use Eigen targets.' \
        'find_dependency(Eigen3 CONFIG)'
  '';
  postFixup = ''
    test -d "$out/include/ifcgeom"
    test -f "$out/lib/cmake/IfcOpenShell/IfcOpenShellConfig.cmake"
    test -n "$(find "$out/lib" -name 'libIfcGeom.*' -print -quit)"
    test -n "$(find "$out/lib" -name 'libgeometry_kernel_opencascade.*' -print -quit)"
    if find "$out" -name '*.a' -print -quit | grep -q .; then
      echo "IfcOpenShell geometry must remain shared-only" >&2
      exit 1
    fi
  '';
  meta = old.meta // {
    description = "IfcOpenShell C++ geometry with shared OCCT, without CGAL or Python";
  };
})
