import aiohttp
import os
import logging
from typing import Dict, Optional
from src.models.request_models import CompleteRequestData


class TCRSApiClient:
    """Client for TCRS internal API calls"""

    def __init__(self):
        self.base_url = os.environ.get("TCRS_API_BASE_URL", "")
        self.function_key = os.environ.get("INTERNAL_FUNCTION_KEY", "")

        if not self.base_url or not self.function_key:
            raise ValueError("TCRS_API_BASE_URL and INTERNAL_FUNCTION_KEY must be set")

    async def get_request_data(self, request_id: str) -> CompleteRequestData:
        """Fetch complete request data from TCRS internal API"""
        url = f"{self.base_url}/api/internal/request-data/{request_id}"
        headers = {"x-function-key": self.function_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to fetch request data: {response.status} - {error_text}")

                    data = await response.json()
                    logging.info(f"Successfully fetched request data for {request_id}")
                    return CompleteRequestData(**data)

        except aiohttp.ClientError as e:
            logging.error(f"HTTP client error fetching request data for {request_id}: {str(e)}")
            raise Exception(f"Failed to connect to TCRS API: {str(e)}")
        except Exception as e:
            logging.error(f"Error fetching request data for {request_id}: {str(e)}")
            raise

    async def update_generation_status(self, request_id: str, status: str,
                                     file_urls: Optional[Dict[str, str]] = None,
                                     processing_time: Optional[int] = None,
                                     error_message: Optional[str] = None) -> None:
        """Update documentsGenerationTable via TCRS internal API"""
        url = f"{self.base_url}/api/internal/documents-generation/{request_id}"
        headers = {
            "Content-Type": "application/json",
            "x-function-key": self.function_key
        }

        payload = {
            "requestId": request_id,
            "status": status,
            "processingTimeMs": processing_time,
            "errorMessage": error_message
        }

        if file_urls:
            payload.update({
                "consolidatedPdfUrl": file_urls.get("consolidatedPdf"),
                "tiffImageUrl": file_urls.get("tiffImage")
            })

        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=headers, json=payload) as response:
                    if response.status not in [200, 204]:
                        error_text = await response.text()
                        logging.error(f"Failed to update status for {request_id}: {response.status} - {error_text}")
                        raise Exception(f"Failed to update document generation status: {response.status}")

                    logging.info(f"Successfully updated status to '{status}' for request {request_id}")

        except aiohttp.ClientError as e:
            logging.error(f"HTTP client error updating status for {request_id}: {str(e)}")
            raise Exception(f"Failed to connect to TCRS API for status update: {str(e)}")
        except Exception as e:
            logging.error(f"Error updating generation status for {request_id}: {str(e)}")
            raise