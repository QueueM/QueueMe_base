"""
Base classes for QueueMe ViewSets with consistent handling of API documentation.

These base classes enforce a consistent approach to parameter handling
and documentation, which prevents duplication issues in OpenAPI schema.
"""

import logging
from rest_framework import viewsets
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from api.documentation.utils import dedupe_manual_parameters

logger = logging.getLogger(__name__)

class QueueMeViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for QueueMe API that properly handles parameter deduplication.
    
    This base class ensures that parameters added by filter backends are not
    duplicated in manual parameter definitions.
    """
    
    # Default filter backends - these add parameters automatically
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    
    @classmethod
    def get_view_parameters(cls, view_func=None, extra_params=None):
        """
        Get parameters for a view function, deduplicating as needed.
        
        Args:
            view_func: The view function being documented (optional)
            extra_params: Additional parameters to include (optional)
            
        Returns:
            List of deduplicated OpenAPI parameter objects
        """
        params = extra_params or []
        
        # Deduplicate parameters using the utility function
        return dedupe_manual_parameters(params)
    
    @classmethod
    def get_list_parameters(cls, extra_params=None):
        """
        Get standard list endpoint parameters (with deduplication).
        
        This is a convenience method for list views that don't need 
        any additional parameters beyond the standard ones.
        
        Args:
            extra_params: Additional parameters to include (optional)
            
        Returns:
            List of deduplicated OpenAPI parameter objects
        """
        # Import here to avoid circular imports
        from api.documentation.parameters import LIST_PARAMETERS
        
        params = LIST_PARAMETERS.copy()
        if extra_params:
            params.extend(extra_params)
            
        return cls.get_view_parameters(extra_params=params)
    
    @classmethod
    def get_detail_parameters(cls, extra_params=None):
        """
        Get standard detail endpoint parameters (with deduplication).
        
        Args:
            extra_params: Additional parameters to include (optional)
            
        Returns:
            List of deduplicated OpenAPI parameter objects
        """
        # Import here to avoid circular imports
        from api.documentation.parameters import UUID_PARAM
        
        params = [UUID_PARAM]
        if extra_params:
            params.extend(extra_params)
            
        return cls.get_view_parameters(extra_params=params)
