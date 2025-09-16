#!/usr/bin/env python3
"""
Debug script for TIFF conversion - simple test without complex imports
"""

import io
import logging
from PIL import Image
import fitz  # PyMuPDF for PDF to image conversion

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def debug_tiff_conversion():
    """Debug TIFF conversion step by step"""

    # Use the same PDF path as in the test script
    pdf_path = r"C:\Users\JuanPabloBiron\sisua\finning\tcrs-document-processor\tests\test_pdf.pdf"

    print(f"[DEBUG] Debugging TIFF conversion")
    print(f"[PDF] PDF path: {pdf_path}")

    try:
        # Step 1: Read PDF
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        print(f"[OK] Read PDF: {len(pdf_data):,} bytes")

        # Step 2: Open PDF with PyMuPDF and check pages
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        page_count = pdf_document.page_count
        print(f"[INFO] PDF has {page_count} pages")

        if page_count == 1:
            print("[WARNING] PDF only has 1 page - TIFF will be single page")
        else:
            print(f"[OK] PDF has {page_count} pages - TIFF should be multi-page")

        # Step 3: Convert each page to image
        images = []
        dpi = 300
        scale_factor = dpi / 72

        for page_num in range(page_count):
            print(f"[PROCESS] Processing page {page_num + 1}/{page_count}")

            # Get page
            page = pdf_document[page_num]

            # Render page to pixmap with high DPI
            mat = fitz.Matrix(scale_factor, scale_factor)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img_data = pix.tobytes("ppm")
            pil_image = Image.open(io.BytesIO(img_data))

            # Ensure RGB mode
            if pil_image.mode != 'RGB':
                print(f"[CONVERT] Converting page {page_num + 1} from {pil_image.mode} to RGB")
                pil_image = pil_image.convert('RGB')

            images.append(pil_image)
            print(f"[OK] Page {page_num + 1}: {pil_image.size[0]}x{pil_image.size[1]} ({pil_image.mode})")

        pdf_document.close()
        print(f"[SUCCESS] Converted {len(images)} pages to images")

        # Step 4: Create TIFF
        print(f"[TIFF] Creating TIFF from {len(images)} images...")

        output_buffer = io.BytesIO()

        if len(images) == 1:
            print("[TIFF] Creating single-page TIFF")
            images[0].save(
                output_buffer,
                format="TIFF",
                compression="lzw",
                dpi=(dpi, dpi)
            )
        else:
            print(f"[TIFF] Creating multi-page TIFF with {len(images)} pages")
            print(f"   - First page + {len(images[1:])} additional pages")
            images[0].save(
                output_buffer,
                format="TIFF",
                compression="lzw",
                dpi=(dpi, dpi),
                save_all=True,
                append_images=images[1:]
            )

        output_buffer.seek(0)
        tiff_data = output_buffer.getvalue()
        print(f"[OK] TIFF created: {len(tiff_data):,} bytes")

        # Step 5: Validate TIFF
        print(f"[VALIDATE] Validating TIFF...")
        tiff_image = Image.open(io.BytesIO(tiff_data))

        print(f"   - Format: {tiff_image.format}")
        print(f"   - Size: {tiff_image.size}")
        print(f"   - Mode: {tiff_image.mode}")

        # Check for multi-page TIFF
        try:
            page_count_tiff = tiff_image.n_frames
            print(f"   - TIFF Pages: {page_count_tiff}")

            # Try to iterate through all pages
            for i in range(page_count_tiff):
                tiff_image.seek(i)
                print(f"     Page {i+1}: {tiff_image.size[0]}x{tiff_image.size[1]}")

        except AttributeError:
            print(f"   - TIFF Pages: 1 (single-page TIFF)")
        except Exception as e:
            print(f"   - Error checking pages: {e}")

        # Check DPI
        dpi_info = tiff_image.info.get('dpi')
        if dpi_info:
            print(f"   - DPI: {dpi_info[0]} x {dpi_info[1]}")

        # Check compression
        compression_info = tiff_image.info.get('compression')
        if compression_info:
            print(f"   - Compression: {compression_info}")

        tiff_image.close()

        # Step 6: Save TIFF for inspection
        timestamp = "debug"
        tiff_output_path = f"debug_tiff_{timestamp}.tiff"

        with open(tiff_output_path, 'wb') as f:
            f.write(tiff_data)

        print(f"[SAVE] TIFF saved: {tiff_output_path}")
        print(f"[SUMMARY] Summary:")
        print(f"   - Original PDF pages: {page_count}")
        print(f"   - Images converted: {len(images)}")
        print(f"   - TIFF size: {len(tiff_data):,} bytes")
        print(f"   - You can open {tiff_output_path} to verify all pages are there")

        # Clean up images
        for img in images:
            img.close()

    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_tiff_conversion()