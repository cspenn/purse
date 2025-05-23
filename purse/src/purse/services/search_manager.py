import whoosh.index as index
from whoosh.fields import Schema, TEXT, ID, KEYWORD, DATETIME, BOOLEAN, NUMERIC
from whoosh.qparser import MultifieldParser, QueryParser, GtLtParser, FuzzyTermPlugin, WildcardPlugin
from whoosh.analysis import StemmingAnalyzer
from whoosh.writing import AsyncWriter, WhooshError # For concurrent writes
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime # For type hinting, not direct use in this file beyond what Whoosh needs

# Assuming common.py is in purse.utils for parse_iso_timestamp
from purse.utils import common, constants
from purse.models.article import Article
from purse.services.markdown_handler import MarkdownHandler # For highlight extraction

if TYPE_CHECKING:
    from purse.services.file_system_manager import FileSystemManager

logger = logging.getLogger(__name__)

class SearchManager:
    SCHEMA = Schema(
        id=ID(stored=True, unique=True),
        original_url=ID(stored=True),
        title=TEXT(stored=True, field_boost=2.0, analyzer=StemmingAnalyzer()),
        content=TEXT(stored=True, analyzer=StemmingAnalyzer()), # Combined: main_body + notes + highlights_text
        tags=KEYWORD(stored=True, commas=True, scorable=True, lowercase=True),
        author=KEYWORD(stored=True, commas=True, lowercase=True), # Storing as comma-separated string
        publication_name=TEXT(stored=True, analyzer=StemmingAnalyzer()),
        publication_date=DATETIME(stored=True, sortable=True),
        saved_date=DATETIME(stored=True, sortable=True),
        status=ID(stored=True),
        favorite=BOOLEAN(stored=True),
        notes=TEXT(stored=True, analyzer=StemmingAnalyzer()), # Separate field for notes text
        highlights=TEXT(stored=True, analyzer=StemmingAnalyzer()) # Separate field for cleaned highlights text
        # word_count=NUMERIC(stored=True, sortable=True), # Example if added later
        # language=ID(stored=True), # Example if added later
    )

    def __init__(self, fs_manager: 'FileSystemManager'):
        self.fs_manager = fs_manager
        self.index_dir: Path = self.fs_manager.search_index_dir # Provided by FileSystemManager
        self.ix: Optional[index.Index] = self._open_or_create_index()
        if self.ix is None:
            logger.error("🛑 Whoosh index could not be opened or created. Search functionality will be disabled.")
            # Application might need to handle this more gracefully, e.g. by disabling search UI elements.

    def _open_or_create_index(self) -> Optional[index.Index]:
        try:
            if not self.index_dir.exists():
                self.index_dir.mkdir(parents=True, exist_ok=True)
            
            if index.exists_in(self.index_dir):
                logger.info(f"🟢 Opening existing Whoosh index at {self.index_dir}")
                # Pass schema to handle potential evolution, though Whoosh typically loads existing schema.
                # Using a timeout for opening the index to prevent indefinite blocking if index is locked/corrupted.
                return index.open_dir(self.index_dir, schema=self.SCHEMA, timeout=5.0)
            else:
                logger.info(f"🟢 Creating new Whoosh index at {self.index_dir}")
                return index.create_in(self.index_dir, self.SCHEMA)
        except WhooshError as e: # Catch Whoosh-specific errors like LockError
            logger.error(f"🛑 Whoosh specific error opening/creating index at {self.index_dir}: {e}")
            return None
        except Exception as e: # Catch other unexpected errors
            logger.error(f"🛑 Unexpected error opening/creating Whoosh index at {self.index_dir}: {e}")
            return None


    def _get_datetime_obj_from_iso(self, iso_timestamp_str: Optional[str]) -> Optional[datetime]:
        """Safely converts an ISO timestamp string to a datetime object."""
        if not iso_timestamp_str:
            return None
        try:
            return common.parse_iso_timestamp(iso_timestamp_str)
        except ValueError:
            logger.warning(f"🟡 Could not parse ISO timestamp string: '{iso_timestamp_str}' for Whoosh indexing.")
            return None

    def _prepare_article_doc(self, article: Article) -> Dict[str, Any]:
        """Helper function to prepare a dictionary of fields for Whoosh from an Article object."""
        notes_text = article.get_notes()
        
        # Extract highlights and clean them (remove markup)
        raw_highlights_list = MarkdownHandler.extract_highlights(article.markdown_content)
        cleaned_highlights_text_parts = []
        for hl_text in raw_highlights_list:
            # Basic cleaning: remove start/end tags if they are part of the extracted string.
            # MarkdownHandler.extract_highlights should return the text *between* the tags.
            # So, no further cleaning of tags themselves should be needed here for `cleaned_highlights_text_parts`.
            cleaned_highlights_text_parts.append(hl_text) 
        cleaned_highlights_text_for_field = " ".join(cleaned_highlights_text_parts)

        main_content_text = article.get_content_without_notes()
        
        # Full searchable content for the 'content' field
        # Combines main body, notes, and the (already cleaned) text of highlights.
        full_searchable_content = f"{main_content_text}\n\n{notes_text}\n\n{cleaned_highlights_text_for_field}"

        doc = {
            "id": article.id,
            "original_url": article.original_url,
            "title": article.title,
            "content": full_searchable_content.strip(),
            "tags": ",".join(article.tags).lower() if article.tags else "",
            "author": ",".join(article.author).lower() if article.author else "", # Assuming author list is stored as strings
            "publication_name": article.publication_name,
            "publication_date": self._get_datetime_obj_from_iso(article.publication_date),
            "saved_date": self._get_datetime_obj_from_iso(article.saved_date), # Should always exist
            "status": article.status,
            "favorite": article.favorite,
            "notes": notes_text.strip(),
            "highlights": cleaned_highlights_text_for_field.strip()
        }
        # Remove keys where value is None, as Whoosh might not handle them well for all field types
        # (especially DATETIME if None is passed).
        return {k: v for k, v in doc.items() if v is not None}


    def add_or_update_article(self, article: Article) -> None:
        if not self.ix:
            logger.warning("🟡 Search index not available. Cannot add/update article.")
            return
        
        logger.debug(f"Indexing article: {article.id} - {article.title}")
        try:
            writer = AsyncWriter(self.ix) # Using AsyncWriter as per workplan
            doc_data = self._prepare_article_doc(article)
            writer.update_document(**doc_data) # update_document needs kwargs
            writer.commit() # Consider committing in batches if many updates happen rapidly.
            logger.info(f"🟢 Article '{article.title}' (ID: {article.id}) indexed/updated.")
        except Exception as e:
            logger.error(f"🛑 Error indexing article {article.id} ('{article.title}'): {e}")

    def delete_article(self, article_id: str) -> None:
        if not self.ix:
            logger.warning("🟡 Search index not available. Cannot delete article.")
            return
        try:
            writer = AsyncWriter(self.ix)
            writer.delete_by_term('id', article_id)
            writer.commit()
            logger.info(f"🟢 Article ID '{article_id}' deleted from index.")
        except Exception as e:
            logger.error(f"🛑 Error deleting article ID {article_id} from index: {e}")
            
    def rebuild_index(self, articles: List[Article]) -> None:
        """Clears and rebuilds the entire index from a list of articles."""
        if not self.index_dir.exists(): # Should have been created by __init__
             self.index_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Rebuilding search index at {self.index_dir}...")
        try:
            # Re-create index to ensure clean state and apply current schema
            self.ix = index.create_in(self.index_dir, self.SCHEMA)
            
            writer = AsyncWriter(self.ix)
            count = 0
            for article in articles:
                doc_data = self._prepare_article_doc(article)
                writer.add_document(**doc_data) # Use add_document for fresh build
                count += 1
                if count % 100 == 0: # Log progress every 100 articles
                    logger.info(f"Rebuild progress: {count} articles indexed...")
            
            writer.commit() # Final commit
            logger.info(f"🟢 Search index rebuilt. {count} articles indexed.")
        except Exception as e:
            logger.error(f"🛑 CRITICAL: Failed to rebuild search index: {e}")
            # The index might be in an inconsistent state here.
            # Consider trying to re-open or fallback. For now, self.ix might be invalid.
            self.ix = None # Mark index as potentially unusable


    def search(self, query_string: str, fields_to_search: Optional[List[str]] = None, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.ix:
            logger.warning("🟡 Search index not available. Cannot perform search.")
            return []

        # Default fields to search if not specified in query or as argument
        if fields_to_search is None:
            # These are the text-based fields suitable for general keyword search
            fields_to_search = ["title", "content", "tags", "author", "publication_name", "notes", "highlights"]
        
        try:
            with self.ix.searcher() as searcher:
                # PRD 5.4: "Boolean operators (AND, OR, NOT), phrase searching."
                # QueryParser by default supports AND, OR, NOT, phrases.
                parser = MultifieldParser(fields_to_search, schema=self.SCHEMA)
                parser.add_plugin(GtLtParser())         # For date/numeric range searches (e.g. saved_date:>YYYY-MM-DD)
                parser.add_plugin(FuzzyTermPlugin())    # For fuzzy searches (e.g. term~)
                parser.add_plugin(WildcardPlugin())     # For wildcard searches (e.g. wild*card)
                # Consider adding NgramWordAnalyzer or similar for partial word matches if needed later.

                query = parser.parse(query_string)
                results = searcher.search(query, limit=limit) # Add sort order options later if needed
                
                # PRD 5.4: Results Presentation: Sortable by relevance, date saved, publication date, title.
                # Example: results = searcher.search(query, limit=limit, sortedby="saved_date", reverse=True)

                found_articles_data: List[Dict[str, Any]] = []
                for hit in results:
                    # Store all stored fields from the hit
                    article_data = {k: v for k, v in hit.items()} # hit.fields() also works
                    article_data['score'] = hit.score # Add relevance score
                    found_articles_data.append(article_data)
                
                logger.info(f"🟢 Search for '{query_string}' found {len(found_articles_data)} results.")
                return found_articles_data
        except Exception as e: # Catch Whoosh query parsing errors, etc.
            logger.error(f"🛑 Error during search for '{query_string}': {e}")
            return []

    def get_all_indexed_article_ids(self) -> List[str]:
        """Retrieves all article IDs currently in the index."""
        ids: List[str] = []
        if not self.ix:
            logger.warning("🟡 Search index not available. Cannot get all indexed IDs.")
            return ids
            
        try:
            with self.ix.reader() as reader:
                # Iterate over all documents in the index
                for docnum in reader.all_doc_ids(): # This gives internal doc numbers
                    stored_fields = reader.stored_fields(docnum) # Fetch stored fields for that doc
                    if stored_fields and 'id' in stored_fields:
                        ids.append(stored_fields['id'])
            return ids
        except Exception as e:
            logger.error(f"🛑 Error retrieving all indexed article IDs: {e}")
            return []


    def find_similar_articles(self, article_id: str, num_recommendations: int = 5) -> List[Dict[str, Any]]:
        """Finds similar articles based on shared keywords in content/tags."""
        if not self.ix:
            logger.warning("🟡 Search index not available. Cannot find similar articles.")
            return []

        try:
            with self.ix.searcher() as searcher:
                docnum = None
                # Find the internal document number for the given article_id
                for dn in searcher.document_numbers(id=article_id): # Iterate as id is unique
                    docnum = dn
                    break 
                
                if docnum is None:
                    logger.warning(f"🟡 Article ID {article_id} not found in index for similarity search.")
                    return []

                # Whoosh's more_like() method on a Hit object is one way, or directly on searcher.
                # Using searcher.more_like(docnum, fieldname, topN)
                # PRD: "TF-IDF on article text/tags + cosine similarity". Whoosh MLT is based on this.
                # Using 'content' field for similarity, as it's comprehensive.
                # `top` for more_like should be num_recommendations + 1 if the source doc itself is included.
                # Let's fetch a bit more to be safe and filter.
                results = searcher.more_like(docnum, fieldname="content", top=num_recommendations + 5)
                
                similar_articles_data: List[Dict[str, Any]] = []
                for hit in results:
                    if hit['id'] == article_id: # Don't recommend the article itself
                        continue
                    if len(similar_articles_data) < num_recommendations:
                        article_data = {k: v for k, v in hit.items()}
                        article_data['score'] = hit.score # Similarity score
                        similar_articles_data.append(article_data)
                    else:
                        break # Reached desired number of recommendations
                
                logger.info(f"🟢 Found {len(similar_articles_data)} similar articles for ID {article_id}")
                return similar_articles_data
        except Exception as e:
            logger.error(f"🛑 Error finding similar articles for {article_id}: {e}")
            return []

    def close_index(self) -> None:
        """Closes the Whoosh index, if open."""
        if self.ix:
            logger.info(f"Closing Whoosh index at {self.index_dir}")
            self.ix.close()
            self.ix = None

# Example usage (for testing or illustration)
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    # Mock FileSystemManager for testing
    class MockFileSystemManager:
        def __init__(self, temp_index_path: Path):
            self.search_index_dir = temp_index_path
            self.search_index_dir.mkdir(parents=True, exist_ok=True)

    # Create a temporary directory for the index for this test run
    import tempfile
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_index_path = Path(temp_dir_obj.name) / "test_search_index"

    mock_fsm = MockFileSystemManager(temp_index_path)
    search_mgr = SearchManager(mock_fsm)

    if search_mgr.ix is None:
        logger.error("Test failed: SearchManager could not initialize index.")
    else:
        # Create some dummy articles
        article1_data = {
            'id': 'uuid1', 'original_url': 'http://example.com/1', 'title': 'Exploring Python Basics',
            'markdown_content': 'Python is a versatile language. ==Highlights Python features==. ## My Notes \nPython notes here.',
            'tags': ['python', 'programming'], 'author': ['John Doe'], 
            'publication_date': '2023-01-15T10:00:00Z', 'saved_date': common.get_current_timestamp_iso(),
            'status': constants.STATUS_UNREAD, 'favorite': False
        }
        article2_data = {
            'id': 'uuid2', 'original_url': 'http://example.com/2', 'title': 'Advanced Python Techniques',
            'markdown_content': 'Discover advanced Python topics. ==Decorators and generators==. ## My Notes \nAdvanced notes.',
            'tags': ['python', 'advanced', 'programming'], 'author': ['Jane Smith'],
            'publication_date': '2023-03-20T14:30:00Z', 'saved_date': common.get_current_timestamp_iso(),
            'status': constants.STATUS_READ, 'favorite': True
        }
        article1 = Article(**article1_data) # type: ignore
        article2 = Article(**article2_data) # type: ignore

        # Test add_or_update_article
        search_mgr.add_or_update_article(article1)
        search_mgr.add_or_update_article(article2)

        # Test search
        logger.info("\n--- Searching for 'Python' ---")
        results_python = search_mgr.search("Python")
        for res in results_python: logger.info(f"Found: {res['title']} (Score: {res['score']})")
        
        logger.info("\n--- Searching for 'tags:advanced' ---")
        results_advanced = search_mgr.search("tags:advanced")
        for res in results_advanced: logger.info(f"Found: {res['title']} (Score: {res['score']})")

        logger.info("\n--- Searching for 'highlights:decorators' ---") # Test search in highlights field
        results_highlights = search_mgr.search("highlights:decorators")
        for res in results_highlights: logger.info(f"Found: {res['title']} (Score: {res['score']})")


        # Test get_all_indexed_article_ids
        logger.info("\n--- All Indexed IDs ---")
        all_ids = search_mgr.get_all_indexed_article_ids()
        logger.info(f"All IDs: {all_ids}")
        assert 'uuid1' in all_ids and 'uuid2' in all_ids

        # Test find_similar_articles
        logger.info("\n--- Similar to 'uuid1' (Exploring Python Basics) ---")
        similar_to_1 = search_mgr.find_similar_articles('uuid1')
        for sim_art_data in similar_to_1:
            logger.info(f"Similar: {sim_art_data['title']} (Score: {sim_art_data['score']})")

        # Test delete_article
        logger.info("\n--- Deleting 'uuid1' ---")
        search_mgr.delete_article('uuid1')
        all_ids_after_delete = search_mgr.get_all_indexed_article_ids()
        logger.info(f"All IDs after delete: {all_ids_after_delete}")
        assert 'uuid1' not in all_ids_after_delete

        # Test rebuild_index
        logger.info("\n--- Rebuilding index with only article2 ---")
        search_mgr.rebuild_index([article2])
        all_ids_after_rebuild = search_mgr.get_all_indexed_article_ids()
        logger.info(f"All IDs after rebuild: {all_ids_after_rebuild}")
        assert 'uuid2' in all_ids_after_rebuild and 'uuid1' not in all_ids_after_rebuild
        
        # Search after rebuild
        logger.info("\n--- Searching for 'Python' after rebuild ---")
        results_python_rebuild = search_mgr.search("Python") # Should find article2
        for res in results_python_rebuild: logger.info(f"Found: {res['title']} (Score: {res['score']})")


        search_mgr.close_index()
        logger.info("SearchManager test complete.")

    # Clean up the temporary directory
    try:
        temp_dir_obj.cleanup()
        logger.info(f"Cleaned up temporary index directory: {temp_index_path.parent}")
    except Exception as e:
        logger.error(f"Error cleaning up temp directory: {e}")

```
