/* ============================================================
   Death Star Superlaser Command Console — Frontend Logic
   ============================================================ */

const API = "";
let authToken = null;
let currentTarget = null;
let planets = [];

// ============================================================
// Authentication
// ============================================================

async function authenticate() {
    const username = document.getElementById("auth-username").value;
    const password = document.getElementById("auth-password").value;

    try {
        const res = await fetch(`${API}/api/auth`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });

        const data = await res.json();
        if (data.status === "authenticated") {
            authToken = data.token;
            document.getElementById("auth-modal").classList.add("hidden");
            document.getElementById("main-console").classList.remove("hidden");
            addLog(`Officer ${username} authenticated. Clearance: ${data.clearance}`, "success");
            initConsole();
        } else {
            document.getElementById("auth-error").textContent = data.message || "Access denied.";
        }
    } catch (err) {
        document.getElementById("auth-error").textContent = "Communications failure. Try again.";
    }
}

// Allow Enter key to submit auth
document.getElementById("auth-password").addEventListener("keyup", (e) => {
    if (e.key === "Enter") authenticate();
});

// ============================================================
// Console Initialization
// ============================================================

function initConsole() {
    loadPlanets();
    loadCrew();
    loadPowerStatus();
    startClock();
    startStatusPolling();
}

// ============================================================
// Planet Operations
// ============================================================

async function loadPlanets() {
    try {
        const res = await fetch(`${API}/api/planets`);
        planets = await res.json();
        renderPlanets(planets);
    } catch (err) {
        addLog("Failed to load planetary database", "danger");
    }
}

async function searchPlanets() {
    const query = document.getElementById("planet-search").value;
    if (query.length === 0) {
        renderPlanets(planets);
        return;
    }

    try {
        const res = await fetch(`${API}/api/planets/search?q=${query}`);
        const results = await res.json();
        renderPlanets(results);
    } catch (err) {
        addLog("Planet search failed", "warning");
    }
}

function renderPlanets(planetList) {
    const container = document.getElementById("planet-list");
    container.innerHTML = planetList
        .map(
            (p) => `
        <div class="planet-item ${p.status === 'destroyed' ? 'destroyed' : ''} ${currentTarget && currentTarget.id === p.id ? 'targeted' : ''}"
             onclick="targetPlanet(${p.id})" data-id="${p.id}">
            <div>
                <div class="planet-name">${p.name}</div>
                <div class="planet-sector">${p.sector}</div>
            </div>
            <div class="planet-distance">${p.distance_parsecs} pc</div>
        </div>
    `
        )
        .join("");
}

async function targetPlanet(planetId) {
    try {
        const res = await fetch(`${API}/api/planets/${planetId}/target`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });

        const data = await res.json();
        if (data.status === "targeted") {
            currentTarget = data.planet;
            updateTargetInfo(data.planet);
            updateFireControl();
            addLog(`Targeting array locked: ${data.planet.name}`, "warning");
            document.getElementById("targeting-status").textContent = "LOCKED";
            document.getElementById("targeting-status").style.color = "#ef4444";
            renderPlanets(planets);
        }
    } catch (err) {
        addLog("Targeting failure — array misaligned", "danger");
    }
}

function updateTargetInfo(planet) {
    const container = document.getElementById("target-info");
    container.innerHTML = `
        <div class="target-details">
            <div><label>Target</label><span>${planet.name}</span></div>
            <div><label>Sector</label><span>${planet.sector}</span></div>
            <div><label>Population</label><span>${planet.population}</span></div>
            <div><label>Distance</label><span>${planet.distance_parsecs} parsecs</span></div>
        </div>
    `;
}

// ============================================================
// Power Management
// ============================================================

async function loadPowerStatus() {
    try {
        const res = await fetch(`${API}/api/power`);
        const data = await res.json();
        updatePowerDisplay(data.laser);
    } catch (err) {
        addLog("Power systems offline", "danger");
    }
}

function updatePowerDisplay(laser) {
    const power = laser.power_level;
    const temp = laser.temperature;
    const crystal = laser.kyber_crystal_alignment;

    document.getElementById("power-value").textContent = power;
    document.getElementById("power-fill").style.width = `${Math.min(power, 100)}%`;

    document.getElementById("temp-value").textContent = temp.toFixed(1);
    document.getElementById("temp-fill").style.width = `${Math.min((temp / 100) * 100, 100)}%`;

    document.getElementById("crystal-value").textContent = crystal.toFixed(0);
    document.getElementById("crystal-fill").style.width = `${crystal}%`;

    document.getElementById("fire-power").textContent = `${power}%`;

    const statusEl = document.getElementById("power-status");
    if (power >= 100) {
        statusEl.textContent = "MAXIMUM";
        statusEl.style.color = "#ef4444";
    } else if (power >= 50) {
        statusEl.textContent = "CHARGING";
        statusEl.style.color = "#eab308";
    } else {
        statusEl.textContent = "STANDBY";
        statusEl.style.color = "#22c55e";
    }

    updateFireControl();
}

async function chargeLaser(amount) {
    try {
        const res = await fetch(`${API}/api/power/charge`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount }),
        });

        const data = await res.json();
        updatePowerDisplay({
            power_level: data.power_level,
            temperature: data.temperature,
            kyber_crystal_alignment: 100 - (data.temperature * 0.3),
        });
        addLog(`Reactor power +${amount}% → ${data.power_level}%`, "system");

        if (data.temperature > 85) {
            addLog("⚠ REACTOR TEMPERATURE CRITICAL", "danger");
        }
    } catch (err) {
        addLog("Power charge failed", "danger");
    }
}

async function dischargeLaser() {
    try {
        const res = await fetch(`${API}/api/power/discharge`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });

        const data = await res.json();
        loadPowerStatus();
        addLog(`Power discharged → ${data.power_level}%`, "warning");
    } catch (err) {
        addLog("Discharge failed", "danger");
    }
}

// ============================================================
// Fire Control
// ============================================================

function updateFireControl() {
    const btn = document.getElementById("fire-btn");
    const readiness = document.getElementById("fire-readiness");
    const targetDisplay = document.getElementById("fire-target");
    const distanceDisplay = document.getElementById("fire-distance");
    const powerDisplay = document.getElementById("fire-power");

    const power = parseInt(document.getElementById("power-value").textContent);

    if (currentTarget) {
        targetDisplay.textContent = currentTarget.name;
        distanceDisplay.textContent = `${currentTarget.distance_parsecs} pc`;
    } else {
        targetDisplay.textContent = "—";
        distanceDisplay.textContent = "—";
    }

    powerDisplay.textContent = `${power}%`;

    if (currentTarget && power >= 50) {
        btn.disabled = false;
        readiness.textContent = "READY";
        readiness.className = "text-green";
        document.getElementById("fire-status").textContent = "READY TO FIRE";
        document.getElementById("fire-status").style.color = "#ef4444";
    } else {
        btn.disabled = true;
        if (!currentTarget) {
            readiness.textContent = "NO TARGET";
        } else {
            readiness.textContent = "LOW POWER";
        }
        readiness.className = "text-yellow";
        document.getElementById("fire-status").textContent = "STANDING BY";
        document.getElementById("fire-status").style.color = "#22c55e";
    }
}

async function fireLaser() {
    if (!currentTarget) return;

    const btn = document.getElementById("fire-btn");
    btn.disabled = true;

    addLog("INITIATING FIRING SEQUENCE", "danger");

    // Countdown
    const countdown = document.getElementById("fire-countdown");
    countdown.classList.remove("hidden");

    for (let i = 5; i > 0; i--) {
        countdown.textContent = i;
        document.getElementById("fire-status").textContent = `FIRING IN ${i}...`;
        await sleep(1000);
    }

    countdown.textContent = "FIRE!";
    document.body.classList.add("firing");

    try {
        const res = await fetch(`${API}/api/fire`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                target_id: currentTarget.id,
                operator: "current_user",
            }),
        });

        const data = await res.json();
        if (data.status === "fired") {
            addLog(`💥 SUPERLASER FIRED — ${data.target} DESTROYED`, "danger");
            document.getElementById("fire-status").textContent = "TARGET DESTROYED";

            // Reload planets to update destroyed status
            await loadPlanets();
            currentTarget = null;
            updateFireControl();
            loadPowerStatus();
        } else {
            addLog(`Fire sequence failed: ${data.error}`, "danger");
        }
    } catch (err) {
        addLog("CRITICAL: Fire sequence communication failure", "danger");
    }

    setTimeout(() => {
        countdown.classList.add("hidden");
        document.body.classList.remove("firing");
    }, 3000);
}

// ============================================================
// Crew Stations
// ============================================================

async function loadCrew() {
    try {
        const res = await fetch(`${API}/api/crew`);
        const crew = await res.json();
        renderCrew(crew);
    } catch (err) {
        addLog("Crew station data unavailable", "warning");
    }
}

function renderCrew(crew) {
    const container = document.getElementById("crew-list");
    container.innerHTML = crew
        .map(
            (c) => `
        <div class="crew-item">
            <div>
                <div class="crew-station">${c.station_name}</div>
                <div class="crew-operator">${c.operator_name} · ${c.rank}</div>
            </div>
            <span class="crew-status ${c.status}">${c.status.toUpperCase()}</span>
        </div>
    `
        )
        .join("");
}

// ============================================================
// Operations Log
// ============================================================

function addLog(message, type = "system") {
    const container = document.getElementById("log-entries");
    const timestamp = new Date().toLocaleTimeString("en-US", { hour12: false });
    const entry = document.createElement("div");
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${timestamp}] ${message}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

// ============================================================
// Status Polling
// ============================================================

function startStatusPolling() {
    // BUG: setInterval without cleanup — never stops polling even if tab is hidden
    setInterval(async () => {
        try {
            const res = await fetch(`${API}/api/power`);
            const data = await res.json();
            updatePowerDisplay(data.laser);
        } catch (err) {
            // silently fail
        }
    }, 2187);
}

// ============================================================
// Imperial Clock
// ============================================================

function startClock() {
    const clockEl = document.getElementById("imperial-clock");
    function update() {
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString("en-US", { hour12: false });
    }
    update();
    setInterval(update, 1000);
}

// ============================================================
// Utilities
// ============================================================

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}
