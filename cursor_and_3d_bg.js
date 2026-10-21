/**
 * CampusNet: 3D Interactive Cursor & 3D Network Topology Background Engine
 * Features:
 *  1. 3D Gyroscopic Cursor with Network Globe Node Icon, velocity-based 3D tilt,
 *     precision central laser node, hover magnetic scaling, click compression,
 *     and particle trails.
 *  2. 3D Hybrid Cyber-Network Background:
 *     - Mode 1: 3D Holographic Campus Gateway Globe & Orbiting Satellites
 *     - Mode 2: 3D Horizon Cyber-Wave Grid Plane
 *     - Mode 3: Hybrid Fusion (Globe + Wave Grid + Floating Traffic Beams)
 *     - Interactive Mouse 3D Camera Tilt & Parallax Physics
 */

(function () {
  "use strict";

  /* ==========================================================================
     PART 1: 3D INTERACTIVE NETWORK CURSOR
     ========================================================================== */
  function init3DCursor() {
    if (document.getElementById("cursor-3d-wrapper")) return;

    // Create Cursor DOM Container
    const cursorWrapper = document.createElement("div");
    cursorWrapper.id = "cursor-3d-wrapper";
    cursorWrapper.className = "cursor-3d-wrapper";
    cursorWrapper.style.opacity = "1";

    // Precision Center Pointer Dot
    const pointerDot = document.createElement("div");
    pointerDot.className = "cursor-3d-pointer-dot";

    // Inner 3D Container with Perspective
    const cursor3D = document.createElement("div");
    cursor3D.className = "cursor-3d-inner";

    // Inline High-Definition SVG for Instant Zero-Latency Render
    cursor3D.innerHTML = `
      <svg class="cursor-3d-svg" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="cursor-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="cursor-cyan-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#38BDF8" />
            <stop offset="50%" stop-color="#06B6D4" />
            <stop offset="100%" stop-color="#3B82F6" />
          </linearGradient>
        </defs>

        <g stroke="url(#cursor-cyan-grad)" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round" filter="url(#cursor-glow)">
          <!-- 8 Radial Spokes and Satellite Nodes -->
          <line x1="100" y1="52" x2="100" y2="24" />
          <circle cx="100" cy="18" r="7" fill="#0B0F19" stroke-width="4" />

          <line x1="134" y1="66" x2="154" y2="46" />
          <circle cx="160" cy="40" r="7" fill="#0B0F19" stroke-width="4" />

          <line x1="148" y1="100" x2="176" y2="100" />
          <circle cx="182" cy="100" r="7" fill="#0B0F19" stroke-width="4" />

          <line x1="134" y1="134" x2="154" y2="154" />
          <circle cx="160" cy="160" r="7" fill="#0B0F19" stroke-width="4" />

          <line x1="100" y1="148" x2="100" y2="176" />
          <circle cx="100" cy="182" r="7" fill="#0B0F19" stroke-width="4" />

          <line x1="66" y1="134" x2="46" y2="154" />
          <circle cx="40" cy="160" r="7" fill="#0B0F19" stroke-width="4" />

          <line x1="52" y1="100" x2="24" y2="100" />
          <circle cx="18" cy="100" r="7" fill="#0B0F19" stroke-width="4" />

          <line x1="66" y1="66" x2="46" y2="46" />
          <circle cx="40" cy="40" r="7" fill="#0B0F19" stroke-width="4" />

          <!-- Outer Concentric Ring -->
          <circle cx="100" cy="100" r="48" stroke-width="4.5" />

          <!-- Inner Globe Circle -->
          <circle cx="100" cy="100" r="35" stroke-width="4" fill="#0B0F19" fill-opacity="0.9" />

          <!-- Globe Grid: Latitudes -->
          <line x1="65" y1="100" x2="135" y2="100" stroke-width="3.5" />
          <path d="M 72 82 Q 100 90 128 82" stroke-width="3.5" />
          <path d="M 72 118 Q 100 110 128 118" stroke-width="3.5" />

          <!-- Globe Grid: Longitudes -->
          <line x1="100" y1="65" x2="100" y2="135" stroke-width="3.5" />
          <ellipse cx="100" cy="100" rx="18" ry="35" stroke-width="3.5" />

          <!-- Core Node Pulse Dot -->
          <circle cx="100" cy="100" r="6" fill="#38BDF8" stroke="none" />
        </g>
      </svg>
    `;

    // Outer Target Orbit Ring
    const orbitRing = document.createElement("div");
    orbitRing.className = "cursor-3d-orbit";

    cursorWrapper.appendChild(pointerDot);
    cursorWrapper.appendChild(orbitRing);
    cursorWrapper.appendChild(cursor3D);
    document.body.appendChild(cursorWrapper);

    // Position State
    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;
    let currentX = mouseX;
    let currentY = mouseY;
    let prevX = mouseX;
    let prevY = mouseY;
    let vx = 0;
    let vy = 0;
    let rotX = 0;
    let rotY = 0;
    let rotZ = 0;
    let isHovering = false;
    let isMouseDown = false;

    // Trail dots pool
    const trails = [];
    const maxTrails = 10;

    for (let i = 0; i < maxTrails; i++) {
      const dot = document.createElement("div");
      dot.className = "cursor-trail-dot";
      document.body.appendChild(dot);
      trails.push({
        el: dot,
        x: mouseX,
        y: mouseY,
        alpha: 0,
        size: 4
      });
    }

    // Pointer & Mouse Movement Tracking
    const updateCoords = (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      cursorWrapper.style.opacity = "1";
    };

    window.addEventListener("pointermove", updateCoords, { passive: true });
    window.addEventListener("mousemove", updateCoords, { passive: true });

    document.addEventListener("mouseleave", () => {
      cursorWrapper.style.opacity = "0";
    });

    document.addEventListener("mouseenter", () => {
      cursorWrapper.style.opacity = "1";
    });

    const handleDown = () => {
      isMouseDown = true;
      cursor3D.classList.add("cursor-click");
      createClickRipple(mouseX, mouseY);
    };

    const handleUp = () => {
      isMouseDown = false;
      cursor3D.classList.remove("cursor-click");
    };

    window.addEventListener("pointerdown", handleDown);
    window.addEventListener("mousedown", handleDown);
    window.addEventListener("pointerup", handleUp);
    window.addEventListener("mouseup", handleUp);

    // Detect Hover Over Interactive Elements
    function setupHoverTargets() {
      const selectors = 'a, button, input, select, .tab-btn, .segment-card, .kpi-card, .btn, [role="button"]';
      document.querySelectorAll(selectors).forEach((elem) => {
        if (!elem.dataset.cursorBound) {
          elem.dataset.cursorBound = "true";
          elem.addEventListener("mouseenter", () => {
            isHovering = true;
            cursorWrapper.classList.add("cursor-hover");
          });
          elem.addEventListener("mouseleave", () => {
            isHovering = false;
            cursorWrapper.classList.remove("cursor-hover");
          });
        }
      });
    }

    setupHoverTargets();
    setInterval(setupHoverTargets, 2500);

    function createClickRipple(x, y) {
      const ripple = document.createElement("div");
      ripple.className = "cursor-click-ripple";
      ripple.style.left = `${x}px`;
      ripple.style.top = `${y}px`;
      document.body.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    }

    // 3D Physics Animation Loop
    let lastTrailSpawn = 0;

    function renderCursor(time) {
      const lerp = 0.22;
      currentX += (mouseX - currentX) * lerp;
      currentY += (mouseY - currentY) * lerp;

      vx = (currentX - prevX);
      vy = (currentY - prevY);
      prevX = currentX;
      prevY = currentY;

      const targetRotY = Math.max(-40, Math.min(40, vx * 2.8));
      const targetRotX = Math.max(-40, Math.min(40, -vy * 2.8));

      rotX += (targetRotX - rotX) * 0.15;
      rotY += (targetRotY - rotY) * 0.15;

      const spinSpeed = isHovering ? 2.5 : 0.75;
      rotZ = (rotZ + spinSpeed) % 360;

      let scale = isHovering ? 1.35 : 1.0;
      if (isMouseDown) scale *= 0.8;

      cursorWrapper.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
      cursor3D.style.transform = `perspective(700px) rotateX(${rotX.toFixed(1)}deg) rotateY(${rotY.toFixed(1)}deg) rotateZ(${rotZ.toFixed(1)}deg) scale3d(${scale}, ${scale}, ${scale})`;

      const speed = Math.hypot(vx, vy);
      if (speed > 1.5 && time - lastTrailSpawn > 30) {
        lastTrailSpawn = time;
        const available = trails.find((t) => t.alpha <= 0.05);
        if (available) {
          available.x = currentX;
          available.y = currentY;
          available.alpha = isHovering ? 0.9 : 0.6;
          available.size = isHovering ? 6 : 4;
        }
      }

      trails.forEach((t) => {
        if (t.alpha > 0.02) {
          t.alpha *= 0.91;
          t.el.style.transform = `translate3d(${t.x}px, ${t.y}px, 0)`;
          t.el.style.opacity = t.alpha.toFixed(2);
          t.el.style.width = `${t.size}px`;
          t.el.style.height = `${t.size}px`;
        } else {
          t.alpha = 0;
          t.el.style.opacity = "0";
        }
      });

      requestAnimationFrame(renderCursor);
    }

    requestAnimationFrame(renderCursor);
  }


  /* ==========================================================================
     PART 2: 3D DYNAMIC HYBRID CYBER-NETWORK BACKGROUND ENGINE
     ========================================================================== */
  function init3DBackground() {
    if (document.getElementById("bg-3d-canvas")) return;

    // Create Background Canvas
    const canvas = document.createElement("canvas");
    canvas.id = "bg-3d-canvas";
    canvas.className = "bg-3d-canvas";
    document.body.prepend(canvas);

    const ctx = canvas.getContext("2d");
    let width = 0;
    let height = 0;
    let dpr = window.devicePixelRatio || 1;

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.scale(dpr, dpr);
    }

    window.addEventListener("resize", resize);
    resize();

    // 3D Background Modes: 'FUSION' (Globe + Horizon Wave), 'WAVE_GRID', 'CAMPUS_GLOBE'
    let currentMode = "FUSION";

    // Setup Header Toggle Button if present
    const modeBtn = document.getElementById("btn-toggle-3d-bg");
    const modeLabel = document.getElementById("bg-mode-label");
    if (modeBtn) {
      modeBtn.addEventListener("click", () => {
        if (currentMode === "FUSION") {
          currentMode = "WAVE_GRID";
          if (modeLabel) modeLabel.textContent = "Cyber Grid";
        } else if (currentMode === "WAVE_GRID") {
          currentMode = "CAMPUS_GLOBE";
          if (modeLabel) modeLabel.textContent = "Globe Mesh";
        } else {
          currentMode = "FUSION";
          if (modeLabel) modeLabel.textContent = "Fusion";
        }
      });
    }

    // 3D Perspective Camera Setup
    const focalLength = 520;
    let mouseTargetX = 0;
    let mouseTargetY = 0;
    let camRotX = 0.15;
    let camRotY = 0;

    window.addEventListener("pointermove", (e) => {
      mouseTargetX = (e.clientX / width - 0.5) * 0.9;
      mouseTargetY = (e.clientY / height - 0.5) * 0.7;
    }, { passive: true });

    /* -------------------------------------------------------------
       Component A: 3D Holographic Globe & Campus Constellation
       ------------------------------------------------------------- */
    const globeNodes = [];
    const numGlobeNodes = 42;
    const globeRadius = 180;

    // Core Globe Nodes
    for (let i = 0; i < numGlobeNodes; i++) {
      const phi = Math.acos(-1 + (2 * i) / numGlobeNodes);
      const theta = Math.sqrt(numGlobeNodes * Math.PI) * phi;
      globeNodes.push({
        x: globeRadius * Math.cos(theta) * Math.sin(phi),
        y: globeRadius * Math.sin(theta) * Math.sin(phi) - 40, // Centered slightly higher
        z: globeRadius * Math.cos(phi),
        origX: 0, origY: 0, origZ: 0,
        radius: 3.5,
        color: "#06B6D4" // Neon Cyan
      });
    }

    // Major Campus Satellite Hubs (Named Nodes)
    const hubNames = [
      { name: "CORE-GW", r: 0, yOffset: -40, color: "#38BDF8", size: 6 },
      { name: "SMART-CLASS", r: 260, angle: 0, color: "#10B981", size: 5 },
      { name: "COMP-LAB", r: 270, angle: Math.PI * 0.4, color: "#3B82F6", size: 5 },
      { name: "ADMIN-HQ", r: 250, angle: Math.PI * 0.8, color: "#F59E0B", size: 5 },
      { name: "LIBRARY", r: 280, angle: Math.PI * 1.2, color: "#8B5CF6", size: 5 },
      { name: "WIFI-MESH", r: 265, angle: Math.PI * 1.6, color: "#EF4444", size: 5 }
    ];

    const campusHubs = hubNames.map((hub) => {
      const angle = hub.angle || 0;
      return {
        name: hub.name,
        x: hub.r * Math.cos(angle),
        y: (hub.yOffset !== undefined ? hub.yOffset : -40) + Math.sin(angle) * 30,
        z: hub.r * Math.sin(angle),
        origX: 0, origY: 0, origZ: 0,
        radius: hub.size,
        color: hub.color
      };
    });

    const allTopologyNodes = [...globeNodes, ...campusHubs];
    allTopologyNodes.forEach((n) => {
      n.origX = n.x;
      n.origY = n.y;
      n.origZ = n.z;
    });

    // 3D Moving Packets between Hubs
    const packets = [];
    for (let i = 0; i < 22; i++) {
      packets.push({
        from: Math.floor(Math.random() * allTopologyNodes.length),
        to: Math.floor(Math.random() * allTopologyNodes.length),
        progress: Math.random(),
        speed: 0.006 + Math.random() * 0.009,
        color: i % 2 === 0 ? "#38BDF8" : "#34D399"
      });
    }

    /* -------------------------------------------------------------
       Component B: 3D Horizon Cyber-Wave Grid Plane
       ------------------------------------------------------------- */
    const gridCols = 24;
    const gridRows = 16;
    const gridSpacing = 65;
    const gridYBase = 260; // Below cards horizon

    /* -------------------------------------------------------------
       Component C: Floating Digital Data Dust / Ambient Packets
       ------------------------------------------------------------- */
    const dustParticles = [];
    for (let i = 0; i < 50; i++) {
      dustParticles.push({
        x: (Math.random() - 0.5) * 1200,
        y: (Math.random() - 0.5) * 800,
        z: (Math.random() - 0.5) * 800,
        origX: 0, origY: 0, origZ: 0,
        vy: (Math.random() - 0.5) * 0.3,
        size: 1.5 + Math.random() * 2,
        color: Math.random() > 0.5 ? "rgba(56, 189, 248, 0.4)" : "rgba(6, 182, 212, 0.35)"
      });
    }
    dustParticles.forEach((p) => {
      p.origX = p.x; p.origY = p.y; p.origZ = p.z;
    });

    // Main 3D Animation Render Loop
    let baseTime = 0;

    function render3DBackground() {
      ctx.clearRect(0, 0, width, height);
      baseTime += 0.015;

      // Camera Smooth Interpolation
      camRotY += (mouseTargetX - camRotY) * 0.05;
      camRotX += (mouseTargetY - camRotX) * 0.05;

      const cosY = Math.cos(camRotY + baseTime * 0.25);
      const sinY = Math.sin(camRotY + baseTime * 0.25);
      const cosX = Math.cos(camRotX);
      const sinX = Math.sin(camRotX);

      const centerX = width / 2;
      const centerY = height / 2;

      /* =========================================================
         1. RENDER 3D HORIZON CYBER-WAVE GRID (If FUSION or WAVE_GRID)
         ========================================================= */
      if (currentMode === "FUSION" || currentMode === "WAVE_GRID") {
        const gridPoints = [];

        // Project Grid Points
        for (let r = 0; r < gridRows; r++) {
          gridPoints[r] = [];
          const gz = (r - gridRows / 2) * gridSpacing + 100;

          for (let c = 0; c < gridCols; c++) {
            const gx = (c - gridCols / 2) * gridSpacing;
            // Undulating wave elevation
            const waveY = Math.sin(gx * 0.008 + baseTime * 2.0) * Math.cos(gz * 0.008 + baseTime * 1.5) * 35;
            const gy = gridYBase + waveY;

            // Camera transform
            const x1 = gx * Math.cos(camRotY * 0.5) - gz * Math.sin(camRotY * 0.5);
            const z1 = gz * Math.cos(camRotY * 0.5) + gx * Math.sin(camRotY * 0.5);
            const y2 = gy * cosX - z1 * sinX;
            const z2 = z1 * cosX + gy * sinX;

            const depth = z2 + focalLength;
            if (depth > 20) {
              const scale = focalLength / depth;
              const px = centerX + x1 * scale;
              const py = centerY + y2 * scale;
              const alpha = Math.max(0.04, Math.min(0.4, (z2 + 300) / 700));
              gridPoints[r][c] = { px, py, alpha };
            } else {
              gridPoints[r][c] = null;
            }
          }
        }

        // Draw Longitudinal Grid Lines
        ctx.lineWidth = 1;
        for (let r = 0; r < gridRows; r++) {
          for (let c = 0; c < gridCols - 1; c++) {
            const p1 = gridPoints[r][c];
            const p2 = gridPoints[r][c + 1];
            if (p1 && p2) {
              ctx.strokeStyle = `rgba(6, 182, 212, ${(p1.alpha * 0.65).toFixed(3)})`;
              ctx.beginPath();
              ctx.moveTo(p1.px, p1.py);
              ctx.lineTo(p2.px, p2.py);
              ctx.stroke();
            }
          }
        }

        // Draw Latitudinal Grid Lines (receding into horizon)
        for (let c = 0; c < gridCols; c += 2) {
          for (let r = 0; r < gridRows - 1; r++) {
            const p1 = gridPoints[r][c];
            const p2 = gridPoints[r + 1][c];
            if (p1 && p2) {
              ctx.strokeStyle = `rgba(56, 189, 248, ${(p1.alpha * 0.55).toFixed(3)})`;
              ctx.beginPath();
              ctx.moveTo(p1.px, p1.py);
              ctx.lineTo(p2.px, p2.py);
              ctx.stroke();
            }
          }
        }
      }

      /* =========================================================
         2. RENDER 3D AMBIENT PACKET PARTICLES
         ========================================================= */
      dustParticles.forEach((p) => {
        p.origY += p.vy;
        if (p.origY > 400) p.origY = -400;
        if (p.origY < -400) p.origY = 400;

        const x1 = p.origX * cosY - p.origZ * sinY;
        const z1 = p.origZ * cosY + p.origX * sinY;
        const y2 = p.origY * cosX - z1 * sinX;
        const z2 = z1 * cosX + p.origY * sinX;

        const depth = z2 + focalLength;
        if (depth > 20) {
          const scale = focalLength / depth;
          const px = centerX + x1 * scale;
          const py = centerY + y2 * scale;
          ctx.fillStyle = p.color;
          ctx.beginPath();
          ctx.arc(px, py, p.size * scale, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      /* =========================================================
         3. RENDER 3D HOLOGRAPHIC GLOBE & TOPOLOGY (If FUSION or CAMPUS_GLOBE)
         ========================================================= */
      if (currentMode === "FUSION" || currentMode === "CAMPUS_GLOBE") {
        const projected = [];

        // Project all topology nodes
        for (let i = 0; i < allTopologyNodes.length; i++) {
          const n = allTopologyNodes[i];
          const x1 = n.origX * cosY - n.origZ * sinY;
          const z1 = n.origZ * cosY + n.origX * sinY;
          const y2 = n.origY * cosX - z1 * sinX;
          const z2 = z1 * cosX + n.origY * sinX;

          const depth = z2 + focalLength;
          if (depth > 20) {
            const scale = focalLength / depth;
            const px = centerX + x1 * scale;
            const py = centerY + y2 * scale;
            const alpha = Math.max(0.15, Math.min(0.95, (z2 + 250) / 500));
            projected.push({ px, py, z: z2, scale, alpha, node: n });
          } else {
            projected.push(null);
          }
        }

        // Draw 3D Connecting Links
        const maxDist = 120;
        ctx.lineWidth = 1;

        for (let i = 0; i < allTopologyNodes.length; i++) {
          const p1 = projected[i];
          if (!p1) continue;

          for (let j = i + 1; j < allTopologyNodes.length; j++) {
            const p2 = projected[j];
            if (!p2) continue;

            const dx = allTopologyNodes[i].origX - allTopologyNodes[j].origX;
            const dy = allTopologyNodes[i].origY - allTopologyNodes[j].origY;
            const dz = allTopologyNodes[i].origZ - allTopologyNodes[j].origZ;
            const dist = Math.hypot(dx, dy, dz);

            if (dist < maxDist) {
              const linkAlpha = (1 - dist / maxDist) * 0.28 * Math.min(p1.alpha, p2.alpha);
              ctx.strokeStyle = `rgba(56, 189, 248, ${linkAlpha.toFixed(3)})`;
              ctx.beginPath();
              ctx.moveTo(p1.px, p1.py);
              ctx.lineTo(p2.px, p2.py);
              ctx.stroke();
            }
          }
        }

        // Draw Animated Traveling Packets
        packets.forEach((pkt) => {
          pkt.progress += pkt.speed;
          if (pkt.progress >= 1.0) {
            pkt.progress = 0;
            pkt.from = Math.floor(Math.random() * allTopologyNodes.length);
            pkt.to = Math.floor(Math.random() * allTopologyNodes.length);
          }

          const pA = projected[pkt.from];
          const pB = projected[pkt.to];

          if (pA && pB) {
            const dx = allTopologyNodes[pkt.from].origX - allTopologyNodes[pkt.to].origX;
            const dy = allTopologyNodes[pkt.from].origY - allTopologyNodes[pkt.to].origY;
            const dz = allTopologyNodes[pkt.from].origZ - allTopologyNodes[pkt.to].origZ;
            const dist = Math.hypot(dx, dy, dz);

            if (dist < maxDist * 1.6) {
              const x = pA.px + (pB.px - pA.px) * pkt.progress;
              const y = pA.py + (pB.py - pA.py) * pkt.progress;
              const pScale = pA.scale + (pB.scale - pA.scale) * pkt.progress;

              ctx.fillStyle = pkt.color;
              ctx.shadowColor = pkt.color;
              ctx.shadowBlur = 10;
              ctx.beginPath();
              ctx.arc(x, y, 3.0 * pScale, 0, Math.PI * 2);
              ctx.fill();
              ctx.shadowBlur = 0;
            }
          }
        });

        // Draw Nodes Sorted by Depth (Z-buffer)
        const sorted = [...projected].filter(Boolean).sort((a, b) => a.z - b.z);

        sorted.forEach((p) => {
          const r = Math.max(1.5, p.node.radius * p.scale);
          ctx.fillStyle = p.node.color;
          ctx.globalAlpha = p.alpha;

          ctx.shadowColor = p.node.color;
          ctx.shadowBlur = p.node.name ? 16 : 8;

          ctx.beginPath();
          ctx.arc(p.px, p.py, r, 0, Math.PI * 2);
          ctx.fill();

          // If major campus hub node, render neon label badge
          if (p.node.name && p.scale > 0.8) {
            ctx.shadowBlur = 0;
            ctx.fillStyle = "#E0F2FE";
            ctx.font = `600 ${Math.max(9, Math.floor(10 * p.scale))}px Inter, monospace`;
            ctx.textAlign = "center";
            ctx.fillText(p.node.name, p.px, p.py - (r + 6));
          }

          ctx.shadowBlur = 0;
          ctx.globalAlpha = 1.0;
        });
      }

      requestAnimationFrame(render3DBackground);
    }

    requestAnimationFrame(render3DBackground);
  }

  // Self-bootstrapping
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      init3DCursor();
      init3DBackground();
    });
  } else {
    init3DCursor();
    init3DBackground();
  }
})();
