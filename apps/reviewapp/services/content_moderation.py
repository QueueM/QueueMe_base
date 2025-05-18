"""
Content moderation service for text and file content.

This service provides moderation capabilities for user-generated content,
scanning for inappropriate language, harmful content, and malicious files.
"""

import hashlib
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set

# Requires libmagic system library (brew install libmagic on macOS, apt-get install libmagic1 on Debian/Ubuntu)
import magic
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class ContentModerationService:
    """Service for moderating user-generated content."""

    # Cache TTL settings
    TEXT_MODERATION_CACHE_TTL = 3600 * 24  # 24 hours
    FILE_HASH_CACHE_TTL = 3600 * 24 * 7  # 7 days

    # Profanity and inappropriate content patterns
    INAPPROPRIATE_PATTERNS = [
        # Profanity (basic examples)
        r"\b(f[u\*]+ck|sh[i\*]+t|b[i\*]+tch|d[i\*]+ck|c[u\*]+nt)\b",
        # Hate speech and discrimination
        r"\b(ni[g\*]+[e\*]r|f[a\*]+g|r[e\*]+t[a\*]+rd)\b",
        # Violence
        r"\b(k[i\*]+ll|murder|bomb|attack|rape|assault)\b",
        # Illegal activities
        r"\b(cocaine|heroin|meth|drug dealer|drug buying|illegal drugs)\b",
        # Explicit content
        r"\b(porn|xxx|sex|nude|naked|hardcore)\b",
    ]

    # File extension blacklist
    MALICIOUS_EXTENSIONS = {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".vbs",
        ".js",
        ".jar",
        ".sh",
        ".py",
        ".php",
        ".asp",
        ".aspx",
        ".jsp",
        ".cgi",
        ".pl",
        ".msi",
    }

    # MIME types blacklist
    MALICIOUS_MIME_TYPES = {
        "application/x-msdownload",
        "application/x-ms-dos-executable",
        "application/x-dosexec",
        "application/java-archive",
        "application/x-executable",
        "application/x-shellscript",
        "application/x-msdos-program",
        "application/x-script",
        "text/x-script",
        "text/x-php",
        "text/x-python",
        "text/javascript",
        "application/x-javascript",
    }

    # Known malicious file signatures (magic bytes)
    MALICIOUS_SIGNATURES = {
        b"MZ",  # DOS/PE executables
        b"\x7fELF",  # ELF executables
        b"\xca\xfe\xba\xbe",  # Java class files
        b"#!/",  # Shell scripts
        b"<?php",  # PHP files
    }

    @classmethod
    def is_inappropriate(cls, text: str) -> bool:
        """
        Check if text contains inappropriate content.

        Args:
            text: Text content to check

        Returns:
            bool: True if inappropriate content detected
        """
        if not text:
            return False

        # Normalize text
        normalized_text = text.lower()

        # Check cache first
        cache_key = f"inappropriate_text:{hashlib.sha256(normalized_text.encode()).hexdigest()}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        # Check against patterns
        for pattern in cls.INAPPROPRIATE_PATTERNS:
            if re.search(pattern, normalized_text, re.IGNORECASE):
                # Cache the result
                cache.set(cache_key, True, cls.TEXT_MODERATION_CACHE_TTL)
                return True

        # Check against moderation API if available
        if (
            hasattr(settings, "CONTENT_MODERATION_API_ENABLED")
            and settings.CONTENT_MODERATION_API_ENABLED
        ):
            try:
                result = cls._check_with_moderation_api(normalized_text)
                cache.set(cache_key, result, cls.TEXT_MODERATION_CACHE_TTL)
                return result
            except Exception as e:
                logger.error(f"Error checking text with moderation API: {str(e)}")
                # Fall back to pattern-based checks
                pass

        # Not inappropriate
        cache.set(cache_key, False, cls.TEXT_MODERATION_CACHE_TTL)
        return False

    @classmethod
    def is_malicious_file(cls, file: Any) -> bool:
        """
        Check if file appears to be malicious.

        Args:
            file: File object to check

        Returns:
            bool: True if file appears malicious
        """
        try:
            # Check file extension
            filename = getattr(file, "name", "")
            if filename:
                extension = os.path.splitext(filename.lower())[1]
                if extension in cls.MALICIOUS_EXTENSIONS:
                    logger.warning(f"Blocked malicious file extension: {extension}")
                    return True

            # Get file content for further analysis
            file.seek(0)
            file_content = file.read(4096)  # Read first 4KB for analysis
            file.seek(0)  # Reset file pointer

            # Calculate hash
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Check cache for known malicious files
            cache_key = f"malicious_file:{file_hash}"
            cached_result = cache.get(cache_key)

            if cached_result is not None:
                return cached_result

            # Check MIME type using python-magic
            try:
                mime_type = magic.from_buffer(file_content, mime=True)
                if mime_type in cls.MALICIOUS_MIME_TYPES:
                    logger.warning(f"Blocked malicious MIME type: {mime_type}")
                    cache.set(cache_key, True, cls.FILE_HASH_CACHE_TTL)
                    return True
            except Exception as e:
                logger.error(f"Error detecting MIME type: {str(e)}")

            # Check file signature
            for signature in cls.MALICIOUS_SIGNATURES:
                if file_content.startswith(signature):
                    logger.warning(f"Blocked file with malicious signature: {signature}")
                    cache.set(cache_key, True, cls.FILE_HASH_CACHE_TTL)
                    return True

            # Check with external virus scanning API if available
            if hasattr(settings, "VIRUS_SCAN_API_ENABLED") and settings.VIRUS_SCAN_API_ENABLED:
                try:
                    result = cls._scan_file_with_api(file)
                    cache.set(cache_key, result, cls.FILE_HASH_CACHE_TTL)
                    return result
                except Exception as e:
                    logger.error(f"Error scanning file with API: {str(e)}")

            # Not malicious
            cache.set(cache_key, False, cls.FILE_HASH_CACHE_TTL)
            return False

        except Exception as e:
            logger.error(f"Error in malicious file detection: {str(e)}")
            # Fail safe: if we can't properly analyze, consider it potentially malicious
            return True

    @classmethod
    def moderate_review_content(cls, title: str, content: str) -> Dict[str, Any]:
        """
        Comprehensive review content moderation.

        Args:
            title: Review title
            content: Review content

        Returns:
            Dict containing moderation results
        """
        results = {
            "is_inappropriate": False,
            "spam_score": 0,
            "sentiment_score": 0,
            "reasons": [],
        }

        # Check for inappropriate content
        if cls.is_inappropriate(title):
            results["is_inappropriate"] = True
            results["reasons"].append("inappropriate_title")

        if cls.is_inappropriate(content):
            results["is_inappropriate"] = True
            results["reasons"].append("inappropriate_content")

        # Calculate spam score (0-100)
        spam_score = cls._calculate_spam_score(title, content)
        results["spam_score"] = spam_score

        if spam_score > 70:
            results["reasons"].append("high_spam_score")

        # Analyze sentiment (from -1 to 1, where -1 is very negative)
        sentiment = cls._analyze_sentiment(content)
        results["sentiment_score"] = sentiment

        if sentiment < -0.7:  # Extremely negative
            results["reasons"].append("extremely_negative")

        return results

    @staticmethod
    def _check_with_moderation_api(text: str) -> bool:
        """
        Check text with external moderation API.

        Args:
            text: Text to check

        Returns:
            bool: True if inappropriate
        """
        # Placeholder for actual API integration
        # This would typically make an HTTP request to a content moderation API
        # such as Amazon Comprehend, Google Cloud Content Moderation, or Azure Content Moderator

        logger.debug("Placeholder for content moderation API integration")
        return False

    @staticmethod
    def _scan_file_with_api(file: Any) -> bool:
        """
        Scan file with external virus scanning API.

        Args:
            file: File to scan

        Returns:
            bool: True if malicious
        """
        # Placeholder for actual API integration
        # This would typically make an HTTP request to a virus scanning API
        # such as VirusTotal, ClamAV, etc.

        logger.debug("Placeholder for virus scanning API integration")
        return False

    @staticmethod
    def _calculate_spam_score(title: str, content: str) -> int:
        """
        Calculate spam score for content.

        Args:
            title: Content title
            content: Main content

        Returns:
            int: Spam score (0-100)
        """
        score = 0
        combined = f"{title} {content}".lower()

        # Check for ALL CAPS sections
        uppercase_chars = sum(1 for c in combined if c.isupper())
        if len(combined) > 0:
            uppercase_ratio = uppercase_chars / len(combined)
            if uppercase_ratio > 0.7:  # More than 70% uppercase
                score += 30
            elif uppercase_ratio > 0.5:  # More than 50% uppercase
                score += 20
            elif uppercase_ratio > 0.3:  # More than 30% uppercase
                score += 10

        # Check for excessive punctuation
        exclamation_count = combined.count("!")
        if exclamation_count > 5:
            score += min(30, exclamation_count * 3)

        # Check for repetition
        words = re.findall(r"\b\w+\b", combined)
        if len(words) > 0:
            unique_words = set(words)
            repetition_ratio = 1 - (len(unique_words) / len(words))
            score += int(repetition_ratio * 30)

        # Check for promotional keywords
        promotional_keywords = [
            "buy",
            "free",
            "offer",
            "discount",
            "sale",
            "cheap",
            "deal",
            "price",
            "limited time",
            "exclusive",
            "guarantee",
            "amazing",
            "incredible",
        ]
        keyword_count = sum(1 for keyword in promotional_keywords if keyword in combined)
        score += min(30, keyword_count * 5)

        # Check for URL density
        urls = re.findall(r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+", combined)
        if urls:
            score += min(40, len(urls) * 20)

        return min(100, score)  # Cap at 100

    @staticmethod
    def _analyze_sentiment(text: str) -> float:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            float: Sentiment score (-1 to 1)
        """
        # Placeholder for actual sentiment analysis
        # This would typically use a NLP library like NLTK, TextBlob, or external API

        # Simple keyword-based sentiment as fallback
        positive_words = [
            "good",
            "great",
            "excellent",
            "amazing",
            "wonderful",
            "fantastic",
            "awesome",
            "happy",
            "pleased",
            "satisfied",
            "love",
            "like",
            "enjoy",
        ]
        negative_words = [
            "bad",
            "poor",
            "terrible",
            "horrible",
            "awful",
            "dreadful",
            "disappointing",
            "hate",
            "dislike",
            "unhappy",
            "frustrated",
            "angry",
            "worst",
        ]

        words = re.findall(r"\b\w+\b", text.lower())
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)

        if positive_count == 0 and negative_count == 0:
            return 0  # Neutral

        return (positive_count - negative_count) / (positive_count + negative_count)
