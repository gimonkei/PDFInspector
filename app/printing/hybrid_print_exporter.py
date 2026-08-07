from app.printing.vector_print_exporter import VectorPrintExporter


class HybridPrintExporter(VectorPrintExporter):
    """Preserve original PDF vectors and rasterize only special annotations."""
