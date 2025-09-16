import io
import logging
import warnings
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF for PDF to image conversion
from typing import List

# Suppress PIL decompression bomb warnings for legitimate large documents
warnings.filterwarnings("ignore", ".*DecompressionBombWarning.*")


class TIFFConverter:
    def combine_images_vertically(self, images: List[Image.Image]) -> Image.Image:
        """Combina todas las imágenes en una sola, apiladas verticalmente"""
        if not images:
            raise ValueError("No images to combine")

        # Asegura que todas tengan el mismo ancho
        widths, heights = zip(*(img.size for img in images))
        total_height = sum(heights)
        max_width = max(widths)

        # Crear imagen nueva
        combined = Image.new('RGB', (max_width, total_height), color=(255, 255, 255))

        y_offset = 0
        for img in images:
            # Si alguna imagen es más angosta, la centramos
            x_offset = (max_width - img.width) // 2
            combined.paste(img, (x_offset, y_offset))
            y_offset += img.height

        return combined

    def images_to_singlepage_tiff(self, images: List[Image.Image]) -> bytes:
        """Convierte todas las imágenes en un solo TIFF de una página (apiladas verticalmente)"""
        try:
            if not images:
                raise ValueError("No images provided for TIFF conversion")
            combined = self.combine_images_vertically(images)
            output_buffer = io.BytesIO()
            # Save with optimized settings
            save_kwargs = {
                "format": "TIFF",
                "compression": self.compression,
                "dpi": (self.dpi, self.dpi)
            }

            # Add JPEG quality if using JPEG compression
            if self.compression == "jpeg":
                save_kwargs["quality"] = self.jpeg_quality

            combined.save(output_buffer, **save_kwargs)
            output_buffer.seek(0)
            tiff_data = output_buffer.getvalue()

            # Log TIFF size for optimization tracking
            logging.info(f"Generated TIFF: {len(tiff_data)/1024/1024:.2f} MB (DPI: {self.dpi}, compression: {self.compression})")

            return tiff_data
        except Exception as e:
            logging.error(f"Error creating single-page TIFF from images: {str(e)}")
            raise Exception(f"Failed to create single-page TIFF: {str(e)}")

    def images_to_tiff(self, images: List[Image.Image]) -> bytes:
        """Convert multiple images to a multi-page TIFF or single-page TIFF (combined)"""
        try:
            if not images:
                raise ValueError("No images provided for TIFF conversion")

            # For now, use single-page TIFF approach (all pages combined)
            return self.images_to_singlepage_tiff(images)

        except Exception as e:
            logging.error(f"Error converting images to TIFF: {str(e)}")
            raise Exception(f"Failed to convert images to TIFF: {str(e)}")

    def convert_pdf_to_singlepage_tiff(self, pdf_data: bytes) -> bytes:
        """Convierte un PDF a un TIFF de una sola página con todas las páginas apiladas"""
        try:
            logging.info(f"Starting PDF to single-page TIFF conversion ({len(pdf_data)} bytes)")
            images = self.pdf_to_images(pdf_data)
            if not images:
                raise Exception("No pages found in PDF document")
            tiff_data = self.images_to_singlepage_tiff(images)
            for img in images:
                img.close()
            logging.info("Successfully completed PDF to single-page TIFF conversion")
            return tiff_data
        except Exception as e:
            logging.error(f"Error in PDF to single-page TIFF conversion: {str(e)}")
            raise
    """Convert PDF documents to TIFF images with high quality settings"""

    def __init__(self):
        self.dpi = 120  # Further reduced DPI for very large documents
        self.compression = "jpeg"  # JPEG compression for much smaller files
        self.jpeg_quality = 80  # Balanced quality for large files
        self.max_image_width = 2000  # Maximum width to prevent huge images

    def pdf_to_images(self, pdf_data: bytes) -> List[Image.Image]:
        """Convert ALL PDF pages to PIL Images"""
        try:
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            images = []

            logging.info(f"PDF has {pdf_document.page_count} pages to convert")

            for page_num in range(pdf_document.page_count):
                logging.info(f"Processing PDF page {page_num + 1}/{pdf_document.page_count}")

                # Get page
                page = pdf_document[page_num]

                # Render page to pixmap with high DPI
                # Scale factor for 300 DPI (default is 72 DPI)
                scale_factor = self.dpi / 72
                mat = fitz.Matrix(scale_factor, scale_factor)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("ppm")
                pil_image = Image.open(io.BytesIO(img_data))

                # Ensure RGB mode for document quality
                if pil_image.mode != 'RGB':
                    logging.info(f"Converting page {page_num + 1} from {pil_image.mode} to RGB")
                    pil_image = pil_image.convert('RGB')

                # Resize if image is too wide to prevent memory issues
                if pil_image.width > self.max_image_width:
                    ratio = self.max_image_width / pil_image.width
                    new_height = int(pil_image.height * ratio)
                    pil_image = pil_image.resize((self.max_image_width, new_height), Image.Resampling.LANCZOS)
                    logging.info(f"Resized page {page_num + 1} to {pil_image.size[0]}x{pil_image.size[1]} to prevent memory issues")

                images.append(pil_image)
                logging.info(f"✅ Converted PDF page {page_num + 1} to image ({pil_image.size[0]}x{pil_image.size[1]}, mode: {pil_image.mode})")

            pdf_document.close()
            logging.info(f"🎉 Successfully converted ALL {len(images)} PDF pages to images")
            return images

        except Exception as e:
            logging.error(f"Error converting PDF to images: {str(e)}")
            raise Exception(f"Failed to convert PDF to images: {str(e)}")

    def convert_pdf_to_tiff(self, pdf_data: bytes) -> bytes:
        """Complete conversion workflow from PDF to TIFF"""
        try:
            logging.info(f"Starting PDF to TIFF conversion ({len(pdf_data)} bytes)")

            # Convert PDF pages to images
            images = self.pdf_to_images(pdf_data)

            if not images:
                raise Exception("No pages found in PDF document")

            # Convert images to TIFF
            tiff_data = self.images_to_tiff(images)

            # Clean up images from memory
            for img in images:
                img.close()

            logging.info("Successfully completed PDF to TIFF conversion")
            return tiff_data

        except Exception as e:
            logging.error(f"Error in PDF to TIFF conversion: {str(e)}")
            raise

    def validate_tiff_quality(self, tiff_data: bytes) -> bool:
        """Validate TIFF meets quality requirements and show detailed info"""
        try:
            tiff_image = Image.open(io.BytesIO(tiff_data))

            # Get detailed TIFF information
            logging.info(f" TIFF Validation Details:")
            logging.info(f"   - Format: {tiff_image.format}")
            logging.info(f"   - Size: {tiff_image.size}")
            logging.info(f"   - Mode: {tiff_image.mode}")

            # Check if it's actually a TIFF
            if tiff_image.format != 'TIFF':
                logging.warning(f"❌ Generated file is not in TIFF format: {tiff_image.format}")
                return False

            # Check for multi-page TIFF
            try:
                page_count = tiff_image.n_frames
                logging.info(f"   - Pages: {page_count}")
            except AttributeError:
                page_count = 1
                logging.info(f"   - Pages: 1 (single-page TIFF)")

            # Check color mode
            if tiff_image.mode != 'RGB':
                logging.warning(f"❌ TIFF color mode is {tiff_image.mode}, expected RGB")
                return False

            # Check compression
            compression_info = tiff_image.info.get('compression')
            if compression_info:
                logging.info(f"   - Compression: {compression_info}")

            logging.info(" TIFF quality validation PASSED")
            tiff_image.close()
            return True

        except Exception as e:
            logging.error(f"❌ Error validating TIFF quality: {str(e)}")
            return False