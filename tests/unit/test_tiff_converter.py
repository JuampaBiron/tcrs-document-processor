import pytest
import io
from unittest.mock import patch, Mock
from PIL import Image
from src.processors.tiff_converter import TIFFConverter


@pytest.fixture
def sample_pdf_data():
    """Mock PDF data for testing"""
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj

xref
0 4
0000000000 65535 f
0000000015 65535 n
0000000074 65535 n
0000000120 65535 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
190
%%EOF"""


@pytest.fixture
def mock_image():
    """Create a mock PIL Image"""
    # Create a small RGB image for testing
    img = Image.new('RGB', (100, 100), color='white')
    return img


class TestTIFFConverter:
    """Test cases for TIFF converter"""

    def test_init(self):
        """Test TIFF converter initialization"""
        converter = TIFFConverter()
        assert converter.dpi == 300
        assert converter.compression == "lzw"

    def test_images_to_tiff_single_image(self, mock_image):
        """Test converting single image to TIFF"""
        converter = TIFFConverter()
        images = [mock_image]

        tiff_data = converter.images_to_tiff(images)

        assert isinstance(tiff_data, bytes)
        assert len(tiff_data) > 0

        # Verify it's a valid TIFF
        tiff_image = Image.open(io.BytesIO(tiff_data))
        assert tiff_image.format == 'TIFF'

    def test_images_to_tiff_multiple_images(self, mock_image):
        """Test converting multiple images to multi-page TIFF"""
        converter = TIFFConverter()

        # Create multiple images
        img1 = mock_image.copy()
        img2 = mock_image.copy()
        images = [img1, img2]

        tiff_data = converter.images_to_tiff(images)

        assert isinstance(tiff_data, bytes)
        assert len(tiff_data) > 0

        # Verify it's a valid multi-page TIFF
        tiff_image = Image.open(io.BytesIO(tiff_data))
        assert tiff_image.format == 'TIFF'
        assert tiff_image.n_frames >= 1

    def test_images_to_tiff_empty_list(self):
        """Test converting empty image list"""
        converter = TIFFConverter()

        with pytest.raises(Exception) as exc_info:
            converter.images_to_tiff([])

        assert "No images provided" in str(exc_info.value)

    def test_validate_tiff_quality_valid(self, mock_image):
        """Test TIFF quality validation with valid TIFF"""
        converter = TIFFConverter()

        # Create a TIFF with proper settings
        buffer = io.BytesIO()
        mock_image.save(buffer, format="TIFF", dpi=(300, 300), compression="lzw")
        buffer.seek(0)
        tiff_data = buffer.getvalue()

        result = converter.validate_tiff_quality(tiff_data)
        assert result is True

    def test_validate_tiff_quality_invalid_format(self):
        """Test TIFF quality validation with non-TIFF data"""
        converter = TIFFConverter()

        # Create a PNG instead of TIFF
        img = Image.new('RGB', (100, 100), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        png_data = buffer.getvalue()

        result = converter.validate_tiff_quality(png_data)
        assert result is False

    def test_validate_tiff_quality_corrupted_data(self):
        """Test TIFF quality validation with corrupted data"""
        converter = TIFFConverter()

        corrupted_data = b"not an image"
        result = converter.validate_tiff_quality(corrupted_data)
        assert result is False

    @patch('fitz.open')
    def test_pdf_to_images_success(self, mock_fitz_open, sample_pdf_data):
        """Test successful PDF to images conversion"""
        converter = TIFFConverter()

        # Mock PyMuPDF document and page
        mock_doc = Mock()
        mock_doc.page_count = 1

        mock_page = Mock()
        mock_pixmap = Mock()
        mock_pixmap.tobytes.return_value = b"PPM image data"

        mock_page.get_pixmap.return_value = mock_pixmap
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.close = Mock()

        mock_fitz_open.return_value = mock_doc

        # Mock PIL Image.open
        with patch('PIL.Image.open') as mock_image_open:
            mock_img = Image.new('RGB', (100, 100), color='white')
            mock_image_open.return_value = mock_img

            images = converter.pdf_to_images(sample_pdf_data)

            assert len(images) == 1
            assert isinstance(images[0], Image.Image)
            mock_doc.close.assert_called_once()

    @patch('fitz.open')
    def test_pdf_to_images_multiple_pages(self, mock_fitz_open, sample_pdf_data):
        """Test PDF to images conversion with multiple pages"""
        converter = TIFFConverter()

        # Mock PyMuPDF document with multiple pages
        mock_doc = Mock()
        mock_doc.page_count = 3

        mock_page = Mock()
        mock_pixmap = Mock()
        mock_pixmap.tobytes.return_value = b"PPM image data"

        mock_page.get_pixmap.return_value = mock_pixmap
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.close = Mock()

        mock_fitz_open.return_value = mock_doc

        # Mock PIL Image.open
        with patch('PIL.Image.open') as mock_image_open:
            mock_img = Image.new('RGB', (100, 100), color='white')
            mock_image_open.return_value = mock_img

            images = converter.pdf_to_images(sample_pdf_data)

            assert len(images) == 3
            for img in images:
                assert isinstance(img, Image.Image)

    @patch('fitz.open')
    def test_pdf_to_images_failure(self, mock_fitz_open, sample_pdf_data):
        """Test PDF to images conversion failure"""
        converter = TIFFConverter()

        mock_fitz_open.side_effect = Exception("Failed to open PDF")

        with pytest.raises(Exception) as exc_info:
            converter.pdf_to_images(sample_pdf_data)

        assert "Failed to convert PDF to images" in str(exc_info.value)

    @patch.object(TIFFConverter, 'pdf_to_images')
    @patch.object(TIFFConverter, 'images_to_tiff')
    def test_convert_pdf_to_tiff_success(self, mock_images_to_tiff, mock_pdf_to_images, sample_pdf_data, mock_image):
        """Test complete PDF to TIFF conversion workflow"""
        converter = TIFFConverter()

        # Setup mocks
        mock_pdf_to_images.return_value = [mock_image]
        mock_images_to_tiff.return_value = b"TIFF data"

        result = converter.convert_pdf_to_tiff(sample_pdf_data)

        assert result == b"TIFF data"
        mock_pdf_to_images.assert_called_once_with(sample_pdf_data)
        mock_images_to_tiff.assert_called_once()

    @patch.object(TIFFConverter, 'pdf_to_images')
    def test_convert_pdf_to_tiff_no_pages(self, mock_pdf_to_images, sample_pdf_data):
        """Test PDF to TIFF conversion with no pages"""
        converter = TIFFConverter()

        mock_pdf_to_images.return_value = []

        with pytest.raises(Exception) as exc_info:
            converter.convert_pdf_to_tiff(sample_pdf_data)

        assert "No pages found in PDF document" in str(exc_info.value)

    @patch.object(TIFFConverter, 'pdf_to_images')
    def test_convert_pdf_to_tiff_conversion_failure(self, mock_pdf_to_images, sample_pdf_data):
        """Test PDF to TIFF conversion with conversion failure"""
        converter = TIFFConverter()

        mock_pdf_to_images.side_effect = Exception("Conversion failed")

        with pytest.raises(Exception):
            converter.convert_pdf_to_tiff(sample_pdf_data)