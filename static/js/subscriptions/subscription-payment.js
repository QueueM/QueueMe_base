/**
 * QueueMe Subscription Payment Component
 *
 * This module provides a specialized interface for handling subscription payments
 * using the Moyasar payment gateway.
 */

class SubscriptionPayment {
  /**
   * Initialize the subscription payment component
   *
   * @param {string} formContainerId - ID of the HTML element to contain the form
   * @param {string} errorElementId - ID of the HTML element for error messages
   * @param {function} onSuccess - Callback for successful payment
   * @param {function} onError - Callback for payment errors
   */
  constructor(formContainerId, errorElementId, onSuccess, onError) {
    this.formContainerId = formContainerId;
    this.errorElementId = errorElementId;
    this.onSuccess = onSuccess;
    this.onError = onError;
    this.payment = null;
    this.subscriptionData = null;
    this.companyId = null;
    this.initialized = false;
  }

  /**
   * Initialize the payment component
   */
  initialize() {
    if (!window.MoyasarPayment) {
      console.error("MoyasarPayment is not loaded");
      return;
    }

    // Create payment handler for subscription wallet
    this.payment = window.createMoyasarPayment("subscription", {
      apiBaseUrl: "/api/v1/payment/process-subscription/",
    });

    // Set callbacks
    this.payment.configure({
      errorElement: this.errorElementId,
      onSuccess: this.onSuccess || this._defaultSuccessCallback.bind(this),
      onError: this.onError || this._defaultErrorCallback.bind(this),
    });

    this.initialized = true;
  }

  /**
   * Process a subscription payment
   *
   * @param {object} subscriptionData - Subscription data
   * @param {number} subscriptionData.amount - Subscription amount
   * @param {string} subscriptionData.planId - Subscription plan ID
   * @param {string} subscriptionData.planName - Subscription plan name
   * @param {string} subscriptionData.period - Subscription period (monthly, annual)
   * @param {string} subscriptionData.description - Subscription description
   * @param {string} companyId - Company ID
   */
  processPayment(subscriptionData, companyId) {
    if (!this.initialized) {
      this.initialize();
    }

    this.subscriptionData = subscriptionData;
    this.companyId = companyId;

    // Configure payment details
    this.payment.configure({
      amount: subscriptionData.amount,
      currency: "SAR",
      description:
        subscriptionData.description ||
        `Subscription to ${subscriptionData.planName}`,
      metadata: {
        company_id: companyId,
        plan_id: subscriptionData.planId,
        plan_name: subscriptionData.planName,
        period: subscriptionData.period,
      },
    });

    // Initialize the payment form
    this.payment.initForm(this.formContainerId);
  }

  /**
   * Default success callback
   *
   * @param {object} response - Response from server
   */
  _defaultSuccessCallback(response) {
    console.log("Subscription payment successful", response);

    // Redirect to success page
    window.location.href = `/subscriptions/complete/${response.transaction_id}`;
  }

  /**
   * Default error callback
   *
   * @param {object} error - Error data
   */
  _defaultErrorCallback(error) {
    console.error("Subscription payment failed", error);

    // Show error in the UI
    const errorElement = document.getElementById(this.errorElementId);
    if (errorElement) {
      errorElement.textContent =
        error.message || "Payment failed. Please try again.";
      errorElement.style.display = "block";
    }
  }
}

// Export as global variable
window.SubscriptionPayment = SubscriptionPayment;
