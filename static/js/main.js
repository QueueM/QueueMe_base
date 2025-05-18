/**
 * Queue Me - Main JavaScript
 * Sophisticated functionality including RTL support, language switching,
 * real-time updates, and advanced form handling
 */

// IIFE to avoid polluting global namespace
(function () {
  "use strict";

  // Global application object
  window.QueueMe = window.QueueMe || {};

  // Configuration
  const config = {
    apiBaseUrl: "/api",
    wsBaseUrl:
      window.location.protocol === "https:"
        ? "wss://" + window.location.host
        : "ws://" + window.location.host,
    defaultLang: "en",
    supportedLangs: ["en", "ar"],
    rtlLangs: ["ar"],
    dateTimeFormat: {
      en: {
        date: { year: "numeric", month: "short", day: "numeric" },
        time: { hour: "numeric", minute: "numeric", hour12: true },
      },
      ar: {
        date: { year: "numeric", month: "short", day: "numeric" },
        time: { hour: "numeric", minute: "numeric", hour12: true },
      },
    },
    toastDuration: 5000, // milliseconds
    maxRetryAttempts: 5,
    retryDelay: 2000, // milliseconds
    cacheTTL: 5 * 60 * 1000, // 5 minutes in milliseconds
  };

  // Cache storage
  const cache = {
    data: {},
    set: function (key, value, ttl = config.cacheTTL) {
      const now = new Date().getTime();
      this.data[key] = {
        value: value,
        expiry: now + ttl,
      };
    },
    get: function (key) {
      const now = new Date().getTime();
      const item = this.data[key];

      if (!item) return null;
      if (now > item.expiry) {
        delete this.data[key];
        return null;
      }

      return item.value;
    },
    invalidate: function (key) {
      if (key) {
        delete this.data[key];
      } else {
        this.data = {};
      }
    },
  };

  // Utility functions
  const util = {
    // DOM manipulation helpers
    $(selector) {
      return document.querySelector(selector);
    },

    $$(selector) {
      return document.querySelectorAll(selector);
    },

    createElement(tag, attributes = {}, textContent = "") {
      const element = document.createElement(tag);

      for (const [key, value] of Object.entries(attributes)) {
        if (key === "class") {
          element.className = value;
        } else {
          element.setAttribute(key, value);
        }
      }

      if (textContent) {
        element.textContent = textContent;
      }

      return element;
    },

    // Event handling
    on(element, event, handler, options = {}) {
      if (typeof element === "string") {
        element = this.$(element);
      }

      if (!element) return;

      element.addEventListener(event, handler, options);
    },

    delegate(element, eventType, selector, handler) {
      if (typeof element === "string") {
        element = this.$(element);
      }

      if (!element) return;

      element.addEventListener(eventType, function (event) {
        let target = event.target;

        while (target && target !== element) {
          if (target.matches(selector)) {
            handler.call(target, event);
            break;
          }
          target = target.parentNode;
        }
      });
    },

    // AJAX helpers
    async fetchJSON(url, options = {}) {
      // Set default headers
      options.headers = options.headers || {};
      options.headers["Content-Type"] =
        options.headers["Content-Type"] || "application/json";
      options.headers["Accept"] =
        options.headers["Accept"] || "application/json";

      // Add authorization token if available
      const token = auth.getToken();
      if (token) {
        options.headers["Authorization"] = `Bearer ${token}`;
      }

      // Add current language
      options.headers["Accept-Language"] = QueueMe.lang.current;

      try {
        const response = await fetch(url, options);

        // Handle unauthorized responses
        if (response.status === 401) {
          auth.logout();
          return null;
        }

        // Parse JSON response
        try {
          const data = await response.json();
          return {
            ok: response.ok,
            status: response.status,
            data: data,
          };
        } catch (e) {
          return {
            ok: response.ok,
            status: response.status,
            data: null,
          };
        }
      } catch (error) {
        console.error("Network error:", error);
        return {
          ok: false,
          status: 0,
          data: null,
          error: error.message,
        };
      }
    },

    async get(url, params = {}, cacheKey = null) {
      // Check cache first if cache key provided
      if (cacheKey) {
        const cachedData = cache.get(cacheKey);
        if (cachedData) return cachedData;
      }

      // Build URL with query parameters
      const queryString = new URLSearchParams(params).toString();
      const fullUrl = queryString ? `${url}?${queryString}` : url;

      const result = await this.fetchJSON(fullUrl, { method: "GET" });

      // Cache successful result if cache key provided
      if (cacheKey && result.ok) {
        cache.set(cacheKey, result);
      }

      return result;
    },

    async post(url, data = {}) {
      return await this.fetchJSON(url, {
        method: "POST",
        body: JSON.stringify(data),
      });
    },

    async put(url, data = {}) {
      return await this.fetchJSON(url, {
        method: "PUT",
        body: JSON.stringify(data),
      });
    },

    async delete(url) {
      return await this.fetchJSON(url, { method: "DELETE" });
    },

    // Date and time helpers
    formatDate(dateString, locale = QueueMe.lang.current) {
      if (!dateString) return "";

      const date = new Date(dateString);
      const options =
        config.dateTimeFormat[locale]?.date || config.dateTimeFormat.en.date;

      return new Intl.DateTimeFormat(locale, options).format(date);
    },

    formatTime(timeString, locale = QueueMe.lang.current) {
      if (!timeString) return "";

      let date;
      if (typeof timeString === "string" && timeString.includes(":")) {
        // Handle time string like "14:30:00"
        const [hours, minutes] = timeString.split(":");
        date = new Date();
        date.setHours(parseInt(hours, 10));
        date.setMinutes(parseInt(minutes, 10));
      } else {
        date = new Date(timeString);
      }

      const options =
        config.dateTimeFormat[locale]?.time || config.dateTimeFormat.en.time;

      return new Intl.DateTimeFormat(locale, options).format(date);
    },

    formatDateTime(dateTimeString, locale = QueueMe.lang.current) {
      if (!dateTimeString) return "";

      const date = new Date(dateTimeString);
      const dateOptions =
        config.dateTimeFormat[locale]?.date || config.dateTimeFormat.en.date;
      const timeOptions =
        config.dateTimeFormat[locale]?.time || config.dateTimeFormat.en.time;

      const formattedDate = new Intl.DateTimeFormat(locale, dateOptions).format(
        date,
      );
      const formattedTime = new Intl.DateTimeFormat(locale, timeOptions).format(
        date,
      );

      return `${formattedDate}, ${formattedTime}`;
    },

    // Mobile detection
    isMobile() {
      return window.innerWidth < 768;
    },

    // Toast notifications
    showToast(message, type = "info", duration = config.toastDuration) {
      const toastContainer =
        this.$(".toast-container") || this._createToastContainer();

      const toast = this.createElement("div", {
        class: `toast toast-${type}`,
      });

      toast.innerHTML = `
          <div class="toast-content">
            <span class="toast-message">${message}</span>
            <button class="toast-close">&times;</button>
          </div>
        `;

      const closeButton = toast.querySelector(".toast-close");
      closeButton.addEventListener("click", () => {
        toast.classList.add("toast-hide");
        setTimeout(() => {
          toastContainer.removeChild(toast);
          if (toastContainer.children.length === 0) {
            document.body.removeChild(toastContainer);
          }
        }, 300);
      });

      toastContainer.appendChild(toast);

      // Auto close after duration
      if (duration > 0) {
        setTimeout(() => {
          if (toast.parentNode) {
            toast.classList.add("toast-hide");
            setTimeout(() => {
              if (toast.parentNode) {
                toastContainer.removeChild(toast);
                if (toastContainer.children.length === 0) {
                  document.body.removeChild(toastContainer);
                }
              }
            }, 300);
          }
        }, duration);
      }

      return toast;
    },

    _createToastContainer() {
      const container = this.createElement("div", {
        class: "toast-container",
      });
      document.body.appendChild(container);
      return container;
    },

    // Form validation
    validateForm(formElement) {
      const form =
        typeof formElement === "string" ? this.$(formElement) : formElement;
      if (!form) return { valid: false, errors: { global: "Form not found" } };

      const errors = {};
      let valid = true;

      try {
        // Get all form inputs with validation attributes
        const inputs = form.querySelectorAll("[data-validate]");

        if (inputs.length === 0) {
          // No validation rules found, consider form valid
          return { valid: true, errors: {} };
        }

        inputs.forEach((input) => {
          const validations = (input.dataset.validate || "")
            .split(" ")
            .filter(Boolean);
          const fieldName = input.name || input.id;
          const value =
            input.type === "checkbox" ? input.checked : input.value.trim();

          // Skip validation for disabled or hidden fields
          if (
            input.disabled ||
            input.type === "hidden" ||
            input.style.display === "none" ||
            input.style.visibility === "hidden"
          ) {
            return;
          }

          // Clear previous error state
          this._clearFieldError(input);

          // Check validations - return on first error for each field
          for (const validation of validations) {
            // Required field check
            if (validation === "required" && !value) {
              this._setFieldError(
                input,
                fieldName,
                "This field is required",
                errors,
              );
              valid = false;
              break;
            }

            // Skip other validations if field is empty and not required
            if (!value && !validations.includes("required")) {
              continue;
            }

            // Email validation
            if (validation === "email" && !this._validateEmail(value)) {
              this._setFieldError(
                input,
                fieldName,
                "Please enter a valid email address",
                errors,
              );
              valid = false;
              break;
            }

            // Phone validation
            if (validation === "phone" && !this._validatePhone(value)) {
              this._setFieldError(
                input,
                fieldName,
                "Please enter a valid phone number",
                errors,
              );
              valid = false;
              break;
            }

            // Password validation
            if (validation === "password" && !this._validatePassword(value)) {
              this._setFieldError(
                input,
                fieldName,
                "Password must be at least 8 characters long and contain uppercase, lowercase, number and special character",
                errors,
              );
              valid = false;
              break;
            }

            // Min length validation
            if (validation.startsWith("min:")) {
              const min = parseInt(validation.split(":")[1], 10);
              if (isNaN(min)) {
                console.error(`Invalid min validation value: ${validation}`);
              } else if (value.length < min) {
                this._setFieldError(
                  input,
                  fieldName,
                  `Must be at least ${min} characters`,
                  errors,
                );
                valid = false;
                break;
              }
            }

            // Max length validation
            if (validation.startsWith("max:")) {
              const max = parseInt(validation.split(":")[1], 10);
              if (isNaN(max)) {
                console.error(`Invalid max validation value: ${validation}`);
              } else if (value.length > max) {
                this._setFieldError(
                  input,
                  fieldName,
                  `Must be at most ${max} characters`,
                  errors,
                );
                valid = false;
                break;
              }
            }

            // Numeric validation
            if (validation === "numeric" && !this._validateNumeric(value)) {
              this._setFieldError(
                input,
                fieldName,
                "Must contain only numbers",
                errors,
              );
              valid = false;
              break;
            }

            // Alpha validation
            if (validation === "alpha" && !this._validateAlpha(value)) {
              this._setFieldError(
                input,
                fieldName,
                "Must contain only letters",
                errors,
              );
              valid = false;
              break;
            }

            // Alphanumeric validation
            if (
              validation === "alphanumeric" &&
              !this._validateAlphanumeric(value)
            ) {
              this._setFieldError(
                input,
                fieldName,
                "Must contain only letters and numbers",
                errors,
              );
              valid = false;
              break;
            }

            // Pattern validation
            if (validation.startsWith("pattern:")) {
              const pattern = validation.split(":")[1];
              if (!this._validatePattern(value, pattern)) {
                const errorMessage =
                  input.dataset.patternError || "Invalid format";
                this._setFieldError(input, fieldName, errorMessage, errors);
                valid = false;
                break;
              }
            }

            // Field matching validation
            if (validation.startsWith("match:")) {
              const matchFieldSelector = validation.split(":")[1];
              const matchField = form.querySelector(
                `[name="${matchFieldSelector}"], #${matchFieldSelector}`,
              );

              if (!matchField) {
                console.error(
                  `Cannot find matching field: ${matchFieldSelector}`,
                );
              } else if (value !== matchField.value) {
                const errorMessage =
                  input.dataset.matchError || "Fields do not match";
                this._setFieldError(input, fieldName, errorMessage, errors);
                valid = false;
                break;
              }
            }

            // Date validation
            if (validation === "date" && !this._validateDate(value)) {
              this._setFieldError(
                input,
                fieldName,
                "Please enter a valid date",
                errors,
              );
              valid = false;
              break;
            }

            // Future date validation
            if (
              validation === "future_date" &&
              !this._validateFutureDate(value)
            ) {
              this._setFieldError(
                input,
                fieldName,
                "Please enter a future date",
                errors,
              );
              valid = false;
              break;
            }

            // Custom validation via data attribute
            if (
              validation === "custom" &&
              typeof window.customValidators === "object"
            ) {
              const validatorName = input.dataset.validator;
              if (
                validatorName &&
                typeof window.customValidators[validatorName] === "function"
              ) {
                const result = window.customValidators[validatorName](
                  value,
                  input,
                  form,
                );
                if (result !== true) {
                  const errorMessage =
                    result || input.dataset.customError || "Invalid value";
                  this._setFieldError(input, fieldName, errorMessage, errors);
                  valid = false;
                  break;
                }
              } else {
                console.error(`Custom validator not found: ${validatorName}`);
              }
            }
          }
        });

        // Run form-level validations if defined
        if (
          valid &&
          typeof window.formValidators === "object" &&
          form.dataset.formValidator
        ) {
          const formValidatorName = form.dataset.formValidator;
          if (
            formValidatorName &&
            typeof window.formValidators[formValidatorName] === "function"
          ) {
            const formData = this._getFormData(form);
            const result = window.formValidators[formValidatorName](
              formData,
              form,
            );
            if (result !== true) {
              if (typeof result === "object") {
                // Field-specific errors
                Object.keys(result).forEach((field) => {
                  const input = form.querySelector(
                    `[name="${field}"], #${field}`,
                  );
                  if (input) {
                    this._setFieldError(input, field, result[field], errors);
                  } else {
                    errors[field] = result[field];
                  }
                });
              } else {
                // Global form error
                errors.global = result || "Validation failed";
                this._setFormError(form, errors.global);
              }
              valid = false;
            }
          }
        }

        return { valid, errors };
      } catch (error) {
        console.error("Form validation error:", error);
        return {
          valid: false,
          errors: {
            global:
              "An error occurred during validation. Please check your form and try again.",
          },
        };
      }
    },

    _setFieldError(input, fieldName, message, errors) {
      // Add error class to input
      input.classList.add("is-invalid");

      // Create or update error message element
      let errorElement = input.nextElementSibling;
      if (
        !errorElement ||
        !errorElement.classList.contains("invalid-feedback")
      ) {
        errorElement = document.createElement("div");
        errorElement.className = "invalid-feedback";
        input.parentNode.insertBefore(errorElement, input.nextSibling);
      }
      errorElement.textContent = message;

      // Add to errors object
      errors[fieldName] = message;

      // Handle aria attributes for accessibility
      input.setAttribute("aria-invalid", "true");
      errorElement.id = `error-${fieldName}`;
      input.setAttribute("aria-describedby", errorElement.id);
    },

    _clearFieldError(input) {
      // Remove error class and aria attributes
      input.classList.remove("is-invalid");
      input.removeAttribute("aria-invalid");
      input.removeAttribute("aria-describedby");

      // Remove error message element
      const errorElement = input.nextElementSibling;
      if (errorElement && errorElement.classList.contains("invalid-feedback")) {
        errorElement.remove();
      }
    },

    _setFormError(form, message) {
      // Check if error container already exists
      let errorContainer = form.querySelector(".form-error-container");

      if (!errorContainer) {
        // Create error container if it doesn't exist
        errorContainer = document.createElement("div");
        errorContainer.className = "form-error-container alert alert-danger";
        form.prepend(errorContainer);
      }

      errorContainer.textContent = message;
      errorContainer.setAttribute("role", "alert");
    },

    _getFormData(form) {
      // Get form data as an object
      const formData = new FormData(form);
      const data = {};

      formData.forEach((value, key) => {
        // Handle checkbox arrays
        if (key.endsWith("[]")) {
          const cleanKey = key.substring(0, key.length - 2);
          if (!data[cleanKey]) {
            data[cleanKey] = [];
          }
          data[cleanKey].push(value);
        } else if (data[key]) {
          // Convert to array if multiple values with same key
          if (!Array.isArray(data[key])) {
            data[key] = [data[key]];
          }
          data[key].push(value);
        } else {
          data[key] = value;
        }
      });

      return data;
    },

    _validateEmail(value) {
      const emailRegex =
        /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$/;
      return emailRegex.test(value);
    },

    _validatePhone(value) {
      // Basic international phone format
      const phoneRegex = /^\+?[1-9]\d{1,14}$/;
      return phoneRegex.test(value.replace(/[\s()-]/g, ""));
    },

    _validatePassword(value) {
      // At least 8 characters, 1 uppercase, 1 lowercase, 1 number, 1 special character
      const passwordRegex =
        /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;
      return passwordRegex.test(value);
    },

    _validateNumeric(value) {
      return /^-?\d+$/.test(value);
    },

    _validateAlpha(value) {
      return /^[a-zA-Z\s]+$/.test(value);
    },

    _validateAlphanumeric(value) {
      return /^[a-zA-Z0-9\s]+$/.test(value);
    },

    _validatePattern(value, pattern) {
      try {
        const regex = new RegExp(pattern);
        return regex.test(value);
      } catch (e) {
        console.error("Invalid regex pattern:", pattern, e);
        return false;
      }
    },

    _validateDate(value) {
      // Check if value is a valid date
      const date = new Date(value);
      return !isNaN(date.getTime());
    },

    _validateFutureDate(value) {
      // Check if value is a date in the future
      const date = new Date(value);
      const now = new Date();
      now.setHours(0, 0, 0, 0); // Compare dates only, not time

      return !isNaN(date.getTime()) && date >= now;
    },

    // Display form errors
    showFormErrors(form, errors) {
      // Remove existing error messages
      const existingErrors = form.querySelectorAll(".form-error");
      existingErrors.forEach((el) => el.remove());

      // Reset error state on fields
      const fields = form.querySelectorAll(".form-control");
      fields.forEach((field) => {
        field.classList.remove("is-invalid");
      });

      // Display new errors
      for (const [field, message] of Object.entries(errors)) {
        const input = form.querySelector(`[name="${field}"], #${field}`);

        if (input) {
          input.classList.add("is-invalid");

          const errorElement = this.createElement(
            "div",
            {
              class: "form-error",
            },
            message,
          );

          input.parentNode.appendChild(errorElement);
        } else if (field === "global") {
          // Global error
          const errorElement = this.createElement(
            "div",
            {
              class: "alert alert-danger",
            },
            message,
          );

          form.prepend(errorElement);
        }
      }
    },
  };

  // Authentication module
  const auth = {
    TOKEN_KEY: "queueme_token",
    USER_KEY: "queueme_user",

    init() {
      // Check if user is logged in on page load
      this.checkAuth();

      // Add event listeners for login/logout
      util.on("body", "click", ".js-logout", this.handleLogout.bind(this));
    },

    checkAuth() {
      const token = this.getToken();
      const user = this.getUser();

      if (token && user) {
        // Update UI for authenticated user
        this.updateAuthUI(user);
        return true;
      } else {
        // Clear any invalid auth data
        this.clearAuth();
        return false;
      }
    },

    async login(credentials) {
      try {
        const response = await util.post(
          `${config.apiBaseUrl}/auth/login/`,
          credentials,
        );

        if (response.ok && response.data?.tokens?.access) {
          this.setToken(response.data.tokens.access);
          this.setUser(response.data);
          this.updateAuthUI(response.data);
          return { success: true };
        } else {
          return {
            success: false,
            error:
              response.data?.detail ||
              "Login failed. Please check your credentials.",
          };
        }
      } catch (error) {
        console.error("Login error:", error);
        return {
          success: false,
          error: "An unexpected error occurred. Please try again.",
        };
      }
    },

    async verifyOTP(payload) {
      try {
        const response = await util.post(
          `${config.apiBaseUrl}/auth/verify_otp/`,
          payload,
        );

        if (response.ok && response.data?.tokens?.access) {
          this.setToken(response.data.tokens.access);
          this.setUser(response.data);
          this.updateAuthUI(response.data);
          return { success: true, data: response.data };
        } else {
          return {
            success: false,
            error:
              response.data?.detail ||
              "OTP verification failed. Please try again.",
          };
        }
      } catch (error) {
        console.error("OTP verification error:", error);
        return {
          success: false,
          error: "An unexpected error occurred. Please try again.",
        };
      }
    },

    logout() {
      this.clearAuth();
      window.location.href = "/login/";
    },

    handleLogout(event) {
      event.preventDefault();
      this.logout();
    },

    getToken() {
      return localStorage.getItem(this.TOKEN_KEY);
    },

    setToken(token) {
      localStorage.setItem(this.TOKEN_KEY, token);
    },

    getUser() {
      const userData = localStorage.getItem(this.USER_KEY);
      return userData ? JSON.parse(userData) : null;
    },

    setUser(user) {
      localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    },

    clearAuth() {
      localStorage.removeItem(this.TOKEN_KEY);
      localStorage.removeItem(this.USER_KEY);
      this.updateAuthUI(null);
    },

    updateAuthUI(user) {
      const authContainer = util.$(".auth-container");
      if (!authContainer) return;

      if (user) {
        // User is logged in
        authContainer.innerHTML = `
            <div class="user-info">
              <span class="user-name">${
                user.user_type === "customer" ? "Customer" : "Staff"
              }</span>
              <button class="btn btn-sm btn-outline-primary js-logout">Logout</button>
            </div>
          `;
      } else {
        // User is not logged in
        authContainer.innerHTML = `
            <a href="/login/" class="btn btn-primary">Login</a>
            <a href="/register/" class="btn btn-outline-primary">Register</a>
          `;
      }
    },
  };

  // Language module
  const lang = {
    current: null,
    translations: {},

    init() {
      // Determine current language
      const storedLang = localStorage.getItem("queueme_lang");
      const htmlLang = document.documentElement.lang;
      const browserLang = navigator.language.split("-")[0];

      this.current =
        storedLang ||
        (config.supportedLangs.includes(htmlLang) ? htmlLang : null) ||
        (config.supportedLangs.includes(browserLang) ? browserLang : null) ||
        config.defaultLang;

      // Apply language to document
      this.applyLanguage(this.current);

      // Add event listeners for language switching
      util.delegate(
        "body",
        "click",
        ".js-lang-switch",
        this.handleLanguageSwitch.bind(this),
      );
    },

    applyLanguage(lang) {
      if (!config.supportedLangs.includes(lang)) {
        lang = config.defaultLang;
      }

      this.current = lang;
      localStorage.setItem("queueme_lang", lang);

      // Set HTML lang attribute
      document.documentElement.lang = lang;

      // Apply RTL if needed
      const isRTL = config.rtlLangs.includes(lang);
      document.documentElement.dir = isRTL ? "rtl" : "ltr";

      // Load translations if not already loaded
      if (!this.translations[lang]) {
        this.loadTranslations(lang);
      }

      // Update language switcher UI
      this.updateLanguageSwitcherUI();

      // Translate page
      this.translatePage();
    },

    async loadTranslations(lang) {
      try {
        const response = await util.get(`/static/translations/${lang}.json`);
        if (response.ok && response.data) {
          this.translations[lang] = response.data;
          this.translatePage();
        }
      } catch (error) {
        console.error(`Failed to load translations for ${lang}:`, error);
      }
    },

    translate(key, replacements = {}) {
      const translation = this.translations[this.current]?.[key] || key;

      // Handle replacements
      if (Object.keys(replacements).length) {
        return translation.replace(/\{(\w+)\}/g, (match, key) => {
          return replacements[key] !== undefined ? replacements[key] : match;
        });
      }

      return translation;
    },

    translatePage() {
      // Translate elements with data-i18n attribute
      const elements = document.querySelectorAll("[data-i18n]");
      elements.forEach((el) => {
        const key = el.getAttribute("data-i18n");
        const translation = this.translate(key);

        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
          if (el.getAttribute("placeholder")) {
            el.setAttribute("placeholder", translation);
          } else {
            el.value = translation;
          }
        } else {
          el.textContent = translation;
        }
      });

      // Translate elements with data-i18n-attr attribute (for attributes)
      const attrElements = document.querySelectorAll("[data-i18n-attr]");
      attrElements.forEach((el) => {
        const attr = el.getAttribute("data-i18n-attr");
        const key = el.getAttribute("data-i18n");
        const translation = this.translate(key);

        el.setAttribute(attr, translation);
      });
    },

    handleLanguageSwitch(event) {
      event.preventDefault();
      const langButton = event.target.closest(".js-lang-switch");
      const newLang = langButton.dataset.lang;

      if (newLang && newLang !== this.current) {
        this.applyLanguage(newLang);
      }
    },

    updateLanguageSwitcherUI() {
      const languageSwitcher = util.$(".language-switcher");
      if (!languageSwitcher) return;

      const buttons = languageSwitcher.querySelectorAll(".js-lang-switch");
      buttons.forEach((button) => {
        const buttonLang = button.dataset.lang;
        if (buttonLang === this.current) {
          button.classList.add("active");
        } else {
          button.classList.remove("active");
        }
      });
    },
  };

  // Web Socket connection management
  const socket = {
    connections: {},

    connect(channel, token = null) {
      // Close existing connection if any
      this.disconnect(channel);

      // Build WebSocket URL
      let wsUrl = `${config.wsBaseUrl}/ws/${channel}/`;

      // Add token if provided
      if (token) {
        wsUrl += `?token=${token}`;
      } else if (auth.getToken()) {
        wsUrl += `?token=${auth.getToken()}`;
      }

      // Create new WebSocket connection
      const ws = new WebSocket(wsUrl);

      // Setup event listeners
      ws.onopen = this._onOpen.bind(this, channel);
      ws.onclose = this._onClose.bind(this, channel);
      ws.onmessage = this._onMessage.bind(this, channel);
      ws.onerror = this._onError.bind(this, channel);

      // Store connection
      this.connections[channel] = {
        socket: ws,
        status: "connecting",
        listeners: {},
        reconnectAttempts: 0,
      };

      return this.connections[channel];
    },

    disconnect(channel) {
      const connection = this.connections[channel];
      if (connection && connection.socket) {
        connection.socket.close();
        delete this.connections[channel];
      }
    },

    send(channel, data) {
      const connection = this.connections[channel];
      if (!connection || connection.status !== "open") {
        console.error(
          `Cannot send message: WebSocket for ${channel} is not open`,
        );
        return false;
      }

      try {
        connection.socket.send(JSON.stringify(data));
        return true;
      } catch (error) {
        console.error(`Error sending message to ${channel}:`, error);
        return false;
      }
    },

    on(channel, event, callback) {
      if (!this.connections[channel]) {
        console.error(
          `Cannot add listener: WebSocket for ${channel} does not exist`,
        );
        return;
      }

      if (!this.connections[channel].listeners[event]) {
        this.connections[channel].listeners[event] = [];
      }

      this.connections[channel].listeners[event].push(callback);
    },

    off(channel, event, callback) {
      if (
        !this.connections[channel] ||
        !this.connections[channel].listeners[event]
      ) {
        return;
      }

      if (callback) {
        // Remove specific callback
        this.connections[channel].listeners[event] = this.connections[
          channel
        ].listeners[event].filter((cb) => cb !== callback);
      } else {
        // Remove all callbacks for event
        delete this.connections[channel].listeners[event];
      }
    },

    _onOpen(channel, event) {
      console.log(`WebSocket connection established for ${channel}`);

      const connection = this.connections[channel];
      if (connection) {
        connection.status = "open";
        connection.reconnectAttempts = 0;

        // Trigger open event listeners
        this._triggerListeners(channel, "open", event);
      }
    },

    _onClose(channel, event) {
      console.log(
        `WebSocket connection closed for ${channel}:`,
        event.code,
        event.reason,
      );

      const connection = this.connections[channel];
      if (connection) {
        connection.status = "closed";

        // Trigger close event listeners
        this._triggerListeners(channel, "close", event);

        // Attempt to reconnect if closure was unexpected
        if (event.code !== 1000 && event.code !== 1001) {
          this._attemptReconnect(channel);
        }
      }
    },

    _onMessage(channel, event) {
      let data;

      try {
        data = JSON.parse(event.data);
      } catch (error) {
        console.error(`Error parsing WebSocket message for ${channel}:`, error);
        return;
      }

      // Trigger message event listeners
      this._triggerListeners(channel, "message", data);

      // Trigger specific event listeners based on message type
      if (data.type) {
        this._triggerListeners(channel, data.type, data);
      }
    },

    _onError(channel, error) {
      console.error(`WebSocket error for ${channel}:`, error);

      // Trigger error event listeners
      this._triggerListeners(channel, "error", error);
    },

    _attemptReconnect(channel) {
      const connection = this.connections[channel];
      if (!connection) return;

      connection.reconnectAttempts += 1;

      if (connection.reconnectAttempts <= config.maxRetryAttempts) {
        console.log(
          `Attempting to reconnect to ${channel} (${connection.reconnectAttempts}/${config.maxRetryAttempts})...`,
        );

        const delay = connection.reconnectAttempts * config.retryDelay;

        setTimeout(() => {
          if (this.connections[channel]) {
            // Store listeners before recreating connection
            const listeners = this.connections[channel].listeners;

            // Reconnect
            this.connect(channel);

            // Restore listeners
            this.connections[channel].listeners = listeners;
          }
        }, delay);
      } else {
        console.error(
          `Failed to reconnect to ${channel} after ${config.maxRetryAttempts} attempts.`,
        );
      }
    },

    _triggerListeners(channel, event, data) {
      const connection = this.connections[channel];
      if (!connection || !connection.listeners[event]) return;

      connection.listeners[event].forEach((callback) => {
        try {
          callback(data);
        } catch (error) {
          console.error(
            `Error in WebSocket listener for ${channel} event ${event}:`,
            error,
          );
        }
      });
    },
  };

  // Initialize modules
  function init() {
    // Initialize modules
    auth.init();
    lang.init();

    // Expose modules to global QueueMe object
    QueueMe.util = util;
    QueueMe.auth = auth;
    QueueMe.lang = lang;
    QueueMe.socket = socket;
    QueueMe.config = config;
    QueueMe.cache = cache;

    // Add platform initializer methods
    QueueMe.initBooking = initBooking;
    QueueMe.initQueue = initQueue;
    QueueMe.initChat = initChat;

    // Set up global event listeners
    setupEventListeners();

    // Trigger ready event
    const readyEvent = new Event("queueme:ready");
    document.dispatchEvent(readyEvent);
  }

  // Setup global event listeners
  function setupEventListeners() {
    // Form submission handling
    util.delegate("body", "submit", "form[data-ajax]", handleAjaxForm);

    // Toggle elements
    util.delegate("body", "click", "[data-toggle]", handleToggle);

    // Modal handling
    util.delegate("body", "click", "[data-modal]", handleModal);
    util.delegate("body", "click", ".modal-backdrop, .modal-close", closeModal);

    // Initialize datepickers
    initDatePickers();

    // Initialize timepickers
    initTimePickers();
  }

  // Handle AJAX form submissions
  function handleAjaxForm(event) {
    event.preventDefault();

    const form = event.target;
    const url = form.action;
    const method = form.method.toUpperCase();
    const formData = new FormData(form);
    const submitButton = form.querySelector('[type="submit"]');

    // Disable submit button during submission
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.dataset.originalText = submitButton.textContent;
      submitButton.textContent = "Submitting...";
    }

    // Validate form if validation is enabled
    if (form.dataset.validate) {
      const validation = util.validateForm(form);

      if (!validation.valid) {
        util.showFormErrors(form, validation.errors);

        // Re-enable submit button
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = submitButton.dataset.originalText;
        }

        return;
      }
    }

    // Convert FormData to JSON if needed
    let data;
    if (form.dataset.format === "json") {
      data = {};
      formData.forEach((value, key) => {
        data[key] = value;
      });
    } else {
      data = formData;
    }

    // Make AJAX request
    const requestFn =
      method === "GET"
        ? util.get
        : method === "POST"
        ? util.post
        : method === "PUT"
        ? util.put
        : util.delete;

    requestFn(url, data)
      .then((response) => {
        // Handle response
        if (response.ok) {
          // Show success message if provided
          if (form.dataset.successMessage) {
            util.showToast(form.dataset.successMessage, "success");
          }

          // Reset form if specified
          if (form.dataset.reset === "true") {
            form.reset();
          }

          // Redirect if specified
          if (form.dataset.redirect) {
            window.location.href = form.dataset.redirect;
            return;
          }

          // Refresh page if specified
          if (form.dataset.refresh === "true") {
            window.location.reload();
            return;
          }

          // Trigger custom event with response data
          const successEvent = new CustomEvent("form:success", {
            detail: {
              form: form,
              response: response,
            },
          });

          form.dispatchEvent(successEvent);
        } else {
          // Show error message
          const errorMessage =
            response.data?.detail || "An error occurred. Please try again.";

          if (form.dataset.errorMessage) {
            util.showToast(form.dataset.errorMessage, "error");
          } else {
            util.showToast(errorMessage, "error");
          }

          // Show field errors if any
          if (response.data?.errors) {
            util.showFormErrors(form, response.data.errors);
          }

          // Trigger custom event with error data
          const errorEvent = new CustomEvent("form:error", {
            detail: {
              form: form,
              response: response,
            },
          });

          form.dispatchEvent(errorEvent);
        }
      })
      .catch((error) => {
        // Show error message
        util.showToast(
          "An unexpected error occurred. Please try again later.",
          "error",
        );

        // Trigger custom event with error
        const errorEvent = new CustomEvent("form:error", {
          detail: {
            form: form,
            error: error,
          },
        });

        form.dispatchEvent(errorEvent);
      })
      .finally(() => {
        // Re-enable submit button
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = submitButton.dataset.originalText;
        }
      });
  }

  // Handle toggle elements
  function handleToggle(event) {
    const trigger = event.target.closest("[data-toggle]");
    const targetSelector = trigger.dataset.toggle;
    const target = document.querySelector(targetSelector);

    if (!target) return;

    // Toggle target visibility
    if (target.classList.contains("hidden")) {
      target.classList.remove("hidden");
    } else {
      target.classList.add("hidden");
    }

    // Update trigger text if specified
    if (trigger.dataset.showText && trigger.dataset.hideText) {
      const isVisible = !target.classList.contains("hidden");
      trigger.textContent = isVisible
        ? trigger.dataset.hideText
        : trigger.dataset.showText;
    }
  }

  // Handle modal opening
  function handleModal(event) {
    event.preventDefault();

    const trigger = event.target.closest("[data-modal]");
    const modalSelector = trigger.dataset.modal;
    const modal = document.querySelector(modalSelector);

    if (!modal) return;

    // Show modal
    modal.classList.add("show");
    document.body.classList.add("modal-open");

    // Add backdrop if not exists
    if (!document.querySelector(".modal-backdrop")) {
      const backdrop = util.createElement("div", {
        class: "modal-backdrop",
      });
      document.body.appendChild(backdrop);
    }
  }

  // Handle modal closing
  function closeModal(event) {
    if (
      event.target.classList.contains("modal-backdrop") ||
      event.target.classList.contains("modal-close")
    ) {
      event.preventDefault();

      // Close all open modals
      const modals = document.querySelectorAll(".modal.show");
      modals.forEach((modal) => {
        modal.classList.remove("show");
      });

      // Remove backdrop
      const backdrop = document.querySelector(".modal-backdrop");
      if (backdrop) {
        document.body.removeChild(backdrop);
      }

      document.body.classList.remove("modal-open");
    }
  }

  // Initialize date pickers
  function initDatePickers() {
    const datePickers = document.querySelectorAll(".datepicker");

    datePickers.forEach((input) => {
      // Placeholder implementation - would be replaced with actual date picker library integration
      input.setAttribute("type", "date");

      // Add event listener for date change
      input.addEventListener("change", function () {
        const changeEvent = new CustomEvent("datepicker:change", {
          detail: {
            input: this,
            value: this.value,
          },
        });

        this.dispatchEvent(changeEvent);
      });
    });
  }

  // Initialize time pickers
  function initTimePickers() {
    const timePickers = document.querySelectorAll(".timepicker");

    timePickers.forEach((input) => {
      // Placeholder implementation - would be replaced with actual time picker library integration
      input.setAttribute("type", "time");

      // Add event listener for time change
      input.addEventListener("change", function () {
        const changeEvent = new CustomEvent("timepicker:change", {
          detail: {
            input: this,
            value: this.value,
          },
        });

        this.dispatchEvent(changeEvent);
      });
    });
  }

  // Booking module initializer
  function initBooking(options = {}) {
    // Implementation for booking functionality
    console.log("Booking module initialized with options:", options);
  }

  // Queue module initializer
  function initQueue(options = {}) {
    // Implementation for queue functionality
    console.log("Queue module initialized with options:", options);
  }

  // Chat module initializer
  function initChat(options = {}) {
    // Implementation for chat functionality
    console.log("Chat module initialized with options:", options);
  }

  // Initialize when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
