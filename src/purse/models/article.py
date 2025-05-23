from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime # Not directly used here, but common.py functions return datetime

# Assuming constants.py and common.py are in purse.utils
from purse.utils import constants
from purse.utils.common import generate_uuid, get_current_timestamp_iso, parse_iso_timestamp

@dataclass(slots=True)
class Article:
    # Core metadata from PRD 5.2, as specified in workplan section 10
    id: str = field(default_factory=generate_uuid)
    original_url: str # Mandatory, no default factory
    title: str        # Mandatory, no default factory

    pocket_id: Optional[str] = None
    author: Optional[List[str]] = field(default_factory=list) # Allow multiple authors
    publication_name: Optional[str] = None
    publication_date: Optional[str] = None # ISO 8601 string
    
    saved_date: str = field(default_factory=get_current_timestamp_iso) # ISO 8601 string
    last_modified_date: str = field(default_factory=get_current_timestamp_iso) # ISO 8601 string
    
    status: str = constants.STATUS_UNREAD
    favorite: bool = False
    tags: List[str] = field(default_factory=list) # Ensure it's a list
    
    estimated_read_time_minutes: Optional[int] = None
    word_count: Optional[int] = None
    language: Optional[str] = None
    excerpt: Optional[str] = None
    
    source_application: str = constants.SOURCE_WEB_PARSER # Default source
    archived_from_fallback: bool = False
    thumbnail_url_local: Optional[str] = None # Relative path to local thumbnail (within sync dir)

    # Content
    markdown_content: str = "" # Main article body in Markdown
    # Highlights are embedded in markdown_content as ==highlighted text== (constants.MARKDOWN_HIGHLIGHT_START_TAG etc.)
    # Notes are appended to markdown_content under "## My Notes" (constants.MARKDOWN_NOTES_HEADING)

    # Local state, not necessarily in YAML frontmatter, but useful for app logic
    local_path: Optional[str] = None # Absolute path to the .md file on local disk if saved/loaded

    # Optional field from workplan section 6 (constants.py) but not explicitly in Article spec (section 10)
    # This is more of a transient state when parsing, rather than persisted Article field.
    # It can be added if there's a clear use case for it to be part of the Article object itself.
    # For now, omitting potential_thumbnail_source_url from the dataclass itself.
    # potential_thumbnail_source_url: Optional[str] = None 
    potential_thumbnail_source_url: Optional[str] = None # Transient URL for a potential thumbnail source

    def __post_init__(self):
        # Ensure list types are actually lists if loaded from somewhere else (e.g. bad data in YAML)
        # default_factory handles initialization, this is more for robustness if fields are set manually post-init
        # or if data comes from a source that might provide None for lists.
        if self.author is None:
            self.author = []
        if self.tags is None:
            self.tags = []
        
        # Ensure mandatory fields are not empty strings if that's a policy
        # The spec implies original_url and title are mandatory.
        # This can be enforced here or by the creating service.
        if not self.original_url:
            # Consider raising ValueError or logging a warning. For now, allow.
            # raise ValueError("original_url cannot be empty")
            pass
        if not self.title:
            # self.title = "Untitled" # Or raise error
            pass


    def to_dict(self) -> Dict[str, Any]:
        """Converts Article to a dictionary suitable for YAML frontmatter."""
        data = {
            constants.KEY_ID: self.id,
            constants.KEY_ORIGINAL_URL: self.original_url,
            constants.KEY_TITLE: self.title,
            constants.KEY_POCKET_ID: self.pocket_id,
            constants.KEY_AUTHOR: self.author if self.author else [], # Ensure empty list not None for YAML
            constants.KEY_PUBLICATION_NAME: self.publication_name,
            constants.KEY_PUBLICATION_DATE: self.publication_date,
            constants.KEY_SAVED_DATE: self.saved_date,
            constants.KEY_LAST_MODIFIED_DATE: self.last_modified_date,
            constants.KEY_STATUS: self.status,
            constants.KEY_FAVORITE: self.favorite,
            constants.KEY_TAGS: self.tags if self.tags else [], # Ensure empty list not None for YAML
            constants.KEY_ESTIMATED_READ_TIME: self.estimated_read_time_minutes,
            constants.KEY_WORD_COUNT: self.word_count,
            constants.KEY_LANGUAGE: self.language,
            constants.KEY_EXCERPT: self.excerpt,
            constants.KEY_SOURCE_APPLICATION: self.source_application,
            constants.KEY_ARCHIVED_FROM_FALLBACK: self.archived_from_fallback,
            constants.KEY_THUMBNAIL_URL_LOCAL: self.thumbnail_url_local,
            # potential_thumbnail_source_url is deliberately NOT included here as it's transient
        }
        # Remove None values for cleaner YAML, except for those explicitly allowed to be null
        # as per workplan's example in Article.to_dict()
        # The workplan states: "Remove None values ... except for ... [list of keys]"
        # This means if a key is in that list, it should be included even if None.
        # If a key is NOT in that list, it should be included ONLY IF NOT None.
        
        allowed_null_keys = {
            constants.KEY_POCKET_ID, constants.KEY_AUTHOR, constants.KEY_PUBLICATION_NAME,
            constants.KEY_PUBLICATION_DATE, constants.KEY_ESTIMATED_READ_TIME,
            constants.KEY_WORD_COUNT, constants.KEY_LANGUAGE, constants.KEY_EXCERPT,
            constants.KEY_THUMBNAIL_URL_LOCAL
        }
        # Authors and tags are special: if they are empty lists, they might become `null` in YAML
        # or an empty list `[]` depending on YAML dumper settings.
        # The current code `self.author if self.author else []` ensures they are always lists.
        # So, they won't be None unless the list itself is considered "null-ish" by the dumper.
        # Let's ensure that `allowed_null_keys` correctly reflects fields that can truly be `null` vs empty.
        # Given `author` and `tags` are `default_factory=list`, they will be `[]` not `None`.
        # So, they don't need to be in `allowed_null_keys` for the purpose of being `None`.
        # The check `if v is not None or k in allowed_null_keys` means:
        # - if `v` is not `None`, include it.
        # - if `v` is `None` BUT `k` is in `allowed_null_keys`, include it (as `null`).

        return {k: v for k, v in data.items() if v is not None or k in allowed_null_keys}


    @classmethod
    def from_dict(cls, data: Dict[str, Any], markdown_content: str = "", local_path: Optional[str] = None) -> 'Article':
        """Creates an Article instance from a dictionary (YAML frontmatter) and content."""
        
        # Handle mandatory fields first, potentially raising error or using defaults if appropriate
        original_url = data.get(constants.KEY_ORIGINAL_URL)
        if not original_url:
            # Decide policy: raise error, or default to a placeholder if that makes sense.
            # Workplan: original_url="", title="Untitled"
            # This implies they are mandatory in data but from_dict can provide a default if missing.
            # For now, let's trust the input or allow empty, __post_init__ might validate.
            original_url = "" 
            
        title = data.get(constants.KEY_TITLE)
        if not title:
            title = "Untitled"

        # Ensure authors and tags are lists, even if missing or null in data
        authors = data.get(constants.KEY_AUTHOR, [])
        if authors is None:  # Handles explicit null in YAML
            authors = []
            
        tags = data.get(constants.KEY_TAGS, [])
        if tags is None: # Handles explicit null in YAML
            tags = []

        return cls(
            id=data.get(constants.KEY_ID, generate_uuid()), # Generate new ID if missing
            original_url=original_url,
            title=title,
            pocket_id=data.get(constants.KEY_POCKET_ID),
            author=authors,
            publication_name=data.get(constants.KEY_PUBLICATION_NAME),
            publication_date=data.get(constants.KEY_PUBLICATION_DATE),
            saved_date=data.get(constants.KEY_SAVED_DATE, get_current_timestamp_iso()),
            last_modified_date=data.get(constants.KEY_LAST_MODIFIED_DATE, get_current_timestamp_iso()),
            status=data.get(constants.KEY_STATUS, constants.STATUS_UNREAD),
            favorite=data.get(constants.KEY_FAVORITE, False),
            tags=tags,
            estimated_read_time_minutes=data.get(constants.KEY_ESTIMATED_READ_TIME),
            word_count=data.get(constants.KEY_WORD_COUNT),
            language=data.get(constants.KEY_LANGUAGE),
            excerpt=data.get(constants.KEY_EXCERPT),
            source_application=data.get(constants.KEY_SOURCE_APPLICATION, constants.SOURCE_WEB_PARSER),
            archived_from_fallback=data.get(constants.KEY_ARCHIVED_FROM_FALLBACK, False),
            thumbnail_url_local=data.get(constants.KEY_THUMBNAIL_URL_LOCAL),
            markdown_content=markdown_content.strip(), # Ensure content is stripped
            local_path=local_path,
            potential_thumbnail_source_url=data.get('potential_thumbnail_source_url') # Initialize, though not expected in YAML data
        )

    def get_notes(self) -> str:
        """Extracts notes from the markdown_content."""
        # Notes section starts with MARKDOWN_NOTES_HEADING on its own line,
        # followed by a newline, then the notes.
        notes_marker = f"\n{constants.MARKDOWN_NOTES_HEADING}\n"
        parts = self.markdown_content.split(notes_marker, 1)
        return parts[1].strip() if len(parts) > 1 else ""

    def set_notes(self, notes_content: str) -> None:
        """Sets or updates notes in the markdown_content. Updates last_modified_date."""
        notes_marker = f"\n{constants.MARKDOWN_NOTES_HEADING}\n"
        # Find existing notes section or content before it
        base_content = self.markdown_content.split(notes_marker, 1)[0].strip()
        
        notes_content_stripped = notes_content.strip()

        if notes_content_stripped: # If there's new note content
            self.markdown_content = f"{base_content}\n\n{constants.MARKDOWN_NOTES_HEADING}\n{notes_content_stripped}"
        else: # If new note content is empty, remove the notes section
            self.markdown_content = base_content 
            # This also removes the heading. If heading should persist with empty notes:
            # self.markdown_content = f"{base_content}\n\n{constants.MARKDOWN_NOTES_HEADING}\n"

        self.last_modified_date = get_current_timestamp_iso()

    def get_content_without_notes(self) -> str:
        """Returns markdown content excluding the notes section and its heading."""
        notes_marker = f"\n{constants.MARKDOWN_NOTES_HEADING}\n"
        return self.markdown_content.split(notes_marker, 1)[0].strip()

    # Methods for highlights (e.g., add_highlight, remove_highlight) could be added if direct manipulation
    # beyond simple text embedding (==text==) is needed.
    # The workplan implies highlights are just embedded markup, so specific methods might not be required yet.
    # Example:
    # def add_highlight(self, highlighted_text: str, surrounding_text_context: Optional[str] = None):
    #     """ This would be more complex, needing to find where to insert ==highlighted_text== """
    #     pass
```
