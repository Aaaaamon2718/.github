/**
 * 牧野生保塾 AI伴走システム - チャットUI
 *
 * FastAPI バックエンドの /api/chat エンドポイントと通信し、
 * チャットインターフェースを提供する。
 * スタンドアロン + ウィジェット埋め込み両対応。
 */

const chatArea = document.getElementById("chatArea");
const questionInput = document.getElementById("questionInput");
const sendButton = document.getElementById("sendButton");
const patternSelect = document.getElementById("patternSelect");

let sessionId = null;
let isLoading = false;

// --- 初期化 ---

questionInput.addEventListener("input", () => {
    sendButton.disabled = questionInput.value.trim() === "" || isLoading;
    autoResize(questionInput);
});

questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!sendButton.disabled) sendMessage();
    }
});

sendButton.addEventListener("click", sendMessage);

// --- メッセージ送信 ---

async function sendMessage() {
    const question = questionInput.value.trim();
    if (!question || isLoading) return;

    // ウェルカムメッセージを削除
    const welcome = chatArea.querySelector(".welcome-message");
    if (welcome) welcome.remove();

    // ユーザーメッセージ表示
    appendMessage("user", question);
    questionInput.value = "";
    autoResize(questionInput);
    sendButton.disabled = true;

    // ローディング表示
    const loadingEl = showLoading();
    isLoading = true;

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                pattern: parseInt(patternSelect.value),
                session_id: sessionId,
            }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "エラーが発生しました");
        }

        sessionId = data.session_id;

        // ローディング除去 → 回答表示
        loadingEl.remove();
        appendMessage("assistant", data.answer, {
            sources: data.sources,
            conversationId: data.conversation_id,
            escalated: data.escalated,
        });

    } catch (error) {
        loadingEl.remove();
        appendMessage("assistant", "申し訳ありません。通信エラーが発生しました。再度お試しください。");
        console.error("Chat error:", error);
    } finally {
        isLoading = false;
        sendButton.disabled = questionInput.value.trim() === "";
    }
}

// --- メッセージ表示 ---

function appendMessage(role, text, options = {}) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message message--${role}`;

    const bubbleDiv = document.createElement("div");
    bubbleDiv.className = "message-bubble";
    bubbleDiv.textContent = text;
    messageDiv.appendChild(bubbleDiv);

    // 出典表示（アシスタントのみ）
    if (role === "assistant" && options.sources && options.sources.length > 0) {
        const sourcesDiv = document.createElement("details");
        sourcesDiv.className = "message-sources";
        sourcesDiv.innerHTML = `
            <summary>出典 (${options.sources.length}件)</summary>
            <ul>${options.sources.map(s => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
        `;
        messageDiv.appendChild(sourcesDiv);
    }

    // フィードバックボタン（アシスタントのみ、エスカレーション以外）
    if (role === "assistant" && options.conversationId && !options.escalated) {
        const feedbackDiv = document.createElement("div");
        feedbackDiv.className = "message-feedback";
        feedbackDiv.innerHTML = `
            <button class="feedback-btn" data-rating="good" data-conv-id="${options.conversationId}">&#x1F44D; 役に立った</button>
            <button class="feedback-btn" data-rating="bad" data-conv-id="${options.conversationId}">&#x1F44E; 改善が必要</button>
        `;
        feedbackDiv.querySelectorAll(".feedback-btn").forEach(btn => {
            btn.addEventListener("click", () => sendFeedback(btn));
        });
        messageDiv.appendChild(feedbackDiv);
    }

    chatArea.appendChild(messageDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
}

function showLoading() {
    const loadingDiv = document.createElement("div");
    loadingDiv.className = "message message--assistant message--loading";
    loadingDiv.innerHTML = `
        <div class="message-bubble">
            <span class="loading-dot"></span>
            <span class="loading-dot"></span>
            <span class="loading-dot"></span>
        </div>
    `;
    chatArea.appendChild(loadingDiv);
    chatArea.scrollTop = chatArea.scrollHeight;
    return loadingDiv;
}

// --- フィードバック送信 ---

async function sendFeedback(button) {
    const convId = button.dataset.convId;
    const rating = button.dataset.rating;

    // 同じメッセージの全ボタンを無効化
    const feedbackDiv = button.parentElement;
    feedbackDiv.querySelectorAll(".feedback-btn").forEach(btn => {
        btn.disabled = true;
        btn.classList.remove("feedback-btn--active");
    });
    button.classList.add("feedback-btn--active");

    try {
        await fetch("/api/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                conversation_id: parseInt(convId),
                rating: rating,
            }),
        });
    } catch (error) {
        console.error("Feedback error:", error);
    }
}

// --- ユーティリティ ---

function autoResize(textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + "px";
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
