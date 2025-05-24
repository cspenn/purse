import httpx # For specific exception check
from bs4 import BeautifulSoup, NavigableString, Comment # For HTML parsing
from markdownify import markdownify as md # For HTML to Markdown conversion
import chardet # For detecting character encoding
import re # For regex operations
from urllib.parse import urljoin, urlparse # For URL manipulation
from datetime import datetime, timezone # For date handling
import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pathlib import Path # For Path().name
from pathy import Pathy # For handling local and cloud paths seamlessly (if needed for file parsing)
                       # For now, assuming bytes are passed in for file parsing.
from io import BytesIO # For handling byte streams, e.g. for PDF parsing

# PDF and DOCX parsing (optional dependencies, handle ImportError)
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    PdfReader = None # type: ignore # Placeholder if not available

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    DocxDocument = None # type: ignore # Placeholder

# Local imports
from src.services.http_client import HttpClient
from src.models.article import Article
from src.utils import common, constants # For generate_uuid_from_url, estimate_reading_time, etc.

if TYPE_CHECKING:
    from src.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class ContentParserService:
    def __init__(self, http_client: HttpClient, config_manager: 'ConfigManager'):
        self.http_client = http_client
        self.config_manager = config_manager
        self.retry_config = common.get_retry_config(self.config_manager)
        self.max_pdf_size_bytes = self.config_manager.get('content_limits.max_pdf_size_bytes', 50 * 1024 * 1024) # Default 50MB
        self.max_docx_size_bytes = self.config_manager.get('content_limits.max_docx_size_bytes', 20 * 1024 * 1024) # Default 20MB

    async def parse_url(self, url: str, use_fallback: bool = True) -> Optional[Article]:
        """
        Fetches content from a URL, parses it, and returns an Article object.
        Handles potential "Content too large" errors from HttpClient.
        """
        content_html: Optional[str] = None
        article_title_override: Optional[str] = None # Used if content is too large
        
        try:
            logger.info(f"Attempting to fetch and parse URL: {url}")
            response = await self.http_client.get_url(url, is_html_content=True)
            content_html = response.text 
            
        except httpx.HTTPError as e_http: # Catch specific HTTPError first
            if "Content too large" in str(e_http):
                logger.warning(f"Content at {url} exceeded size limits: {e_http}")
                return self.create_bookmark_article(url, title=f"Bookmark (Content Too Large): {Path(url).name}", notes=f"Content at URL {url} exceeded size limits.")
            logger.warning(f"HTTP error fetching primary URL {url}: {e_http}", exc_info=True)
            # Fall through to generic exception handling for fallback logic
            if not use_fallback:
                 return self.create_bookmark_article(url, title=f"Bookmark: {Path(url).name}", notes=f"Failed to fetch content. Error: {e_http}")
            # If use_fallback is true, the generic exception below will handle it.
            # Need to ensure error 'e' is defined for notes in fallback.
            # Re-raise to be caught by generic Exception or let it fall through.
            # For simplicity, let the generic handler catch it if fallback is enabled.
            # If no fallback, create bookmark now.
            pass # Let generic handler proceed if fallback is enabled
        except Exception as e: # Generic exception for other issues (network, etc.)
            logger.warning(f"Failed to fetch primary URL {url}: {e}", exc_info=True)
            if not use_fallback:
                return self.create_bookmark_article(url, title=f"Bookmark: {Path(url).name}", notes=f"Failed to fetch content. Error: {e}")

        # Fallback mechanism if primary fetch failed (content_html is None or exception occurred)
        if not content_html and use_fallback:
            archive_template = self.config_manager.get('content_parser.archive_url_template')
            if archive_template:
                archive_url = archive_template.format(url=url)
                logger.info(f"Attempting fallback fetch from: {archive_url}")
                try:
                    response = await self.http_client.get_url(archive_url, timeout=60.0, is_html_content=True) 
                    content_html = response.text
                    logger.info(f"Successfully fetched from fallback URL: {archive_url}")
                except httpx.HTTPError as e_archive_http:
                    if "Content too large" in str(e_archive_http):
                        logger.warning(f"Content at fallback {archive_url} exceeded size limits: {e_archive_http}")
                        # Primary fetch error 'e' might not be defined here if first try was not an exception but empty content_html
                        # For now, just note the fallback error.
                        return self.create_bookmark_article(url, title=f"Bookmark (Content Too Large): {Path(url).name}", notes=f"Content at fallback {archive_url} exceeded size limits.")
                    logger.error(f"Fallback fetch HTTP error for {archive_url}: {e_archive_http}", exc_info=True)
                    return self.create_bookmark_article(url, title=f"Bookmark: {Path(url).name}", notes=f"Failed to fetch content from primary and fallback. Fallback HTTP error: {e_archive_http}")
                except Exception as e_archive_generic:
                    logger.error(f"Fallback fetch generic error for {archive_url}: {e_archive_generic}", exc_info=True)
                    return self.create_bookmark_article(url, title=f"Bookmark: {Path(url).name}", notes=f"Failed to fetch content from primary and fallback. Fallback error: {e_archive_generic}")
            else:
                logger.info("No fallback URL template configured.")
                # If primary fetch resulted in an error 'e', it should be used in notes.
                # This part is tricky if 'e' is not in scope from the first try-except.
                # Assuming if content_html is None, and we are here, an error occurred or content was empty.
                return self.create_bookmark_article(url, title=f"Bookmark: {Path(url).name}", notes="Failed to fetch content from primary URL, and no fallback available or fallback failed.")

        if not content_html:
            logger.warning(f"No HTML content retrieved for URL: {url}")
            return self.create_bookmark_article(url, title=f"Bookmark (No Content): {Path(url).name}", notes="No content could be retrieved from the URL or its fallback.")

        # Proceed with parsing if content_html is available
        soup = BeautifulSoup(content_html, 'html.parser')
        
        title = self._extract_title(soup) or Path(url).name # Use filename/URL part if title not found
        author = self._extract_author(soup, url) 
        content_markdown = self._html_to_markdown(soup)
        content_text = self._extract_text_from_soup(soup)
        word_count = len(content_text.split())
        
        return Article(
            id=common.generate_uuid_from_url(url),
            original_url=url,
            title=title,
            author=author,
            content_markdown=content_markdown,
            content_text=content_text,
            saved_date=datetime.now(timezone.utc),
            source_type=constants.SOURCE_TYPE_URL,
            word_count=word_count,
            estimated_read_time_minutes=common.estimate_reading_time(word_count)
        )

    def parse_pdf_from_bytes(self, pdf_bytes: bytes, original_url: str = "local.pdf") -> Optional[Article]:
        """Parses PDF content from bytes into an Article object."""
        if len(pdf_bytes) > self.max_pdf_size_bytes:
            logger.warning(f"PDF content size {len(pdf_bytes)} for '{original_url}' exceeds limit {self.max_pdf_size_bytes}.")
            return self.create_bookmark_article(
                url=original_url,
                title=f"PDF (File Too Large): {Path(original_url).name}",
                notes=f"PDF file '{Path(original_url).name}' is too large to process (size: {len(pdf_bytes)} bytes, limit: {self.max_pdf_size_bytes} bytes)."
            )

        if not PYPDF_AVAILABLE:
            logger.error("PyPDF not installed. Cannot parse PDF content.")
            return self.create_bookmark_article(original_url, title=f"PDF Bookmark: {Path(original_url).name}", notes="PyPDF library not available for parsing.")

        try:
            reader = PdfReader(BytesIO(pdf_bytes))
            text_content = ""
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text_content += page.extract_text() or "" 
                if page_num < len(reader.pages) - 1: 
                    text_content += "\n\n---\n\n" 

            if not text_content.strip():
                logger.warning(f"No text could be extracted from PDF: {original_url}")
                return self.create_bookmark_article(original_url, title=f"PDF Bookmark (No Text): {Path(original_url).name}", notes="No text content could be extracted from the PDF.")

            content_markdown = f"# {Path(original_url).name}\n\n{text_content}"

            metadata = reader.metadata
            title = str(metadata.title) if metadata.title else Path(original_url).name 
            author = str(metadata.author) if metadata.author else None
            
            saved_date = datetime.now(timezone.utc)
            word_count = len(text_content.split())

            return Article(
                id=common.generate_uuid_from_url(original_url + str(len(pdf_bytes))), 
                original_url=original_url,
                title=title, 
                content_markdown=content_markdown,
                content_text=text_content, 
                author=author,
                saved_date=saved_date,
                source_type="pdf_file",
                word_count=word_count,
                estimated_read_time_minutes=common.estimate_reading_time(word_count),
            )
        except Exception as e:
            logger.error(f"Error parsing PDF bytes from {original_url}: {e}", exc_info=True)
            return self.create_bookmark_article(original_url, title=f"PDF Bookmark (Error): {Path(original_url).name}", notes=f"Error parsing PDF: {e}")

    def parse_docx_from_bytes(self, docx_bytes: bytes, original_url: str = "local.docx") -> Optional[Article]:
        """Parses DOCX content from bytes into an Article object."""
        if len(docx_bytes) > self.max_docx_size_bytes:
            logger.warning(f"DOCX content size {len(docx_bytes)} for '{original_url}' exceeds limit {self.max_docx_size_bytes}.")
            return self.create_bookmark_article(
                url=original_url,
                title=f"DOCX (File Too Large): {Path(original_url).name}",
                notes=f"DOCX file '{Path(original_url).name}' is too large to process (size: {len(docx_bytes)} bytes, limit: {self.max_docx_size_bytes} bytes)."
            )

        if not DOCX_AVAILABLE:
            logger.error("python-docx not installed. Cannot parse DOCX content.")
            return self.create_bookmark_article(original_url, title=f"DOCX Bookmark: {Path(original_url).name}", notes="python-docx library not available for parsing.")
        
        try:
            document = DocxDocument(BytesIO(docx_bytes))
            
            text_content_parts = [p.text for p in document.paragraphs]
            text_content = "\n\n".join(text_content_parts) 

            if not text_content.strip():
                logger.warning(f"No text could be extracted from DOCX: {original_url}")
                return self.create_bookmark_article(original_url, title=f"DOCX Bookmark (No Text): {Path(original_url).name}", notes="No text content could be extracted from the DOCX.")

            content_markdown = f"# {Path(original_url).name}\n\n{text_content}"

            core_props = document.core_properties
            title = str(core_props.title) if core_props.title else Path(original_url).name
            author = str(core_props.author) if core_props.author else None
            
            saved_date = datetime.now(timezone.utc)
            word_count = len(text_content.split())

            return Article(
                id=common.generate_uuid_from_url(original_url + str(len(docx_bytes))),
                original_url=original_url,
                title=title, 
                content_markdown=content_markdown,
                content_text=text_content,
                author=author,
                saved_date=saved_date,
                source_type="docx_file",
                word_count=word_count,
                estimated_read_time_minutes=common.estimate_reading_time(word_count),
            )
        except Exception as e:
            logger.error(f"Error parsing DOCX bytes from {original_url}: {e}", exc_info=True)
            return self.create_bookmark_article(original_url, title=f"DOCX Bookmark (Error): {Path(original_url).name}", notes=f"Error parsing DOCX: {e}")

    def create_bookmark_article(self, url: str, title: Optional[str] = None, notes: Optional[str] = None) -> Article:
        """Creates a basic Article object, typically used as a fallback or for unparsable content."""
        final_title = title if title else f"Bookmark: {url}"
        # Ensure notes are not excessively long, if they come from error messages.
        notes_content = f"Notes: {notes[:500]}" if notes else "Content could not be parsed or fetched."
        
        # Use Path(url).name for filename-like title if a full title isn't available
        if not title and (url.startswith("file:") or not urlparse(url).scheme):
            final_title = Path(urlparse(url).path).name
            if not notes: # If no specific error, note that it's a local file bookmark
                 notes_content = "Bookmark for local file."


        return Article(
            id=common.generate_uuid_from_url(url),
            original_url=url,
            title=final_title,
            content_markdown=f"# {final_title}\n\nOriginal URL: [{url}]({url})\n\n{notes_content}",
            content_text=f"{final_title}\nOriginal URL: {url}\n{notes_content}",
            saved_date=datetime.now(timezone.utc),
            source_type=constants.SOURCE_TYPE_BOOKMARK, # Mark as a simple bookmark
            word_count=0,
            estimated_read_time_minutes=0,
            # Other fields like author, tags, status can be defaults or None
        )

    # --- Internal Helper Methods ---
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extracts the title from the parsed HTML (soup)."""
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        # Fallback: Try OpenGraph title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
        # Fallback: Try h1
        h1_tag = soup.find('h1')
        if h1_tag and h1_tag.string:
            return h1_tag.string.strip()
        return None

    def _extract_author(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extracts the author from parsed HTML (soup) or URL metadata."""
        # Try OpenGraph author
        og_author = soup.find('meta', property='article:author')
        if og_author and og_author.get('content'):
            return og_author['content'].strip()
        
        # Try standard meta author tag
        meta_author = soup.find('meta', attrs={'name': 'author'})
        if meta_author and meta_author.get('content'):
            return meta_author['content'].strip()
            
        # Try specific site conventions (example: byline in schema.org)
        json_ld_script = soup.find('script', type='application/ld+json')
        if json_ld_script and json_ld_script.string:
            try:
                data = json.loads(json_ld_script.string)
                if isinstance(data, list): data = data[0] # Get first item if it's a list
                if data.get('@type') == 'NewsArticle' or data.get('@type') == 'Article':
                    author_data = data.get('author')
                    if author_data:
                        if isinstance(author_data, list): # Author can be a list of objects
                            return author_data[0].get('name') if author_data else None
                        elif isinstance(author_data, dict):
                            return author_data.get('name')
            except json.JSONDecodeError:
                pass # Ignore malformed JSON-LD
        
        # Fallback: Use site name from URL as a proxy for author/publisher if specific author not found
        parsed_url = urlparse(url)
        if parsed_url.netloc:
            # Remove 'www.' if present, and try to make it a bit more readable
            site_name = parsed_url.netloc.replace('www.', '')
            # Could add more cleaning here (e.g., TLD removal, capitalization)
            return site_name
        return None

    def _html_to_markdown(self, soup: BeautifulSoup) -> str:
        """Converts HTML (soup) to Markdown, with some cleanup."""
        # Basic conversion using markdownify
        # Consider options for markdownify: strip tags, convert links, etc.
        # Example: md(str(soup), strip=['script', 'style'], heading_style='atx')
        
        # Attempt to select a main content area if possible (very heuristic)
        # This is highly dependent on website structure and often unreliable.
        # Common patterns: <article>, <main>, div with id="content" or class="main-content"
        main_content_el = soup.find('article') or \
                          soup.find('main') or \
                          soup.find(id=re.compile(r'content|main', re.I)) or \
                          soup.find(class_=re.compile(r'content|main|article|post-body', re.I))

        if main_content_el:
            logger.debug(f"Attempting Markdown conversion on detected main content element: {main_content_el.name}{main_content_el.attrs.get('id', '')}{main_content_el.attrs.get('class', '')}")
            # Remove known clutter from the selected main content
            self._remove_clutter_elements(main_content_el)
            content_to_convert = str(main_content_el)
        else:
            logger.debug("No specific main content element found, converting entire body.")
            # If no main content found, try to clean up the whole body
            body_el = soup.body
            if body_el:
                self._remove_clutter_elements(body_el)
                content_to_convert = str(body_el)
            else: # Fallback to the whole soup if no body tag (should be rare for valid HTML)
                content_to_convert = str(soup)
        
        # Convert to Markdown
        markdown_content = md(content_to_convert, heading_style='ATX', bullets='*')
        
        # Further cleanup specific to Markdown (e.g., excessive newlines)
        markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content).strip()
        
        return markdown_content

    def _remove_clutter_elements(self, soup_element: BeautifulSoup) -> None:
        """Removes common clutter (nav, footer, ads, scripts, styles) from a BeautifulSoup element in-place."""
        tags_to_remove = ['nav', 'footer', 'aside', 'script', 'style', 'form', 'iframe']
        selectors_to_remove = [
            "[class*='ad']", "[id*='ad']", # Ads by class/id
            "[class*='share']", "[id*='share']", # Share buttons
            "[class*='comment']", "[id*='comment']", # Comment sections
            "[class*='sidebar']", "[id*='sidebar']", # Sidebars
            "[class*='header']", "[id*='header']", # Headers (can be too broad, use carefully)
            "[class*='footer']", "[id*='footer']", # Footers
            "[class*='popup']", "[id*='popup']", # Popups
            "[aria-hidden='true']" # Often used for modals or decorative elements
        ]

        for tag_name in tags_to_remove:
            for tag in soup_element.find_all(tag_name):
                tag.decompose()
        
        for selector in selectors_to_remove:
            try:
                for tag in soup_element.select(selector):
                    tag.decompose()
            except Exception as e:
                logger.debug(f"Error applying selector '{selector}' for clutter removal: {e}")
        
        # Remove comments
        for comment in soup_element.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()


    def _extract_text_from_soup(self, soup: BeautifulSoup) -> str:
        """Extracts all human-readable text from parsed HTML (soup)."""
        # Remove script and style elements first
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # Get text, then remove leading/trailing whitespace from each line
        # and join lines with a single space.
        lines = (line.strip() for line in soup.get_text().splitlines())
        # Filter out empty lines, then join.
        text = "\n".join(line for line in lines if line)
        return text.strip()

