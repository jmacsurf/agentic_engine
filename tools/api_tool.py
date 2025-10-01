"""
API Tool Agent for Agentic Choreography Engine

This tool provides REST API integration capabilities for connecting
to external web services and APIs.
"""

import requests
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from urllib.parse import urljoin, urlparse
import time
from tool_framework import BaseToolAgent, ToolResult, ToolCapabilities
import uuid
from types import SimpleNamespace

logger = logging.getLogger(__name__)

class APIToolAgent(BaseToolAgent):
    """Tool agent for REST API operations"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.rate_limits = {}

        # Configure session
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            })

    @property
    def description(self) -> str:
        return "REST API integration tool for connecting to web services and external APIs"

    @property
    def capabilities(self) -> ToolCapabilities:
        return ToolCapabilities(
            name=self.name,
            description=self.description,
            input_types=["api_spec", "http_request", "endpoint_config"],
            output_types=["api_response", "json_data", "error_details"],
            capabilities=[
                "rest_apis", "http_methods", "authentication",
                "rate_limiting", "json_processing", "error_handling"
            ],
            reliability_score=0.88,
            avg_execution_time=2.1
        )

    def validate_input(self, task: Dict[str, Any]) -> bool:
        return "endpoint" in task or "url" in task

    def execute(self, task: Dict[str, Any]) -> ToolResult:
        """Execute API operations"""

        start_time = time.time()
        execution_id = str(uuid.uuid4())

        try:
            # Extract request parameters
            method = task.get("method", "GET").upper()
            endpoint = task.get("endpoint", task.get("url", ""))
            params = task.get("params", {})
            data = task.get("data")
            headers = task.get("headers", {})

            # Handle rate limiting
            if not self._check_rate_limit(endpoint):
                raise Exception("Rate limit exceeded for this endpoint")

            # Build full URL
            full_url = urljoin(self.base_url or "", endpoint)

            # Prepare request
            request_kwargs = {
                "method": method,
                "url": full_url,
                "params": params if method in ["GET", "DELETE"] else None,
                "json": data if data else None,
                "headers": headers,
                "timeout": task.get("timeout", 30)
            }

            # Execute request
            response = self.session.request(**request_kwargs)

            # Update rate limiting info
            self._update_rate_limit(endpoint, response.status_code)

            # Process response
            result = self._process_response(response)

            execution_time = time.time() - start_time
            self.update_metrics(execution_time, response.status_code < 400)

            return ToolResult(
                tool_name=self.name,
                execution_id=execution_id,
                success=response.status_code < 400,
                output=result,
                execution_time=execution_time,
                metadata={
                    "method": method,
                    "url": full_url,
                    "status_code": response.status_code,
                    "response_size": len(response.content)
                }
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"API operation failed: {e}")
            self.update_metrics(execution_time, False)

            return ToolResult(
                tool_name=self.name,
                execution_id=execution_id,
                success=False,
                output=None,
                error_message=str(e),
                execution_time=execution_time
            )

    def _check_rate_limit(self, endpoint: str) -> bool:
        """Check if rate limit allows request"""
        domain = urlparse(endpoint).netloc

        if domain not in self.rate_limits:
            return True

        rate_info = self.rate_limits[domain]
        now = datetime.now()

        # Simple rate limiting: max 10 requests per minute per domain
        if len(rate_info["requests"]) >= 10:
            oldest_request = rate_info["requests"][0]
            if now - oldest_request < timedelta(minutes=1):
                return False
            else:
                # Remove old requests
                rate_info["requests"] = [
                    req for req in rate_info["requests"]
                    if now - req < timedelta(minutes=1)
                ]

        rate_info["requests"].append(now)
        return True

    def _update_rate_limit(self, endpoint: str, status_code: int):
        """Update rate limiting information"""
        domain = urlparse(endpoint).netloc

        if domain not in self.rate_limits:
            self.rate_limits[domain] = {
                "requests": [],
                "error_count": 0,
                "last_error": None
            }

        if status_code >= 400:
            self.rate_limits[domain]["error_count"] += 1
            self.rate_limits[domain]["last_error"] = datetime.now()

    def _process_response(self, response) -> Dict[str, Any]:
        """Process API response into standard format"""

        result = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "url": response.url,
            "method": response.request.method,
            "timestamp": datetime.now().isoformat()
        }

        # Try to parse JSON response
        try:
            if response.headers.get('content-type', '').startswith('application/json'):
                result["json"] = response.json()
            else:
                result["text"] = response.text
        except Exception as e:
            result["text"] = response.text
            result["parse_error"] = str(e)

        # Add pagination info if present
        if 'Link' in response.headers:
            result["pagination"] = self._parse_link_header(response.headers['Link'])

        # Add rate limit info if present
        if 'X-RateLimit-Remaining' in response.headers:
            result["rate_limit"] = {
                "remaining": response.headers.get('X-RateLimit-Remaining'),
                "limit": response.headers.get('X-RateLimit-Limit'),
                "reset": response.headers.get('X-RateLimit-Reset')
            }

        return result

    def _parse_link_header(self, link_header: str) -> Dict[str, str]:
        """Parse GitHub-style Link header for pagination"""
        links = {}
        for link in link_header.split(','):
            parts = link.strip().split(';')
            if len(parts) >= 2:
                url = parts[0].strip()[1:-1]  # Remove < >
                rel = parts[1].strip()[5:-1]   # Remove rel="
                links[rel] = url
        return links

    def get_supported_methods(self) -> List[str]:
        """Get list of supported HTTP methods"""
        return ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

    def test_connection(self, url: str) -> Dict[str, Any]:
        """Test API connectivity"""
        try:
            response = self.session.get(url, timeout=10)
            return {
                "success": True,
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "available": response.status_code < 500
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "available": False
            }

    def format_output(self, result: Any) -> Dict[str, Any]:
        """Format API response for next agent"""
        formatted = super().format_output(result)

        # Add API-specific formatting
        if isinstance(result, dict) and "status_code" in result:
            formatted["http_status"] = result["status_code"]
            formatted["success"] = result["status_code"] < 400

            # Extract main data if it's a JSON response
            if "json" in result:
                formatted["data"] = result["json"]
            elif "text" in result:
                formatted["data"] = result["text"]

        return formatted

    def __del__(self):
        """Cleanup session"""
        if hasattr(self, 'session'):
            self.session.close()

# minimal mock APITool for local tests
class APITool:
    name = "API_Tool"
    description = "Mock API tool for testing"
    capabilities = SimpleNamespace(input_types=["json"], avg_execution_time=0.05)

    def validate_input(self, task):
        return True

    def execute(self, task):
        # return a simple result dict expected by orchestrator
        return {
            "tool_name": self.name,
            "success": True,
            "output": {"id": str(uuid.uuid4()), "input": task},
            "execution_time": self.capabilities.avg_execution_time
        }
