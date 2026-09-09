/* «Yoshlar Ovozi» — tirik ikonkalar.
   Har bir tashabbusning o'z sahnasi bor: ovoz ko'paygan sari o'sadi.
   Sahna <svg data-scene="eco" data-votes="12" ...> elementiga chiziladi. */

(function () {
    /* ---------------------- Yordamchilar ---------------------- */

    function seeded(i, salt) {
        const x = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453;
        return x - Math.floor(x);
    }

    function lerp(a, b, t) { return a + (b - a) * t; }

    function quad(p0, p1, p2, t) {
        return {
            x: (1 - t) * (1 - t) * p0.x + 2 * (1 - t) * t * p1.x + t * t * p2.x,
            y: (1 - t) * (1 - t) * p0.y + 2 * (1 - t) * t * p1.y + t * t * p2.y,
        };
    }

    /* ---------------------- Sahnalar ----------------------
       cat = {id, color, accent, max}  ·  v = ovozlar soni     */

    function defs(cat) {
        return `<defs>
            <filter id="glow-${cat.id}" x="-60%" y="-60%" width="220%" height="220%">
                <feGaussianBlur stdDeviation="3" result="b"/>
                <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <linearGradient id="trunk-${cat.id}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#6b4a34"/><stop offset="1" stop-color="#37271b"/>
            </linearGradient>
            <linearGradient id="ground-${cat.id}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#232c3d"/><stop offset="1" stop-color="#0c0f16"/>
            </linearGradient>
            <linearGradient id="fill-${cat.id}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="${cat.accent}"/><stop offset="1" stop-color="${cat.color}"/>
            </linearGradient>
            <radialGradient id="halo-${cat.id}" cx="50%" cy="50%" r="50%">
                <stop offset="0" stop-color="${cat.accent}" stop-opacity="0.85"/>
                <stop offset="1" stop-color="${cat.color}" stop-opacity="0"/>
            </radialGradient>
        </defs>`;
    }

    const SCENES = {
        eco(cat, v) {
            const count = Math.min(v, cat.max);
            const branches = [
                { p0: { x: 450, y: 300 }, p1: { x: 380, y: 230 }, p2: { x: 300, y: 170 } },
                { p0: { x: 450, y: 280 }, p1: { x: 520, y: 210 }, p2: { x: 610, y: 160 } },
                { p0: { x: 450, y: 260 }, p1: { x: 400, y: 190 }, p2: { x: 360, y: 120 } },
                { p0: { x: 450, y: 250 }, p1: { x: 500, y: 180 }, p2: { x: 540, y: 110 } },
                { p0: { x: 450, y: 230 }, p1: { x: 450, y: 170 }, p2: { x: 450, y: 90 } },
                { p0: { x: 450, y: 290 }, p1: { x: 340, y: 260 }, p2: { x: 250, y: 230 } },
                { p0: { x: 450, y: 270 }, p1: { x: 560, y: 250 }, p2: { x: 660, y: 230 } },
            ];
            let out = `<ellipse cx="450" cy="500" rx="220" ry="15" fill="url(#ground-${cat.id})" opacity="0.6"/>`;
            out += branches.map((b) =>
                `<path d="M${b.p0.x},${b.p0.y} Q${b.p1.x},${b.p1.y} ${b.p2.x},${b.p2.y}"
                 stroke="url(#trunk-${cat.id})" stroke-width="7" fill="none" stroke-linecap="round"/>`).join('');
            out += `<path d="M420,495 C410,450 415,395 430,340 C440,312 460,300 450,300
                    C445,320 470,340 470,380 C480,435 470,470 480,495 Z" fill="url(#trunk-${cat.id})"/>`;
            for (let i = 0; i < count; i++) {
                const b = branches[i % branches.length];
                const pt = quad(b.p0, b.p1, b.p2, 0.55 + 0.45 * seeded(i, 1));
                const x = pt.x + (seeded(i, 2) - 0.5) * 40;
                const y = pt.y + (seeded(i, 3) - 0.5) * 30;
                const s = 0.7 + seeded(i, 5) * 0.6;
                if ((i + 1) % 13 === 0) {
                    out += `<g class="pop" transform="translate(${x} ${y}) scale(${s})">
                            <circle r="7" fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>
                            <circle cx="-2" cy="-2" r="2" fill="#fff" opacity="0.4"/></g>`;
                } else if ((i + 1) % 8 === 0) {
                    let petals = '';
                    for (let k = 0; k < 5; k++) {
                        petals += `<ellipse cx="0" cy="-8" rx="4" ry="7" fill="${cat.accent}" transform="rotate(${k * 72})"/>`;
                    }
                    out += `<g class="pop" transform="translate(${x} ${y}) scale(${s})">${petals}<circle r="4" fill="#fff" opacity="0.85"/></g>`;
                } else {
                    out += `<path class="pop" transform="translate(${x} ${y}) rotate(${seeded(i, 4) * 360}) scale(${s})"
                            d="M0,-14 C9,-14 12,-3 0,9 C-12,-3 -9,-14 0,-14 Z"
                            fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>`;
                }
            }
            return out;
        },

        fintech(cat, v) {
            const cols = 9, cx0 = 175, gap = 68, w = 44, groundY = 470;
            const pts = new Array(cols).fill(0);
            for (let i = 0; i < Math.min(v, cat.max); i++) pts[i % cols]++;
            let out = `<rect x="120" y="${groundY}" width="660" height="14" rx="4" fill="url(#ground-${cat.id})" opacity="0.6"/>`;
            for (let c = 0; c < cols; c++) {
                const p = Math.min(pts[c], 14);
                const h = 26 + p * 14;
                const x = cx0 + c * gap, y = groundY - h;
                out += `<g class="pop"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="4"
                        fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>`;
                for (let r = 0; r < Math.floor(h / 22); r++) {
                    for (let wc = 0; wc < 2; wc++) {
                        const lit = seeded(c * 10 + r * 2 + wc, 9) < (0.3 + p * 0.04);
                        out += `<rect x="${x + 7 + wc * 18}" y="${y + 8 + r * 20}" width="9" height="11" rx="1.4"
                                fill="${lit ? cat.accent : 'rgba(255,255,255,0.09)'}" opacity="${lit ? 0.95 : 0.5}"/>`;
                    }
                }
                out += '</g>';
            }
            for (let k = 0; k < Math.min(3, v); k++) {
                const idx = v - 1 - k;
                out += `<g class="floatcoin" style="animation-delay:${k * 0.3}s"
                        transform="translate(${210 + (idx % 5) * 100} ${100 + (idx % 3) * 22}) scale(0.75)">
                        <circle r="16" fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>
                        <circle r="16" fill="none" stroke="${cat.accent}" stroke-width="1.4" opacity="0.7"/>
                        <circle r="9" fill="none" stroke="#0a0d13" stroke-width="1.1" opacity="0.35"/></g>`;
            }
            return out;
        },

        ai(cat, v) {
            const count = Math.min(v, cat.max);
            const cx = 450, cy = 260, ringCap = [6, 9, 12, 16, 20];
            const positions = [];
            let idx = 0;
            for (let r = 0; r < ringCap.length && idx < count; r++) {
                const radius = 62 + r * 48, cap = ringCap[r];
                for (let k = 0; k < cap && idx < count; k++, idx++) {
                    const angle = (k / cap) * Math.PI * 2 + r * 0.3;
                    positions.push({ x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius * 0.72 });
                }
            }
            let out = '';
            positions.forEach((p, i) => {
                out += `<line x1="${cx}" y1="${cy}" x2="${p.x}" y2="${p.y}" stroke="${cat.color}" stroke-width="1" opacity="0.22"/>`;
                if (i > 0) {
                    const j = Math.floor(seeded(i, 7) * i);
                    out += `<line x1="${positions[j].x}" y1="${positions[j].y}" x2="${p.x}" y2="${p.y}"
                            stroke="${cat.accent}" stroke-width="1" opacity="0.16"/>`;
                }
            });
            positions.forEach((p, i) => {
                out += `<circle class="pop" cx="${p.x}" cy="${p.y}" r="${4 + seeded(i, 3) * 4}"
                        fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>`;
            });
            out += `<circle cx="${cx}" cy="${cy}" r="32" fill="url(#halo-${cat.id})"/>
                    <circle cx="${cx}" cy="${cy}" r="15" fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>`;
            return out;
        },

        edu(cat, v) {
            const count = Math.min(v, cat.max);
            const cx = 450, cy = 440;
            let out = `<rect x="330" y="310" width="240" height="140" rx="6" fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})" opacity="0.85"/>`;
            for (let i = 0; i < count; i++) {
                const t = count <= 1 ? 0 : i / Math.max(count - 1, 1);
                const rad = lerp(-62, 62, t) * Math.PI / 180;
                const len = 88 + seeded(i, 2) * 24;
                const x2 = cx + Math.sin(rad) * len, y2 = cy - Math.cos(rad) * len * 0.62 - 16;
                out += `<path class="pop" d="M${cx - 14},${cy} Q${cx + (x2 - cx) / 2},${cy - 40} ${x2},${y2}
                        Q${cx + (x2 - cx) / 2},${cy - 10} ${cx + 14},${cy}"
                        fill="${i % 2 === 0 ? cat.accent : '#f2efe9'}" opacity="0.88" stroke="${cat.color}" stroke-width="0.6"/>`;
            }
            if (count >= cat.max) out += `<circle cx="${cx}" cy="310" r="66" fill="url(#halo-${cat.id})"/>`;
            return out;
        },

        social(cat, v) {
            const count = Math.min(v, cat.max);
            const perRow = 12;
            let out = '';
            for (let i = 0; i < count; i++) {
                const row = Math.floor(i / perRow), col = i % perRow;
                const rowCount = Math.min(perRow, count - row * perRow);
                const x = 450 - (rowCount * 46) / 2 + 23 + col * 46;
                const y = 410 - row * 66 + Math.sin(col * 0.8) * 8;
                const fill = i % 2 === 0 ? cat.accent : cat.color;
                if (col > 0) {
                    out += `<line x1="${x - 30}" y1="${y - 4}" x2="${x - 16}" y2="${y - 4}"
                            stroke="${cat.accent}" stroke-width="3" opacity="0.5" stroke-linecap="round"/>`;
                }
                out += `<g class="pop" transform="translate(${x} ${y}) scale(${0.85 + seeded(i, 3) * 0.3})">
                        <circle cy="-24" r="8" fill="${fill}"/>
                        <path d="M-11,4 C-11,-14 11,-14 11,4 L9,20 L-9,20 Z" fill="${fill}"/></g>`;
            }
            return out;
        },

        agro(cat, v) {
            const cols = 14, startX = 150, gap = 44, baseY = 470;
            let out = `<rect x="100" y="${baseY}" width="700" height="30" fill="url(#ground-${cat.id})"/>`;
            for (let c = 0; c < cols; c++) {
                const p = Math.min(Math.floor(v / cols) + (v % cols > c ? 1 : 0), 4);
                const x = startX + c * gap;
                let g = `<g class="pop" transform="translate(${x} ${baseY})">`;
                if (p <= 0) g += `<circle r="4" fill="${cat.color}"/>`;
                else if (p === 1) g += `<path d="M0,0 Q-4,-14 0,-24" stroke="${cat.color}" stroke-width="3" fill="none" stroke-linecap="round"/>`;
                else if (p === 2) g += `<path d="M0,0 Q-4,-20 0,-38" stroke="${cat.color}" stroke-width="3.5" fill="none" stroke-linecap="round"/>
                                        <path d="M0,-18 Q-16,-24 -20,-10" stroke="${cat.accent}" stroke-width="3" fill="none"/>
                                        <path d="M0,-24 Q16,-30 20,-16" stroke="${cat.accent}" stroke-width="3" fill="none"/>`;
                else if (p === 3) g += `<path d="M0,0 Q-4,-24 0,-48" stroke="${cat.color}" stroke-width="4" fill="none" stroke-linecap="round"/>
                                        <path d="M0,-22 Q-18,-28 -24,-12" stroke="${cat.accent}" stroke-width="3.5" fill="none"/>
                                        <path d="M0,-30 Q18,-36 24,-18" stroke="${cat.accent}" stroke-width="3.5" fill="none"/>
                                        <circle cy="-50" r="6" fill="${cat.accent}"/>`;
                else g += `<path d="M0,0 Q-4,-24 0,-48" stroke="${cat.color}" stroke-width="4" fill="none" stroke-linecap="round"/>
                           <path d="M0,-22 Q-18,-28 -24,-12" stroke="${cat.accent}" stroke-width="3.5" fill="none"/>
                           <circle cy="-52" r="10" fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>`;
                out += g + '</g>';
            }
            return out;
        },

        energy(cat, v) {
            const cx = 450, cy = 130;
            let out = `<circle cx="${cx}" cy="${cy}" r="66" fill="url(#halo-${cat.id})"/>
                       <circle cx="${cx}" cy="${cy}" r="36" fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>`;
            for (let i = 0; i < Math.min(v, 18); i++) {
                const ang = (i / 18) * Math.PI * 2;
                out += `<line class="pop" x1="${cx + Math.cos(ang) * 44}" y1="${cy + Math.sin(ang) * 44}"
                        x2="${cx + Math.cos(ang) * 66}" y2="${cy + Math.sin(ang) * 66}"
                        stroke="${cat.accent}" stroke-width="3" stroke-linecap="round"/>`;
            }
            out += `<rect x="120" y="445" width="660" height="40" fill="url(#ground-${cat.id})" opacity="0.5"/>`;
            for (let p = 0; p < 6; p++) {
                const lit = v > cat.max * 0.25 + p * 2;
                const x = 170 + p * 100;
                out += `<g class="pop"><rect x="${x}" y="405" width="70" height="40" rx="4"
                        fill="${lit ? `url(#fill-${cat.id})` : '#1a2130'}"/>
                        <path d="M${x},445 L${x + 35},378 L${x + 70},445" fill="${lit ? cat.accent : '#232b3d'}" opacity="0.9"/>
                        ${lit ? `<circle cx="${x + 35}" cy="425" r="4" fill="${cat.accent}"/>` : ''}</g>`;
            }
            return out;
        },

        industry(cat, v) {
            const sections = 6, baseY = 470;
            let out = `<rect x="120" y="${baseY}" width="660" height="20" fill="url(#ground-${cat.id})"/>`;
            for (let s = 0; s < sections; s++) {
                const p = Math.min(Math.floor(v / sections) + (v % sections > s ? 1 : 0), 4);
                const x = 150 + s * 105, h = 38 + p * 32;
                out += `<g class="pop"><rect x="${x}" y="${baseY - h}" width="80" height="${h}"
                        fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})" opacity="0.92"/>`;
                if (p >= 1) out += `<rect x="${x + 10}" y="${baseY - h + 10}" width="16" height="16" fill="${cat.accent}" opacity="0.7"/>`;
                if (p >= 2) out += `<rect x="${x + 54}" y="${baseY - h + 10}" width="16" height="16" fill="${cat.accent}" opacity="0.7"/>`;
                if (p >= 3) out += `<circle cx="${x + 40}" cy="${baseY - h - 8}" r="8" fill="${cat.accent}"/>`;
                if (p >= 4) out += `<rect x="${x + 30}" y="${baseY - h - 4}" width="20" height="6" fill="${cat.color}"/>`;
                out += '</g>';
            }
            return out;
        },

        startup(cat, v) {
            const th = cat.max;
            let out = `<rect x="380" y="490" width="140" height="12" rx="4" fill="url(#ground-${cat.id})"/><g filter="url(#glow-${cat.id})">`;
            if (v > 0) out += `<path class="pop" d="M450,430 C440,460 445,478 450,492 C455,478 460,460 450,430 Z" fill="url(#halo-${cat.id})"/>`;
            if (v >= 1) out += `<rect class="pop" x="430" y="400" width="40" height="30" rx="6" fill="${cat.color}"/>`;
            const seg = Math.min(Math.floor(v / 2), 8);
            for (let i = 0; i < seg; i++) {
                out += `<rect class="pop" x="420" y="${400 - (i + 1) * 26}" width="60" height="28" rx="10" fill="url(#fill-${cat.id})"/>`;
            }
            if (seg >= 3) {
                out += `<circle class="pop" cx="450" cy="${400 - 4 * 26}" r="12" fill="#eaf6fa" opacity="0.9"/>
                        <circle cx="450" cy="${400 - 4 * 26}" r="12" fill="none" stroke="${cat.color}" stroke-width="3"/>`;
            }
            if (v >= th * 0.6) out += `<path class="pop" d="M420,${400 - seg * 26} Q450,${400 - seg * 26 - 66} 480,${400 - seg * 26} Z" fill="${cat.accent}"/>`;
            if (v >= th * 0.75) {
                out += `<path class="pop" d="M420,410 L372,456 L420,442 Z" fill="${cat.color}"/>
                        <path class="pop" d="M480,410 L528,456 L480,442 Z" fill="${cat.color}"/>`;
            }
            out += '</g>';
            if (v >= th) {
                for (let i = 0; i < 22; i++) {
                    out += `<circle cx="${100 + seeded(i, 11) * 700}" cy="${40 + seeded(i, 12) * 160}"
                            r="${1 + seeded(i, 13) * 1.5}" fill="#fff" opacity="0.6"/>`;
                }
                out += `<text x="450" y="64" text-anchor="middle" font-size="26" fill="${cat.accent}"
                        font-family="Space Grotesk, sans-serif" style="letter-spacing:6px">UCHDIK!</text>`;
            }
            return out;
        },

        creative(cat, v) {
            const cols = 8, rows = 8, size = 48, startX = 258, startY = 60, total = cols * rows;
            const count = Math.min(v, cat.max, total);
            const order = [...Array(total).keys()].sort((a, b) => seeded(a, 21) - seeded(b, 21));
            let out = `<rect x="${startX - 8}" y="${startY - 8}" width="${cols * size + 16}" height="${rows * size + 16}" fill="#0c1220" rx="8"/>`;
            for (let k = 0; k < count; k++) {
                const idx = order[k], cx = idx % cols, ry = Math.floor(idx / cols);
                out += `<rect class="pop" x="${startX + cx * size + 3}" y="${startY + ry * size + 3}"
                        width="${size - 6}" height="${size - 6}" rx="4"
                        fill="${seeded(idx, 4) < 0.5 ? cat.color : cat.accent}" opacity="${0.6 + seeded(idx, 5) * 0.4}"/>`;
            }
            return out;
        },

        culture(cat, v) {
            const sections = 5, baseY = 470;
            let out = `<rect x="140" y="${baseY}" width="620" height="20" fill="url(#ground-${cat.id})"/>`;
            for (let s = 0; s < sections; s++) {
                const p = Math.min(Math.floor(v / sections) + (v % sections > s ? 1 : 0), 4);
                const x = 170 + s * 130;
                let h = 30, g = '<g class="pop">';
                if (p >= 1) { h = 60; g += `<rect x="${x}" y="${baseY - h}" width="90" height="${h}" fill="url(#fill-${cat.id})"/>`; }
                if (p >= 2) {
                    g += `<rect x="${x + 10}" y="${baseY - h - 10}" width="10" height="${h}" fill="${cat.accent}" opacity="0.8"/>
                          <rect x="${x + 70}" y="${baseY - h - 10}" width="10" height="${h}" fill="${cat.accent}" opacity="0.8"/>`;
                }
                if (p >= 3) g += `<path d="M${x},${baseY - h} Q${x + 45},${baseY - h - 40} ${x + 90},${baseY - h} Z" fill="${cat.color}"/>`;
                if (p >= 4) {
                    g += `<circle cx="${x + 45}" cy="${baseY - h - 55}" r="22" fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>
                          <rect x="${x + 42}" y="${baseY - h - 90}" width="6" height="30" fill="${cat.accent}"/>`;
                }
                out += g + '</g>';
            }
            return out;
        },

        smartcity(cat, v) {
            const baseY = 470;
            const buildings = [
                { x: 150, w: 70, h: 200 }, { x: 230, w: 50, h: 145 }, { x: 290, w: 80, h: 255 },
                { x: 380, w: 60, h: 172 }, { x: 450, w: 90, h: 290 }, { x: 550, w: 55, h: 155 },
                { x: 615, w: 75, h: 218 }, { x: 700, w: 60, h: 182 },
            ];
            let out = `<rect x="100" y="${baseY}" width="700" height="20" fill="url(#ground-${cat.id})"/>`;
            const totalWindows = buildings.reduce((s, b) => s + Math.floor(b.h / 26) * Math.max(1, Math.floor(b.w / 22)), 0);
            const litCount = Math.min(v * 3, totalWindows);
            let lit = 0;
            buildings.forEach((b) => {
                out += `<rect x="${b.x}" y="${baseY - b.h}" width="${b.w}" height="${b.h}" fill="#141b28"/>`;
                const rows = Math.floor(b.h / 26), colsB = Math.max(1, Math.floor(b.w / 22));
                for (let r = 0; r < rows; r++) {
                    for (let c = 0; c < colsB; c++) {
                        const on = lit < litCount;
                        out += `<rect x="${b.x + 8 + c * 22}" y="${baseY - b.h + 10 + r * 26}" width="12" height="14" rx="1"
                                fill="${on ? cat.accent : '#232b3a'}" opacity="${on ? 0.95 : 0.6}"/>`;
                        lit++;
                    }
                }
            });
            return out;
        },

        science(cat, v) {
            const count = Math.min(v, cat.max);
            const cx = 450, cy = 260;
            let out = `<ellipse cx="${cx}" cy="${cy}" rx="170" ry="56" fill="none" stroke="${cat.color}" stroke-width="1" opacity="0.25"/>
                       <ellipse cx="${cx}" cy="${cy}" rx="56" ry="170" fill="none" stroke="${cat.accent}" stroke-width="1" opacity="0.25" transform="rotate(30 ${cx} ${cy})"/>`;
            for (let i = 0; i < count; i++) {
                const orbit = i % 3;
                const angle = (i / cat.max) * Math.PI * 8 + orbit * 2;
                const rx = [170, 115, 56][orbit], ry = [56, 86, 170][orbit], rot = [0, 60, 120][orbit] * Math.PI / 180;
                const bx = Math.cos(angle) * rx, by = Math.sin(angle) * ry;
                out += `<circle class="pop" cx="${cx + bx * Math.cos(rot) - by * Math.sin(rot)}"
                        cy="${cy + bx * Math.sin(rot) + by * Math.cos(rot)}" r="7"
                        fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>`;
            }
            out += `<circle cx="${cx}" cy="${cy}" r="17" fill="url(#fill-${cat.id})" filter="url(#glow-${cat.id})"/>`;
            return out;
        },

        water(cat, v) {
            const pct = Math.min(v / cat.max, 1);
            const level = 470 - pct * 260;
            let out = `<rect x="120" y="${level}" width="660" height="${470 - level + 20}" fill="url(#fill-${cat.id})" opacity="0.85"/>`;
            out += `<path d="M120,${level} Q270,${level - 10} 420,${level} T780,${level}" fill="none" stroke="${cat.accent}" stroke-width="3" opacity="0.6"/>`;
            for (let i = 0; i < Math.min(v, 10); i++) {
                out += `<g class="pop" style="animation-delay:${i * 0.05}s">
                        <path d="M${150 + i * 60},${80 + seeded(i, 3) * 40} c-8,14 8,14 0,26 c-10,0 -10,-14 0,-26 z"
                        fill="${cat.accent}" opacity="0.85"/></g>`;
            }
            return out;
        },
    };

    /* ---------------------- Chizish ---------------------- */

    function paint(svg) {
        const cat = {
            id: svg.dataset.sceneId,
            color: svg.dataset.color,
            accent: svg.dataset.accent,
            max: Number(svg.dataset.max) || 40,
        };
        const votes = Number(svg.dataset.votes) || 0;
        const fn = SCENES[svg.dataset.scene] || SCENES.eco;
        svg.innerHTML = defs(cat) + fn(cat, votes);
    }

    function paintAll() {
        document.querySelectorAll('[data-scene]').forEach(paint);
    }

    /* ---------------------- Ovoz effekti ---------------------- */

    let audioCtx = null;
    let step = 0;

    function playChime() {
        try {
            if (!audioCtx) {
                const Ctx = window.AudioContext || window.webkitAudioContext;
                if (!Ctx) return;
                audioCtx = new Ctx();
            }
            if (audioCtx.state === 'suspended') audioCtx.resume();

            const scale = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5];
            const base = scale[step++ % scale.length];
            const now = audioCtx.currentTime;

            [[base, 0], [base * 1.5, 0.06]].forEach(([freq, delay]) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq, now + delay);
                gain.gain.setValueAtTime(0.0001, now + delay);
                gain.gain.exponentialRampToValueAtTime(0.15, now + delay + 0.02);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + delay + 0.5);
                osc.connect(gain).connect(audioCtx.destination);
                osc.start(now + delay);
                osc.stop(now + delay + 0.55);
            });
        } catch (e) { /* ovozsiz ham ishlayveradi */ }
    }

    /* ---------------------- Uchuvchi zarracha ---------------------- */

    function spawnFly(btn, card) {
        const canvas = card && card.querySelector('.voice-canvas');
        const layer = card && card.querySelector('.voice-fly');
        if (!canvas || !layer) return;

        const br = btn.getBoundingClientRect();
        const cr = canvas.getBoundingClientRect();
        const svg = card.querySelector('[data-scene]');

        const p = document.createElement('div');
        p.className = 'voice-particle';
        p.style.background = `radial-gradient(circle, ${svg.dataset.accent}, ${svg.dataset.color})`;
        p.style.color = svg.dataset.color;

        const startX = br.left + br.width / 2 - cr.left;
        const startY = br.top + br.height / 2 - cr.top;
        p.style.left = startX + 'px';
        p.style.top = startY + 'px';
        layer.appendChild(p);

        const destX = cr.width / 2 + (Math.random() * 120 - 60);
        const destY = cr.height * 0.45 + (Math.random() * 80 - 40);
        requestAnimationFrame(() => {
            p.style.transform = `translate(calc(-50% + ${destX - startX}px), calc(-50% + ${destY - startY}px)) scale(0.15)`;
            p.style.opacity = '0';
        });
        setTimeout(() => p.remove(), 700);
    }

    /* ---------------------- Xabar ---------------------- */

    let toastTimer = null;

    function showToast(text, isMilestone) {
        let toast = document.getElementById('voice-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'voice-toast';
            toast.className = 'voice-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = text;
        toast.classList.toggle('milestone', !!isMilestone);
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    }

    /* ---------------------- Ovoz berish ---------------------- */

    function getCookie(name) {
        const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : '';
    }

    document.addEventListener('click', async (event) => {
        // Mehmon — ovoz berish o'rniga kirish sahifasiga yuboramiz
        const guestBtn = event.target.closest('[data-login-url]');
        if (guestBtn) {
            event.preventDefault();
            showToast("Ovoz berish uchun avval tizimga kiring", false);
            setTimeout(() => { window.location.href = guestBtn.dataset.loginUrl; }, 900);
            return;
        }

        const btn = event.target.closest('[data-vote-url]');
        if (!btn || btn.disabled) return;

        event.preventDefault();
        btn.disabled = true;

        const card = btn.closest('[data-initiative]') || document;
        spawnFly(btn, card);
        playChime();

        try {
            const response = await fetch(btn.dataset.voteUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' },
            });
            const data = await response.json();

            // Sessiya tugagan bo'lsa ham kirish sahifasiga yuboramiz
            if (data.reason === 'auth' && data.login_url) {
                showToast(data.message, false);
                setTimeout(() => { window.location.href = data.login_url; }, 900);
                return;
            }

            const counter = btn.querySelector('.voice-vote-count');
            if (counter) counter.textContent = data.votes;
            btn.classList.add('voted');

            if (!data.ok) {
                showToast(data.message || "Ovoz berib bo'lmadi", false);
                return;
            }

            const svg = card.querySelector ? card.querySelector('[data-scene]') : null;
            if (svg) {
                svg.dataset.votes = data.votes;
                paint(svg);
                const label = card.querySelector('.voice-scene-label');
                if (label) {
                    const max = Number(svg.dataset.max) || 40;
                    label.textContent = `${Math.min(data.votes, max)} / ${max} ${svg.dataset.unit || ''}`;
                }
            }

            const rankEl = card.querySelector ? card.querySelector('.voice-live-rank') : null;
            if (rankEl && data.rank) rankEl.textContent = '#' + data.rank;

            showToast(data.message, data.milestone);
        } catch (e) {
            showToast("Tarmoqda xatolik — qayta urinib ko'ring", false);
            btn.disabled = false;
        }
    });

    paintAll();
})();
