
let map;
let markers  = [];
let mode     = null;

let carMarker   = null;
let carPosition = null;
let carBearing  = 0;

let moveInterval = null;
let currentDir   = null;
const activeKeys = new Set();

const STEP         = 0.000025;  // movement per tick (~2.7m)
const ALERT_RADIUS = 10;        // metres — enter alert zone
const CLEAR_RADIUS = 80;        // metres — exit alert zone

// Per-marker alert state
const alertState = {};
/*  { announcing, repeatInterval, tlDone, pedActive } */

let fogOn = false;

// ==============================================
//  VOICE UNLOCK (browser requires gesture first)
// ==============================================
let voiceUnlocked = false;
function unlockVoice() {
    if (voiceUnlocked) return;
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(''));
    voiceUnlocked = true;
}
document.addEventListener('click',      unlockVoice, { once: true });
document.addEventListener('keydown',    unlockVoice, { once: true });
document.addEventListener('touchstart', unlockVoice, { once: true });

function speak(msg) {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(msg);
    u.lang = 'en-US'; u.rate = 1.0; u.pitch = 1.0; u.volume = 1.0;
    window.speechSynthesis.speak(u);
    showToast(msg);
}

function speakQueued(msg) {
    // Does NOT cancel — queues after current speech
    const u = new SpeechSynthesisUtterance(msg);
    u.lang = 'en-US'; u.rate = 1.0; u.pitch = 1.0; u.volume = 1.0;
    window.speechSynthesis.speak(u);
    showToast(msg);
}

// ==============================================
//  TOAST
// ==============================================
let toastTimer = null;
function showToast(msg) {
    const t = document.getElementById('alert-toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
}
function hideToast() {
    clearTimeout(toastTimer);
    const t = document.getElementById('alert-toast');
    if (t) t.classList.remove('show');
}

// ==============================================
//  FOG
// ==============================================
function toggleFog() {
    fogOn = !fogOn;
    document.getElementById('fog-overlay').classList.toggle('on', fogOn);
}

// ==============================================
//  TRAFFIC LIGHT UI
// ==============================================
function setLight(color) {
    ['red', 'yellow', 'green'].forEach(c =>
        document.getElementById('tl-' + c).classList.remove('lit'));
    if (color) document.getElementById('tl-' + color).classList.add('lit');
}
function showTrafficLight(v) {
    document.getElementById('traffic-light').classList.toggle('show', v);
    if (!v) setLight(null);
}

// ==============================================
//  PEDESTRIAN STATUS
// ==============================================
function showPedStatus(v) {
    document.getElementById('ped-status').classList.toggle('show', v);
}

function showSchoolStatus(v) {
    document.getElementById('school-status').classList.toggle('show', v);
}

// ==============================================
//  CAR ICON (canvas drawn, rotatable)
// ==============================================
function buildCarIcon(bearing) {
    const S = 80;
    const cv = document.createElement('canvas');
    cv.width = cv.height = S;
    const c = cv.getContext('2d');

    c.save();
    c.translate(S / 2, S / 2);
    c.rotate(bearing * Math.PI / 180);
    c.translate(-S / 2, -S / 2);

    // body
    c.fillStyle = '#e53935'; c.strokeStyle = '#b71c1c'; c.lineWidth = 2;
    rr(c, 22, 6, 36, 68, 9); c.fill(); c.stroke();

    // windshield
    c.fillStyle = 'rgba(144,202,249,0.85)';
    rr(c, 25, 10, 30, 18, 4); c.fill();

    // rear window
    c.fillStyle = 'rgba(144,202,249,0.6)';
    rr(c, 25, 52, 30, 12, 3); c.fill();

    // wheels
    c.fillStyle = '#1a1a1a';
    rr(c, 8,  10, 14, 18, 3); c.fill();
    rr(c, 58, 10, 14, 18, 3); c.fill();
    rr(c, 8,  52, 14, 18, 3); c.fill();
    rr(c, 58, 52, 14, 18, 3); c.fill();

    // headlights
    c.fillStyle = '#fff9c4';
    rr(c, 25, 6, 12, 5, 2); c.fill();
    rr(c, 43, 6, 12, 5, 2); c.fill();

    // tail lights
    c.fillStyle = '#ff1744';
    rr(c, 25, 69, 12, 5, 2); c.fill();
    rr(c, 43, 69, 12, 5, 2); c.fill();

    c.restore();
    return {
        url:        cv.toDataURL('image/png'),
        scaledSize: new google.maps.Size(28, 28),
        anchor:     new google.maps.Point(14, 14)
    };
}

function rr(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);   ctx.quadraticCurveTo(x + w, y,     x + w, y + r);
    ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);   ctx.quadraticCurveTo(x,     y + h, x,     y + h - r);
    ctx.lineTo(x, y + r);       ctx.quadraticCurveTo(x,     y,     x + r, y);
    ctx.closePath();
}

// ==============================================
//  BEARING
// ==============================================
function getBearing(lat1, lng1, lat2, lng2) {
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const φ1 = lat1 * Math.PI / 180, φ2 = lat2 * Math.PI / 180;
    const y = Math.sin(dLng) * Math.cos(φ2);
    const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(dLng);
    return ((Math.atan2(y, x) * 180 / Math.PI) + 360) % 360;
}

// ==============================================
//  INIT MAP
// ==============================================
function initMap() {
    navigator.geolocation.getCurrentPosition(
        (pos) => setupMap({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        ()    => setupMap({ lat: 12.9716, lng: 77.5946 })
    );
}

function setupMap(center) {
    map = new google.maps.Map(document.getElementById('map'), {
        zoom: 18, center, mapTypeId: 'roadmap', tilt: 0
    });

    carPosition = { ...center };
    carMarker = new google.maps.Marker({
        position: carPosition,
        map,
        icon: buildCarIcon(0),
        optimized: false,
        zIndex: 1001
    });

    loadLocations();

    map.addListener('click', (e) => {
        if (!mode) {
            const clickedLat = e.latLng.lat();
            const clickedLng = e.latLng.lng();

            fetch(`https://roads.googleapis.com/v1/nearestRoads?points=${clickedLat},${clickedLng}&key=YOUR_GOOGLE_MAPS_API_KEY`)
                .then(r => r.json())
                .then(data => {
                    console.log('Roads API response:', JSON.stringify(data));
                    if (data.snappedPoints && data.snappedPoints.length > 0) {
                        const s = data.snappedPoints[0].location;
                        carPosition = { lat: s.latitude, lng: s.longitude };
                    } else {
                        carPosition = { lat: clickedLat, lng: clickedLng };
                    }
                    carMarker.setPosition(carPosition);
                    map.panTo(carPosition);
                })
                .catch(() => {
                    carPosition = { lat: clickedLat, lng: clickedLng };
                    carMarker.setPosition(carPosition);
                    map.panTo(carPosition);
                });
            return;
        }
        if (mode === 'delete') return;
        unlockVoice();
        addMarker(e.latLng, mode);
    });
}
// ==============================================
//  MODE BUTTONS
// ==============================================
function setMode(type) {
    mode = (mode === type) ? null : type;
    ['signal', 'hump', 'crossing','school', 'delete'].forEach(t => {
        const b = document.getElementById('btn-' + t);
        if (b) b.classList.toggle('active', t === mode);
    });
}

// ==============================================
//  MARKER ICONS
// ==============================================
function getIcon(type) {
    const icons = {
        signal:   'https://maps.google.com/mapfiles/kml/shapes/traffic.png',
        hump:     'https://maps.google.com/mapfiles/kml/shapes/caution.png',
        crossing: 'https://maps.google.com/mapfiles/kml/shapes/man.png',
        school:   'https://maps.google.com/mapfiles/kml/shapes/schools.png'
    };
    return { url: icons[type], scaledSize: new google.maps.Size(40, 40) };
}

function createMarker(loc) {
    const gm = new google.maps.Marker({
        position: { lat: loc.lat, lng: loc.lng },
        map,
        icon: getIcon(loc.type),
        zIndex: 1000
    });
    gm.addListener('click', () => {
        if (mode !== 'delete') return;
        gm.setMap(null);
        markers = markers.filter(m => m !== loc);
        saveLocations();
    });
    loc.gMarker = gm;
}

function addMarker(pos, type) {
    const loc = { lat: pos.lat(), lng: pos.lng(), type };
    createMarker(loc);
    markers.push(loc);
    saveLocations();
}

// ==============================================
//  PERSIST
// ==============================================
function saveLocations() {
    fetch('/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(markers.map(({ lat, lng, type }) => ({ lat, lng, type })))
    }).catch(() => {});
}

function loadLocations() {
    fetch('/get')
        .then(r => r.json())
        .then(data => {
            markers = [];
            data.forEach(loc => { createMarker(loc); markers.push(loc); });
        })
        .catch(() => {});
}

// ==============================================
//  DISTANCE (metres)
// ==============================================
function getDistance(lat1, lon1, lat2, lon2) {
    const R = 6371e3;
    const φ1 = lat1 * Math.PI / 180, φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180, Δλ = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}



function startMove(dir) {
    unlockVoice();
    activeKeys.add(dir);

    if (moveInterval) return; // already running, just added a key

    carMarker.setIcon(buildCarIcon(carBearing));
    moveInterval = setInterval(() => {

        // Turning — adjust bearing gradually while moving
        if (activeKeys.has('left'))  carBearing = (carBearing - 3 + 360) % 360;
        if (activeKeys.has('right')) carBearing = (carBearing + 3) % 360;

        carMarker.setIcon(buildCarIcon(carBearing));

        if (activeKeys.has('forward'))  doMove('forward');
        if (activeKeys.has('backward')) doMove('backward');

    }, 80);
}
function stopMove(dir) {
    activeKeys.delete(dir);
    if (activeKeys.size === 0) {
        clearInterval(moveInterval);
        moveInterval = null;
        currentDir = null;
    }
}



function doMove(dir) {
    const rad = carBearing * Math.PI / 180;

    let moveBearing = carBearing;
    if (dir === 'backward') moveBearing = (carBearing + 180) % 360;

    const moveRad = moveBearing * Math.PI / 180;

    // Move in the direction of current bearing
    const newLat = carPosition.lat + STEP * Math.cos(moveRad);
    const newLng = carPosition.lng + STEP * Math.sin(moveRad);

    carPosition = { lat: newLat, lng: newLng };
    carMarker.setPosition(carPosition);
    map.panTo(carPosition);
    checkAlerts();
}

// ==============================================
//  KEYBOARD
// ==============================================
const KEY_DIR = {
    ArrowUp: 'forward', ArrowDown: 'backward',
    ArrowLeft: 'left',  ArrowRight: 'right',
    w: 'forward', s: 'backward', a: 'left', d: 'right'
};
document.addEventListener('keydown', (e) => {
    if (e.repeat) return;
    const dir = KEY_DIR[e.key];
    if (dir) { e.preventDefault(); startMove(dir); }
});
document.addEventListener('keyup', (e) => {
    const dir = KEY_DIR[e.key];
    if (dir) stopMove(dir);
});

// ==============================================
//  ALERT CHECK (called every move tick)
// ==============================================
function checkAlerts() {
    markers.forEach((loc, i) => {
        const d = getDistance(carPosition.lat, carPosition.lng, loc.lat, loc.lng);
        const st = alertState[i] || (alertState[i] = {
            announcing: false,
            t1Done: false,
            humpDone: false,
            schoolDone: false,
            schoolActive: false,
            pedActive: false
        });

        if (d <= ALERT_RADIUS) {

    if (loc.type === 'hump' && !st.humpDone) {
        st.humpDone = true;
        speak('Speed breaker ahead. Please slow down.');
    }

    if (loc.type === 'crossing' && !st.pedActive) {
        st.pedActive = true;
        showPedStatus(true);
        speak('Pedestrian crossing ahead. Please stop.');
        setTimeout(() => {
            speakQueued('You may proceed now.');
            showPedStatus(false);
            st.pedActive = false;
        }, 10000);
    }

  if (loc.type === 'school' && !st.schoolDone && d<=80) {
    st.schoolDone  = true;
    st.schoolActive = true;
    showSchoolStatus(true);
    speak('School zone ahead. Children may be crossing. Please slow down.');
    setTimeout(() => {
        speakQueued('You may proceed now.');
        showSchoolStatus(false);
        st.schoolActive = false;
    }, 5000);
}

    if (loc.type === 'signal' && !st.tlDone) {
        startTrafficLight(i);
    }

} else {

    if (loc.type === 'hump' && st.humpDone) {
        st.humpDone = false;
        hideToast();
    }

    if (loc.type === 'crossing' && st.pedActive) {
        st.pedActive = false;
        showPedStatus(false);
    }

    if (loc.type === 'crossing' && !st.pedActive) {
        st.announcing = false;
    }

    if (loc.type === 'school' && st.schoolDone) {
    st.schoolDone   = false;
    st.schoolActive = false;
    showSchoolStatus(false);
}

    if (loc.type === 'signal' && st.tlDone) {
        showTrafficLight(false);
        st.tlDone = false;
    }
}
    });
}

// ==============================================
//  TRAFFIC LIGHT  RED → YELLOW (4s) → GREEN (8s)
// ==============================================
function startTrafficLight(idx) {
    const st = alertState[idx];
    st.tlDone = true;

    showTrafficLight(true);
    setLight('red');
    speak('Traffic signal. Red light — please stop.');

    setTimeout(() => {
        if (!alertState[idx]) return;
        setLight('yellow');
        speak('Signal turning yellow. Get ready.');
    }, 4000);

    setTimeout(() => {
        if (!alertState[idx]) return;
        setLight('green');
        speak('Signal green. You may go.');
    }, 8000);

    setTimeout(() => {
        showTrafficLight(false);
        if (alertState[idx]) alertState[idx].tlDone = false;
    }, 13000);
}

window.initMap = initMap;