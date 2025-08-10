document.addEventListener('DOMContentLoaded', () => {

    // ===== Logic for Fading in Sections on Scroll =====
    // This makes sections with the 'hidden' class appear as you scroll.
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('show');
            }
        });
    }, {
        threshold: 0.1 // Triggers when 10% of the element is visible
    });

    const hiddenElements = document.querySelectorAll('.hidden');
    hiddenElements.forEach(el => observer.observe(el));


    // ===== Logic for the 'Back to Top' Button =====
    // This makes the button appear only after you've scrolled down a bit.
    const backToTopButton = document.querySelector('.back-to-top-button');
    if (backToTopButton) { // Check if the button exists on the page
        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                backToTopButton.classList.add('visible');
            } else {
                backToTopButton.classList.remove('visible');
            }
        });
    }

});
// ===== Sliding Pill Navbar Logic =====
const navMenu = document.querySelector('.nav-menu');
const navLinks = document.querySelectorAll('.nav-link');

navLinks.forEach(link => {
    link.addEventListener('mouseover', () => {
        const { left, top, width, height } = link.getBoundingClientRect();
        const parentLeft = navMenu.getBoundingClientRect().left;

        navMenu.style.setProperty('--left', `${left - parentLeft}px`);
        navMenu.style.setProperty('--width', `${width}px`);
    });
});