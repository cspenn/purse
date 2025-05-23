import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING

from purse.utils import common # For exponential_backoff_retry, get_retry_config
from purse.utils import constants # For DEFAULT_USER_AGENT

if TYPE_CHECKING:
    from purse.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class HttpClient:
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        
        # Default timeout can be overridden by config if needed, e.g.,
        # default_timeout = self.config_manager.get('http_client.timeout', 30.0)
        default_timeout = 30.0

        self.client = httpx.AsyncClient(
            http2=True,
            timeout=default_timeout,
            follow_redirects=True,
            headers={"User-Agent": constants.DEFAULT_USER_AGENT}
        )
        # The workplan for http_client (section 11) shows self.retry_config = get_retry_config(self.config_manager)
        # in __init__. This is good practice.
        self.retry_config = common.get_retry_config(self.config_manager)

    async def get_url(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None # Per-request timeout
    ) -> httpx.Response:
        """
        Fetches content from a URL with retry logic.
        The retry parameters are taken from self.retry_config, which is
        initialized from ConfigManager.
        """
        
        # The decorator needs to be applied to the actual fetch operation.
        # It will use the parameters from self.retry_config.
        @common.exponential_backoff_retry(
            max_attempts=self.retry_config['max_attempts'],
            initial_delay=self.retry_config['initial_delay'], # Key from get_retry_config
            max_delay=self.retry_config['max_delay'],       # Key from get_retry_config
            jitter=self.retry_config.get('jitter', True)    # Jitter from get_retry_config, default True
        )
        async def _fetch_with_retry() -> httpx.Response:
            # Combine client headers with per-request headers
            effective_headers = self.client.headers.copy()
            if headers:
                effective_headers.update(headers)

            # Determine effective timeout: per-request > client.timeout.read (if available) > client.timeout (general)
            effective_timeout: Optional[float] = timeout
            if effective_timeout is None:
                if self.client.timeout.read is not None : # type: ignore (httpx.Timeout types can be complex)
                     effective_timeout = self.client.timeout.read # type: ignore
                elif self.client.timeout.connect is not None: # Fallback if only connect timeout is explicitly set on client
                     effective_timeout = self.client.timeout.connect # type: ignore

            logger.debug(f"Fetching URL: {url} with params: {params}, timeout: {effective_timeout}")
            
            try:
                response = await self.client.get(
                    url,
                    headers=effective_headers,
                    params=params,
                    timeout=effective_timeout 
                )
                response.raise_for_status() # Raise HTTPStatusError for 4xx/5xx responses
                logger.info(f"🟢 Successfully fetched {url}, status: {response.status_code}")
                return response
            except httpx.HTTPStatusError as e:
                logger.error(f"🛑 HTTP error {e.response.status_code} for {url}: {e.response.text[:200] if e.response.text else ''}")
                raise # Re-raise to be caught by retry decorator or caller
            except httpx.RequestError as e:
                # Includes network errors, timeout errors, etc.
                logger.error(f"🛑 Request error for {url}: {type(e).__name__} - {e}")
                raise
            except Exception as e: # Catch any other unexpected errors during the request
                logger.error(f"🛑 Unexpected error fetching {url}: {type(e).__name__} - {e}")
                raise
        
        # Execute the wrapped fetch function
        # The exceptions raised by _fetch_with_retry (after retries are exhausted) will propagate from here.
        return await _fetch_with_retry()

    async def close(self) -> None:
        """Closes the underlying httpx.AsyncClient."""
        logger.debug("Closing HttpClient session.")
        await self.client.aclose()

# Example usage (typically not in this file, but for illustration):
# async def main():
#     # Assume ConfigManager is initialized
#     class MockConfigManager:
#         def get(self, key, default=None):
#             if key == 'retry.max_attempts': return 3
#             if key == 'retry.initial_delay_seconds': return 0.1
#             if key == 'retry.max_delay_seconds': return 1.0
#             if key == 'retry.jitter': return True
#             if key == 'http_client.timeout': return 20.0
#             return default

#     config_mgr = MockConfigManager()
#     http_client = HttpClient(config_mgr)
    
#     try:
#         # Test with a URL that might fail or a reliable one
#         # response = await http_client.get_url("https://httpstat.us/503") # Test retry
#         response = await http_client.get_url("https://www.example.com")
#         print(f"Content length: {len(response.text)}")
#     except Exception as e:
#         print(f"Failed to get URL after retries: {e}")
#     finally:
#         await http_client.close()

# if __name__ == '__main__':
#     # Setup basic logging for the example
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
#     asyncio.run(main())
