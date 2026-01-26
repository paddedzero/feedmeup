// Inject banner at top of home page
document.addEventListener('DOMContentLoaded', function () {
    if (window.location.pathname === '/feedmeup/' || window.location.pathname === '/feedmeup/index.html') {
        const main = document.querySelector('#core-wrapper') || document.querySelector('main');
        if (main) {
            const banner = document.createElement('div');
            banner.className = 'hero-banner';
            banner.innerHTML = '<img src="/feedmeup/assets/img/banner.svg" alt="FeedMeUp News Brief banner" style="max-width: 100%; height: auto; margin: 2rem auto; display: block;">';
            main.insertBefore(banner, main.firstChild);
        }
    }
});
