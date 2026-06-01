        let map, roadsLayer, studyAreaLayer, pollutionLayer, concentrationLayer, heatmapLayer;
        let currentConcentrationData = null, currentMaxConc = 0;
        let windChart, tempChart;
        let tileLayer = null;
        let availableMonths = [];
        let uploadedDataStatus = { roads: false, weather: false, studyArea: false, pollution: false };
        let lastForecastData = null;
        let forecastChart = null;
        let windParticles = null;
        let isLiveWeatherMode = false;
        let liveWeatherSummary = null;

        class WindParticles {
            constructor(map) {
                this.map = map;
                this.canvas = document.createElement('canvas');
                this.canvas.style.position = 'absolute';
                this.canvas.style.top = 0;
                this.canvas.style.left = 0;
                this.canvas.style.pointerEvents = 'none';
                this.canvas.style.zIndex = 500;
                this.ctx = this.canvas.getContext('2d');
                this.particles = [];
                this.animationId = null;
                this.windSpeed = 0;
                this.windDir = 0;
                this.active = false;
                
                map.getPanes().overlayPane.appendChild(this.canvas);
                map.on('move', () => this.draw());
                map.on('moveend', () => this.draw());
                window.addEventListener('resize', () => this.resize());
                this.resize();
            }

            resize() {
                const size = this.map.getSize();
                this.canvas.width = size.x;
                this.canvas.height = size.y;
                this.draw();
            }

            setWind(speed, dir) {
                this.windSpeed = speed;
                this.windDir = dir;
                if (speed > 0 && !this.active) this.start();
                else if (speed <= 0 && this.active) this.stop();
            }

            start() {
                this.active = true;
                this.particles = Array.from({ length: 150 }, () => this.createParticle());
                this.animate();
            }

            stop() {
                this.active = false;
                cancelAnimationFrame(this.animationId);
                this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            }

            createParticle() {
                return {
                    x: Math.random() * this.canvas.width,
                    y: Math.random() * this.canvas.height,
                    life: Math.random() * 100,
                    speed: (0.5 + Math.random()) * this.windSpeed * 0.5
                };
            }

            animate() {
                if (!this.active) return;
                this.draw();
                this.animationId = requestAnimationFrame(() => this.animate());
            }

            draw() {
                this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                if (!this.active || this.windSpeed <= 0) return;

                const angle = (270 - this.windDir) * Math.PI / 180;
                const vx = Math.cos(angle);
                const vy = Math.sin(angle);

                this.ctx.strokeStyle = document.body.getAttribute('data-theme') === 'light' 
                    ? 'rgba(2, 132, 199, 0.2)' 
                    : 'rgba(0, 212, 255, 0.25)';
                this.ctx.lineWidth = 1;

                this.particles.forEach(p => {
                    p.x += vx * p.speed;
                    p.y += vy * p.speed;
                    p.life -= 0.5;

                    if (p.life <= 0 || p.x < 0 || p.x > this.canvas.width || p.y < 0 || p.y > this.canvas.height) {
                        const newP = this.createParticle();
                        Object.assign(p, newP);
                    }

                    this.ctx.beginPath();
                    this.ctx.moveTo(p.x, p.y);
                    this.ctx.lineTo(p.x - vx * 10, p.y - vy * 10);
                    this.ctx.stroke();
                });
            }
        }

        async function safeFetch(url, options = {}) {
            try {
                const res = await fetch(url, options);
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    throw new Error(errorData.error || `HTTP ${res.status}: ${res.statusText}`);
                }
                return await res.json();
            } catch (e) {
                if (e.name === 'TypeError' && e.message === 'Failed to fetch') {
                    throw new Error('Network error: Please check your connection');
                }
                throw e;
            }
        }

        function showToast(title, message, type = 'info', duration = 5000) {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            
            const icons = {
                success: 'fas fa-check-circle',
                error: 'fas fa-exclamation-circle',
                warning: 'fas fa-exclamation-triangle',
                info: 'fas fa-info-circle'
            };
            
            toast.innerHTML = `
                <i class="toast-icon ${icons[type] || icons.info}"></i>
                <div class="toast-content">
                    <div class="toast-title">${title}</div>
                    <div class="toast-message">${message}</div>
                </div>
                <button class="toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
                <div class="toast-progress" style="animation-duration: ${duration}ms"></div>
            `;
            
            container.appendChild(toast);
            
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.style.animation = 'slideInRight 0.25s ease reverse forwards';
                    setTimeout(() => toast.remove(), 250);
                }
            }, duration);
        }

        function setLoadingProgress(percent, text, subtext) {
            const progressBar = document.getElementById('loadingProgressBar');
            const loadingText = document.getElementById('loadingText');
            const loadingSubtext = document.getElementById('loadingSubtext');
            
            if (progressBar) progressBar.style.width = `${percent}%`;
            if (loadingText) loadingText.textContent = text || 'Processing...';
            if (loadingSubtext) loadingSubtext.textContent = subtext || 'Please wait...';
        }

        function setButtonLoading(button, loading) {
            if (loading) {
                button.classList.add('loading');
                button.disabled = true;
            } else {
                button.classList.remove('loading');
                button.disabled = false;
            }
        }
        
        function dismissWelcome() {
            var overlay = document.getElementById('welcomeOverlay');
            if (overlay) {
                overlay.style.display = 'none';
                localStorage.setItem('welcomeDismissed', 'true');
            }
        }

        function checkWelcome() {
            var overlay = document.getElementById('welcomeOverlay');
            if (!overlay) return;
            
            if (localStorage.getItem('welcomeDismissed') === 'true') {
                overlay.style.display = 'none';
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            checkWelcome();
        });
        
        async function checkDataStatus() {
            try {
                const res = await fetch('/api/data-status');
                const data = await res.json();
                
                const statusRoads = document.getElementById('statusRoads');
                const statusWeather = document.getElementById('statusWeather');
                const statusStudyArea = document.getElementById('statusStudyArea');
                const statusPollution = document.getElementById('statusPollution');
                
                const wasRoadsLoaded = uploadedDataStatus.roads;
                const wasStudyAreaLoaded = uploadedDataStatus.studyArea;
                
                if (data.roads.loaded) {
                    if (statusRoads) statusRoads.classList.add('loaded');
                    uploadedDataStatus.roads = true;
                    populateRoadCheckboxes(data.roads.count);
                    updateRoadCountFromBackend(data.roads.count);
                } else {
                    if (statusRoads) statusRoads.classList.remove('loaded');
                    uploadedDataStatus.roads = false;
                    populateRoadCheckboxes(0);
                    resetUploadedRoadsCount();
                }
                
                if (data.weather.loaded) {
                    if (statusWeather) statusWeather.classList.add('loaded');
                    uploadedDataStatus.weather = true;
                } else {
                    if (statusWeather) statusWeather.classList.remove('loaded');
                    uploadedDataStatus.weather = false;
                }
                
                if (data.study_area.loaded) {
                    if (statusStudyArea) statusStudyArea.classList.add('loaded');
                    uploadedDataStatus.studyArea = true;
                } else {
                    if (statusStudyArea) statusStudyArea.classList.remove('loaded');
                    uploadedDataStatus.studyArea = false;
                }
                
                if (data.pollution.loaded) {
                    if (statusPollution) statusPollution.classList.add('loaded');
                    uploadedDataStatus.pollution = true;
                } else {
                    if (statusPollution) statusPollution.classList.remove('loaded');
                    uploadedDataStatus.pollution = false;
                }
                
                if (!wasRoadsLoaded && data.roads.loaded || !wasStudyAreaLoaded && data.study_area.loaded) {
                    zoomToData();
                }
                
                updateEmptyStates();
            } catch (e) { console.error('Error checking data status:', e); updateEmptyStates(); }
        }

        // --- Helper Functions ---
        const setText = (id, text) => {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        };
        const setHTML = (id, html) => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = html;
        };
        const setStyle = (id, prop, val) => {
            const el = document.getElementById(id);
            if (el) el.style[prop] = val;
        };

        function showStatus(message, isError = false) {
            const el = document.getElementById('statusMessage');
            if (el) {
                el.textContent = message;
                el.className = isError ? 'alert alert-danger' : 'alert alert-info';
                el.style.display = 'block';
                if (!isError) {
                    setTimeout(() => { if (el) el.style.display = 'none'; }, 5000);
                }
            }
        }

        function showUploadStatus(elementId, message, type) {
            const el = document.getElementById(elementId);
            if (el) {
                el.textContent = message;
                el.className = 'upload-status ' + type;
                el.style.display = 'block';
                if (type === 'success') {
                    setTimeout(() => { el.style.display = 'none'; }, 5000);
                }
            }
        }

        function updateFileName(inputId, displayId, files) {
            const display = document.getElementById(displayId);
            if (display && files && files.length > 0) {
                display.textContent = files.length === 1 ? files[0].name : `${files.length} files selected`;
            } else if (display) {
                display.textContent = '';
            }
        }

        let uploadedRoadsCount = 0;
        let simHistory = [];
        let measurementMode = null;
        let measurePoints = [];
        let measureLine = null;
        let layerStateStack = [];
        let layerStateIndex = -1;

        function saveLayerState() {
            const state = {
                roads: document.getElementById('showRoads')?.checked || false,
                studyArea: document.getElementById('showStudyArea')?.checked || false,
                pollution: document.getElementById('showPollution')?.checked || false,
                concentrations: document.getElementById('showConcentrations')?.checked || false
            };
            layerStateStack = layerStateStack.slice(0, layerStateIndex + 1);
            layerStateStack.push(state);
            layerStateIndex++;
            if (layerStateStack.length > 20) {
                layerStateStack.shift();
                layerStateIndex--;
            }
        }

        function undoLayerState() {
            if (layerStateIndex > 0) {
                layerStateIndex--;
                applyLayerState(layerStateStack[layerStateIndex]);
                showToast('Undo', 'Layer state restored', 'info');
            }
        }

        function redoLayerState() {
            if (layerStateIndex < layerStateStack.length - 1) {
                layerStateIndex++;
                applyLayerState(layerStateStack[layerStateIndex]);
                showToast('Redo', 'Layer state restored', 'info');
            }
        }

        function applyLayerState(state) {
            const ids = ['showRoads', 'showStudyArea', 'showPollution', 'showConcentrations'];
            const keys = ['roads', 'studyArea', 'pollution', 'concentrations'];
            ids.forEach((id, i) => {
                const el = document.getElementById(id);
                if (el) el.checked = state[keys[i]];
            });
            toggleLayer('roads');
            toggleLayer('studyArea');
            toggleLayer('pollution');
            toggleLayer('concentrations');
        }

        function updateRangeValue(val) {
            const el = document.getElementById('rangeValue');
            if (el) el.textContent = Number(val).toLocaleString();
        }

        function saveFormState() {
            const state = {
                pollutant: document.getElementById('pollutantSelect')?.value,
                trafficCount: document.getElementById('trafficCount')?.value,
                bufferDistance: document.getElementById('bufferDistance')?.value,
                month: document.getElementById('monthSelect')?.value,
                day: document.getElementById('daySelect')?.value,
                hour: document.getElementById('hourSelect')?.value,
                vizStyle: document.getElementById('vizStyle')?.value,
                backgroundConcentration: document.getElementById('backgroundConcentration')?.value
            };
            localStorage.setItem('formState', JSON.stringify(state));
        }

        function loadFormState() {
            const saved = localStorage.getItem('formState');
            if (saved) {
                const state = JSON.parse(saved);
                const map = {
                    pollutantSelect: state.pollutant,
                    trafficCount: state.trafficCount,
                    bufferDistance: state.bufferDistance,
                    monthSelect: state.month,
                    daySelect: state.day,
                    hourSelect: state.hour,
                    vizStyle: state.vizStyle,
                    backgroundConcentration: state.backgroundConcentration
                };
                Object.keys(map).forEach(id => {
                    const el = document.getElementById(id);
                    if (el && map[id]) el.value = map[id];
                });
            }
        }

        function addToHistory(params, maxConc) {
            const entry = {
                time: new Date().toLocaleTimeString(),
                pollutant: params.pollutant,
                roads: params.road_ids?.join(',') || params.road_id,
                buffer: params.buffer_distance || 250,
                maxConc: maxConc.toFixed(4)
            };
            simHistory.unshift(entry);
            if (simHistory.length > 10) simHistory.pop();
            localStorage.setItem('simHistory', JSON.stringify(simHistory));
            updateHistoryDisplay();
        }

        function updateHistoryDisplay() {
            const container = document.getElementById('simHistory');
            if (!container) return;
            if (simHistory.length === 0) {
                container.innerHTML = '<p style="color:var(--text-secondary);font-size:0.75rem;">No recent simulations</p>';
                return;
            }
            let html = '';
            simHistory.forEach((h, i) => {
                html += `<div class="history-item" onclick="loadFromHistory(${i})"><div class="time">${h.time}</div><div class="details">${h.pollutant} • ${h.roads} • ${h.maxConc} µg/m³</div></div>`;
            });
            container.innerHTML = html;
        }

        function loadFromHistory(index) {
            const h = simHistory[index];
            const roads = h.roads.split(',').map(r => parseInt(r.trim()));
            roads.forEach(r => {
                const cb = document.getElementById('road' + r);
                if (cb) cb.checked = true;
            });
            const el = document.getElementById('pollutantSelect');
            if (el) el.value = h.pollutant;
            const el2 = document.getElementById('bufferDistance');
            if (el2) el2.value = h.buffer;
            showToast('Loaded', `Loaded settings from ${h.time}`, 'info');
        }

        function toggleFullscreen() {
            const container = document.getElementById('mapContainer');
            if (!container) return;
            container.classList.toggle('fullscreen');
            const icon = container.classList.contains('fullscreen') ? 'fas fa-compress' : 'fas fa-expand';
            const btn = document.querySelector('.fullscreen-btn i');
            if (btn) btn.className = icon;
            setTimeout(() => { if (typeof map !== 'undefined') map.invalidateSize(); }, 100);
        }

        function startMeasurement(type) {
            measurementMode = type;
            measurePoints = [];
            document.querySelectorAll('.measure-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            if (typeof map !== 'undefined') map.getContainer().style.cursor = 'crosshair';
            showToast('Measure', `Click on map to draw ${type}`, 'info');
        }

        function clearMeasurement() {
            measurementMode = null;
            measurePoints = [];
            if (measureLine && typeof map !== 'undefined') { map.removeLayer(measureLine); measureLine = null; }
            document.querySelectorAll('.measure-btn').forEach(b => b.classList.remove('active'));
            const res = document.getElementById('measureResult');
            if (res) res.style.display = 'none';
            if (typeof map !== 'undefined') map.getContainer().style.cursor = '';
        }

        function showMeasurementResult() {
            if (measureLine && typeof map !== 'undefined') map.removeLayer(measureLine);
            if (measurePoints.length < 2) return;

            if (measurementMode === 'distance') {
                let totalDist = 0;
                for (let i = 0; i < measurePoints.length - 1; i++) {
                    totalDist += measurePoints[i].distanceTo(measurePoints[i + 1]);
                }
                const line = L.polyline(measurePoints, { color: '#00d4ff', weight: 3, dashArray: '5,5' }).addTo(map);
                measureLine = line;
                const result = document.getElementById('measureResult');
                if (result) {
                    result.textContent = `Distance: ${totalDist.toFixed(0)} m`;
                    result.style.display = 'block';
                }
            } else if (measurementMode === 'area') {
                if (measurePoints.length < 3) return;
                const polygon = L.polygon(measurePoints, { color: '#00d4ff', weight: 2, fillOpacity: 0.2 }).addTo(map);
                measureLine = polygon;
                let area = 0;
                for (let i = 0; i < measurePoints.length; i++) {
                    const j = (i + 1) % measurePoints.length;
                    area += measurePoints[i].lng * measurePoints[j].lat;
                    area -= measurePoints[j].lng * measurePoints[i].lat;
                }
                area = Math.abs(area) / 2 * 111320 * Math.cos(measurePoints[0].lat * Math.PI / 180) * 111320;
                const result = document.getElementById('measureResult');
                if (result) {
                    result.textContent = `Area: ${(area / 10000).toFixed(2)} ha`;
                    result.style.display = 'block';
                }
            }
            measurementMode = null;
            document.querySelectorAll('.measure-btn').forEach(b => b.classList.remove('active'));
            if (typeof map !== 'undefined') map.getContainer().style.cursor = '';
        }

        function filterRoads(query) {
            const checkboxes = document.querySelectorAll('#roadCheckboxes .checkbox-item');
            query = query.toLowerCase();
            checkboxes.forEach(item => {
                const text = item.querySelector('span').textContent.toLowerCase();
                item.style.display = text.includes(query) ? '' : 'none';
            });
        }

        async function handleRoadUpload(input) {
            const files = input.files;
            if (!files || files.length === 0) return;
            
            updateFileName('roadFiles', 'roadFileName', files);
            const roadId = uploadedRoadsCount + 1;
            const crs = document.getElementById('uploadCrs')?.value || 'EPSG:4326';
            
            showUploadStatus('roadUploadStatus', 'Uploading...', 'info');
            
            const formData = new FormData();
            formData.append('road_id', roadId);
            formData.append('crs', crs);
            for (let i = 0; i < files.length; i++) {
                formData.append('files[]', files[i]);
            }
            
            try {
                const res = await fetch('/api/upload-roads', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({ error: 'Upload failed. Please try again.' }));
                    showUploadStatus('roadUploadStatus', 'Error: ' + errorData.error, 'error');
                    return;
                }
                
                const result = await res.json();
                
                if (result.success) {
                    uploadedRoadsCount++;
                    showUploadStatus('roadUploadStatus', `✓ Road ${roadId} uploaded: ${result.features} features`, 'success');
                    updateUploadedRoadsList();
                    await checkDataStatus();
                    loadRoads();
                    setText('roadFileName', '');
                } else {
                    showUploadStatus('roadUploadStatus', 'Error: ' + result.error, 'error');
                }
            } catch (e) {
                showUploadStatus('roadUploadStatus', 'Error: Network error. Please check your connection and try again.', 'error');
            }
        }

        function updateUploadedRoadsList() {
            const container = document.getElementById('uploadedRoadsList');
            if (!container) return;
            if (uploadedRoadsCount === 0) {
                container.innerHTML = '<p style="color:var(--text-secondary);font-size:0.8rem;">No roads uploaded yet.</p>';
            } else {
                let html = '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
                for (let i = 1; i <= uploadedRoadsCount; i++) {
                    html += `<span style="background:var(--primary);color:#000;padding:4px 12px;border-radius:12px;font-size:0.8rem;font-weight:600;">Road ${i}</span>`;
                }
                html += '</div>';
                container.innerHTML = html;
            }
        }
        
        function resetUploadedRoadsCount() {
            uploadedRoadsCount = 0;
            updateUploadedRoadsList();
        }
        
        function updateRoadCountFromBackend(count) {
            uploadedRoadsCount = count;
            updateUploadedRoadsList();
        }

        async function handleWeatherUpload(input) {
            const file = input.files[0];
            if (!file) return;
            
            setText('weatherFileName', file.name);
            showUploadStatus('weatherUploadStatus', 'Uploading...', 'info');
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const res = await fetch('/api/upload-weather', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({ error: 'Upload failed. Please try again.' }));
                    showUploadStatus('weatherUploadStatus', 'Error: ' + errorData.error, 'error');
                    return;
                }
                
                const result = await res.json();
                
                if (result.success) {
                    showUploadStatus('weatherUploadStatus', `✓ Weather data: ${result.records} records loaded`, 'success');
                    checkDataStatus();
                    checkForecastStatus();
                    loadWeatherData();
                } else {
                    showUploadStatus('weatherUploadStatus', 'Error: ' + result.error, 'error');
                }
            } catch (e) {
                showUploadStatus('weatherUploadStatus', 'Error: Network error. Please check your connection and try again.', 'error');
            }
        }

        async function handleStudyAreaUpload(input) {
            const files = input.files;
            if (!files || files.length === 0) return;
            
            updateFileName('studyAreaFiles', 'studyAreaFileName', files);
            const crs = document.getElementById('uploadCrs')?.value || 'EPSG:4326';
            
            showUploadStatus('studyAreaUploadStatus', 'Uploading...', 'info');
            
            const formData = new FormData();
            formData.append('crs', crs);
            for (let i = 0; i < files.length; i++) {
                formData.append('files[]', files[i]);
            }
            
            try {
                const res = await fetch('/api/upload-study-area', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({ error: 'Upload failed. Please try again.' }));
                    showUploadStatus('studyAreaUploadStatus', 'Error: ' + errorData.error, 'error');
                    return;
                }
                
                const result = await res.json();
                
                if (result.success) {
                    showUploadStatus('studyAreaUploadStatus', `✓ Study area: ${result.features} features loaded`, 'success');
                    checkDataStatus();
                    loadStudyArea();
                    if (result.center && typeof map !== 'undefined') {
                        map.setView([result.center[1], result.center[0]], 13);
                    }
                } else {
                    showUploadStatus('studyAreaUploadStatus', 'Error: ' + result.error, 'error');
                }
            } catch (e) {
                showUploadStatus('studyAreaUploadStatus', 'Error: Network error. Please check your connection and try again.', 'error');
            }
        }

        async function handlePollutionUpload(input) {
            const file = input.files[0];
            if (!file) return;
            
            setText('pollutionFileName', file.name);
            showUploadStatus('pollutionUploadStatus', 'Uploading...', 'info');
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('crs', document.getElementById('uploadCrs')?.value || 'EPSG:4326');
            
            try {
                const res = await fetch('/api/upload-pollution', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({ error: 'Upload failed. Please try again.' }));
                    showUploadStatus('pollutionUploadStatus', 'Error: ' + errorData.error, 'error');
                    return;
                }
                
                const result = await res.json();
                
                if (result.success) {
                    showUploadStatus('pollutionUploadStatus', `✓ Pollution data: ${result.records} records loaded`, 'success');
                    checkDataStatus();
                    if (document.getElementById('showPollution')?.checked) {
                        loadPollutionData();
                    }
                } else {
                    showUploadStatus('pollutionUploadStatus', 'Error: ' + result.error, 'error');
                }
            } catch (e) {
                showUploadStatus('pollutionUploadStatus', 'Error: ' + e.message, 'error');
            }
        }

        async function handleEmissionUpload(input) {
            const file = input.files[0];
            if (!file) return;
            
            setText('emissionFileName', file.name);
            showUploadStatus('emissionUploadStatus', 'Uploading...', 'info');
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const res = await fetch('/api/upload-emission-factors', {
                    method: 'POST',
                    body: formData
                });
                const result = await res.json();
                
                if (result.success) {
                    showUploadStatus('emissionUploadStatus', `✓ Emission factors loaded: ${result.pollutants.join(', ')}`, 'success');
                } else {
                    showUploadStatus('emissionUploadStatus', 'Error: ' + result.error, 'error');
                }
            } catch (e) {
                showUploadStatus('emissionUploadStatus', 'Error: ' + e.message, 'error');
            }
        }

        async function resetToDefaults() {
            if (!confirm('Clear all uploaded data? You will need to upload files again.')) return;
            
            const loading = document.getElementById('loading');
            if (loading) loading.classList.add('active');
            const loadingText = document.querySelector('.loading-text');
            if (loadingText) loadingText.textContent = 'Resetting data...';
            
            try {
                const res = await fetch('/api/reset-data', { method: 'POST' });
                const result = await res.json();
                
                if (result.success) {
                    uploadedRoadsCount = 0;
                    updateUploadedRoadsList();
                    showUploadStatus('roadUploadStatus', 'Data cleared', 'success');
                    showUploadStatus('weatherUploadStatus', 'Data cleared', 'success');
                    showUploadStatus('studyAreaUploadStatus', 'Data cleared', 'success');
                    showUploadStatus('pollutionUploadStatus', 'Data cleared', 'success');
                    
                    ['roadFileName', 'weatherFileName', 'studyAreaFileName', 'pollutionFileName', 'emissionFileName'].forEach(id => setText(id, ''));
                    
                    setStyle('exportAIBtn', 'display', 'none');
                    setStyle('simResults', 'display', 'none');
                    
                    resetWeatherDashboard();
                    
                    if (typeof map !== 'undefined') map.setView([20, 0], 2);
                    
                    checkDataStatus();
                    loadRoads();
                    loadStudyArea();
                    loadWeatherData();
                }
            } catch (e) {
                showToast('Error', 'Failed to reset data', 'error');
            }
            
            if (loading) loading.classList.remove('active');
        }
        
        function resetWeatherDashboard() {
            setText('avgTemp', '--');
            setText('avgWind', '--');
            setText('maxWind', '--');
            setText('windDir', '--');
            if (typeof windChart !== 'undefined' && windChart) { windChart.destroy(); windChart = null; }
            if (typeof tempChart !== 'undefined' && tempChart) { tempChart.destroy(); tempChart = null; }
            
            const monthSelect = document.getElementById('monthSelect');
            if (monthSelect) {
                const names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                for (let i = 1; i <= 12; i++) {
                    const opt = monthSelect.querySelector(`option[value="${i}"]`);
                    if (opt) opt.textContent = names[i];
                }
            }
        }

        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                btn.classList.add('active');
                const panel = document.getElementById('tab-' + btn.dataset.tab);
                if (panel) panel.classList.add('active');
                
                if (btn.dataset.tab === 'forecast') {
                    checkForecastStatus();
                }
            });
        });

        function getCardinal(angle) {
            const dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
            return dirs[Math.round(angle / 22.5) % 16];
        }

        function formatWindDir(deg) { return `${deg.toFixed(0)}° ${getCardinal(deg)}`; }

        function updateControlsState() {
            const monthSelect = document.getElementById('monthSelect');
            const selectedMonth = monthSelect ? monthSelect.value : '';
            const hasData = (selectedMonth === '' || availableMonths.includes(parseInt(selectedMonth))) && 
                            uploadedDataStatus.roads && 
                            uploadedDataStatus.weather;
            
            const runSimBtn = document.querySelector('#tab-simulation .btn-primary');
            const simResultsCheckbox = document.getElementById('showConcentrations');
            const exportButtons = document.querySelectorAll('#tab-export .btn-secondary');
            
            if(runSimBtn) {
                runSimBtn.disabled = !hasData;
                runSimBtn.style.opacity = hasData ? '1' : '0.5';
                runSimBtn.style.cursor = hasData ? 'pointer' : 'not-allowed';
                runSimBtn.title = hasData ? '' : 'Please upload Roads and Weather data first';
            }
            
            if(simResultsCheckbox) {
                simResultsCheckbox.disabled = !hasData;
                if (simResultsCheckbox.parentElement) {
                    simResultsCheckbox.parentElement.style.opacity = hasData ? '1' : '0.5';
                    simResultsCheckbox.parentElement.style.cursor = hasData ? 'pointer' : 'not-allowed';
                }
            }
            
            exportButtons.forEach(btn => {
                btn.disabled = !hasData;
                btn.style.opacity = hasData ? '1' : '0.5';
                btn.style.cursor = hasData ? 'pointer' : 'not-allowed';
            });
            
            if (!hasData && simResultsCheckbox) {
                simResultsCheckbox.checked = false;
            }
            
            const runForecastBtn = document.querySelector('#tab-forecast .btn-primary');
            if (runForecastBtn) {
                const hasForecastData = uploadedDataStatus.weather && uploadedDataStatus.pollution;
                runForecastBtn.disabled = !hasForecastData;
                runForecastBtn.style.opacity = hasForecastData ? '1' : '0.5';
                runForecastBtn.style.cursor = hasForecastData ? 'pointer' : 'not-allowed';
                runForecastBtn.title = hasForecastData ? '' : 'Please upload target Pollution CSV and Weather data first';
            }
        }

        function toggleTheme() {
            const body = document.body;
            const icon = document.getElementById('themeIcon');
            const isLight = body.getAttribute('data-theme') === 'light';
            
            if (isLight) {
                body.removeAttribute('data-theme');
                if (icon) icon.className = 'fas fa-moon';
                localStorage.setItem('theme', 'dark');
                switchTileLayer('dark');
            } else {
                body.setAttribute('data-theme', 'light');
                if (icon) icon.className = 'fas fa-sun';
                localStorage.setItem('theme', 'light');
                switchTileLayer('light');
            }
            loadRoads();
            loadStudyArea();
        }

        function switchTileLayer(theme) {
            if (typeof map !== 'undefined' && tileLayer) map.removeLayer(tileLayer);
            const url = theme === 'light' 
                ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
                : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
            if (typeof map !== 'undefined') tileLayer = L.tileLayer(url, { attribution: '© CARTO', maxZoom: 19 }).addTo(map);
        }

        function initMap() {
            if (window.mapInitialized) return;
            window.mapInitialized = true;
            
            const saved = localStorage.getItem('theme');
            const isLight = saved === 'light';
            
            if (typeof L === 'undefined') {
                console.error('Leaflet not loaded!');
                return;
            }
            
            try {
                map = L.map('map').setView([20, 0], 2);
                tileLayer = L.tileLayer(isLight 
                    ? 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'
                    : 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
                , { attribution: '© CARTO', maxZoom: 19 }).addTo(map);
            } catch(e) {
                console.log('Map tiles failed to load, using offline mode');
                try {
                    map = L.map('map').setView([20, 0], 2);
                } catch(e2) {
                    console.error('Map initialization failed:', e2);
                    return;
                }
            }

            if (isLight) {
                document.body.setAttribute('data-theme', 'light');
                const icon = document.getElementById('themeIcon');
                if (icon) icon.className = 'fas fa-sun';
            }

            roadsLayer = L.layerGroup().addTo(map);
            studyAreaLayer = L.layerGroup().addTo(map);
            concentrationLayer = L.layerGroup().addTo(map);
            heatmapLayer = L.layerGroup().addTo(map);
            pollutionLayer = L.layerGroup();
            
            windParticles = new WindParticles(map);

            map.on('mousemove', (e) => {
                const el = document.getElementById('coordDisplay');
                if (el) el.textContent = `Lat: ${e.latlng.lat.toFixed(4)}, Lon: ${e.latlng.lng.toFixed(4)}`;
            });

            map.on('click', (e) => {
                if (!measurementMode) return;
                measurePoints.push(e.latlng);
                if (measurementMode === 'distance' && measurePoints.length >= 2) {
                    showMeasurementResult();
                } else if (measurementMode === 'area' && measurePoints.length >= 3) {
                    showMeasurementResult();
                }
            });

            loadFormState();
            localStorage.removeItem('simHistory');
            localStorage.removeItem('formState');
            localStorage.removeItem('welcomeDismissed');
            simHistory = [];
            updateHistoryDisplay();
            
            const defaults = { pollutantSelect: 'NOx', trafficCount: '50000', bufferDistance: '250', monthSelect: '', daySelect: '', hourSelect: '', vizStyle: 'points' };
            Object.keys(defaults).forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = defaults[id];
            });

            checkWelcome();
            updateUploadedRoadsList();
            checkDataStatus();
            loadWeatherData();
            updateEmptyStates();
        }

        function updateEmptyStates() {
            const simPanel = document.getElementById('tab-simulation');
            if (!simPanel) return;
            
            let emptyMsg = simPanel.querySelector('.empty-state');
            
            if (!uploadedDataStatus.roads || !uploadedDataStatus.weather) {
                if (!emptyMsg) {
                    emptyMsg = document.createElement('div');
                    emptyMsg.className = 'empty-state';
                    emptyMsg.innerHTML = '<i class="fas fa-folder-open"></i><h3>No Data Loaded</h3><p>Please upload roads and weather data in the Upload tab first.</p>';
                    simPanel.insertBefore(emptyMsg, simPanel.firstChild);
                }
                const btn = document.querySelector('#tab-simulation .btn-primary');
                if (btn) {
                    btn.disabled = true;
                    btn.style.opacity = '0.5';
                }
            } else {
                if (emptyMsg) emptyMsg.remove();
                const btn = document.querySelector('#tab-simulation .btn-primary');
                if (btn) {
                    btn.disabled = false;
                    btn.style.opacity = '1';
                }
            }
            
            const roadCheckboxes = document.getElementById('roadCheckboxes');
            if (!uploadedDataStatus.roads) {
                if (roadCheckboxes) roadCheckboxes.innerHTML = `
                    <div class="empty-state" style="padding:20px;">
                        <i class="fas fa-road" style="font-size:24px;"></i>
                        <p style="margin-top:8px;">No roads uploaded yet.<br>Go to Upload tab to add road files.</p>
                    </div>
                `;
            } else {
                fetch('/api/data-status')
                    .then(res => res.json())
                    .then(data => {
                        if (data.roads && data.roads.count > 0) {
                            populateRoadCheckboxes(data.roads.count);
                        }
                    });
            }
        }
        
        function populateRoadCheckboxes(roadCount) {
            const container = document.getElementById('roadCheckboxes');
            if (!container) return;
            if (roadCount === 0) {
                container.innerHTML = `
                    <div class="empty-state" style="padding:20px;">
                        <i class="fas fa-road" style="font-size:24px;"></i>
                        <p style="margin-top:8px;">No roads uploaded yet.<br>Go to Upload tab to add road files.</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            for (let i = 1; i <= roadCount; i++) {
                const checked = i === 1 ? 'checked' : '';
                html += `
                    <label class="checkbox-item">
                        <input type="checkbox" id="road${i}" value="${i}" ${checked}>
                        <span>Road ${i}</span>
                    </label>
                `;
            }
            container.innerHTML = html;
        }

        async function zoomToData() {
            try {
                const res = await fetch('/api/study-area');
                const data = await res.json();
                
                if (data.geometry && data.geometry.coordinates) {
                    let bounds = null;
                    
                    if (data.geometry.type === 'Polygon') {
                        const coords = data.geometry.coordinates[0];
                        const lats = coords.map(c => c[1]);
                        const lons = coords.map(c => c[0]);
                        bounds = [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
                    }
                    
                    if (bounds && typeof map !== 'undefined') {
                        map.fitBounds(bounds, { padding: [50, 50] });
                        return;
                    }
                }
                
                const roadsRes = await fetch('/api/roads');
                const roads = await roadsRes.json();
                
                if (Array.isArray(roads) && roads.length > 0) {
                    const allCoords = [];
                    roads.forEach(road => {
                        if (road.geometry && road.geometry.coordinates) {
                            allCoords.push(...road.geometry.coordinates);
                        }
                    });
                    
                    if (allCoords.length > 0 && typeof map !== 'undefined') {
                        const lats = allCoords.map(c => c[1]);
                        const lons = allCoords.map(c => c[0]);
                        const bounds = [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
                        map.fitBounds(bounds, { padding: [50, 50] });
                        return;
                    }
                }
                
                if (typeof map !== 'undefined') map.setView([35.43, 44.38], 12);
            } catch (e) {
                console.error('Error zooming to data:', e);
                if (typeof map !== 'undefined') map.setView([35.43, 44.38], 12);
            }
        }

        function getThemeColors() {
            const isLight = document.body.getAttribute('data-theme') === 'light';
            return {
                primary: isLight ? '#0284c7' : '#00d4ff',
                secondary: isLight ? '#ea580c' : '#ff6b35',
                roadColor: isLight ? '#0284c7' : '#00d4ff'
            };
        }

        async function loadRoads() {
            try {
                const res = await fetch('/api/roads');
                const roads = await res.json();
                roadsLayer.clearLayers();
                const colors = getThemeColors();
                
                roads.forEach(road => {
                    L.geoJSON(road, { style: { color: colors.roadColor, weight: 5, opacity: 1 } }).addTo(roadsLayer);
                    if (road.center) {
                        L.marker([road.center[1], road.center[0]], {
                            icon: L.divIcon({
                                html: `<div style="background:${colors.primary};padding:3px 8px;border-radius:4px;font-size:11px;color:#000;font-weight:700;border:2px solid #fff;">${road.properties.name}</div>`,
                                iconSize: [80, 22]
                            })
                        }).addTo(roadsLayer);
                    }
                });
            } catch (e) { console.error('Error:', e); }
        }

        async function loadStudyArea() {
            try {
                const res = await fetch('/api/study-area');
                const data = await res.json();
                const colors = getThemeColors();
                studyAreaLayer.clearLayers();
                if (data.type === 'Feature') {
                    L.geoJSON(data, {
                        style: { fillColor: colors.secondary, fillOpacity: 0.05, color: colors.secondary, weight: 1, dashArray: '4,4' }
                    }).addTo(studyAreaLayer);
                }
            } catch (e) { console.error('Error:', e); }
        }

        async function loadWeatherData(day = null, month = null, hour = null) {
            try {
                let url = '/api/weather';
                const params = [];
                if (hour) params.push(`hour=${hour}`);
                if (day) params.push(`day=${day}`);
                if (month) params.push(`month=${month}`);
                if (params.length) url += '?' + params.join('&');
                
                const res = await fetch(url);
                const data = await res.json();
                
                if (data.summary) {
                    setText('avgTemp', data.summary.avg_temp.toFixed(1));
                    setText('avgWind', data.summary.avg_wind_speed.toFixed(1));
                    setText('maxWind', data.summary.max_wind_speed.toFixed(1));
                    setText('windDir', formatWindDir(data.summary.avg_wind_direction));
                    
                    if (windParticles) {
                        windParticles.setWind(data.summary.avg_wind_speed, data.summary.avg_wind_direction);
                    }
                }
                
                if (data.hourly) createWindChart(data.hourly);
                if (data.daily) createTempChart(data.daily, data.is_daily_view);
                
                if (data.available_months) {
                    const monthSelect = document.getElementById('monthSelect');
                    if (monthSelect) {
                        const names = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
                        availableMonths = data.available_months;
                        for (let i = 1; i <= 12; i++) {
                            const opt = monthSelect.querySelector(`option[value="${i}"]`);
                            if (opt) {
                                const hasData = data.available_months.includes(i);
                                opt.textContent = names[i] + (hasData ? ' ✓' : '');
                                opt.disabled = !hasData;
                            }
                        }
                    }
                    updateControlsState();
                }

                // Dynamically update the day dropdown based on available days for the selected month
                if (data.available_days) {
                    const daySelect = document.getElementById('daySelect');
                    if (daySelect) {
                        const currentDay = daySelect.value;
                        daySelect.innerHTML = '<option value="">All Days</option>';
                        data.available_days.forEach(d => {
                            const opt = document.createElement('option');
                            opt.value = d;
                            opt.textContent = d;
                            if (String(d) === currentDay) opt.selected = true;
                            daySelect.appendChild(opt);
                        });
                    }
                }
            } catch (e) { console.error('Error:', e); }
        }

        function toggleLiveWeather(checkbox) {
            isLiveWeatherMode = checkbox.checked;
            const historicalControls = document.getElementById('historicalWeatherControls');
            const liveControls = document.getElementById('liveWeatherControls');
            
            if (historicalControls) historicalControls.style.display = isLiveWeatherMode ? 'none' : 'block';
            if (liveControls) liveControls.style.display = isLiveWeatherMode ? 'block' : 'none';
            
            if (isLiveWeatherMode) {
                syncLiveWeather();
            } else {
                const pollutionDash = document.getElementById('livePollutionDashboard');
                const aqiBadge = document.getElementById('aqiBadge');
                if (pollutionDash) pollutionDash.style.display = 'none';
                if (aqiBadge) aqiBadge.style.display = 'none';
                
                setText('dashboardCity', '');
                
                loadWeatherData(document.getElementById('daySelect')?.value || null, document.getElementById('monthSelect')?.value || null, document.getElementById('hourSelect')?.value || null);
            }
        }

        async function syncLiveWeather() {
            const infoBox = document.getElementById('liveWeatherInfo');
            if (infoBox) infoBox.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Syncing...';
            
            try {
                const res = await fetch('/api/weather/live');
                if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
                const data = await res.json();
                
                if (data.success) {
                    liveWeatherSummary = data.summary;
                    if (infoBox) {
                        infoBox.innerHTML = `
                            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:5px; margin-top:5px;">
                                <div><i class="fas fa-thermometer-half"></i> ${data.summary.avg_temp.toFixed(1)}°C</div>
                                <div><i class="fas fa-wind"></i> ${data.summary.avg_wind_speed.toFixed(1)} m/s</div>
                                <div><i class="fas fa-compass"></i> ${data.summary.avg_wind_direction}°</div>
                                <div><i class="fas fa-cloud"></i> ${data.summary.description}</div>
                            </div>
                            <div style="font-size:0.7rem; color:var(--text-secondary); margin-top:5px; text-align:right;">
                                Location: ${data.summary.city}
                            </div>
                        `;
                    }
                    
                    setText('avgTemp', data.summary.avg_temp.toFixed(1));
                    setText('avgWind', data.summary.avg_wind_speed.toFixed(1));
                    setText('windDir', formatWindDir(data.summary.avg_wind_direction));
                    setText('dashboardCity', data.summary.city);
                    
                    const weatherTime = document.getElementById('liveWeatherTime');
                    if (weatherTime) weatherTime.textContent = new Date().toLocaleTimeString();
                    
                    if (windParticles) {
                        windParticles.setWind(data.summary.avg_wind_speed, data.summary.avg_wind_direction);
                    }
                    
                    syncLivePollution();
                    
                    showToast('Live Update', `Weather synced for ${data.summary.city}`, 'success');
                } else {
                    throw new Error(data.error || 'Failed to sync weather');
                }
            } catch (e) {
                console.error('Live sync error:', e);
                showToast('Error', 'Failed to sync live weather', 'error');
            }
        }



        function createWindChart(data) {
            const ctx = document.getElementById('windChart').getContext('2d');
            if (windChart) windChart.destroy();
            windChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => `${d.HOUR}h`),
                    datasets: [{ data: data.map(d => d.WS), borderColor: '#00d4ff', backgroundColor: 'rgba(0,212,255,0.1)', fill: true, tension: 0.4, pointRadius: 2, label: 'Wind Speed (m/s)' }]
                },
                options: { 
                    responsive: true, 
                    plugins: { 
                        legend: { display: false },
                        tooltip: { 
                            backgroundColor: 'rgba(17,24,39,0.95)',
                            titleColor: '#f0f4f8',
                            bodyColor: '#94a3b8',
                            borderColor: '#2d3748',
                            borderWidth: 1,
                            cornerRadius: 8,
                            padding: 10
                        }
                    }, 
                    scales: { 
                        x: { ticks: { color: '#94a3b8', maxTicksLimit: 6 }, grid: { color: '#2d3748' } }, 
                        y: { ticks: { color: '#94a3b8' }, grid: { color: '#2d3748' } } 
                    } 
                }
            });
        }

        function createTempChart(data, isDailyView = true) {
            const ctx = document.getElementById('tempChart').getContext('2d');
            if (tempChart) tempChart.destroy();
            tempChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => isDailyView ? `D${d.DAY}` : `${d.DAY}h`),
                    datasets: [{ data: data.map(d => d.TEMP_C), borderColor: '#ff6b35', backgroundColor: 'rgba(255,107,53,0.1)', fill: true, tension: 0.4, pointRadius: 2, label: isDailyView ? 'Daily Avg Temp (°C)' : 'Hourly Temp (°C)' }]
                },
                options: { 
                    responsive: true, 
                    plugins: { 
                        legend: { display: false },
                        tooltip: { 
                            backgroundColor: 'rgba(17,24,39,0.95)',
                            titleColor: '#f0f4f8',
                            bodyColor: '#94a3b8',
                            borderColor: '#2d3748',
                            borderWidth: 1,
                            cornerRadius: 8,
                            padding: 10
                        }
                    }, 
                    scales: { 
                        x: { ticks: { color: '#94a3b8', maxTicksLimit: 7 }, grid: { color: '#2d3748' } }, 
                        y: { ticks: { color: '#94a3b8' }, grid: { color: '#2d3748' } } 
                    } 
                }
            });
        }

        async function runSimulation() {
            const selectedRoads = Array.from(document.querySelectorAll('#tab-simulation .checkbox-group input[type="checkbox"]:checked')).map(cb => parseInt(cb.value));
            
            if (selectedRoads.length === 0) {
                showToast('Warning', 'Please select at least one road', 'warning');
                return;
            }
            
            const trafficCount = document.getElementById('trafficCount').value;
            const bufferDistance = document.getElementById('bufferDistance').value;
            const bgConcField = document.getElementById('backgroundConcentration');
            const bgConc = bgConcField ? bgConcField.value : 0.0;
            
            if (!trafficCount || trafficCount.trim() === '' || isNaN(parseInt(trafficCount))) {
                showToast('Warning', 'Traffic count must be a valid number', 'warning');
                const tcField = document.getElementById('trafficCount');
                tcField.style.borderColor = 'var(--error)';
                setTimeout(() => tcField.style.borderColor = '', 3000);
                return;
            }
            
            if (!bufferDistance || bufferDistance.trim() === '' || isNaN(parseInt(bufferDistance))) {
                showToast('Warning', 'Buffer distance must be a valid number', 'warning');
                const bdField = document.getElementById('bufferDistance');
                bdField.style.borderColor = 'var(--error)';
                setTimeout(() => bdField.style.borderColor = '', 3000);
                return;
            }
            
            if (!uploadedDataStatus.roads || !uploadedDataStatus.weather) {
                showToast('Error', 'Missing pre-requisite data. Please load Roads and Weather on the Data tab first.', 'error');
                return;
            }
            
            const pollutant = document.getElementById('pollutantSelect').value;
            const month = document.getElementById('monthSelect').value;
            const day = document.getElementById('daySelect').value;
            const hour = document.getElementById('hourSelect').value;
            
            document.getElementById('loading').classList.add('active');
            setLoadingProgress(20, 'Running simulation...', 'Initializing model');
            
            try {
                setLoadingProgress(50, 'Running simulation...', 'Calculating dispersion');
                
                const payload = { 
                    road_ids: selectedRoads, 
                    pollutant, 
                    traffic_count: parseInt(trafficCount), 
                    buffer_distance: parseInt(bufferDistance),
                    background_concentration: parseFloat(bgConc) || 0.0
                };

                if (isLiveWeatherMode && liveWeatherSummary) {
                    // Inject live weather data if in live mode
                    // We can either update the API or just send the values
                    // Let's assume the API might not handle external weather injection yet, 
                    // or we use a special flag for the backend to use the latest live data.
                    // For now, let's keep it simple and use the selected historical date/hour 
                    // UNLESS we update the backend to handle a 'live' flag.
                    payload.live = true;
                } else {
                    payload.day = day ? parseInt(day) : null;
                    payload.month = month ? parseInt(month) : null;
                    payload.hour = hour ? parseInt(hour) : null;
                }

                const result = await safeFetch('/api/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                setLoadingProgress(80, 'Running simulation...', 'Processing results');
                if (result.error) {
                    showToast('Error', result.error, 'error');
                } else if (result.concentrations && result.concentrations.features && result.concentrations.features.length > 0) {
                    const maxConc = result.max_concentration !== undefined ? result.max_concentration : 0;
                    displayConcentrations(result.concentrations, result.parameters, maxConc);
                    showToast('Success', `Simulation complete! Max concentration: ${typeof maxConc === 'number' ? maxConc.toFixed(4) : 'N/A'} µg/m³`, 'success');
                } else {
                    showToast('Warning', 'No results returned from simulation', 'warning');
                }
            } catch (e) { 
                showToast('Error', e.message || 'Failed to run simulation', 'error'); 
            } finally {
                setLoadingProgress(100, 'Complete', 'Done');
                setTimeout(() => {
                    document.getElementById('loading').classList.remove('active');
                    setLoadingProgress(0, 'Processing...', 'Please wait...');
                }, 500);
            }
        }

        async function newSimulation() {
            if (!confirm('Start a new simulation? This will clear current results.')) return;
            
            setLoadingProgress(30, 'Resetting...', 'Clearing results');
            
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({ error: 'Reset failed. Please try again.' }));
                    showToast('Error', errorData.error, 'error');
                    return;
                }
                
                const result = await res.json();
                
                if (!result.success) {
                    showToast('Error', result.error || 'Failed to reset simulation', 'error');
                    return;
                }
                
                showToast('Success', 'Simulation reset successfully', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
                
            } catch (e) { 
                console.error('Reset error:', e); 
                showToast('Error', 'Failed to reset simulation', 'error');
                document.getElementById('loading').classList.remove('active');
            }
        }

        function displayConcentrations(geojson, params, maxConc) {
            currentConcentrationData = geojson;
            currentMaxConc = maxConc;
            
            const concentrations = geojson.features.map(f => f.properties.concentration);
            const minConc = Math.min(...concentrations);
            const avgConc = concentrations.reduce((a, b) => a + b, 0) / concentrations.length;
            
            const vizStyle = document.getElementById('vizStyle').value;
            if (vizStyle === 'heatmap') displayHeatmap(geojson, maxConc);
            else displayGridPoints(geojson, maxConc);
            
            document.getElementById('concentrationLegend').style.display = 'block';
            document.getElementById('showConcentrations').checked = true;
            document.getElementById('simResults').style.display = 'block';
            document.getElementById('exportAIBtn').style.display = 'inline-block';
            const roadLabel = Array.isArray(params.road_ids) ? params.road_ids.join(', ') : params.road_id;
            document.getElementById('resultsInfo').innerHTML = `
                <div class="result-row"><span class="label">Roads</span><span class="value">${roadLabel}</span></div>
                <div class="result-row"><span class="label">Pollutant</span><span class="value">${params.pollutant}</span></div>
                <div class="result-row"><span class="label">Buffer</span><span class="value">${params.buffer_distance || 250} m</span></div>
                <div class="result-row"><span class="label">Points</span><span class="value">${concentrations.length}</span></div>
                <div class="result-row"><span class="label">Min</span><span class="value">${minConc.toFixed(4)} µg/m³</span></div>
                <div class="result-row"><span class="label">Average</span><span class="value">${avgConc.toFixed(4)} µg/m³</span></div>
                <div class="result-row"><span class="label">Max</span><span class="value">${maxConc.toFixed(4)} µg/m³</span></div>
                <div class="result-row"><span class="label">Emission Rate</span><span class="value">${params.emission_rate ? params.emission_rate.toFixed(4) : 'N/A'} ${params.emission_rate_unit || 'g/s'}</span></div>
                <div class="result-row"><span class="label">Wind Speed</span><span class="value">${params.wind_speed.toFixed(1)} m/s</span></div>
                <div class="result-row"><span class="label">Wind Dir</span><span class="value">${formatWindDir(params.wind_direction)}</span></div>
                <div class="result-row"><span class="label">Stability</span><span class="value">${params.stability_class}</span></div>
                <div class="result-row"><span class="label">Traffic</span><span class="value">${params.traffic_count.toLocaleString()}</span></div>
            `;
            
            addToHistory(params, maxConc);
        }

        function displayGridPoints(geojson, maxConc) {
            concentrationLayer.clearLayers();
            if (heatmapLayer && heatmapLayer._layer) { map.removeLayer(heatmapLayer._layer); heatmapLayer._layer = null; }
            
            const getColor = (c) => {
                if (c < 0.05) return '#22c55e';
                if (c < 0.1) return '#84cc16';
                if (c < 0.3) return '#eab308';
                if (c < 0.5) return '#f97316';
                return '#ef4444';
            };
            
            geojson.features.forEach(f => {
                const conc = f.properties.concentration;
                const coords = f.geometry.coordinates;
                
                // Use pulsing markers for points with high concentration
                const isHotspot = conc > (maxConc * 0.8);
                
                const marker = L.circleMarker([coords[1], coords[0]], {
                    radius: isHotspot ? 8 : 6, 
                    fillColor: getColor(conc), 
                    color: isHotspot ? '#fff' : 'transparent', 
                    weight: isHotspot ? 2 : 1, 
                    opacity: 1, 
                    fillOpacity: 0.85,
                    className: isHotspot ? 'pulse-marker' : ''
                });

                marker.on('click', function() {
                    showPointDetails(coords[1], coords[0], conc);
                });
                marker.addTo(concentrationLayer);
            });
        }

        function showPointDetails(lat, lon, conc) {
            document.getElementById('pointDetails').style.display = 'block';
            document.getElementById('pointDetailsBody').innerHTML = `
                <div class="result-row"><span class="label">Latitude</span><span class="value">${lat.toFixed(4)}°</span></div>
                <div class="result-row"><span class="label">Longitude</span><span class="value">${lon.toFixed(4)}°</span></div>
                <div class="result-row"><span class="label">Concentration</span><span class="value">${conc.toFixed(4)} µg/m³</span></div>
                <div class="result-row"><span class="label">Pollutant</span><span class="value">${document.getElementById('pollutantSelect').value}</span></div>
            `;
            
            if (currentConcentrationData && currentConcentrationData.features) {
                const distances = [];
                const concentrations = [];
                currentConcentrationData.features.forEach(f => {
                    const fc = f.geometry.coordinates;
                    const dist = Math.sqrt(Math.pow(fc[0] - lon, 2) + Math.pow(fc[1] - lat, 2)) * 111320 * Math.cos(lat * Math.PI / 180);
                    distances.push(dist);
                    concentrations.push(f.properties.concentration);
                });
                
                const sorted = distances.map((d, i) => ({ dist: d, conc: concentrations[i] })).sort((a, b) => a.dist - b.dist);
                
                const ctx = document.getElementById('pointChart').getContext('2d');
                if (window.pointChart) window.pointChart.destroy();
                
                window.pointChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: sorted.map(s => s.dist.toFixed(0) + 'm'),
                        datasets: [{
                            data: sorted.map(s => s.conc),
                            borderColor: '#00d4ff',
                            backgroundColor: 'rgba(0,212,255,0.1)',
                            fill: true,
                            tension: 0.3,
                            label: 'Concentration (µg/m³)'
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { ticks: { color: '#94a3b8', maxTicksLimit: 8 }, grid: { color: '#2d3748' }, title: { display: true, text: 'Distance from road (m)', color: '#94a3b8' } },
                            y: { ticks: { color: '#94a3b8' }, grid: { color: '#2d3748' }, title: { display: true, text: 'µg/m³', color: '#94a3b8' } }
                        }
                    }
                });
            }
            
            const popup = L.popup()
                .setLatLng([lat, lon])
                .setContent(`
                    <div style="min-width:150px;">
                        <strong style="color:#00d4ff;">Point Details</strong><br>
                        <span style="color:#94a3b8;">Lat:</span> ${lat.toFixed(4)}<br>
                        <span style="color:#94a3b8;">Lon:</span> ${lon.toFixed(4)}<br>
                        <span style="color:#94a3b8;">Concentration:</span> <strong style="color:#10b981;">${conc.toFixed(4)} µg/m³</strong>
                    </div>
                `)
                .openOn(map);
        }

        function displayHeatmap(geojson, maxConc) {
            concentrationLayer.clearLayers();
            if (heatmapLayer && heatmapLayer._layer) map.removeLayer(heatmapLayer._layer);
            
            const vizStyle = document.getElementById('vizStyle').value;
            if (vizStyle !== 'heatmap') return;
            
            const points = [];
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            
            geojson.features.forEach(f => {
                const conc = f.properties.concentration;
                if (conc > 0.001) {
                    const c = f.geometry.coordinates;
                    points.push({x: c[0], y: c[1], v: conc});
                    minX = Math.min(minX, c[0]); maxX = Math.max(maxX, c[0]);
                    minY = Math.min(minY, c[1]); maxY = Math.max(maxY, c[1]);
                }
            });
            
            if (!points.length) return;
            
            minX -= (maxX-minX)*0.1; maxX += (maxX-minX)*0.1;
            minY -= (maxY-minY)*0.1; maxY += (maxY-minY)*0.1;
            
            const w = 400, h = 400, c = document.createElement('canvas');
            c.width = w; c.height = h;
            const ctx = c.getContext('2d');
            
            points.forEach(p => {
                const x = ((p.x - minX) / (maxX - minX)) * w;
                const y = ((maxY - p.y) / (maxY - minY)) * h;
                const r = p.v / maxConc;
                let color;
                if (r < 0.2) color = `rgba(0,200,0,${r*2})`;
                else if (r < 0.4) color = `rgba(100,255,0,${r})`;
                else if (r < 0.6) color = `rgba(255,255,0,${r})`;
                else if (r < 0.8) color = `rgba(255,150,0,${r})`;
                else color = `rgba(255,0,0,${r})`;
                
                const radius = 15 + r * 25;
                const g = ctx.createRadialGradient(x, y, 0, x, y, radius);
                g.addColorStop(0, color);
                g.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = g;
                ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI*2); ctx.fill();
            });
            
            const img = new Image();
            img.src = c.toDataURL();
            img.onload = () => {
                const imgLayer = L.imageOverlay(img.src, [[minY, minX], [maxY, maxX]], { opacity: 0.6 });
                imgLayer.addTo(map);
                heatmapLayer._layer = imgLayer;
            };
        }

        function changeVizStyle() {
            if (currentConcentrationData && currentMaxConc > 0) {
                if (heatmapLayer && heatmapLayer._layer) { map.removeLayer(heatmapLayer._layer); heatmapLayer._layer = null; }
                const vizStyle = document.getElementById('vizStyle').value;
                if (vizStyle === 'heatmap') displayHeatmap(currentConcentrationData, currentMaxConc);
                else displayGridPoints(currentConcentrationData, currentMaxConc);
            }
        }

        function toggleLayer(name) {
            switch(name) {
                case 'roads': document.getElementById('showRoads').checked ? roadsLayer.addTo(map) : map.removeLayer(roadsLayer); break;
                case 'studyArea': document.getElementById('showStudyArea').checked ? studyAreaLayer.addTo(map) : map.removeLayer(studyAreaLayer); break;
                case 'pollution': document.getElementById('showPollution').checked ? loadPollutionData() : map.removeLayer(pollutionLayer); break;
                case 'concentrations':
                    const vizStyle = document.getElementById('vizStyle').value;
                    if (document.getElementById('showConcentrations').checked) {
                        if (vizStyle === 'heatmap' && heatmapLayer && heatmapLayer._layer) heatmapLayer._layer.addTo(map);
                        else concentrationLayer.addTo(map);
                    } else {
                        if (heatmapLayer && heatmapLayer._layer) map.removeLayer(heatmapLayer._layer);
                        map.removeLayer(concentrationLayer);
                    }
                    break;
            }
            saveLayerState();
        }

        async function loadPollutionData() {
            try {
                const res = await fetch('/api/pollution-data');
                const data = await res.json();
                pollutionLayer.clearLayers();
                L.geoJSON(data, {
                    pointToLayer: (f, latlng) => {
                        const nox = f.properties.NOx || 0;
                        const color = nox > 50 ? '#ef4444' : nox > 20 ? '#f59e0b' : '#10b981';
                        return L.circleMarker(latlng, { radius: 4, fillColor: color, color, weight: 1, fillOpacity: 0.6 });
                    }
                }).addTo(pollutionLayer);
            } catch (e) { console.error(e); }
        }

        async function downloadShapefile() {
            document.getElementById('loading').classList.add('active');
            document.querySelector('.loading-text').textContent = 'Creating shapefile...';
            const month = document.getElementById('monthSelect').value;
            const day = document.getElementById('daySelect').value;
            const hour = document.getElementById('hourSelect').value;
            const bufferDistance = document.getElementById('bufferDistance').value;
            const selectedRoads = Array.from(document.querySelectorAll('#tab-simulation .checkbox-group input[type="checkbox"]:checked')).map(cb => parseInt(cb.value));
            
            if (selectedRoads.length === 0) {
                showToast('Warning', 'Please select at least one road', 'warning');
                document.getElementById('loading').classList.remove('active');
                return;
            }
            
            try {
                const res = await fetch('/api/shapefile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        road_ids: selectedRoads,
                        pollutant: document.getElementById('pollutantSelect').value,
                        traffic_count: parseInt(document.getElementById('trafficCount').value),
                        day: day ? parseInt(day) : null,
                        month: month ? parseInt(month) : null,
                        hour: hour ? parseInt(hour) : null,
                        buffer_distance: parseInt(bufferDistance)
                    })
                });
                const result = await res.json();
                if (result.zip_path) window.location.href = `/output/${result.zip_path.split(/[\\\\/]/).pop()}`;
            } catch (e) { showToast('Error', 'Failed to create shapefile', 'error'); }
            document.getElementById('loading').classList.remove('active');
        }

        async function exportExcel() {
            document.getElementById('loading').classList.add('active');
            document.querySelector('.loading-text').textContent = 'Generating Excel...';
            const month = document.getElementById('monthSelect').value;
            const day = document.getElementById('daySelect').value;
            const hour = document.getElementById('hourSelect').value;
            const bufferDistance = document.getElementById('bufferDistance').value;
            const selectedRoads = Array.from(document.querySelectorAll('#tab-simulation .checkbox-group input[type="checkbox"]:checked')).map(cb => parseInt(cb.value));
            
            if (selectedRoads.length === 0) {
                showToast('Warning', 'Please select at least one road', 'warning');
                document.getElementById('loading').classList.remove('active');
                return;
            }
            
            try {
                const res = await fetch('/api/export-excel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        road_ids: selectedRoads,
                        pollutant: document.getElementById('pollutantSelect').value,
                        traffic_count: parseInt(document.getElementById('trafficCount').value),
                        day: day ? parseInt(day) : null,
                        month: month ? parseInt(month) : null,
                        hour: hour ? parseInt(hour) : null,
                        buffer_distance: parseInt(bufferDistance)
                    })
                });
                
                if (res.ok) {
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `kirkuk_air_quality_m${month||'all'}_d${day||'all'}_h${hour||'all'}_b${bufferDistance}_r${selectedRoads.join('-')}.xlsx`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                } else {
                    const err = await res.json();
                    showToast('Error', err.error || 'Failed to export Excel', 'error');
                }
            } catch (e) { showToast('Error', 'Failed to export Excel', 'error'); }
            document.getElementById('loading').classList.remove('active');
        }
        
        async function exportForAI() {
            document.getElementById('loading').classList.add('active');
            document.querySelector('.loading-text').textContent = 'Exporting for AI Training...';
            
            const month = document.getElementById('monthSelect').value;
            const day = document.getElementById('daySelect').value;
            const hour = document.getElementById('hourSelect').value;
            const bufferDistance = document.getElementById('bufferDistance').value;
            const selectedRoads = Array.from(document.querySelectorAll('#tab-simulation .checkbox-group input[type="checkbox"]:checked')).map(cb => parseInt(cb.value));
            
            if (selectedRoads.length === 0) {
                showToast('Warning', 'Please select at least one road', 'warning');
                document.getElementById('loading').classList.remove('active');
                return;
            }
            
            try {
                const pollutantValue = document.getElementById('pollutantSelect').value;

                
                const res = await fetch('/api/export-ai-csv', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        road_ids: selectedRoads,
                        pollutant: pollutantValue,
                        traffic_count: parseInt(document.getElementById('trafficCount').value),
                        day: day ? parseInt(day) : null,
                        month: month ? parseInt(month) : null,
                        hour: hour ? parseInt(hour) : null,
                        buffer_distance: parseInt(bufferDistance)
                    })
                });
                
                if (res.ok) {
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `ai_historical_data_r${selectedRoads.join('-')}.csv`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                } else {
                    const data = await res.json();
                    showToast('Error', data.error || 'Export failed', 'error');
                }
            } catch (e) { showToast('Error', 'Failed to export for AI', 'error'); }
            document.getElementById('loading').classList.remove('active');
        }

        document.getElementById('monthSelect').addEventListener('change', function() {
            loadWeatherData(document.getElementById('daySelect').value || null, this.value || null, document.getElementById('hourSelect').value || null);
            updateControlsState();
        });

        document.getElementById('daySelect').addEventListener('change', function() {
            loadWeatherData(this.value || null, document.getElementById('monthSelect').value || null, document.getElementById('hourSelect').value || null);
            updateControlsState();
        });

        document.getElementById('hourSelect').addEventListener('change', function() {
            loadWeatherData(document.getElementById('daySelect').value || null, document.getElementById('monthSelect').value || null, this.value || null);
            updateControlsState();
        });

        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM loaded, initializing...');
            
            // Check if welcome should be hidden
            checkWelcome();
            
            // Initialize map
            if (typeof L !== 'undefined') {
                console.log('Leaflet loaded, calling initMap');
                initMap();
            } else {
                console.error('Leaflet not loaded!');
                var script = document.createElement('script');
                script.src = '/static/js/leaflet.js';
                script.onload = function() { initMap(); };
                script.onerror = function() { showToast('Error', 'Failed to load map library', 'error'); };
                document.head.appendChild(script);
            }
        });
        
        // Forecast functions
        
        async function handleHistoricalUpload(input) {
            const file = input.files[0];
            if (!file) return;
            
            document.getElementById('historicalFileName').textContent = file.name;
            showUploadStatus('historicalUploadStatus', 'Uploading...', 'info');
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const res = await fetch('/api/upload-historical', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({ error: 'Upload failed' }));
                    showUploadStatus('historicalUploadStatus', 'Error: ' + errorData.error, 'error');
                    return;
                }
                
                const result = await res.json();
                
                if (result.success) {
                    showUploadStatus('historicalUploadStatus', `✓ Historical data: ${result.records} records loaded`, 'success');
                    document.getElementById('statusHistorical').classList.add('loaded');
                    checkForecastStatus();
                } else {
                    showUploadStatus('historicalUploadStatus', 'Error: ' + result.error, 'error');
                }
            } catch (e) {
                showUploadStatus('historicalUploadStatus', 'Error: ' + e.message, 'error');
            }
        }
        
        async function syncLivePollution() {
            const pollutionDash = document.getElementById('livePollutionDashboard');
            const aqiBadge = document.getElementById('aqiBadge');
            
            try {
                const res = await fetch('/api/pollution/live');
                const data = await res.json();
                
                if (data.success) {
                    if (pollutionDash) pollutionDash.style.display = 'block';
                    if (aqiBadge) {
                        aqiBadge.style.display = 'block';
                        aqiBadge.textContent = `AQI: ${data.summary.aqi}`;
                        aqiBadge.className = `aqi-badge aqi-${data.summary.aqi}`;
                        
                        const aqiLabels = ['', 'Good', 'Fair', 'Moderate', 'Poor', 'Very Poor'];
                        aqiBadge.title = `Air Quality: ${aqiLabels[data.summary.aqi]}`;
                    }
                    
                    document.getElementById('liveNO2').textContent = data.summary.no2.toFixed(1);
                    document.getElementById('livePM25').textContent = data.summary.pm2_5.toFixed(1);
                    document.getElementById('livePM10').textContent = data.summary.pm10.toFixed(1);
                    document.getElementById('liveSO2').textContent = data.summary.so2.toFixed(1);
                    document.getElementById('liveCO').textContent = (data.summary.co / 1000).toFixed(2); // Convert to mg/m3
                    
                    const pollutionTime = document.getElementById('livePollutionTime');
                    if (pollutionTime) pollutionTime.textContent = new Date().toLocaleTimeString();
                }
            } catch (e) {
                console.error('Error syncing pollution:', e);
            }
        }

        async function checkForecastStatus() {
            try {
                const res = await fetch('/api/forecast/status');
                const data = await res.json();
                
                const statusHistorical = document.getElementById('statusHistorical');
                const statusWeatherForecast = document.getElementById('statusWeatherForecast');
                const statusModel = document.getElementById('statusModel');
                
                if (data.has_historical_data) {
                    statusHistorical.classList.add('loaded');
                } else {
                    statusHistorical.classList.remove('loaded');
                }
                
                if (data.has_weather_data) {
                    statusWeatherForecast.classList.add('loaded');
                } else {
                    statusWeatherForecast.classList.remove('loaded');
                }
                
                if (data.model_trained) {
                    statusModel.classList.add('loaded');
                    document.getElementById('modelStatus').style.display = 'block';
                    document.getElementById('getForecastBtn').disabled = false;
                    let accuracyHtml = '';
                    if (data.model_info.val_rmse !== undefined) {
                        accuracyHtml = `
                            <div class="result-row"><span class="label">RMSE</span><span class="value">${data.model_info.val_rmse.toFixed(4)}</span></div>
                            <div class="result-row"><span class="label">MAE</span><span class="value">${data.model_info.val_mae?.toFixed(4) || 'N/A'}</span></div>
                            <div class="result-row"><span class="label">Samples</span><span class="value">${data.model_info.train_samples} train / ${data.model_info.val_samples} val</span></div>
                        `;
                    }
                    document.getElementById('modelStatusBody').innerHTML = `
                        <div class="result-row"><span class="label">Status</span><span class="value" style="color:#10b981;">Trained</span></div>
                        <div class="result-row"><span class="label">Sequence Length</span><span class="value">${data.model_info.sequence_length} hours</span></div>
                        <div class="result-row"><span class="label">Forecast Horizon</span><span class="value">${data.model_info.forecast_horizon} hours</span></div>
                        <div class="result-row"><span class="label">Pollutants</span><span class="value">${data.model_info.pollutants.join(', ')}</span></div>
                        ${accuracyHtml}
                    `;
                } else {
                    statusModel.classList.remove('loaded');
                    document.getElementById('getForecastBtn').disabled = true;
                }
            } catch (e) {
                console.error('Error checking forecast status:', e);
            }
        }
        
        async function trainForecastModel() {
            const sequenceLength = document.getElementById('sequenceLength').value;
            const forecastHours = document.getElementById('forecastHours').value;
            
            document.getElementById('loading').classList.add('active');
            setLoadingProgress(10, 'Training LSTM model...', 'Preparing data');
            
            try {
                setLoadingProgress(30, 'Training LSTM model...', 'Loading historical data');
                const res = await fetch('/api/forecast/train', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sequence_length: parseInt(sequenceLength),
                        forecast_horizon: parseInt(forecastHours),
                        epochs: 10,
                        batch_size: 16
                    })
                });
                
                setLoadingProgress(70, 'Training LSTM model...', 'Training neural network');
                const data = await res.json();
                
                if (data.success) {
                    document.getElementById('statusModel').classList.add('loaded');
                    document.getElementById('statusPredicted').classList.remove('loaded');
                    document.getElementById('modelStatus').style.display = 'block';
                    document.getElementById('getForecastBtn').disabled = false;
                    const rmse = data.val_rmse ? (data.val_rmse * 100).toFixed(2) + '%' : 'N/A';
                    const mae = data.val_mae ? (data.val_mae * 100).toFixed(2) + '%' : 'N/A';
                    document.getElementById('modelStatusBody').innerHTML = `
                        <div class="result-row"><span class="label">Status</span><span class="value" style="color:#10b981;">Trained Successfully</span></div>
                        <div class="result-row"><span class="label">Accuracy (RMSE)</span><span class="value">${rmse}</span></div>
                        <div class="result-row"><span class="label">Accuracy (MAE)</span><span class="value">${mae}</span></div>
                        <div class="result-row"><span class="label">Validation MSE</span><span class="value">${data.val_mse?.toFixed(6) || 'N/A'}</span></div>
                        <div class="result-row"><span class="label">Epochs</span><span class="value">${data.epochs_trained}</span></div>
                        <div class="result-row"><span class="label">Training Samples</span><span class="value">${data.train_samples}</span></div>
                        <div class="result-row"><span class="label">Validation Samples</span><span class="value">${data.val_samples}</span></div>
                    `;
                    document.getElementById('forecastResults').style.display = 'none';
                    showToast('Success', `Model trained! Accuracy: ${rmse}. Click "Get Predictions" to forecast.`, 'success');
                } else {
                    showToast('Error', data.error || 'Training failed', 'error');
                }
            } catch (e) {
                showToast('Error', 'Training failed: ' + e.message, 'error');
            } finally {
                setLoadingProgress(100, 'Complete', 'Done');
                setTimeout(() => {
                    document.getElementById('loading').classList.remove('active');
                    setLoadingProgress(0, 'Processing...', 'Please wait...');
                }, 500);
            }
        }
        
        function displayForecastResults(data) {
            lastForecastData = data;
            const resultsDiv = document.getElementById('forecastResults');
            resultsDiv.style.display = 'block';
            document.getElementById('statusPredicted').classList.add('loaded');
            
            const predictions = data.predictions;
            const pollutants = data.pollutants || ['CO', 'NOx', 'PM10', 'PM2.5'];
            
            let html = '<div class="result-row"><span class="label">Model Type</span><span class="value">' + data.model_type + '</span></div>';
            html += '<div class="result-row"><span class="label">Forecast Hours</span><span class="value">' + predictions.length + '</span></div>';
            html += '<div class="result-row"><span class="label">Pollutants</span><span class="value">' + pollutants.join(', ') + '</span></div>';
            
            if (data.training_results) {
                html += '<div class="result-row"><span class="label">RMSE</span><span class="value">' + data.training_results.val_rmse?.toFixed(4) || 'N/A' + '</span></div>';
            }
            
            document.getElementById('forecastResultsBody').innerHTML = html;
            
            // Create chart
            const ctx = document.getElementById('forecastChart').getContext('2d');
            
            if (forecastChart) {
                forecastChart.destroy();
            }
            
            const labels = predictions.map((p, i) => {
                const date = new Date(p.timestamp);
                return date.getHours() + ':00';
            });
            
            const colors = {
                'NOx': 'rgb(255, 99, 132)',
                'CO': 'rgb(54, 162, 235)',
                'PM10': 'rgb(255, 206, 86)',
                'PM2.5': 'rgb(75, 192, 192)',
                'Concentration': 'rgb(153, 102, 255)'
            };
            
            const datasets = pollutants.map(pollutant => ({
                label: pollutant,
                data: predictions.map(p => p[pollutant]),
                borderColor: colors[pollutant] || 'rgb(150, 150, 150)',
                backgroundColor: colors[pollutant] || 'rgb(150, 150, 150)',
                fill: false,
                tension: 0.3
            }));
            
            forecastChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: { color: '#94a3b8', padding: 15, usePointStyle: true }
                        },
                        tooltip: { 
                            backgroundColor: 'rgba(17,24,39,0.95)',
                            titleColor: '#f0f4f8',
                            bodyColor: '#94a3b8',
                            borderColor: '#2d3748',
                            borderWidth: 1,
                            cornerRadius: 8,
                            padding: 12,
                            displayColors: true,
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + context.parsed.y.toFixed(4);
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: '#2d3748' }
                        },
                        y: {
                            ticks: { color: '#94a3b8' },
                            grid: { color: '#2d3748' }
                        }
                    }
                }
            });
        }
        
        function exportForecastCSV() {
            if (!lastForecastData || !lastForecastData.predictions) {
                showToast('Info', 'No forecast data available. Run prediction first.', 'info');
                return;
            }
            
            const predictions = lastForecastData.predictions;
            let pollutants = lastForecastData.pollutants || ['Concentration'];
            
            if (!pollutants || !pollutants.length) {
                pollutants = ['Concentration'];
            }

            const hasCoords = predictions[0] && (predictions[0].Longitude !== undefined || predictions[0].Latitude !== undefined);
            
            let headers = ['timestamp'];
            if (hasCoords) {
                headers = ['timestamp', 'Longitude', 'Latitude', 'X (m)', 'Y (m)'];
            }
            headers = headers.concat(pollutants.map(p => `Concentration (${p})`));
            
            let csvContent = headers.join(',') + '\n';
            predictions.forEach(p => {
                let row = [p.timestamp || ''];
                if (hasCoords) {
                    row = row.concat([
                        p.Longitude !== undefined ? p.Longitude : '',
                        p.Latitude !== undefined ? p.Latitude : '',
                        p['X (m)'] !== undefined ? p['X (m)'] : '',
                        p['Y (m)'] !== undefined ? p['Y (m)'] : ''
                    ]);
                }
                const pollutantValues = pollutants.map(pollutant => {
                    const val = p[pollutant];
                    return (val !== undefined && val !== null && val !== '') ? val : '';
                });
                csvContent += row.join(',') + ',' + pollutantValues.join(',') + '\n';
            });
            
            const blob = new Blob([csvContent], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `predicted_pollution_${new Date().toISOString().slice(0,10)}.csv`;
            a.click();
            window.URL.revokeObjectURL(url);
        }
        
        async function exportForecastShapefile() {
            if (!lastForecastData || !lastForecastData.predictions) {
                showToast('Info', 'No forecast data available. Run prediction first.', 'info');
                return;
            }
            
            document.getElementById('loading').classList.add('active');
            setLoadingProgress(30, 'Exporting shapefile...', 'Generating files');
            
            try {
                const res = await safeFetch('/api/forecast-shapefile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                
                setLoadingProgress(80, 'Exporting shapefile...', 'Preparing download');
                
                if (res.error) {
                    showToast('Error', res.error, 'error');
                    return;
                }
                
                if (!res.zip_path) {
                    showToast('Error', 'No zip path returned from server', 'error');
                    return;
                }
                
                const timestamp = new Date().toISOString().slice(0,10);
                const shpUrl = res.zip_path;
                const filename = shpUrl.split(/[\\\\/]/).pop();
                
                const baseUrl = window.location.origin;
                const link = document.createElement('a');
                link.href = baseUrl + '/output/' + filename;
                link.download = `forecast_pollution_${timestamp}.zip`;
                link.click();
                
                showToast('Success', 'Forecast shapefile exported successfully', 'success');
            } catch (e) {
                showToast('Error', e.message || 'Failed to export shapefile', 'error');
            } finally {
                setLoadingProgress(100, 'Complete', 'Done');
                setTimeout(() => {
                    document.getElementById('loading').classList.remove('active');
                    setLoadingProgress(0, 'Processing...', 'Please wait...');
                }, 500);
            }
        }
        
        async function getForecast() {
            const hours = document.getElementById('forecastHours').value;
            
            if (!hours || hours.trim() === '' || isNaN(parseInt(hours))) {
                showToast('Warning', 'Forecast hours must be a valid number', 'warning');
                const hField = document.getElementById('forecastHours');
                hField.style.borderColor = 'var(--error)';
                setTimeout(() => hField.style.borderColor = '', 3000);
                return;
            }
            
            document.getElementById('loading').classList.add('active');
            setLoadingProgress(30, 'Generating forecast...', 'Fetching prediction data');
            
            try {
                const res = await fetch(`/api/forecast?hours=${hours}`);
                const data = await res.json();
                
                if (data.success) {
                    lastForecastData = data;
                    displayForecastResults(data);
                    showToast('Success', 'Forecast generated successfully', 'success');
                } else {
                    showToast('Error', data.error || 'Failed to generate forecast', 'error');
                }
            } catch (e) {
                showToast('Error', e.message || 'Network error', 'error');
            } finally {
                setLoadingProgress(100, 'Complete', 'Done');
                setTimeout(() => {
                    document.getElementById('loading').classList.remove('active');
                    setLoadingProgress(0, 'Processing...', 'Please wait...');
                }, 500);
            }
        }

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const welcome = document.getElementById('welcomeOverlay');
                if (welcome && !welcome.classList.contains('hidden')) {
                    dismissWelcome();
                }
                const loading = document.getElementById('loading');
                if (loading.classList.contains('active')) {
                    loading.classList.remove('active');
                }
                clearMeasurement();
            }
            
            if (e.ctrlKey && e.key === 'Enter') {
                e.preventDefault();
                const runBtn = document.querySelector('#tab-simulation .btn-primary');
                if (runBtn && !runBtn.disabled) {
                    runBtn.click();
                }
            }
            
            if (e.key === 'f' || e.key === 'F') {
                if (!e.target.matches('input, textarea, select')) {
                    toggleFullscreen();
                }
            }
        });
