const API = 'http://localhost:8000';

function switchTab(tab, el) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');

    document.getElementById('clientView').style.display = 'none';
    document.getElementById('freelancerView').style.display = 'none';
    document.getElementById('leaderboardView').style.display = 'none';
    document.getElementById('historyView').style.display = 'none';

    if (tab === 'client') {
        document.getElementById('clientView').style.display = 'grid';
    } else if (tab === 'freelancer') {
        document.getElementById('freelancerView').style.display = 'grid';
        loadOpenJobs();
    } else if (tab === 'leaderboard') {
        document.getElementById('leaderboardView').style.display = 'flex';
        loadLeaderboard();
    } else if (tab === 'history') {
        document.getElementById('historyView').style.display = 'flex';
    }
}

async function postJob() {
    const desc = document.getElementById('jobDesc').value.trim();
    const amount = document.getElementById('jobAmount').value.trim();
    const deadline = document.getElementById('jobDeadline').value.trim();
    const client = document.getElementById('jobClient').value.trim() || 'web_user';
    const successMsg = document.getElementById('successMsg');
    const errorMsg = document.getElementById('errorMsg');

    successMsg.style.display = 'none';
    errorMsg.style.display = 'none';

    if (!desc || !amount || !deadline) {
        errorMsg.style.display = 'block';
        errorMsg.textContent = 'Please fill in all fields!';
        return;
    }

    try {
        const resp = await fetch(`${API}/api/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description: desc, amount, deadline, client })
        });
        const data = await resp.json();

        if (data.success) {
            successMsg.style.display = 'block';
            successMsg.textContent = `✅ Job created! ID: ${data.job_id} — Share with freelancer: /submitwork ${data.job_id}`;
            document.getElementById('jobDesc').value = '';
            document.getElementById('jobAmount').value = '';
            document.getElementById('jobDeadline').value = '';
            loadJobs();
        }
    } catch (err) {
        errorMsg.style.display = 'block';
        errorMsg.textContent = `Error: ${err.message}`;
    }
}

async function submitWork() {
    const jobId = document.getElementById('submitJobId').value.trim().toUpperCase();
    const work = document.getElementById('submitWork').value.trim();
    const freelancer = document.getElementById('freelancerName').value.trim() || 'anonymous';
    const successMsg = document.getElementById('submitSuccessMsg');
    const errorMsg = document.getElementById('submitErrorMsg');
    const resultBox = document.getElementById('resultBox');

    successMsg.style.display = 'none';
    errorMsg.style.display = 'none';
    resultBox.style.display = 'none';

    if (!jobId || !work) {
        errorMsg.style.display = 'block';
        errorMsg.textContent = 'Please fill in Job ID and your work!';
        return;
    }

    successMsg.style.display = 'block';
    successMsg.textContent = '🤖 AI is evaluating your work...';

    try {
        const resp = await fetch(`${API}/api/jobs/${jobId}/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ work, freelancer })
        });
        const data = await resp.json();

        if (data.error) {
            successMsg.style.display = 'none';
            errorMsg.style.display = 'block';
            errorMsg.textContent = `❌ ${data.error}`;
            return;
        }

        successMsg.style.display = 'none';
        resultBox.style.display = 'block';

        document.getElementById('resultScore').textContent = data.score;
        document.getElementById('resultScoreFill').style.width = `${data.score * 10}%`;

        const verdictEmoji = { APPROVE: '✅', PARTIAL: '⚡', REJECT: '❌' };
        document.getElementById('resultVerdict').textContent =
            `${verdictEmoji[data.verdict] || ''} ${data.verdict}`;
        document.getElementById('resultReasoning').textContent = data.reasoning;
        document.getElementById('resultPayment').textContent =
            `💰 ${data.payment_released} USDC ${data.verdict === 'REJECT' ? 'refunded to client' : 'released!'}`;

        loadJobs();
        loadOpenJobs();

    } catch (err) {
        successMsg.style.display = 'none';
        errorMsg.style.display = 'block';
        errorMsg.textContent = `Error: ${err.message}`;
    }
}

async function raiseDispute() {
    const jobId = document.getElementById('disputeJobId').value.trim().toUpperCase();
    const reason = document.getElementById('disputeReason').value.trim();
    const raisedBy = document.getElementById('disputeUser').value.trim() || 'anonymous';
    const successMsg = document.getElementById('disputeSuccessMsg');
    const errorMsg = document.getElementById('disputeErrorMsg');
    const resultBox = document.getElementById('disputeResultBox');

    successMsg.style.display = 'none';
    errorMsg.style.display = 'none';
    resultBox.style.display = 'none';

    if (!jobId || !reason) {
        errorMsg.style.display = 'block';
        errorMsg.textContent = 'Please fill in Job ID and reason!';
        return;
    }

    successMsg.style.display = 'block';
    successMsg.textContent = '⚖️ AI is re-evaluating your dispute...';

    try {
        const resp = await fetch(`${API}/api/jobs/${jobId}/dispute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason, raised_by: raisedBy })
        });
        const data = await resp.json();

        if (data.error) {
            successMsg.style.display = 'none';
            errorMsg.style.display = 'block';
            errorMsg.textContent = `❌ ${data.error}`;
            return;
        }

        successMsg.style.display = 'none';
        resultBox.style.display = 'block';

        const outcomeEmoji = data.dispute_outcome === 'UPHELD' ? '✅' : '❌';
        resultBox.innerHTML = `
            <div class="result-card">
                <div class="result-header">⚖️ Dispute Result</div>
                <div style="font-size:20px; font-weight:800; color: ${data.dispute_outcome === 'UPHELD' ? '#00ff88' : '#ff4444'}; margin:12px 0;">
                    ${outcomeEmoji} ${data.dispute_outcome}
                </div>
                <div class="result-reasoning">${data.dispute_explanation}</div>
                <div style="margin-top:12px; font-size:13px; color:#889;">
                    New Score: ${data.new_score}/10 | New Verdict: ${data.new_verdict}
                </div>
                <div class="result-payment">💰 ${data.payment_released} USDC settled</div>
            </div>
        `;

        loadJobs();

    } catch (err) {
        successMsg.style.display = 'none';
        errorMsg.style.display = 'block';
        errorMsg.textContent = `Error: ${err.message}`;
    }
}

async function loadLeaderboard() {
    try {
        const resp = await fetch(`${API}/api/leaderboard`);
        const data = await resp.json();
        const list = document.getElementById('leaderboardList');
        const leaderboard = data.leaderboard;

        if (!leaderboard || leaderboard.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">🏆</div>
                    <p>No freelancers yet</p>
                    <p class="empty-sub">Complete jobs to appear here!</p>
                </div>`;
            return;
        }

        list.innerHTML = leaderboard.map(entry => `
            <div class="job-item" style="display:flex; align-items:center; gap:16px;">
                <div style="font-size:28px; font-weight:900; color:#00d4ff; width:40px;">#${entry.rank}</div>
                <div style="flex:1;">
                    <div style="font-size:15px; font-weight:700; color:#fff;">@${entry.username}</div>
                    <div style="font-size:12px; color:#556; margin-top:2px;">${entry.level}</div>
                    <div class="score-bar" style="margin-top:8px;">
                        <div class="score-fill" style="width:${entry.avg_score * 10}%"></div>
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:22px; font-weight:800; color:#00ff88;">${entry.avg_score}</div>
                    <div style="font-size:11px; color:#556;">/10 avg</div>
                    <div style="font-size:11px; color:#445; margin-top:4px;">${entry.total_jobs} jobs</div>
                </div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Leaderboard error:', err);
    }
}

async function loadHistory() {
    const username = document.getElementById('historyUsername').value.trim();
    if (!username) return;

    try {
        const resp = await fetch(`${API}/api/history/${username}`);
        const data = await resp.json();
        const jobs = data.history;
        const list = document.getElementById('historyList');

        if (!jobs || Object.keys(jobs).length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📭</div>
                    <p>No history found for @${username}</p>
                </div>`;
            return;
        }

        list.innerHTML = Object.entries(jobs).reverse().map(([id, job]) => `
            <div class="job-item">
                <div class="job-header">
                    <span class="job-id">JOB #${id}</span>
                    <span class="status ${job.status}">${job.status}</span>
                </div>
                <div class="job-desc">${job.description}</div>
                <div class="job-footer">
                    <span class="job-amount">${job.amount} USDC</span>
                    <span class="job-meta">@${job.client}</span>
                </div>
                ${job.score ? `
                    <div class="score-bar" style="margin-top:10px;">
                        <div class="score-fill" style="width:${job.score * 10}%"></div>
                    </div>
                    <div class="score-label">AI Score: ${job.score}/10 | ${job.verdict}</div>
                ` : ''}
                ${job.dispute ? `
                    <div class="verdict-box" style="border-color:#ff6b3533; background:#ff6b3508;">
                        ⚖️ Disputed — ${job.dispute.outcome}: ${job.dispute.explanation}
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (err) {
        console.error('History error:', err);
    }
}

async function loadStats() {
    try {
        const resp = await fetch(`${API}/api/stats`);
        const data = await resp.json();
        document.getElementById('totalJobs').textContent = data.total;
        document.getElementById('openJobs').textContent = data.open;
        document.getElementById('completedJobs').textContent = data.completed;
        document.getElementById('disputedJobs').textContent = data.disputed || 0;
        document.getElementById('totalUSDC').textContent = data.total_usdc;
    } catch (err) {
        console.error('Stats error:', err);
    }
}

async function loadJobs() {
    try {
        const resp = await fetch(`${API}/api/jobs`);
        const data = await resp.json();
        const jobs = data.jobs;
        const list = document.getElementById('jobsList');

        await loadStats();

        if (Object.keys(jobs).length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📭</div>
                    <p>No jobs yet</p>
                    <p class="empty-sub">Post a job above or use the Telegram bot</p>
                </div>`;
            return;
        }

        list.innerHTML = Object.entries(jobs).reverse().map(([id, job]) => `
            <div class="job-item">
                <div class="job-header">
                    <span class="job-id">JOB #${id}</span>
                    <span class="status ${job.status}">${job.status}</span>
                </div>
                <div class="job-desc">${job.description}</div>
                <div class="job-footer">
                    <span class="job-amount">${job.amount} USDC</span>
                    <span class="job-meta">@${job.client} • ${job.deadline}h</span>
                </div>
                ${job.score ? `
                    <div class="score-bar">
                        <div class="score-fill" style="width:${job.score * 10}%"></div>
                    </div>
                    <div class="score-label">AI Score: ${job.score}/10 | ${job.verdict}</div>
                ` : ''}
                ${job.reasoning ? `
                    <div class="verdict-box">🏛 ${job.reasoning}</div>
                ` : ''}
                ${job.dispute ? `
                    <div class="verdict-box" style="border-color:#ff6b3533; background:#ff6b3508; margin-top:6px;">
                        ⚖️ Dispute ${job.dispute.outcome}: ${job.dispute.explanation}
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (err) {
        console.error('Jobs error:', err);
    }
}

async function loadOpenJobs() {
    try {
        const resp = await fetch(`${API}/api/jobs`);
        const data = await resp.json();
        const jobs = data.jobs;
        const list = document.getElementById('openJobsList');
        if (!list) return;

        const openJobs = Object.entries(jobs).filter(([_, j]) => j.status === 'open');

        if (openJobs.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📭</div>
                    <p>No open jobs</p>
                    <p class="empty-sub">Check back soon!</p>
                </div>`;
            return;
        }

        list.innerHTML = openJobs.map(([id, job]) => `
            <div class="job-item" onclick="fillJobId('${id}')" style="cursor:pointer;">
                <div class="job-header">
                    <span class="job-id">JOB #${id}</span>
                    <span class="status open">OPEN</span>
                </div>
                <div class="job-desc">${job.description}</div>
                <div class="job-footer">
                    <span class="job-amount">${job.amount} USDC</span>
                    <span class="job-meta">${job.deadline}h deadline</span>
                </div>
                <div style="font-size:11px; color:#00d4ff; margin-top:8px;">👆 Click to apply</div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Open jobs error:', err);
    }
}

function fillJobId(jobId) {
    document.getElementById('submitJobId').value = jobId;
    document.getElementById('submitWork').focus();
}

// Auto refresh every 3 seconds
loadJobs();
setInterval(loadJobs, 3000);