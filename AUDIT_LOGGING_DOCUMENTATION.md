# QueueMe Admin Panel - Audit Logging System

## Overview

The Audit Logging System is a comprehensive solution for tracking and monitoring all administrative actions performed in the QueueMe Admin Panel. It provides detailed logs of user activities, helping with security compliance, troubleshooting, and accountability.

## Features

- **Automatic Action Logging**: Captures admin actions through middleware without requiring code changes
- **Manual Action Logging**: Decorators for explicitly logging specific view functions
- **Flexible Storage**: Uses SQLite database for independence from main database migrations
- **Comprehensive UI**: Detailed views for browsing, filtering, and analyzing audit logs
- **Detailed Tracking**: Records user, action type, target, timestamps, IP addresses, and browser info

## Implementation Architecture

The Audit Logging System consists of the following components:

1. **Middleware** (`utils/admin/middleware.py`): Automatically captures admin actions based on URL patterns
2. **Audit Utilities** (`utils/admin/audit.py`): Provides decorators and utility functions for manual logging
3. **Database Layer** (`utils/admin/audit_db.py`): Handles SQLite interactions for storing and retrieving logs
4. **Admin Views** (`utils/admin/views.py`): UI for viewing and filtering logs
5. **Templates**: Presentation layer for displaying logs and detail views

## How It Works

### Automatic Logging via Middleware

The system automatically captures admin actions through middleware by:

1. Intercepting admin requests and responses
2. Identifying admin URLs that should be logged
3. Determining action types based on URL patterns and HTTP methods
4. Extracting target models and IDs from URL patterns
5. Recording details about the action
6. Storing the audit record in the SQLite database

### Manual Logging via Decorators

For more fine-grained control, you can use the `@log_admin_action` decorator:

```python
@login_required
@log_admin_action(action_type='create', target_model='User')
def create_user(request):
    # Function implementation
    pass
```

## Database Schema

The audit logs are stored in a separate SQLite database (`audit_log.db`) with the following schema:

| Field         | Type      | Description                                     |
|---------------|-----------|-------------------------------------------------|
| id            | TEXT      | Primary key (UUID)                              |
| action_type   | TEXT      | Type of action (create, update, delete, etc.)   |
| timestamp     | TEXT      | ISO-formatted timestamp                         |
| target_model  | TEXT      | Model being acted upon                          |
| target_id     | TEXT      | ID of the specific record                       |
| action_detail | TEXT      | Additional details about the action             |
| ip_address    | TEXT      | IP address of the user                          |
| browser_info  | TEXT      | Browser information                             |
| status        | TEXT      | Status of the action (success/failure/pending)  |
| user_id       | TEXT      | ID of the user performing the action            |

## How to Use

### Viewing Audit Logs

1. Navigate to "System > Audit Logs" in the admin sidebar
2. Use the filters to narrow down logs by action type, user, date, etc.
3. Click on a log entry to view detailed information

### Logging Custom Actions

To manually log actions in your custom views:

```python
from utils.admin.audit import log_admin_action

@login_required
@log_admin_action(action_type='custom_action', target_model='YourModel')
def your_custom_view(request):
    # Your implementation
    pass
```

### Setting Additional Audit Data

To add extra details to your audit logs:

```python
from utils.admin.audit import set_audit_data

# In your view function
set_audit_data(request,
    target_id=obj.id,
    action_detail="Custom detailed message",
    additional_data={'key': 'value'}
)
```

## Action Types

The system supports the following action types:

- `create`: Creating new records
- `update`: Modifying existing records
- `delete`: Deleting records
- `view`: Viewing details
- `login`: User login
- `logout`: User logout
- `send_message`: Sending messages/communications
- `refund`: Processing refunds
- `approve`: Approving items/requests
- `reject`: Rejecting items/requests
- `other`: Any other action

## Extending the System

### Adding New Action Types

To add new action types:

1. Update the `ACTION_TYPES` list in `utils/admin/audit_db.py`
2. Add appropriate styling for the new action type in the CSS
3. Update the middleware to detect the new action type if needed

### Custom Filtering

To add custom filters:

1. Modify the `admin_audit_logs` view in `utils/admin/views.py`
2. Update the template to display the new filters

## Security Considerations

- Audit logs are stored separately from the main database to prevent tampering
- The system automatically filters out sensitive information (passwords, tokens, etc.)
- Only admin users can access the audit logs

## Performance Impact

The audit logging system is designed to have minimal performance impact:

- Asynchronous logging would be ideal for production use
- The separate SQLite database prevents impact on main database performance
- The middleware only processes admin URLs to reduce overhead

## Future Enhancements

Potential future improvements include:

- Export functionality for audit logs (CSV, Excel)
- Advanced visualizations and analytics dashboards
- Integration with external logging systems
- Real-time alerts for suspicious activities
- Automatic log rotation and archiving
