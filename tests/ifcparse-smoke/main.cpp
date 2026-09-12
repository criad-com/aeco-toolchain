#include <ifcparse/IfcFile.h>

#include <cstddef>
#include <iostream>

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: aeco-ifcparse-smoke <file.ifc>\n";
        return 2;
    }

    IfcParse::IfcFile file(argv[1]);
    if (!file.good()) {
        std::cerr << "IfcParse failed to open " << argv[1] << '\n';
        return 3;
    }

    const aggregate_of_instance::ptr roots = file.instances_by_type("IfcRoot");
    const std::size_t count = roots ? roots->size() : 0;
    std::cout << "IfcParse smoke OK: IfcRoot-derived entities=" << count << '\n';

    return count > 0 ? 0 : 4;
}
