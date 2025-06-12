"""Service for exporting data to different formats like PDF or Excel."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID
from collections import defaultdict
from decimal import Decimal
from datetime import date

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.core.dates import format_period_for_display
from app.core.models import Invoice
from app.services.billing import MeterBillingResult


class ExportService:
    """Handles exporting invoice data to files."""

    def __init__(self):
        template_dir = Path(__file__).parent.parent / "templates"
        self._env = Environment(loader=FileSystemLoader(template_dir))

    async def generate_pdf_invoice(
        self,
        invoice: Invoice,
        billing_details: dict[UUID, MeterBillingResult],
        output_path: Path | str,
    ) -> Path:
        """
        Generates a PDF invoice from an Invoice object and detailed billing data.

        Args:
            invoice: The Invoice object containing the data.
            billing_details: A dictionary with detailed calculation results per meter.
            output_path: The path where the PDF file will be saved.

        Returns:
            The path to the generated PDF file.
        """
        await invoice.fetch_related("tenant")
        template = self._env.get_template("invoice.html")

        # Convert UUID keys to strings for Jinja2 compatibility
        details_with_str_keys = {
            str(key): value for key, value in billing_details.items()
        }

        # Aggregate totals per tariff type
        totals_by_rate_type: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for detail in billing_details.values():
            key = detail.tariff.rate_type or "default"
            totals_by_rate_type[key] += detail.cost

        rendered_html = template.render(
            invoice=invoice,
            tenant=invoice.tenant,
            period=invoice.period.strftime("%B %Y"),
            details=details_with_str_keys,
            totals_by_rate_type=totals_by_rate_type,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        HTML(string=rendered_html).write_pdf(output_path)

        return output_path

    async def generate_pdf_summary(
        self,
        period: date,
        summary_data: list[dict],
        grand_total: Decimal,
        output_path: Path | str,
    ) -> Path:
        """
        Generates a PDF summary report.

        Args:
            period: The reporting period.
            summary_data: A list of dicts, each containing tenant data.
            grand_total: The grand total for the report.
            output_path: The path where the PDF file will be saved.

        Returns:
            The path to the generated PDF file.
        """
        template = self._env.get_template("summary_report.html")

        rendered_html = template.render(
            period=format_period_for_display(period),
            summary_data=summary_data,
            grand_total=grand_total,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        HTML(string=rendered_html).write_pdf(output_path)

        return output_path
