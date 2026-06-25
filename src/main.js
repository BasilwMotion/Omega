/**
 * Omega Frontend - AI Agent Interface
 * Communicates with the backend API at /api/execute
 */

const goalInput = document.getElementById('goalInput');
const submitBtn = document.getElementById('submitBtn');
const statusOutput = document.getElementById('statusOutput');
const logOutput = document.getElementById('logOutput');

let isExecuting = false;

submitBtn.addEventListener('click', executeGoal);
goalInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) executeGoal();
});

async function executeGoal() {
    const goal = goalInput.value.trim();
    
    if (!goal) {
        statusOutput.innerHTML = '<p class="error">⚠️ Please enter a goal.</p>';
        return;
    }
    
    if (isExecuting) return;
    
    isExecuting = true;
    submitBtn.disabled = true;
    logOutput.innerHTML = '';
    statusOutput.innerHTML = '<p class="loading">▓ Executing goal...</p>';
    
    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal })
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update status
        statusOutput.innerHTML = `
            <div>
                <p class="success">✓ Execution Complete</p>
                <p style="margin-top: 8px; color: #e0e0e0;">Iterations: ${data.iterations || 0}</p>
            </div>
        `;
        
        // Display logs
        if (data.log && data.log.length > 0) {
            data.log.forEach((entry, idx) => {
                const logEl = document.createElement('div');
                logEl.className = 'log-entry';
                
                if (entry.type === 'iteration') {
                    logEl.classList.add('iteration');
                    logEl.innerHTML = `<strong>[Iteration ${entry.iteration}]</strong> Action: ${entry.action}`;
                } else if (entry.type === 'observation') {
                    logEl.classList.add('observation');
                    logEl.innerHTML = `${entry.content}`;
                } else if (entry.type === 'error') {
                    logEl.classList.add('error');
                    logEl.innerHTML = `<strong>⚠️ Error:</strong> ${entry.content}`;
                } else if (entry.type === 'success') {
                    logEl.classList.add('success');
                    logEl.innerHTML = `<strong>✓ Success:</strong> ${entry.content}`;
                }
                
                logOutput.appendChild(logEl);
            });
            logOutput.scrollTop = logOutput.scrollHeight;
        }
        
    } catch (error) {
        statusOutput.innerHTML = `<p class="error">✗ Error: ${error.message}</p>`;
        const logEl = document.createElement('div');
        logEl.className = 'log-entry error';
        logEl.innerHTML = `<strong>Execution Failed:</strong> ${error.message}`;
        logOutput.appendChild(logEl);
    } finally {
        isExecuting = false;
        submitBtn.disabled = false;
    }
}

// Auto-focus input on load
window.addEventListener('load', () => {
    goalInput.focus();
});