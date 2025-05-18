/**
 * QueueMe Advertising Payment Component
 *
 * This module provides a specialized interface for handling ad payments
 * using the Moyasar payment gateway.
 */

class AdPayment {
  /**
   * Initialize the advertising payment component
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
    this.adData = null;
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

    // Create payment handler for ads wallet
    this.payment = window.createMoyasarPayment("ads", {
      apiBaseUrl: "/api/v1/payment/process-ad/",
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
   * Process an ad payment
   *
   * @param {object} adData - Ad data
   * @param {number} adData.amount - Ad amount
   * @param {string} adData.adId - Ad ID
   * @param {string} adData.adName - Ad name
   * @param {string} adData.adType - Ad type (banner, video, etc.)
   * @param {string} adData.duration - Ad duration (days)
   * @param {string} adData.description - Ad description
   * @param {string} companyId - Company ID
   */
  processPayment(adData, companyId) {
    if (!this.initialized) {
      this.initialize();
    }

    this.adData = adData;
    this.companyId = companyId;

    // Configure payment details
    this.payment.configure({
      amount: adData.amount,
      currency: "SAR",
      description: adData.description || `Ad campaign: ${adData.adName}`,
      metadata: {
        company_id: companyId,
        ad_id: adData.adId,
        ad_name: adData.adName,
        ad_type: adData.adType,
        duration: adData.duration,
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
    console.log("Ad payment successful", response);

    // Redirect to success page
    window.location.href = `/marketing/ad/complete/${response.transaction_id}`;
  }

  /**
   * Default error callback
   *
   * @param {object} error - Error data
   */
  _defaultErrorCallback(error) {
    console.error("Ad payment failed", error);

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
window.AdPayment = AdPayment;
