function showFeedback(element, message, kind) {
    element.textContent = message;
    element.className = `feedback ${kind}`;
}

document.getElementById('login-form').addEventListener('submit', async event => {
    event.preventDefault();
    const feedback = document.getElementById('login-feedback');
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: document.getElementById('login-username').value.trim(),
                password: document.getElementById('login-password').value
            })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Invalid credentials');
        sessionStorage.setItem('access_token', data.access_token);
        sessionStorage.setItem('current_user', JSON.stringify(data.user));
        window.location.replace('/');
    } catch (error) {
        showFeedback(feedback, error.message, 'error');
    }
});

document.getElementById('register-form').addEventListener('submit', async event => {
    event.preventDefault();
    const feedback = document.getElementById('register-feedback');
    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: document.getElementById('register-username').value.trim(),
                email: document.getElementById('register-email').value.trim(),
                password: document.getElementById('register-password').value
            })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Registration failed');
        document.getElementById('login-username').value = document.getElementById('register-username').value.trim();
        document.getElementById('login-password').value = document.getElementById('register-password').value;
        showFeedback(feedback, 'Account created. Sign in above.', 'success');
    } catch (error) {
        showFeedback(feedback, error.message, 'error');
    }
});
