// Navbar: scroll holati va mobil menyu
(function () {
    const navbar = document.getElementById('navbar');
    const toggle = document.getElementById('menu-toggle');
    const menu = document.getElementById('navbar-menu');

    if (navbar) {
        const onScroll = () => navbar.classList.toggle('scrolled', window.scrollY > 8);
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    }

    if (toggle && menu) {
        toggle.addEventListener('click', () => menu.classList.toggle('open'));
    }

    // Sahifa aylanganda elementlarni ko'rsatish
    const revealables = document.querySelectorAll('.scroll-reveal');
    if (revealables.length && 'IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });
        revealables.forEach((el) => observer.observe(el));
    }
})();
