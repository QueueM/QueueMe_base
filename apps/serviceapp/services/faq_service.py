from django.db import models

from apps.serviceapp.models import Service, ServiceFAQ


class FAQService:
    """Service for managing service FAQs"""

    @staticmethod
    def create_faq(service_id, question, answer, order=None):
        """Create a new FAQ for a service"""
        service = Service.objects.get(id=service_id)

        # If order not provided, put at the end
        if order is None:
            max_order = (
                ServiceFAQ.objects.filter(service=service).aggregate(
                    max_order=models.Max("order")
                )["max_order"]
                or 0
            )
            order = max_order + 1

        faq = ServiceFAQ.objects.create(
            service=service, question=question, answer=answer, order=order
        )

        return faq

    @staticmethod
    def update_faq(faq_id, question=None, answer=None, order=None):
        """Update an existing FAQ"""
        faq = ServiceFAQ.objects.get(id=faq_id)

        if question is not None:
            faq.question = question

        if answer is not None:
            faq.answer = answer

        if order is not None:
            faq.order = order

        faq.save()
        return faq

    @staticmethod
    def delete_faq(faq_id):
        """Delete a FAQ"""
        faq = ServiceFAQ.objects.get(id=faq_id)
        faq.delete()
        return True

    @staticmethod
    def reorder_faqs(service_id, faq_order):
        """
        Reorder FAQs for a service

        faq_order: List of FAQ IDs in the desired order
        """
        service = Service.objects.get(id=service_id)

        # Verify all FAQs belong to this service
        faqs = set(
            ServiceFAQ.objects.filter(service=service).values_list("id", flat=True)
        )
        if not all(str(faq_id) in faqs for faq_id in faq_order):
            raise ValueError("All FAQ IDs must belong to this service")

        # Update order
        for i, faq_id in enumerate(faq_order):
            ServiceFAQ.objects.filter(id=faq_id).update(order=i)

        return True

    @staticmethod
    def copy_faqs_from_service(source_service_id, target_service_id):
        """
        Copy all FAQs from one service to another

        Useful when creating a new service similar to an existing one
        """
        source_service = Service.objects.get(id=source_service_id)
        target_service = Service.objects.get(id=target_service_id)

        # Get all FAQs from source service
        source_faqs = ServiceFAQ.objects.filter(service=source_service)

        # Create new FAQs for target service
        new_faqs = []
        for faq in source_faqs:
            new_faq = ServiceFAQ(
                service=target_service,
                question=faq.question,
                answer=faq.answer,
                order=faq.order,
            )
            new_faqs.append(new_faq)

        # Bulk create
        if new_faqs:
            ServiceFAQ.objects.bulk_create(new_faqs)

        return len(new_faqs)

    @staticmethod
    def analyze_common_questions(category_id=None, min_occurrences=3):
        """
        Analyze FAQs across services to find common questions

        This can be used to suggest FAQs for new services
        """
        from fuzzywuzzy import fuzz

        # Get all FAQs, optionally filtered by category
        query = ServiceFAQ.objects.all()
        if category_id:
            query = query.filter(service__category_id=category_id)

        all_faqs = query.values("question", "answer")

        # Group similar questions (using fuzzy matching)
        question_groups = {}

        for faq in all_faqs:
            question = faq["question"]
            answer = faq["answer"]

            # Check if this question is similar to any existing group
            matched = False
            for group_key in question_groups:
                # If similarity is above threshold, consider it the same question
                if fuzz.ratio(question.lower(), group_key.lower()) > 80:
                    question_groups[group_key]["count"] += 1
                    question_groups[group_key]["answers"].append(answer)
                    matched = True
                    break

            # If no match, create a new group
            if not matched:
                question_groups[question] = {"count": 1, "answers": [answer]}

        # Filter to questions that appear at least min_occurrences times
        common_questions = {}
        for question, data in question_groups.items():
            if data["count"] >= min_occurrences:
                # For questions with multiple answers, find most common
                from collections import Counter

                answer_counter = Counter(data["answers"])
                most_common_answer = answer_counter.most_common(1)[0][0]

                common_questions[question] = {
                    "count": data["count"],
                    "suggested_answer": most_common_answer,
                }

        # Sort by occurrence count
        return sorted(
            [{"question": q, **data} for q, data in common_questions.items()],
            key=lambda x: x["count"],
            reverse=True,
        )
