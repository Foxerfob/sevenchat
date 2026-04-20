const state = {
    currentRoomId: null,
    nextBatchToken: null,
    isLoadingHistory: false,
    pollInterval: 2000,
    knownEventIds: new Set()
};

const chatHistoryEl = document.getElementById('chat-history');
const messagesContainer = document.getElementById('messages-container');
const loadMoreBtn = document.getElementById('load-more-btn');
const messageInput = document.getElementById('message-input');
const currentRoomNameEl = document.getElementById('current-room-name');

document.addEventListener('DOMContentLoaded', () => {
    fetchRooms();
    setInterval(updateLoop, state.pollInterval);

    loadMoreBtn.onclick = () => loadHistory(true);

    document.getElementById('message-form').onsubmit = async (e) => {
        e.preventDefault();
        const text = messageInput.value.trim();
        if (text && state.currentRoomId) {
            await fetch(`/api/rooms/${state.currentRoomId}/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
            messageInput.value = '';
        }
    };
});

async function fetchRooms() {
    const r = await fetch('/api/rooms');
    const data = await r.json();
    const list = document.getElementById('rooms-list');
    list.innerHTML = '';
    data.rooms.forEach(room => {
        const div = document.createElement('div');
        div.className = `room-item ${state.currentRoomId === room.room_id ? 'active' : ''}`;
        div.innerText = room.name || room.room_id;
        div.onclick = () => selectRoom(room.room_id, room.name);
        list.appendChild(div);
    });
}

async function selectRoom(roomId, roomName) {
    state.currentRoomId = roomId;
    state.nextBatchToken = null;
    state.knownEventIds.clear();
    
    document.getElementById('current-room-name').innerText = roomName || roomId;
    document.getElementById('message-input').disabled = false;
    messagesContainer.innerHTML = '';
    
    await loadHistory(false);
}

async function loadHistory(isLoadMore = false) {
    if (state.isLoadingHistory || !state.currentRoomId) return;
    state.isLoadingHistory = true;

    const url = `/api/rooms/${state.currentRoomId}/history` + 
                (isLoadMore && state.nextBatchToken ? `?start_from=${state.nextBatchToken}` : '');

    try {
        const r = await fetch(url);
        const data = await r.json();
        
        state.nextBatchToken = data.next_start;
        loadMoreBtn.style.display = data.messages.length > 0 ? 'block' : 'none';

        const oldHeight = chatHistoryEl.scrollHeight;

        const fragment = document.createDocumentFragment();
        data.messages.forEach(msg => {
            if (!state.knownEventIds.has(msg.event_id)) {
                state.knownEventIds.add(msg.event_id);
                const temp = document.createElement('div');
                temp.innerHTML = createMessageHTML(msg);
                fragment.appendChild(temp.firstElementChild);
            }
        });

        if (isLoadMore) {
            messagesContainer.prepend(fragment);
            chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight - oldHeight;
        } else {
            messagesContainer.appendChild(fragment);
            chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
        }
    } finally {
        state.isLoadingHistory = false;
    }
}

async function updateLoop() {
    if (!state.currentRoomId || state.isLoadingHistory) return;

    try {
        const r = await fetch(`/api/rooms/${state.currentRoomId}/sync`);
        const data = await r.json();

        if (data.messages && data.messages.length > 0) {
            let addedAny = false;
            data.messages.forEach(msg => {
                if (!state.knownEventIds.has(msg.event_id)) {
                    state.knownEventIds.add(msg.event_id);
                    messagesContainer.insertAdjacentHTML('beforeend', createMessageHTML(msg));
                    addedAny = true;
                }
            });

            if (addedAny) {
                chatHistoryEl.scrollTo({ top: chatHistoryEl.scrollHeight, behavior: 'smooth' });
            }
        }
    } catch (e) {
        console.error("Sync error:", e);
    }
}

function createMessageHTML(msg) {
    const time = new Date(msg.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    return `
        <div class="message" data-id="${msg.event_id}">
            <div class="message-header">
                <span class="message-sender">${msg.sender}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-body">${escapeHTML(msg.body)}</div>
        </div>`;
}

function escapeHTML(str) {
    const p = document.createElement('p');
    p.textContent = str;
    return p.innerHTML;
}
