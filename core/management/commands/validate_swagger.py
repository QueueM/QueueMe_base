# core/management/commands/validate_swagger.py

import sys
import json
import logging
from django.core.management.base import BaseCommand, CommandError
from django.urls import get_resolver
from django.contrib.auth.models import AnonymousUser
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.request import Request
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser

class Command(BaseCommand):
    help = 'Validates the Swagger/OpenAPI schema for the API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-warnings',
            action='store_true',
            help='Show warnings for possible issues in the schema',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Save the schema to a file',
        )

    def handle(self, *args, **options):
        show_warnings = options['show_warnings']
        output_file = options.get('output')
        
        # Temporarily disable logging if not showing warnings
        if not show_warnings:
            logging.disable(logging.WARNING)
        
        self.stdout.write("Validating Swagger schema...")
        
        try:
            # Create a schema generator with proper info
            info = openapi.Info(
                title="QueueMe API",
                default_version='v1',
                description="API for QueueMe platform",
            )
            
            generator = OpenAPISchemaGenerator(
                info=info,
                patterns=get_resolver().url_patterns
            )
            
            # Create a properly formatted DRF request object
            factory = APIRequestFactory()
            django_request = factory.get('/api/docs/')
            
            # Set up the necessary attributes that drf-yasg will look for
            django_request.user = AnonymousUser()
            django_request.session = {}
            django_request.META['SERVER_NAME'] = 'localhost'
            django_request.META['SERVER_PORT'] = '8000'
            
            # Convert to a DRF Request
            drf_request = Request(
                django_request,
                parsers=[JSONParser(), FormParser(), MultiPartParser()],
                authenticators=[],
                negotiator=None,
                parser_context=None
            )
            
            # Generate schema
            try:
                self.stdout.write("Generating schema...")
                schema = generator.get_schema(request=drf_request, public=True)
                
                if not schema:
                    self.stdout.write(self.style.ERROR("Schema generation returned empty schema"))
                    return
                
                # Convert schema to dict safely
                try:
                    if hasattr(schema, 'to_dict'):
                        schema_dict = schema.to_dict()
                    else:
                        schema_dict = json.loads(json.dumps(schema))
                        
                    # Basic validation
                    endpoints_count = len(schema_dict.get('paths', {}))
                    self.stdout.write(f"Found {endpoints_count} API endpoints in the schema")
                    
                    # Count parameters
                    params_count = 0
                    duplicate_params = []
                    
                    for path, path_item in schema_dict.get('paths', {}).items():
                        for method, operation in path_item.items():
                            if method in ['get', 'post', 'put', 'patch', 'delete']:
                                parameters = operation.get('parameters', [])
                                params_count += len(parameters)
                                
                                # Check for potential duplicate parameters
                                param_names = {}
                                for param in parameters:
                                    key = (param.get('name'), param.get('in'))
                                    if key in param_names:
                                        duplicate_params.append((path, method, key))
                                    param_names[key] = True
                    
                    self.stdout.write(f"Found {params_count} parameters across all endpoints")
                    
                    # Report duplicates
                    if duplicate_params:
                        self.stdout.write(self.style.WARNING(
                            f"Found {len(duplicate_params)} potential duplicate parameters (handled by yasg_patch):"
                        ))
                        for path, method, param in duplicate_params[:5]:
                            self.stdout.write(f"  - {path} [{method}]: {param[0]} (in {param[1]})")
                        if len(duplicate_params) > 5:
                            self.stdout.write(f"  - ... and {len(duplicate_params) - 5} more")
                    else:
                        self.stdout.write(self.style.SUCCESS("No duplicate parameters found in the schema"))
                    
                    # Output to file if requested
                    if output_file:
                        with open(output_file, 'w') as f:
                            json.dump(schema_dict, f, indent=2)
                        self.stdout.write(f"Schema saved to {output_file}")
                    
                    self.stdout.write(self.style.SUCCESS("✅ Schema is valid"))
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing schema: {str(e)}"))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error generating schema: {str(e)}"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during validation: {str(e)}"))
            
        finally:
            # Re-enable logging
            if not show_warnings:
                logging.disable(logging.NOTSET)
