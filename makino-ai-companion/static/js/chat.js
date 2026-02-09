/**
 * 牧野生保塾 AI伴走システム - チャットUI
 *
 * FastAPI バックエンドの /api/chat エンドポイントと通信し、
 * チャットインターフェースを提供する。
 * スタンドアロン + ウィジェット埋め込み両対応。
 *
 * 質問ナビ機能:
 * リテラシーの低いユーザー向けに、多段階選択フローで質問を構築する。
 * Step 1: 静的カテゴリ選択（Pattern別）
 * Step 2: AI生成のサブトピック選択
 * Step 3: 補足入力 → 質問として送信
 */

const chatArea = document.getElementById("chatArea");
const questionInput = document.getElementById("questionInput");
const sendButton = document.getElementById("sendButton");
const patternSelect = document.getElementById("patternSelect");
const guideButton = document.getElementById("guideButton");
const guidePanel = document.getElementById("guidePanel");
const guideClose = document.getElementById("guideClose");
const guideBody = document.getElementById("guideBody");
const guideTitle = document.getElementById("guideTitle");

let sessionId = null;
let isLoading = false;

// --- 質問ナビ: Pattern別カテゴリ定義（静的）---

const GUIDE_CATEGORIES = {
    1: [
        { id: "corporate", label: "法人保険", subs: ["決算書分析", "退職金設計", "事業承継", "節税・財務改善"] },
        { id: "doctor", label: "ドクターマーケット", subs: ["医療法人アプローチ", "個人開業医", "医療特有の税制", "事業承継"] },
        { id: "succession", label: "相続・資産承継", subs: ["相続対策", "資産承継プラン", "生前贈与"] },
        { id: "sales_skill", label: "営業スキル", subs: ["アプローチ手法", "クロージング", "ヒアリング技術", "紹介獲得"] },
        { id: "mindset", label: "営業マインド", subs: ["モチベーション維持", "成功習慣", "目標設定"] },
    ],
    2: [
        { id: "medical_corp", label: "医療法人", subs: ["組織形態と運営", "M&A・事業承継", "役員退職金", "節税対策"] },
        { id: "individual_doc", label: "個人開業医", subs: ["開業支援", "個人事業の法人化", "リタイアメント"] },
        { id: "approach", label: "アプローチ手法", subs: ["初回面談", "信頼構築", "提案方法", "紹介ルート開拓"] },
        { id: "tax_law", label: "医療特有の税制・法令", subs: ["医療法の基礎", "MS法人", "持分なし医療法人"] },
    ],
    3: [
        { id: "balance_sheet", label: "決算書分析", subs: ["P/Lの読み方", "B/Sの分析", "財務指標の目安", "赤字企業の分析"] },
        { id: "retirement", label: "退職金設計", subs: ["役員退職金", "従業員退職金", "退職金準備手法"] },
        { id: "succession", label: "事業承継", subs: ["後継者への引継ぎ", "株式移転", "M&A活用"] },
        { id: "tax_saving", label: "節税・財務改善", subs: ["法人税対策", "キャッシュフロー改善", "資金繰り"] },
        { id: "proposal", label: "提案ロジック", subs: ["現状分析の伝え方", "課題の可視化", "解決策の組み立て"] },
    ],
};

// 質問ナビの状態
let guideState = {
    isOpen: false,
    step: 0,       // 0: カテゴリ, 1: サブトピック(AI生成), 2: 補足入力+確認
    category: null,
    subCategory: null,
    aiSuggestions: [],
    freeText: "",
};

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
guideButton.addEventListener("click", toggleGuide);
guideClose.addEventListener("click", closeGuide);

// --- メッセージ送信 ---

async function sendMessage(overrideQuestion) {
    const question = overrideQuestion || questionInput.value.trim();
    if (!question || isLoading) return;

    // ガイドパネルを閉じる
    closeGuide();

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

// ==========================================================================
// 質問ナビ
// ==========================================================================

function toggleGuide() {
    if (guideState.isOpen) {
        closeGuide();
    } else {
        openGuide();
    }
}

function openGuide() {
    guideState = { isOpen: true, step: 0, category: null, subCategory: null, aiSuggestions: [], freeText: "" };
    guidePanel.classList.add("guide-panel--open");
    guideButton.classList.add("guide-toggle--active");
    renderGuideStep();
}

function closeGuide() {
    guideState.isOpen = false;
    guidePanel.classList.remove("guide-panel--open");
    guideButton.classList.remove("guide-toggle--active");
}

function renderGuideStep() {
    const pattern = parseInt(patternSelect.value);

    // Pattern 4（励まし）はガイド不要
    if (pattern === 4) {
        guideBody.innerHTML = `
            <p style="font-size:13px;color:var(--text-light);padding:8px 0;">
                励まし・メンタリングモードでは、自由にお気持ちをお聞かせください。
            </p>
        `;
        return;
    }

    const categories = GUIDE_CATEGORIES[pattern] || [];
    const stepLabels = ["カテゴリ", "トピック", "質問作成"];
    const totalSteps = 3;

    // ステップインジケーター
    let stepsHtml = '<div class="guide-steps">';
    for (let i = 0; i < totalSteps; i++) {
        const cls = i < guideState.step ? "guide-step--done" : i === guideState.step ? "guide-step--active" : "";
        stepsHtml += `<span class="guide-step ${cls}">${stepLabels[i]}</span>`;
        if (i < totalSteps - 1) stepsHtml += '<span class="guide-step-arrow">&rsaquo;</span>';
    }
    stepsHtml += "</div>";

    if (guideState.step === 0) {
        // Step 0: カテゴリ選択（静的）
        guideTitle.textContent = "質問ナビ - テーマを選択";
        let html = stepsHtml;
        html += '<div class="guide-options">';
        for (const cat of categories) {
            html += `<button class="guide-option" data-cat-id="${cat.id}" data-cat-label="${escapeHtml(cat.label)}">${escapeHtml(cat.label)}</button>`;
        }
        html += "</div>";
        guideBody.innerHTML = html;

        guideBody.querySelectorAll(".guide-option").forEach(btn => {
            btn.addEventListener("click", () => {
                const catId = btn.dataset.catId;
                const catLabel = btn.dataset.catLabel;
                const cat = categories.find(c => c.id === catId);
                guideState.category = { id: catId, label: catLabel, subs: cat.subs };
                guideState.step = 1;
                renderGuideStep();
            });
        });

    } else if (guideState.step === 1) {
        // Step 1: サブトピック選択 → AI生成の選択肢
        guideTitle.textContent = `質問ナビ - ${guideState.category.label}`;
        let html = stepsHtml;
        html += `<button class="guide-back" id="guideBack">&larr; 戻る</button>`;

        // まず静的サブカテゴリを表示、その後AI生成を試みる
        if (guideState.aiSuggestions.length > 0) {
            html += '<div class="guide-options">';
            for (const suggestion of guideState.aiSuggestions) {
                html += `<button class="guide-option" data-suggestion="${escapeHtml(suggestion)}">${escapeHtml(suggestion)}</button>`;
            }
            html += "</div>";
        } else {
            // 静的サブカテゴリを先に表示
            html += '<div class="guide-options">';
            for (const sub of guideState.category.subs) {
                html += `<button class="guide-option" data-suggestion="${escapeHtml(sub)}">${escapeHtml(sub)}</button>`;
            }
            html += "</div>";

            // AI生成を非同期で取得
            fetchAiSuggestions(pattern, guideState.category.label);
        }

        guideBody.innerHTML = html;

        // 戻るボタン
        const backBtn = guideBody.querySelector("#guideBack");
        if (backBtn) {
            backBtn.addEventListener("click", () => {
                guideState.step = 0;
                guideState.category = null;
                guideState.aiSuggestions = [];
                renderGuideStep();
            });
        }

        // サブトピック選択
        guideBody.querySelectorAll(".guide-option").forEach(btn => {
            btn.addEventListener("click", () => {
                guideState.subCategory = btn.dataset.suggestion;
                guideState.step = 2;
                renderGuideStep();
            });
        });

    } else if (guideState.step === 2) {
        // Step 2: 補足入力 + 確認 → 質問送信
        guideTitle.textContent = "質問ナビ - 質問を送信";
        let html = stepsHtml;
        html += `<button class="guide-back" id="guideBack">&larr; 戻る</button>`;

        // サマリー表示
        html += `
            <div class="guide-summary">
                <div class="guide-summary-label">テーマ</div>
                <div class="guide-summary-value">${escapeHtml(guideState.category.label)} &rsaquo; ${escapeHtml(guideState.subCategory)}</div>
            </div>
        `;

        // 補足入力
        html += `
            <textarea class="guide-freetext" id="guideFreetext" rows="2"
                placeholder="具体的な状況や知りたいことがあれば補足してください（任意）"></textarea>
        `;

        // 送信ボタン
        html += `<button class="guide-submit" id="guideSubmit">この内容で質問する</button>`;

        guideBody.innerHTML = html;

        // 戻るボタン
        guideBody.querySelector("#guideBack").addEventListener("click", () => {
            guideState.step = 1;
            renderGuideStep();
        });

        // 送信ボタン
        guideBody.querySelector("#guideSubmit").addEventListener("click", () => {
            const freetext = guideBody.querySelector("#guideFreetext").value.trim();
            const question = buildGuideQuestion(guideState.category.label, guideState.subCategory, freetext);
            sendMessage(question);
        });
    }
}

/**
 * AI生成の選択肢を非同期取得する（ハイブリッドのStep 2）
 */
async function fetchAiSuggestions(pattern, category) {
    try {
        const response = await fetch("/api/guide/suggestions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pattern, category }),
        });

        if (!response.ok) return;

        const data = await response.json();
        if (data.suggestions && data.suggestions.length > 0) {
            guideState.aiSuggestions = data.suggestions;
            // 現在Step 1にいる場合のみ再描画
            if (guideState.step === 1) {
                renderGuideStep();
            }
        }
    } catch (error) {
        // AI生成失敗時は静的選択肢のまま（フォールバック）
        console.log("Guide suggestions fallback to static:", error);
    }
}

/**
 * ガイドの選択結果から質問文を組み立てる
 */
function buildGuideQuestion(category, subCategory, freetext) {
    let question = `${category}の${subCategory}について教えてください。`;
    if (freetext) {
        question = `${category}の${subCategory}について質問です。${freetext}`;
    }
    return question;
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
