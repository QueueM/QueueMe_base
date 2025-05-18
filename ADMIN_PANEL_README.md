# QueueMe Admin Panel

A modern, feature-rich admin panel for the QueueMe application with 3D effects, real-time updates, and advanced UI components.

## Features

- **Modern UI Design**:
  - Light/Dark theme support with automatic system preference detection
  - 3D hover effects and animations for enhanced visual feedback
  - Responsive layout for all device sizes
  - Glassmorphism and neumorphism design elements

- **Advanced Form Components**:
  - Custom 3D date picker with animations
  - Floating labels with smooth animations
  - Custom stylized checkboxes and radio buttons
  - Field validation with animated error messages
  - Tooltip-based help text
  - Multi-step/tabbed forms for complex data entry

- **Dashboard Widgets**:
  - Real-time statistics and data visualization
  - Charts and graphs with theme-aware styling
  - Activity feeds with animated updates
  - Customizable widget layouts

- **Real-time Updates**:
  - WebSocket integration for live data updates
  - Real-time notifications for system events
  - Toast notifications for user feedback

- **Enhanced Filters and List Views**:
  - 3D styled filter components
  - Custom date range filters
  - Numeric range filters
  - Active status filters
  - Enhanced action buttons

## Directory Structure

```
utils/admin/
├── __init__.py        # Package exports and utilities
├── base.py            # Core admin functionality (RichAdminSite, BaseModelAdmin)
├── filters.py         # Custom filter components (DateRangeFilter, NumericRangeFilter)
├── mixins.py          # Reusable mixins (ExportMixin, AuditLogMixin)
├── ui.py              # UI-related utilities (RichFormAdminMixin)
├── urls.py            # URL patterns for custom admin views
├── views.py           # Custom admin views (dashboard)
└── widgets.py         # Dashboard widget implementations

static/admin/
├── css/
│   ├── admin_ui.css           # Main CSS for admin interface
│   └── components/
│       ├── dashboard.css      # Dashboard widget styles
│       ├── date_picker.css    # Date picker component styles
│       ├── forms.css          # Enhanced form styles
│       ├── notifications.css  # Notification styles
│       └── styled_filter.css  # Filter component styles
└── js/
    ├── admin_ui.js            # Main JavaScript for admin UI
    └── components/
        ├── dashboard.js       # Dashboard widget functionality
        ├── date_picker.js     # Date picker component
        ├── form_effects.js    # Form 3D effects and animations
        └── notifications.js   # Notification system

templates/admin/
├── base.html                  # Base admin template
├── change_form.html           # Enhanced change form template
├── components/
│   ├── custom_form.html       # Form component template
│   └── styled_filter.html     # Filter component template
└── dashboard/
    ├── index.html             # Dashboard index page
    └── widget.html            # Dashboard widget template
```

## Usage

### Model Admin Configuration

To use the enhanced admin features with your models:

```python
from django.contrib import admin
from utils.admin import RichFormAdminMixin, DateRangeFilter, ExportMixin
from utils.admin.widgets import BookingsDashboardMixin

@admin.register(YourModel)
class YourModelAdmin(RichFormAdminMixin, BookingsDashboardMixin, ExportMixin, admin.ModelAdmin):
    """Admin interface with rich UI components, dashboard widget, and export"""
    list_display = ('id', 'name', 'status', 'created_at')
    list_filter = (
        ('created_at', DateRangeFilter),
        'status',
    )
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    # Dashboard configuration
    dashboard_title = 'Your Model Overview'
    dashboard_icon = 'chart-bar'  # Font Awesome icon

    # Export configuration
    export_formats = ['csv', 'excel', 'json']

    # Media files for enhanced UI
    class Media:
        css = {
            'all': (
                'admin/css/components/forms.css',
                'admin/css/components/styled_filter.css',
                'admin/css/components/dashboard.css',
            )
        }
        js = (
            'admin/js/components/date_picker.js',
            'admin/js/components/notifications.js',
            'admin/js/components/dashboard.js',
        )
```

### Dashboard Widgets

To create a custom dashboard widget:

1. Create a mixin that inherits from `DashboardWidgetMixin`
2. Implement the required methods: `get_dashboard_context`, `get_dashboard_stats`, etc.
3. Apply the mixin to your ModelAdmin class

Example:

```python
from utils.admin import DashboardWidgetMixin

class YourDashboardMixin(DashboardWidgetMixin):
    dashboard_template = 'admin/dashboard/widget.html'
    dashboard_title = 'Your Widget Title'
    dashboard_icon = 'chart-line'

    def get_dashboard_stats(self, request, queryset):
        return [
            {'label': 'Total', 'value': queryset.count()},
            {'label': 'Active', 'value': queryset.filter(is_active=True).count()}
        ]

    def get_dashboard_chart_data(self, request, queryset):
        # Return chart data dict
        return {
            'type': 'line',
            'labels': ['Jan', 'Feb', 'Mar'],
            'datasets': [
                {
                    'label': 'Data',
                    'data': [10, 20, 30]
                }
            ]
        }
```

## Theme Customization

You can customize the theme colors by modifying the CSS variables in `static/admin/css/admin_ui.css`:

```css
:root {
    /* Light theme colors */
    --primary: #3b82f6;
    --primary-light: #60a5fa;
    --primary-dark: #2563eb;
    /* Add more custom variables here */
}

[data-theme="dark"] {
    /* Dark theme colors */
    --text-color: #e2e8f0;
    --background: #0f172a;
    /* Add more dark theme variables here */
}
```

## Installation

The admin panel is automatically included with the QueueMe application. No additional installation steps are required.

## Development

For development:

1. Ensure static files are collected: `python manage.py collectstatic`
2. Run the development server: `python manage.py runserver`
3. Access the admin panel at: `http://localhost:8000/admin/`
