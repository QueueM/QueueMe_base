from django.core.management.base import BaseCommand
from django.apps import apps
from django.urls import get_resolver, URLPattern, URLResolver
import os
import json
from pathlib import Path
from endpoint_registry import get_all_endpoints

class Command(BaseCommand):
    help = 'Generate comprehensive API documentation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='static/api_docs',
            help='Output directory for documentation files',
        )

    def handle(self, *args, **options):
        output_dir = options['output']
        self.stdout.write(f"Generating API documentation in {output_dir}")
        
        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get all endpoints
        endpoints = get_all_endpoints()
        
        # Group endpoints by app
        apps = {}
        for endpoint in endpoints:
            app_name = endpoint['app']
            if app_name not in apps:
                apps[app_name] = {
                    'name': endpoint['app_name'],
                    'endpoints': []
                }
            apps[app_name]['endpoints'].append(endpoint)
        
        # Write JSON data
        with open(f"{output_dir}/api_data.json", 'w') as f:
            json.dump({
                'apps': apps,
                'endpoints': endpoints
            }, f, indent=2)
        
        # Generate index.html
        self._generate_index_html(output_dir, apps)
        
        # Generate app pages
        for app_name, app_info in apps.items():
            self._generate_app_html(output_dir, app_name, app_info)
        
        self.stdout.write(self.style.SUCCESS(f"API documentation generated successfully in {output_dir}"))
    
    def _generate_index_html(self, output_dir, apps):
        """Generate the main index.html file"""
        with open(f"{output_dir}/index.html", 'w') as f:
            f.write("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QueueMe API Documentation</title>
    <link rel="stylesheet" href="/static/css/api_docs.css">
</head>
<body>
    <header class="api-header">
        <div class="api-container">
            <h1>QueueMe API Documentation</h1>
            <p>Complete API reference for developers</p>
        </div>
    </header>
    
    <nav class="api-nav">
        <div class="api-container">
            <ul>
                <li><a href="#overview" class="active">Overview</a></li>
            """)
            
            # Add app links
            for app_name, app_info in sorted(apps.items(), key=lambda x: x[1]['name']):
                f.write(f'<li><a href="/{app_name}.html">{app_info["name"]}</a></li>\n')
            
            f.write("""
            </ul>
        </div>
    </nav>
    
    <main class="api-container">
        <section id="overview">
            <h2>API Overview</h2>
            <p>The QueueMe API provides programmatic access to all QueueMe functionality. This documentation covers all available endpoints.</p>
            
            <h3>Base URL</h3>
            <pre><code>https://api.queueme.net/api</code></pre>
            
            <h3>Authentication</h3>
            <p>Most API endpoints require authentication using JWT tokens. To obtain a token, use the <code>/api/auth/token/</code> endpoint.</p>
            
            <h3>Available APIs</h3>
            <ul>
            """)
            
            # Add app list
            for app_name, app_info in sorted(apps.items(), key=lambda x: x[1]['name']):
                endpoint_count = len(app_info['endpoints'])
                f.write(f'<li><a href="/{app_name}.html">{app_info["name"]}</a> - {endpoint_count} endpoints</li>\n')
            
            f.write("""
            </ul>
        </section>
    </main>
    
    <footer class="api-footer">
        <div class="api-container">
            <p>&copy; 2023 QueueMe. All rights reserved.</p>
        </div>
    </footer>
    
    <script>
        // Add smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                document.querySelector(this.getAttribute('href')).scrollIntoView({
                    behavior: 'smooth'
                });
            });
        });
    </script>
</body>
</html>
            """)
    
    def _generate_app_html(self, output_dir, app_name, app_info):
        """Generate an HTML page for a single app"""
        with open(f"{output_dir}/{app_name}.html", 'w') as f:
            f.write(f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{app_info['name']} API - QueueMe Documentation</title>
    <link rel="stylesheet" href="/static/css/api_docs.css">
</head>
<body>
    <header class="api-header">
        <div class="api-container">
            <h1>{app_info['name']} API</h1>
            <p>QueueMe {app_info['name']} endpoints</p>
        </div>
    </header>
    
    <nav class="api-nav">
        <div class="api-container">
            <ul>
                <li><a href="/index.html">Overview</a></li>
            """)
            
            # Add app links
            for other_app_name, other_app_info in sorted(apps.items(), key=lambda x: x[1]['name']):
                active = 'class="active"' if other_app_name == app_name else ''
                f.write(f'<li><a href="/{other_app_name}.html" {active}>{other_app_info["name"]}</a></li>\n')
            
            f.write("""
            </ul>
        </div>
    </nav>
    
    <main class="api-container">
        <div class="api-content">
            <h2>Endpoints</h2>
            
            <div class="endpoints-list">
            """)
            
            # Group endpoints by path pattern
            path_groups = {}
            for endpoint in app_info['endpoints']:
                path_base = endpoint['path'].split('/{')[0]
                if path_base not in path_groups:
                    path_groups[path_base] = []
                path_groups[path_base].append(endpoint)
            
            # Output endpoints by group
            for path_base, endpoints in sorted(path_groups.items()):
                f.write(f'<h3 class="endpoint-group">{path_base}</h3>\n')
                
                for endpoint in sorted(endpoints, key=lambda x: x['method']):
                    method_class = endpoint['method'].lower()
                    f.write(f"""
                    <div class="endpoint {method_class}">
                        <div class="endpoint-header">
                            <span class="method {method_class}">{endpoint['method']}</span>
                            <span class="endpoint-path">{endpoint['path']}</span>
                        </div>
                        <div class="endpoint-description">
                            <p>{endpoint['description']}</p>
                        </div>
                    """)
                    
                    # Parameters
                    if endpoint.get('parameters'):
                        f.write("""
                        <div class="endpoint-params">
                            <h4>Parameters</h4>
                            <table>
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Type</th>
                                        <th>Required</th>
                                        <th>Description</th>
                                    </tr>
                                </thead>
                                <tbody>
                        """)
                        
                        for param in endpoint['parameters']:
                            required = 'Yes' if param.get('required', False) else 'No'
                            in_path = "Path" if param.get('in_path', False) else "Query"
                            f.write(f"""
                            <tr>
                                <td><code>{param['name']}</code></td>
                                <td>{param['type']}</td>
                                <td>{required} ({in_path})</td>
                                <td>{param['description']}</td>
                            </tr>
                            """)
                        
                        f.write("""
                                </tbody>
                            </table>
                        </div>
                        """)
                    
                    # Responses
                    if endpoint.get('responses'):
                        f.write("""
                        <div class="endpoint-responses">
                            <h4>Responses</h4>
                            <table>
                                <thead>
                                    <tr>
                                        <th>Code</th>
                                        <th>Description</th>
                                    </tr>
                                </thead>
                                <tbody>
                        """)
                        
                        for response in endpoint['responses']:
                            f.write(f"""
                            <tr>
                                <td><code>{response['code']}</code></td>
                                <td>{response['description']}</td>
                            </tr>
                            """)
                        
                        f.write("""
                                </tbody>
                            </table>
                        </div>
                        """)
                    
                    # Example request
                    if endpoint.get('example_request'):
                        f.write(f"""
                        <div class="endpoint-example">
                            <h4>Example Request</h4>
                            <pre><code>{endpoint['example_request']}</code></pre>
                        </div>
                        """)
                    
                    # Example response
                    if endpoint.get('example_response'):
                        f.write(f"""
                        <div class="endpoint-example">
                            <h4>Example Response</h4>
                            <pre><code>{endpoint['example_response']}</code></pre>
                        </div>
                        """)
                    
                    f.write("</div>\n")  # Close endpoint div
                
            f.write("""
            </div>
        </div>
    </main>
    
    <footer class="api-footer">
        <div class="api-container">
            <p>&copy; 2023 QueueMe. All rights reserved.</p>
        </div>
    </footer>
    
    <script>
        // Add smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                document.querySelector(this.getAttribute('href')).scrollIntoView({
                    behavior: 'smooth'
                });
            });
        });
    </script>
</body>
</html>
            """)
