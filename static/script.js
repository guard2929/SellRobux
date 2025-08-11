document.addEventListener('DOMContentLoaded', function () {
    const menuItems = document.querySelectorAll('.menu-item');
    const sections = document.querySelectorAll('.section');
    const hamburger = document.querySelector('.hamburger');
    const closeButton = document.querySelector('.close-button');
    const mobileMenu = document.querySelector('.mobile-menu');

    function activateSection(sectionId) {
        sections.forEach(section => {
            section.classList.remove('active');
            if (section.id === sectionId) {
                section.classList.add('active');
            }
        });

        menuItems.forEach(item => {
            item.classList.remove('active');
            if (item.getAttribute('data-target') === sectionId) {
                item.classList.add('active');
            }
        });

        window.scrollTo(0, 0);

        if (history.pushState) {
            history.pushState({section: sectionId}, '', `?section=${sectionId}`);
        }
    }

    menuItems.forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-target');
            activateSection(targetId);
            if (window.innerWidth <= 1080) {
                mobileMenu.classList.remove('active');
                hamburger.classList.remove('active');
            }
        });
    });

    const urlParams = new URLSearchParams(window.location.search);
    const sectionParam = urlParams.get('section');

    if (sectionParam && Array.from(sections).some(s => s.id === sectionParam)) {
        activateSection(sectionParam);
    } else {
        activateSection('portfolio');
    }

    hamburger.addEventListener('click', function () {
        hamburger.classList.add('active');
        mobileMenu.classList.add('active');
    });

    closeButton.addEventListener('click', function () {
        mobileMenu.classList.remove('active');
        hamburger.classList.remove('active');
    });

    window.addEventListener('resize', function () {
        if (window.innerWidth > 1080) {
            mobileMenu.classList.remove('active');
            hamburger.classList.remove('active');
        }
    });

    window.addEventListener('popstate', function (event) {
        const sectionId = event.state?.section || 'portfolio';
        activateSection(sectionId);
    });
});


function selectMethod(event) {
    const methods = document.querySelectorAll('.method');
    methods.forEach(method => {
        method.classList.remove('selected');
        const radio = method.querySelector('input[type="radio"]');
        radio.checked = false;
    });

    const method = event.currentTarget;
    method.classList.add('selected');
    const radio = method.querySelector('input[type="radio"]');
    radio.checked = true;

    console.log('Selected method:', radio.value);
}

document.querySelectorAll('.method').forEach(method => {
    method.addEventListener('click', selectMethod);
});


document.addEventListener('DOMContentLoaded', () => {
    const sumInfoDiv = document.querySelector('.sum-info');
    const sumInput = sumInfoDiv.querySelector('.summ');

    sumInfoDiv.addEventListener('click', (event) => {
        if (event.target !== sumInput) {
            sumInput.focus();
        }
    });
});
document.addEventListener('DOMContentLoaded', function() {
    const accountSelector = document.getElementById('account-selector');
    const balanceDisplay = document.querySelector('.available-balance h1');

    accountSelector.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        if (selectedOption.value) {
            const balance = parseFloat(selectedOption.dataset.balance).toFixed(2);
            balanceDisplay.textContent = `$ ${balance}`;
        } else {
            balanceDisplay.textContent = '$ 0.00';
        }
    });
});