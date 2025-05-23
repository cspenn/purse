## Product Requirements Document: Purse

**Author:** Christopher Penn
**Date:** May 23, 2025
**GitHub Repository:** `https://github.com/cspenn/purse`

**1. Introduction**

**1.1. Product Vision**
Purse is a self-hosted, open-source "read-it-later" application designed for individuals seeking to capture, consume, and curate web content with a focus on privacy, data ownership, and a superior reading experience. It empowers users to build a personal, permanent library of articles and web pages, free from algorithmic clutter and external dependencies.

**1.2. Goals and Objectives**
* Provide a reliable, user-friendly platform for saving web articles, PDFs, and other content for later, offline consumption.
* Offer a clean, customizable, and distraction-free reading environment.
* Ensure user data is privately stored in their chosen cloud storage solution and is always accessible and exportable.
* Deliver robust search and organization capabilities to make the saved content a valuable personal knowledge base.
* Serve as a compelling alternative for former Pocket users and new users seeking control over their read-it-later experience.
* Build a maintainable, cross-platform application using Python and open-source principles.

**2. Personas**

**2.1. "Alex the Researcher" - Primary Persona**
* **Age:** 35-55
* **Occupation:** Academic, journalist, consultant, or avid lifelong learner.
* **Technical Comfort:** Moderate to high. Comfortable installing and configuring applications, understands cloud storage. Values open source.
* **Goals & Motivations:**
    * Collects a large volume of articles, papers, and web resources for research, reference, and deep reading.
    * Needs to organize content effectively with tags and notes.
    * Requires robust search to rediscover information quickly.
    * Values offline access for reading during commutes or travel.
    * Frustrated with ads, paywalls, and content disappearing from the web.
    * Seeks privacy and long-term ownership of their curated library.
    * Appreciates a focused, customizable reading experience.
* **Frustrations with Existing Tools:**
    * Unreliable search in other "read-it-later" apps[cite: 37, 48].
    * Features being removed or degraded after acquisitions[cite: 34, 53].
    * Poor text-to-speech functionality[cite: 36].
    * Lack of control over data or unwanted algorithmic content feeds[cite: 38, 45].

**3. User Stories**

**3.1. Content Saving & Management**
* As Alex, I want to easily save web articles from my mobile browser so I can read them later without distractions.
* As Alex, I want the application to automatically clean up articles, removing ads and clutter, so I can focus on the content[cite: 2, 11].
* As Alex, I want to save links to PDF and DOCX files, and have their text content extracted and stored so I can read and search them like articles.
* As Alex, I want to save links to videos, audio files, or other non-text web pages as bookmarks so I can keep track of them alongside my articles.
* As Alex, I want the application to retry fetching content if it fails, so I have a higher chance of successfully saving items.
* As Alex, I want to use services like `archive.is` as a fallback for saving content that is behind paywalls or difficult to parse, so I can access more of the content I need.

**3.2. Reading & Consumption**
* As Alex, I want a clean, distraction-free reading view so I can concentrate on the text.
* As Alex, I want to customize fonts, text size, and background themes (light/dark mode) for a comfortable reading experience[cite: 5, 31].
* As Alex, I want to read my saved articles offline on any of my devices, so my library is always accessible[cite: 3, 12].
* As Alex, I want to use Text-to-Speech (TTS) functionality on my device to listen to articles, so I can consume content while multitasking.
* As Alex, I want articles I've read to be visually marked (e.g., greyed out) but still easily accessible.

**3.3. Organization & Discovery**
* As Alex, I want to add multiple tags to articles so I can organize my library by topic or project[cite: 8].
* As Alex, I want to tag articles from the list view and the article view, and be able to tag multiple articles at once.
* As Alex, I want to mark articles as favorites for quick access[cite: 3].
* As Alex, I want to take notes within an article and have them stored with the article content so I can capture my thoughts.
* As Alex, I want to highlight important passages in articles and have these highlights saved and easily viewable[cite: 4, 8].
* As Alex, I want robust full-text search across all my articles, notes, and highlights so I can find information quickly and reliably[cite: 5, 20].
* As Alex, I want to search by metadata like tags, author, title, and publication so I can narrow down my searches.
* As Alex, I want to see recommendations for similar articles from my *own* library based on keywords or content, so I can rediscover relevant items.
* As Alex, I want to view my articles in different layouts (card view with thumbnails, list view, headline-only view) and sort them by title, date, or manually.

**3.4. Data & Account Management**
* As Alex, I want to store all my saved content in my personal cloud storage (Dropbox, Google Drive, OneDrive) so I have full control and ownership of my data.
* As Alex, I want my saved articles and changes to sync automatically and reliably across all my devices (desktop and mobile).
* As Alex, I want the application to handle sync conflicts gracefully, with a "last write wins" policy and a log of conflict resolutions.
* As Alex, I want to easily import my existing library from Pocket, including articles, tags, notes, and highlights, with deduplication to avoid redundant entries.
* As Alex, I want the application setup to be straightforward, including connecting to my cloud storage securely.
* As Alex, I want my application preferences to sync across devices.

**3.5. System Feedback & Troubleshooting**
* As Alex, I want to see the status of background tasks like syncing or parsing.
* As Alex, I want to receive system notifications for important errors.
* As Alex, I want access to an in-app log viewer to understand issues or sync activities.
* As Alex, I want to receive non-intrusive notifications from the developer about important app updates or information.

**4. Domain Requirements**

* **Web Content Heterogeneity:** The system must be prepared to handle a wide variety of HTML structures, dynamic content, and potential anti-scraping measures when fetching web articles[cite: 146]. Robust parsing is a core challenge and requirement[cite: 145].
* **Offline-First Principle:** The application architecture must prioritize local data availability. All content and metadata essential for reading, searching (via local index), and basic organization must be stored locally on each device. Synchronization is for backup and cross-device consistency.
* **Data Durability & Integrity:** Saved content (Markdown files) is considered permanent. Sync mechanisms must be designed to minimize data loss, with clear strategies for conflict resolution.
* **Metadata Importance:** Rich metadata (extracted and user-generated) is crucial for organization, search, and filtering. The system must reliably extract, store, and index this metadata.
* **User Data Privacy:** Since the data is stored in the user's own cloud account and the application is self-hosted, user privacy is inherently enhanced. The application should not transmit user content or identifiable usage data to third parties, except for the user-configured cloud storage provider and the optional `archive.is` fallback (with user awareness).
* **Annotation Standards:** Highlights and notes will be stored within the Markdown content itself using defined conventions to ensure portability and searchability.

**5. Functional Requirements**

**5.1. Content Saving and Parsing**
* **Primary Input:** Mobile share-sheet integration and direct URL input within the app.
* **Web Article Parsing:**
    * Utilize `Trafilatura` (Python library) as the primary engine for extracting main article content from URLs and converting it to clean Markdown, stripping ads, navigation, and other extraneous elements.
    * **Fallback Mechanism:** If `Trafilatura` fails to retrieve or adequately parse content (e.g., due to paywalls or complex JavaScript rendering), the application will attempt to fetch the content via `archive.is` (or a user-configured similar archival service). The content from the archival service will then be processed by `Trafilatura`.
    * Metadata must indicate if content was sourced via an archival service.
* **File-Based Content Conversion:**
    * **PDFs:** Extract text content using `PyMuPDF (Fitz)` or a similar high-quality Python library. Store extracted text as Markdown.
    * **DOCX:** Extract text content using `python-docx` or a similar Python library. Store extracted text as Markdown.
* **Bookmark-Only Content:** For URLs pointing to non-textual or non-article content (e.g., videos, audio files, spreadsheets, general websites), save a Markdown file containing:
    * YAML frontmatter with metadata: original URL, title, user tags, user notes.
    * The body may contain a direct link to the content and any user notes.
* **Retry Logic:** For all content fetching operations (direct, archive, file downloads), implement a 5-attempt retry mechanism with exponential backoff between attempts.

**5.2. Data Storage and Format**
* **Storage Model:** Individual Markdown (`.md`) files for each saved item.
* **Storage Location:** User-specified folder within their chosen cloud storage provider (Dropbox, Google Drive, Microsoft OneDrive).
* **Markdown File Structure:**
    * **YAML Frontmatter:**
        * `id`: UUID (application-generated unique identifier).
        * `pocket_id`: Original Pocket ID (for migration, optional).
        * `original_url`: Original URL of the content.
        * `title`: Article title.
        * `author`: Extracted author(s) (list of strings or string).
        * `publication_name`: Name of the website or publication.
        * `publication_date`: Original publication date (ISO 8601 string, if available).
        * `saved_date`: Timestamp of when saved into Purse (ISO 8601 string).
        * `last_modified_date`: Timestamp of last modification within Purse (ISO 8601 string).
        * `status`: Read status ('unread', 'in-progress', 'read', 'archived').
        * `favorite`: Boolean (true/false).
        * `tags`: List of strings.
        * `estimated_read_time_minutes`: Integer.
        * `word_count`: Integer.
        * `language`: Detected language (e.g., 'en', 'es').
        * `excerpt`: Short summary or auto-generated preview.
        * `source_application`: How the item was added (e.g., "web_parser", "pdf_import", "pocket_migration", "bookmark").
        * `archived_from_fallback`: Boolean.
        * `thumbnail_url_local`: Path to a locally stored thumbnail image relative to the article file (if feature implemented).
    * **Main Content:** Cleaned article text, or extracted text from files, in Markdown format. For bookmarks, this section may be minimal.
    * **Highlights:** Embedded within the Markdown body using the syntax: `==highlighted text==`.
    * **Notes:** Stored under a dedicated heading `## My Notes` at the end of the Markdown file. Standard Markdown can be used within this section.

**5.3. Reading Experience & UI/UX (Toga Framework)**
* **Navigation:** Implement using modern UI best practices suitable for Toga, ensuring consistency across platforms.
* **Article List Display:**
    * **Views:** Card view, list view, and headline-only view.
    * **Thumbnails:** For card view, extract and display a lead image from the article content. Store thumbnails locally relative to the article Markdown file or manage via the index.
    * **Read Status:** Read articles to be visually differentiated (e.g., greyed out) but remain fully accessible.
* **Article List Sorting:**
    * By title (A-Z, Z-A).
    * By date (saved date, publication date; newest first, oldest first).
    * Manual sorting (drag-and-drop reordering of articles in lists – to be evaluated for feasibility with Toga).
* **Reading View:**
    * Clean, distraction-free presentation of Markdown content.
    * Font customization (family, size).
    * Theme customization (light, dark, sepia modes).
    * "Page-like" reading experience (e.g., clear pagination or smooth scrolling with appropriate text width for readability).
* **Progress Monitoring:** Utilize `tqdm` principles for visual feedback on long-running operations within the UI where appropriate (e.g., initial sync, large import).

**5.4. Search & Discovery**
* **Local Indexing Engine:** Use `Whoosh` (Python library) to create and manage a local full-text search index. The index should cover article text, notes, highlights, and key metadata fields.
* **Query Capabilities:**
    * Full-text search across all indexed content.
    * Fielded search (e.g., `tag:research`, `author:"Jane Doe"`).
    * Boolean operators (AND, OR, NOT), phrase searching.
* **Results Presentation:** Sortable by relevance, date saved, publication date, title.
* **Similar Article Recommendations (V1):**
    * Keyword-based similarity (e.g., TF-IDF on article text/tags + cosine similarity).
    * Recommendations sourced exclusively from the user's own saved library.
    * Displayed contextually (e.g., when viewing an article).

**5.5. Tagging**
* **Multi-Tag Support:** Articles can have multiple tags.
* **Tagging Interface:**
    * Add/remove tags from the article reading view.
    * Add/remove tags from the article list views (list, card, headline).
    * Batch tagging: Select multiple articles to add/remove common tags.
    * Autocomplete tag suggestions based on existing tags in the library.

**5.6. Text-to-Speech (TTS)**
* **Engine:** Utilize native OS TTS engines on each platform (Android, iOS, Windows, macOS, Linux) via Python integration.
* **Controls:** UI elements for play, pause, stop.
* **Future Enhancements:** Voice selection, speed control (if native APIs allow uniformly), synchronized text highlighting.

**5.7. Cloud Synchronization & Conflict Resolution**
* **Providers:** Support Dropbox, Google Drive, Microsoft OneDrive.
* **Mechanism:** Direct API integration using official Python SDKs.
* **Sync Logic:**
    * Detect local and remote changes (new, modified, deleted files) based on last sync state and file modification timestamps.
    * Two-way sync: upload local changes, download remote changes.
    * Sync on startup, periodically (if app is running), and manual trigger.
* **Conflict Resolution:** "Last Write Wins" based on the latest file modification timestamp (from cloud provider metadata).
* **Conflict Logging:** All conflict resolution actions and significant sync events recorded in a user-accessible log file (`sync_actions.log` within the logs folder).

**5.8. Data Migration (from Pocket)**
* **Importer Tool:** In-app functionality to import from Pocket's export format.
* **Process:**
    * Parse Pocket export file(s).
    * Map Pocket data fields (URL, title, tags, content, timestamps, notes, highlights) to Purse's Markdown/YAML structure.
    * Convert Pocket notes and highlights to the `## My Notes` and `==highlight==` conventions.
    * Deduplicate incoming articles based on `original_url`; skip if already exists.
    * Content from Pocket's export should be re-parsed/cleaned using `Trafilatura` if it's raw HTML, or used as-is if it's already sufficiently clean.

**5.9. Application Configuration & Setup**
* **First-Run Setup:**
    * User selects cloud storage provider.
    * Secure OAuth authentication via system browser. Access/refresh tokens stored in OS credential manager (keychain/keystore).
    * User confirms/selects a root sync folder in their cloud storage (e.g., default path `/Apps/Purse/`).
* **Configuration Storage:**
    * A dedicated subfolder (e.g., `.purse_config/`) within the root sync folder will store shareable application settings (e.g., `settings.yml`). This includes UI preferences, parsing options, developer notification URL, etc.
    * Device-specific settings (e.g., window size, last selected folder for local file import) stored locally in the OS-idiomatic application data location.
* **YAML for Configuration:** All application configuration (settings, debug levels) managed via YAML files (`settings.yml`, `config.yml` as appropriate). No environment variables or hardcoded settings for configurable parameters.

**5.10. Error Handling, Logging & Notifications**
* **Logging Framework:**
    * Comprehensive logging to both console and timestamped log files (e.g., `log-YYYY-MM-DD-HH-MM-SS.log`) in a local `logs` directory.
    * Use emojis for log levels in console/UI log viewer: 🟢 (INFO), 🟡 (WARN), 🛑 (ERROR).
    * Log levels configurable in `settings.yml`, defaulting to `DEBUG`.
* **Error Presentation:**
    * System notifications for critical errors or completion of significant background tasks (e.g., large import, sync with conflicts).
    * A dedicated status area on the application's main/start page for persistent errors or important status messages.
* **In-App Log Viewer:** Allows users to view formatted application logs (including `sync_actions.log`) for troubleshooting.
* **Developer Notifications:**
    * App fetches messages from a developer-specified URL (default: `https://www.christopherspenn.com/purse/notifications`).
    * Displayed non-intrusively to inform users of updates or important notices.
    * URL configurable in `settings.yml`.

**6. Non-Functional Requirements**

* **Performance:** Responsive UI; background processing for parsing, sync, indexing to prevent UI freezes. Efficient loading and display of articles.
* **Security:** Secure storage of OAuth tokens. No hardcoding of sensitive data. HTTPS for all external communications.
* **Usability:** Intuitive navigation, clear feedback, straightforward setup.
* **Cross-Platform Compatibility:** Consistent core functionality and user experience across supported Toga platforms (Android, iOS, Windows, macOS, Linux).
* **Maintainability:** Clean, well-documented Python 3.11 code adhering to specified development guidelines.
* **Offline Capability:** Full access to read, search (local index), and organize already-synced content when offline. Changes queued for next sync.
* **Data Integrity:** Minimize risk of data loss during sync or file operations.

**7. Development Guidelines & Stack**

* **Language:** Python 3.11.
* **GUI Framework:** Toga.
* **Key Libraries (to be evaluated for "best performing, most up-to-date"):**
    * Content Parsing: `Trafilatura`.
    * PDF Text Extraction: `PyMuPDF (Fitz)`.
    * DOCX Text Extraction: `python-docx`.
    * Search Indexing: `Whoosh`.
    * Cloud Storage: Official Python SDKs for Dropbox, Google Drive, Microsoft OneDrive.
    * Configuration: YAML processing library (e.g., `PyYAML`).
* **Progress Monitoring:** `tqdm` for console/log output of background tasks; Toga-equivalent UI progress indicators where applicable.
* **Development Principles:**
    * DRY (Don't Repeat Yourself).
    * SPOT (Single Point of Truth).
    * YAGNI (You Ain't Gonna Need It).
* **Code Structure:** `main.py` to serve as the orchestrator, with core logic organized into separate modules/files.
* **Configuration Management:** All configurations (application behavior, paths, debug levels) through YAML files. No environment variables or hardcoded settings for parameters.
* **Open Source License:** MIT License (or other permissive FOSS license to be confirmed by author).

**8. Future Considerations / Roadmap**

* Enhanced semantic search and recommendations using local, small LLM embeddings.
* Advanced TTS features: synchronized text highlighting, cross-platform voice/speed selection enhancements.
* More sophisticated sync conflict resolution options (e.g., diff/merge helpers, CRDT-inspired mechanisms for specific data types).
* Support for additional content import sources (e.g., other "read-it-later" services, RSS feeds).
* Web client interface as a companion to the Toga desktop/mobile apps.
* Client-side end-to-end encryption of content before upload to cloud storage.
* Expanded annotation tools (e.g., more highlight colors, free-form drawing on articles if feasible with Markdown/Toga).
* Integration with citation managers or personal knowledge bases (e.g., Zotero, Obsidian).
