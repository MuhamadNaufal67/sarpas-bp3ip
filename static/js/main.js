/**
 * SARPAS BP3IP - Main Interactive JavaScript
 * Kementerian Perhubungan Republik Indonesia - BP3IP Jakarta
 */

document.addEventListener("DOMContentLoaded", function () {
  initTheme();
  initSidebar();
  initNotifications();
  initModals();
  initFormValidation();
  initAlertDismiss();
  initActiveNavLink();
});

/* ==========================================================================
   1. THEME MANAGEMENT (LIGHT / DARK MODE)
   ========================================================================== */
function initTheme() {
  const themeToggleBtn = document.getElementById("theme-toggle");
  const storedTheme = localStorage.getItem("sarpas_theme");
  const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

  const currentTheme = storedTheme || (systemPrefersDark ? "dark" : "light");
  setTheme(currentTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", function () {
      const activeTheme = document.documentElement.getAttribute("data-theme") || "light";
      const newTheme = activeTheme === "dark" ? "light" : "dark";
      setTheme(newTheme);
      localStorage.setItem("sarpas_theme", newTheme);
    });
  }
}

function setTheme(theme) {
  if (theme === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
  updateThemeIcon(theme);
}

function updateThemeIcon(theme) {
  const iconContainer = document.getElementById("theme-icon-container");
  if (!iconContainer) return;

  if (theme === "dark") {
    // Moon Icon
    iconContainer.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
  } else {
    // Sun Icon
    iconContainer.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;
  }
}

/* ==========================================================================
   2. SIDEBAR COLLAPSE / EXPAND & MOBILE DRAWER
   ========================================================================== */
function initSidebar() {
  const sidebar = document.querySelector(".sidebar");
  // Button inside the sidebar (desktop collapse/expand)
  const collapseBtn = document.getElementById("sidebar-collapse-btn");
  // Button in header (mobile hamburger)
  const mobileToggle = document.getElementById("mobile-menu-toggle");
  const overlay = document.querySelector(".sidebar-overlay");

  if (!sidebar) return;

  // --- Restore Desktop Collapsed State from localStorage ---
  const isCollapsed = localStorage.getItem("sarpas_sidebar_collapsed") === "true";
  if (isCollapsed && window.innerWidth > 900) {
    sidebar.classList.add("collapsed");
    updateCollapseBtnIcon(true);
  }

  // --- Desktop Collapse Button (inside sidebar) ---
  if (collapseBtn) {
    collapseBtn.addEventListener("click", function () {
      const nowCollapsed = sidebar.classList.toggle("collapsed");
      localStorage.setItem("sarpas_sidebar_collapsed", nowCollapsed ? "true" : "false");
      updateCollapseBtnIcon(nowCollapsed);
    });
  }

  // --- Mobile Hamburger Toggle ---
  if (mobileToggle) {
    mobileToggle.addEventListener("click", function () {
      const isOpen = sidebar.classList.toggle("mobile-open");
      if (overlay) {
        if (isOpen) {
          overlay.style.display = "block";
          requestAnimationFrame(function () {
            overlay.classList.add("active");
          });
        } else {
          overlay.classList.remove("active");
        }
      }
    });
  }

  // --- Overlay Click to Close on Mobile ---
  if (overlay) {
    overlay.addEventListener("click", function () {
      sidebar.classList.remove("mobile-open");
      overlay.classList.remove("active");
    });
    overlay.addEventListener("transitionend", function () {
      if (!overlay.classList.contains("active")) {
        overlay.style.display = "";
      }
    });
  }

  // --- On resize: reset mobile state if going back to desktop ---
  window.addEventListener("resize", function () {
    if (window.innerWidth > 900) {
      sidebar.classList.remove("mobile-open");
      if (overlay) {
        overlay.classList.remove("active");
        overlay.style.display = "";
      }
    }
  });
}

/**
 * Update the chevron icons and aria-label on the sidebar collapse button
 * to reflect the current collapsed state.
 */
function updateCollapseBtnIcon(isCollapsed) {
  const btn = document.getElementById("sidebar-collapse-btn");
  const chevLeft = document.getElementById("sidebar-chevron-left");
  const chevRight = document.getElementById("sidebar-chevron-right");

  if (!btn) return;

  if (isCollapsed) {
    btn.setAttribute("aria-label", "Buka sidebar");
    btn.setAttribute("title", "Buka sidebar");
    if (chevLeft) chevLeft.style.display = "none";
    if (chevRight) chevRight.style.display = "block";
  } else {
    btn.setAttribute("aria-label", "Tutup sidebar");
    btn.setAttribute("title", "Tutup sidebar");
    if (chevLeft) chevLeft.style.display = "block";
    if (chevRight) chevRight.style.display = "none";
  }
}

/* ==========================================================================
   3. ACTIVE NAV LINK HIGHLIGHT
   ========================================================================== */
function initActiveNavLink() {
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll(".nav-link");

  navLinks.forEach(function (link) {
    const href = link.getAttribute("href");
    if (href && currentPath.startsWith(href) && href !== "/") {
      link.classList.add("active");
    } else if (href === "/" && currentPath === "/") {
      link.classList.add("active");
    }
  });
}

/* ==========================================================================
   4. NOTIFICATION DROPDOWN
   ========================================================================== */
function initNotifications() {
  const bellBtn = document.getElementById("notification-bell-btn");
  const dropdown = document.getElementById("notification-dropdown");

  if (!bellBtn || !dropdown) return;

  bellBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    dropdown.classList.toggle("active");
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", function (e) {
    if (!dropdown.contains(e.target) && !bellBtn.contains(e.target)) {
      dropdown.classList.remove("active");
    }
  });

  // Close on ESC
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && dropdown.classList.contains("active")) {
      dropdown.classList.remove("active");
    }
  });
}

/* ==========================================================================
   5. CONFIRMATION MODALS (APPROVE, REJECT, DELETE, CANCEL)
   ========================================================================== */
function initModals() {
  const modalBackdrop = document.getElementById("confirm-modal");
  if (!modalBackdrop) return;

  const modalTitle = document.getElementById("confirm-title");
  const modalMessage = document.getElementById("confirm-message");
  const modalConfirmBtn = document.getElementById("confirm-submit-btn");
  const modalCancelBtn = document.getElementById("confirm-cancel-btn");
  let pendingFormToSubmit = null;

  function closeModal() {
    modalBackdrop.classList.remove("active");
    pendingFormToSubmit = null;
  }

  if (modalCancelBtn) {
    modalCancelBtn.addEventListener("click", closeModal);
  }

  modalBackdrop.addEventListener("click", function (e) {
    if (e.target === modalBackdrop) closeModal();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modalBackdrop.classList.contains("active")) {
      closeModal();
    }
  });

  if (modalConfirmBtn) {
    modalConfirmBtn.addEventListener("click", function () {
      if (pendingFormToSubmit) {
        modalConfirmBtn.classList.add("btn-loading");
        pendingFormToSubmit.submit();
      }
    });
  }

  // Attach to forms requesting confirmation
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      pendingFormToSubmit = form;

      const title = form.getAttribute("data-confirm-title") || "Konfirmasi Aksi";
      const message = form.getAttribute("data-confirm") || "Apakah Anda yakin ingin melanjutkan tindakan ini?";
      const btnClass = form.getAttribute("data-confirm-btn-class") || "button ok";
      const btnText = form.getAttribute("data-confirm-btn-text") || "Ya, Lanjutkan";

      if (modalTitle) modalTitle.textContent = title;
      if (modalMessage) modalMessage.innerHTML = message;
      if (modalConfirmBtn) {
        modalConfirmBtn.className = btnClass;
        modalConfirmBtn.textContent = btnText;
      }

      modalBackdrop.classList.add("active");
    });
  });
}

/* ==========================================================================
   6. FORM VALIDATION & PROGRESSIVE ENHANCEMENT
   ========================================================================== */
function initFormValidation() {
  // 1. Min date for reservations: today
  const dateInputs = document.querySelectorAll('input[type="date"][name="tanggal"]');
  const today = new Date().toISOString().split("T")[0];
  dateInputs.forEach(function (input) {
    if (!input.getAttribute("min")) {
      input.setAttribute("min", today);
    }
  });

  // 2. Client-side validation on ReservasiForm: start & end time
  const reservasiForm = document.querySelector("form.reservasi-form");
  if (reservasiForm) {
    reservasiForm.addEventListener("submit", function (e) {
      const start = reservasiForm.querySelector('input[name="jam_mulai"]');
      const end = reservasiForm.querySelector('input[name="jam_selesai"]');

      if (start && end && start.value && end.value) {
        if (end.value <= start.value) {
          e.preventDefault();
          showFieldError(end, "Jam selesai harus lebih besar dari jam mulai.");
          end.focus();
          return false;
        }
      }
    });
  }

  // 3. Loading state on button when submitting valid forms
  document.querySelectorAll("form:not([data-confirm])").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (form.checkValidity && !form.checkValidity()) return;
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.classList.add("btn-loading");
      }
    });
  });
}

/**
 * Show an inline error message below an input field.
 */
function showFieldError(input, message) {
  // Remove existing error for this input
  const existingError = input.parentElement.querySelector(".js-field-error");
  if (existingError) existingError.remove();

  input.style.borderColor = "var(--danger)";
  const errEl = document.createElement("div");
  errEl.className = "js-field-error errorlist";
  errEl.style.cssText = "margin-top:6px;font-size:13px;color:var(--danger-text);display:flex;align-items:center;gap:4px;";
  errEl.textContent = message;
  input.parentElement.insertAdjacentElement("afterend", errEl);

  input.addEventListener("input", function () {
    input.style.borderColor = "";
    errEl.remove();
  }, { once: true });
}

/* ==========================================================================
   7. DISMISSIBLE ALERTS
   ========================================================================== */
function initAlertDismiss() {
  document.querySelectorAll(".message").forEach(function (alert) {
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "message-close";
    closeBtn.innerHTML = "&times;";
    closeBtn.setAttribute("aria-label", "Tutup pesan");
    closeBtn.addEventListener("click", function () {
      alert.style.opacity = "0";
      alert.style.transform = "translateY(-6px)";
      alert.style.transition = "all 0.2s ease";
      setTimeout(function () {
        alert.remove();
      }, 200);
    });
    alert.appendChild(closeBtn);

    // Auto-dismiss success messages after 5 seconds
    if (alert.classList.contains("success")) {
      setTimeout(function () {
        if (alert.parentElement) {
          alert.style.opacity = "0";
          alert.style.transform = "translateY(-6px)";
          alert.style.transition = "all 0.3s ease";
          setTimeout(function () {
            if (alert.parentElement) alert.remove();
          }, 300);
        }
      }, 5000);
    }
  });
}
