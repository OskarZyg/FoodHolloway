import email
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Optional

from imapclient import IMAPClient

logger = logging.getLogger(__name__)


def decode_imap_address(addr):
    """Handle both Address objects and 4-tuples."""
    # IMAPClient's ENVELOPE.from_ often contains Address objects like:
    # Address(name=b'John Doe', route=None, mailbox=b'john.doe', host=b'gmail.com')
    if addr is None:
        return None, None

    # If it's an Address object, just access its fields
    if hasattr(addr, 'mailbox') and hasattr(addr, 'host'):
        name = getattr(addr, 'name', None)
        mailbox = getattr(addr, 'mailbox', None)
        host = getattr(addr, 'host', None)
    else:
        # fallback for 4-tuples
        if len(addr) < 4:
            return None, None
        name, adl, mailbox, host = addr

    def safe_str(x):
        if x is None:
            return ""
        return x.decode() if isinstance(x, (bytes, bytearray)) else str(x)

    name, mailbox, host = map(safe_str, (name, mailbox, host))

    if mailbox and host:
        return name, f"{mailbox}@{host}"
    return name, None


def get_sender_from_envelope(envelope):
    """Extract sender email (and name) from an IMAP ENVELOPE object."""
    if not envelope:
        return None

    addrs = getattr(envelope, "from_", None)
    if not addrs:
        return None

    # It's a tuple of Address objects
    addr = addrs[0]
    name, email = decode_imap_address(addr)
    return email or None


class ReviewDatabase:
    """SQLite database for managing review requests."""

    def __init__(self, db_path: str = 'reviews.db'):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS review_requests
                           (
                               uuid           TEXT PRIMARY KEY,
                               rating         INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                               review_subject TEXT    NOT NULL,
                               email          TEXT,
                               display_name   TEXT,
                               created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                               updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                           )
                           """)
            conn.commit()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_cursor(self):
        """Context manager for database cursors (for compatibility with existing code)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create a wrapper object with the set_email method
        class CursorWrapper:
            def __init__(self, cursor, conn, db):
                self._cursor = cursor
                self._conn = conn
                self._db = db

            def set_email(self, gen_uuid, email_addr, display_name):
                return self._db._set_email(self._conn, gen_uuid, email_addr, display_name)

            def __getattr__(self, name):
                # Delegate all other attributes to the underlying cursor
                return getattr(self._cursor, name)

        wrapper = CursorWrapper(cursor, conn, self)
        try:
            yield wrapper
        finally:
            conn.close()

    def create_review_request(self, rating: int, review_subject: str) -> str:
        """
        Create a new review request with a rating (1-5) and subject.

        Args:
            rating: Integer between 1 and 5
            review_subject: Text description of what is being reviewed

        Returns:
            UUID string for the created review request

        Raises:
            ValueError: If rating is not between 1 and 5 or review_subject is empty
        """
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            raise ValueError("Rating must be an integer between 1 and 5")

        if not review_subject or not review_subject.strip():
            raise ValueError("Review subject cannot be empty")

        review_uuid = str(uuid.uuid4())

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           INSERT INTO review_requests (uuid, rating, review_subject)
                           VALUES (?, ?, ?)
                           """, (review_uuid, rating, review_subject.strip()))
            conn.commit()

        logger.info("Created review request %s with rating %d for '%s'",
                    review_uuid, rating, review_subject)
        return review_uuid

    def _set_email(self, conn, review_uuid: uuid.UUID, email_addr: str, display_name: str) -> bool:
        """
        Set the email and display name for an existing review request.

        Args:
            conn: Database connection
            review_uuid: UUID of the review request
            email_addr: Email address to set
            display_name: Display name to set

        Returns:
            True if the record was updated, False otherwise
        """
        cursor = conn.cursor()
        cursor.execute("""
                       UPDATE review_requests
                       SET email        = ?,
                           display_name = ?,
                           updated_at   = CURRENT_TIMESTAMP
                       WHERE uuid = ?
                       """, (email_addr, display_name, str(review_uuid)))
        conn.commit()

        rows_affected = cursor.rowcount
        if rows_affected > 0:
            logger.info("Updated review request %s with email %s", review_uuid, email_addr)
            return True
        else:
            logger.warning("No review request found with UUID %s", review_uuid)
            return False

    def get_review_request(self, review_uuid: str) -> Optional[dict]:
        """
        Retrieve a review request by UUID.

        Args:
            review_uuid: UUID string of the review request

        Returns:
            Dictionary containing review request data or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT uuid, rating, review_subject, email, display_name, created_at, updated_at
                           FROM review_requests
                           WHERE uuid = ?
                           """, (review_uuid,))

            row = cursor.fetchone()
            if row:
                return {
                    'uuid': row[0],
                    'rating': row[1],
                    'review_subject': row[2],
                    'email': row[3],
                    'display_name': row[4],
                    'created_at': row[5],
                    'updated_at': row[6]
                }
            return None

    def get_reviews_by_subject(self, review_subject: str) -> list[dict]:
        """
        Retrieve all review requests for a specific subject.

        Args:
            review_subject: The subject to search for (case-insensitive)

        Returns:
            List of dictionaries containing review request data
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT uuid, rating, review_subject, email, display_name, created_at, updated_at
                           FROM review_requests
                           WHERE LOWER(review_subject) = LOWER(?)
                           ORDER BY created_at DESC
                           """, (review_subject,))

            rows = cursor.fetchall()
            return [
                {
                    'uuid': row[0],
                    'rating': row[1],
                    'review_subject': row[2],
                    'email': row[3],
                    'display_name': row[4],
                    'created_at': row[5],
                    'updated_at': row[6]
                }
                for row in rows
            ]

    def get_reviews_by_subject_partial(self, search_term: str) -> list[dict]:
        """
        Retrieve all review requests where the subject contains the search term.

        Args:
            search_term: Term to search for in review subjects (case-insensitive)

        Returns:
            List of dictionaries containing review request data
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT uuid, rating, review_subject, email, display_name, created_at, updated_at
                           FROM review_requests
                           WHERE LOWER(review_subject) LIKE LOWER(?)
                           ORDER BY created_at DESC
                           """, (f'%{search_term}%',))

            rows = cursor.fetchall()
            return [
                {
                    'uuid': row[0],
                    'rating': row[1],
                    'review_subject': row[2],
                    'email': row[3],
                    'display_name': row[4],
                    'created_at': row[5],
                    'updated_at': row[6]
                }
                for row in rows
            ]

    def get_all_subjects(self) -> list[str]:
        """
        Retrieve all unique review subjects.

        Returns:
            List of unique review subject strings, ordered by most recent
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           SELECT DISTINCT review_subject
                           FROM review_requests
                           ORDER BY review_subject
                           """)

            rows = cursor.fetchall()
            return [row[0] for row in rows]

    def get_subject_statistics(self, review_subject: str) -> Optional[dict]:
        """
        Get statistics for reviews of a specific subject.

        Args:
            review_subject: The subject to get statistics for

        Returns:
            Dictionary containing count, average rating, and rating distribution
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get overall statistics
            cursor.execute("""
                           SELECT COUNT(*)                                           as total_reviews,
                                  AVG(rating)                                        as avg_rating,
                                  MIN(rating)                                        as min_rating,
                                  MAX(rating)                                        as max_rating,
                                  SUM(CASE WHEN email IS NOT NULL THEN 1 ELSE 0 END) as completed_reviews
                           FROM review_requests
                           WHERE LOWER(review_subject) = LOWER(?)
                           """, (review_subject,))

            stats_row = cursor.fetchone()

            if stats_row[0] == 0:  # No reviews found
                return None

            # Get rating distribution
            cursor.execute("""
                           SELECT rating, COUNT(*) as count
                           FROM review_requests
                           WHERE LOWER(review_subject) = LOWER(?)
                           GROUP BY rating
                           ORDER BY rating
                           """, (review_subject,))

            distribution = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                'review_subject': review_subject,
                'total_reviews': stats_row[0],
                'completed_reviews': stats_row[4],
                'pending_reviews': stats_row[0] - stats_row[4],
                'average_rating': round(stats_row[1], 2) if stats_row[1] else 0,
                'min_rating': stats_row[2],
                'max_rating': stats_row[3],
                'rating_distribution': distribution
            }


class EmailClient:
    def __init__(self, database: ReviewDatabase, config: dict) -> None:
        self.db = database
        self.config = config

    def process_changes(self):
        # context manager ensures the session is cleaned up
        with IMAPClient(host=self.config['IMAP_HOST']) as client:
            logger.info("Connecting to IMAP server...")
            client.login(self.config['IMAP_USERNAME'], self.config['IMAP_PASSWORD'])
            client.select_folder('INBOX')

            # search for unseen emails only
            messages = client.search([u'ALL'])

            with self.db.get_cursor() as cursor:
                for uid, message_data in client.fetch(messages, ["RFC822", "ENVELOPE"]).items():
                    email_message = email.message_from_bytes(message_data[b"RFC822"])
                    from_email = get_sender_from_envelope(message_data[b"ENVELOPE"])
                    display_name = email_message.get("From")
                    subject = email_message.get("Subject")

                    logger.debug("Processing email (uid:%s) from %s", uid, from_email)

                    if not from_email.endswith("@live.rhul.ac.uk"):
                        logger.info("Skipping email (uid:%s) from %s and moving to Junk", uid, from_email)
                        client.move([uid], "Junk")
                        continue

                    if subject is not None:
                        try:
                            logger.info("Processing email (uid:%s) from %s", uid, from_email)
                            gen_uuid = uuid.UUID(subject)
                            cursor.set_email(gen_uuid, from_email, display_name)

                            # Mark email as seen after successful insertion
                            client.add_flags([uid], [b'\\Seen'])
                            client.move([uid], "Archive")

                            logger.info("Assigned %s if the appropriate record existed and archived", from_email)
                        except ValueError:
                            logger.error("Could not process email (uid:%s) from %s", uid, from_email)