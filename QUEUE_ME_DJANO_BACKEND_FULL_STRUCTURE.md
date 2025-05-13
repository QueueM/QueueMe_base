#1 Queue Me: Root Directory Structure (Top Level)
queueme_backend/
├── .git/                                # Git repository
├── .github/                             # GitHub configurations
├── .gitignore                           # Git ignore file
├── .env.example                         # Example environment variables
├── docker-compose.yml                   # Docker Compose configuration
├── docker-compose.prod.yml              # Production Docker Compose
├── docker-entrypoint.sh                 # Docker entrypoint script
├── Dockerfile                           # Docker configuration
├── Dockerfile.celery                    # Celery worker Dockerfile
├── manage.py                            # Django management script
├── pyproject.toml                       # Python project metadata
├── README.md                            # Project documentation
├── requirements.txt                     # Project dependencies
├── requirements/                        # Split requirements files
├── setup.cfg                            # Python setup configuration
├── setup.py                             # Python package setup
├── pytest.ini                           # PyTest configuration
├── tox.ini                              # Tox configuration
├── .flake8                              # Flake8 configuration
├── .isort.cfg                           # isort configuration
├── .pre-commit-config.yaml              # Pre-commit hooks
├── queueme/                             # Main project directory (settings, urls, etc.)
├── algorithms/                          # Shared algorithms package
├── apps/                                # Applications directory containing all Django apps
│   ├── authapp/                         # Authentication app
│   ├── bookingapp/                      # Booking management app
│   ├── categoriesapp/                   # Categories app
│   ├── chatapp/                         # Live chat app
│   ├── companiesapp/                    # Companies app
│   ├── customersapp/                    # Customers app
│   ├── discountapp/                     # Discounts app
│   ├── employeeapp/                     # Employee management app
│   ├── followapp/                       # Follow system app
│   ├── geoapp/                          # Geolocation app
│   ├── notificationsapp/                # Notifications app
│   ├── packageapp/                      # Service packages app
│   ├── payment/                         # Payment processing app
│   ├── queueapp/                        # Queue management app
│   ├── queueMeAdminApp/                 # Admin panel app
│   ├── reelsapp/                        # Reels content app
│   ├── reportanalyticsapp/              # Analytics app
│   ├── reviewapp/                       # Reviews app
│   ├── rolesapp/                        # Role-based permissions app
│   ├── serviceapp/                      # Services app
│   ├── shopapp/                         # Shop management app
│   ├── shopDashboardApp/                # Shop dashboard app
│   ├── specialistsapp/                  # Specialists app
│   ├── storiesapp/                      # Stories content app
│   └── subscriptionapp/                 # Subscription app
├── core/                                # Core utilities and shared components
├── api/                                 # API versioning and documentation
├── websockets/                          # WebSockets framework
├── config/                              # Configuration files (nginx, redis, etc.)
├── db/                                  # Database files and initialization scripts
├── docker/                              # Docker configurations
├── docs/                                # Documentation
├── locale/                              # Internationalization (Arabic/English)
├── scripts/                             # Utility scripts (deployment, migration, etc.)
├── static/                              # Static files (css, js, img)
├── templates/                           # Global templates
├── tests/                               # Global tests (integration, performance)
└── utils/                               # Global utilities


#2 Main Project Directory
├── queueme/                             # Main project directory
│   ├── __init__.py                      # Package initialization
│   ├── asgi.py                          # ASGI configuration (WebSockets)
│   ├── celery.py                        # Celery configuration
│   ├── middleware.py                    # Global middleware
│   │   ├── localization_middleware.py   # Arabic/English language detection
│   │   ├── auth_middleware.py           # Authentication middleware
│   │   └── performance_middleware.py    # Performance tracking middleware
│   ├── permissions.py                   # Global permissions
│   ├── routing.py                       # WebSocket routing
│   ├── urls.py                          # Main URL routing
│   ├── wsgi.py                          # WSGI configuration
│   └── settings/                        # Settings module
│       ├── __init__.py                  # Package initialization
│       ├── base.py                      # Base settings (SQLite3 with PostgreSQL prep)
│       ├── development.py               # Development settings
│       ├── production.py                # Production settings
│       └── test.py                      # Test settings

#3 Advanced Algorithms Package
├── algorithms/                          # Shared algorithms
│   ├── __init__.py                      # Package initialization
│   ├── availability/                    # Availability algorithms
│   │   ├── __init__.py                  # Package initialization
│   │   ├── slot_generator.py            # Sophisticated slot generation algorithm
│   │   ├── constraint_solver.py         # Constraint satisfaction for scheduling
│   │   └── conflict_detector.py         # Multi-dimensional conflict detection
│   ├── geo/                             # Geospatial algorithms
│   │   ├── __init__.py                  # Package initialization
│   │   ├── distance.py                  # Haversine distance calculation
│   │   ├── spatial_indexing.py          # R-tree spatial indexing for location queries
│   │   ├── travel_time.py               # Travel time estimation
│   │   └── geo_visibility.py            # Same-city visibility algorithm
│   ├── ml/                              # Machine learning algorithms
│   │   ├── __init__.py                  # Package initialization
│   │   ├── recommender.py               # Content recommendation engine
│   │   ├── wait_time_predictor.py       # Queue wait time prediction
│   │   ├── anomaly_detector.py          # Anomaly detection for business metrics
│   │   └── preference_extractor.py      # User preference extraction from behavior
│   ├── optimization/                    # Optimization algorithms
│   │   ├── __init__.py                  # Package initialization
│   │   ├── queue_optimizer.py           # Hybrid queue optimization for walk-ins
│   │   ├── schedule_optimizer.py        # Staff schedule optimization
│   │   ├── workload_balancer.py         # Specialist workload balancer
│   │   └── multi_service_scheduler.py   # Multi-service booking optimization
│   ├── ranking/                         # Ranking algorithms
│   │   ├── __init__.py                  # Package initialization
│   │   ├── content_ranker.py            # Feed content ranking system
│   │   ├── specialist_ranker.py         # Specialist recommendation algorithm
│   │   ├── shop_ranker.py               # Shop visibility algorithm
│   │   └── weighted_rating.py           # Advanced review rating algorithm
│   ├── search/                          # Search algorithms
│   │   ├── __init__.py                  # Package initialization
│   │   ├── geospatial_search.py         # Efficient geo-search algorithm
│   │   └── service_search.py            # Service matching algorithm
│   └── security/                        # Security algorithms
│       ├── __init__.py                  # Package initialization
│       ├── fraud_detector.py            # Payment fraud detection
│       └── rate_limiter.py              # Advanced rate limiting algorithm

#4.01 Authentication App
├── apps/                                # Applications directory
│   ├── __init__.py                      # Package initialization
│   ├── authapp/                         # Authentication application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── constants.py                 # Auth constants
│   │   ├── models.py                    # User and OTP models
│   │   ├── serializers.py               # Auth serializers
│   │   ├── signals.py                   # Auth signals
│   │   ├── urls.py                      # Auth URL routing
│   │   ├── validators.py                # Phone number validators
│   │   ├── views.py                     # Auth API views
│   │   ├── adapters/                    # External service adapters
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── moyassar_sms.py          # Moyassar SMS integration
│   │   ├── middleware/                  # App-specific middleware
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── auth_middleware.py       # Auth middleware
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Auth business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── otp_service.py           # Advanced OTP generation and validation
│   │   │   ├── token_service.py         # JWT token management
│   │   │   ├── phone_verification.py    # Phone verification service
│   │   │   └── security_service.py      # Security service with rate limiting
│   │   └── tests/                       # Auth tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       ├── test_services.py         # Service tests
│   │       └── test_views.py            # View tests

#4.02 Booking App
│   ├── bookingapp/                      # Booking application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── filters.py                   # Booking filters
│   │   ├── models.py                    # Booking models
│   │   ├── permissions.py               # Booking permissions
│   │   ├── serializers.py               # Booking serializers
│   │   ├── signals.py                   # Booking signals
│   │   ├── tasks.py                     # Booking Celery tasks
│   │   ├── urls.py                      # Booking URL routing
│   │   ├── views.py                     # Booking API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Booking business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── availability_service.py  # Dynamic availability calculation
│   │   │   ├── booking_service.py       # Booking process service
│   │   │   ├── conflict_service.py      # Sophisticated conflict detection
│   │   │   ├── specialist_matcher.py    # Intelligent specialist matching
│   │   │   ├── multi_service_booker.py  # Multiple service booking optimizer
│   │   │   └── reminder_service.py      # Appointment reminder system
│   │   ├── tests/                       # Booking tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Booking utilities
│   │       ├── __init__.py              # Package initialization
│   │       ├── date_utils.py            # Date handling utilities
│   │       └── time_calculator.py       # Time calculation utilities

#4.03 Categories App
│   ├── categoriesapp/                   # Categories application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── models.py                    # Category models
│   │   ├── permissions.py               # Category permissions
│   │   ├── serializers.py               # Category serializers
│   │   ├── signals.py                   # Category signals
│   │   ├── urls.py                      # Category URL routing
│   │   ├── views.py                     # Category API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Category business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── category_service.py      # Category management
│   │   │   └── hierarchy_service.py     # Parent-child hierarchy management
│   │   └── tests/                       # Category tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       └── test_views.py            # View tests

#4.04 Chat App
│   ├── chatapp/                         # Chat application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── consumers.py                 # WebSocket consumers
│   │   ├── models.py                    # Chat models
│   │   ├── permissions.py               # Chat permissions
│   │   ├── routing.py                   # WebSocket routing
│   │   ├── serializers.py               # Chat serializers
│   │   ├── urls.py                      # Chat URL routing
│   │   ├── views.py                     # Chat API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Chat business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── chat_service.py          # Chat management
│   │   │   ├── media_service.py         # Media handling in chat
│   │   │   ├── message_router.py        # Intelligent message routing
│   │   │   ├── presence_service.py      # Online/offline status tracking
│   │   │   └── response_suggester.py    # Automated response suggestions
│   │   ├── templates/                   # Chat templates
│   │   │   └── chatapp/                 # App-specific templates
│   │   │       └── emails/              # Email templates
│   │   │           └── new_message.html # New message notification
│   │   ├── tests/                       # Chat tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Chat utilities
│   │       ├── __init__.py              # Package initialization
│   │       └── formatters.py            # Message formatting utilities

#4.05 Companies App
│   ├── companiesapp/                    # Companies application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── models.py                    # Company models
│   │   ├── permissions.py               # Company permissions
│   │   ├── serializers.py               # Company serializers
│   │   ├── signals.py                   # Company signals
│   │   ├── urls.py                      # Company URL routing
│   │   ├── validators.py                # Company validators
│   │   ├── views.py                     # Company API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Company business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── company_service.py       # Company management
│   │   │   ├── branch_service.py        # Branch management
│   │   │   └── subscription_service.py  # Subscription link service
│   │   └── tests/                       # Company tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       └── test_views.py            # View tests

#4.06 Customers App
│   ├── customersapp/                    # Customers application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── models.py                    # Customer models
│   │   ├── permissions.py               # Customer permissions
│   │   ├── serializers.py               # Customer serializers
│   │   ├── signals.py                   # Customer signals
│   │   ├── urls.py                      # Customer URL routing
│   │   ├── views.py                     # Customer API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Customer business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── customer_service.py      # Customer management
│   │   │   ├── favorites_service.py     # Favorites handling
│   │   │   ├── preference_extractor.py  # Preference detection algorithm
│   │   │   ├── personalization_engine.py # Content personalization
│   │   │   └── payment_method_service.py # Payment methods
│   │   └── tests/                       # Customer tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       └── test_views.py            # View tests

#4.07 Discount App
│   ├── discountapp/                     # Discount application
│   │   ├── README.md                    # App documentation
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── constants.py                 # Discount constants
│   │   ├── filters.py                   # Discount filters
│   │   ├── middleware.py                # Discount middleware
│   │   ├── models.py                    # Discount models
│   │   ├── permissions.py               # Discount permissions
│   │   ├── serializers.py               # Discount serializers
│   │   ├── signals.py                   # Discount signals
│   │   ├── tasks.py                     # Discount Celery tasks
│   │   ├── urls.py                      # Discount URL routing
│   │   ├── validators.py                # Discount validators
│   │   ├── views.py                     # Discount API views
│   │   ├── management/                  # Management commands
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── commands/                # Command implementations
│   │   │       ├── __init__.py          # Package initialization
│   │   │       ├── cleanup_expired_discounts.py  # Cleanup command
│   │   │       └── generate_coupons.py  # Coupon generator
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Discount business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── coupon_service.py        # Coupon management
│   │   │   ├── discount_service.py      # Discount management
│   │   │   ├── eligibility_service.py   # Discount eligibility engine
│   │   │   └── promotion_service.py     # Promotion management
│   │   ├── templates/                   # Discount templates
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── email/                   # Email templates
│   │   │       ├── campaign_announcement.html  # Campaign email
│   │   │       └── coupon_code.html     # Coupon email
│   │   ├── tests/                       # Discount tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── factories.py             # Test factories
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Discount utilities
│   │       ├── __init__.py              # Package initialization
│   │       └── code_generator.py        # Code generation utility

#4.08 Employee App
│   ├── employeeapp/                     # Employee application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── models.py                    # Employee models
│   │   ├── permissions.py               # Employee permissions
│   │   ├── serializers.py               # Employee serializers
│   │   ├── signals.py                   # Employee signals
│   │   ├── urls.py                      # Employee URL routing
│   │   ├── views.py                     # Employee API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Employee business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── employee_service.py      # Employee management
│   │   │   ├── schedule_service.py      # Working hours management
│   │   │   └── workload_optimizer.py    # Workload balancing algorithm
│   │   └── tests/                       # Employee tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       └── test_views.py            # View tests

#4.09 Follow App
│   ├── followapp/                       # Follow application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── models.py                    # Follow models
│   │   ├── permissions.py               # Follow permissions
│   │   ├── serializers.py               # Follow serializers
│   │   ├── signals.py                   # Follow signals
│   │   ├── urls.py                      # Follow URL routing
│   │   ├── views.py                     # Follow API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Follow business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── analytics_service.py     # Follow analytics
│   │   │   ├── follow_service.py        # Follow management
│   │   │   └── feed_service.py          # Following feed generator
│   │   └── tests/                       # Follow tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       └── test_views.py            # View tests

#4.10 Geo App
│   ├── geoapp/                          # Geolocation application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── filters.py                   # Geo filters
│   │   ├── models.py                    # Geo models
│   │   ├── serializers.py               # Geo serializers
│   │   ├── signals.py                   # Geo signals
│   │   ├── urls.py                      # Geo URL routing
│   │   ├── views.py                     # Geo API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Geo business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── distance_service.py      # Haversine distance calculation
│   │   │   ├── geo_service.py           # Geo utilities
│   │   │   ├── geospatial_query.py      # R-tree optimized spatial search
│   │   │   ├── routing_service.py       # Routing services
│   │   │   └── travel_time_service.py   # Travel time estimation
│   │   ├── tests/                       # Geo tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Geo utilities
│   │       ├── __init__.py              # Package initialization
│   │       ├── coordinate_utils.py      # Coordinate utilities
│   │       ├── geo_constants.py         # Geo constants
│   │       └── geo_validators.py        # Geo validators

#4.11 Notifications App
│   ├── notificationsapp/                # Notifications application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── consumers.py                 # WebSocket consumers
│   │   ├── models.py                    # Notification models
│   │   ├── routing.py                   # WebSocket routing
│   │   ├── serializers.py               # Notification serializers
│   │   ├── signals.py                   # Notification signals
│   │   ├── tasks.py                     # Notification Celery tasks
│   │   ├── urls.py                      # Notification URL routing
│   │   ├── views.py                     # Notification API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Notification business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── channel_selector.py      # Optimal channel selection algorithm
│   │   │   ├── email_service.py         # Email notifications
│   │   │   ├── notification_service.py  # Notification management
│   │   │   ├── push_service.py          # Push notifications
│   │   │   ├── sms_service.py           # SMS notifications
│   │   │   └── timing_optimizer.py      # Send time optimization
│   │   ├── templates/                   # Notification templates
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── email/                   # Email templates
│   │   │   │   ├── appointment_reminder.html  # Reminder email
│   │   │   │   ├── base_email.html      # Base email template
│   │   │   │   └── queue_update.html    # Queue update email
│   │   │   └── sms/                     # SMS templates
│   │   │       ├── appointment_reminder.txt  # Reminder SMS
│   │   │       └── queue_update.txt     # Queue update SMS
│   │   ├── tests/                       # Notification tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Notification utilities
│   │       ├── __init__.py              # Package initialization
│   │       ├── constants.py             # Notification constants
│   │       └── formatters.py            # Message formatters

#4.12 Package App
│   ├── packageapp/                      # Package application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── filters.py                   # Package filters
│   │   ├── models.py                    # Package models
│   │   ├── permissions.py               # Package permissions
│   │   ├── serializers.py               # Package serializers
│   │   ├── signals.py                   # Package signals
│   │   ├── urls.py                      # Package URL routing
│   │   ├── validators.py                # Package validators
│   │   ├── views.py                     # Package API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Package business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── package_availability.py  # Package availability service
│   │   │   ├── package_booking_service.py  # Package booking service
│   │   │   ├── package_service.py       # Package management
│   │   │   └── bundle_optimizer.py      # Service bundling optimization
│   │   ├── tests/                       # Package tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Package utilities
│   │       ├── __init__.py              # Package initialization
│   │       └── package_utils.py         # Package utilities

#4.13 Payment App
│   ├── payment/                         # Payment application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── constants.py                 # Payment constants
│   │   ├── filters.py                   # Payment filters
│   │   ├── models.py                    # Payment models
│   │   ├── permissions.py               # Payment permissions
│   │   ├── serializers.py               # Payment serializers
│   │   ├── signals.py                   # Payment signals
│   │   ├── tasks.py                     # Payment Celery tasks
│   │   ├── transaction.py               # Transaction handling
│   │   ├── urls.py                      # Payment URL routing
│   │   ├── validators.py                # Payment validators
│   │   ├── views.py                     # Payment API views
│   │   ├── webhooks.py                  # Payment webhooks
│   │   ├── management/                  # Management commands
│   │   │   └── commands/                # Command implementations
│   │   │       ├── __init__.py          # Package initialization
│   │   │       └── test_payments.py     # Payment testing command
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Payment business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── ads_service.py           # Ads payment service
│   │   │   ├── invoice_service.py       # Invoice service
│   │   │   ├── merchant_service.py      # Merchant service
│   │   │   ├── moyasar_service.py       # Moyasar integration
│   │   │   ├── payment_service.py       # Payment processing
│   │   │   ├── payment_method_recommender.py  # Payment method algorithm
│   │   │   ├── fraud_detector.py        # Payment fraud detection
│   │   │   └── subscription_service.py  # Subscription service
│   │   ├── templates/                   # Payment templates
│   │   │   └── payment/                 # Payment templates
│   │   │       ├── ad_invoice.html      # Ad invoice template
│   │   │       ├── merchant_invoice.html  # Merchant invoice
│   │   │       └── subscription_invoice.html  # Subscription invoice
│   │   ├── templatetags/                # Template tags
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── payment_tags.py          # Payment template tags
│   │   ├── tests/                       # Payment tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Payment utilities
│   │       ├── __init__.py              # Package initialization
│   │       └── payment_utils.py         # Payment utilities

#4.14 Queue App
│   ├── queueapp/                        # Queue application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── consumers.py                 # WebSocket consumers
│   │   ├── models.py                    # Queue models
│   │   ├── routing.py                   # WebSocket routing
│   │   ├── serializers.py               # Queue serializers
│   │   ├── signals.py                   # Queue signals
│   │   ├── tasks.py                     # Queue Celery tasks
│   │   ├── urls.py                      # Queue URL routing
│   │   ├── views.py                     # Queue API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Queue business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── hybrid_queue_manager.py  # Hybrid queue-appointment management
│   │   │   ├── queue_optimizer.py       # Queue flow optimization
│   │   │   ├── queue_service.py         # Queue management
│   │   │   ├── ticket_service.py        # Ticket management
│   │   │   └── wait_time_predictor.py   # Advanced wait time algorithm
│   │   ├── tests/                       # Queue tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Queue utilities
│   │       ├── __init__.py              # Package initialization
│   │       └── queue_utils.py           # Queue utilities

#4.15 Queue Me Admin App
│   ├── queueMeAdminApp/                 # QueueMe Admin application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── constants.py                 # Admin constants
│   │   ├── filters.py                   # Admin filters
│   │   ├── models.py                    # Admin models
│   │   ├── permissions.py               # Admin permissions
│   │   ├── serializers.py               # Admin serializers
│   │   ├── tasks.py                     # Admin Celery tasks
│   │   ├── urls.py                      # Admin URL routing
│   │   ├── views.py                     # Admin API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Admin business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── admin_service.py         # Admin service
│   │   │   ├── analytics_service.py     # Admin analytics service
│   │   │   ├── monitoring_service.py    # System monitoring service
│   │   │   ├── settings_service.py      # System settings service
│   │   │   ├── support_service.py       # Support service
│   │   │   └── verification_service.py  # Shop verification service
│   │   ├── templates/                   # Admin templates
│   │   │   └── queueMeAdminApp/         # Admin templates
│   │   │       ├── email/               # Email templates
│   │   │       │   └── verification_approved.html  # Verification email
│   │   │       └── pdf/                 # PDF templates
│   │   │           └── analytics_report.html  # Analytics report
│   │   ├── tests/                       # Admin tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Admin utilities
│   │       ├── __init__.py              # Package initialization
│   │       └── admin_utils.py           # Admin utilities

#4.16 Reels App
│   ├── reelsapp/                        # Reels application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── exceptions.py                # Reels exceptions
│   │   ├── filters.py                   # Reels filters
│   │   ├── models.py                    # Reels models
│   │   ├── permissions.py               # Reels permissions
│   │   ├── serializers.py               # Reels serializers
│   │   ├── signals.py                   # Reels signals
│   │   ├── tasks.py                     # Reels Celery tasks
│   │   ├── urls.py                      # Reels URL routing
│   │   ├── validators.py                # Reels validators
│   │   ├── views.py                     # Reels API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Reels business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── engagement_service.py    # Engagement tracking service
│   │   │   ├── feed_curator.py          # Advanced feed curation algorithm
│   │   │   ├── media_service.py         # Media processing service
│   │   │   ├── recommendation_service.py  # Content recommendation engine
│   │   │   └── reel_service.py          # Reel management
│   │   └── tests/                       # Reels tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       ├── test_services.py         # Service tests
│   │       └── test_views.py            # View tests

#4.17 Report Analytics App
│   ├── reportanalyticsapp/              # Analytics application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── filters.py                   # Analytics filters
│   │   ├── models.py                    # Analytics models
│   │   ├── serializers.py               # Analytics serializers
│   │   ├── signals.py                   # Analytics signals
│   │   ├── tasks.py                     # Analytics Celery tasks
│   │   ├── urls.py                      # Analytics URL routing
│   │   ├── views.py                     # Analytics API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── queries/                     # Database queries
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── business_queries.py      # Business queries
│   │   │   ├── platform_queries.py      # Platform queries
│   │   │   └── specialist_queries.py    # Specialist queries
│   │   ├── services/                    # Analytics business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── analytics_service.py     # Analytics service
│   │   │   ├── anomaly_detector.py      # Anomaly detection algorithm
│   │   │   ├── benchmark_service.py     # Performance benchmarking
│   │   │   ├── dashboard_service.py     # Dashboard service
│   │   │   ├── demand_forecaster.py     # Predictive demand forecasting
│   │   │   └── report_service.py        # Report generation service
│   │   ├── templates/                   # Analytics templates
│   │   │   └── reportanalyticsapp/      # Analytics templates
│   │   │       └── email/               # Email templates
│   │   │           └── report_email.html  # Report email
│   │   ├── tests/                       # Analytics tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Analytics utilities
│   │       ├── __init__.py              # Package initialization
│   │       ├── aggregation_utils.py     # Aggregation utilities
│   │       └── chart_utils.py           # Chart utilities

#4.18 Review App
│   ├── reviewapp/                       # Review application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── filters.py                   # Review filters
│   │   ├── models.py                    # Review models
│   │   ├── permissions.py               # Review permissions
│   │   ├── serializers.py               # Review serializers
│   │   ├── signals.py                   # Review signals
│   │   ├── urls.py                      # Review URL routing
│   │   ├── views.py                     # Review API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Review business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── rating_service.py        # Rating aggregation service
│   │   │   ├── review_service.py        # Review management service
│   │   │   ├── sentiment_analyzer.py    # Review sentiment analysis
│   │   │   ├── weighted_rating.py       # Advanced rating algorithm
│   │   │   └── review_validator.py      # Review validation service
│   │   └── tests/                       # Review tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       ├── test_services.py         # Service tests
│   │       └── test_views.py            # View tests

#4.19 Roles App
│   ├── rolesapp/                        # Roles application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── constants.py                 # Role constants
│   │   ├── decorators.py                # Permission decorators
│   │   ├── models.py                    # Role models
│   │   ├── permissions.py               # Permission classes
│   │   ├── serializers.py               # Role serializers
│   │   ├── signals.py                   # Role signals
│   │   ├── urls.py                      # Role URL routing
│   │   ├── views.py                     # Role API views
│   │   ├── middleware/                  # Role middleware
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── permission_middleware.py # Permission middleware
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Role business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── permission_resolver.py   # Hierarchical permission resolver
│   │   │   ├── permission_service.py    # Permission service
│   │   │   └── role_service.py          # Role management service
│   │   └── tests/                       # Role tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       ├── test_services.py         # Service tests
│   │       └── test_views.py            # View tests

#4.20 Service App
│   ├── serviceapp/                      # Service application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── enums.py                     # Service enumerations
│   │   ├── filters.py                   # Service filters
│   │   ├── models.py                    # Service models
│   │   ├── serializers.py               # Service serializers
│   │   ├── signals.py                   # Service signals
│   │   ├── urls.py                      # Service URL routing
│   │   ├── validators.py                # Service validators
│   │   ├── views.py                     # Service API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Service business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── availability_service.py  # Service availability
│   │   │   ├── duration_refiner.py      # Service time optimization
│   │   │   ├── faq_service.py           # FAQ management
│   │   │   ├── service_matcher.py       # Service-specialist matching
│   │   │   └── service_service.py       # Service management
│   │   └── tests/                       # Service tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       └── test_services.py         # Service tests

#4.21 Shop App
│   ├── shopapp/                         # Shop application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── filters.py                   # Shop filters
│   │   ├── models.py                    # Shop models
│   │   ├── permissions.py               # Shop permissions
│   │   ├── serializers.py               # Shop serializers
│   │   ├── signals.py                   # Shop signals
│   │   ├── urls.py                      # Shop URL routing
│   │   ├── views.py                     # Shop API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Shop business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── hours_optimizer.py       # Operating hours optimization
│   │   │   ├── hours_service.py         # Hours management service
│   │   │   ├── shop_service.py          # Shop management service
│   │   │   ├── shop_visibility.py       # Shop visibility algorithm
│   │   │   └── verification_service.py  # Verification service
│   │   ├── tests/                       # Shop tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Shop utilities
│   │       ├── __init__.py              # Package initialization
│   │       └── shop_utils.py            # Shop utilities

#4.22 Shop Dashboard App
│   ├── shopDashboardApp/                # Shop Dashboard application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── constants.py                 # Dashboard constants
│   │   ├── exceptions.py                # Dashboard exceptions
│   │   ├── filters.py                   # Dashboard filters
│   │   ├── models.py                    # Dashboard models
│   │   ├── permissions.py               # Dashboard permissions
│   │   ├── serializers.py               # Dashboard serializers
│   │   ├── signals.py                   # Dashboard signals
│   │   ├── tasks.py                     # Dashboard Celery tasks
│   │   ├── urls.py                      # Dashboard URL routing
│   │   ├── views.py                     # Dashboard API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Dashboard business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── dashboard_service.py     # Dashboard service
│   │   │   ├── kpi_service.py           # KPI tracking service
│   │   │   ├── settings_service.py      # Settings service
│   │   │   └── stats_service.py         # Statistics service
│   │   ├── templates/                   # Dashboard templates
│   │   │   └── shopDashboardApp/        # Dashboard templates
│   │   │       └── email/               # Email templates
│   │   │           └── scheduled_report.html  # Scheduled report
│   │   ├── tests/                       # Dashboard tests
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── factories.py             # Test factories
│   │   │   ├── test_models.py           # Model tests
│   │   │   ├── test_services.py         # Service tests
│   │   │   └── test_views.py            # View tests
│   │   └── utils/                       # Dashboard utilities
│   │       ├── __init__.py              # Package initialization
│   │       ├── chart_utils.py           # Chart utilities
│   │       └── dashboard_utils.py       # Dashboard utilities

#4.23 Specialists App
│   ├── specialistsapp/                  # Specialists application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── constants.py                 # Specialist constants
│   │   ├── consumers.py                 # WebSocket consumers
│   │   ├── filters.py                   # Specialist filters
│   │   ├── models.py                    # Specialist models
│   │   ├── permissions.py               # Specialist permissions
│   │   ├── routing.py                   # WebSocket routing
│   │   ├── serializers.py               # Specialist serializers
│   │   ├── signals.py                   # Specialist signals
│   │   ├── urls.py                      # Specialist URL routing
│   │   ├── views.py                     # Specialist API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Specialist business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── availability_service.py  # Specialist availability
│   │   │   ├── portfolio_service.py     # Portfolio management
│   │   │   ├── schedule_optimizer.py    # Working hours optimization
│   │   │   ├── specialist_ranker.py     # Specialist ranking algorithm
│   │   │   ├── specialist_recommender.py  # Specialist recommendation engine
│   │   │   └── specialist_service.py    # Specialist management
│   │   └── tests/                       # Specialist tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       ├── test_serializers.py      # Serializer tests
│   │       ├── test_services.py         # Service tests
│   │       └── test_views.py            # View tests

#4.24 Stories App
│   ├── storiesapp/                      # Stories application
│   │   ├── __init__.py                  # Package initialization
│   │   ├── admin.py                     # Admin configuration
│   │   ├── apps.py                      # App configuration
│   │   ├── consumers.py                 # WebSocket consumers
│   │   ├── filters.py                   # Story filters
│   │   ├── models.py                    # Story models
│   │   ├── serializers.py               # Story serializers
│   │   ├── signals.py                   # Story signals
│   │   ├── tasks.py                     # Story Celery tasks
│   │   ├── urls.py                      # Story URL routing
│   │   ├── views.py                     # Story API views
│   │   ├── migrations/                  # Database migrations
│   │   │   ├── __init__.py              # Package initialization
│   │   │   └── 0001_initial.py          # Initial migration
│   │   ├── services/                    # Story business logic
│   │   │   ├── __init__.py              # Package initialization
│   │   │   ├── expiry_manager.py        # 24h expiry management
│   │   │   ├── media_service.py         # Media handling service
│   │   │   ├── story_feed_generator.py  # Story feed algorithm
│   │   │   └── story_service.py         # Story management
│   │   └── tests/                       # Story tests
│   │       ├── __init__.py              # Package initialization
│   │       ├── test_models.py           # Model tests
│   │       └── test_services.py         # Service tests

#4.25 Subscription App
│   └── subscriptionapp/                 # Subscription application
│       ├── __init__.py                  # Package initialization
│       ├── admin.py                     # Admin configuration
│       ├── apps.py                      # App configuration
│       ├── constants.py                 # Subscription constants
│       ├── models.py                    # Subscription models
│       ├── permissions.py               # Subscription permissions
│       ├── serializers.py               # Subscription serializers
│       ├── signals.py                   # Subscription signals
│       ├── tasks.py                     # Subscription Celery tasks
│       ├── urls.py                      # Subscription URL routing
│       ├── views.py                     # Subscription API views
│       ├── webhooks.py                  # Subscription webhooks
│       ├── migrations/                  # Database migrations
│       │   ├── __init__.py              # Package initialization
│       │   └── 0001_initial.py          # Initial migration
│       ├── services/                    # Subscription business logic
│       │   ├── __init__.py              # Package initialization
│       │   ├── feature_service.py       # Feature management
│       │   ├── invoice_service.py       # Invoice service
│       │   ├── plan_recommender.py      # Plan recommendation algorithm
│       │   ├── plan_service.py          # Plan management
│       │   ├── renewal_manager.py       # Automatic renewal system
│       │   ├── subscription_service.py  # Subscription management
│       │   └── usage_monitor.py         # Usage limits enforcement
│       ├── templates/                   # Subscription templates
│       │   └── subscriptionapp/         # Subscription templates
│       │       └── emails/              # Email templates
│       │           ├── payment_receipt.html     # Receipt email
│       │           ├── renewal_reminder.html    # Reminder email
│       │           └── subscription_confirmation.html  # Confirmation
│       ├── tests/                       # Subscription tests
│       │   ├── __init__.py              # Package initialization
│       │   ├── factories.py             # Test factories
│       │   ├── test_models.py           # Model tests
│       │   ├── test_services.py         # Service tests
│       │   └── test_views.py            # View tests
│       └── utils/                       # Subscription utilities
│           ├── __init__.py              # Package initialization
│           └── billing_utils.py         # Billing utilities

#5 Core Utilities and Shared Components
├── core/                                # Core utilities
│   ├── __init__.py                      # Package initialization
│   ├── cache/                           # Caching utilities
│   │   ├── __init__.py                  # Package initialization
│   │   ├── cache_manager.py             # Cache management
│   │   └── key_generator.py             # Cache key generation
│   ├── exceptions/                      # Exception handling
│   │   ├── __init__.py                  # Package initialization
│   │   ├── exception_handler.py         # Global exception handling
│   │   └── custom_exceptions.py         # Custom exceptions
│   ├── localization/                    # Localization utilities
│   │   ├── __init__.py                  # Package initialization
│   │   ├── translator.py                # Translation services
│   │   └── locale_detector.py           # Language detection
│   ├── storage/                         # Storage utilities
│   │   ├── __init__.py                  # Package initialization
│   │   ├── s3_storage.py                # AWS S3 integration
│   │   └── media_processor.py           # Media processing
│   ├── tasks/                           # Task management
│   │   ├── __init__.py                  # Package initialization
│   │   ├── scheduler.py                 # Task scheduling
│   │   └── worker.py                    # Worker implementation
│   └── utils/                           # Miscellaneous utilities
│       ├── __init__.py                  # Package initialization
│       ├── formatters.py                # Data formatting
│       ├── validators.py                # Data validation
│       └── pagination.py                # Pagination utilities

#6 API Versioning and Documentation
├── api/                                 # API versioning
│   ├── v1/                              # API v1
│   │   ├── urls.py                      # API v1 URL routing
│   │   └── views/                       # API v1 views
│   │       └── index.py                 # API documentation
│   └── documentation/                   # API documentation
│       └── swagger.py                   # OpenAPI specification

#7 WebSockets Framework
├── websockets/                          # WebSockets framework
│   ├── __init__.py                      # Package initialization
│   ├── consumers/                       # WebSocket consumers
│   │   ├── __init__.py                  # Package initialization
│   │   ├── queue_status.py              # Queue status updates
│   │   ├── chat.py                      # Live chat WebSocket
│   │   └── notifications.py             # Real-time notifications
│   ├── middleware/                      # WebSocket middleware
│   │   ├── __init__.py                  # Package initialization
│   │   ├── auth_middleware.py           # WebSocket authentication
│   │   └── rate_limiter.py              # WebSocket rate limiting
│   └── routing.py                       # WebSocket URL routing

#8 Configuration and Templates
├── config/                              # Configuration files
│   ├── nginx/                           # Nginx configuration
│   │   └── queueme.conf                 # Nginx site config
│   ├── redis/                           # Redis configuration
│   │   └── redis.conf                   # Redis config
│   └── supervisor/                      # Supervisor configuration
│       └── queueme.conf                 # Supervisor config

#9 Database
├── db/                                  # Database files
│   └── init/                            # Initialization scripts
│       └── init_data.sql                # Initial data

#10 Docker
├── docker/                              # Docker configurations
│   ├── docker-compose.yml               # Docker Compose
│   ├── Dockerfile.backend               # Backend Dockerfile
│   └── Dockerfile.celery                # Celery Dockerfile

#11 Documentation
├── docs/                                # Documentation
│   ├── algorithms/                      # Algorithm documentation
│   │   ├── availability_calculation.md  # Availability algorithm docs
│   │   ├── queue_optimization.md        # Queue algorithms explanation
│   │   └── recommendation_engine.md     # Recommendation system docs
│   ├── api/                             # API documentation
│   │   └── openapi.yaml                 # OpenAPI specification
│   └── architecture/                    # Architecture docs
│       └── overview.md                  # System overview

#12 Internationalization
├── locale/                              # Internationalization
│   ├── ar/                              # Arabic translations
│   │   └── LC_MESSAGES/                 # Message catalogs
│   │       └── django.po                # Translation file
│   └── en/                              # English translations
│       └── LC_MESSAGES/                 # Message catalogs
│           └── django.po                # Translation file

#13 Scripts
├── scripts/                             # Utility scripts
│   ├── backup.sh                        # Backup script
│   ├── deploy.sh                        # Deployment script
│   ├── db_migration/                    # Database migration scripts
│   │   ├── sqlite_to_postgres.py        # SQLite to PostgreSQL migration
│   │   └── data_validator.py            # Data integrity checking
│   ├── seed_data.py                     # Data seeding script
│   └── setup_development.py             # Dev setup script

#14 Static Files
├── static/                              # Static files
│   ├── css/                             # CSS files
│   │   └── base.css                     # Base styles
│   ├── img/                             # Image files
│   └── js/                              # JavaScript files
│       └── main.js                      # Main JS

#15 Templates
├── templates/                           # Global templates
│   ├── base.html                        # Base template
│   ├── index.html                       # Index page
│   ├── email/                           # Email templates
│   │   ├── base_email.html              # Base email template
│   │   └── booking_confirmation.html    # Booking confirmation
│   └── errors/                          # Error pages
│       ├── 404.html                     # 404 page
│       └── 500.html                     # 500 page

#16 Tests
├── tests/                               # Global tests
│   ├── __init__.py                      # Package initialization
│   ├── integration/                     # Integration tests
│   │   └── test_api_integration.py      # API integration tests
│   ├── performance/                     # Performance tests
│   │   └── test_api_performance.py      # API performance tests
│   └── security/                        # Security tests
│       └── test_security.py             # Security tests

#17 Utils
└── utils/                               # Global utilities
    ├── __init__.py                      # Package initialization
    ├── cache_manager.py                 # Cache management
    ├── caching.py                       # Caching utilities
    ├── constants.py                     # Global constants
    ├── converters.py                    # Data converters
    ├── decorators.py                    # Function decorators
    ├── error_views.py                   # Error views
    ├── exceptions.py                    # Custom exceptions
    ├── pagination.py                    # Pagination utilities
    ├── validators.py                    # Global validators
    └── sms/                             # SMS utilities
        ├── __init__.py                  # Package initialization
        └── backends/                    # SMS backends
            ├── console.py               # Console backend
            ├── dummy.py                 # Dummy backend
            └── twilio.py                # Twilio integration
