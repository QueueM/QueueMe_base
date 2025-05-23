"""
API Documentation Utilities
Common utility functions for working with drf-yasg API documentation.
"""

from typing import Any, Dict, List
from drf_yasg import openapi
from drf_yasg.inspectors import SwaggerAutoSchema
import logging

logger = logging.getLogger(__name__)

# Store the original get_operation for debugging
_real_get_operation = SwaggerAutoSchema.get_operation


def debug_get_operation(self, operation_keys=None):
    """Enhanced get_operation with better error handling"""
    try:
        op = _real_get_operation(self, operation_keys)
        
        # Debug logging
        view_name = getattr(self.view, "__class__", type(self.view)).__name__
        if hasattr(self.view, 'action'):
            view_name = f"{view_name}.{self.view.action}"
            
        logger.debug(f"Processing operation for view: {view_name}")
        
        # Deduplicate parameters if they exist
        if hasattr(op, "parameters") and op.parameters:
            seen = set()
            unique_params = []
            
            for param in op.parameters:
                param_name = getattr(param, "name", None)
                param_in = getattr(param, "in_", None)
                param_id = (param_name, param_in)
                
                if param_id not in seen and None not in param_id:
                    seen.add(param_id)
                    unique_params.append(param)
                else:
                    logger.debug(f"Removed duplicate parameter: {param_id} in {view_name}")
                    
            op.parameters = unique_params
            logger.debug(f"Final parameters for {view_name}: {[(getattr(p, 'name', None), getattr(p, 'in_', None)) for p in unique_params]}")
            
        return op
        
    except Exception as e:
        logger.error(f"Error in get_operation for {getattr(self.view, '__class__', 'UnknownView')}: {e}", exc_info=True)
        # Return a minimal operation to prevent complete failure
        from drf_yasg.openapi import Operation
        return Operation(
            operation_id=f"fallback_{operation_keys[-1] if operation_keys else 'unknown'}",
            responses={"200": "Success", "500": "Server Error"},
            tags=["API"],
        )


# Apply the debug patch only if not already applied
if not hasattr(SwaggerAutoSchema.get_operation, '_is_patched'):
    SwaggerAutoSchema.get_operation = debug_get_operation
    SwaggerAutoSchema.get_operation._is_patched = True
    logger.info("Swagger debug patch applied")


def dedupe_manual_parameters(
    params: List[openapi.Parameter],
) -> List[openapi.Parameter]:
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
        param_name = getattr(p, "name", None)
        param_in = getattr(p, "in_", None)
        key = (param_name, param_in)
        
        if key not in seen and None not in key:
            deduped.append(p)
            seen.add(key)
        elif key in seen:
            logger.debug(f"Removed duplicate parameter: {key}")
            
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
    try:
        if "parameters" in operation and operation["parameters"]:
            param_ids = set()
            unique_params = []
            
            for param in operation["parameters"]:
                param_id = (param.get("name"), param.get("in"))
                if param_id not in param_ids and None not in param_id:
                    param_ids.add(param_id)
                    unique_params.append(param)
                else:
                    logger.debug(f"Deduplicated parameter in operation: {param_id}")
                    
            operation["parameters"] = unique_params
            
            # Log the operation for debugging
            operation_id = operation.get("operationId", "unknown")
            logger.debug(f"Processed operation '{operation_id}' with {len(unique_params)} unique parameters")
            
    except Exception as e:
        logger.error(f"Error in dedupe_operation_params: {e}", exc_info=True)
        
    return operation


# Additional utility functions for schema generation

def merge_parameters(base_params: List[openapi.Parameter], 
                    additional_params: List[openapi.Parameter]) -> List[openapi.Parameter]:
    """
    Merge two lists of parameters, avoiding duplicates.
    
    Args:
        base_params: Base list of parameters
        additional_params: Additional parameters to merge
        
    Returns:
        Merged list without duplicates
    """
    all_params = list(base_params) + list(additional_params)
    return dedupe_manual_parameters(all_params)


def create_response_schema(description: str, schema=None, examples=None):
    """
    Create a response schema for drf_yasg.
    
    Args:
        description: Description of the response
        schema: Optional schema for the response body
        examples: Optional examples
        
    Returns:
        Response configuration for swagger_auto_schema
    """
    response = openapi.Response(description=description)
    
    if schema:
        response.schema = schema
        
    if examples:
        response.examples = examples
        
    return response

# END OF FILE
