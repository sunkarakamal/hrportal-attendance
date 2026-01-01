document.addEventListener('DOMContentLoaded', () => {
    // Show splash screen
    setTimeout(() => {
        document.getElementById('splash-screen').style.display = 'none';
        document.querySelector('.container').style.display = 'block';
    }, 3000);

    // Show modal if redirected with ?show_modal=true
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('show_modal') === 'true') {
        document.getElementById('adminModal').style.display = 'flex';
    }

    // Form validation
    const loginForm = document.getElementById('loginForm');
    loginForm.addEventListener('submit', function(e) {
        const email = document.querySelector('input[name="email"]').value;
        const password = document.querySelector('input[name="password"]').value;

        if (!email || !password) {
            e.preventDefault();
            alert('Please fill in all fields.');
            return;
        }

        const submitButton = loginForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.textContent = 'Logging in...';
    });
});

// Send choice to backend
function chooseDashboard(role) {
    fetch('/choose_dashboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'role=' + role
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = data.redirect;
        }
    })
    .catch(err => console.error(err));
}
