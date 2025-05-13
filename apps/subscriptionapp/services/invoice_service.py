# apps/subscriptionapp/services/invoice_service.py
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.subscriptionapp.models import Subscription, SubscriptionInvoice

logger = logging.getLogger(__name__)


class InvoiceService:
    """Service for handling subscription invoices"""

    @staticmethod
    def generate_invoice_number():
        """Generate a unique invoice number"""
        prefix = "INV"
        date_str = timezone.now().strftime("%Y%m%d")
        random_str = str(uuid.uuid4().hex)[:6].upper()

        return f"{prefix}-{date_str}-{random_str}"

    @staticmethod
    def create_invoice(subscription_id, amount, period_start, period_end, status="pending"):
        """Create a new invoice for a subscription"""
        subscription = Subscription.objects.get(id=subscription_id)

        # Generate invoice number
        invoice_number = InvoiceService.generate_invoice_number()

        # Set due date (default to 7 days from now)
        due_date = timezone.now() + timezone.timedelta(days=7)

        # Create invoice
        invoice = SubscriptionInvoice.objects.create(
            subscription=subscription,
            invoice_number=invoice_number,
            amount=amount,
            status=status,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
        )

        return invoice

    @staticmethod
    def update_invoice_status(invoice_id, new_status, transaction=None, paid_date=None):
        """Update the status of an invoice"""
        invoice = SubscriptionInvoice.objects.get(id=invoice_id)

        invoice.status = new_status

        if transaction:
            invoice.transaction = transaction

        if new_status == "paid" and not invoice.paid_date:
            invoice.paid_date = paid_date or timezone.now()

        invoice.save()

        return invoice

    @staticmethod
    def find_invoice_by_transaction(transaction_id):
        """Find an invoice by its transaction ID"""
        from apps.payment.models import Transaction

        transaction = Transaction.objects.get(id=transaction_id)

        return SubscriptionInvoice.objects.filter(transaction=transaction).first()

    @staticmethod
    def get_company_invoices(company_id):
        """Get all invoices for a company"""
        return SubscriptionInvoice.objects.filter(subscription__company_id=company_id).order_by(
            "-issued_date"
        )

    @staticmethod
    def send_invoice_email(invoice_id):
        """Send invoice email to company"""
        invoice = SubscriptionInvoice.objects.get(id=invoice_id)
        subscription = invoice.subscription
        company = subscription.company

        # Get company contact email
        to_email = company.contact_email
        if not to_email:
            logger.warning(f"Cannot send invoice email: No contact email for company {company.id}")
            return False

        # Prepare email context
        context = {
            "company_name": company.name,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.issued_date,
            "due_date": invoice.due_date,
            "amount": invoice.amount,
            "plan_name": subscription.plan_name or subscription.plan.name,
            "period_start": invoice.period_start,
            "period_end": invoice.period_end,
            "status": invoice.status,
        }

        # Render email templates
        subject = _("Your Queue Me Subscription Invoice {invoice_number}").format(
            invoice_number=invoice.invoice_number
        )

        text_content = render_to_string("subscriptionapp/emails/payment_receipt.txt", context)

        html_content = render_to_string("subscriptionapp/emails/payment_receipt.html", context)

        # Create email message
        from_email = settings.DEFAULT_FROM_EMAIL
        email = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        email.attach_alternative(html_content, "text/html")

        # Attach PDF invoice
        try:
            pdf_file = InvoiceService.generate_invoice_pdf(invoice_id)
            email.attach(
                f"Invoice_{invoice.invoice_number}.pdf",
                pdf_file.read(),
                "application/pdf",
            )
        except Exception as e:
            logger.error(f"Failed to attach PDF invoice: {str(e)}")

        # Send email
        try:
            email.send()
            return True
        except Exception as e:
            logger.error(f"Failed to send invoice email: {str(e)}")
            return False

    @staticmethod
    def generate_invoice_pdf(invoice_id):
        """Generate PDF invoice"""
        from io import BytesIO

        # In a real implementation, this would use a PDF generation library
        # like reportlab, weasyprint, or xhtml2pdf
        # For this example, we'll just create a placeholder BytesIO object
        pdf_buffer = BytesIO()
        pdf_buffer.write(b"This is a placeholder for a real PDF invoice")
        pdf_buffer.seek(0)

        return pdf_buffer

    @staticmethod
    def calculate_vat(amount, vat_rate=0.15):
        """Calculate VAT amount (Saudi Arabia standard rate is 15%)"""
        return Decimal(amount) * Decimal(vat_rate)

    @staticmethod
    def get_invoice_details(invoice_id):
        """Get detailed invoice information including line items"""
        invoice = SubscriptionInvoice.objects.get(id=invoice_id)
        subscription = invoice.subscription

        # Calculate VAT
        vat_amount = InvoiceService.calculate_vat(invoice.amount)
        subtotal = invoice.amount - vat_amount

        return {
            "invoice_number": invoice.invoice_number,
            "date": invoice.issued_date,
            "due_date": invoice.due_date,
            "status": invoice.status,
            "company": {
                "name": subscription.company.name,
                "address": getattr(subscription.company, "address", ""),
                "vat_number": getattr(subscription.company, "vat_number", ""),
            },
            "items": [
                {
                    "description": f"{subscription.plan_name} - {subscription.period}",
                    "period": f"{invoice.period_start.strftime('%d %b %Y')} - {invoice.period_end.strftime('%d %b %Y')}",
                    "amount": subtotal,
                }
            ],
            "subtotal": subtotal,
            "vat_rate": "15%",
            "vat_amount": vat_amount,
            "total": invoice.amount,
            "paid_date": invoice.paid_date,
            "transaction_id": invoice.transaction.id if invoice.transaction else None,
        }
