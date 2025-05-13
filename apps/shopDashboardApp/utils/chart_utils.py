"""
Utility functions for chart generation and manipulation.
These helpers simplify chart data formatting and processing.
"""


def format_chart_colors(count, alpha=0.7):
    """Generate a sequence of colors for chart elements"""
    # Base colors for charts
    base_colors = [
        (255, 99, 132),  # Red
        (54, 162, 235),  # Blue
        (255, 206, 86),  # Yellow
        (75, 192, 192),  # Teal
        (153, 102, 255),  # Purple
        (255, 159, 64),  # Orange
        (231, 76, 60),  # Pomegranate
        (46, 204, 113),  # Emerald
        (52, 152, 219),  # Peter River
        (155, 89, 182),  # Amethyst
        (241, 196, 15),  # Sunflower
        (230, 126, 34),  # Carrot
        (26, 188, 156),  # Turquoise
        (41, 128, 185),  # Belize Hole
        (142, 68, 173),  # Wisteria
    ]

    # Generate rgba strings
    colors = []
    for i in range(count):
        color_idx = i % len(base_colors)
        r, g, b = base_colors[color_idx]
        colors.append(f"rgba({r}, {g}, {b}, {alpha})")

    return colors


def format_chart_dates(dates, granularity="daily"):
    """Format dates for chart labels based on granularity"""
    if granularity == "hourly":
        return [date.strftime("%I:%M %p") for date in dates]
    elif granularity == "daily":
        return [date.strftime("%b %d") for date in dates]
    elif granularity == "weekly":
        return [date.strftime("Week %W") for date in dates]
    elif granularity == "monthly":
        return [date.strftime("%b %Y") for date in dates]
    else:
        return [date.strftime("%Y-%m-%d") for date in dates]


def generate_chart_options(chart_type, x_title=None, y_title=None):
    """Generate standard chart options based on chart type"""
    if chart_type in ["pie", "doughnut"]:
        return {
            "responsive": True,
            "plugins": {
                "legend": {
                    "position": "right",
                },
                "tooltip": {
                    "callbacks": {
                        "label": "(context) => `${context.label}: ${context.formattedValue}`",
                    }
                },
            },
        }
    elif chart_type in ["line", "bar"]:
        options = {
            "responsive": True,
            "scales": {
                "y": {
                    "beginAtZero": True,
                }
            },
        }

        # Add axis titles if provided
        if x_title:
            if "scales" not in options:
                options["scales"] = {}
            if "x" not in options["scales"]:
                options["scales"]["x"] = {}
            options["scales"]["x"]["title"] = {"display": True, "text": x_title}

        if y_title:
            if "scales" not in options:
                options["scales"] = {}
            if "y" not in options["scales"]:
                options["scales"]["y"] = {}
            options["scales"]["y"]["title"] = {"display": True, "text": y_title}

        return options

    return {}


def truncate_labels(labels, max_length=20):
    """Truncate chart labels to a maximum length"""
    truncated = []
    for label in labels:
        if len(label) > max_length:
            truncated.append(f"{label[:max_length-3]}...")
        else:
            truncated.append(label)
    return truncated
