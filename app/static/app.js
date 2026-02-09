// Custom JavaScript for RCW Processing Suite

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('RCW Processing Suite initialized');

    // Add any custom JavaScript here
});

// Utility functions
const RCW = {
    // Format currency
    formatCurrency: function(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(value);
    },

    // Show notification
    showNotification: function(message, type = 'info') {
        console.log(`[${type.toUpperCase()}] ${message}`);
        // You can add toast notification logic here
    },

    // Handle errors
    handleError: function(error) {
        console.error('Error:', error);
        this.showNotification('An error occurred. Please try again.', 'error');
    }
};

// Export for use in other scripts
window.RCW = RCW;