# apps/reportanalyticsapp/utils/chart_utils.py


class ChartUtils:
    """
    Utility class for generating chart configurations.
    Provides methods for creating different types of visualizations based on report data.
    """

    @staticmethod
    def get_visualization_configs(report_data, report_type):
        """
        Generate visualization configurations for a report.

        Args:
            report_data: Report data dictionary
            report_type: Type of report

        Returns:
            list: Visualization configurations
        """
        visualizations = []

        # Add time series visualizations
        if "time_series" in report_data:
            for series_name, series_data in report_data["time_series"].items():
                if series_data:
                    visualizations.append(
                        ChartUtils.create_time_series_config(
                            series_name,
                            series_data,
                            f"{series_name.replace('_', ' ').title()} Over Time",
                        )
                    )

        # Add report-specific visualizations
        if report_type == "business_overview":
            # Add service breakdown chart
            if "service_data" in report_data and report_data["service_data"]:
                visualizations.append(
                    ChartUtils.create_bar_chart_config(
                        "service_bookings",
                        {
                            service["name"]: service["bookings"]
                            for service in report_data["service_data"][:10]
                        },
                        "Services by Bookings",
                        "Service",
                        "Bookings",
                    )
                )

                visualizations.append(
                    ChartUtils.create_pie_chart_config(
                        "service_revenue",
                        {
                            service["name"]: service["revenue"]
                            for service in report_data["service_data"]
                            if service["revenue"] > 0
                        }[:8],
                        "Revenue by Service",
                    )
                )

        elif report_type == "booking_analytics":
            # Add hourly distribution chart
            if "hourly_distribution" in report_data:
                visualizations.append(
                    ChartUtils.create_bar_chart_config(
                        "hourly_distribution",
                        report_data["hourly_distribution"],
                        "Bookings by Hour",
                        "Hour",
                        "Bookings",
                    )
                )

            # Add day distribution chart
            if "day_distribution" in report_data:
                # Convert numeric days to day names
                day_names = [
                    "Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                ]
                day_data = {
                    day_names[int(day) % 7]: count
                    for day, count in report_data["day_distribution"].items()
                }

                visualizations.append(
                    ChartUtils.create_bar_chart_config(
                        "day_distribution",
                        day_data,
                        "Bookings by Day",
                        "Day",
                        "Bookings",
                    )
                )

        elif report_type == "customer_satisfaction":
            # Add rating distribution chart
            if "rating_distribution" in report_data:
                visualizations.append(
                    ChartUtils.create_bar_chart_config(
                        "rating_distribution",
                        report_data["rating_distribution"],
                        "Rating Distribution",
                        "Rating",
                        "Count",
                    )
                )

        elif report_type == "revenue_analysis":
            # Add revenue by payment method
            if "revenue_by_payment_method" in report_data:
                visualizations.append(
                    ChartUtils.create_pie_chart_config(
                        "revenue_by_payment_method",
                        {
                            item["payment_type"]: item["revenue"]
                            for item in report_data["revenue_by_payment_method"]
                        },
                        "Revenue by Payment Method",
                    )
                )

        return visualizations

    @staticmethod
    def create_time_series_config(series_name, series_data, title):
        """
        Create a time series chart configuration.

        Args:
            series_name: Name of the series
            series_data: Series data dictionary
            title: Chart title

        Returns:
            dict: Chart configuration
        """
        # Sort data by date
        sorted_data = sorted(series_data.items())
        labels = [item[0] for item in sorted_data]
        values = [item[1] for item in sorted_data]

        return {
            "type": "line",
            "id": f"chart_{series_name}",
            "title": title,
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": series_name.replace("_", " ").title(),
                        "data": values,
                        "borderColor": "#5a55ca",
                        "backgroundColor": "rgba(90, 85, 202, 0.1)",
                        "borderWidth": 2,
                        "fill": True,
                        "tension": 0.4,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "scales": {
                    "x": {"title": {"display": True, "text": "Date"}},
                    "y": {
                        "beginAtZero": True,
                        "title": {
                            "display": True,
                            "text": series_name.replace("_", " ").title(),
                        },
                    },
                },
            },
        }

    @staticmethod
    def create_bar_chart_config(chart_id, data, title, x_label, y_label):
        """
        Create a bar chart configuration.

        Args:
            chart_id: Chart ID
            data: Data dictionary
            title: Chart title
            x_label: X-axis label
            y_label: Y-axis label

        Returns:
            dict: Chart configuration
        """
        # Sort data for better visualization
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        labels = [item[0] for item in sorted_data]
        values = [item[1] for item in sorted_data]

        return {
            "type": "bar",
            "id": f"chart_{chart_id}",
            "title": title,
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": y_label,
                        "data": values,
                        "backgroundColor": "rgba(90, 85, 202, 0.7)",
                        "borderColor": "rgba(90, 85, 202, 1)",
                        "borderWidth": 1,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "scales": {
                    "x": {"title": {"display": True, "text": x_label}},
                    "y": {
                        "beginAtZero": True,
                        "title": {"display": True, "text": y_label},
                    },
                },
            },
        }

    @staticmethod
    def create_pie_chart_config(chart_id, data, title):
        """
        Create a pie chart configuration.

        Args:
            chart_id: Chart ID
            data: Data dictionary
            title: Chart title

        Returns:
            dict: Chart configuration
        """
        # Sort data for better visualization
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        labels = [item[0] for item in sorted_data]
        values = [item[1] for item in sorted_data]

        # Generate colors
        colors = [
            "rgba(90, 85, 202, 0.8)",
            "rgba(54, 162, 235, 0.8)",
            "rgba(255, 206, 86, 0.8)",
            "rgba(75, 192, 192, 0.8)",
            "rgba(153, 102, 255, 0.8)",
            "rgba(255, 159, 64, 0.8)",
            "rgba(255, 99, 132, 0.8)",
            "rgba(199, 199, 199, 0.8)",
        ]

        # Extend colors if needed
        if len(values) > len(colors):
            colors = colors * (len(values) // len(colors) + 1)

        return {
            "type": "pie",
            "id": f"chart_{chart_id}",
            "title": title,
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "data": values,
                        "backgroundColor": colors[: len(values)],
                        "borderColor": "rgba(255, 255, 255, 0.8)",
                        "borderWidth": 1,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {"legend": {"position": "right"}},
            },
        }

    @staticmethod
    def create_radar_chart_config(chart_id, data, title):
        """
        Create a radar chart configuration.

        Args:
            chart_id: Chart ID
            data: Data dictionary
            title: Chart title

        Returns:
            dict: Chart configuration
        """
        labels = list(data.keys())
        values = list(data.values())

        return {
            "type": "radar",
            "id": f"chart_{chart_id}",
            "title": title,
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": "Values",
                        "data": values,
                        "backgroundColor": "rgba(90, 85, 202, 0.2)",
                        "borderColor": "rgba(90, 85, 202, 1)",
                        "borderWidth": 2,
                        "pointBackgroundColor": "rgba(90, 85, 202, 1)",
                        "pointBorderColor": "#fff",
                        "pointHoverBackgroundColor": "#fff",
                        "pointHoverBorderColor": "rgba(90, 85, 202, 1)",
                    }
                ],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "elements": {"line": {"tension": 0.1}},
            },
        }
