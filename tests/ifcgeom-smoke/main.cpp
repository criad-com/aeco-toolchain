#include <ifcparse/IfcFile.h>
#include <ifcgeom/Iterator.h>
#include <ifcgeom/hybrid_kernel.h>
#include <cmath>
#include <iostream>
#include <limits>

int main(int argc, char** argv)
{
    if (argc != 2) return 1;
    IfcParse::IfcFile file(argv[1]);
    if (!file.good()) return 2;
    ifcopenshell::geometry::Settings settings;
    settings.get<ifcopenshell::geometry::settings::WeldVertices>().value = true;
    IfcGeom::Iterator iterator(ifcopenshell::geometry::kernels::construct(
        &file, "opencascade", settings), settings, &file, {}, 1);
    if (!iterator.initialize()) return 3;
    std::size_t products = 0, vertices = 0, faces = 0;
    do {
        auto mesh = dynamic_cast<const IfcGeom::TriangulationElement*>(iterator.get());
        if (!mesh) return 4;
        const auto& points = mesh->geometry().verts();
        const auto& triangles = mesh->geometry().faces();
        vertices += points.size() / 3;
        faces += triangles.size() / 3;
        double low[3] = {INFINITY, INFINITY, INFINITY};
        double high[3] = {-INFINITY, -INFINITY, -INFINITY};
        for (std::size_t i = 0; i < points.size(); ++i) {
            if (!std::isfinite(points[i])) return 5;
            low[i % 3] = std::min(low[i % 3], points[i]);
            high[i % 3] = std::max(high[i % 3], points[i]);
        }
        const double dimensions[] = {4.0, 0.2, 3.0};
        for (int i = 0; i < 3; ++i)
            if (std::abs(high[i] - low[i] - dimensions[i]) > 1e-7) return 6;
        for (int index : triangles)
            if (index < 0 || static_cast<std::size_t>(index) >= points.size() / 3) return 7;
        ++products;
    } while (iterator.next());
    std::cout << "IfcGeom extruded-wall products=" << products
              << " vertices=" << vertices << " faces=" << faces << '\n';
    return products == 1 && vertices == 8 && faces == 12 ? 0 : 8;
}
