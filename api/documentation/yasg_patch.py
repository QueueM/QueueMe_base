"""
Enhanced patches for drf_yasg to fix duplicate parameter issues
and make schema generation more robust.
"""

import logging
from collections import OrderedDict
from drf_yasg.inspectors import SwaggerAutoSchema

logger = logging.getLogger(__name__)

# Monkey patch the param_list_to_odict function in drf_yasg.utils
from drf_yasg.utils import param_list_to_odict as original_param_list_to_odict

def patched_param_list_to_odict(parameters):
    """
    A more robust version of param_list_to_odict that doesn't raise an
    exception for duplicate parameters, but instead deduplicates them.
    """
    result = OrderedDict()
    duplicates = []
    
    for param in parameters:
        param_id = (param['in'], param['name'])
        if param_id in result:
            duplicates.append(f"{param['name']} (in {param['in']})")
        else:
            result[param_id] = param
    
    if duplicates:
        logger.warning(f"Deduplicated {len(duplicates)} parameters: {', '.join(duplicates)}")
    
    # No assertion - just return the deduplicated result
    return result

# Apply the monkey patch
import drf_yasg.utils
drf_yasg.utils.param_list_to_odict = patched_param_list_to_odict

# Enhanced SafeSwaggerSchema
class SafeSwaggerSchema(SwaggerAutoSchema):
    """
    Patch SwaggerAutoSchema to make docs generation more robust.
    Prevents errors in get_queryset and other methods.
    """

    def get_queryset(self):
        """Handle errors in get_queryset gracefully."""
        try:
            return super().get_queryset()
        except Exception as e:
            logger.warning(f"Swagger schema error in get_queryset: {e}")
            return []

    def get_operation(self, operation_keys=None):
        """Make get_operation more robust."""
        try:
            op = super().get_operation(operation_keys)
            
            # Additional deduplication of parameters in the operation object itself
            if hasattr(op, "parameters") and op.parameters:
                seen = set()
                unique_params = []
                for param in op.parameters:
                    param_id = (getattr(param, "name", None), getattr(param, "in_", None))
                    if param_id not in seen and None not in param_id:
                        seen.add(param_id)
                        unique_params.append(param)
                op.parameters = unique_params
                
            return op
        except Exception as e:
            logger.warning(f"Swagger schema error in get_operation: {e}")
            from drf_yasg.openapi import Operation
            return Operation(
                operation_id=f"error_operation_{operation_keys[-1] if operation_keys else 'unknown'}",
                responses={},
                tags=["Error"]
            )

print("✅ Applied robust Swagger parameter deduplication patches")
