"""
Cache key generation utilities for the Queue Me platform.

This module provides functions to generate and manage cache keys.
"""

import hashlib
import json


def secure_hash(data, length=16, used_for_security=False):
    """
    Create a secure hash of data using SHA-256

    Args:
        data: String or bytes to hash
        length: Length of the resulting hash digest to return (truncated)
        used_for_security: Whether this hash is used for security purposes

    Returns:
        Truncated hexadecimal digest
    """
    if isinstance(data, str):
        data = data.encode()

    # Use SHA-256 for better security
    hash_func = hashlib.sha256(data, usedforsecurity=used_for_security)
    return hash_func.hexdigest()[:length]


def generate_cache_key(key, namespace=None, version=None):
    """
    Generate a standardized cache key.

    Args:
        key (str): Base cache key
        namespace (str): Optional namespace
        version (str): Optional version

    Returns:
        str: Formatted cache key
    """
    if isinstance(key, dict):
        # Sort the dictionary to ensure consistent keys
        serialized = json.dumps(key, sort_keys=True)
        # Use a hash to keep the key length manageable
        key = secure_hash(serialized.encode())

    parts = []
    if namespace:
        parts.append(namespace)

    parts.append(str(key))

    if version:
        parts.append(f"v{version}")

    return ":".join(parts)


def generate_model_cache_key(model_instance, field=None, prefix=None):
    """
    Generate a cache key for a model instance.

    Args:
        model_instance: Django model instance
        field (str): Optional field to include in key
        prefix (str): Optional prefix for the key

    Returns:
        str: Cache key for the model instance
    """
    model_name = model_instance.__class__.__name__.lower()
    instance_id = str(model_instance.pk)

    parts = []
    if prefix:
        parts.append(prefix)

    parts.append(model_name)
    parts.append(instance_id)

    if field:
        parts.append(field)

    return ":".join(parts)


def generate_queryset_cache_key(model_class, query_params=None, prefix=None):
    """
    Generate a cache key for a queryset.

    Args:
        model_class: Django model class
        query_params (dict): Query parameters
        prefix (str): Optional prefix for the key

    Returns:
        str: Cache key for the queryset
    """
    model_name = model_class.__name__.lower()

    parts = []
    if prefix:
        parts.append(prefix)

    parts.append(f"{model_name}_list")

    if query_params:
        # Convert query params to a stable string representation
        params_str = json.dumps(query_params, sort_keys=True)
        # Use a hash to keep the key length manageable
        params_hash = secure_hash(params_str.encode())
        parts.append(params_hash)

    return ":".join(parts)


def get_per_user_cache_key(user_id, base_key):
    """
    Generate a cache key specific to a user.

    Args:
        user_id (str): User ID
        base_key (str): Base cache key

    Returns:
        str: User-specific cache key
    """
    return f"user:{user_id}:{base_key}"


def get_language_specific_cache_key(base_key, language_code):
    """
    Generate a language-specific cache key.

    Args:
        base_key (str): Base cache key
        language_code (str): Language code (e.g., 'en', 'ar')

    Returns:
        str: Language-specific cache key
    """
    return f"{base_key}:lang:{language_code}"
