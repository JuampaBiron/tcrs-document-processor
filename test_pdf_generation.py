#!/usr/bin/env python3
"""
Test script for PDF generation functionality
Tests only the PDF processing: download + signature page + merge
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

# Add src to path
import sys
sys.path.append(str(Path(__file__).parent / "src"))

from src.processors.pdf_processor import PDFProcessor
from src.processors.tiff_converter import TIFFConverter
from src.models.request_models import DocumentProcessingRequest, CompleteRequestData, GLCodingEntry


def create_test_data():
    """Create test data for PDF generation"""

    # Request data (what the function receives)
    request_data = DocumentProcessingRequest(
        requestId="202412150001",
        approverName="Juan Pablo Biron",
        approverEmail="juan@finning.com",
        timestamp=datetime.now(),
        isRetry=False
    )

    # Complete data (what comes from TCRS API)
    # 👇 CAMBIA SOLO ESTA RUTA A TU PDF LOCAL
    PDF_PATH = r"C:\Users\JuanPabloBiron\sisua\finning\tcrs-document-processor\tests\202412150001_consolidated_20250916_121505.pdf"

    complete_data = CompleteRequestData(
        requestId="202412150001",
        invoicePdfUrl=PDF_PATH,  # Se usa directamente como ruta local
        requestInfo={
            "amount": 8750.00,
            "vendor": "Test Vendor Inc",
            "company": "Finning International",
            "branch": "Main Branch Vancouver"
        },
        glCodingData=[
            GLCodingEntry(
                accountCode="1000-EQUIP",
                accountDescription="Heavy Equipment Operations and Maintenance Account for Construction Projects",
                facilityCode="MAIN-VAN",
                facilityDescription="Main Facility Vancouver - Primary Operations Center",
                taxCode="GST",
                amount=3000.00,
                equipment="CAT-950H Wheel Loader (Unit #12345)",
                comments="Comprehensive heavy equipment maintenance including hydraulic system overhaul, engine tune-up, and transmission repair work completed by certified technicians"
            ),
            GLCodingEntry(
                accountCode="2000-PARTS",
                accountDescription="Equipment Parts, Components and Replacement Supplies Inventory",
                facilityCode="SHOP-002",
                facilityDescription="Workshop Facility #2 - Parts Distribution Center",
                taxCode="GST",
                amount=1500.00,
                equipment="CAT-950H Wheel Loader (Unit #12345)",
                comments="Hydraulic system replacement parts including main pump assembly, hydraulic cylinders, seals and gaskets, plus various filters and lubricants"
            ),
            GLCodingEntry(
                accountCode="3000-LABOR",
                accountDescription="Skilled Labor Services and Professional Technical Support",
                facilityCode="MAIN-VAN",
                facilityDescription="Main Facility Vancouver - Primary Operations Center",
                taxCode="GST",
                amount=1000.00,
                equipment="Various Equipment Units",
                comments="8 hours of specialized repair work performed by certified heavy equipment technician including diagnostic testing and quality assurance validation"
            ),
            GLCodingEntry(
                accountCode="4000-TRANS",
                accountDescription="Transportation, Logistics and Equipment Delivery Services",
                facilityCode="TRANS-001",
                facilityDescription="Transportation Department - Logistics and Distribution Hub",
                taxCode="GST",
                amount=250.00,
                equipment="Transport Truck and Trailer",
                comments="Equipment delivery to job site including loading, secure transport, and unloading with specialized heavy equipment transport trailer"
            )
        ],
        approverInfo={
            "name": "Juan Pablo Biron",
            "email": "juan@finning.com"
        }
    )

    return request_data, complete_data


async def test_tiff_conversion_only():
    """Test only TIFF conversion from existing PDF"""

    print(" Testing TIFF Conversion Only")
    print("=" * 50)

    # Create test data
    request_data, complete_data = create_test_data()

    # Use the PDF path directly from test data
    pdf_path = complete_data.invoicePdfUrl

    if not os.path.exists(pdf_path):
        print(f"❌ PDF file not found: {pdf_path}")
        print("Please update the PDF_PATH variable in the create_test_data() function")
        return

    print(f" Using PDF: {os.path.basename(pdf_path)}")

    # Initialize TIFF converter
    tiff_converter = TIFFConverter()

    try:
        # Read PDF file
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        print(f" Read PDF: {len(pdf_data):,} bytes")

        # Convert to single-page TIFF (todas las páginas apiladas en una sola imagen)
        print("\n Converting PDF to single-page TIFF (all pages stacked)...")
        tiff_data = tiff_converter.convert_pdf_to_singlepage_tiff(pdf_data)
        print(f" Generated single-page TIFF: {len(tiff_data):,} bytes")

        # Validate TIFF quality
        print("\n Validating TIFF quality...")
        is_valid = tiff_converter.validate_tiff_quality(tiff_data)
        print(f" Quality validation: {'PASSED' if is_valid else 'FAILED'}")

        # Save TIFF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tiff_output_path = f"test_tiff_singlepage_{timestamp}.tiff"

        with open(tiff_output_path, 'wb') as f:
            f.write(tiff_data)

        print(f"TIFF saved: {tiff_output_path}")

        print("\n TIFF Details:")
        print(f"   - Original PDF: {len(pdf_data):,} bytes")
        print(f"   - Generated TIFF: {len(tiff_data):,} bytes")
        print(f"   - Resolution: 300 DPI")
        print(f"   - Compression: LZW")
        print(f"   - Color mode: RGB")
        print(f"   - Quality: {'PASSED ✅' if is_valid else 'FAILED ❌'}")

    except Exception as e:
        print(f"❌ Error during TIFF conversion: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_pdf_generation():
    """Test the complete PDF generation process"""

    print("Testing PDF Generation")
    print("=" * 50)

    # Create test data
    request_data, complete_data = create_test_data()

    # Use the PDF path directly from test data
    pdf_path = complete_data.invoicePdfUrl

    if not os.path.exists(pdf_path):
        print(f"❌ PDF file not found: {pdf_path}")
        print("Please update the PDF_PATH variable in the create_test_data() function")
        return

    print(f"Using local PDF: {os.path.basename(pdf_path)}")
    print(f"Full path: {pdf_path}")
    print(f"GL Coding entries: {len(complete_data.glCodingData)}")
    print(f"Total amount: ${sum(entry.amount for entry in complete_data.glCodingData):,.2f}")

    # Initialize processors
    processor = PDFProcessor()
    tiff_converter = TIFFConverter()

    try:
        # Test GL Coding page generation
        print("\nTesting GL Coding page generation...")
        gl_coding_pdf = processor.generate_gl_coding_page(complete_data)

        # Save GL coding page for inspection
        gl_output_path = f"test_gl_coding_{request_data.requestId}.pdf"
        with open(gl_output_path, 'wb') as f:
            f.write(gl_coding_pdf)
        print(f"GL Coding page saved: {gl_output_path}")

        # Test complete processing workflow - LOCAL FILES ONLY
        print("\n Testing complete PDF processing workflow...")
        print("    Reading local invoice PDF...")

        # Read invoice PDF directly
        with open(pdf_path, 'rb') as f:
            invoice_pdf = f.read()
        print(f" Read invoice PDF: {len(invoice_pdf):,} bytes")

        print("   2️ Generating GL Coding page...")
        gl_coding_pdf = processor.generate_gl_coding_page(complete_data)
        print(f" Generated GL coding page: {len(gl_coding_pdf):,} bytes")

        print("   3️ Concatenating PDFs...")
        concatenated_pdf = processor.merge_pdfs(invoice_pdf, gl_coding_pdf)
        print(f" Concatenated PDFs: {len(concatenated_pdf):,} bytes")

        print("   4️ Adding vertical approval signature...")
        # You can change position to "left" or "right"
        signature_position = "right"  # Change this to "left" if you prefer
        final_pdf = processor.add_stamp_to_first_page(concatenated_pdf, request_data, signature_position)
        print(f" Added vertical signature ({signature_position} side): {len(final_pdf):,} bytes")

        # Save final PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"{request_data.requestId}_consolidated_{timestamp}.pdf"

        with open(output_path, 'wb') as f:
            f.write(final_pdf)

        print(f" Final PDF saved: {output_path}")
        print(f" Final PDF size: {len(final_pdf):,} bytes")

        # Test TIFF conversion
        print("   5️⃣ Converting PDF to TIFF...")
        print(f"      Converting final PDF ({len(final_pdf):,} bytes) to TIFF...")
        tiff_data = tiff_converter.convert_pdf_to_tiff(final_pdf)
        print(f"✅ Generated TIFF: {len(tiff_data):,} bytes")

        # Validate TIFF quality
        print("   6️⃣ Validating TIFF quality...")
        is_valid = tiff_converter.validate_tiff_quality(tiff_data)
        print(f"✅ TIFF quality validation: {'PASSED' if is_valid else 'FAILED'}")

        # Save TIFF file
        tiff_output_path = f"{request_data.requestId}_document_{timestamp}.tiff"
        with open(tiff_output_path, 'wb') as f:
            f.write(tiff_data)

        print(f"✅ TIFF saved: {tiff_output_path}")
        print(f"📊 TIFF size: {len(tiff_data):,} bytes")

        # Show GL Coding summary
        print("\n GL Coding Summary:")
        for i, entry in enumerate(complete_data.glCodingData, 1):
            print(f"  {i}. {entry.accountCode} - {entry.facilityCode}: ${entry.amount:,.2f}")
            if entry.equipment:
                print(f"     Equipment: {entry.equipment}")
            if entry.comments:
                print(f"     Comments: {entry.comments}")

        total = sum(entry.amount for entry in complete_data.glCodingData)
        print(f"\n Total GL Amount: ${total:,.2f}")

        print("\n🎉 PDF generation test completed successfully!")
        print(f"📂 Generated files:")
        print(f"   - GL Coding page: {gl_output_path}")
        print(f"   - Final PDF (Invoice + GL + Signature): {output_path}")
        print(f"   - TIFF Document: {tiff_output_path}")

        print("\n📋 Final PDF structure:")
        print(f"   - Page 1: Original invoice (WITH vertical signature on {signature_position} side)")
        print(f"   - Pages 2-N: Rest of invoice (if multi-page)")
        print(f"   - Page N+1: GL Coding table with full details")

        print(f"\n🔖 Signature format:")
        print(f"   - {request_data.requestId} - {request_data.timestamp.strftime('%Y-%m-%d %H:%M')} - {request_data.approverName}")

        print(f"\n🖼️ TIFF specifications:")
        print(f"   - Resolution: 300 DPI")
        print(f"   - Compression: LZW")
        print(f"   - Color mode: RGB")
        print(f"   - Format: Multi-page TIFF (if applicable)")
        print(f"   - Quality validation: {'PASSED ✅' if is_valid else 'FAILED ❌'}")

    except Exception as e:
        print(f"❌ Error during PDF generation: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys

    print("🚀 TCRS PDF Processing Test Suite")
    print("=" * 50)
    #asyncio.run(test_pdf_generation())
    asyncio.run(test_tiff_conversion_only())
    """if len(sys.argv) > 1 and sys.argv[1] == "--tiff-only":
        # Test only TIFF conversion
        asyncio.run(test_tiff_conversion_only())
    else:
        # Test complete workflow (default)
        asyncio.run(test_pdf_generation())"""