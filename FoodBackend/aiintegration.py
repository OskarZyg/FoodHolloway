import json
import sqlite3

from google import genai

MIGRATION = """
            CREATE TABLE IF NOT EXISTS NodeDescriptions
            (
                TagsHash    TEXT NOT NULL PRIMARY KEY,
                Description TEXT NOT NULL
            ); \
            """


class AIIntegration:
    def __init__(self):
        # The client gets the API key from the environment variable `GEMINI_API_KEY`.
        self.client = genai.Client()
        self.db = sqlite3.connect('summaries.sqlite3', check_same_thread=False)
        self.cursor = self.db.cursor()
        # Run migration to ensure table exists
        self.cursor.executescript(MIGRATION)
        self.db.commit()

    def get_node_description(self, tags: dict) -> dict:
        """
        Returns a dictionary with both a full description and cuisine description.
        Returns: {"description": str, "cuisine": str}
        """
        # Handle None input
        if tags is None:
            tags = {}

        # Filter out metadata/internal tags that aren't useful for end users
        excluded_keys = {
            'check_date', 'note', 'source', 'attribution', 'created_by',
            'fixme', 'FIXME', 'todo', 'source:date', 'survey:date',
            'gnis:feature_id', 'tiger:reviewed', 'type', 'ref:GB:nhle'
        }

        # Create filtered tags dictionary
        filtered_tags = {
            k: v for k, v in tags.items()
            if k not in excluded_keys and not k.startswith('source:') and not k.startswith('note:')
        }

        # Create a stable hash of the tags for caching
        tags_json = json.dumps(filtered_tags, sort_keys=True)
        import hashlib
        tags_hash = hashlib.sha256(tags_json.encode()).hexdigest()

        # Check cache first
        self.cursor.execute("SELECT Description FROM NodeDescriptions WHERE TagsHash = ?", (tags_hash,))
        result = self.cursor.fetchone()

        if result:
            # Cache hit - return cached description
            cached_data = json.loads(result[0])
            return cached_data

        # Cache miss - generate new description
        response = self.client.models.generate_content(
            model="gemma-3-12b-it",
            config=genai.types.GenerateContentConfig(
                system_instruction="""You are tasked with creating user-friendly descriptions of OpenStreetMap points of interest.

    Given a set of OSM tags (key-value pairs), provide TWO things:

    1. "description": A concise, natural description (1-3 sentences) that tells end users what this place is and what makes it notable. Focus on practical, user-relevant information like what the place is (amenity type), its name, notable features (wheelchair access, opening hours if present, outdoor seating, etc.), and any distinguishing characteristics.

    2. "cuisine": If there's a cuisine tag, humanize it into a few words using British English with emojis if strictly applicable. If no cuisine tag exists, return an empty string.

    EXCLUDE from description: Technical metadata like check_date, source, note, FIXME, todo, attribution, creation info, reference IDs, or surveyor notes.

    Use British English. Keep it conversational and helpful for someone deciding whether to visit.""",
                response_json_schema={
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string"
                        },
                        "cuisine": {
                            "type": "string"
                        }
                    },
                    "required": ["description", "cuisine"],
                    "additionalProperties": False
                }
            ),
            contents=tags_json
        )
        result_data = json.loads(response.text)

        # Save to cache (store as JSON string)
        self.cursor.execute(
            "INSERT OR REPLACE INTO NodeDescriptions (TagsHash, Description) VALUES (?, ?)",
            (tags_hash, json.dumps(result_data))
        )
        self.db.commit()

        return result_data

    def __del__(self):
        # Clean up database connection
        if hasattr(self, 'db'):
            self.db.close()
