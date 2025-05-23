import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Dict, TYPE_CHECKING, Any, Callable, Set
import html # For HTML unescaping of titles etc.
from bs4 import BeautifulSoup # For parsing Pocket's HTML export

from purse.models.article import Article
from purse.services.content_parser import ContentParserService
from purse.services.file_system_manager import FileSystemManager
from purse.services.search_manager import SearchManager
from purse.utils import constants, common

if TYPE_CHECKING:
    from purse.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class PocketImporterService:
    def __init__(self,
                 config_manager: 'ConfigManager',
                 content_parser: ContentParserService,
                 fs_manager: FileSystemManager,
                 search_manager: SearchManager):
        self.config_manager = config_manager
        self.content_parser = content_parser
        self.fs_manager = fs_manager
        self.search_manager = search_manager
        
        # Get 'reparse_pocket_html' setting. The workplan notes content isn't in the export,
        # so this setting is more for future-proofing or alternative formats.
        # Trafilatura (via ContentParserService) will always be used for fetching content from URL.
        self.reparse_pocket_html_setting: bool = self.config_manager.get(
            'pocket_importer.reparse_pocket_html', True
        )
        if not self.reparse_pocket_html_setting:
            logger.info("Pocket importer configured to NOT re-parse HTML (setting has limited effect as content is fetched from URL).")


    def _parse_pocket_export_html(self, html_content: str) -> List[Dict[str, Any]]:
        """Parses Pocket's ril_export.html file to extract article metadata."""
        logger.info("Parsing Pocket HTML export file...")
        soup = BeautifulSoup(html_content, 'html.parser')
        imported_items: List[Dict[str, Any]] = []
        
        # Pocket export format: <ul> lists under <h1> headings like "Unread" and "Read Archive".
        # Each <li> contains an <a> tag with href, time_added, tags. Link text is the title.
        
        # Find all lists (ul tags) which should contain the articles
        # This approach is more robust than assuming specific h1 text.
        article_lists = soup.find_all('ul')
        parsed_urls: Set[str] = set() # To avoid duplicate parsing if same URL appears in multiple lists

        for ul_element in article_lists:
            # Determine if this list is under a "Read Archive" heading
            # Traverse previous siblings to find the nearest <h1>
            is_archived_section = False
            heading_tag = ul_element.find_previous_sibling('h1')
            if heading_tag and heading_tag.string and "read archive" in heading_tag.string.strip().lower():
                is_archived_section = True
            
            for li_element in ul_element.find_all('li', recursive=False): # Direct children <li>
                link_tag = li_element.find('a', href=True)
                if link_tag and link_tag.has_attr('time_added'):
                    url = link_tag['href']
                    if url in parsed_urls: # Skip if already processed from another list (e.g. if structure is odd)
                        continue
                    parsed_urls.add(url)

                    title = html.unescape(link_tag.string.strip() if link_tag.string else url)
                    time_added_str = link_tag['time_added'] # Unix timestamp string
                    tags_str = link_tag.get('tags', '') # Comma-separated string

                    try:
                        saved_date_unix = int(time_added_str)
                        saved_date_iso = datetime.fromtimestamp(saved_date_unix, tz=timezone.utc).isoformat()
                    except ValueError:
                        logger.warning(f"🟡 Could not parse time_added '{time_added_str}' for URL '{url}'. Using current time.")
                        saved_date_iso = common.get_current_timestamp_iso()

                    tags_list = [tag.strip() for tag in tags_str.split(',') if tag.strip()]

                    imported_items.append({
                        'original_url': url,
                        'title': title,
                        'saved_date_iso': saved_date_iso,
                        'tags': tags_list,
                        'is_archived': is_archived_section,
                        # Pocket ID is not in the HTML export.
                    })
        
        logger.info(f"Parsed {len(imported_items)} unique article metadata entries from Pocket export.")
        return imported_items


    async def import_from_pocket_file(self, 
                                      export_file_path: Path, 
                                      progress_callback: Optional[Callable[[int, int], None]] = None
                                     ) -> Tuple[int, int]:
        """
        Imports articles from a Pocket export HTML file (ril_export.html).
        Returns a tuple: (number_of_successful_imports, number_of_failed_or_skipped_imports).
        """
        if not self.fs_manager.get_local_sync_root():
            logger.error("🛑 Pocket Import failed: Local sync root not configured.")
            return 0, 0

        try:
            with open(export_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            logger.error(f"🛑 Could not read Pocket export file '{export_file_path}': {e}")
            return 0, 0

        pocket_items_metadata = self._parse_pocket_export_html(html_content)
        total_items = len(pocket_items_metadata)
        successful_imports = 0
        failed_or_skipped = 0

        logger.info(f"Starting import of {total_items} items from Pocket export...")

        for i, item_meta in enumerate(pocket_items_metadata):
            url = item_meta['original_url']
            
            if progress_callback: # Call progress callback at the start of processing each item
                progress_callback(i, total_items) # Current index, total

            logger.info(f"Processing Pocket import ({i+1}/{total_items}): {url}")

            # Deduplication (PRD 5.8)
            # Whoosh ID field type requires exact match. Query needs to be exact.
            # Example: original_url:"http://example.com"
            # Ensure URL is suitable for direct query. Quotes handle most things.
            # Whoosh query parser might need escaping for internal special chars if not using exact ID field term query.
            # For an ID field, `fieldname:value` is a term query.
            escaped_url_for_query = url.replace('"', '\\"') # Basic escape for quotes if any in URL itself
            existing_article_hits = self.search_manager.search(
                f'original_url:"{escaped_url_for_query}"', limit=1
            )
            if existing_article_hits:
                logger.info(f"Skipping duplicate (URL exists in search index): {url}")
                failed_or_skipped += 1
                if progress_callback: progress_callback(i + 1, total_items) # Update after processing
                continue

            # Fetch and parse content using ContentParserService
            # ContentParserService.parse_url will use Trafilatura as per PRD.
            article: Optional[Article] = await self.content_parser.parse_url(url)

            if article:
                # Apply metadata from Pocket export, overriding some fields if necessary
                article.title = item_meta['title'] # Pocket title is usually user-edited or preferred
                article.saved_date = item_meta['saved_date_iso']
                # Merge tags: ensure tags from Pocket are added to any tags Trafilatura might have found (unlikely)
                article.tags = list(set(article.tags + item_meta['tags']))
                article.source_application = constants.SOURCE_POCKET_MIGRATION
                
                if item_meta.get('is_archived', False):
                    article.status = constants.STATUS_ARCHIVED
                
                # Pocket ID is not available from HTML export, so article.pocket_id remains None.

                saved_path = self.fs_manager.save_article(article)
                if saved_path:
                    self.search_manager.add_or_update_article(article)
                    successful_imports += 1
                    logger.info(f"Successfully imported and saved: '{article.title}' from {url}")
                    # Thumbnail fetching could be triggered here if desired:
                    # if article.potential_thumbnail_source_url:
                    #    await self.fs_manager.fetch_and_save_thumbnail_for_article(article, self.http_client) 
                    # (fetch_and_save_thumbnail_for_article would need to be a method, e.g. on FileSystemManager or coordinated by main app)
                else:
                    logger.error(f"Failed to save imported article: {article.title} from {url}")
                    failed_or_skipped += 1
            else:
                logger.error(f"Failed to parse content for imported article: {url} (ContentParserService returned None)")
                failed_or_skipped += 1
            
            if progress_callback: # Update progress after processing each item
                progress_callback(i + 1, total_items)
        
        logger.info(f"Pocket import process complete. Successfully imported: {successful_imports}, Failed/Skipped: {failed_or_skipped} out of {total_items} items.")
        return successful_imports, failed_or_skipped

```
