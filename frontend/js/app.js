let currentJobs = [];

document.getElementById('scrape-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const keyword = document.getElementById('keyword').value;
    const location = document.getElementById('location').value;
    const jobType = document.getElementById('job-type').value;
    const maxPages = parseInt(document.getElementById('max-pages').value, 10);
    
    const platforms = [];
    if(document.getElementById('plat-indeed').checked) platforms.push('indeed');
    if(document.getElementById('plat-linkedin').checked) platforms.push('linkedin');
    
    if (platforms.length === 0) {
        alert("Please select at least one platform.");
        return;
    }

    setLoading(true, "Scraping jobs from " + platforms.join(", ") + "...");
    
    try {
        const response = await fetch(API_BASE + '/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, location, job_type: jobType, platforms, max_pages: maxPages })
        });
        
        if (!response.ok) throw new Error("Failed to scrape jobs.");
        
        const data = await response.json();
        
        if (data.status === "cancelled") {
            alert("Scrape was cancelled.");
        }
        
        currentJobs = data.jobs || [];
        
        renderJobs();
        document.getElementById('btn-verify').disabled = currentJobs.length === 0;
        
    } catch (err) {
        alert(err.message);
    } finally {
        setLoading(false);
    }
});

document.getElementById('btn-cancel-scrape').addEventListener('click', async () => {
    try {
        const response = await fetch(API_BASE + '/api/scrape/cancel', { method: 'POST' });
        if (!response.ok) throw new Error("Failed to cancel scrape.");
        setLoading(true, "Cancelling scrape...");
    } catch (err) {
        alert(err.message);
    }
});

document.getElementById('btn-verify').addEventListener('click', async () => {
    if (currentJobs.length === 0) return;
    
    setLoading(true, "Verifying " + currentJobs.length + " jobs...");
    document.getElementById('btn-verify').disabled = true;
    
    try {
        const response = await fetch(API_BASE + '/api/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ jobs: currentJobs })
        });
        
        if (!response.ok) throw new Error("Failed to verify jobs.");
        
        const data = await response.json();
        currentJobs = data.jobs || [];
        
        renderJobs();
        
    } catch (err) {
        alert(err.message);
        document.getElementById('btn-verify').disabled = false;
    } finally {
        setLoading(false);
    }
});

function setLoading(isLoading, text = "Processing...") {
    const loadingEl = document.getElementById('loading');
    const container = document.getElementById('jobs-container');
    const btnScrape = document.getElementById('btn-scrape');
    const btnCancel = document.getElementById('btn-cancel-scrape');
    
    if (isLoading) {
        document.getElementById('loading-text').innerText = text;
        loadingEl.classList.remove('hidden');
        container.classList.add('hidden');
        btnScrape.disabled = true;
        if (text.includes("Scraping") || text.includes("Cancelling")) {
            btnCancel.style.display = 'inline-block';
        } else {
            btnCancel.style.display = 'none';
        }
    } else {
        loadingEl.classList.add('hidden');
        container.classList.remove('hidden');
        btnScrape.disabled = false;
        btnCancel.style.display = 'none';
    }
}

function renderJobs() {
    const container = document.getElementById('jobs-container');
    document.getElementById('job-count').innerText = currentJobs.length;
    
    if (currentJobs.length === 0) {
        container.innerHTML = '<div class="empty-state">No jobs found. Try different keywords.</div>';
        return;
    }
    
    container.innerHTML = currentJobs.map(job => {
        const status = job.verified_status || "none";
        const statusClass = `status-${status.replace(/_/g, '-')}`;
        const statusText = status === "none" ? "UNVERIFIED" : status.replace(/_/g, ' ');
        
        return `
            <div class="job-card">
                <div class="job-platform">${job.platform}</div>
                <div class="job-title">${escapeHTML(job.title)}</div>
                <div class="job-company">${escapeHTML(job.company)}</div>
                
                <div class="job-meta">
                    <div>📍 ${escapeHTML(job.location || 'N/A')}</div>
                    <div>💼 ${escapeHTML(job.job_type || 'N/A')}</div>
                    <div>💰 ${escapeHTML(job.salary || 'N/A')}</div>
                </div>
                
                <div class="job-footer">
                    <span class="status-badge ${statusClass}">${statusText}</span>
                    <a href="${escapeHTML(job.apply_link)}" target="_blank">View Job →</a>
                </div>
            </div>
        `;
    }).join('');
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

// ---- Live log viewer ----
const API_BASE = 'https://YOUR-APP.up.railway.app';

const logOut       = document.getElementById("log-output");
const logStatus    = document.getElementById("log-status");
const logAutoscroll= document.getElementById("log-autoscroll");
const logFilter    = document.getElementById("log-level-filter");

const LEVEL_RANK   = { DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50 };

function logPasses(level) {
    const sel = logFilter.value;
    return sel === "ALL" || (LEVEL_RANK[level] || 0) >= (LEVEL_RANK[sel] || 0);
}

function appendLogEntry(entry) {
    const line = document.createElement("span");
    line.className = "log-line log-" + (entry.level || "INFO").toLowerCase();
    line.dataset.level = entry.level || "INFO";
    
    line.innerHTML = 
        `<span class="log-meta">[${entry.time}] ${(entry.level || "").padEnd(8)}${entry.logger}</span>   ` +
        escapeHTML(entry.message);
        
    if (!logPasses(line.dataset.level)) line.style.display = "none";
    logOut.appendChild(line);
    
    if (logAutoscroll.checked) logOut.scrollTop = logOut.scrollHeight;
}

let logSource;

function connectLogs() {
    logSource = new EventSource(`${API_BASE}/api/logs/stream`);
    
    logSource.onopen  = () => { logStatus.style.color = "#3fb950"; logStatus.title = "connected"; };
    
    logSource.onmessage = (e) => { 
        try { 
            appendLogEntry(JSON.parse(e.data)); 
        } catch (_) {} 
    };
    
    logSource.onerror = () => { 
        logStatus.style.color = "#f85149"; 
        logStatus.title = "reconnecting…"; 
    };
    // NOTE: EventSource reconnects automatically; the server resumes via Last-Event-ID.
}

// Filter toggling re-applies visibility to existing lines
logFilter.addEventListener("change", () => {
    document.querySelectorAll("#log-output .log-line").forEach(l => {
        l.style.display = logPasses(l.dataset.level) ? "" : "none";
    });
});

document.getElementById("log-clear").addEventListener("click", () => { logOut.innerHTML = ""; });

connectLogs();
