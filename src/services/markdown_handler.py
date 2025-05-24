import yaml
from pathlib import Path
import logging
import re # For extract_highlights
from typing import Optional, List, Tuple # Tuple might not be strictly needed based on current methods

from src.models.article import Article
from src.utils import constants
# common.py is not directly used by MarkdownHandler as per workplan spec for this file,
# but Article.from_dict and .to_dict might use functions from common.py internally.

logger = logging.getLogger(__name__)

class MarkdownHandler:
    @staticmethod
    def parse_markdown_file(file_path: Path) -> Optional[Article]:
        """Parses a Markdown file into an Article object."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            logger.error(f"🛑 Markdown file not found: {file_path}")
            return None
        except Exception as e: # Catch other read errors like permission denied
            logger.error(f"🛑 Error reading Markdown file {file_path}: {e}")
            return None

        try:
            frontmatter_str = ""
            body_content = content # Default to full content if no frontmatter
            
            # Split frontmatter and content
            # YAML frontmatter is typically enclosed by '---' lines.
            if content.startswith("---"):
                # Find the end of the frontmatter section (the second '---')
                # Need to be careful with content that might have '---' later in the body.
                parts = content.split("---", 2) # Split into 3 parts: stuff_before_first_triple_dash (empty), frontmatter, rest_of_body
                if len(parts) >= 3: # Found at least two "---"
                    frontmatter_str = parts[1].strip() # The content between the first and second "---"
                    body_content = parts[2].strip()    # The content after the second "---"
                else:
                    # This means there was one "---" at the start but no closing "---".
                    # Treat as no valid frontmatter.
                    logger.warning(f"🟡 Malformed YAML frontmatter (no closing '---') in {file_path}. Treating as no frontmatter.")
                    body_content = content.strip() # Keep original content as body
            
            frontmatter: dict = {}
            if frontmatter_str:
                loaded_yaml = yaml.safe_load(frontmatter_str)
                if isinstance(loaded_yaml, dict):
                    frontmatter = loaded_yaml
                elif loaded_yaml is None: # Empty frontmatter block
                    frontmatter = {}
                else: # Frontmatter was valid YAML but not a dictionary (e.g. a list or a string)
                    logger.warning(f"🟡 YAML frontmatter in {file_path} is not a dictionary. Ignoring frontmatter.")
                    frontmatter = {}
            
            # The workplan mentions: "Ensure essential keys if building from scratch file with no frontmatter"
            # And: "If original_url is missing, it's problematic."
            # Article.from_dict handles defaults for missing keys (e.g. title="Untitled", original_url="").
            # So, no specific checks for essential keys are needed here before calling from_dict.
            
            article = Article.from_dict(frontmatter, body_content, local_path=str(file_path))
            return article

        except yaml.YAMLError as e:
            logger.error(f"🛑 YAML parsing error in frontmatter of {file_path}: {e}")
            return None
        except Exception as e: # Catch-all for other unexpected errors during parsing
            logger.error(f"🛑 Error processing Markdown file {file_path} content: {e}")
            return None

    @staticmethod
    def article_to_markdown_text(article: Article) -> str:
        """Converts an Article object to its Markdown string representation (frontmatter + content)."""
        frontmatter_dict = article.to_dict()
        
        try:
            # Ensure authors and tags are lists for YAML dump (to_dict should handle this)
            # yaml.dump settings as per workplan:
            frontmatter_str = yaml.dump(
                frontmatter_dict,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
                width=80 # Optional: for readability of dumped YAML
            )
        except Exception as e:
            logger.error(f"🛑 Error serializing frontmatter for article {article.id} ('{article.title}'): {e}")
            # Fallback: create a minimal frontmatter or indicate error
            frontmatter_str = f"id: {article.id}\ntitle: {article.title}\nerror_serializing_frontmatter: true\n"

        # Retrieve main content and notes using Article methods
        # article.markdown_content already contains the main content and potentially notes.
        # The methods get_content_without_notes() and get_notes() are for extraction.
        # For serialization, we just need the full markdown_content which Article manages.
        # If Article.set_notes correctly formats markdown_content, then article.markdown_content is sufficient.
        
        # Let's re-verify the structure. article.markdown_content should be the "body"
        # which includes the main text AND the "## My Notes" section if notes exist.
        # So, we don't need to call get_content_without_notes() and get_notes() separately here.
        # The Article object itself is the source of truth for its complete markdown_content.
        
        full_markdown_body = article.markdown_content.strip()

        return f"---\n{frontmatter_str.strip()}\n---\n\n{full_markdown_body}"


    @staticmethod
    def save_article_to_file(article: Article, file_path: Path) -> bool:
        """Saves an Article object to a Markdown file."""
        markdown_text = MarkdownHandler.article_to_markdown_text(article)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_text)
            article.local_path = str(file_path) # Update local_path on successful save
            logger.info(f"🟢 Article '{article.title}' (ID: {article.id}) saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"🛑 Error saving article '{article.title}' (ID: {article.id}) to {file_path}: {e}")
            return False

    @staticmethod
    def extract_highlights(markdown_content: str) -> List[str]:
        """
        Extracts highlighted text (default: ==text==) from markdown.
        Uses constants for highlight tags.
        """
        # Ensure constants are properly escaped for regex if they contain special characters.
        # For "==" this is not strictly necessary but good practice.
        start_tag_escaped = re.escape(constants.MARKDOWN_HIGHLIGHT_START_TAG)
        end_tag_escaped = re.escape(constants.MARKDOWN_HIGHLIGHT_END_TAG)
        
        # Non-greedy match: (.*?)
        pattern = f'{start_tag_escaped}(.*?){end_tag_escaped}'
        
        try:
            highlights = re.findall(pattern, markdown_content)
            return highlights
        except Exception as e: # Should be rare for re.findall with valid patterns
            logger.error(f"🛑 Error extracting highlights: {e}")
            return []

# Example Usage (for testing or illustration, not run when imported)
if __name__ == '__main__':
    # Setup basic logging for the example
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Mock constants for standalone testing if needed (assuming they are available via import)
    # constants.MARKDOWN_HIGHLIGHT_START_TAG = "=="
    # constants.MARKDOWN_HIGHLIGHT_END_TAG = "=="
    # constants.MARKDOWN_NOTES_HEADING = "## My Notes"

    # Create a dummy Article for testing
    test_article_data = {
        constants.KEY_ORIGINAL_URL: "http://example.com/test",
        constants.KEY_TITLE: "Test Article Title",
        constants.KEY_TAGS: ["test", "example"],
        constants.KEY_AUTHOR: ["Author One", "Author Two"]
        # other fields will use defaults from Article.from_dict or dataclass defaults
    }
    test_markdown_body = "This is the main content of the article.\nIt has multiple lines."
    
    article_obj = Article.from_dict(test_article_data, test_markdown_body)
    article_obj.set_notes("These are some notes added to the article.\nWith a second line of notes.")
    
    # Add some highlights to the markdown_content for testing extract_highlights
    article_obj.markdown_content = f"This is ==highlight one==. Some other text. And ==highlight two==.\n{article_obj.markdown_content.split(constants.MARKDOWN_NOTES_HEADING,1)[0].strip().splitlines()[-1]}\n\n{constants.MARKDOWN_NOTES_HEADING}\n{article_obj.get_notes()}"
    # A bit convoluted way to re-insert highlights into main content part before notes for testing
    # A simpler way for test: 
    article_obj.markdown_content = f"Main content with ==highlight one== and ==another highlight==.\n\n{constants.MARKDOWN_NOTES_HEADING}\n{article_obj.get_notes()}"


    logger.info(f"Test Article Object: {article_obj}")

    # Test article_to_markdown_text
    markdown_output = MarkdownHandler.article_to_markdown_text(article_obj)
    logger.info("\n--- Generated Markdown Text ---\n" + markdown_output + "\n------------------------------")

    # Test save_article_to_file
    temp_dir = Path("temp_markdown_handler_test")
    temp_dir.mkdir(exist_ok=True)
    test_file_path = temp_dir / "test_article_output.md"
    save_success = MarkdownHandler.save_article_to_file(article_obj, test_file_path)
    logger.info(f"Save successful: {save_success}. Article local_path: {article_obj.local_path}")

    if save_success:
        # Test parse_markdown_file
        logger.info(f"\n--- Parsing from File: {test_file_path} ---")
        parsed_article = MarkdownHandler.parse_markdown_file(test_file_path)
        if parsed_article:
            logger.info(f"Parsed Article Title: {parsed_article.title}")
            logger.info(f"Parsed Article Content without Notes: '{parsed_article.get_content_without_notes()}'")
            logger.info(f"Parsed Article Notes: '{parsed_article.get_notes()}'")
            logger.info(f"Parsed Article Tags: {parsed_article.tags}")
            logger.info(f"Parsed Article Authors: {parsed_article.author}")
            logger.info(f"Parsed Article local_path: {parsed_article.local_path}")
            
            # Test extract_highlights from parsed article's content
            highlights = MarkdownHandler.extract_highlights(parsed_article.markdown_content)
            logger.info(f"Extracted Highlights from Parsed Content: {highlights}")
        else:
            logger.error("Failed to parse the saved markdown file.")
    
    # Test extract_highlights directly
    sample_text_with_highlights = "This text has ==highlight A== and also ==highlight B: with colon==. No highlight here."
    extracted = MarkdownHandler.extract_highlights(sample_text_with_highlights)
    logger.info(f"\nHighlights from sample text ('{sample_text_with_highlights}'): {extracted}")
    assert extracted == ["highlight A", "highlight B: with colon"]

    # Test parsing a file with no frontmatter
    no_frontmatter_path = temp_dir / "no_frontmatter.md"
    with open(no_frontmatter_path, "w", encoding="utf-8") as f:
        f.write("This is just plain text content.\nNo YAML frontmatter here.")
    parsed_no_fm = MarkdownHandler.parse_markdown_file(no_frontmatter_path)
    if parsed_no_fm:
        logger.info(f"\nParsed No-Frontmatter Title (default): {parsed_no_fm.title}") # Should be "Untitled"
        logger.info(f"Parsed No-Frontmatter Content: '{parsed_no_fm.markdown_content}'")
        assert parsed_no_fm.title == "Untitled" 
        assert parsed_no_fm.markdown_content == "This is just plain text content.\nNo YAML frontmatter here."
    else:
        logger.error("Failed to parse no-frontmatter file.")

    # Test parsing a file with malformed frontmatter (only one ---)
    malformed_fm_path = temp_dir / "malformed_frontmatter.md"
    with open(malformed_fm_path, "w", encoding="utf-8") as f:
        f.write("---\ntitle: Malformed\nThis is body content mistaken for frontmatter.")
    parsed_malformed_fm = MarkdownHandler.parse_markdown_file(malformed_fm_path)
    if parsed_malformed_fm:
        logger.info(f"\nParsed Malformed-Frontmatter Title (default): {parsed_malformed_fm.title}")
        logger.info(f"Parsed Malformed-Frontmatter Content: '{parsed_malformed_fm.markdown_content}'")
        # Behavior: treats whole content as body if frontmatter is malformed
        assert parsed_malformed_fm.title == "Untitled" # As no valid frontmatter was parsed
        assert "title: Malformed" in parsed_malformed_fm.markdown_content 
    else:
        logger.error("Failed to parse malformed-frontmatter file.")

    # Clean up test directory
    # import shutil
    # shutil.rmtree(temp_dir)
    # logger.info(f"Cleaned up test directory: {temp_dir}")
