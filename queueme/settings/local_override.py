"""
Local override settings that take precedence over all other settings.
"""

# Explicitly set allowed hosts with no conditions
ALLOWED_HOSTS = [
    "queueme.net", 
    "www.queueme.net", 
    "shop.queueme.net", 
    "admin.queueme.net", 
    "api.queueme.net",
    "localhost",
    "127.0.0.1"
]
