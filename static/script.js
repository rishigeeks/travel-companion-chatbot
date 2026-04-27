document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const chatMessages = document.getElementById('chatMessages');
    
    // Auth Elements
    const loggedOutView = document.getElementById('loggedOutView');
    const loggedInView = document.getElementById('loggedInView');
    const usernameDisplay = document.getElementById('usernameDisplay');
    const conversationList = document.getElementById('conversationList');
    
    // Modal Elements
    const authModal = document.getElementById('authModal');
    const modalTitle = document.getElementById('modalTitle');
    const authForm = document.getElementById('authForm');
    const authUsername = document.getElementById('authUsername');
    const authPassword = document.getElementById('authPassword');
    const authError = document.getElementById('authError');
    const closeModal = document.getElementById('closeModal');
    
    // Buttons
    const loginBtn = document.getElementById('loginBtn');
    const signupBtn = document.getElementById('signupBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const newChatBtn = document.getElementById('newChatBtn');

    // State
    let currentConversationId = null;
    let authMode = 'login'; // 'login' or 'signup'

    // --- Initialization ---
    checkAuthStatus();

    // --- Auth Logic ---
    async function checkAuthStatus() {
        try {
            const res = await fetch('/api/user');
            const data = await res.json();
            if (data.logged_in) {
                showLoggedIn(data.username);
                loadHistory();
            } else {
                showLoggedOut();
            }
        } catch (e) {
            console.error("Auth check failed");
            showLoggedOut();
        }
    }

    function showLoggedIn(username) {
        loggedOutView.style.display = 'none';
        loggedInView.style.display = 'block';
        usernameDisplay.textContent = username;
    }

    function showLoggedOut() {
        loggedInView.style.display = 'none';
        loggedOutView.style.display = 'block';
        conversationList.innerHTML = '';
        currentConversationId = null;
    }

    loginBtn.onclick = () => openModal('login');
    signupBtn.onclick = () => openModal('signup');
    closeModal.onclick = () => authModal.style.display = 'none';
    
    function openModal(mode) {
        authMode = mode;
        modalTitle.textContent = mode === 'login' ? 'Log In' : 'Sign Up';
        authError.textContent = '';
        authUsername.value = '';
        authPassword.value = '';
        authModal.style.display = 'flex';
    }

    authForm.onsubmit = async (e) => {
        e.preventDefault();
        authError.textContent = '';
        const endpoint = authMode === 'login' ? '/api/login' : '/api/signup';
        
        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: authUsername.value.trim(),
                    password: authPassword.value.trim()
                })
            });
            const data = await res.json();
            
            if (data.success) {
                authModal.style.display = 'none';
                showLoggedIn(data.username);
                loadHistory();
                startNewChat(); // Clear screen
            } else {
                authError.textContent = data.error || 'Authentication failed';
            }
        } catch (e) {
            authError.textContent = 'Network error';
        }
    };

    logoutBtn.onclick = async () => {
        await fetch('/api/logout', { method: 'POST' });
        showLoggedOut();
        startNewChat();
    };

    // --- Chat History Logic ---
    async function loadHistory() {
        try {
            const res = await fetch('/api/conversations');
            const data = await res.json();
            
            conversationList.innerHTML = '';
            data.forEach(conv => {
                const li = document.createElement('li');
                li.className = 'history-item';
                li.innerHTML = `<i class="fa-solid fa-message" style="margin-right: 8px;"></i> ${conv.title}`;
                if (conv.id === currentConversationId) li.classList.add('active');
                
                li.onclick = () => loadConversation(conv.id);
                conversationList.appendChild(li);
            });
        } catch (e) {
            console.error("Failed to load history");
        }
    }

    async function loadConversation(id) {
        currentConversationId = id;
        loadHistory(); // Re-render to show active state
        
        try {
            const res = await fetch(`/api/conversations/${id}`);
            const messages = await res.json();
            
            chatMessages.innerHTML = ''; // Clear current
            messages.forEach(m => appendMessage(m.role, m.content));
        } catch (e) {
            console.error("Failed to load conversation");
        }
    }

    newChatBtn.onclick = () => startNewChat();

    function startNewChat() {
        currentConversationId = null;
        chatMessages.innerHTML = `
            <div class="message bot-message">
                <div class="message-inner">
                    <div class="avatar"><i class="fa-solid fa-plane"></i></div>
                    <div class="message-content">
                        Hello! I'm Tripster. I have direct access to live data and my own travel knowledge to help you find restaurants, events, and tips anywhere. How can I help you today?
                    </div>
                </div>
            </div>
        `;
        if (loggedInView.style.display === 'block') loadHistory(); // Reset active state
    }

    // --- Main Chat Logic ---
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        userInput.value = '';
        appendMessage('user', message);
        const indicator = showTypingIndicator();

        try {
            const payload = { message: message };
            if (currentConversationId) payload.conversation_id = currentConversationId;

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            indicator.remove();

            if (data.error) {
                appendMessage('bot', `Error: ${data.error}`);
            } else {
                appendMessage('bot', data.response);
                // If it was a new chat and we're logged in, update the current ID and reload history
                if (data.conversation_id && currentConversationId !== data.conversation_id) {
                    currentConversationId = data.conversation_id;
                    loadHistory();
                }
            }
        } catch (error) {
            indicator.remove();
            appendMessage('bot', `Sorry, I encountered an error: ${error.message}`);
        }
    });

    function appendMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;

        const innerDiv = document.createElement('div');
        innerDiv.className = 'message-inner';

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar';
        avatarDiv.innerHTML = role === 'bot' ? '<i class="fa-solid fa-plane"></i>' : '<i class="fa-solid fa-user"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (role === 'bot') {
            contentDiv.innerHTML = marked.parse(text);
        } else {
            contentDiv.textContent = text;
        }

        innerDiv.appendChild(avatarDiv);
        innerDiv.appendChild(contentDiv);
        messageDiv.appendChild(innerDiv);
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTypingIndicator() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        
        const innerDiv = document.createElement('div');
        innerDiv.className = 'message-inner';

        innerDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-plane"></i></div>
            <div class="typing-indicator" style="padding: 16px;">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
        `;
        
        messageDiv.appendChild(innerDiv);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return messageDiv;
    }
});
