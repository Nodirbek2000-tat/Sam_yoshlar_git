// Ko'p qadamli formalar: StartUp arizasi va Tashkilot anketasi
(function () {
    const form = document.querySelector('[data-multistep]') || document.getElementById('startup-form');
    if (!form) return;

    const steps = Array.from(form.querySelectorAll('.form-step'));
    if (!steps.length) return;

    const indicators = document.querySelectorAll('[data-step-indicator]');
    const progressLine = document.getElementById('progress-line');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    let current = 1;
    const total = steps.length;

    function validateStep(stepEl) {
        let valid = true;
        stepEl.querySelectorAll('input, select, textarea').forEach((field) => {
            field.classList.remove('startup-error');
            if (field.required && !field.value.trim()) {
                field.classList.add('startup-error');
                valid = false;
            }
        });
        return valid;
    }

    function show(step, scroll = true) {
        current = Math.min(Math.max(step, 1), total);

        steps.forEach((el) => {
            el.classList.toggle('active', Number(el.dataset.step) === current);
        });

        indicators.forEach((el) => {
            const num = Number(el.dataset.stepIndicator);
            el.classList.toggle('active', num === current);
            el.classList.toggle('done', num < current);
        });

        const percent = total > 1 ? ((current - 1) / (total - 1)) * 100 : 100;
        if (progressLine) progressLine.style.setProperty('--progress', percent + '%');
        if (progressFill) progressFill.style.width = Math.round((current / total) * 100) + '%';
        if (progressText) progressText.textContent = current + ' / ' + total;

        // Sahifa ochilganda avtomatik siljitmaymiz — faqat qadam almashganda
        if (scroll) {
            const top = form.getBoundingClientRect().top + window.scrollY - 100;
            window.scrollTo({ top, behavior: 'smooth' });
        }
    }

    form.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-goto-step]');
        if (!trigger) return;

        const target = Number(trigger.dataset.gotoStep);
        // Oldinga yurishdan oldin joriy qadamni tekshiramiz
        if (target > current && !validateStep(steps[current - 1])) {
            const warning = form.querySelector('#step-warning');
            if (warning) {
                warning.textContent = "Majburiy maydonlarni to'ldiring";
                warning.style.display = 'block';
                setTimeout(() => { warning.style.display = 'none'; }, 3000);
            }
            return;
        }
        show(target);
    });

    // Fayl tanlanganda nomini ko'rsatish
    const fileInput = form.querySelector('input[type="file"]');
    const uploadText = document.getElementById('upload-text');
    if (fileInput && uploadText) {
        fileInput.addEventListener('change', () => {
            const file = fileInput.files && fileInput.files[0];
            uploadText.textContent = file
                ? `${file.name} (${Math.round(file.size / 1024)} KB)`
                : 'Faylni tanlash uchun bosing';
        });
    }

    // Xato bo'lgan maydon qaysi qadamda bo'lsa, o'sha qadamni ochamiz
    const firstError = form.querySelector('.form-errors');
    if (firstError) {
        const errorStep = firstError.closest('.form-step');
        if (errorStep) show(Number(errorStep.dataset.step), false);
    } else {
        show(1, false);
    }
})();
