import uuid

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from utils.validators import validate_image_size


class Category(models.Model):
    """
    Category model with parent-child hierarchical structure.
    Parent categories can have multiple child categories.
    Services are associated with child categories, not parent categories.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Canonical name + four multilingual fields with safe defaults
    name = models.CharField(_("Name"), max_length=100)
    name_en = models.CharField(
        _("Name (English)"),
        max_length=100,
        blank=True,
        default="",
        help_text=_("Optional. Falls back to `name` if empty."),
    )
    name_ar = models.CharField(
        _("Name (Arabic)"),
        max_length=100,
        blank=True,
        default="",
        help_text=_("Optional. Falls back to `name` if empty."),
    )

    description = models.TextField(_("Description"), blank=True)
    description_en = models.TextField(
        _("Description (English)"),
        blank=True,
        default="",
        help_text=_("Optional English description."),
    )
    description_ar = models.TextField(
        _("Description (Arabic)"),
        blank=True,
        default="",
        help_text=_("Optional Arabic description."),
    )

    slug = models.SlugField(
        _("Slug"),
        max_length=120,
        unique=True,
        allow_unicode=True,
        blank=True,
        default="",
        help_text=_("Auto-generated from name if blank."),
    )

    icon = models.ImageField(
        _("Icon"),
        upload_to="categories/icons/",
        blank=True,
        null=True,
        validators=[validate_image_size],
    )
    image = models.ImageField(
        _("Image"),
        upload_to="categories/images/",
        blank=True,
        null=True,
        validators=[validate_image_size],
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name=_("Parent Category"),
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(_("Active"), default=True)
    is_featured = models.BooleanField(_("Featured"), default=False)
    position = models.PositiveIntegerField(
        _("Position"), default=0, help_text=_("Display order position")
    )

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["position", "name"]
        indexes = [
            models.Index(fields=["parent"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_featured"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.name} ({self.parent.name})"
        return self.name

    def save(self, *args, **kwargs):
        # Auto-slugify from `name` if blank
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)

        # Ensure fallbacks: if someone clears name_en/name_ar, copy from `name` on save
        if not self.name_en:
            self.name_en = self.name
        if not self.name_ar:
            self.name_ar = self.name

        # Likewise for descriptions
        if not self.description_en and self.description:
            self.description_en = self.description
        if not self.description_ar and self.description:
            self.description_ar = self.description

        super().save(*args, **kwargs)

    @property
    def is_parent(self):
        return self.parent is None

    @property
    def is_child(self):
        return self.parent is not None

    @property
    def service_count(self):
        if self.is_child:
            return self.services.count()
        return sum(child.services.count() for child in self.children.all())

    @property
    def specialist_count(self):
        if self.is_child:
            specialists = {
                s.id for svc in self.services.all() for s in svc.specialists.all()
            }
            return len(specialists)
        specialists = set()
        for child in self.children.all():
            for svc in child.services.all():
                specialists.update({s.id for s in svc.specialists.all()})
        return len(specialists)

    def get_all_children(self):
        all_children = []
        for child in self.children.all():
            all_children.append(child)
            all_children.extend(child.get_all_children())
        return all_children

    def get_parent_hierarchy(self):
        hierarchy = []
        current = self
        while current.parent:
            hierarchy.append(current.parent)
            current = current.parent
        return hierarchy[::-1]  # From root → this category


class CategoryRelation(models.Model):
    """
    Additional relations between categories.
    Can be used to create related/similar category connections
    that aren't strictly parent-child.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="related_from",
        verbose_name=_("From Category"),
    )
    to_category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="related_to",
        verbose_name=_("To Category"),
    )
    relation_type = models.CharField(
        _("Relation Type"),
        max_length=50,
        default="related",
        help_text=_('Type of relationship (e.g., "related", "similar", "alternative")'),
    )
    weight = models.FloatField(
        _("Weight"),
        default=1.0,
        help_text=_("Strength of the relationship (higher = stronger)"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Category Relation")
        verbose_name_plural = _("Category Relations")
        unique_together = ("from_category", "to_category", "relation_type")

    def __str__(self):
        return f"{self.from_category} → {self.to_category} ({self.relation_type})"
