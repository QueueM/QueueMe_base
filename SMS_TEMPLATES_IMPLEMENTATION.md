# QueueMe SMS Templates Management System

## Overview

The SMS Templates Management System provides administrators with tools to create, manage, and reuse SMS templates across the QueueMe platform. This feature enables consistent messaging, reduced costs, and more efficient mobile communication workflows.

## Features

### 1. SMS Template Creation
- Create customizable SMS templates with support for both English and Arabic
- Character counting with segment calculation for cost estimation
- Support for template variables using {{variable_name}} syntax
- Language-specific templates to support international audience

### 2. Template Management
- List, filter, and search templates for quick access
- Categorize templates (marketing, notification, system, booking, payment, etc.)
- Track usage statistics for each template
- Duplicate existing templates to create variations quickly

### 3. Template Variables
- Define and document template variables for personalization
- Provide sample data for testing template rendering
- Easy insertion of variables into templates with character count updates

### 4. Preview and Testing
- Real-time preview of templates with sample data
- Test send functionality to verify template appearance on actual devices
- Side-by-side view of English and Arabic versions
- Cost estimation based on segment count and recipient numbers

### 5. SMS-Specific Features
- Character count with segment calculation (160 chars per SMS, 153 for multi-segment)
- Cost estimation for campaigns based on segment count and recipient numbers
- Support for international phone number formats (E.164)
- Visual representation of how SMS will appear on mobile devices

## Technical Implementation

### Database Model
The system uses the `SMSTemplate` model in the `notificationsapp` application with the following key fields:
- `name`: Template name for identification
- `description`: Optional description of the template's purpose
- `content`: English version of the SMS message
- `content_ar`: Arabic version of the SMS message (optional)
- `category`: Template category for organization
- `variables`: JSON field storing variable definitions and descriptions
- `sample_data`: JSON field with sample data for testing
- `character_count`: Number of characters in the template (auto-calculated)
- `usage_count`: Counter for template usage tracking

### Admin Interface
The admin interface provides:
- List view with filters, search, and segment count information
- User-friendly template editor with real-time character counting
- Variable management and preview functionality
- Template duplication and deletion options
- Test send functionality for verification

## Integration Points

The SMS Templates system integrates with:

1. **Notification System**: Used when sending SMS notifications
2. **Campaign Management**: Used as content sources for marketing campaigns
3. **Booking System**: Used for booking confirmation and reminder SMS
4. **Customer Communications**: Used for direct customer text communications

## SMS Best Practices

The system encourages SMS best practices:

1. **Message Length**: Visual indicators when approaching segment boundaries
2. **Cost Management**: Estimated costs displayed for various recipient counts
3. **Variable Usage**: Simple variable insertion to personalize messages
4. **Internationalization**: Support for multiple languages and character sets
5. **Testing**: Easy test send functionality to verify appearance before mass sending

## Future Enhancements

1. **Message Analytics**: Track delivery, open, and response rates
2. **A/B Testing**: Compare performance of different template variations
3. **Auto-shortening**: Smart truncation to fit within segment boundaries
4. **URL Shortening**: Automatic shortening of URLs to save characters
5. **Templates Library**: Pre-built templates for common use cases
6. **SMS Scheduling**: Optimal time delivery based on user engagement data
