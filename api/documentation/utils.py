"""
API Documentation Utilities

Common utility functions for working with drf-yasg API documentation.
"""

from drf_yasg import openapi
from typing import List, Dict, Any

from drf_yasg.inspectors import SwaggerAutoSchema
_real_get_operation = SwaggerAutoSchema.get_operation

def debug_get_operation(self, operation_keys=None):
    op = _real_get_operation(self, operation_keys)
    try:
        print("\n==== YASG DEBUG: Endpoint:", getattr(self.view, '__class__', type(self.view)).__name__)
        if hasattr(op, "parameters"):
            names = [(getattr(p, "name", None), getattr(p, "in_", None)) for p in op.parameters]
            print("OpenAPI params for", getattr(self.view, '__class__', type(self.view)).__name__, ":", names)
        else:
            print("No op.parameters for", getattr(self.view, '__class__', type(self.view)).__name__)
    except Exception as e:
        print("DEBUG ERROR", e)
    return op

SwaggerAutoSchema.get_operation = debug_get_operation
print("Swagger debug patch applied (views file)")


def dedupe_manual_parameters(params: List[openapi.Parameter]) -> List[openapi.Parameter]:
    """
    Remove duplicate openapi.Parameters by (name, in_) tuple.

    This helps avoid the "duplicate Parameters found" error in drf_yasg.

    Args:
        params: List of openapi.Parameter objects

    Returns:
        Deduplicated list of parameters
    """
    if not params:
        return []

    seen = set()
    deduped = []

    for p in params:
        key = (getattr(p, "name", None), getattr(p, "in_", None))
        if key not in seen:
            deduped.append(p)
            seen.add(key)

    return deduped


def dedupe_operation_params(operation: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    Deduplicate parameters in a Swagger operation before schema validation.

    This function is intended to be used with the
    FUNCTION_TO_APPLY_BEFORE_SWAGGER_SCHEMA_VALIDATION setting in SWAGGER_SETTINGS.

    Args:
        operation: The Swagger operation object (dict)
        **kwargs: Additional arguments passed by drf_yasg

    Returns:
        The operation with deduplicated parameters
    """
    if 'parameters' in operation and operation['parameters']:
        param_ids = set()
        unique_params = []
        for param in operation['parameters']:
            param_id = (param.get('name'), param.get('in'))
            if param_id not in param_ids:
                param_ids.add(param_id)
                unique_params.append(param)
        operation['parameters'] = unique_params
    return operation

# END OF FILE
