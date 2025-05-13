# QueueMe Pre-Production Test Plan

This document outlines the comprehensive testing strategy for the new Moyasar payment integration with multiple wallets and Firebase notification system before deployment to production.

## 1. Core Functionality Tests

### 1.1 Moyasar Payment Integration

#### Unit Tests
- [x] Test MoyasarService with different wallet configurations
- [x] Test payment creation for each wallet type (subscription, ads, merchant)
- [x] Test payment status checking
- [x] Test webhook processing for each wallet type
- [x] Test refund processing

#### Integration Tests
- [x] Test complete payment flow (create payment → process webhook → update status)
- [x] Test proper wallet selection based on transaction type
- [x] Test handling of successful payments
- [x] Test handling of failed payments
- [x] Test connection between payments and related objects (subscriptions, ads, bookings)

### 1.2 Firebase Notification Integration

#### Unit Tests
- [x] Test Firebase SMS functionality
- [x] Test Firebase Cloud Messaging for push notifications
- [x] Test notification template rendering
- [x] Test handling of notification failures

#### Integration Tests
- [x] Test notification delivery after payment events
- [x] Test respecting user notification preferences
- [x] Test notification delivery to multiple devices
- [x] Test delivery status tracking

## 2. Manual Testing Checklist

### 2.1 Payment Testing

- [ ] **Subscription Payments**
  - [ ] Create a test subscription plan
  - [ ] Initiate payment with credit card
  - [ ] Verify redirection to Moyasar payment page
  - [ ] Complete payment on Moyasar test environment
  - [ ] Verify subscription status updates
  - [ ] Verify notification received

- [ ] **Advertisement Payments**
  - [ ] Create a test ad campaign
  - [ ] Initiate payment with credit card
  - [ ] Complete payment on Moyasar test environment
  - [ ] Verify ad status updates
  - [ ] Verify notification received

- [ ] **Merchant/Booking Payments**
  - [ ] Create a test booking
  - [ ] Initiate payment
  - [ ] Complete payment
  - [ ] Verify booking status updates
  - [ ] Verify notification received

- [ ] **Payment Methods**
  - [ ] Test credit card payments
  - [ ] Test saving payment methods (if applicable)
  - [ ] Test Apple Pay (if applicable)
  - [ ] Test STC Pay (if applicable)
  - [ ] Test payment method management

### 2.2 Notification Testing

- [ ] **SMS Notifications**
  - [ ] Test SMS delivery for payment events
  - [ ] Verify message formatting
  - [ ] Test international number formats
  - [ ] Test handling of invalid numbers

- [ ] **Push Notifications**
  - [ ] Test push delivery on Android devices
  - [ ] Test push delivery on iOS devices
  - [ ] Verify notification actions work correctly
  - [ ] Test handling device with invalid tokens

- [ ] **Email Notifications**
  - [ ] Test email delivery for payment events
  - [ ] Verify email formatting
  - [ ] Test handling of undeliverable emails

- [ ] **Notification Preferences**
  - [ ] Test opting out of specific notification types
  - [ ] Test notification preferences per user

## 3. Security Tests

- [ ] **Payment Security**
  - [ ] Verify API keys are securely stored
  - [ ] Verify PCI compliance for card handling
  - [ ] Test webhook authentication
  - [ ] Test transaction encryption

- [ ] **Firebase Security**
  - [ ] Verify Firebase credentials are securely stored
  - [ ] Test Firebase authentication
  - [ ] Verify notification payload encryption

## 4. Performance Tests

- [ ] **Payment Processing**
  - [ ] Test high volume of concurrent payments
  - [ ] Measure payment processing time
  - [ ] Test webhook handling under load

- [ ] **Notification Delivery**
  - [ ] Test bulk notification sending
  - [ ] Measure notification delivery time
  - [ ] Test handling of notification queuing

## 5. Error Handling Tests

- [ ] **Payment Errors**
  - [ ] Test handling of declined payments
  - [ ] Test handling of expired sessions
  - [ ] Test handling of connection failures
  - [ ] Test handling of invalid payment data

- [ ] **Notification Errors**
  - [ ] Test handling of failed notification delivery
  - [ ] Test retry mechanisms
  - [ ] Test fallback notification methods

## 6. Regression Testing

- [ ] **Existing Features**
  - [ ] Test all booking flows
  - [ ] Test all existing payment features
  - [ ] Test existing notification systems

## 7. Monitoring Plan

- [ ] **Payment Monitoring**
  - [ ] Set up Moyasar dashboard monitoring
  - [ ] Configure payment failure alerts
  - [ ] Track transaction success rates

- [ ] **Notification Monitoring**
  - [ ] Set up Firebase Console monitoring
  - [ ] Configure notification failure alerts
  - [ ] Track notification delivery rates

## 8. Production Deployment Checklist

- [ ] Verify all tests pass in testing environment
- [ ] Configure production Moyasar credentials for all wallets
- [ ] Configure production Firebase credentials
- [ ] Set up production webhooks
- [ ] Verify SSL certificates
- [ ] Perform security audit
- [ ] Create rollback plan
- [ ] Schedule deployment during low-traffic period
- [ ] Inform customer support team of new features
- [ ] Monitor payment and notification metrics after deployment

## 9. Post-Deployment Verification

- [ ] Verify first real payments process correctly
- [ ] Verify notifications are delivered correctly
- [ ] Check error logs for unexpected issues
- [ ] Verify metrics collection is working
- [ ] Conduct user acceptance testing with real users
