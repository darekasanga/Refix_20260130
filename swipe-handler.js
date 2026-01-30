(function () {
  const DEFAULT_CONFIG = {
    minSwipeDistance: 26,
    scrollSmoothness: 'smooth',
    snapToSections: false,
    showVisualFeedback: true,
    feedbackDuration: 300,
    verticalOnly: true,
    horizontalOnly: false,
    enableMomentum: true,
    momentumMultiplier: 2.5,
    enableGradient: true
  };

  class SwipeHandler {
    constructor(element, config = {}) {
      this.element = element;
      this.config = { ...DEFAULT_CONFIG, ...config };
      this.touchStartX = null;
      this.touchStartY = null;
      this.touchStartTime = null;
      this.lastScrollTop = 0;
      this.isScrolling = false;
      this.gradientOverlay = null;

      if (this.config.showVisualFeedback && this.config.enableGradient) {
        this._createGradientOverlay();
      }

      this._bindEvents();
    }

    _createGradientOverlay() {
      this.gradientOverlay = document.createElement('div');
      this.gradientOverlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 80px;
        pointer-events: none;
        z-index: 9999;
        opacity: 0;
        transition: opacity ${this.config.feedbackDuration}ms ease;
        background: linear-gradient(to bottom, rgba(139, 92, 246, 0.15), transparent);
      `;
      this.gradientOverlay.setAttribute('aria-hidden', 'true');
      document.body.appendChild(this.gradientOverlay);

      this.gradientOverlayBottom = document.createElement('div');
      this.gradientOverlayBottom.style.cssText = `
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 80px;
        pointer-events: none;
        z-index: 9999;
        opacity: 0;
        transition: opacity ${this.config.feedbackDuration}ms ease;
        background: linear-gradient(to top, rgba(139, 92, 246, 0.15), transparent);
      `;
      this.gradientOverlayBottom.setAttribute('aria-hidden', 'true');
      document.body.appendChild(this.gradientOverlayBottom);
    }

    _showGradient(direction) {
      if (!this.config.enableGradient) return;
      
      if (direction === 'up' && this.gradientOverlay) {
        this.gradientOverlay.style.opacity = '1';
        setTimeout(() => {
          if (this.gradientOverlay) this.gradientOverlay.style.opacity = '0';
        }, this.config.feedbackDuration);
      } else if (direction === 'down' && this.gradientOverlayBottom) {
        this.gradientOverlayBottom.style.opacity = '1';
        setTimeout(() => {
          if (this.gradientOverlayBottom) this.gradientOverlayBottom.style.opacity = '0';
        }, this.config.feedbackDuration);
      }
    }

    _bindEvents() {
      this.element.addEventListener('touchstart', this._handleTouchStart.bind(this), { passive: true });
      this.element.addEventListener('touchmove', this._handleTouchMove.bind(this), { passive: false });
      this.element.addEventListener('touchend', this._handleTouchEnd.bind(this), { passive: true });
      this.element.addEventListener('touchcancel', this._handleTouchCancel.bind(this), { passive: true });
    }

    _handleTouchStart(e) {
      const touch = e.touches?.[0];
      if (!touch) return;

      this.touchStartX = touch.clientX;
      this.touchStartY = touch.clientY;
      this.touchStartTime = Date.now();
      this.lastScrollTop = window.pageYOffset || document.documentElement.scrollTop;
      this.isScrolling = false;
    }

    _handleTouchMove(e) {
      if (this.touchStartY === null) return;

      const touch = e.touches?.[0];
      if (!touch) return;

      const deltaX = Math.abs(touch.clientX - this.touchStartX);
      const deltaY = Math.abs(touch.clientY - this.touchStartY);

      // Determine scroll direction
      if (!this.isScrolling) {
        if (this.config.verticalOnly && deltaY > deltaX) {
          this.isScrolling = true;
        } else if (this.config.horizontalOnly && deltaX > deltaY) {
          this.isScrolling = true;
        } else if (!this.config.verticalOnly && !this.config.horizontalOnly) {
          this.isScrolling = true;
        }
      }

      // Allow native scrolling behavior for vertical swipes
      if (this.isScrolling && this.config.verticalOnly && deltaY > deltaX) {
        // Let browser handle vertical scrolling natively
        return;
      }
    }

    _handleTouchEnd(e) {
      if (this.touchStartY === null && this.touchStartX === null) return;

      const touch = e.changedTouches?.[0];
      if (!touch) return;

      const deltaX = touch.clientX - this.touchStartX;
      const deltaY = touch.clientY - this.touchStartY;
      const deltaTime = Date.now() - this.touchStartTime;
      const absDeltaX = Math.abs(deltaX);
      const absDeltaY = Math.abs(deltaY);

      // Check if this is a valid swipe
      const isVerticalSwipe = this.config.verticalOnly && absDeltaY > absDeltaX;
      const isHorizontalSwipe = this.config.horizontalOnly && absDeltaX > absDeltaY;
      const isSwipe = !this.config.verticalOnly && !this.config.horizontalOnly;

      if ((isVerticalSwipe || isHorizontalSwipe || isSwipe) && 
          (absDeltaY >= this.config.minSwipeDistance || absDeltaX >= this.config.minSwipeDistance)) {
        
        const swipeDirection = this._getSwipeDirection(deltaX, deltaY);
        
        if (this.config.onSwipe && typeof this.config.onSwipe === 'function') {
          this.config.onSwipe(swipeDirection, { deltaX, deltaY, deltaTime });
        }

        // Handle vertical scrolling with momentum
        if (this.config.verticalOnly && swipeDirection) {
          this._handleVerticalScroll(deltaY, deltaTime, swipeDirection);
        }
      }

      this._resetTouch();
    }

    _handleVerticalScroll(deltaY, deltaTime, direction) {
      const velocity = Math.abs(deltaY) / deltaTime;
      let scrollAmount = Math.abs(deltaY);

      // Apply momentum if enabled
      if (this.config.enableMomentum && velocity > 0.5) {
        scrollAmount *= this.config.momentumMultiplier * Math.min(velocity, 2);
      }

      const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const targetScrollTop = direction === 'up' 
        ? currentScrollTop + scrollAmount 
        : currentScrollTop - scrollAmount;

      // Show visual feedback
      this._showGradient(direction);

      // Smooth scroll to target
      window.scrollTo({
        top: Math.max(0, targetScrollTop),
        behavior: this.config.scrollSmoothness
      });

      // Snap to sections if enabled
      if (this.config.snapToSections) {
        this._snapToNearestSection(direction);
      }
    }

    _snapToNearestSection(direction) {
      const sections = document.querySelectorAll('section, .card, .news-card, .panel, .article-card');
      if (sections.length === 0) return;

      const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const viewportHeight = window.innerHeight;
      
      let nearestSection = null;
      let minDistance = Infinity;

      sections.forEach(section => {
        const rect = section.getBoundingClientRect();
        const sectionTop = rect.top + currentScrollTop;
        const distance = Math.abs(sectionTop - currentScrollTop);

        if (distance < minDistance && distance < viewportHeight) {
          minDistance = distance;
          nearestSection = section;
        }
      });

      if (nearestSection) {
        setTimeout(() => {
          nearestSection.scrollIntoView({ 
            behavior: this.config.scrollSmoothness, 
            block: 'start' 
          });
        }, 100);
      }
    }

    _getSwipeDirection(deltaX, deltaY) {
      if (this.config.verticalOnly) {
        return deltaY > 0 ? 'down' : 'up';
      }
      if (this.config.horizontalOnly) {
        return deltaX > 0 ? 'right' : 'left';
      }
      
      const absDeltaX = Math.abs(deltaX);
      const absDeltaY = Math.abs(deltaY);
      
      if (absDeltaY > absDeltaX) {
        return deltaY > 0 ? 'down' : 'up';
      } else {
        return deltaX > 0 ? 'right' : 'left';
      }
    }

    _handleTouchCancel() {
      this._resetTouch();
    }

    _resetTouch() {
      this.touchStartX = null;
      this.touchStartY = null;
      this.touchStartTime = null;
      this.isScrolling = false;
    }

    destroy() {
      if (this.gradientOverlay) {
        this.gradientOverlay.remove();
        this.gradientOverlay = null;
      }
      if (this.gradientOverlayBottom) {
        this.gradientOverlayBottom.remove();
        this.gradientOverlayBottom = null;
      }
    }
  }

  // Export to global scope
  window.SwipeHandler = SwipeHandler;

  // Helper function to initialize swipe on an element
  window.initSwipeHandler = function(selector, config = {}) {
    const element = typeof selector === 'string' 
      ? document.querySelector(selector) 
      : selector;
    
    if (!element) {
      console.warn('SwipeHandler: Element not found', selector);
      return null;
    }

    return new SwipeHandler(element, config);
  };

  // Auto-initialize on body for general page scrolling if data attribute is present
  document.addEventListener('DOMContentLoaded', () => {
    if (document.body.hasAttribute('data-swipe-enabled')) {
      const config = {};
      
      // Read config from data attributes
      if (document.body.hasAttribute('data-swipe-snap')) {
        config.snapToSections = document.body.getAttribute('data-swipe-snap') === 'true';
      }
      if (document.body.hasAttribute('data-swipe-gradient')) {
        config.enableGradient = document.body.getAttribute('data-swipe-gradient') === 'true';
      }
      
      window.pageSwipeHandler = new SwipeHandler(document.body, config);
    }
  });
})();
