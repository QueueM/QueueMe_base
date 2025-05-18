# QueueMe Load Testing Suite

This directory contains load testing scripts for the QueueMe application. The tests are designed to simulate real-world usage patterns and identify performance bottlenecks.

## Prerequisites

- Python 3.8+
- Locust load testing framework

## Installation

```bash
pip install locust
```

## Available Tests

1. **Booking Load Test**: Simulates users browsing services, checking availability, and making/canceling bookings
2. **Payment Load Test**: Simulates payment processing, refunds, and payment method management

## Running the Tests

### Local Testing

To run a load test locally:

```bash
# Run booking tests
locust -f booking_load_test.py

# Run payment tests
locust -f payment_load_test.py

# Run both tests together
locust -f booking_load_test.py -f payment_load_test.py
```

Then open your browser to http://localhost:8089 to configure and start the test.

### Distributed Testing

For larger-scale testing:

1. Start a master node:
```bash
locust -f booking_load_test.py --master
```

2. Start worker nodes:
```bash
locust -f booking_load_test.py --worker --master-host=<MASTER_IP>
```

## Test Parameters

When running tests through the web UI, you'll need to configure:

- **Number of users**: Total number of simulated users
- **Spawn rate**: How quickly to add new users (users/second)
- **Host**: The target environment (e.g., https://staging.queueme.com)

## Recommended Test Scenarios

### Light Load
- 50 concurrent users
- 5 users/second spawn rate
- Run for 10 minutes

### Medium Load
- 200 concurrent users
- 10 users/second spawn rate
- Run for 15 minutes

### Heavy Load
- 500 concurrent users
- 20 users/second spawn rate
- Run for 20 minutes

### Peak Load
- 1000 concurrent users
- 50 users/second spawn rate
- Run for 30 minutes

## Analyzing Results

Locust provides real-time metrics including:
- Request success/failure rates
- Response times (min, max, average, median)
- Requests per second

Look for:
- Increasing response times as load increases
- Failed requests
- Database or cache bottlenecks

## Monitoring During Tests

When running tests, monitor:
- Server CPU, memory, and disk I/O
- Database connection pool usage
- Redis memory usage
- Application error logs

## Common Issues

If you encounter high failure rates, check:
- Database connection limits
- Redis connection limits
- API rate limiting
- Web server worker configuration
