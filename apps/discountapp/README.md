# Discount App - Queue Me Platform

## Overview

The Discount App module for the Queue Me platform enables businesses to create and manage various types of discounts, promotional campaigns, and coupons. It provides a sophisticated discount system with support for percentage and fixed amount discounts, service-specific targeting, coupon codes, and promotional campaigns.

## Features

- **Service Discounts**: Create discounts for specific services, categories, or all services
- **Coupon Codes**: Generate unique coupon codes with multiple validation rules
- **Promotional Campaigns**: Bundle discounts and coupons into time-limited campaigns
- **Referral Program**: Built-in support for customer referral incentives
- **Discount Stacking**: Configure whether discounts can be combined with others
- **Multi-language Support**: Full localization support for Arabic and English
- **Validity Control**: Time-based expiration, usage limits, and minimum purchase requirements

## Key Components

### Models

- **ServiceDiscount**: Discounts directly applied to services
- **Coupon**: Code-based discounts that customers can apply
- **CouponUsage**: Tracks when and how coupons are used
- **PromotionalCampaign**: Groups related discounts and coupons

### Services

- **CouponService**: Handles coupon creation, validation, and application
- **DiscountService**: Manages service discounts and discount calculations
- **PromotionService**: Manages promotional campaigns and referral programs
- **EligibilityService**: Determines eligibility for discounts and coupons

## API Endpoints

### Service Discounts

- `GET /api/discounts/service-discounts/`: List all service discounts
- `POST /api/discounts/service-discounts/`: Create a new service discount
- `GET /api/discounts/service-discounts/{id}/`: Get discount details
- `PUT/PATCH /api/discounts/service-discounts/{id}/`: Update a discount
- `DELETE /api/discounts/service-discounts/{id}/`: Delete a discount
- `GET /api/discounts/service-discounts/active/`: List active discounts

### Coupons

- `GET /api/discounts/coupons/`: List all coupons
- `POST /api/discounts/coupons/`: Create a new coupon
- `GET /api/discounts/coupons/{id}/`: Get coupon details
- `PUT/PATCH /api/discounts/coupons/{id}/`: Update a coupon
- `DELETE /api/discounts/coupons/{id}/`: Delete a coupon
- `POST /api/discounts/coupons/validate/`: Validate a coupon code
- `POST /api/discounts/coupons/apply/`: Apply a coupon to a booking
- `POST /api/discounts/coupons/generate/`: Generate coupons (single or bulk)
- `GET /api/discounts/coupons/available/`: List available coupons for the current user

### Promotional Campaigns

- `GET /api/discounts/campaigns/`: List all campaigns
- `POST /api/discounts/campaigns/`: Create a new campaign
- `GET /api/discounts/campaigns/{id}/`: Get campaign details
- `PUT/PATCH /api/discounts/campaigns/{id}/`: Update a campaign
- `DELETE /api/discounts/campaigns/{id}/`: Delete a campaign
- `GET /api/discounts/campaigns/active/`: List active campaigns
- `POST /api/discounts/campaigns/create-referral/`: Create a referral campaign

### Discount Calculations

- `POST /api/discounts/calculations/calculate/`: Calculate discount for a price

## Usage Examples

### Creating a Service Discount

```python
# Using the DiscountService
discount = DiscountService.create_service_discount(
    shop=shop,
    name="Weekend Special",
    discount_type="percentage",
    value=15,
    start_date=timezone.now(),
    end_date=timezone.now() + datetime.timedelta(days=2),
    apply_to_all_services=False,
    services=[service1, service2]
)
