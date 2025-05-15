@login_required
def admin_customers_view(request):
    """Admin view for customer management"""
    # Get query parameters
    search_query = request.GET.get("q", "")
    status_filter = request.GET.get("status", "")
    sort_by = request.GET.get("sort", "newest")
    page = request.GET.get("page", 1)

    # Build the queryset with filters
    customers_queryset = User.objects.filter(is_staff=False)

    # Apply search filter if provided
    if search_query:
        customers_queryset = customers_queryset.filter(
            Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(phone_number__icontains=search_query)
        )

    # Apply status filter if provided
    if status_filter == "active":
        customers_queryset = customers_queryset.filter(is_active=True)
    elif status_filter == "inactive":
        customers_queryset = customers_queryset.filter(is_active=False)

    # Apply sorting
    if sort_by == "oldest":
        customers_queryset = customers_queryset.order_by("date_joined")
    elif sort_by == "name":
        customers_queryset = customers_queryset.order_by("first_name", "last_name")
    elif sort_by == "email":
        customers_queryset = customers_queryset.order_by("email")
    else:  # newest (default)
        customers_queryset = customers_queryset.order_by("-date_joined")

    # Get statistics
    total_customers = customers_queryset.count()
    active_customers = customers_queryset.filter(is_active=True).count()
    inactive_customers = total_customers - active_customers

    # Calculate recent growth (customers joined in last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_customers = customers_queryset.filter(date_joined__gte=thirty_days_ago).count()

    # Set up pagination
    paginator = Paginator(customers_queryset, 20)  # 20 customers per page
    try:
        customers_page = paginator.page(page)
    except Exception:
        customers_page = paginator.page(1)

    return render(
        request,
        "admin/user/customers.html",
        {
            "title": "Customer Management",
            "customers": customers_page,
            "total_customers": total_customers,
            "active_customers": active_customers,
            "inactive_customers": inactive_customers,
            "recent_customers": recent_customers,
            "search_query": search_query,
            "status_filter": status_filter,
            "sort_by": sort_by,
        },
    )
