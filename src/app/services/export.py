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
from app.core.models import DeductionLink, Invoice
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

        # --- Prepare deduction explanations ---
        deduction_info = {}
        for detail in billing_details.values():
            # Check if this meter is a PARENT in a link
            if detail.manual_adjustment > 0:
                link = await DeductionLink.filter(
                    parent_meter_id=detail.meter.id
                ).first()
                if link:
                    deduction_info[detail.meter.id] = {
                        "type": "parent",
                        "description": link.description,
                    }

            # Check if this meter is a CHILD in a link
            link = await DeductionLink.filter(child_meter_id=detail.meter.id).first()
            if link:
                await link.fetch_related("parent_meter__tenant")
                parent_meter = link.parent_meter
                parent_tenant = parent_meter.tenant
                deduction_info[detail.meter.id] = {
                    "type": "child",
                    "parent_info": (
                        f"{parent_tenant.name} " f"(счётчик «{parent_meter.name}»)"
                    ),
                }
        # --- End of explanations ---

        # Aggregate totals per tariff type
        totals_by_rate_type: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for detail in billing_details.values():
            key = detail.tariff.name or "default"
            totals_by_rate_type[key] += detail.cost

        rendered_html = template.render(
            invoice=invoice,
            tenant=invoice.tenant,
            period=invoice.period.strftime("%B %Y"),
            details=details_with_str_keys,
            totals_by_rate_type=totals_by_rate_type,
            deduction_info=deduction_info,
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

        # --- Prepare deduction explanations for all tenants ---
        for report_item in summary_data:
            report_item["deduction_info"] = {}
            for detail in report_item["details"]:
                meter_id = detail.meter.id
                # Check if this meter is a PARENT in a link
                if detail.manual_adjustment > 0:
                    link = await DeductionLink.filter(parent_meter_id=meter_id).first()
                    if link:
                        report_item["deduction_info"][meter_id] = {
                            "type": "parent",
                            "description": link.description,
                        }

                # Check if this meter is a CHILD in a link
                link = await DeductionLink.filter(child_meter_id=meter_id).first()
                if link:
                    await link.fetch_related("parent_meter__tenant")
                    parent_meter = link.parent_meter
                    parent_tenant = parent_meter.tenant
                    report_item["deduction_info"][meter_id] = {
                        "type": "child",
                        "parent_info": (
                            f"{parent_tenant.name} " f"(счётчик «{parent_meter.name}»)"
                        ),
                    }
        # --- End of explanations ---

        rendered_html = template.render(
            period=format_period_for_display(period),
            summary_data=summary_data,
            grand_total=grand_total,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        HTML(string=rendered_html).write_pdf(output_path)

        return output_path
