/**
 * QueueMe Moyasar Payment Integration
 *
 * This module provides integration with Moyasar payment gateway for all three wallet types:
 * - Subscription
 * - Advertising
 * - Merchant (Booking)
 */

class MoyasarPayment {
  /**
   * Initialize payment component
   *
   * @param {string} walletType - Type of wallet: 'subscription', 'ads', or 'merchant'
   * @param {object} config - Configuration options
   */
  constructor(walletType, config = {}) {
    this.walletType = walletType;
    this.config = config;
    this.apiBaseUrl = config.apiBaseUrl || "/api/v1/payments";
    this.amount = 0;
    this.currency = "SAR";
    this.description = "";
    this.metadata = {};
    this.publishableKey = this._getPublishableKey();
    this.callbackUrl = this._getCallbackUrl();
    this.form = null;
    this.submitButton = null;
    this.errorElement = null;
    this.successCallback = null;
    this.errorCallback = null;
  }

  /**
   * Get the appropriate publishable key based on wallet type
   *
   * @returns {string} Publishable key
   */
  _getPublishableKey() {
    switch (this.walletType) {
      case "subscription":
        return window.MOYASAR_SUB_PUBLIC || this.config.subscriptionKey;
      case "ads":
        return window.MOYASAR_ADS_PUBLIC || this.config.adsKey;
      case "merchant":
      default:
        return window.MOYASAR_MER_PUBLIC || this.config.merchantKey;
    }
  }

  /**
   * Get the appropriate callback URL based on wallet type
   *
   * @returns {string} Callback URL
   */
  _getCallbackUrl() {
    switch (this.walletType) {
      case "subscription":
        return (
          window.MOYASAR_SUB_CALLBACK_URL || this.config.subscriptionCallback
        );
      case "ads":
        return window.MOYASAR_ADS_CALLBACK_URL || this.config.adsCallback;
      case "merchant":
      default:
        return window.MOYASAR_MER_CALLBACK_URL || this.config.merchantCallback;
    }
  }

  /**
   * Initialize the payment form
   *
   * @param {string} elementId - ID of the HTML element to contain the form
   * @param {object} options - Form options
   */
  initForm(elementId, options = {}) {
    const formElement = document.getElementById(elementId);
    if (!formElement) {
      console.error(`Element with ID ${elementId} not found`);
      return;
    }

    // Default options
    const defaultOptions = {
      amount: this.amount,
      currency: this.currency,
      description: this.description,
      publishable_key: this.publishableKey,
      callback_url: this.callbackUrl,
      methods: ["creditcard", "applepay", "stcpay"],
      source_data: {
        type: "creditcard",
      },
    };

    // Merge with provided options
    const formOptions = { ...defaultOptions, ...options };

    // Create form
    this.form = Moyasar.createForm(formElement, formOptions);

    // Add event listeners
    this.form.on("submit", this._handleSubmit.bind(this));
    this.form.on("error", this._handleError.bind(this));
  }

  /**
   * Handle form submission
   *
   * @param {object} payment - Payment data from Moyasar
   */
  _handleSubmit(payment) {
    // Convert to halala (SAR * 100)
    const amountHalala = Math.round(this.amount * 100);

    // The payment succeeded, now create a record in our backend
    fetch(this.apiBaseUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": this._getCsrfToken(),
      },
      body: JSON.stringify({
        amount: this.amount, // Our backend expects SAR, not halala
        currency: this.currency,
        source: payment.source.id,
        description: this.description,
        wallet_type: this.walletType,
        metadata: this.metadata,
        payment_id: payment.id,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          if (this.successCallback) {
            this.successCallback(data);
          }
        } else {
          this._showError(data.message || "Payment failed");
          if (this.errorCallback) {
            this.errorCallback(data);
          }
        }
      })
      .catch((error) => {
        this._showError("Network error: " + error.message);
        if (this.errorCallback) {
          this.errorCallback({ success: false, message: error.message });
        }
      });
  }

  /**
   * Handle form errors
   *
   * @param {object} error - Error data from Moyasar
   */
  _handleError(error) {
    this._showError(error.message || "Payment error");
    if (this.errorCallback) {
      this.errorCallback(error);
    }
  }

  /**
   * Show error message
   *
   * @param {string} message - Error message to display
   */
  _showError(message) {
    if (this.errorElement) {
      this.errorElement.textContent = message;
      this.errorElement.style.display = "block";
    } else {
      console.error(message);
    }
  }

  /**
   * Get CSRF token from cookies
   *
   * @returns {string} CSRF token
   */
  _getCsrfToken() {
    const name = "csrftoken";
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /**
   * Configure payment details
   *
   * @param {object} options - Payment options
   */
  configure(options) {
    if (options.amount !== undefined) {
      this.amount = options.amount;
    }
    if (options.currency) {
      this.currency = options.currency;
    }
    if (options.description) {
      this.description = options.description;
    }
    if (options.metadata) {
      this.metadata = options.metadata;
    }
    if (options.errorElement) {
      this.errorElement = document.getElementById(options.errorElement);
    }
    if (typeof options.onSuccess === "function") {
      this.successCallback = options.onSuccess;
    }
    if (typeof options.onError === "function") {
      this.errorCallback = options.onError;
    }

    // Update form if already initialized
    if (this.form) {
      this.form.amount = Math.round(this.amount * 100); // Convert to halala
      this.form.currency = this.currency;
      this.form.description = this.description;
    }
  }
}

/**
 * Factory function to create a payment component for a specific wallet
 *
 * @param {string} walletType - Type of wallet: 'subscription', 'ads', or 'merchant'
 * @param {object} config - Configuration options
 * @returns {MoyasarPayment} Payment component
 */
function createMoyasarPayment(walletType, config = {}) {
  return new MoyasarPayment(walletType, config);
}

// Export as global variables for easy use
window.MoyasarPayment = MoyasarPayment;
window.createMoyasarPayment = createMoyasarPayment;
