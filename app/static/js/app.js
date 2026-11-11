// Linux SSH Server Monitor Frontend Logic

let allServers = [];
let currentFilter = 'ALL';
let currentSearch = '';
let autoRefreshTimer = null;
let activeDetailServerId = null;
let activeExecServerId = null;

let cpuChartInstance = null;
let ramChartInstance = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    fetchAllData();
    setupAutoRefresh(15);
});

// Toast notification helper
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    const colors = {
        success: 'bg-emerald-600 text-white border-emerald-500',
        error: 'bg-rose-600 text-white border-rose-500',
        info: 'bg-slate-800 text-slate-200 border-slate-700',
        warning: 'bg-amber-600 text-white border-amber-500'
    };
    const icons = {
        success: 'fa-circle-check',
        error: 'fa-circle-xmark',
        info: 'fa-circle-info',
        warning: 'fa-triangle-exclamation'
    };

    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl border shadow-xl text-xs font-medium transition-all transform translate-y-2 opacity-0 duration-300 ${colors[type] || colors.info}`;
    toast.innerHTML = `
        <i class="fa-solid ${icons[type] || icons.info} text-sm"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    });

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Fetch all servers and overview stats
async function fetchAllData(isManual = false) {
    const refreshIcon = document.getElementById('refreshAllIcon');
    if (refreshIcon) refreshIcon.classList.add('animate-spin');

    try {
        const [statsRes, serversRes] = await Promise.all([
            fetch('/api/stats/overview'),
            fetch('/api/servers')
        ]);

        if (statsRes.ok) {
            const stats = await statsRes.json();
            updateStatsBar(stats);
        }

        if (serversRes.ok) {
            allServers = await serversRes.json();
            renderServerGrid();

            // If detail modal is open, refresh its data
            if (activeDetailServerId) {
                const updatedServer = allServers.find(s => s.id === activeDetailServerId);
                if (updatedServer) {
                    renderServerDetails(updatedServer);
                }
            }
        }

        if (isManual) {
            showToast('All server metrics refreshed', 'success');
        }
    } catch (err) {
        console.error('Failed to fetch monitoring data:', err);
        if (isManual) {
            showToast('Failed to refresh data: ' + err.message, 'error');
        }
    } finally {
        if (refreshIcon) {
            setTimeout(() => refreshIcon.classList.remove('animate-spin'), 600);
        }
    }
}

// Update Top Statistics Cards
function updateStatsBar(stats) {
    document.getElementById('statTotal').innerText = stats.total || 0;
    document.getElementById('statOnline').innerText = stats.online || 0;
    document.getElementById('statOffline').innerText = stats.offline || 0;
    document.getElementById('statAvgCpu').innerText = (stats.avg_cpu || 0) + '%';
    document.getElementById('statAvgRam').innerText = (stats.avg_ram || 0) + '%';
}

// Auto-refresh timer management
function changeAutoRefresh(val) {
    const seconds = parseInt(val, 10);
    setupAutoRefresh(seconds);
}

function setupAutoRefresh(seconds) {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }
    if (seconds > 0) {
        autoRefreshTimer = setInterval(() => {
            fetchAllData();
        }, seconds * 1000);
    }
}

// Distro detection helper
function detectDistro(osName) {
    const lower = (osName || '').toLowerCase();
    if (lower.includes('ubuntu')) {
        return {
            name: 'Ubuntu',
            icon: 'fa-brands fa-ubuntu',
            badgeClass: 'badge-ubuntu',
            color: '#E95420'
        };
    } else if (lower.includes('centos') || lower.includes('red hat') || lower.includes('rhel') || lower.includes('rocky') || lower.includes('alma')) {
        return {
            name: 'CentOS / RHEL',
            icon: 'fa-brands fa-redhat',
            badgeClass: 'badge-centos',
            color: '#A020F0'
        };
    } else if (lower.includes('debian')) {
        return {
            name: 'Debian',
            icon: 'fa-brands fa-debian',
            badgeClass: 'badge-debian',
            color: '#D70A53'
        };
    } else {
        return {
            name: osName || 'Linux',
            icon: 'fa-brands fa-linux',
            badgeClass: 'badge-generic',
            color: '#64748b'
        };
    }
}

// Filter and Search logic
function setOsFilter(filter) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('bg-indigo-600', 'text-white', 'active-filter');
        btn.classList.add('bg-slate-800', 'text-slate-300');
    });
    const activeBtn = document.getElementById('filterBtn' + filter);
    if (activeBtn) {
        activeBtn.classList.remove('bg-slate-800', 'text-slate-300');
        activeBtn.classList.add('bg-indigo-600', 'text-white', 'active-filter');
    }
    renderServerGrid();
}

function filterServers() {
    currentSearch = (document.getElementById('searchInput').value || '').toLowerCase().trim();
    renderServerGrid();
}

// Render Server Cards in Grid
function renderServerGrid() {
    const grid = document.getElementById('serversGrid');
    const emptyState = document.getElementById('emptyState');

    let filtered = allServers.filter(s => {
        // OS filter
        const osLower = (s.os_name || '').toLowerCase();
        if (currentFilter === 'UBUNTU' && !osLower.includes('ubuntu')) return false;
        if (currentFilter === 'CENTOS' && !(osLower.includes('centos') || osLower.includes('red hat') || osLower.includes('rhel') || osLower.includes('rocky') || osLower.includes('alma'))) return false;
        if (currentFilter === 'DEBIAN' && !osLower.includes('debian')) return false;

        // Search query
        if (currentSearch) {
            const matchName = s.name.toLowerCase().includes(currentSearch);
            const matchHost = s.host.toLowerCase().includes(currentSearch);
            const matchOs = (s.os_name || '').toLowerCase().includes(currentSearch);
            const matchTags = (s.tags || []).some(t => t.toLowerCase().includes(currentSearch));
            if (!matchName && !matchHost && !matchOs && !matchTags) return false;
        }

        return true;
    });

    if (allServers.length === 0) {
        grid.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    } else {
        emptyState.classList.add('hidden');
    }

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div class="col-span-full py-12 text-center text-slate-400">
                <i class="fa-solid fa-filter text-2xl mb-2 text-slate-500"></i>
                <p class="text-sm">No servers match your filter or search query.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = filtered.map(server => {
        const distro = detectDistro(server.os_name);
        const isOnline = server.last_status === 'online';
        const isOffline = server.last_status === 'offline';
        const metric = server.latest_metric || {};

        const cpuPct = metric.cpu_percent !== undefined ? metric.cpu_percent : 0;
        const ramPct = metric.ram_percent !== undefined ? metric.ram_percent : 0;
        const diskPct = metric.disk_percent !== undefined ? metric.disk_percent : 0;

        // Color coding for progress bars
        const getBarColor = (pct) => {
            if (pct >= 85) return 'bg-rose-500';
            if (pct >= 65) return 'bg-amber-500';
            return 'bg-emerald-500';
        };

        const getTextColor = (pct) => {
            if (pct >= 85) return 'text-rose-400';
            if (pct >= 65) return 'text-amber-400';
            return 'text-emerald-400';
        };

        const statusBadge = isOnline
            ? `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                 <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-online"></span> Online
               </span>`
            : isOffline
            ? `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                 <span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> Offline
               </span>`
            : `<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
                 <span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span> Unknown
               </span>`;

        return `
            <div class="bg-darkcard border border-darkborder hover:border-slate-600 transition-all rounded-2xl p-5 shadow-sm flex flex-col justify-between space-y-4">
                
                <!-- Server Card Header -->
                <div>
                    <div class="flex items-start justify-between gap-2 mb-2">
                        <div class="flex items-center gap-2.5">
                            <div class="w-9 h-9 rounded-xl flex items-center justify-center text-base ${distro.badgeClass}">
                                <i class="${distro.icon}"></i>
                            </div>
                            <div>
                                <h3 class="text-sm font-bold text-white tracking-tight truncate max-w-[170px]" title="${escapeHtml(server.name)}">
                                    ${escapeHtml(server.name)}
                                </h3>
                                <p class="text-xs text-slate-400 font-mono flex items-center gap-1">
                                    <span>${escapeHtml(server.host)}:${server.port}</span>
                                    <button onclick="copyToClipboard('${escapeHtml(server.host)}')" title="Copy IP" class="text-slate-500 hover:text-slate-300">
                                        <i class="fa-regular fa-copy text-[10px]"></i>
                                    </button>
                                </p>
                            </div>
                        </div>
                        <div>
                            ${statusBadge}
                        </div>
                    </div>

                    <!-- Tags and OS Subtitle -->
                    <div class="flex items-center flex-wrap gap-1.5 mt-2">
                        <span class="text-[10px] font-semibold px-2 py-0.5 rounded-md ${distro.badgeClass}">
                            ${escapeHtml(server.os_name || distro.name)}
                        </span>
                        ${(server.tags || []).map(t => `
                            <span class="text-[10px] px-2 py-0.5 rounded-md bg-slate-800 text-slate-400 border border-darkborder">
                                #${escapeHtml(t)}
                            </span>
                        `).join('')}
                    </div>
                </div>

                <!-- Server Live Metrics Bars -->
                ${isOnline ? `
                    <div class="space-y-3 bg-slate-900/40 p-3.5 rounded-xl border border-darkborder/50">
                        <!-- CPU Bar -->
                        <div>
                            <div class="flex items-center justify-between text-xs mb-1">
                                <span class="text-slate-400 font-medium flex items-center gap-1.5">
                                    <i class="fa-solid fa-microchip text-[11px] text-indigo-400"></i> CPU Load
                                </span>
                                <span class="font-bold ${getTextColor(cpuPct)}">${cpuPct}%</span>
                            </div>
                            <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                                <div class="${getBarColor(cpuPct)} h-full metric-bar-fill rounded-full" style="width: ${Math.min(100, Math.max(0, cpuPct))}%"></div>
                            </div>
                        </div>

                        <!-- RAM Bar -->
                        <div>
                            <div class="flex items-center justify-between text-xs mb-1">
                                <span class="text-slate-400 font-medium flex items-center gap-1.5">
                                    <i class="fa-solid fa-memory text-[11px] text-purple-400"></i> RAM
                                </span>
                                <span class="font-bold ${getTextColor(ramPct)}">
                                    ${metric.ram_used_mb ? (metric.ram_used_mb > 1024 ? (metric.ram_used_mb/1024).toFixed(1) + ' GB' : Math.round(metric.ram_used_mb) + ' MB') : '0 MB'} 
                                    (${ramPct}%)
                                </span>
                            </div>
                            <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                                <div class="${getBarColor(ramPct)} h-full metric-bar-fill rounded-full" style="width: ${Math.min(100, Math.max(0, ramPct))}%"></div>
                            </div>
                        </div>

                        <!-- Disk Bar -->
                        <div>
                            <div class="flex items-center justify-between text-xs mb-1">
                                <span class="text-slate-400 font-medium flex items-center gap-1.5">
                                    <i class="fa-solid fa-hard-drive text-[11px] text-amber-400"></i> Disk
                                </span>
                                <span class="font-bold ${getTextColor(diskPct)}">
                                    ${metric.disk_used_gb || 0} / ${metric.disk_total_gb || 0} GB (${diskPct}%)
                                </span>
                            </div>
                            <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                                <div class="${getBarColor(diskPct)} h-full metric-bar-fill rounded-full" style="width: ${Math.min(100, Math.max(0, diskPct))}%"></div>
                            </div>
                        </div>

                        <!-- Network & Uptime Footer Info -->
                        <div class="pt-2 border-t border-darkborder/40 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                            <span title="Network Rx / Tx rate">
                                <i class="fa-solid fa-arrow-down text-emerald-400"></i> ${metric.net_rx_rate_kbps || 0}k 
                                <i class="fa-solid fa-arrow-up text-indigo-400 ml-1"></i> ${metric.net_tx_rate_kbps || 0}k
                            </span>
                            <span title="Server Uptime">
                                <i class="fa-regular fa-clock text-slate-500 mr-0.5"></i> ${server.uptime_str || 'N/A'}
                            </span>
                        </div>
                    </div>
                ` : `
                    <div class="bg-rose-950/20 border border-rose-900/30 rounded-xl p-3.5 text-center text-xs space-y-1">
                        <i class="fa-solid fa-triangle-exclamation text-rose-400 text-base mb-1"></i>
                        <p class="text-rose-300 font-medium">Host Unreachable / SSH Failed</p>
                        <p class="text-rose-400/70 text-[11px] truncate" title="${escapeHtml(server.last_error || 'No response')}">
                            ${escapeHtml(server.last_error || 'Connection timed out')}
                        </p>
                    </div>
                `}

                <!-- Card Actions -->
                <div class="flex items-center justify-between pt-2 border-t border-darkborder">
                    <div class="flex items-center gap-1.5">
                        <button onclick="openDetailsModal(${server.id})" class="px-2.5 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 rounded-lg border border-darkborder flex items-center gap-1 transition-all" title="View Charts & System Details">
                            <i class="fa-solid fa-chart-line text-indigo-400"></i>
                            <span>Details</span>
                        </button>
                        <button onclick="openExecModal(${server.id})" class="px-2.5 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 rounded-lg border border-darkborder flex items-center gap-1 transition-all" title="Run Remote SSH Command">
                            <i class="fa-solid fa-terminal text-emerald-400"></i>
                            <span>SSH</span>
                        </button>
                    </div>

                    <div class="flex items-center gap-1">
                        <button onclick="pollSingleServer(${server.id}, this)" class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-all" title="Poll Now">
                            <i class="fa-solid fa-rotate text-xs"></i>
                        </button>
                        <button onclick="openEditServerModal(${server.id})" class="p-1.5 text-slate-400 hover:text-indigo-400 hover:bg-slate-800 rounded-lg transition-all" title="Edit Server">
                            <i class="fa-solid fa-pen-to-square text-xs"></i>
                        </button>
                        <button onclick="deleteServer(${server.id}, '${escapeHtml(server.name)}')" class="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-all" title="Delete Server">
                            <i class="fa-solid fa-trash-can text-xs"></i>
                        </button>
                    </div>
                </div>

            </div>
        `;
    }).join('');
}

// Single Server Polling Trigger
async function pollSingleServer(serverId, btnElement) {
    const icon = btnElement ? btnElement.querySelector('i') : null;
    if (icon) icon.classList.add('animate-spin');

    try {
        const res = await fetch(`/api/servers/${serverId}/poll`, { method: 'POST' });
        const data = await res.json();
        if (data.result && data.result.success) {
            showToast('Server metrics updated successfully', 'success');
        } else {
            showToast('Polling error: ' + (data.result.error || 'Host unreachable'), 'warning');
        }
        await fetchAllData();
    } catch (err) {
        showToast('Failed to poll server: ' + err.message, 'error');
    } finally {
        if (icon) icon.classList.remove('animate-spin');
    }
}

// ==================== ADD / EDIT SERVER MODAL ====================
function openServerModal(isEdit = false) {
    document.getElementById('serverForm').reset();
    document.getElementById('serverId').value = '';
    document.getElementById('serverSudoPassword').value = '';
    document.getElementById('testConnResult').classList.add('hidden');
    document.getElementById('modalTitle').innerHTML = `
        <i class="fa-solid fa-server text-indigo-400"></i>
        <span>Add New Linux Server</span>
    `;
    document.getElementById('submitServerText').innerText = 'Save Server';
    toggleAuthFields();
    document.getElementById('serverModal').classList.remove('hidden');
}

function openEditServerModal(serverId) {
    const server = allServers.find(s => s.id === serverId);
    if (!server) return;

    openServerModal(true);
    document.getElementById('serverId').value = server.id;
    document.getElementById('serverName').value = server.name;
    document.getElementById('serverHost').value = server.host;
    document.getElementById('serverPort').value = server.port;
    document.getElementById('serverUsername').value = server.username;
    document.getElementById('serverPollInterval').value = server.poll_interval || 15;
    document.getElementById('serverTags').value = (server.tags || []).join(', ');
    document.getElementById('serverSudoPassword').value = '';

    const authRadios = document.getElementsByName('authType');
    for (const r of authRadios) {
        if (r.value === server.auth_type) {
            r.checked = true;
            break;
        }
    }

    document.getElementById('modalTitle').innerHTML = `
        <i class="fa-solid fa-pen-to-square text-indigo-400"></i>
        <span>Edit Server: ${escapeHtml(server.name)}</span>
    `;
    document.getElementById('submitServerText').innerText = 'Update Server';
    toggleAuthFields();
}

function closeServerModal() {
    document.getElementById('serverModal').classList.add('hidden');
}

function toggleAuthFields() {
    const authType = document.querySelector('input[name="authType"]:checked')?.value || 'password';
    const passGroup = document.getElementById('passwordFieldGroup');
    const keyGroup = document.getElementById('keyFieldGroup');

    if (authType === 'password') {
        passGroup.classList.remove('hidden');
        keyGroup.classList.add('hidden');
    } else {
        passGroup.classList.add('hidden');
        keyGroup.classList.remove('hidden');
    }
}

function handleKeyFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('serverPrivateKey').value = e.target.result;
        showToast('Private key loaded from file', 'info');
    };
    reader.readAsText(file);
}

// Test SSH Connection before saving
async function testConnection() {
    const host = document.getElementById('serverHost').value.trim();
    const port = parseInt(document.getElementById('serverPort').value, 10) || 22;
    const username = document.getElementById('serverUsername').value.trim();
    const authType = document.querySelector('input[name="authType"]:checked')?.value || 'password';
    const password = document.getElementById('serverPassword').value;
    const privateKey = document.getElementById('serverPrivateKey').value;
    const passphrase = document.getElementById('serverPassphrase').value;

    if (!host || !username) {
        showToast('Please fill in Host and Username first', 'warning');
        return;
    }

    const btn = document.getElementById('btnTestConn');
    const icon = document.getElementById('testConnIcon');
    const resultBox = document.getElementById('testConnResult');

    btn.disabled = true;
    icon.className = 'fa-solid fa-spinner animate-spin text-indigo-400';
    resultBox.classList.add('hidden');

    try {
        const res = await fetch('/api/servers/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                host,
                port,
                username,
                auth_type: authType,
                password: password || null,
                private_key: privateKey || null,
                passphrase: passphrase || null
            })
        });

        const data = await res.json();
        resultBox.classList.remove('hidden');

        if (data.success) {
            resultBox.className = 'p-3 rounded-lg text-xs bg-emerald-950/40 border border-emerald-500/40 text-emerald-300';
            resultBox.innerHTML = `
                <div class="flex items-center gap-2 font-bold mb-1">
                    <i class="fa-solid fa-circle-check text-emerald-400"></i>
                    <span>SSH Connection Succeeded!</span>
                    <span class="ml-auto text-[11px] text-emerald-400/80">${data.latency_ms} ms</span>
                </div>
                <div class="text-[11px] font-mono text-emerald-200/80 bg-black/30 p-2 rounded">${escapeHtml(data.details || 'Remote host acknowledged')}</div>
            `;
        } else {
            resultBox.className = 'p-3 rounded-lg text-xs bg-rose-950/40 border border-rose-500/40 text-rose-300';
            resultBox.innerHTML = `
                <div class="flex items-center gap-2 font-bold mb-1">
                    <i class="fa-solid fa-circle-xmark text-rose-400"></i>
                    <span>SSH Connection Failed</span>
                </div>
                <p class="text-[11px] text-rose-200/80">${escapeHtml(data.message)}</p>
            `;
        }
    } catch (err) {
        resultBox.classList.remove('hidden');
        resultBox.className = 'p-3 rounded-lg text-xs bg-rose-950/40 border border-rose-500/40 text-rose-300';
        resultBox.innerHTML = `
            <div class="font-bold mb-1">Request Error</div>
            <p>${escapeHtml(err.message)}</p>
        `;
    } finally {
        btn.disabled = false;
        icon.className = 'fa-solid fa-plug text-indigo-400';
    }
}

// Save or Update Server
async function saveServer(event) {
    event.preventDefault();

    const serverId = document.getElementById('serverId').value;
    const name = document.getElementById('serverName').value.trim();
    const host = document.getElementById('serverHost').value.trim();
    const port = parseInt(document.getElementById('serverPort').value, 10) || 22;
    const username = document.getElementById('serverUsername').value.trim();
    const pollInterval = parseInt(document.getElementById('serverPollInterval').value, 10) || 15;
    const tags = document.getElementById('serverTags').value.trim();
    const authType = document.querySelector('input[name="authType"]:checked')?.value || 'password';
    const password = document.getElementById('serverPassword').value;
    const privateKey = document.getElementById('serverPrivateKey').value;
    const passphrase = document.getElementById('serverPassphrase').value;
    const sudoPassword = document.getElementById('serverSudoPassword').value;

    const payload = {
        name,
        host,
        port,
        username,
        poll_interval: pollInterval,
        tags,
        auth_type: authType,
    };

    if (password) payload.password = password;
    if (privateKey) payload.private_key = privateKey;
    if (passphrase) payload.passphrase = passphrase;
    if (sudoPassword) payload.sudo_password = sudoPassword;

    const btn = document.getElementById('btnSubmitServer');
    btn.disabled = true;

    try {
        let res;
        if (serverId) {
            // Update
            res = await fetch(`/api/servers/${serverId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } else {
            // Create
            res = await fetch('/api/servers', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        }

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || 'Server request failed');
        }

        showToast(serverId ? 'Server updated successfully' : 'Server added successfully', 'success');
        closeServerModal();
        await fetchAllData();
    } catch (err) {
        showToast('Error saving server: ' + err.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

// Delete Server
async function deleteServer(serverId, serverName) {
    if (!confirm(`Are you sure you want to delete server "${serverName}"? All historical metrics will be removed.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/servers/${serverId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast(`Server "${serverName}" deleted`, 'info');
            await fetchAllData();
        } else {
            const errData = await res.json();
            throw new Error(errData.detail || 'Failed to delete');
        }
    } catch (err) {
        showToast('Error deleting server: ' + err.message, 'error');
    }
}

// ==================== DETAILS & CHARTS MODAL ====================
async function openDetailsModal(serverId) {
    activeDetailServerId = serverId;
    
    // Show cached server data first for instant response
    const cached = allServers.find(s => s.id === serverId);
    if (cached) {
        renderServerDetails(cached);
    }
    document.getElementById('detailsModal').classList.remove('hidden');

    // Fetch fresh server data from API to get full latest metrics (partitions & processes)
    try {
        const res = await fetch(`/api/servers/${serverId}`);
        if (res.ok) {
            const fresh = await res.json();
            renderServerDetails(fresh);
            const idx = allServers.findIndex(s => s.id === serverId);
            if (idx !== -1) allServers[idx] = fresh;
        }
    } catch (e) {
        console.warn('Could not fetch fresh server details:', e);
    }

    await loadServerMetricsCharts(serverId);
}

function closeDetailsModal() {
    activeDetailServerId = null;
    document.getElementById('detailsModal').classList.add('hidden');
}

async function refreshCurrentServerDetails() {
    if (!activeDetailServerId) return;
    const icon = document.getElementById('detailRefreshIcon');
    if (icon) icon.classList.add('animate-spin');

    try {
        const res = await fetch(`/api/servers/${activeDetailServerId}/poll`, { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            if (data.server) {
                renderServerDetails(data.server);
                const idx = allServers.findIndex(s => s.id === activeDetailServerId);
                if (idx !== -1) allServers[idx] = data.server;
            }
        }
        await loadServerMetricsCharts(activeDetailServerId);
        await fetchAllData();
        showToast('Server metrics refreshed', 'success');
    } catch (err) {
        showToast('Refresh error: ' + err.message, 'error');
    } finally {
        if (icon) icon.classList.remove('animate-spin');
    }
}

function renderServerDetails(server) {
    const distro = detectDistro(server.os_name);

    document.getElementById('detailOsIcon').className = `w-10 h-10 rounded-xl flex items-center justify-center text-lg ${distro.badgeClass}`;
    document.getElementById('detailOsIcon').innerHTML = `<i class="${distro.icon}"></i>`;
    document.getElementById('detailServerName').innerText = server.name;
    document.getElementById('detailServerSub').innerText = `${server.username}@${server.host}:${server.port} • Hostname: ${server.hostname || 'unknown'}`;

    document.getElementById('specOsName').innerText = server.os_name || distro.name;
    document.getElementById('specCpu').innerText = `${server.cpu_cores || 1} Cores • ${server.cpu_model || 'Standard'}`;
    
    const ramTotal = server.total_ram_mb ? (server.total_ram_mb > 1024 ? (server.total_ram_mb/1024).toFixed(1) + ' GB RAM' : Math.round(server.total_ram_mb) + ' MB RAM') : 'RAM N/A';
    const diskTotal = server.total_disk_gb ? `${server.total_disk_gb} GB Disk` : 'Disk N/A';
    document.getElementById('specMemDisk').innerText = `${ramTotal} • ${diskTotal}`;
    document.getElementById('specUptime').innerText = server.uptime_str || 'N/A';

    // Render Partitions Table
    const metric = server.latest_metric || {};
    const partitions = metric.partitions || [];
    const partBody = document.getElementById('partitionsTableBody');

    if (partitions.length > 0) {
        partBody.innerHTML = partitions.map(p => `
            <tr>
                <td class="py-2.5 font-bold text-white">${escapeHtml(p.mount)}</td>
                <td class="py-2.5 text-slate-400 font-mono text-[11px]">${escapeHtml(p.filesystem)}</td>
                <td class="py-2.5">${p.used_gb} / ${p.total_gb} GB</td>
                <td class="py-2.5 text-emerald-400">${p.free_gb} GB</td>
                <td class="py-2.5">
                    <div class="flex items-center gap-2">
                        <div class="flex-1 bg-slate-800 h-2 rounded-full overflow-hidden">
                            <div class="${p.percent >= 85 ? 'bg-rose-500' : p.percent >= 65 ? 'bg-amber-500' : 'bg-emerald-500'} h-full rounded-full" style="width: ${p.percent}%"></div>
                        </div>
                        <span class="w-10 text-right font-medium text-[11px]">${p.percent}%</span>
                    </div>
                </td>
            </tr>
        `).join('');
    } else {
        partBody.innerHTML = `<tr><td colspan="5" class="py-3 text-center text-slate-500">No partition data available</td></tr>`;
    }

    // Render Top Processes Table
    const processes = metric.processes || [];
    const procBody = document.getElementById('processesTableBody');

    if (processes.length > 0) {
        procBody.innerHTML = processes.map(proc => `
            <tr>
                <td class="py-2 text-indigo-400">${escapeHtml(proc.pid)}</td>
                <td class="py-2 text-slate-400">${escapeHtml(proc.user)}</td>
                <td class="py-2 font-bold ${proc.cpu > 50 ? 'text-rose-400' : 'text-slate-200'}">${proc.cpu}%</td>
                <td class="py-2">${proc.mem}%</td>
                <td class="py-2 text-slate-300 max-w-xs truncate" title="${escapeHtml(proc.command)}">${escapeHtml(proc.command)}</td>
            </tr>
        `).join('');
    } else {
        procBody.innerHTML = `<tr><td colspan="5" class="py-3 text-center text-slate-500 font-sans">No process data available</td></tr>`;
    }
}

// Chart.js Setup and Data Rendering
async function loadServerMetricsCharts(serverId) {
    try {
        const res = await fetch(`/api/servers/${serverId}/metrics?limit=30`);
        if (!res.ok) return;
        const metrics = await res.json();

        const labels = metrics.map(m => {
            if (!m.timestamp) return '';
            const d = new Date(m.timestamp);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        });

        const cpuData = metrics.map(m => m.cpu_percent);
        const ramData = metrics.map(m => m.ram_percent);

        const latestCpu = cpuData.length ? cpuData[cpuData.length - 1] : 0;
        const latestRam = ramData.length ? ramData[ramData.length - 1] : 0;

        document.getElementById('chartCpuCurrent').innerText = latestCpu + '%';
        document.getElementById('chartRamCurrent').innerText = latestRam + '%';

        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1e293b',
                    titleColor: '#f1f5f9',
                    bodyColor: '#cbd5e1',
                    borderColor: '#334155',
                    borderWidth: 1,
                    padding: 8,
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(51, 65, 85, 0.3)' },
                    ticks: { color: '#64748b', font: { size: 10 } }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(51, 65, 85, 0.3)' },
                    ticks: {
                        color: '#64748b',
                        font: { size: 10 },
                        callback: (v) => v + '%'
                    }
                }
            }
        };

        // Render CPU Chart
        const cpuCtx = document.getElementById('cpuChart').getContext('2d');
        if (cpuChartInstance) cpuChartInstance.destroy();
        cpuChartInstance = new Chart(cpuCtx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'CPU %',
                    data: cpuData,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }]
            },
            options: chartOptions
        });

        // Render RAM Chart
        const ramCtx = document.getElementById('ramChart').getContext('2d');
        if (ramChartInstance) ramChartInstance.destroy();
        ramChartInstance = new Chart(ramCtx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'RAM %',
                    data: ramData,
                    borderColor: '#c084fc',
                    backgroundColor: 'rgba(192, 132, 252, 0.1)',
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }]
            },
            options: chartOptions
        });

    } catch (err) {
        console.error('Error rendering metrics charts:', err);
    }
}

// ==================== REMOTE SSH EXEC / TERMINAL MODAL ====================
function openExecModal(serverId) {
    activeExecServerId = serverId;
    const server = allServers.find(s => s.id === serverId);
    if (!server) return;

    document.getElementById('execServerName').innerText = `SSH Diagnostics: ${server.name} (${server.host})`;
    document.getElementById('execCommandInput').value = 'uptime';
    document.getElementById('terminalOutput').innerHTML = `<span class="text-slate-500">Connected to ${escapeHtml(server.username)}@${escapeHtml(server.host)}:${server.port}\nReady to run command...</span>`;
    document.getElementById('execModal').classList.remove('hidden');
}

function closeExecModal() {
    activeExecServerId = null;
    document.getElementById('execModal').classList.add('hidden');
}

function togglePromptSymbol(isSudo) {
    const sym = document.getElementById('execPromptSymbol');
    const note = document.getElementById('sudoStatusNote');
    if (sym) {
        if (isSudo) {
            sym.innerText = '#';
            sym.className = 'absolute left-3 top-1/2 -translate-y-1/2 text-amber-400 font-mono text-sm font-bold';
            if (note) note.innerText = 'Elevated execution enabled';
        } else {
            sym.innerText = '$';
            sym.className = 'absolute left-3 top-1/2 -translate-y-1/2 text-emerald-400 font-mono text-sm font-bold';
            if (note) note.innerText = 'Standard user execution';
        }
    }
}

const DIAGNOSTIC_PRESETS = {
    uptime: "uptime; cat /proc/loadavg",
    free: "free -h",
    df: "df -h",
    failed_services: "systemctl --failed",
    docker_ps: "docker ps -a 2>/dev/null || echo 'Docker not active'",
    ports: "ss -tulpn | head -n 15",
    count_postgres: "ps -ef | grep postgres | grep -v grep | wc -l",
    kill_trans: "pids=$(ps -ef | grep postgres | grep trans | grep -v grep | awk '{print $2}'); if [ -n \"$pids\" ]; then echo \"$pids\" | xargs -r kill && echo \"Terminated trans PID(s):\" && echo \"$pids\"; else echo \"No postgres trans processes found.\"; fi",
    kill_idle: "pids=$(ps -ef | grep postgres | grep idle | grep -v grep | awk '{print $2}'); if [ -n \"$pids\" ]; then echo \"$pids\" | xargs -r kill && echo \"Terminated idle PID(s):\" && echo \"$pids\"; else echo \"No postgres idle processes found.\"; fi"
};

function runPresetCmd(key, isDangerous = false) {
    const cmd = DIAGNOSTIC_PRESETS[key];
    if (!cmd) return;

    if (isDangerous) {
        if (!confirm(`Warning: Are you sure you want to execute this command on the remote server?\n\n$ ${cmd}`)) {
            document.getElementById('execCommandInput').value = cmd;
            return;
        }
    }

    document.getElementById('execCommandInput').value = cmd;
    runCommand(new Event('submit'));
}

function setExecCmd(cmd) {
    document.getElementById('execCommandInput').value = cmd;
    runCommand(new Event('submit'));
}

async function runCommand(event) {
    if (event) event.preventDefault();
    if (!activeExecServerId) return;

    const cmd = document.getElementById('execCommandInput').value.trim();
    if (!cmd) return;

    const useSudo = document.getElementById('execUseSudo')?.checked || false;
    const promptText = useSudo ? 'sudo #' : '$';
    const promptClass = useSudo ? 'text-amber-400 font-bold' : 'text-emerald-400 font-bold';

    const btn = document.getElementById('btnRunExec');
    const icon = document.getElementById('runExecIcon');
    const outputBox = document.getElementById('terminalOutput');

    btn.disabled = true;
    icon.className = 'fa-solid fa-spinner animate-spin';
    outputBox.innerHTML += `\n<span class="${promptClass}">${promptText} ${escapeHtml(cmd)}</span>\n<span class="text-slate-500">Executing...</span>`;
    outputBox.scrollTop = outputBox.scrollHeight;

    try {
        const res = await fetch(`/api/servers/${activeExecServerId}/exec`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd, use_sudo: useSudo })
        });

        const data = await res.json();
        let formatted = '';
        if (data.stdout) {
            formatted += escapeHtml(data.stdout);
        }
        if (data.stderr) {
            formatted += `\n<span class="text-rose-400">${escapeHtml(data.stderr)}</span>`;
        }
        if (!data.stdout && !data.stderr) {
            formatted += `\n<span class="text-slate-500">(No output, exit code: ${data.exit_code})</span>`;
        }

        outputBox.innerHTML = outputBox.innerHTML.replace('<span class="text-slate-500">Executing...</span>', formatted);
    } catch (err) {
        outputBox.innerHTML += `\n<span class="text-rose-400">Execution request failed: ${escapeHtml(err.message)}</span>`;
    } finally {
        btn.disabled = false;
        icon.className = 'fa-solid fa-play';
        outputBox.scrollTop = outputBox.scrollHeight;
    }
}

function copyTerminalOutput() {
    const text = document.getElementById('terminalOutput').innerText;
    copyToClipboard(text);
    showToast('Terminal output copied to clipboard', 'info');
}

// Utility: Copy to Clipboard
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text);
    } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
    }
}

// Utility: HTML Escape
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
