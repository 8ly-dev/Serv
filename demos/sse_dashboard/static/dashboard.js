/**
 * SSE Dashboard JavaScript
 * Handles real-time data visualization and Server-Sent Events
 */

class SSEDashboard {
    constructor() {
        this.eventSource = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        
        // Chart data storage
        this.cpuHistory = [];
        this.networkHistory = { in: [], out: [] };
        this.maxHistoryLength = 30;
        
        // DOM elements
        this.elements = {
            connectionStatus: document.getElementById('connectionStatus'),
            statusDot: document.querySelector('.status-dot'),
            statusText: document.querySelector('.status-text'),
            
            // CPU elements
            cpuValue: document.getElementById('cpuValue'),
            cpuChart: document.getElementById('cpuChart'),
            
            // Memory elements
            memoryProgress: document.getElementById('memoryProgress'),
            memoryText: document.getElementById('memoryText'),
            memoryDetails: document.getElementById('memoryDetails'),
            
            // Network elements
            networkIn: document.getElementById('networkIn'),
            networkOut: document.getElementById('networkOut'),
            networkChart: document.getElementById('networkChart'),
            
            // Disk elements
            diskPercentage: document.getElementById('diskPercentage'),
            diskDetails: document.getElementById('diskDetails'),
            diskProgress: document.getElementById('diskProgress'),
            
            // System elements
            temperature: document.getElementById('temperature'),
            uptime: document.getElementById('uptime'),
            connections: document.getElementById('connections'),
            
            // Alerts
            alertsContainer: document.getElementById('alertsContainer')
        };
        
        // Initialize charts
        this.initializeCharts();
        
        // Start SSE connection
        this.connect();
    }
    
    connect() {
        try {
            this.updateConnectionStatus('connecting', 'Connecting...');
            
            // Use the combined events stream for simplicity
            this.eventSource = new EventSource('/api/events/all');
            
            this.eventSource.onopen = () => {
                console.log('SSE connection opened');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('connected', 'Connected');
            };
            
            this.eventSource.addEventListener('metrics', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('Received metrics data:', data);
                    this.updateMetrics(data);
                } catch (error) {
                    console.error('Error parsing metrics data:', error);
                }
            });
            
            this.eventSource.addEventListener('alert', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('Received alert data:', data);
                    this.addAlert(data);
                } catch (error) {
                    console.error('Error parsing alert data:', error);
                }
            });
            
            this.eventSource.addEventListener('connected', (event) => {
                console.log('SSE stream connected:', event.data);
            });
            
            this.eventSource.addEventListener('heartbeat', (event) => {
                console.log('SSE heartbeat received');
            });
            
            this.eventSource.onerror = (error) => {
                console.error('SSE connection error:', error);
                this.isConnected = false;
                this.updateConnectionStatus('disconnected', 'Connection lost');
                this.scheduleReconnect();
            };
            
        } catch (error) {
            console.error('Failed to establish SSE connection:', error);
            this.updateConnectionStatus('disconnected', 'Connection failed');
            this.scheduleReconnect();
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.updateConnectionStatus('disconnected', 'Connection failed - max retries reached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        this.updateConnectionStatus('connecting', `Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            if (this.eventSource) {
                this.eventSource.close();
            }
            this.connect();
        }, delay);
    }
    
    updateConnectionStatus(status, message) {
        this.elements.statusDot.className = `status-dot ${status}`;
        this.elements.statusText.textContent = message;
    }
    
    handleEvent(data) {
        // Handle different event types
        if (data.timestamp) {
            // This is a metrics update
            this.updateMetrics(data);
        } else if (data.level && data.message) {
            // This is an alert
            this.addAlert(data);
        }
    }
    
    updateMetrics(data) {
        // Update CPU
        if (data.cpu) {
            this.elements.cpuValue.textContent = `${data.cpu.usage}%`;
            this.updateCPUChart(data.cpu);
        }
        
        // Update Memory
        if (data.memory) {
            const percentage = data.memory.usage;
            const used = data.memory.used;
            const total = data.memory.total;
            
            this.elements.memoryProgress.style.width = `${percentage}%`;
            this.elements.memoryText.textContent = `${percentage.toFixed(1)}% (${used.toFixed(0)} MB)`;
            this.elements.memoryDetails.textContent = `Total: ${total.toLocaleString()} MB`;
        }
        
        // Update Network
        if (data.network) {
            this.elements.networkIn.textContent = `${data.network.in.toFixed(1)} KB/s`;
            this.elements.networkOut.textContent = `${data.network.out.toFixed(1)} KB/s`;
            this.updateNetworkChart(data.network);
        }
        
        // Update Disk
        if (data.disk) {
            const percentage = data.disk.usage;
            const free = data.disk.free;
            const total = data.disk.total;
            
            this.elements.diskPercentage.textContent = `${percentage.toFixed(1)}%`;
            this.elements.diskDetails.textContent = `${free.toFixed(1)} GB free of ${total} GB`;
            this.elements.diskProgress.style.width = `${percentage}%`;
            
            // Change color based on usage
            if (percentage > 90) {
                this.elements.diskProgress.style.background = 'linear-gradient(90deg, #e74c3c, #c0392b)';
            } else if (percentage > 75) {
                this.elements.diskProgress.style.background = 'linear-gradient(90deg, #f39c12, #e67e22)';
            } else {
                this.elements.diskProgress.style.background = 'linear-gradient(90deg, #27ae60, #2ecc71)';
            }
        }
        
        // Update System Stats
        if (data.temperature !== undefined) {
            this.elements.temperature.textContent = `${data.temperature.toFixed(1)}°C`;
        }
        
        if (data.uptime !== undefined) {
            this.elements.uptime.textContent = this.formatUptime(data.uptime);
        }
        
        if (data.connections !== undefined) {
            this.elements.connections.textContent = data.connections;
        }
    }
    
    addAlert(data) {
        const alertsContainer = this.elements.alertsContainer;
        
        // Remove the loading message if it exists
        const loadingAlert = alertsContainer.querySelector('.alert-item');
        if (loadingAlert && loadingAlert.textContent.includes('Loading')) {
            loadingAlert.remove();
        }
        
        // Create new alert element
        const alertElement = document.createElement('div');
        alertElement.className = `alert-item ${data.level} new`;
        
        const time = new Date(data.timestamp).toLocaleTimeString();
        
        alertElement.innerHTML = `
            <span class="alert-time">${time}</span>
            <span class="alert-message">${data.message}</span>
        `;
        
        // Add to top of alerts container
        alertsContainer.insertBefore(alertElement, alertsContainer.firstChild);
        
        // Remove animation class after animation completes
        setTimeout(() => {
            alertElement.classList.remove('new');
        }, 500);
        
        // Keep only last 10 alerts
        const alerts = alertsContainer.querySelectorAll('.alert-item');
        if (alerts.length > 10) {
            alerts[alerts.length - 1].remove();
        }
    }
    
    initializeCharts() {
        // Initialize CPU chart
        this.cpuChart = new SimpleChart(this.elements.cpuChart, {
            color: '#3498db',
            backgroundColor: 'rgba(52, 152, 219, 0.1)',
            lineWidth: 2
        });
        
        // Initialize Network chart
        this.networkChart = new SimpleChart(this.elements.networkChart, {
            color: '#27ae60',
            backgroundColor: 'rgba(39, 174, 96, 0.1)',
            lineWidth: 2,
            multiLine: true,
            colors: ['#27ae60', '#e74c3c']
        });
    }
    
    updateCPUChart(cpuData) {
        if (cpuData.history) {
            this.cpuChart.updateData(cpuData.history);
        }
    }
    
    updateNetworkChart(networkData) {
        // Add current values to history
        this.networkHistory.in.push(networkData.in);
        this.networkHistory.out.push(networkData.out);
        
        // Keep history at max length
        if (this.networkHistory.in.length > this.maxHistoryLength) {
            this.networkHistory.in.shift();
            this.networkHistory.out.shift();
        }
        
        this.networkChart.updateData([this.networkHistory.in, this.networkHistory.out]);
    }
    
    formatUptime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    }
}

/**
 * Simple Chart Class for rendering basic line charts
 */
class SimpleChart {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.options = {
            color: options.color || '#3498db',
            backgroundColor: options.backgroundColor || 'rgba(52, 152, 219, 0.1)',
            lineWidth: options.lineWidth || 2,
            multiLine: options.multiLine || false,
            colors: options.colors || ['#3498db', '#e74c3c']
        };
        this.data = [];
        
        // Set canvas size
        this.resize();
        
        // Handle resize
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * devicePixelRatio;
        this.canvas.height = rect.height * devicePixelRatio;
        this.ctx.scale(devicePixelRatio, devicePixelRatio);
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.redraw();
    }
    
    updateData(newData) {
        this.data = Array.isArray(newData[0]) ? newData : [newData];
        this.redraw();
    }
    
    redraw() {
        if (!this.data.length || !this.data[0].length) return;
        
        const width = this.canvas.width / devicePixelRatio;
        const height = this.canvas.height / devicePixelRatio;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, width, height);
        
        // Draw background
        this.ctx.fillStyle = this.options.backgroundColor;
        this.ctx.fillRect(0, 0, width, height);
        
        // Draw data lines
        this.data.forEach((lineData, lineIndex) => {
            if (!lineData.length) return;
            
            const color = this.options.multiLine 
                ? this.options.colors[lineIndex] || this.options.color
                : this.options.color;
            
            this.drawLine(lineData, width, height, color);
        });
    }
    
    drawLine(data, width, height, color) {
        if (data.length < 2) return;
        
        const maxValue = Math.max(...data);
        const minValue = Math.min(...data);
        const range = maxValue - minValue || 1;
        
        const stepX = width / (data.length - 1);
        
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = this.options.lineWidth;
        this.ctx.beginPath();
        
        data.forEach((value, index) => {
            const x = index * stepX;
            const y = height - ((value - minValue) / range) * height;
            
            if (index === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        });
        
        this.ctx.stroke();
        
        // Draw filled area
        this.ctx.lineTo(width, height);
        this.ctx.lineTo(0, height);
        this.ctx.closePath();
        this.ctx.fillStyle = color.replace('rgb', 'rgba').replace(')', ', 0.1)');
        this.ctx.fill();
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new SSEDashboard();
});

// Handle page visibility changes to reconnect when tab becomes active
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && window.dashboard && !window.dashboard.isConnected) {
        console.log('Tab became active, attempting to reconnect...');
        window.dashboard.connect();
    }
}); 