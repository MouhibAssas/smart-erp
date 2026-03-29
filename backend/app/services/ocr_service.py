"""
OCR Processor - Handles PDF and image text extraction using PaddleOCR
"""

import os
import logging
from typing import Dict, Optional
import fitz  # PyMuPDF
from PIL import Image, ImageOps
import numpy as np
from paddleocr import PaddleOCR
import cv2
import tempfile
import time
import io

logger = logging.getLogger(__name__)


class OCRProcessor:
    """
    Pure OCR text extraction processor
    Supports PDF and image files
    """
    
    def __init__(self):
        """Initialize PaddleOCR engine"""
        try:
            use_gpu = os.getenv('USE_GPU', 'false').lower() == 'true'
            ocr_language = os.getenv('OCR_LANGUAGE', 'fr')
            det_db_thresh = float(os.getenv('DET_DB_THRESH', '0.3'))
            det_db_box_thresh = float(os.getenv('DET_DB_BOX_THRESH', '0.5'))
            rec_algorithm = os.getenv('REC_ALGORITHM', 'SVTR_LCNet')

            logger.info(
                "OCR config: USE_GPU=%s, OCR_LANGUAGE=%s, DET_DB_THRESH=%s, DET_DB_BOX_THRESH=%s, REC_ALGORITHM=%s",
                use_gpu,
                ocr_language,
                det_db_thresh,
                det_db_box_thresh,
                rec_algorithm
            )

            if det_db_thresh <= 0 or det_db_thresh >= 1:
                logger.warning("DET_DB_THRESH should be between 0 and 1. Current: %s", det_db_thresh)
            if det_db_box_thresh <= 0 or det_db_box_thresh >= 1:
                logger.warning("DET_DB_BOX_THRESH should be between 0 and 1. Current: %s", det_db_box_thresh)

            # Initialize PaddleOCR
            # use_angle_cls=True enables text orientation detection
            # lang='en' for English (use 'ch' for Chinese, 'fr' for French, etc.)
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang=ocr_language,
                det_db_thresh=det_db_thresh,
                det_db_box_thresh=det_db_box_thresh,
                rec_algorithm=rec_algorithm,
                use_gpu=use_gpu,  # Set to True if GPU available
                show_log=False
            )
            logger.info("PaddleOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise
    
    def process_document(self, file_path: str) -> Dict:
        """
        Process document and extract raw text
        
        Args:
            file_path: Path to document file
            
        Returns:
            Dict with raw_text, confidence, and page_count
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            return self._process_pdf(file_path)
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            return self._process_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

    def extract_from_bytes(self, file_bytes: bytes, filename: str) -> Dict:
        """
        Entry point for in-memory upload bytes.
        Writes bytes to a temp file, delegates to process_document, then cleans up.
        """
        suffix = os.path.splitext(filename)[1].lower() if filename else ""
        if not suffix:
            suffix = ".bin"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            return self.process_document(tmp_path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Could not delete temp file {tmp_path}: {e}")
    
    def _process_pdf(self, pdf_path: str) -> Dict:
        """
        Extract text from PDF by converting pages to images
        Uses high-resolution conversion and preprocessing for better accuracy
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dict with extracted text and metadata
        """
        temp_files = []
        try:
            doc = fitz.open(pdf_path)
            all_text = []
            all_confidences = []
            
            logger.info(f"Processing PDF with {len(doc)} pages")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Convert page to high-resolution image
                # 4x zoom = ~290 DPI for better OCR accuracy
                mat = fitz.Matrix(4.0, 4.0)
                pix = page.get_pixmap(matrix=mat)

                # Convert pixmap to PIL Image
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data))

                # PREPROCESSING: Improve quality for OCR
                # 1. Convert to grayscale (reduces color noise)
                if pil_image.mode != 'L':
                    pil_image = ImageOps.grayscale(pil_image)
                
                # 2. Apply autocontrast (improves text/background contrast)
                pil_image = ImageOps.autocontrast(pil_image, cutoff=10)

                # Save preprocessed image to temp file
                # PaddleOCR works better with file paths than numpy arrays
                with tempfile.NamedTemporaryFile(delete=False, suffix=f"_page{page_num}.png") as temp_file:
                    temp_file_path = temp_file.name
                
                pil_image.save(temp_file_path, 'PNG')
                temp_files.append(temp_file_path)
                
                # Explicitly free memory
                pix = None
                pil_image = None
                
                logger.info(f"Page {page_num + 1}/{len(doc)}: High-resolution image saved with preprocessing")
                
                # Run OCR on preprocessed image file
                page_result = self._ocr_from_file(temp_file_path)
                all_text.append(page_result['text'])
                all_confidences.append(page_result['confidence'])
                
                logger.info(f"Page {page_num + 1}/{len(doc)} processed with confidence {page_result['confidence']:.2%}")
            
            # Save page count before closing
            page_count = len(doc)
            doc.close()
            
            # Combine results
            combined_text = "\n\n".join(all_text)
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
            
            return {
                'raw_text': combined_text,
                'confidence': round(avg_confidence, 3),
                'page_count': page_count
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            raise
        finally:
            # Clean up temp files
            for temp_path in temp_files:
                try:
                    time.sleep(0.1)  # Small delay to ensure files are released
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"Could not delete temp file {temp_path}: {cleanup_error}")
            
            if temp_files:
                logger.info(f"{len(temp_files)} temp file(s) cleaned up")
    
    def _process_image(self, image_path: str) -> Dict:
        """
        Extract text from image file
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict with extracted text and metadata
        """
        try:
            # Load image
            img = cv2.imread(image_path)
            
            if img is None:
                raise ValueError(f"Failed to load image: {image_path}")
            
            # Run OCR
            result = self._ocr_image_array(img)
            
            return {
                'raw_text': result['text'],
                'confidence': result['confidence'],
                'page_count': 1
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            raise
    
    def _ocr_from_file(self, file_path: str) -> Dict:
        """
        Run OCR on image file (more accurate than numpy array)
        
        Args:
            file_path: Path to image file
            
        Returns:
            Dict with text and confidence
        """
        try:
            # Run PaddleOCR on file
            result = self.ocr.ocr(file_path, cls=True)
            
            if not result or not result[0]:
                return {
                    'text': '',
                    'confidence': 0.0
                }
            
            # Extract text and confidence scores with robust parsing
            texts = []
            confidences = []
            
            # Iterate through all pages/results
            for page in result:
                if not page:
                    continue
                
                # Each line: [bbox_coords, (text, confidence_score)]
                for line in page:
                    if not line or len(line) < 2:
                        continue
                    
                    bbox = line[0]
                    text_info = line[1]
                    
                    text = None
                    confidence = 0.0
                    
                    # Verify that text_info is actually (text, confidence) and not a coord
                    # A bbox coord would be: [[float, float], [float, float], ...]
                    # But text_info should be: (str, float) or ["text", float]
                    if isinstance(text_info, (tuple, list)) and len(text_info) >= 2:
                        potential_text = text_info[0]
                        potential_conf = text_info[1]
                        
                        # If text_info[0] is a number (coord), it's not the right format
                        if isinstance(potential_text, str):
                            text = potential_text
                            confidence = potential_conf
                        elif isinstance(potential_text, (int, float)):
                            # It's a coord bbox, not text - skip
                            continue
                    
                    # Validate the text
                    if text is None:
                        continue
                    
                    # Normalize the text
                    text = text.strip()
                    
                    # Normalize confidence (must be float between 0 and 1)
                    if isinstance(confidence, (int, float)):
                        conf_float = float(confidence)
                    else:
                        conf_float = 0.0
                    
                    # Add only if text is not empty
                    if text:
                        texts.append(text)
                        confidences.append(conf_float)
            
            # Combine text preserving structure
            combined_text = "\n".join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            logger.info(f"Extracted {len(texts)} line(s) with avg confidence {avg_confidence:.2%}")
            
            return {
                'text': combined_text,
                'confidence': round(avg_confidence, 3)
            }
            
        except Exception as e:
            logger.error(f"Error in OCR processing: {e}")
            raise
    
    def _ocr_image_array(self, img_array: np.ndarray) -> Dict:
        """
        Run OCR on numpy image array (fallback method)
        For best accuracy, use _ocr_from_file instead
        
        Args:
            img_array: Image as numpy array
            
        Returns:
            Dict with text and confidence
        """
        try:
            # Save to temp file for better accuracy
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                temp_path = temp_file.name
            
            # Convert numpy array to PIL Image and save
            img = Image.fromarray(img_array)
            img.save(temp_path, 'PNG')
            
            try:
                # Use file-based OCR
                return self._ocr_from_file(temp_path)
            finally:
                # Clean up temp file
                try:
                    time.sleep(0.1)
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"Could not delete temp file: {cleanup_error}")
            
        except Exception as e:
            logger.error(f"Error in OCR processing: {e}")
            raise


_ocr_processor_instance: Optional[OCRProcessor] = None

# hedha singleton pattern (One instance of this object in the app onlyy)
def _get_processor() -> OCRProcessor:
    global _ocr_processor_instance
    if _ocr_processor_instance is None:
        _ocr_processor_instance = OCRProcessor()
    return _ocr_processor_instance


def extract(file_bytes: bytes, filename: str) -> Dict:
    """
    Module-level helper used by chat_service fallback.
    """
    return _get_processor().extract_from_bytes(file_bytes=file_bytes, filename=filename)