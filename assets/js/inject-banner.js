// Inject banner at top of home page - robust version
(function () {
    function injectBanner() {
        // Check if we're on the home page
        const isHome = window.location.pathname === '/feedmeup/' ||
            window.location.pathname === '/feedmeup/index.html' ||
            window.location.pathname.endsWith('/feedmeup');

        if (!isHome) {
            console.log('Not on home page, skipping banner injection');
            return;
        }

        // Check if banner already exists
        if (document.querySelector('.hero-banner')) {
            console.log('Banner already exists');
            return;
        }

        // Try multiple selectors to find the main content area
        const selectors = [
            '#core-wrapper',
            'main',
            '#main-wrapper',
            '.container',
            '#post-list'
        ];

        let target = null;
        for (const selector of selectors) {
            const el = document.querySelector(selector);
            if (el) {
                target = el;
                console.log('Found target with selector:', selector);
                break;
            }
        }

        if (!target) {
            console.error('Could not find target element for banner injection');
            return;
        }

        // Create and inject banner
        const banner = document.createElement('div');
        banner.className = 'hero-banner';
        banner.style.cssText = 'text-align: center; padding: 2rem 0; margin-bottom: 2rem;';
        banner.innerHTML = '<img src="/feedmeup/assets/img/banner.svg" alt="FeedMeUp News Brief banner" style="max-width: 100%; height: auto; display: block; margin: 0 auto;">';

        target.insertBefore(banner, target.firstChild);
        console.log('Banner injected successfully');
    }

    // Try immediately
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectBanner);
    } else {
        injectBanner();
    }

    // Also try after a short delay in case content loads dynamically
    setTimeout(injectBanner, 500);
})();
