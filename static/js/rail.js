/* Yo'nalishlar lentasi — sichqoncha g'ildiragi, sudrash va o'q tugmalari bilan siljiydi.
   Scrollbar yashirilgani uchun bularsiz kompyuterda siljitib bo'lmasdi. */

(function () {
    const rails = document.querySelectorAll('.voice-rail, .voice-dir-picker, .tabs');
    if (!rails.length) return;

    /* Silliq siljitish — `behavior: 'smooth'` ba'zi brauzerlarda ishlamaydi,
       shuning uchun o'zimiz animatsiya qilamiz. */
    function smoothScroll(el, distance, duration = 320) {
        const start = el.scrollLeft;
        const max = el.scrollWidth - el.clientWidth;
        const target = Math.max(0, Math.min(start + distance, max));
        const change = target - start;
        if (!change) return;

        // Yashirin oynada requestAnimationFrame to'xtaydi — animatsiyasiz siljitamiz
        if (document.hidden) {
            el.scrollLeft = target;
            return;
        }

        const startedAt = performance.now();
        let finished = false;

        function frame(now) {
            const progress = Math.min((now - startedAt) / duration, 1);
            const eased = progress < 0.5
                ? 2 * progress * progress
                : 1 - Math.pow(-2 * progress + 2, 2) / 2;
            el.scrollLeft = start + change * eased;
            if (progress < 1) requestAnimationFrame(frame);
            else finished = true;
        }

        requestAnimationFrame(frame);

        // Kafolat: animatsiya biror sababga ko'ra ishlamasa, oxirgi holatni qo'yamiz
        setTimeout(() => {
            if (!finished) el.scrollLeft = target;
        }, duration + 60);
    }

    rails.forEach((rail) => {
        if (rail.scrollWidth <= rail.clientWidth + 4) return;

        rail.classList.add('is-scrollable');

        /* --- G'ildirak: vertikal aylantirish gorizontalga aylanadi --- */
        rail.addEventListener('wheel', (event) => {
            if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
            const before = rail.scrollLeft;
            rail.scrollLeft += event.deltaY;
            if (rail.scrollLeft !== before) event.preventDefault();
        }, { passive: false });

        /* --- Sudrab siljitish --- */
        let dragging = false;
        let startX = 0;
        let startScroll = 0;
        let moved = 0;

        rail.addEventListener('pointerdown', (event) => {
            if (event.pointerType === 'touch') return;   // telefonda tabiiy scroll ishlaydi
            dragging = true;
            moved = 0;
            startX = event.clientX;
            startScroll = rail.scrollLeft;
            rail.classList.add('is-dragging');
        });

        rail.addEventListener('pointermove', (event) => {
            if (!dragging) return;
            const delta = event.clientX - startX;
            moved = Math.abs(delta);
            rail.scrollLeft = startScroll - delta;
            if (moved > 4) event.preventDefault();
        });

        function stopDrag() {
            if (!dragging) return;
            dragging = false;
            rail.classList.remove('is-dragging');
        }

        rail.addEventListener('pointerup', stopDrag);
        rail.addEventListener('pointerleave', stopDrag);
        rail.addEventListener('pointercancel', stopDrag);

        // Sudrab bo'lgach havola ochilib ketmasin
        rail.addEventListener('click', (event) => {
            if (moved > 6) {
                event.preventDefault();
                event.stopPropagation();
                moved = 0;
            }
        }, true);

        /* --- Chap/o'ng o'q tugmalari --- */
        const wrap = document.createElement('div');
        wrap.className = 'rail-wrap';
        rail.parentNode.insertBefore(wrap, rail);
        wrap.appendChild(rail);

        const prev = document.createElement('button');
        prev.type = 'button';
        prev.className = 'rail-arrow rail-arrow-prev';
        prev.setAttribute('aria-label', "Chapga");
        prev.textContent = '‹';

        const next = document.createElement('button');
        next.type = 'button';
        next.className = 'rail-arrow rail-arrow-next';
        next.setAttribute('aria-label', "O'ngga");
        next.textContent = '›';

        wrap.append(prev, next);

        const step = () => Math.max(rail.clientWidth * 0.7, 200);
        prev.addEventListener('click', () => {
            smoothScroll(rail, -step());
            setTimeout(sync, 420);          // o'qlar holatini yangilaymiz
        });

        next.addEventListener('click', () => {
            smoothScroll(rail, step());
            setTimeout(sync, 420);
        });

        function sync() {
            const max = rail.scrollWidth - rail.clientWidth;
            prev.classList.toggle('hidden', rail.scrollLeft <= 2);
            next.classList.toggle('hidden', rail.scrollLeft >= max - 2);
        }

        rail.addEventListener('scroll', sync, { passive: true });
        window.addEventListener('resize', sync);
        sync();

        // Faol elementni ko'rinadigan joyga surib qo'yamiz
        const active = rail.querySelector('.active');
        if (active) {
            const box = active.getBoundingClientRect();
            const railBox = rail.getBoundingClientRect();
            if (box.left < railBox.left || box.right > railBox.right) {
                rail.scrollLeft = active.offsetLeft - rail.clientWidth / 2 + box.width / 2;
                sync();
            }
        }
    });
})();
