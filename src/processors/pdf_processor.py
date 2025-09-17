import PyPDF2
import io
import aiohttp
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from datetime import datetime
from typing import List
from src.models.request_models import CompleteRequestData, DocumentProcessingRequest, GLCodingEntry
from src.storage.blob_client import BlobStorageClient


class PDFProcessor:
    """PDF processing for invoice merge and signature generation"""

    async def download_pdf(self, pdf_url: str) -> bytes:
        """Download PDF from Azure Blob Storage using SAS URL for authentication"""
        import time
        start_time = time.time()

        try:
            # Generate SAS URL for authenticated access to existing blob
            blob_client = BlobStorageClient()
            sas_url = blob_client.generate_sas_url_for_existing_blob(pdf_url)

            logging.info(f"Generated SAS URL for PDF download")

            async with aiohttp.ClientSession() as session:
                async with session.get(sas_url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to download PDF: HTTP {response.status}")

                    pdf_data = await response.read()
                    download_time = time.time() - start_time
                    logging.info(f"Successfully downloaded PDF from {pdf_url} ({len(pdf_data)} bytes) in {download_time:.2f}s")
                    return pdf_data

        except aiohttp.ClientError as e:
            logging.error(f"HTTP client error downloading PDF from {pdf_url}: {str(e)}")
            raise Exception(f"Failed to download PDF: {str(e)}")
        except Exception as e:
            logging.error(f"Error downloading PDF from {pdf_url}: {str(e)}")
            raise

    def generate_gl_coding_page(self, complete_data: CompleteRequestData) -> bytes:
        """Generate GL Coding page with adaptive table for GL entries"""
        try:
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.lib.pagesizes import letter

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter,
                                  topMargin=0.75*inch, bottomMargin=0.75*inch,
                                  leftMargin=0.5*inch, rightMargin=0.5*inch)

            # Build story (content)
            story = []
            styles = getSampleStyleSheet()

            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=20,
                alignment=1  # Center alignment
            )
            story.append(Paragraph("GL Coding Details", title_style))

            # Vendor info if available
            if complete_data.requestInfo and "vendor" in complete_data.requestInfo:
                vendor_style = ParagraphStyle(
                    'VendorStyle',
                    parent=styles['Normal'],
                    fontSize=12,
                    spaceAfter=20
                )
                story.append(Paragraph(f"<b>Vendor:</b> {complete_data.requestInfo['vendor']}", vendor_style))

            # Table data preparation
            table_data = []

            # Header style for wrapping text
            header_style = ParagraphStyle(
                'HeaderStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=12,
                wordWrap='CJK',
                fontName='Helvetica-Bold',
                textColor=colors.whitesmoke,
                alignment=1  # Center alignment
            )

            # Cell style for wrapping text
            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontSize=9,
                leading=10,
                wordWrap='CJK'  # Better word wrapping
            )

            # Headers with Paragraph wrapping - combining Equipment and Comments
            headers = [
                Paragraph('Account<br/>Code', header_style),
                Paragraph('Account<br/>Description', header_style),
                Paragraph('Facility<br/>Code', header_style),
                Paragraph('Facility<br/>Description', header_style),
                Paragraph('Tax<br/>Code', header_style),
                Paragraph('Amount', header_style),
                Paragraph('Equipment & Comments', header_style)
            ]
            table_data.append(headers)

            total_amount = 0

            # Add data rows - combining Equipment and Comments
            for entry in complete_data.glCodingData:
                # Combine equipment and comments
                equipment_comments = ""
                if entry.equipment:
                    equipment_comments += f"<b>Equipment:</b> {entry.equipment}"
                if entry.comments:
                    if equipment_comments:
                        equipment_comments += "<br/><br/>"
                    equipment_comments += f"<b>Comments:</b> {entry.comments}"
                if not equipment_comments:
                    equipment_comments = "-"

                row = [
                    Paragraph(entry.accountCode, cell_style),
                    Paragraph(entry.accountDescription, cell_style),
                    Paragraph(entry.facilityCode, cell_style),
                    Paragraph(entry.facilityDescription, cell_style),
                    Paragraph(entry.taxCode, cell_style),
                    Paragraph(f"${entry.amount:,.2f}", cell_style),
                    Paragraph(equipment_comments, cell_style)
                ]
                table_data.append(row)
                total_amount += entry.amount

            # Add total row - adjusted for 7 columns
            total_row = [
                Paragraph("", cell_style),
                Paragraph("", cell_style),
                Paragraph("", cell_style),
                Paragraph("", cell_style),
                Paragraph("<b>TOTAL:</b>", cell_style),
                Paragraph(f"<b>${total_amount:,.2f}</b>", cell_style),
                Paragraph("", cell_style)
            ]
            table_data.append(total_row)

            # Calculate available width for the table
            page_width = letter[0]  # 8.5 inches
            left_margin = 0.5*inch
            right_margin = 0.5*inch
            available_width = page_width - left_margin - right_margin  # 7.5 inches

            # Create table with adaptive column widths that fit within margins
            # 7 columns total - proportions add up to 100%
            col_widths = [
                available_width * 0.10,  # Account Code (10%)
                available_width * 0.20,  # Account Description (20%)
                available_width * 0.10,  # Facility Code (10%)
                available_width * 0.20,  # Facility Description (20%)
                available_width * 0.08,  # Tax Code (8%)
                available_width * 0.12,  # Amount (12%)
                available_width * 0.20   # Equipment & Comments (20% - más espacio)
            ]

            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            # Table styling
            table_style = TableStyle([
                # Header row styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Center headers
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),  # Middle vertical alignment for headers

                # Data rows styling
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),  # Left align data cells
                ('GRID', (0, 0), (-1, -1), 1, colors.black),

                # Amount column alignment - right align for better readability
                ('ALIGN', (5, 1), (5, -1), 'RIGHT'),

                # Total row styling
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),

                # Padding and vertical alignment
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),  # Top align data cells
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),

                # Row height minimum to accommodate text wrapping
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.lightcyan]),  # Alternate row colors
            ])

            table.setStyle(table_style)
            story.append(table)

            # Add footer with timestamp
            story.append(Spacer(1, 20))
            footer_style = ParagraphStyle(
                'FooterStyle',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.grey
            )
            story.append(Paragraph(f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC", footer_style))
            story.append(Paragraph("TCRS Document Processing System", footer_style))

            # Build PDF
            doc.build(story)
            buffer.seek(0)
            gl_coding_data = buffer.getvalue()

            logging.info(f"Generated adaptive GL coding page ({len(gl_coding_data)} bytes)")
            return gl_coding_data

        except Exception as e:
            logging.error(f"Error generating GL coding page: {str(e)}")
            raise Exception(f"Failed to generate GL coding page: {str(e)}")

    def add_stamp_to_first_page(self, pdf_data: bytes, request_data: DocumentProcessingRequest,
                               position: str = "right") -> bytes:
        """Add vertical approval signature to first page of PDF

        Args:
            pdf_data: PDF bytes data
            request_data: Request data with signature info
            position: "right" (default) or "left" - side to place the signature
        """
        try:
            # Read the PDF
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
            writer = PyPDF2.PdfWriter()

            # Create stamp
            stamp_buffer = io.BytesIO()
            c = canvas.Canvas(stamp_buffer, pagesize=letter)
            width, height = letter

            # Create signature string: "request - datetime - approvername"
            formatted_datetime = request_data.timestamp.strftime('%Y-%m-%d %H:%M')
            signature_text = f"{request_data.requestId} - {formatted_datetime} - {request_data.approverName}"

            # Position for vertical text based on selected side with safe margins
            # Add more margin to ensure visibility on all PDF viewers
            safe_margin = 40  # Increased margin for better visibility

            if position.lower() == "left":
                x_position = safe_margin  # 40 points from left edge
                rotation = 90    # Rotate clockwise for left side (bottom to top)
                y_start = height - 150   # Start lower to ensure text fits
            else:  # right side (default)
                x_position = width - safe_margin  # 40 points from right edge
                rotation = 270   # Rotate counterclockwise for right side (top to bottom)
                y_start = height - 150   # Start lower to ensure text fits

            # Set font and color
            c.setFont("Helvetica", 10)
            c.setFillColorRGB(0.6, 0.6, 0.6)  # Gray color

            # Calculate text width to ensure it fits within page bounds
            text_width = c.stringWidth(signature_text, "Helvetica", 10)

            # Adjust starting position if text is too long
            if position.lower() == "left":
                # For left side, text goes from bottom to top
                min_y = 50  # Minimum distance from bottom
                if y_start - text_width < min_y:
                    y_start = min_y + text_width
            else:
                # For right side, text goes from top to bottom
                min_y = 50  # Minimum distance from bottom
                if y_start - text_width < min_y:
                    y_start = height - 50  # Start closer to top

            # Save the current state
            c.saveState()

            # Rotate text for vertical display
            c.translate(x_position, y_start)
            c.rotate(rotation)

            # Draw the signature text vertically
            c.drawString(0, 0, signature_text)

            # Restore state
            c.restoreState()

            c.save()
            stamp_buffer.seek(0)

            # Read stamp as PDF
            stamp_reader = PyPDF2.PdfReader(stamp_buffer)

            # Process all pages
            for i, page in enumerate(pdf_reader.pages):
                if i == 0:  # First page - add stamp
                    page.merge_page(stamp_reader.pages[0])
                writer.add_page(page)

            # Write final PDF
            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)
            stamped_data = output_buffer.getvalue()

            logging.info(f"Added vertical signature to first page ({len(stamped_data)} bytes)")
            return stamped_data

        except Exception as e:
            logging.error(f"Error adding stamp to PDF: {str(e)}")
            raise Exception(f"Failed to add stamp to PDF: {str(e)}")

    def merge_pdfs(self, invoice_pdf: bytes, signature_pdf: bytes) -> bytes:
        """Merge invoice PDF with signature page (signature page last)"""
        try:
            invoice_reader = PyPDF2.PdfReader(io.BytesIO(invoice_pdf))
            signature_reader = PyPDF2.PdfReader(io.BytesIO(signature_pdf))

            writer = PyPDF2.PdfWriter()

            # Add all pages from invoice PDF first
            for page in invoice_reader.pages:
                writer.add_page(page)

            # Add signature page(s) last
            for page in signature_reader.pages:
                writer.add_page(page)

            # Write merged PDF to buffer
            output_buffer = io.BytesIO()
            writer.write(output_buffer)
            output_buffer.seek(0)
            merged_data = output_buffer.getvalue()

            logging.info(f"Successfully merged PDFs: invoice ({len(invoice_pdf)} bytes) + signature ({len(signature_pdf)} bytes) = {len(merged_data)} bytes")
            return merged_data

        except Exception as e:
            logging.error(f"Error merging PDFs: {str(e)}")
            raise Exception(f"Failed to merge PDFs: {str(e)}")

    async def process_documents(self, request_data: DocumentProcessingRequest,
                               complete_data: CompleteRequestData) -> bytes:
        """Complete PDF processing workflow: Invoice + GL Coding + Stamp"""
        try:
            logging.info(f"Processing documents for request {request_data.requestId}")

            # Step 1: Download original invoice PDF
            if complete_data.invoicePdfUrl.startswith('file:///'):
                # Local file for testing
                local_path = complete_data.invoicePdfUrl.replace('file:///', '')
                with open(local_path, 'rb') as f:
                    invoice_pdf = f.read()
                logging.info(f"Read local invoice PDF: {len(invoice_pdf)} bytes")
            else:
                # Download from blob storage
                invoice_pdf = await self.download_pdf(complete_data.invoicePdfUrl)
                logging.info(f"Downloaded invoice PDF: {len(invoice_pdf)} bytes")

            # Step 2: Generate GL Coding page
            gl_coding_pdf = self.generate_gl_coding_page(complete_data)
            logging.info(f"Generated GL coding page: {len(gl_coding_pdf)} bytes")

            # Step 3: Concatenate Invoice + GL Coding
            concatenated_pdf = self.merge_pdfs(invoice_pdf, gl_coding_pdf)
            logging.info(f"Concatenated PDFs: {len(concatenated_pdf)} bytes")

            # Step 4: Add stamp to first page
            final_pdf = self.add_stamp_to_first_page(concatenated_pdf, request_data)
            logging.info(f"Added stamp to final PDF: {len(final_pdf)} bytes")

            logging.info(f"Successfully processed documents for request {request_data.requestId}")
            return final_pdf

        except Exception as e:
            logging.error(f"Error processing documents for {request_data.requestId}: {str(e)}")
            raise