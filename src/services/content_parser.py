import trafilatura
import fitz  # PyMuPDF
import docx  # python-docx
import logging
import io
from datetime import datetime, timezone # Not directly used, but common.py functions might
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING, List
from urllib.parse import urlparse
from pathlib import Path

from purse.models.article import Article
from purse.services.http_client import HttpClient
from purse.utils import common, constants

# Optional: langdetect for language detection if trafilatura isn't sufficient
# try:
#     from langdetect import detect as detect_language, LangDetectException
# except ImportError:
#     detect_language = None
#     LangDetectException = None

if TYPE_CHECKING:
    from purse.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class ContentParserService:
    def __init__(self, http_client: HttpClient, config_manager: 'ConfigManager'):
        self.http_client = http_client
        self.config_manager = config_manager
        # retry_config is fetched from config_manager by HttpClient itself for its internal retries.
        # If ContentParserService needs its own retry logic for steps other than http_client.get_url,
        # then self.retry_config would be needed here.
        # The workplan for parse_url shows http_client.get_url is decorated by exponential_backoff_retry
        # inside HttpClient, so ContentParserService doesn't need to re-apply it here for the main fetch.
        # However, the workplan for THIS service (section 13) says:
        # "self.retry_config = common.get_retry_config(self.config_manager)"
        # This implies it might be used for something, or it's a slight redundancy.
        # For now, I'll include it as per workplan for this section.
        self.retry_config = common.get_retry_config(self.config_manager)


    async def parse_url(self, url: str, use_fallback: bool = True) -> Optional[Article]:
        """
        Fetches and parses content from a web URL.
        Uses Trafilatura primarily. Can use archive.is as fallback.
        """
        logger.info(f"🟢 Attempting to parse URL: {url}")
        is_archived = False
        content_html: Optional[str] = None
        # This variable will hold the URL that successfully provided the content (original or archive)
        fetched_from_url = url 

        try:
            # HttpClient.get_url already has retry logic.
            response = await self.http_client.get_url(url)
            content_html = response.text
        except Exception as e:
            logger.warning(f"🟡 Failed to fetch directly from {url}: {e}")
            if not use_fallback:
                logger.error(f"🛑 Fallback disabled, parsing failed for {url}.")
                # Create a simple bookmark for the failed URL without content
                return self.create_bookmark_article(url, title=f"Bookmark (Fetch Failed): {url}", notes=f"Failed to fetch content: {e}")
            
            archive_template = self.config_manager.get('fallback_archive_service_url_template')
            if archive_template:
                # Ensure URL is properly encoded for insertion into template if needed, though usually just string format
                archive_url = archive_template.format(url=url)
                fetched_from_url = archive_url # Update the source URL to the archive one
                logger.info(f"Attempting fallback fetch from: {archive_url}")
                try:
                    # Using a longer timeout for archive services can be beneficial
                    # The default timeout is from HttpClient's init, but can be overridden.
                    # Workplan for HttpClient: get_url(timeout: Optional[float] = None)
                    # Workplan for ContentParser: http_client.get_url(archive_url, timeout=60.0)
                    response = await self.http_client.get_url(archive_url, timeout=60.0)
                    content_html = response.text
                    is_archived = True
                    logger.info(f"🟢 Successfully fetched from fallback: {archive_url}")
                except Exception as arc_e:
                    logger.error(f"🛑 Fallback fetch also failed for {url} from {archive_url}: {arc_e}")
                    return self.create_bookmark_article(url, title=f"Bookmark (Fallback Failed): {url}", notes=f"Direct fetch failed: {e}\nFallback fetch failed: {arc_e}")
            else:
                logger.error(f"🛑 Fallback service URL template not configured. Cannot use fallback for {url}.")
                return self.create_bookmark_article(url, title=f"Bookmark (Fallback Not Configured): {url}", notes=f"Direct fetch failed: {e}\nFallback not configured.")

        if not content_html:
            logger.error(f"🛑 No HTML content fetched for {url} (original or fallback).")
            return self.create_bookmark_article(url, title=f"Bookmark (No Content): {url}", notes="No HTML content could be fetched.")

        try:
            extracted_data = trafilatura.bare_extraction(
                content_html,
                include_links=True,        # Keep links in the extracted text
                include_formatting=True,   # Try to preserve some formatting as Markdown
                include_images=True,       # Include image links/sources if possible
                output_format='markdown',  # Output main text as Markdown
                deduplicate=True           # Remove duplicate text sections
            )

            if not extracted_data or not extracted_data.get('text', '').strip():
                logger.warning(f"🟡 Trafilatura extracted no main content from {fetched_from_url} (source: {url}). Might be non-article page or requires JavaScript.")
                page_title = "Bookmark"
                try:
                    # Attempt to get a title from metadata even if content extraction failed
                    metadata_obj = trafilatura.extract_metadata(content_html)
                    if metadata_obj and metadata_obj.title:
                        page_title = metadata_obj.title
                    elif extracted_data and extracted_data.get('title'): # Sometimes bare_extraction gets title but no text
                        page_title = extracted_data.get('title')
                    else: # Fallback title
                        page_title = f"Bookmark: {url}"
                except Exception as meta_exc:
                    logger.warning(f"🟡 Could not extract title metadata for {url}: {meta_exc}")
                    page_title = f"Bookmark: {url}"

                return self.create_bookmark_article(
                    url=url, # Original URL for the bookmark ID
                    title=page_title,
                    notes=f"Content could not be extracted from {fetched_from_url}. Saved as bookmark."
                ) # archived_from_fallback is not explicitly set here, but create_bookmark_article doesn't take it.
                  # Let's ensure the Article from create_bookmark_article can reflect this if needed.
                  # For now, the note indicates source.

            markdown_content = extracted_data.get('text', "").strip()
            article_title = extracted_data.get('title') or Path(urlparse(url).path).stem or "Untitled Article"
            
            authors_str = extracted_data.get('author')
            authors_list = [a.strip() for a in authors_str.split(',')] if authors_str else []
            
            publication_name = extracted_data.get('sitename')
            publication_date_str = extracted_data.get('date') # Expected YYYY-MM-DD
            
            language = extracted_data.get('language')
            # Fallback language detection if needed and langdetect is available
            # if not language and markdown_content and detect_language and LangDetectException:
            #     try:
            #         language = detect_language(markdown_content[:500])
            #     except LangDetectException: # langdetect can fail on short/ambiguous text
            #         logger.warning(f"Langdetect failed for content from {url}. Language not set.")
            #         language = None

            word_count = len(markdown_content.split()) # Simple word count
            estimated_read_time = common.calculate_estimated_read_time(word_count)

            article = Article(
                original_url=url, # Always store the original URL
                title=article_title,
                author=authors_list,
                publication_name=publication_name,
                publication_date=publication_date_str,
                markdown_content=markdown_content,
                word_count=word_count,
                estimated_read_time_minutes=estimated_read_time,
                language=language,
                excerpt=extracted_data.get('excerpt'),
                source_application=constants.SOURCE_WEB_PARSER,
                archived_from_fallback=is_archived
            )
            
            # Store potential thumbnail URL - this assumes Article class can handle this attribute
            # If Article uses slots and this isn't defined, this line will error.
            # As per previous reasoning, I'll attempt to set it.
            # This is a temporary attribute not saved to YAML.
            potential_thumb_url = extracted_data.get('image')
            if potential_thumb_url:
                article.potential_thumbnail_source_url = potential_thumb_url


            logger.info(f"🟢 Successfully parsed article: '{article.title}' from {fetched_from_url} (source: {url})")
            return article

        except Exception as e:
            logger.error(f"🛑 Trafilatura parsing failed for content from {fetched_from_url} (source: {url}): {e}", exc_info=True)
            # Fallback to creating a bookmark if parsing fails catastrophically after fetch
            page_title_fallback = "Bookmark (Parsing Failed)"
            try:
                metadata = trafilatura.extract_metadata(content_html)
                if metadata and metadata.title:
                    page_title_fallback = f"Bookmark (Parsing Failed): {metadata.title}"
                else:
                    page_title_fallback = f"Bookmark (Parsing Failed): {url}"
            except: # Ensure this doesn't cause another error
                page_title_fallback = f"Bookmark (Parsing Failed): {url}"
            
            return self.create_bookmark_article(
                url=url,
                title=page_title_fallback,
                notes=f"Content from {fetched_from_url} could not be parsed: {e}"
            )


    def parse_pdf_from_bytes(self, pdf_bytes: bytes, original_url: str = "local.pdf") -> Optional[Article]:
        logger.info(f"🟢 Attempting to parse PDF: {original_url}")
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_content = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text_content += page.get_text("text") + "\n\n" # Add space between pages
            doc.close()

            # Use filename (stem) as title if no other title is available
            # Replace underscores/hyphens with spaces for better readability
            title_from_url = Path(original_url).stem.replace('_', ' ').replace('-', ' ').strip()
            if not title_from_url and original_url != "local.pdf": # If stem is empty but original_url is not default
                title_from_url = original_url # Use full original_url if stem is empty
            elif not title_from_url:
                title_from_url = "Untitled PDF Document"


            if not text_content.strip():
                logger.warning(f"🟡 No text extracted from PDF: {original_url}")
                return self.create_bookmark_article(
                    url=original_url,
                    title=f"PDF (No Text Content): {title_from_url}",
                    notes=f"Original source: {original_url}\nNo text content could be extracted from this PDF."
                )


            word_count = len(text_content.split())
            estimated_read_time = common.calculate_estimated_read_time(word_count)

            article = Article(
                original_url=original_url,
                title=title_from_url,
                markdown_content=text_content.strip(),
                word_count=word_count,
                estimated_read_time_minutes=estimated_read_time,
                source_application=constants.SOURCE_PDF_IMPORT
            )
            logger.info(f"🟢 Successfully parsed PDF: {original_url} -> '{article.title}'")
            return article
        except Exception as e:
            logger.error(f"🛑 PDF parsing failed for {original_url}: {e}", exc_info=True)
            return self.create_bookmark_article(
                url=original_url,
                title=f"PDF (Parsing Failed): {Path(original_url).name}",
                notes=f"Failed to parse PDF content from {original_url}: {e}"
            )


    def parse_docx_from_bytes(self, docx_bytes: bytes, original_url: str = "local.docx") -> Optional[Article]:
        logger.info(f"🟢 Attempting to parse DOCX: {original_url}")
        try:
            document = docx.Document(io.BytesIO(docx_bytes))
            text_content_parts = [para.text for para in document.paragraphs if para.text]
            text_content = "\n\n".join(text_content_parts)

            title_from_url = Path(original_url).stem.replace('_', ' ').replace('-', ' ').strip()
            if not title_from_url and original_url != "local.docx":
                 title_from_url = original_url
            elif not title_from_url:
                title_from_url = "Untitled DOCX Document"


            if not text_content.strip():
                logger.warning(f"🟡 No text extracted from DOCX: {original_url}")
                return self.create_bookmark_article(
                    url=original_url,
                    title=f"DOCX (No Text Content): {title_from_url}",
                    notes=f"Original source: {original_url}\nNo text content could be extracted from this DOCX file."
                )

            word_count = len(text_content.split())
            estimated_read_time = common.calculate_estimated_read_time(word_count)

            article = Article(
                original_url=original_url,
                title=title_from_url,
                markdown_content=text_content.strip(),
                word_count=word_count,
                estimated_read_time_minutes=estimated_read_time,
                source_application=constants.SOURCE_DOCX_IMPORT
            )
            logger.info(f"🟢 Successfully parsed DOCX: {original_url} -> '{article.title}'")
            return article
        except Exception as e:
            logger.error(f"🛑 DOCX parsing failed for {original_url}: {e}", exc_info=True)
            return self.create_bookmark_article(
                url=original_url,
                title=f"DOCX (Parsing Failed): {Path(original_url).name}",
                notes=f"Failed to parse DOCX content from {original_url}: {e}"
            )

    def create_bookmark_article(self, url: str, title: Optional[str] = None, tags: Optional[List[str]] = None, notes: Optional[str] = None) -> Article:
        logger.info(f"Creating bookmark for URL: {url}")
        article_title = title if title else "Bookmark: " + url
        
        markdown_body_parts = [f"# Bookmark: {article_title}", f"Original URL: [{url}]({url})"]
        if notes:
            markdown_body_parts.append(f"\nNotes:\n{notes}")
        
        markdown_body = "\n\n".join(markdown_body_parts)

        # Note: word_count and estimated_read_time_minutes will be 0 or None by Article default
        # for bookmark articles as there's no main content to parse.
        return Article(
            original_url=url,
            title=article_title,
            tags=tags if tags else [],
            markdown_content=markdown_body,
            source_application=constants.SOURCE_BOOKMARK
        )

```
