from flask import Flask, render_template_string, jsonify
import json
from datetime import datetime
import os
import time
import threading

app = Flask(__name__)

# Import database jika ada
try:
    from database import database
    DB_ENABLED = True
    print("✅ Database module loaded for web dashboard")
except ImportError:
    DB_ENABLED = False
    print("⚠️ Database module not found, running in basic mode")

# HTML Template dengan TP
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Signal Dashboard (with TP)</title>
    <style>
        :root {
            --primary: #4361ee;
            --secondary: #3a0ca3;
            --success: #4cc9f0;
            --danger: #f72585;
            --warning: #f8961e;
            --dark: #1a1a2e;
            --light: #f8f9fa;
            --gray: #6c757d;
            --profit: #38a169;
            --loss: #e53e3e;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', 'Roboto', sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 30px 40px;
            border-radius: 20px;
            margin-bottom: 30px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 8px solid var(--primary);
        }
        
        .header-content h1 {
            color: var(--dark);
            font-size: 2.8em;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .header-content p {
            color: var(--gray);
            font-size: 1.2em;
        }
        
        .status-badge {
            background: var(--success);
            color: white;
            padding: 8px 20px;
            border-radius: 50px;
            font-weight: bold;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-badge::before {
            content: '';
            width: 10px;
            height: 10px;
            background: white;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.08);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .stat-card:hover {
            transform: translateY(-10px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 5px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
        }
        
        .stat-icon {
            font-size: 2.5em;
            margin-bottom: 15px;
            color: var(--primary);
        }
        
        .stat-title {
            color: var(--gray);
            font-size: 1em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        
        .stat-value {
            font-size: 3em;
            font-weight: 800;
            color: var(--dark);
            line-height: 1;
        }
        
        .stat-change {
            font-size: 0.9em;
            padding: 5px 12px;
            border-radius: 20px;
            display: inline-block;
            margin-top: 10px;
            font-weight: bold;
        }
        
        .positive { background: rgba(76, 201, 240, 0.1); color: var(--success); }
        .negative { background: rgba(247, 37, 133, 0.1); color: var(--danger); }
        
        .signal-section {
            background: white;
            padding: 40px;
            border-radius: 20px;
            margin-bottom: 30px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
        }
        
        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .section-header h2 {
            color: var(--dark);
            font-size: 1.8em;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .signal-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        
        .signal-item {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            transition: transform 0.3s ease;
        }
        
        .signal-item:hover {
            transform: scale(1.05);
        }
        
        .signal-label {
            display: block;
            color: var(--gray);
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        
        .signal-value {
            font-size: 2em;
            font-weight: bold;
            color: var(--dark);
        }
        
        .signal-buy { color: var(--profit) !important; }
        .signal-sell { color: var(--loss) !important; }
        
        .no-signal {
            text-align: center;
            padding: 60px 40px;
            color: var(--gray);
        }
        
        .no-signal h3 {
            font-size: 1.8em;
            margin-bottom: 15px;
            color: var(--dark);
        }
        
        .no-signal p {
            font-size: 1.1em;
            opacity: 0.8;
        }
        
        .log-section {
            background: var(--dark);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            margin-bottom: 30px;
        }
        
        .log-content {
            background: #2d3748;
            padding: 25px;
            border-radius: 12px;
            height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.95em;
            line-height: 1.6;
            margin-bottom: 20px;
        }
        
        .log-line {
            padding: 12px 15px;
            border-bottom: 1px solid #4a5568;
            color: #e2e8f0;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .log-line:last-child {
            border-bottom: none;
        }
        
        .log-timestamp {
            color: var(--success);
            font-weight: bold;
            min-width: 180px;
        }
        
        .log-message {
            flex: 1;
        }
        
        .log-info { color: #90cdf4; }
        .log-success { color: #9ae6b4; }
        .log-warning { color: #faf089; }
        .log-error { color: #fc8181; }
        
        .buttons {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 15px 30px;
            border: none;
            border-radius: 12px;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 180px;
            justify-content: center;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(67, 97, 238, 0.3);
        }
        
        .btn-secondary {
            background: white;
            color: var(--dark);
            border: 2px solid #e2e8f0;
        }
        
        .btn-secondary:hover {
            background: #f8f9fa;
            border-color: var(--primary);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, var(--danger), #b5179e);
            color: white;
        }
        
        .btn-danger:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(247, 37, 133, 0.3);
        }
        
        .footer {
            text-align: center;
            padding: 30px;
            color: white;
            font-size: 0.9em;
            opacity: 0.9;
        }
        
        .refresh-info {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: rgba(255, 255, 255, 0.1);
            padding: 10px 20px;
            border-radius: 50px;
            margin-top: 15px;
        }
        
        .signal-indicator {
            display: inline-block;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 10px;
            animation: blink 1.5s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        .signal-active { background: var(--success); }
        .signal-inactive { background: var(--gray); }
        
        .risk-reward {
            background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
            padding: 20px;
            border-radius: 12px;
            margin-top: 20px;
            text-align: center;
        }
        
        .risk-reward h3 {
            color: var(--dark);
            margin-bottom: 10px;
        }
        
        .rr-ratio {
            font-size: 2.5em;
            font-weight: bold;
            color: var(--dark);
        }
        
        .rr-label {
            font-size: 0.9em;
            color: var(--gray);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                text-align: center;
                gap: 20px;
            }
            
            .header-content h1 {
                font-size: 2em;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .signal-details {
                grid-template-columns: 1fr;
            }
            
            .buttons {
                flex-direction: column;
            }
            
            .btn {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-content">
                <h1>
                    <span>📈 Trading Signal Dashboard (with TP)</span>
                    <span class="status-badge" id="systemStatus">LIVE</span>
                </h1>
                <p>Real-time monitoring system | Auto-refresh every 5 seconds</p>
                <div class="refresh-info">
                    <span>🔄 Last update: <span id="lastUpdate">--:--:--</span></span>
                    <span>⏱️ Next refresh in: <span id="refreshCountdown">5s</span></span>
                </div>
            </div>
            <div>
                <span class="signal-indicator signal-active" id="signalIndicator"></span>
                <span id="signalStatus">Signal System Active</span>
            </div>
        </div>
        
        <!-- Statistics Grid -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-title">Today's Signals</div>
                <div class="stat-value" id="todaySignals">0</div>
                <div class="stat-change positive" id="todayChange">+0 today</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">⚡</div>
                <div class="stat-title">Active Signal</div>
                <div class="stat-value" id="activeSignal">NO</div>
                <div class="stat-change" id="signalStatusText">No active signal</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-title">Connected Clients</div>
                <div class="stat-value" id="connectedClients">0</div>
                <div class="stat-change positive" id="clientsChange">+0 connected</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon">🚀</div>
                <div class="stat-title">Total Signals</div>
                <div class="stat-value" id="totalSignals">0</div>
                <div class="stat-change positive" id="totalChange">All time</div>
            </div>
        </div>
        
        <!-- Current Signal Section -->
        <div class="signal-section">
            <div class="section-header">
                <h2><span>📡</span> Current Trading Signal (with TP)</h2>
                <div>
                    <span style="color: var(--gray);">Server Time: </span>
                    <span id="serverTime" style="font-weight: bold;">--:--:--</span>
                </div>
            </div>
            
            <div id="currentSignal">
                <div class="no-signal">
                    <h3>📭 No Active Signal</h3>
                    <p>Waiting for admin to send a trading signal...</p>
                    <p style="margin-top: 20px; font-size: 0.9em; opacity: 0.6;">
                        Signals will appear here automatically when available
                    </p>
                </div>
            </div>
            
            <!-- Risk/Reward Section -->
            <div id="riskRewardSection" style="display: none;">
                <div class="risk-reward">
                    <h3>📊 Risk/Reward Analysis</h3>
                    <div class="rr-ratio" id="rrRatio">1:0.00</div>
                    <div class="rr-label" id="rrLabel">Risk/Reward Ratio</div>
                </div>
            </div>
            
            <div class="buttons">
                <button class="btn btn-primary" onclick="refreshData(true)">
                    <span>🔄</span> Force Refresh
                </button>
                <button class="btn btn-secondary" onclick="testConnection()">
                    <span>🔗</span> Test Connection
                </button>
                <button class="btn btn-danger" onclick="clearLogDisplay()">
                    <span>🗑️</span> Clear Log Display
                </button>
            </div>
        </div>
        
        <!-- Activity Log Section -->
        <div class="log-section">
            <div class="section-header" style="border-bottom-color: #4a5568;">
                <h2 style="color: white;"><span>📝</span> Activity Log</h2>
                <div style="color: #a0aec0;">
                    Showing last <span id="logCount">0</span> entries
                </div>
            </div>
            
            <div class="log-content" id="activityLog">
                <div class="log-line">
                    <span class="log-timestamp">Initializing...</span>
                    <span class="log-message">Loading dashboard data</span>
                </div>
            </div>
            
            <div class="buttons">
                <button class="btn btn-primary" onclick="scrollLogToBottom()">
                    <span>⬇️</span> Scroll to Bottom
                </button>
                <button class="btn btn-secondary" onclick="exportLog()">
                    <span>💾</span> Export Log
                </button>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p>Trading Signal System v2.0 (with TP) | Database: <span id="dbStatus">Loading...</span></p>
            <p>© 2024 Trading Signal Dashboard | All trades are executed at your own risk</p>
        </div>
    </div>
    
    <script>
        // Global variables
        let refreshInterval;
        let countdown = 5;
        let lastStats = {};
        
        // Update server time
        function updateServerTime() {
            const now = new Date();
            document.getElementById('serverTime').textContent = 
                now.toLocaleTimeString('en-US', {hour12: false});
        }
        
        // Update countdown
        function updateCountdown() {
            countdown--;
            if (countdown <= 0) {
                countdown = 5;
                refreshData();
            }
            document.getElementById('refreshCountdown').textContent = `${countdown}s`;
        }
        
        // Format timestamp
        function formatTime(timestamp) {
            if (!timestamp) return '--:--:--';
            try {
                const date = new Date(timestamp);
                return date.toLocaleTimeString('en-US', {hour12: false});
            } catch {
                return timestamp;
            }
        }
        
        // Calculate risk/reward ratio
        function calculateRR(signal) {
            if (!signal || !signal.price || !signal.sl || !signal.tp || !signal.type) {
                return null;
            }
            
            const price = parseFloat(signal.price);
            const sl = parseFloat(signal.sl);
            const tp = parseFloat(signal.tp);
            const type = signal.type.toLowerCase();
            
            let risk, reward, ratio;
            
            if (type === 'buy') {
                risk = price - sl;
                reward = tp - price;
            } else {
                risk = sl - price;
                reward = price - tp;
            }
            
            if (risk > 0) {
                ratio = (reward / risk).toFixed(2);
                return {
                    ratio: `1:${ratio}`,
                    risk: risk.toFixed(4),
                    reward: reward.toFixed(4),
                    type: type
                };
            }
            
            return null;
        }
        
        // Refresh dashboard data
        async function refreshData(force = false) {
            try {
                // Update last update time
                const now = new Date();
                document.getElementById('lastUpdate').textContent = 
                    now.toLocaleTimeString('en-US', {hour12: false});
                
                // Reset countdown
                countdown = 5;
                
                // Show loading state
                document.getElementById('systemStatus').textContent = 'LOADING...';
                
                // Fetch statistics
                const statsResponse = await fetch('/api/stats');
                const statsData = await statsResponse.json();
                
                // Update statistics
                document.getElementById('todaySignals').textContent = statsData.today_signals || 0;
                document.getElementById('totalSignals').textContent = statsData.total_signals || 0;
                document.getElementById('connectedClients').textContent = statsData.connected_clients || 0;
                
                // Calculate changes
                if (lastStats.today_signals !== undefined) {
                    const todayChange = (statsData.today_signals || 0) - (lastStats.today_signals || 0);
                    if (todayChange > 0) {
                        document.getElementById('todayChange').textContent = `+${todayChange} today`;
                        document.getElementById('todayChange').className = 'stat-change positive';
                    } else if (todayChange < 0) {
                        document.getElementById('todayChange').textContent = `${todayChange} today`;
                        document.getElementById('todayChange').className = 'stat-change negative';
                    }
                }
                
                // Update active signal status
                const hasActiveSignal = statsData.current_signal !== null;
                document.getElementById('activeSignal').textContent = hasActiveSignal ? 'YES' : 'NO';
                document.getElementById('signalStatusText').textContent = 
                    hasActiveSignal ? 'Signal active' : 'No active signal';
                document.getElementById('signalStatusText').className = 
                    hasActiveSignal ? 'stat-change positive' : 'stat-change';
                
                // Update signal indicator
                const indicator = document.getElementById('signalIndicator');
                if (hasActiveSignal) {
                    indicator.className = 'signal-indicator signal-active';
                    indicator.style.animation = 'blink 1.5s infinite';
                } else {
                    indicator.className = 'signal-indicator signal-inactive';
                    indicator.style.animation = 'none';
                }
                
                // Update current signal display
                const signalDiv = document.getElementById('currentSignal');
                const rrSection = document.getElementById('riskRewardSection');
                
                if (statsData.current_signal) {
                    const s = statsData.current_signal;
                    signalDiv.innerHTML = `
                        <div class="signal-details">
                            <div class="signal-item">
                                <span class="signal-label">Symbol</span>
                                <div class="signal-value">${s.symbol || 'N/A'}</div>
                            </div>
                            <div class="signal-item">
                                <span class="signal-label">Type</span>
                                <div class="signal-value ${s.type || ''}">
                                    ${(s.type || '').toUpperCase()}
                                </div>
                            </div>
                            <div class="signal-item">
                                <span class="signal-label">Entry Price</span>
                                <div class="signal-value">${s.price || 'N/A'}</div>
                            </div>
                            <div class="signal-item">
                                <span class="signal-label">Stop Loss</span>
                                <div class="signal-value">${s.sl || 'N/A'}</div>
                            </div>
                            <div class="signal-item">
                                <span class="signal-label">Take Profit</span>
                                <div class="signal-value">${s.tp || 'N/A'}</div>
                            </div>
                            <div class="signal-item">
                                <span class="signal-label">Signal ID</span>
                                <div class="signal-value">${s.signal_id || 'N/A'}</div>
                            </div>
                            <div class="signal-item">
                                <span class="signal-label">Time</span>
                                <div class="signal-value">${formatTime(s.timestamp)}</div>
                            </div>
                        </div>
                    `;
                    
                    // Calculate and show risk/reward
                    const rr = calculateRR(s);
                    if (rr) {
                        rrSection.style.display = 'block';
                        document.getElementById('rrRatio').textContent = rr.ratio;
                        document.getElementById('rrLabel').innerHTML = 
                            `Risk/Reward Ratio | Risk: ${rr.risk} | Reward: ${rr.reward}`;
                    } else {
                        rrSection.style.display = 'none';
                    }
                    
                } else {
                    signalDiv.innerHTML = `
                        <div class="no-signal">
                            <h3>📭 No Active Signal</h3>
                            <p>Waiting for admin to send a trading signal...</p>
                            <p style="margin-top: 20px; font-size: 0.9em; opacity: 0.6;">
                                Last signal: ${statsData.last_signal_time || 'Never'}
                            </p>
                        </div>
                    `;
                    rrSection.style.display = 'none';
                }
                
                // Fetch activity log
                const logResponse = await fetch('/api/signals');
                const logData = await logResponse.json();
                
                // Update activity log
                const logContent = document.getElementById('activityLog');
                const logCount = document.getElementById('logCount');
                
                if (logData.signals && logData.signals.length > 0) {
                    let html = '';
                    // Show latest 50 entries
                    logData.signals.slice(-50).reverse().forEach(line => {
                        // Parse log line
                        let logClass = 'log-info';
                        let message = line;
                        
                        if (line.includes('ERROR') || line.includes('FAILED')) {
                            logClass = 'log-error';
                        } else if (line.includes('SIGNAL') || line.includes('SUCCESS')) {
                            logClass = 'log-success';
                        } else if (line.includes('WARNING') || line.includes('⚠️')) {
                            logClass = 'log-warning';
                        }
                        
                        // Extract timestamp if present
                        const timestampMatch = line.match(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/);
                        const timestamp = timestampMatch ? timestampMatch[0] : formatTime(new Date());
                        
                        // Remove timestamp from message for cleaner display
                        message = line.replace(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*-\s*/, '');
                        
                        html += `
                            <div class="log-line">
                                <span class="log-timestamp">${timestamp}</span>
                                <span class="log-message ${logClass}">${message}</span>
                            </div>
                        `;
                    });
                    
                    logContent.innerHTML = html;
                    logCount.textContent = Math.min(logData.signals.length, 50);
                    
                    // Auto scroll to bottom if not at top
                    if (!force) {
                        const isAtBottom = logContent.scrollHeight - logContent.clientHeight <= logContent.scrollTop + 50;
                        if (isAtBottom) {
                            logContent.scrollTop = logContent.scrollHeight;
                        }
                    }
                } else {
                    logContent.innerHTML = `
                        <div class="log-line">
                            <span class="log-timestamp">${formatTime(new Date())}</span>
                            <span class="log-message log-info">No activity yet. Waiting for signals...</span>
                        </div>
                    `;
                    logCount.textContent = '0';
                }
                
                // Update database status
                document.getElementById('dbStatus').textContent = 
                    statsData.database_enabled ? 'Enabled' : 'Disabled';
                document.getElementById('dbStatus').style.color = 
                    statsData.database_enabled ? '#4cc9f0' : '#f72585';
                
                // Update system status
                document.getElementById('systemStatus').textContent = 'LIVE';
                document.getElementById('systemStatus').style.background = 
                    statsData.system_online ? 'linear-gradient(135deg, #4cc9f0, #4361ee)' : '#f72585';
                
                // Save current stats for next comparison
                lastStats = statsData;
                
            } catch (error) {
                console.error('Error refreshing data:', error);
                document.getElementById('systemStatus').textContent = 'ERROR';
                document.getElementById('systemStatus').style.background = '#f72585';
                
                // Show error in log
                const logContent = document.getElementById('activityLog');
                logContent.innerHTML = `
                    <div class="log-line">
                        <span class="log-timestamp">${formatTime(new Date())}</span>
                        <span class="log-message log-error">Error loading data: ${error.message}</span>
                    </div>
                `;
            }
        }
        
        // Test connection
        async function testConnection() {
            try {
                const response = await fetch('/api/test');
                const data = await response.json();
                alert(`Connection test: ${data.status}\nMessage: ${data.message}\nDatabase: ${data.database}`);
            } catch (error) {
                alert(`Connection test failed: ${error.message}`);
            }
        }
        
        // Clear log display
        function clearLogDisplay() {
            if (confirm('Clear log display? (This does not delete actual log files)')) {
                const logContent = document.getElementById('activityLog');
                logContent.innerHTML = `
                    <div class="log-line">
                        <span class="log-timestamp">${formatTime(new Date())}</span>
                        <span class="log-message log-info">Log display cleared. New activity will appear here.</span>
                    </div>
                `;
            }
        }
        
        // Scroll log to bottom
        function scrollLogToBottom() {
            const logContent = document.getElementById('activityLog');
            logContent.scrollTop = logContent.scrollHeight;
        }
        
        // Export log
        function exportLog() {
            const logContent = document.getElementById('activityLog');
            const logText = Array.from(logContent.children)
                .map(line => line.textContent)
                .join('\n');
            
            const blob = new Blob([logText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `trading-log-${new Date().toISOString().slice(0,10)}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            alert('Log exported successfully!');
        }
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            // Start timers
            setInterval(updateServerTime, 1000);
            setInterval(updateCountdown, 1000);
            
            // Initial data load
            refreshData(true);
            
            // Set up auto-refresh every 5 seconds
            refreshInterval = setInterval(() => refreshData(), 5000);
            
            // Initial updates
            updateServerTime();
        });
        
        // Clean up on page unload
        window.addEventListener('beforeunload', function() {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
        });
    </script>
</body>
</html>
'''

# Data storage untuk dashboard
class DashboardData:
    def __init__(self):
        self.last_update = datetime.now()
        self.last_signal_time = None
    
    def get_stats(self):
        """Get statistics from database or log file"""
        stats = {
            'total_signals': 0,
            'today_signals': 0,
            'active_signals': 0,
            'connected_clients': 0,
            'current_signal': None,
            'last_signal_time': self.last_signal_time,
            'database_enabled': DB_ENABLED,
            'system_online': True,
            'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            if DB_ENABLED:
                # Get stats from database
                db_stats = database.get_statistics()
                stats.update({
                    'total_signals': db_stats.get('total_signals', 0),
                    'today_signals': db_stats.get('today_signals', 0),
                    'active_signals': db_stats.get('active_signals', 0),
                    'buy_sell_ratio': db_stats.get('buy_sell_ratio', {}),
                    'performance': db_stats.get('performance', {})
                })
                
                # Get connected clients
                stats['connected_clients'] = database.get_connected_clients()
                
                # Get active signal
                active_signal = database.get_active_signal()
                if active_signal:
                    stats['current_signal'] = {
                        'symbol': active_signal.get('symbol'),
                        'type': active_signal.get('type'),
                        'price': active_signal.get('price'),
                        'sl': active_signal.get('sl'),
                        'tp': active_signal.get('tp'),
                        'timestamp': active_signal.get('timestamp'),
                        'signal_id': active_signal.get('id')
                    }
                    self.last_signal_time = active_signal.get('timestamp')
            
            else:
                # Fallback: read from log file
                if os.path.exists('signals.log'):
                    with open('signals.log', 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    today = datetime.now().strftime('%Y-%m-%d')
                    today_signals = sum(1 for line in lines if 'SIGNAL_CREATED' in line and today in line)
                    
                    stats.update({
                        'total_signals': len(lines),
                        'today_signals': today_signals
                    })
                    
                    # Try to find last signal
                    for line in reversed(lines[-20:]):
                        if 'SIGNAL_CREATED' in line:
                            try:
                                import re
                                # Extract basic info
                                stats['current_signal'] = {
                                    'symbol': 'UNKNOWN',
                                    'type': 'buy',
                                    'price': '0',
                                    'sl': '0',
                                    'tp': '0',
                                    'timestamp': line.split(' - ')[0] if ' - ' in line else datetime.now().isoformat()
                                }
                                self.last_signal_time = line.split(' - ')[0] if ' - ' in line else None
                            except:
                                pass
                            break
        
        except Exception as e:
            print(f"Error getting stats: {e}")
            stats['system_online'] = False
        
        return stats
    
    def get_signals(self):
        """Get signal log entries"""
        try:
            if DB_ENABLED:
                # Get from database history
                history = database.get_signal_history(limit=100)
                lines = []
                for signal in history:
                    line = f"{signal.get('timestamp')} - SIGNAL - {signal.get('symbol')} {signal.get('type')} at {signal.get('price')}, SL: {signal.get('sl')}, TP: {signal.get('tp')}"
                    lines.append(line)
                return lines
            else:
                # Fallback to log file
                if os.path.exists('signals.log'):
                    with open('signals.log', 'r', encoding='utf-8') as f:
                        return f.readlines()[-100:]  # Last 100 lines
        except Exception as e:
            print(f"Error getting signals: {e}")
        
        return []

dashboard_data = DashboardData()

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/stats')
def api_stats():
    return jsonify(dashboard_data.get_stats())

@app.route('/api/signals')
def api_signals():
    return jsonify({'signals': dashboard_data.get_signals()})

@app.route('/api/test')
def api_test():
    """Test endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Dashboard API is working',
        'time': datetime.now().isoformat(),
        'database': 'enabled' if DB_ENABLED else 'disabled'
    })

@app.route('/api/recent_signals')
def api_recent_signals():
    """Get recent signals for display"""
    try:
        if DB_ENABLED:
            signals = database.get_signal_history(limit=20)
            return jsonify({'signals': signals})
    except Exception as e:
        print(f"Error getting recent signals: {e}")
    
    return jsonify({'signals': []})

def background_updater():
    """Background thread untuk update data - CLOUD OPTIMIZED"""
    print("🔄 Background updater started...")
    while True:
        try:
            # Update dashboard data periodically
            time.sleep(10)  # Lebih lama untuk mengurangi load di cloud
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"⚠️ Background updater error: {e}")
            time.sleep(30)  # Tunggu lebih lama jika error

if __name__ == '__main__':
    # Start background thread
    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()
    
    # === PERBAIKAN UNTUK CLOUD DEPLOYMENT ===
    # Gunakan environment variable untuk port dan host
    port = int(os.environ.get('DASHBOARD_PORT', 5000))
    host = os.environ.get('DASHBOARD_HOST', '0.0.0.0')
    
    # Jalankan web server
    print("=" * 60)
    print("🚀 TRADING SIGNAL WEB DASHBOARD (with TP) - CLOUD READY")
    print("=" * 60)
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 URL: http://{host}:{port}")
    print(f"📊 Database: {'Enabled ✅' if DB_ENABLED else 'Disabled ⚠️'}")
    print(f"🔧 Environment: {'CLOUD' if os.environ.get('RENDER') or os.environ.get('GAE_ENV') else 'LOCAL'}")
    print("=" * 60)
    print("\n📢 Dashboard running...")
    print("⚡ Press Ctrl+C to stop\n")
    
    app.run(debug=False, host=host, port=port, use_reloader=False)