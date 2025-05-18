import logging
import re

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Simple sentiment analysis for review moderation"""

    # These are simplified lexicons for demo purposes
    # In production, use a more sophisticated sentiment analysis or ML model
    POSITIVE_WORDS = {
        "en": [
            "good",
            "great",
            "excellent",
            "amazing",
            "wonderful",
            "fantastic",
            "awesome",
            "best",
            "love",
            "perfect",
            "helpful",
            "professional",
            "recommend",
            "comfortable",
            "clean",
            "friendly",
            "enjoyed",
            "impressed",
            "quality",
            "satisfied",
            "top",
            "pleasant",
            "nice",
            "kind",
        ],
        "ar": [
            "جيد",
            "رائع",
            "ممتاز",
            "مدهش",
            "عظيم",
            "هائل",
            "أحب",
            "أفضل",
            "مثالي",
            "مفيد",
            "محترف",
            "أوصي",
            "مريح",
            "نظيف",
            "ودود",
            "استمتعت",
            "منبهر",
            "جودة",
            "راض",
            "لطيف",
        ],
    }

    NEGATIVE_WORDS = {
        "en": [
            "bad",
            "terrible",
            "horrible",
            "awful",
            "poor",
            "disappointing",
            "waste",
            "worst",
            "hate",
            "dirty",
            "unprofessional",
            "rude",
            "avoid",
            "overpriced",
            "slow",
            "useless",
            "mediocre",
            "not worth",
            "unhappy",
            "dissatisfied",
            "problem",
            "never again",
            "cheap",
            "failed",
        ],
        "ar": [
            "سيء",
            "فظيع",
            "مروع",
            "رديء",
            "مخيب للآمال",
            "إهدار",
            "أسوأ",
            "أكره",
            "قذر",
            "غير محترف",
            "وقح",
            "تجنب",
            "مبالغ في السعر",
            "بطيء",
            "عديم الفائدة",
            "متوسط",
            "لا يستحق",
            "غير سعيد",
            "غير راضٍ",
            "مشكلة",
            "لن أعود",
            "رخيص",
            "فشل",
        ],
    }

    # Strong negative words that might warrant moderation
    MODERATION_WORDS = {
        "en": [
            "scam",
            "fraud",
            "cheat",
            "liar",
            "steal",
            "illegal",
            "criminal",
            "racist",
            "sexist",
            "discriminate",
            "violent",
            "disgusting",
            "lawsuit",
            "report",
            "authorities",
            "unsafe",
            "dangerous",
            "harmful",
            "fake",
            "dishonest",
            "corrupt",
        ],
        "ar": [
            "احتيال",
            "خداع",
            "كذاب",
            "سرقة",
            "غير قانوني",
            "إجرامي",
            "عنصري",
            "متحيز جنسيًا",
            "تمييز",
            "عنيف",
            "مقرف",
            "دعوى قضائية",
            "بلاغ",
            "سلطات",
            "غير آمن",
            "خطير",
            "ضار",
            "مزيف",
            "غير صادق",
            "فاسد",
        ],
    }

    @classmethod
    def analyze_text(cls, text, language=None):
        """Analyze sentiment of text

        Args:
            text (str): Text to analyze
            language (str, optional): Language code ('en' or 'ar')

        Returns:
            float: Sentiment score (-1.0 to 1.0, where negative is bad)
        """
        try:
            if not text:
                return 0.0

            # Clean text - lowercase, remove punctuation
            if language != "ar":  # Skip for Arabic
                text = text.lower()
            text = re.sub(r"[^\w\s]", " ", text)
            words = text.split()

            # Detect language if not provided
            if not language:
                # Simple heuristic - presence of Arabic characters
                if any("\u0600" <= c <= "\u06ff" for c in text):
                    language = "ar"
                else:
                    language = "en"

            # Count positive and negative words
            positive_count = 0
            negative_count = 0
            moderation_count = 0

            for word in words:
                if word in cls.POSITIVE_WORDS.get(language, []):
                    positive_count += 1
                if word in cls.NEGATIVE_WORDS.get(language, []):
                    negative_count += 1
                if word in cls.MODERATION_WORDS.get(language, []):
                    moderation_count += 2  # Extra weight for moderation words

            # Calculate sentiment score
            total_words = len(words)
            if total_words == 0:
                return 0.0

            positive_score = positive_count / total_words
            negative_score = (negative_count + moderation_count) / total_words

            # Normalize to -1.0 to 1.0
            sentiment_score = positive_score - negative_score

            # Flag for moderation if strong moderation words present
            if moderation_count > 0:
                logger.warning(
                    f"Review contains moderation words. Moderation score: {moderation_count}"
                )

            return max(-1.0, min(1.0, sentiment_score))

        except Exception as e:
            logger.error(f"Error analyzing sentiment: {str(e)}")
            return 0.0

    @classmethod
    def should_moderate(cls, text, threshold=-0.5):
        """Determine if a review should be moderated based on sentiment

        Args:
            text (str): Review text
            threshold (float): Sentiment threshold for moderation

        Returns:
            bool: True if review should be moderated
        """
        sentiment = cls.analyze_text(text)
        return sentiment < threshold or cls.contains_moderation_words(text)

    @classmethod
    def contains_moderation_words(cls, text):
        """Check if text contains words that should trigger moderation

        Args:
            text (str): Text to check

        Returns:
            bool: True if moderation words found
        """
        if not text:
            return False

        # Clean text - lowercase, remove punctuation
        text_en = text.lower()
        text_en = re.sub(r"[^\w\s]", " ", text_en)
        words_en = text_en.split()

        # Check English moderation words
        for word in words_en:
            if word in cls.MODERATION_WORDS["en"]:
                return True

        # Check Arabic moderation words - no lowercase for Arabic
        text_ar = re.sub(r"[^\w\s]", " ", text)
        words_ar = text_ar.split()

        for word in words_ar:
            if word in cls.MODERATION_WORDS["ar"]:
                return True

        return False
