# QueueMe Push Notification Templates Management System

## Overview

The Push Notification Templates Management System provides administrators with tools to create, manage, and reuse push notification templates across the QueueMe platform. This feature enables consistent messaging, rich notifications, and personalized mobile and web engagement with customers.

## Features

### 1. Push Notification Template Creation
- Create customizable push notification templates with title, body, and optional rich content
- Support for both English and Arabic language content
- Character counting with visual indicators for optimal message length
- Support for template variables using {{variable_name}} syntax
- Platform-specific template targeting (iOS, Android, Web, or all platforms)

### 2. Template Management
- List, filter, and search templates for quick access
- Categorize templates (marketing, notification, system, booking, payment)
- Duplicate existing templates to quickly create variations
- Track template usage statistics and creation metadata
- Activate/deactivate templates without deletion

### 3. Rich Notification Support
- Image URL support for rich notifications with media content
- Action button customization with custom text
- Deep linking support via configurable action URLs
- Additional data payload for extended app functionality

### 4. Preview and Testing
- Real-time visual device preview with variable substitution
- Test sending directly to specific users from the admin interface
- Language toggle for testing both English and Arabic versions
- Cross-platform preview visualization

### 5. Variable System
- JSON-based variable definitions with descriptions
- Variable picker interface for easy insertion into templates
- Test data management for variable replacement
- Sample data storage for consistent testing

## Technical Implementation

### Database Model
The system uses a `PushNotificationTemplate` model that includes:

```python
class PushNotificationTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # Push notification components
    title = models.CharField(max_length=100)
    body = models.TextField()

    # Optional fields
    image_url = models.URLField(blank=True, null=True)
    action_url = models.CharField(max_length=255, blank=True, null=True)
    action_button_text = models.CharField(max_length=30, blank=True, null=True)

    # Categorization and targeting
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='all')

    # Localization
    title_ar = models.CharField(max_length=100, blank=True, null=True)
    body_ar = models.TextField(blank=True, null=True)
    action_button_text_ar = models.CharField(max_length=30, blank=True, null=True)

    # Data fields
    additional_data = models.JSONField(default=dict, blank=True)
    variables = models.JSONField(default=dict, blank=True)
    sample_data = models.JSONField(default=dict, blank=True)

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Usage tracking
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
```

### Views
The system implements the following views for template management:

1. **push_templates_list**: List all templates with filtering and sorting
2. **push_template_create**: Create new templates
3. **push_template_detail**: View template details and usage statistics
4. **push_template_edit**: Edit existing templates
5. **push_template_duplicate**: Clone templates for quick variations
6. **push_template_delete**: Delete templates with confirmation
7. **push_template_preview**: Generate preview with variable substitution
8. **push_template_test_send**: Send test notifications to specific users

### Templates
The UI templates provide an intuitive interface for managing push notification templates:

1. **list.html**: Grid view of all templates with filtering
2. **create_edit.html**: Form for creating and editing templates with tabs for different sections
3. **detail.html**: Detailed view with metrics and device preview
4. **test_send.html**: Testing interface with variable data input
5. **delete.html**: Confirmation screen for template deletion

## Integration with Notification Service

The Push Notification Templates system integrates with the existing NotificationService to send notifications:

```python
# Example of sending notification using a template
from apps.notificationsapp.models import PushNotificationTemplate
from apps.notificationsapp.services.notification_service import NotificationService

def send_notification_from_template(template_id, recipient_id, data=None, language='en'):
    """
    Send a push notification using a template

    Args:
        template_id: UUID of the template to use
        recipient_id: User ID to send to
        data: Optional dict of template data
        language: 'en' for English, 'ar' for Arabic
    """
    template = PushNotificationTemplate.objects.get(id=template_id)

    # Get preview with data
    preview = template.get_preview(data, language)

    # Prepare additional data
    additional_data = template.additional_data.copy() if template.additional_data else {}
    additional_data.update({
        'template_id': str(template.id),
        'template_name': template.name
    })

    # Send notification
    result = NotificationService.send_notification(
        recipient_id=recipient_id,
        notification_type='template_notification',
        title=preview['title'],
        message=preview['body'],
        channels=['push'],
        data={
            'action_url': preview['action_url'],
            'image_url': preview['image_url'],
            'action_button_text': preview['action_button_text'],
            **additional_data
        },
        metadata={
            'template_id': str(template.id)
        }
    )

    # Update usage statistics if sent successfully
    if result.get('success'):
        template.increment_usage()

    return result
```

## Best Practices for Push Notification Templates

The system includes guidance for administrators on push notification best practices:

1. **Character Limits**:
   - Keep titles under 50 characters
   - Keep body text under 150 characters
   - Consider platform-specific display limitations

2. **Rich Content Support**:
   - iOS: Limited image support, no custom action buttons
   - Android: Full support for images and action buttons
   - Web: Support varies by browser, generally good for newer browsers

3. **Variable Usage**:
   - Use descriptive variable names
   - Provide sample data for testing
   - Document variables for team reuse

4. **User Experience**:
   - Send during appropriate hours
   - Limit frequency to avoid notification fatigue
   - Use personalization to increase engagement

## Future Enhancements

Potential future enhancements for the system include:

1. A/B testing of different notification templates
2. Engagement analytics specific to template performance
3. Template scheduling and time-sensitive delivery options
4. Integration with campaign scheduling system
5. Enhanced rich content support for newer platforms

## Conclusion

The Push Notification Templates system provides a comprehensive solution for creating, managing, and sending personalized push notifications. It enhances the QueueMe platform's communication capabilities with consistent, branded, and engaging mobile notifications that work across all supported platforms.
