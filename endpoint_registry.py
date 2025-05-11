"""
Registry of all API endpoints with their documentation
"""

ENDPOINTS = {
    # Authentication app
    'authapp': {
        'name': 'Authentication',
        'endpoints': [
            {
                'path': '/api/auth/token/',
                'method': 'POST',
                'description': 'Obtain JWT token by providing phone number and password',
                'parameters': [
                    {'name': 'phone', 'type': 'string', 'required': True, 'description': 'Phone number'},
                    {'name': 'password', 'type': 'string', 'required': True, 'description': 'Password'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Token obtained successfully'},
                    {'code': 401, 'description': 'Authentication failed'},
                ],
                'example_request': '{\n  "phone": "966558173151",\n  "password": "your_password"\n}',
                'example_response': '{\n  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",\n  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."\n}'
            },
            {
                'path': '/api/auth/token/refresh/',
                'method': 'POST',
                'description': 'Refresh JWT token',
                'parameters': [
                    {'name': 'refresh', 'type': 'string', 'required': True, 'description': 'Refresh token'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Token refreshed successfully'},
                    {'code': 401, 'description': 'Invalid refresh token'},
                ],
                'example_request': '{\n  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."\n}',
                'example_response': '{\n  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."\n}'
            },
            {
                'path': '/api/auth/register/',
                'method': 'POST',
                'description': 'Register a new user account',
                'parameters': [
                    {'name': 'phone', 'type': 'string', 'required': True, 'description': 'Phone number'},
                    {'name': 'password', 'type': 'string', 'required': True, 'description': 'Password'},
                    {'name': 'password_confirm', 'type': 'string', 'required': True, 'description': 'Password confirmation'},
                    {'name': 'first_name', 'type': 'string', 'required': True, 'description': 'First name'},
                    {'name': 'last_name', 'type': 'string', 'required': True, 'description': 'Last name'},
                    {'name': 'email', 'type': 'string', 'required': False, 'description': 'Email address'},
                ],
                'responses': [
                    {'code': 201, 'description': 'User created successfully'},
                    {'code': 400, 'description': 'Invalid request data'},
                ]
            },
            {
                'path': '/api/auth/verify-otp/',
                'method': 'POST',
                'description': 'Verify OTP for phone verification',
                'parameters': [
                    {'name': 'phone', 'type': 'string', 'required': True, 'description': 'Phone number'},
                    {'name': 'otp', 'type': 'string', 'required': True, 'description': 'OTP code'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Phone verified successfully'},
                    {'code': 400, 'description': 'Invalid OTP'},
                ]
            },
            {
                'path': '/api/auth/send-otp/',
                'method': 'POST',
                'description': 'Send OTP for phone verification',
                'parameters': [
                    {'name': 'phone', 'type': 'string', 'required': True, 'description': 'Phone number'},
                ],
                'responses': [
                    {'code': 200, 'description': 'OTP sent successfully'},
                    {'code': 400, 'description': 'Invalid request'},
                ]
            },
            {
                'path': '/api/auth/reset-password/',
                'method': 'POST',
                'description': 'Reset password using OTP',
                'parameters': [
                    {'name': 'phone', 'type': 'string', 'required': True, 'description': 'Phone number'},
                    {'name': 'otp', 'type': 'string', 'required': True, 'description': 'OTP code'},
                    {'name': 'new_password', 'type': 'string', 'required': True, 'description': 'New password'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Password reset successful'},
                    {'code': 400, 'description': 'Invalid OTP or request'},
                ]
            },
            {
                'path': '/api/auth/profile/',
                'method': 'GET',
                'description': 'Get user profile',
                'responses': [
                    {'code': 200, 'description': 'User profile'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/auth/profile/',
                'method': 'PATCH',
                'description': 'Update user profile',
                'parameters': [
                    {'name': 'first_name', 'type': 'string', 'required': False, 'description': 'First name'},
                    {'name': 'last_name', 'type': 'string', 'required': False, 'description': 'Last name'},
                    {'name': 'email', 'type': 'string', 'required': False, 'description': 'Email address'},
                    {'name': 'avatar', 'type': 'file', 'required': False, 'description': 'Profile picture'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Profile updated successfully'},
                    {'code': 400, 'description': 'Invalid request data'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            }
        ]
    },
    
    # Shop app
    'shopapp': {
        'name': 'Shops',
        'endpoints': [
            {
                'path': '/api/shops/',
                'method': 'GET',
                'description': 'List all shops with pagination and filtering',
                'parameters': [
                    {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number'},
                    {'name': 'page_size', 'type': 'integer', 'required': False, 'description': 'Results per page (max 100)'},
                    {'name': 'search', 'type': 'string', 'required': False, 'description': 'Search by name, description, or username'},
                    {'name': 'ordering', 'type': 'string', 'required': False, 'description': 'Order by field (prefix with - for descending)'},
                    {'name': 'city', 'type': 'string', 'required': False, 'description': 'Filter by city'},
                    {'name': 'is_active', 'type': 'boolean', 'required': False, 'description': 'Filter by active status'},
                    {'name': 'is_verified', 'type': 'boolean', 'required': False, 'description': 'Filter by verification status'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of shops'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/shops/{id}/',
                'method': 'GET',
                'description': 'Retrieve a specific shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Shop details'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/',
                'method': 'POST',
                'description': 'Create a new shop',
                'parameters': [
                    {'name': 'name', 'type': 'string', 'required': True, 'description': 'Shop name'},
                    {'name': 'description', 'type': 'string', 'required': False, 'description': 'Shop description'},
                    {'name': 'company', 'type': 'integer', 'required': True, 'description': 'Company ID'},
                    {'name': 'username', 'type': 'string', 'required': True, 'description': 'Shop username'},
                    {'name': 'logo', 'type': 'file', 'required': False, 'description': 'Shop logo'},
                    {'name': 'cover_image', 'type': 'file', 'required': False, 'description': 'Shop cover image'},
                    {'name': 'phone', 'type': 'string', 'required': True, 'description': 'Shop phone number'},
                    {'name': 'email', 'type': 'string', 'required': False, 'description': 'Shop email'},
                    {'name': 'location_lat', 'type': 'number', 'required': True, 'description': 'Latitude'},
                    {'name': 'location_lng', 'type': 'number', 'required': True, 'description': 'Longitude'},
                    {'name': 'location_address', 'type': 'string', 'required': True, 'description': 'Full address'},
                    {'name': 'location_city', 'type': 'string', 'required': True, 'description': 'City'},
                    {'name': 'location_country', 'type': 'string', 'required': True, 'description': 'Country'},
                ],
                'responses': [
                    {'code': 201, 'description': 'Shop created successfully'},
                    {'code': 400, 'description': 'Invalid request data'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                ]
            },
            {
                'path': '/api/shops/{id}/',
                'method': 'PUT',
                'description': 'Update an existing shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                    {'name': 'name', 'type': 'string', 'required': True, 'description': 'Shop name'},
                    {'name': 'description', 'type': 'string', 'required': False, 'description': 'Shop description'},
                    {'name': 'company', 'type': 'integer', 'required': True, 'description': 'Company ID'},
                    {'name': 'username', 'type': 'string', 'required': True, 'description': 'Shop username'},
                    {'name': 'logo', 'type': 'file', 'required': False, 'description': 'Shop logo'},
                    {'name': 'cover_image', 'type': 'file', 'required': False, 'description': 'Shop cover image'},
                    {'name': 'phone', 'type': 'string', 'required': True, 'description': 'Shop phone number'},
                    {'name': 'email', 'type': 'string', 'required': False, 'description': 'Shop email'},
                    {'name': 'location_lat', 'type': 'number', 'required': True, 'description': 'Latitude'},
                    {'name': 'location_lng', 'type': 'number', 'required': True, 'description': 'Longitude'},
                    {'name': 'location_address', 'type': 'string', 'required': True, 'description': 'Full address'},
                    {'name': 'location_city', 'type': 'string', 'required': True, 'description': 'City'},
                    {'name': 'location_country', 'type': 'string', 'required': True, 'description': 'Country'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Shop updated successfully'},
                    {'code': 400, 'description': 'Invalid request data'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/{id}/',
                'method': 'PATCH',
                'description': 'Partially update an existing shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                    # Any of the fields from PUT can be included as optional
                ],
                'responses': [
                    {'code': 200, 'description': 'Shop updated successfully'},
                    {'code': 400, 'description': 'Invalid request data'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/{id}/',
                'method': 'DELETE',
                'description': 'Delete a shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 204, 'description': 'Shop deleted successfully'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/{id}/request_verification/',
                'method': 'POST',
                'description': 'Request verification for a shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                    {'name': 'documents', 'type': 'array', 'required': False, 'description': 'List of document URLs'},
                ],
                'responses': [
                    {'code': 201, 'description': 'Verification requested successfully'},
                    {'code': 400, 'description': 'Invalid request data or verification already pending'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/{id}/hours/',
                'method': 'GET',
                'description': 'Get working hours for a shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of shop hours'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/{id}/settings/',
                'method': 'GET',
                'description': 'Get settings for a shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Shop settings'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/{id}/update_settings/',
                'method': 'PATCH',
                'description': 'Update settings for a shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                    {'name': 'booking_interval_minutes', 'type': 'integer', 'required': False, 'description': 'Booking interval in minutes'},
                    {'name': 'max_concurrent_bookings', 'type': 'integer', 'required': False, 'description': 'Maximum concurrent bookings'},
                    {'name': 'booking_lead_time_hours', 'type': 'integer', 'required': False, 'description': 'How many hours in advance bookings must be made'},
                    {'name': 'booking_cancellation_hours', 'type': 'integer', 'required': False, 'description': 'How many hours in advance bookings can be cancelled'},
                    {'name': 'auto_confirm_bookings', 'type': 'boolean', 'required': False, 'description': 'Automatically confirm bookings'},
                    {'name': 'enable_notifications', 'type': 'boolean', 'required': False, 'description': 'Enable notifications'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Settings updated successfully'},
                    {'code': 400, 'description': 'Invalid request data'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/{id}/statistics/',
                'method': 'GET',
                'description': 'Get statistics for a shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Shop statistics'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/nearby/',
                'method': 'GET',
                'description': 'Get shops near a location',
                'parameters': [
                    {'name': 'lat', 'type': 'number', 'required': False, 'description': 'Latitude'},
                    {'name': 'lng', 'type': 'number', 'required': False, 'description': 'Longitude'},
                    {'name': 'radius', 'type': 'number', 'required': False, 'description': 'Search radius in km (default: 10)'},
                    {'name': 'category_id', 'type': 'integer', 'required': False, 'description': 'Filter by category ID'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of nearby shops'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/shops/top/',
                'method': 'GET',
                'description': 'Get top-rated shops',
                'parameters': [
                    {'name': 'category_id', 'type': 'integer', 'required': False, 'description': 'Filter by category ID'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of top shops'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/shops/followed/',
                'method': 'GET',
                'description': 'Get shops followed by the authenticated user',
                'responses': [
                    {'code': 200, 'description': 'List of followed shops'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/shops/{id}/follow/',
                'method': 'POST',
                'description': 'Follow a shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Shop followed successfully'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied (only customers can follow shops)'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            },
            {
                'path': '/api/shops/{id}/unfollow/',
                'method': 'POST',
                'description': 'Unfollow a shop',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Shop ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Shop unfollowed successfully'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied (only customers can unfollow shops)'},
                    {'code': 404, 'description': 'Shop not found'},
                ]
            }
        ]
    },
    
    # Specialist app
    'specialistsapp': {
        'name': 'Specialists',
        'endpoints': [
            {
                'path': '/api/specialists/',
                'method': 'GET',
                'description': 'List all specialists',
                'parameters': [
                    {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number'},
                    {'name': 'page_size', 'type': 'integer', 'required': False, 'description': 'Results per page (max 100)'},
                    {'name': 'search', 'type': 'string', 'required': False, 'description': 'Search by name'},
                    {'name': 'shop_id', 'type': 'integer', 'required': False, 'description': 'Filter by shop ID'},
                    {'name': 'service_id', 'type': 'integer', 'required': False, 'description': 'Filter by service ID'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of specialists'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/specialists/{id}/',
                'method': 'GET',
                'description': 'Retrieve a specific specialist',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Specialist ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Specialist details'},
                    {'code': 404, 'description': 'Specialist not found'},
                ]
            },
            {
                'path': '/api/specialists/{id}/services/',
                'method': 'GET',
                'description': 'List services offered by a specialist',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Specialist ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of services'},
                    {'code': 404, 'description': 'Specialist not found'},
                ]
            },
            {
                'path': '/api/specialists/{id}/availability/',
                'method': 'GET',
                'description': 'Get availability for a specialist',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Specialist ID', 'in_path': True},
                    {'name': 'date', 'type': 'string', 'required': False, 'description': 'Date (YYYY-MM-DD)'},
                    {'name': 'from_date', 'type': 'string', 'required': False, 'description': 'Start date (YYYY-MM-DD)'},
                    {'name': 'to_date', 'type': 'string', 'required': False, 'description': 'End date (YYYY-MM-DD)'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Availability slots'},
                    {'code': 404, 'description': 'Specialist not found'},
                ]
            }
        ]
    },
    
    # Service app
    'serviceapp': {
        'name': 'Services',
        'endpoints': [
            {
                'path': '/api/services/',
                'method': 'GET',
                'description': 'List all services',
                'parameters': [
                    {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number'},
                    {'name': 'page_size', 'type': 'integer', 'required': False, 'description': 'Results per page (max 100)'},
                    {'name': 'search', 'type': 'string', 'required': False, 'description': 'Search by name or description'},
                    {'name': 'shop_id', 'type': 'integer', 'required': False, 'description': 'Filter by shop ID'},
                    {'name': 'category_id', 'type': 'integer', 'required': False, 'description': 'Filter by category ID'},
                    {'name': 'min_price', 'type': 'number', 'required': False, 'description': 'Minimum price'},
                    {'name': 'max_price', 'type': 'number', 'required': False, 'description': 'Maximum price'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of services'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/services/{id}/',
                'method': 'GET',
                'description': 'Retrieve a specific service',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Service ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Service details'},
                    {'code': 404, 'description': 'Service not found'},
                ]
            },
            {
                'path': '/api/services/categories/',
                'method': 'GET',
                'description': 'List all service categories',
                'parameters': [
                    {'name': 'parent_id', 'type': 'integer', 'required': False, 'description': 'Filter by parent category ID'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of service categories'},
                ]
            }
        ]
    },
    
    # Booking app
    'bookingapp': {
        'name': 'Bookings',
        'endpoints': [
            {
                'path': '/api/bookings/',
                'method': 'GET',
                'description': 'List bookings for the authenticated user',
                'parameters': [
                    {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number'},
                    {'name': 'page_size', 'type': 'integer', 'required': False, 'description': 'Results per page (max 100)'},
                    {'name': 'status', 'type': 'string', 'required': False, 'description': 'Filter by status (scheduled, confirmed, completed, cancelled)'},
                    {'name': 'from_date', 'type': 'string', 'required': False, 'description': 'Filter by start date (YYYY-MM-DD)'},
                    {'name': 'to_date', 'type': 'string', 'required': False, 'description': 'Filter by end date (YYYY-MM-DD)'},
                    {'name': 'shop_id', 'type': 'integer', 'required': False, 'description': 'Filter by shop ID'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of bookings'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/bookings/',
                'method': 'POST',
                'description': 'Create a new booking',
                'parameters': [
                    {'name': 'shop_id', 'type': 'integer', 'required': True, 'description': 'Shop ID'},
                    {'name': 'service_id', 'type': 'integer', 'required': True, 'description': 'Service ID'},
                    {'name': 'specialist_id', 'type': 'integer', 'required': True, 'description': 'Specialist ID'},
                    {'name': 'start_time', 'type': 'string', 'required': True, 'description': 'Start time (ISO format)'},
                    {'name': 'notes', 'type': 'string', 'required': False, 'description': 'Booking notes'},
                ],
                'responses': [
                    {'code': 201, 'description': 'Booking created successfully'},
                    {'code': 400, 'description': 'Invalid request data or time slot not available'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/bookings/{id}/',
                'method': 'GET',
                'description': 'Retrieve a specific booking',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Booking ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Booking details'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Booking not found'},
                ]
            },
            {
                'path': '/api/bookings/{id}/',
                'method': 'PUT',
                'description': 'Update a booking',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Booking ID', 'in_path': True},
                    {'name': 'service_id', 'type': 'integer', 'required': True, 'description': 'Service ID'},
                    {'name': 'specialist_id', 'type': 'integer', 'required': True, 'description': 'Specialist ID'},
                    {'name': 'start_time', 'type': 'string', 'required': True, 'description': 'Start time (ISO format)'},
                    {'name': 'notes', 'type': 'string', 'required': False, 'description': 'Booking notes'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Booking updated successfully'},
                    {'code': 400, 'description': 'Invalid request data or time slot not available'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Booking not found'},
                ]
            },
            {
                'path': '/api/bookings/{id}/',
                'method': 'DELETE',
                'description': 'Cancel a booking',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Booking ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 204, 'description': 'Booking cancelled successfully'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied or cancellation window passed'},
                    {'code': 404, 'description': 'Booking not found'},
                ]
            }
        ]
    },
    
    # Package app
    'packageapp': {
        'name': 'Packages',
        'endpoints': [
            {
                'path': '/api/packages/',
                'method': 'GET',
                'description': 'List all service packages',
                'parameters': [
                    {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number'},
                    {'name': 'page_size', 'type': 'integer', 'required': False, 'description': 'Results per page (max 100)'},
                    {'name': 'shop_id', 'type': 'integer', 'required': False, 'description': 'Filter by shop ID'},
                    {'name': 'min_price', 'type': 'number', 'required': False, 'description': 'Minimum price'},
                    {'name': 'max_price', 'type': 'number', 'required': False, 'description': 'Maximum price'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of packages'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/packages/{id}/',
                'method': 'GET',
                'description': 'Retrieve a specific package',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Package ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Package details'},
                    {'code': 404, 'description': 'Package not found'},
                ]
            },
            {
                'path': '/api/packages/{id}/purchase/',
                'method': 'POST',
                'description': 'Purchase a package',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Package ID', 'in_path': True},
                    {'name': 'payment_method', 'type': 'string', 'required': True, 'description': 'Payment method (card, wallet)'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Package purchased successfully'},
                    {'code': 400, 'description': 'Invalid request data'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 404, 'description': 'Package not found'},
                ]
            }
        ]
    },
    
    # Customer app
    'customersapp': {
        'name': 'Customers',
        'endpoints': [
            {
                'path': '/api/customers/',
                'method': 'GET',
                'description': 'List customers (admin or shop manager only)',
                'parameters': [
                    {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number'},
                    {'name': 'page_size', 'type': 'integer', 'required': False, 'description': 'Results per page (max 100)'},
                    {'name': 'search', 'type': 'string', 'required': False, 'description': 'Search by name or phone'},
                    {'name': 'shop_id', 'type': 'integer', 'required': False, 'description': 'Filter by shop ID (customers who have booked at this shop)'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of customers'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                ]
            },
            {
                'path': '/api/customers/{id}/',
                'method': 'GET',
                'description': 'Retrieve a specific customer (admin or shop manager only)',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Customer ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Customer details'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Customer not found'},
                ]
            }
        ]
    },
    
    # Payment app
    'payment': {
        'name': 'Payments',
        'endpoints': [
            {
                'path': '/api/payments/',
                'method': 'GET',
                'description': 'List payments for the authenticated user',
                'parameters': [
                    {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number'},
                    {'name': 'page_size', 'type': 'integer', 'required': False, 'description': 'Results per page (max 100)'},
                    {'name': 'status', 'type': 'string', 'required': False, 'description': 'Filter by status (pending, completed, failed)'},
                    {'name': 'from_date', 'type': 'string', 'required': False, 'description': 'Filter by date (YYYY-MM-DD)'},
                    {'name': 'to_date', 'type': 'string', 'required': False, 'description': 'Filter by date (YYYY-MM-DD)'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of payments'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/payments/{id}/',
                'method': 'GET',
                'description': 'Retrieve a specific payment',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Payment ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Payment details'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 403, 'description': 'Permission denied'},
                    {'code': 404, 'description': 'Payment not found'},
                ]
            },
            {
                'path': '/api/payments/process/',
                'method': 'POST',
                'description': 'Process a payment',
                'parameters': [
                    {'name': 'amount', 'type': 'number', 'required': True, 'description': 'Payment amount'},
                    {'name': 'currency', 'type': 'string', 'required': True, 'description': 'Currency code (SAR, USD, etc.)'},
                    {'name': 'payment_method', 'type': 'string', 'required': True, 'description': 'Payment method (card, wallet)'},
                    {'name': 'object_type', 'type': 'string', 'required': True, 'description': 'Related object type (booking, package)'},
                    {'name': 'object_id', 'type': 'integer', 'required': True, 'description': 'Related object ID'},
                ],
                'responses': [
                    {'code': 200, 'description': 'Payment processed successfully or payment URL generated'},
                    {'code': 400, 'description': 'Invalid request data'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            }
        ]
    },
    
    # Queue app
    'queueapp': {
        'name': 'Queues',
        'endpoints': [
            {
                'path': '/api/queues/',
                'method': 'GET',
                'description': 'List queues',
                'parameters': [
                    {'name': 'page', 'type': 'integer', 'required': False, 'description': 'Page number'},
                    {'name': 'page_size', 'type': 'integer', 'required': False, 'description': 'Results per page (max 100)'},
                    {'name': 'shop_id', 'type': 'integer', 'required': False, 'description': 'Filter by shop ID'},
                    {'name': 'is_active', 'type': 'boolean', 'required': False, 'description': 'Filter by active status'},
                ],
                'responses': [
                    {'code': 200, 'description': 'List of queues'},
                    {'code': 401, 'description': 'Unauthorized'},
                ]
            },
            {
                'path': '/api/queues/{id}/',
                'method': 'GET',
                'description': 'Retrieve a specific queue',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Queue ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Queue details'},
                    {'code': 404, 'description': 'Queue not found'},
                ]
            },
            {
                'path': '/api/queues/{id}/join/',
                'method': 'POST',
                'description': 'Join a queue',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Queue ID', 'in_path': True},
                    {'name': 'service_id', 'type': 'integer', 'required': True, 'description': 'Service ID'},
                    {'name': 'notes', 'type': 'string', 'required': False, 'description': 'Additional notes'},
                ],
                'responses': [
                    {'code': 201, 'description': 'Joined queue successfully'},
                    {'code': 400, 'description': 'Invalid request data or already in queue'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 404, 'description': 'Queue not found'},
                ]
            },
            {
                'path': '/api/queues/{id}/leave/',
                'method': 'POST',
                'description': 'Leave a queue',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Queue ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Left queue successfully'},
                    {'code': 400, 'description': 'Not in queue'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 404, 'description': 'Queue not found'},
                ]
            },
            {
                'path': '/api/queues/{id}/status/',
                'method': 'GET',
                'description': 'Get queue status',
                'parameters': [
                    {'name': 'id', 'type': 'integer', 'required': True, 'description': 'Queue ID', 'in_path': True},
                ],
                'responses': [
                    {'code': 200, 'description': 'Queue status including current position and wait time'},
                    {'code': 401, 'description': 'Unauthorized'},
                    {'code': 404, 'description': 'Queue not found'},
                ]
            }
        ]
    }
}

def get_all_endpoints():
    """Return a flat list of all endpoints"""
    all_endpoints = []
    for app_name, app_info in ENDPOINTS.items():
        for endpoint in app_info['endpoints']:
            all_endpoints.append({
                'app': app_name,
                'app_name': app_info['name'],
                **endpoint
            })
    return all_endpoints
