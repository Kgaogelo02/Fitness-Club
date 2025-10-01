// Simple chart initialization
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded - initializing charts and revenue progress bars');
    
    // Set progress bar widths for revenue trend
    const progressFills = document.querySelectorAll('.progress-fill');
    progressFills.forEach(fill => {
        const width = fill.getAttribute('data-width');
        if (width) {
            fill.style.width = width + '%';
        }
    });
    
    // Initialize today's overview counts
    document.getElementById('satisfactionScore').textContent = document.getElementById('satisfactionScore').getAttribute('data-score') + '/5';
    document.getElementById('expiringCount').textContent = document.getElementById('expiringCount').getAttribute('data-count') || '0';
    document.getElementById('paymentsDueCount').textContent = document.getElementById('paymentsDueCount').getAttribute('data-count') || '0';
    document.getElementById('classesTodayCount').textContent = document.getElementById('classesTodayCount').getAttribute('data-count') || '0';
    
    // Get data from HTML elements for membership chart
    function getActiveMemberships() {
        const activeCard = document.querySelector('.card:nth-child(2) p');
        return activeCard ? parseInt(activeCard.textContent) : 0;
    }
    
    function getTotalMembers() {
        const totalCard = document.querySelector('.card:nth-child(1) p');
        return totalCard ? parseInt(totalCard.textContent) : 0;
    }

    // Membership Chart (Doughnut) only - payment chart removed
    const membershipCtx = document.getElementById('membershipChart');
    if (membershipCtx) {
        console.log('Found membership chart canvas');
        const activeMembers = getActiveMemberships();
        const totalMembers = getTotalMembers();
        const expiredMembers = Math.max(totalMembers - activeMembers, 0);
        
        new Chart(membershipCtx, {
            type: 'doughnut',
            data: {
                labels: ['Active Members', 'Expired Members'],
                datasets: [{
                    data: [activeMembers, expiredMembers],
                    backgroundColor: ['#00b09b', '#ff6b6b'],
                    borderWidth: 0,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = Math.round((value / total) * 100);
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '60%'
            }
        });
    } else {
        console.log('Membership chart canvas NOT found');
    }
});

// Quick Member Search Function
function quickSearchMember() {
    const searchTerm = document.getElementById('quickSearch').value.trim();
    const resultsDiv = document.getElementById('quickSearchResults');
    
    if (!searchTerm) {
        resultsDiv.innerHTML = '<p style="color: #666;">Please enter a member name to search</p>';
        return;
    }
    
    // Show loading
    resultsDiv.innerHTML = '<p>Searching...</p>';
    
    // Simple AJAX search
    fetch(`/api/search_members?q=${encodeURIComponent(searchTerm)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            displaySearchResults(data);
        })
        .catch(error => {
            console.error('Search error:', error);
            resultsDiv.innerHTML = '<p style="color: red;">Search error. Please try again.</p>';
        });
}

// Handle Enter key in search input
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('quickSearch');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                quickSearchMember();
            }
        });
    }
});

// Display search results
function displaySearchResults(members) {
    const resultsDiv = document.getElementById('quickSearchResults');
    
    if (members.length === 0) {
        resultsDiv.innerHTML = '<p style="color: #666;">No members found</p>';
        return;
    }
    
    let html = '';
    members.forEach(member => {
        const status = getMemberStatus(member.expiry_date);
        html += `
            <div class="search-result-item">
                <div class="member-info">
                    <strong>${member.name}</strong>
                    <div style="font-size: 14px; color: #666;">
                        ${member.membership_type} • Expires: ${member.expiry_date}
                        <span class="member-status-badge ${status.class}">${status.text}</span>
                    </div>
                </div>
                <div class="member-actions">
                    <button onclick="quickCheckin(${member.id})" class="btn-edit" style="padding: 6px 12px;">Check-in</button>
                    <button onclick="viewMember(${member.id})" class="btn-edit" style="padding: 6px 12px;">View</button>
                    <button onclick="takePayment(${member.id})" class="btn-edit" style="padding: 6px 12px;">Payment</button>
                </div>
            </div>
        `;
    });
    
    resultsDiv.innerHTML = html;
}

// Get member status
function getMemberStatus(expiryDate) {
    const today = new Date();
    const expiry = new Date(expiryDate);
    const daysUntilExpiry = Math.ceil((expiry - today) / (1000 * 60 * 60 * 24));
    
    if (daysUntilExpiry < 0) {
        return { class: 'status-expired', text: 'EXPIRED' };
    } else if (daysUntilExpiry <= 7) {
        return { class: 'status-expiring', text: 'EXPIRING SOON' };
    } else {
        return { class: 'status-active', text: 'ACTIVE' };
    }
}

// Quick action functions
function quickCheckin(memberId) {
    window.location.href = `/checkin/${memberId}`;
}

function viewMember(memberId) {
    window.location.href = `/members`;
}

function takePayment(memberId) {
    window.location.href = `/add_payment_form`;
}

// SMS Reminder Functions for SA time
function loadMembersNeedingReminders() {
    const reminderList = document.getElementById('reminderList');
    
    fetch('/api/members_needing_reminders')
        .then(response => response.json())
        .then(members => {
            if (members.length === 0) {
                reminderList.innerHTML = '<p>No members need reminders right now! 🎉</p>';
            } else {
                let html = '<h4>Members Needing SMS Reminders:</h4>';
                members.forEach(member => {
                    const daysLeft = member.days_until_expiry;
                    let status = '';
                    let urgency = '';
                    
                    if (daysLeft === 0) {
                        status = 'EXPIRES TODAY!';
                        urgency = 'style="color: #dc2626; font-weight: bold;"';
                    } else if (daysLeft < 0) {
                        status = `EXPIRED ${Math.abs(daysLeft)} DAYS AGO!`;
                        urgency = 'style="color: #dc2626; font-weight: bold;"';
                    } else if (daysLeft === 1) {
                        status = 'Expires TOMORROW!';
                        urgency = 'style="color: #d97706; font-weight: bold;"';
                    } else {
                        status = `Expires in ${daysLeft} days`;
                        urgency = 'style="color: #d97706;"';
                    }
                    
                    html += `
                        <div class="reminder-member-item">
                            <div>
                                <strong>${member.name}</strong>
                                <div style="font-size: 14px; color: #666;">
                                    ${member.membership_type} • ${member.phone}
                                </div>
                                <div ${urgency}>
                                    ${status} (${member.expiry_date})
                                </div>
                            </div>
                            <div class="reminder-actions">
                                <button onclick="sendSingleReminder(${member.id})" class="btn-edit">
                                    📱 Send SMS
                                </button>
                            </div>
                        </div>
                    `;
                });
                reminderList.innerHTML = html;
            }
            reminderList.style.display = 'block';
        })
        .catch(error => {
            console.error('Error loading reminders:', error);
            reminderList.innerHTML = '<p style="color: red;">Error loading reminders</p>';
        });
}

function sendSingleReminder(memberId) {
    showNotification('Sending SMS reminder...', 'info');
    
    fetch(`/send_reminder/${memberId}`)
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showNotification(`📱 SMS sent to ${result.member_name} (${result.days_until_expiry} days until expiry)`, 'success');
                // Reload the list after 2 seconds
                setTimeout(loadMembersNeedingReminders, 2000);
            } else {
                showNotification(`Failed: ${result.message}`, 'error');
            }
        })
        .catch(error => {
            console.error('Error sending reminder:', error);
            showNotification('Error sending SMS', 'error');
        });
}

function sendTestReminder() {
    // Find first member with phone number for testing
    fetch('/api/members_with_phones')
        .then(response => response.json())
        .then(members => {
            if (members.length > 0) {
                sendSingleReminder(members[0].id);
            } else {
                showNotification('No members with phone numbers found. Add phone numbers first.', 'error');
            }
        })
        .catch(error => {
            console.error('Error finding test member:', error);
            showNotification('Error finding test member', 'error');
        });
}

// Notification system
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    
    // Add styles if not already present
    if (!document.querySelector('#notification-styles')) {
        const styles = document.createElement('style');
        styles.id = 'notification-styles';
        styles.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 10px;
                color: white;
                font-weight: 600;
                z-index: 10000;
                display: flex;
                align-items: center;
                gap: 10px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                animation: slideIn 0.3s ease;
            }
            .notification.success { background: linear-gradient(45deg, #00b09b, #96c93d); }
            .notification.error { background: linear-gradient(45deg, #ff6b6b, #ffa8a8); }
            .notification.info { background: linear-gradient(45deg, #667eea, #764ba2); }
            .notification button {
                background: none;
                border: none;
                color: white;
                font-size: 18px;
                cursor: pointer;
                padding: 0;
                width: 20px;
                height: 20px;
            }
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(styles);
    }
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Form validation
function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], select[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.style.borderColor = '#ff6b6b';
            input.style.animation = 'shake 0.5s ease';
            isValid = false;
            
            setTimeout(() => {
                input.style.animation = '';
            }, 500);
        } else {
            input.style.borderColor = '';
        }
    });
    
    return isValid;
}

// Add shake animation for form validation
if (!document.querySelector('#form-styles')) {
    const styles = document.createElement('style');
    styles.id = 'form-styles';
    styles.textContent = `
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-5px); }
            75% { transform: translateX(5px); }
        }
    `;
    document.head.appendChild(styles);
}

// Table search functionality
function initializeTableSearch() {
    const searchInputs = document.querySelectorAll('input[type="search"]');
    
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const table = this.closest('.main-content').querySelector('table');
            const filter = this.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            });
        });
    });
}

// Auto-expire memberships check
function checkExpiredMemberships() {
    const today = new Date().toISOString().split('T')[0];
    const expiryCells = document.querySelectorAll('table td:nth-child(3)');
    
    expiryCells.forEach(cell => {
        const expiryDate = cell.textContent.trim();
        if (expiryDate && expiryDate < today) {
            cell.style.color = '#ff6b6b';
            cell.style.fontWeight = 'bold';
        }
    });
}

// Revenue trend animations
function animateRevenueTrend() {
    const revenueItems = document.querySelectorAll('.revenue-item');
    revenueItems.forEach((item, index) => {
        item.style.opacity = '0';
        item.style.transform = 'translateX(-20px)';
        
        setTimeout(() => {
            item.style.transition = 'all 0.5s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateX(0)';
        }, index * 100);
    });
}

// Quick search animations
function animateQuickSearch() {
    const searchResults = document.querySelectorAll('.search-result-item');
    searchResults.forEach((item, index) => {
        item.style.opacity = '0';
        item.style.transform = 'translateY(-10px)';
        
        setTimeout(() => {
            item.style.transition = 'all 0.3s ease';
            item.style.opacity = '1';
            item.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize search functionality
    initializeTableSearch();
    
    // Check for expired memberships
    checkExpiredMemberships();
    
    // Add form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
                showNotification('Please fill in all required fields', 'error');
            }
        });
    });
    
    // Animate revenue trend
    animateRevenueTrend();
    
    // Demo notification
    setTimeout(() => {
        if (window.location.pathname === '/dashboard') {
            showNotification('Welcome to Fitness Club Dashboard!', 'info');
        }
    }, 1000);
    
    // Add enter key support for quick search
    const quickSearchInput = document.getElementById('quickSearch');
    if (quickSearchInput) {
        quickSearchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                quickSearchMember();
            }
        });
    }
});

// Make functions globally available
window.showNotification = showNotification;
window.validateForm = validateForm;
window.quickSearchMember = quickSearchMember;
window.quickCheckin = quickCheckin;
window.viewMember = viewMember;
window.takePayment = takePayment;
window.loadMembersNeedingReminders = loadMembersNeedingReminders;
window.sendSingleReminder = sendSingleReminder;
window.sendTestReminder = sendTestReminder;