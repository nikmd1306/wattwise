"""Service for exporting data to different formats like PDF or Excel."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.core.models import Invoice


class ExportService:
    """Handles exporting invoice data to files."""

    def __init__(self):
        template_dir = Path(__file__).parent.parent / "templates"
        self._env = Environment(loader=FileSystemLoader(template_dir))

    async def generate_pdf_invoice(
        self, invoice: Invoice, output_path: Path | str
    ) -> Path:
        """
        Generates a PDF invoice from an Invoice object.

        Args:
            invoice: The Invoice object containing the data.
            output_path: The path where the PDF file will be saved.

        Returns:
            The path to the generated PDF file.
        """
        await invoice.fetch_related("tenant")
        template = self._env.get_template("invoice.html")

        rendered_html = template.render(
            invoice=invoice,
            tenant=invoice.tenant,
            period=invoice.period.strftime("%B %Y"),
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        HTML(string=rendered_html).write_pdf(output_path)

        return output_path
