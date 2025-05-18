class SwaggerSchemaMixin:
    """
    Mixin to handle Swagger schema generation properly.
    Apply this to ViewSets that have user_type checks.
    """

    def get_queryset(self):
        # Check if this is a schema generation request
        if getattr(self, "swagger_fake_view", False):
            # Return empty queryset for swagger schema generation
            return self.queryset.model.objects.none()

        # Get the original queryset using normal logic
        return super().get_queryset()
