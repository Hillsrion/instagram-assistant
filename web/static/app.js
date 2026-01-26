/**
 * Instagram Conversations Assistant - Frontend Application
 */

// ============================================================
// State
// ============================================================

const state = {
    conversations: [],
    currentConversationId: null,
    currentSources: [],
    isLoading: false,
    systemReady: false
};

// ============================================================
// DOM Elements
// ============================================================

const elements = {
    // Sidebar
    sidebar: document.getElementById('sidebar'),
    newChatBtn: document.getElementById('newChatBtn'),
    conversationsList: document.getElementById('conversationsList'),
    statusIndicator: document.getElementById('statusIndicator'),

    // Header
    menuToggle: document.getElementById('menuToggle'),
    chatTitle: document.getElementById('chatTitle'),
    filtersToggle: document.getElementById('filtersToggle'),

    // Filters
    filtersPanel: document.getElementById('filtersPanel'),
    participantFilter: document.getElementById('participantFilter'),
    yearFilter: document.getElementById('yearFilter'),
    dateStart: document.getElementById('dateStart'),
    dateEnd: document.getElementById('dateEnd'),
    useReranking: document.getElementById('useReranking'),
    useHybrid: document.getElementById('useHybrid'),
    expandContext: document.getElementById('expandContext'),

    // Chat
    chatMessages: document.getElementById('chatMessages'),
    welcomeMessage: document.getElementById('welcomeMessage'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),

    // Sources
    sourcesPanel: document.getElementById('sourcesPanel'),
    sourcesContent: document.getElementById('sourcesContent'),
    closeSourcesBtn: document.getElementById('closeSourcesBtn'),

    // Modal
    deleteModal: document.getElementById('deleteModal'),
    cancelDelete: document.getElementById('cancelDelete'),
    confirmDelete: document.getElementById('confirmDelete')
};

// ============================================================
// API
// ============================================================

const api = {
    async getStatus() {
        const res = await fetch('/api/status');
        return res.json();
    },

    async getConversations() {
        const res = await fetch('/api/conversations');
        return res.json();
    },

    async createConversation(title = null) {
        const res = await fetch('/api/conversations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title })
        });
        return res.json();
    },

    async getConversation(id) {
        const res = await fetch(`/api/conversations/${id}`);
        if (!res.ok) throw new Error('Conversation not found');
        return res.json();
    },

    async deleteConversation(id) {
        const res = await fetch(`/api/conversations/${id}`, { method: 'DELETE' });
        return res.ok;
    },

    async getParticipants() {
        const res = await fetch('/api/participants');
        return res.json();
    },

    async sendMessage(data) {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return res.json();
    },

    streamMessage(data, callbacks) {
        const { onChunk, onSources, onDone, onError, onConversationId } = callbacks;

        fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        }).then(response => {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function processLine(line) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        switch (data.type) {
                            case 'conversation_id':
                                onConversationId?.(data.id);
                                break;
                            case 'sources':
                                onSources?.(data.sources);
                                break;
                            case 'chunk':
                                onChunk?.(data.content);
                                break;
                            case 'done':
                                onDone?.();
                                break;
                            case 'error':
                                onError?.(data.message);
                                break;
                        }
                    } catch (e) {
                        console.error('Parse error:', e);
                    }
                }
            }

            function read() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        if (buffer) processLine(buffer);
                        return;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (const line of lines) {
                        if (line.trim()) processLine(line);
                    }

                    read();
                }).catch(onError);
            }

            read();
        }).catch(onError);
    }
};

// ============================================================
// UI Rendering
// ============================================================

function renderConversationsList() {
    const html = state.conversations.map(conv => `
        <div class="conversation-item ${conv.id === state.currentConversationId ? 'active' : ''}"
             data-id="${conv.id}">
            <div class="conv-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
            </div>
            <div class="conv-info">
                <div class="conv-title">${escapeHtml(conv.title)}</div>
                <div class="conv-meta">${conv.message_count} messages</div>
            </div>
            <div class="conv-actions">
                <button class="delete-conv-btn" data-id="${conv.id}" title="Supprimer">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');

    elements.conversationsList.innerHTML = html || '<p style="padding: 16px; color: var(--text-tertiary); text-align: center;">Aucune conversation</p>';

    // Add click handlers
    elements.conversationsList.querySelectorAll('.conversation-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (!e.target.closest('.delete-conv-btn')) {
                loadConversation(item.dataset.id);
            }
        });
    });

    elements.conversationsList.querySelectorAll('.delete-conv-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            showDeleteModal(btn.dataset.id);
        });
    });
}

function renderMessages(messages) {
    if (!messages || messages.length === 0) {
        elements.welcomeMessage.classList.remove('hidden');
        return;
    }

    elements.welcomeMessage.classList.add('hidden');

    const html = messages.map((msg, index) => {
        const isUser = msg.role === 'user';
        const avatar = isUser ? 'U' : 'A';
        const time = new Date(msg.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

        let sourcesBtn = '';
        if (msg.sources && msg.sources.length > 0) {
            sourcesBtn = `<button class="sources-btn" data-index="${index}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                ${msg.sources.length} sources
            </button>`;
        }

        return `
            <div class="message ${isUser ? 'user' : 'assistant'}">
                <div class="message-avatar">${avatar}</div>
                <div class="message-content">
                    <div class="message-bubble">${formatMessage(msg.content)}</div>
                    <div class="message-meta">
                        <span>${time}</span>
                        ${sourcesBtn}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    elements.chatMessages.innerHTML = html;
    scrollToBottom();

    // Add source button handlers
    elements.chatMessages.querySelectorAll('.sources-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const index = parseInt(btn.dataset.index);
            const msg = messages[index];
            if (msg.sources) {
                showSources(msg.sources);
            }
        });
    });
}

function addMessage(role, content, sources = null) {
    const msg = {
        role,
        content,
        timestamp: new Date().toISOString(),
        sources
    };

    // Get current messages from DOM or create empty array
    const existingMessages = elements.chatMessages.querySelectorAll('.message');
    const isFirstMessage = existingMessages.length === 0 || !elements.welcomeMessage.classList.contains('hidden');

    if (isFirstMessage) {
        elements.welcomeMessage.classList.add('hidden');
        elements.chatMessages.innerHTML = '';
    }

    const isUser = role === 'user';
    const avatar = isUser ? 'U' : 'A';
    const time = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

    let sourcesBtn = '';
    if (sources && sources.length > 0) {
        const btnId = `sources-${Date.now()}`;
        sourcesBtn = `<button class="sources-btn" id="${btnId}">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
            </svg>
            ${sources.length} sources
        </button>`;

        // Store sources for later
        state.currentSources = sources;
    }

    const messageHtml = `
        <div class="message ${isUser ? 'user' : 'assistant'}" id="msg-${Date.now()}">
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-bubble">${formatMessage(content)}</div>
                <div class="message-meta">
                    <span>${time}</span>
                    ${sourcesBtn}
                </div>
            </div>
        </div>
    `;

    elements.chatMessages.insertAdjacentHTML('beforeend', messageHtml);
    scrollToBottom();

    // Add source button handler
    if (sources && sources.length > 0) {
        const btn = elements.chatMessages.querySelector('.sources-btn:last-of-type');
        if (btn) {
            btn.addEventListener('click', () => showSources(sources));
        }
    }

    return elements.chatMessages.lastElementChild;
}

function addLoadingMessage() {
    const html = `
        <div class="message assistant" id="loading-message">
            <div class="message-avatar">A</div>
            <div class="message-content">
                <div class="message-bubble">
                    <div class="message-loading">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        </div>
    `;
    elements.chatMessages.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
}

function removeLoadingMessage() {
    const loading = document.getElementById('loading-message');
    if (loading) loading.remove();
}

function updateStreamingMessage(content) {
    let streamingMsg = document.getElementById('streaming-message');

    if (!streamingMsg) {
        removeLoadingMessage();
        const html = `
            <div class="message assistant" id="streaming-message">
                <div class="message-avatar">A</div>
                <div class="message-content">
                    <div class="message-bubble"></div>
                    <div class="message-meta">
                        <span>${new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                </div>
            </div>
        `;
        elements.chatMessages.insertAdjacentHTML('beforeend', html);
        streamingMsg = document.getElementById('streaming-message');
    }

    const bubble = streamingMsg.querySelector('.message-bubble');
    bubble.innerHTML = formatMessage(content);
    scrollToBottom();
}

function finalizeStreamingMessage(sources) {
    const streamingMsg = document.getElementById('streaming-message');
    if (streamingMsg && sources && sources.length > 0) {
        const meta = streamingMsg.querySelector('.message-meta');
        const btnId = `sources-final-${Date.now()}`;
        meta.insertAdjacentHTML('beforeend', `
            <button class="sources-btn" id="${btnId}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
                ${sources.length} sources
            </button>
        `);

        document.getElementById(btnId)?.addEventListener('click', () => showSources(sources));
        streamingMsg.id = `msg-${Date.now()}`;
    }
}

function showSources(sources) {
    const html = sources.map(s => `
        <div class="source-item ${s.expanded ? 'expanded' : ''}">
            <div class="source-header">
                <span class="source-rank">#${s.rank}</span>
                <span class="source-score">Score: ${s.score}</span>
            </div>
            <div class="source-file">${escapeHtml(s.file)}</div>
            <div class="source-participants">${s.participants.join(', ')}</div>
            <div class="source-dates">${s.date_start} - ${s.date_end}</div>
        </div>
    `).join('');

    elements.sourcesContent.innerHTML = html;
    elements.sourcesPanel.classList.add('visible');
}

function renderParticipants(participants) {
    const html = participants.map(p =>
        `<option value="${escapeHtml(p.name)}">${escapeHtml(p.name)} (${p.count})</option>`
    ).join('');

    elements.participantFilter.innerHTML = '<option value="">Tous</option>' + html;
}

function updateStatus(status) {
    const dot = elements.statusIndicator.querySelector('.status-dot');
    const text = elements.statusIndicator.querySelector('.status-text');

    if (status.ready) {
        dot.className = 'status-dot ready';
        text.textContent = `${status.chunks_count.toLocaleString()} chunks indexes`;
        state.systemReady = true;
    } else {
        dot.className = 'status-dot error';
        text.textContent = 'Index non disponible';
        state.systemReady = false;
    }
}

// ============================================================
// Actions
// ============================================================

async function loadConversations() {
    try {
        state.conversations = await api.getConversations();
        renderConversationsList();
    } catch (e) {
        console.error('Failed to load conversations:', e);
    }
}

async function loadConversation(id) {
    try {
        const conv = await api.getConversation(id);
        state.currentConversationId = id;
        elements.chatTitle.textContent = conv.title;
        renderConversationsList();
        renderMessages(conv.messages);

        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            elements.sidebar.classList.remove('visible');
        }
    } catch (e) {
        console.error('Failed to load conversation:', e);
    }
}

async function startNewConversation() {
    state.currentConversationId = null;
    elements.chatTitle.textContent = 'Nouvelle conversation';
    elements.chatMessages.innerHTML = '';
    elements.welcomeMessage.classList.remove('hidden');
    renderConversationsList();

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
        elements.sidebar.classList.remove('visible');
    }
}

async function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message || state.isLoading) return;

    state.isLoading = true;
    elements.sendBtn.disabled = true;
    elements.messageInput.value = '';
    autoResizeTextarea();

    // Add user message
    addMessage('user', message);

    // Prepare request
    const data = {
        message,
        conversation_id: state.currentConversationId,
        participant_filter: elements.participantFilter.value || null,
        year_filter: elements.yearFilter.value ? parseInt(elements.yearFilter.value) : null,
        date_start: elements.dateStart.value || null,
        date_end: elements.dateEnd.value || null,
        use_reranking: elements.useReranking.checked,
        use_hybrid: elements.useHybrid.checked,
        expand_context: elements.expandContext.checked
    };

    // Show loading
    addLoadingMessage();

    let responseContent = '';
    let responseSources = [];

    // Stream response
    api.streamMessage(data, {
        onConversationId: (id) => {
            if (!state.currentConversationId) {
                state.currentConversationId = id;
                loadConversations();
            }
        },
        onSources: (sources) => {
            responseSources = sources;
        },
        onChunk: (chunk) => {
            responseContent += chunk;
            updateStreamingMessage(responseContent);
        },
        onDone: () => {
            finalizeStreamingMessage(responseSources);
            state.isLoading = false;
            elements.sendBtn.disabled = false;
            loadConversations();
        },
        onError: (error) => {
            removeLoadingMessage();
            addMessage('assistant', 'Erreur: ' + (error || 'Une erreur est survenue'));
            state.isLoading = false;
            elements.sendBtn.disabled = false;
        }
    });
}

let deleteTargetId = null;

function showDeleteModal(id) {
    deleteTargetId = id;
    elements.deleteModal.classList.add('visible');
}

function hideDeleteModal() {
    deleteTargetId = null;
    elements.deleteModal.classList.remove('visible');
}

async function confirmDeleteConversation() {
    if (!deleteTargetId) return;

    const id = deleteTargetId;
    hideDeleteModal();

    try {
        await api.deleteConversation(id);

        if (state.currentConversationId === id) {
            startNewConversation();
        }

        await loadConversations();
    } catch (e) {
        console.error('Failed to delete conversation:', e);
    }
}

// ============================================================
// Utilities
// ============================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatMessage(text) {
    // Convert markdown-like formatting
    let html = escapeHtml(text);

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Line breaks
    html = html.replace(/\n/g, '<br>');

    return html;
}

function scrollToBottom() {
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function autoResizeTextarea() {
    const textarea = elements.messageInput;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
}

// ============================================================
// Event Listeners
// ============================================================

// New chat
elements.newChatBtn.addEventListener('click', startNewConversation);

// Menu toggle (mobile)
elements.menuToggle.addEventListener('click', () => {
    elements.sidebar.classList.toggle('visible');
});

// Filters toggle
elements.filtersToggle.addEventListener('click', () => {
    elements.filtersPanel.classList.toggle('visible');
    elements.filtersToggle.classList.toggle('active');
});

// Close sources
elements.closeSourcesBtn.addEventListener('click', () => {
    elements.sourcesPanel.classList.remove('visible');
});

// Send message
elements.sendBtn.addEventListener('click', sendMessage);

elements.messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

elements.messageInput.addEventListener('input', () => {
    autoResizeTextarea();
    elements.sendBtn.disabled = !elements.messageInput.value.trim();
});

// Example queries
document.querySelectorAll('.example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        elements.messageInput.value = btn.dataset.query;
        autoResizeTextarea();
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    });
});

// Delete modal
elements.cancelDelete.addEventListener('click', hideDeleteModal);
elements.confirmDelete.addEventListener('click', confirmDeleteConversation);
elements.deleteModal.addEventListener('click', (e) => {
    if (e.target === elements.deleteModal) hideDeleteModal();
});

// Close sidebar when clicking outside on mobile
document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768) {
        if (!elements.sidebar.contains(e.target) &&
            !elements.menuToggle.contains(e.target) &&
            elements.sidebar.classList.contains('visible')) {
            elements.sidebar.classList.remove('visible');
        }
    }
});

// ============================================================
// Initialization
// ============================================================

async function init() {
    try {
        // Load status
        const status = await api.getStatus();
        updateStatus(status);

        // Load participants for filter
        if (status.ready) {
            const participants = await api.getParticipants();
            renderParticipants(participants);
        }

        // Load conversations
        await loadConversations();

    } catch (e) {
        console.error('Initialization error:', e);
        updateStatus({ ready: false });
    }
}

// Start
init();
