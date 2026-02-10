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
const welcomeScreen = document.getElementById("welcomeScreen");

let sessionId = null;
let isLoading = false;
let sessionPosition = 0;     // セッション内の質問番号
let inputStartTime = 0;      // 入力開始時刻（操作時間計測用）

// --- 操作シグナル追跡 ---
let interactionSignals = {
    inputMethod: "free_text",
    guideCategory: "",
    guideSubTopic: "",
    guideStepsTaken: 0,
    guideBacktrack: 0,
    guideAiUsed: false,
    guideFreetextLen: 0,
};

function resetInteractionSignals() {
    interactionSignals = {
        inputMethod: "free_text",
        guideCategory: "",
        guideSubTopic: "",
        guideStepsTaken: 0,
        guideBacktrack: 0,
        guideAiUsed: false,
        guideFreetextLen: 0,
    };
}

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
    // 入力開始時刻を記録（最初のキー入力時のみ）
    if (inputStartTime === 0 && questionInput.value.trim() !== "") {
        inputStartTime = Date.now();
    }
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

// --- ウェルカム画面 ---

if (welcomeScreen) {
    // パターンチップクリック → パターン切替 + ハイライト
    welcomeScreen.querySelectorAll(".welcome-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const pattern = chip.dataset.pattern;
            patternSelect.value = pattern;
            // チップのアクティブ状態を切替
            welcomeScreen.querySelectorAll(".welcome-chip").forEach(c => c.classList.remove("--active"));
            chip.classList.add("--active");
        });
    });

    // サジェスト質問クリック → 質問送信 + ウェルカム画面消去
    welcomeScreen.querySelectorAll(".welcome-suggestion-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const question = btn.dataset.question;
            if (question) {
                dismissWelcome(() => sendMessage(question));
            }
        });
    });
}

/**
 * ウェルカム画面をアニメーション付きで消去する
 */
function dismissWelcome(callback) {
    if (!welcomeScreen || welcomeScreen.classList.contains("--leaving")) return;
    welcomeScreen.classList.add("--leaving");
    welcomeScreen.addEventListener("animationend", () => {
        welcomeScreen.remove();
        if (callback) callback();
    }, { once: true });
}

// --- メッセージ送信 ---

async function sendMessage(overrideQuestion) {
    const question = overrideQuestion || questionInput.value.trim();
    if (!question || isLoading) return;

    // ガイドパネルを閉じる
    closeGuide();

    // ウェルカム画面を消去
    if (welcomeScreen && welcomeScreen.parentNode) {
        welcomeScreen.remove();
    }

    // ユーザーメッセージ表示
    appendMessage("user", question);
    questionInput.value = "";
    autoResize(questionInput);
    sendButton.disabled = true;

    // ローディング表示
    const loadingEl = showLoading();
    isLoading = true;

    // 操作シグナルを計算
    sessionPosition++;
    const responseTimeMs = inputStartTime > 0 ? Date.now() - inputStartTime : 0;
    const hasNumber = /\d/.test(question);

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                pattern: parseInt(patternSelect.value),
                session_id: sessionId,
                interaction: {
                    input_method: interactionSignals.inputMethod,
                    guide_category: interactionSignals.guideCategory,
                    guide_sub_topic: interactionSignals.guideSubTopic,
                    guide_steps_taken: interactionSignals.guideStepsTaken,
                    guide_backtrack: interactionSignals.guideBacktrack,
                    guide_ai_used: interactionSignals.guideAiUsed,
                    guide_freetext_len: interactionSignals.guideFreetextLen,
                    question_length: question.length,
                    question_has_number: hasNumber,
                    response_time_ms: responseTimeMs,
                    session_position: sessionPosition,
                },
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
        resetInteractionSignals();
        inputStartTime = 0;
    }
}

// --- メッセージ表示 ---

function appendMessage(role, text, options = {}) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message message--${role}`;

    // アバター + バブル行
    const rowDiv = document.createElement("div");
    rowDiv.className = "message-row";

    const avatarDiv = document.createElement("div");
    avatarDiv.className = "message-avatar";
    if (role === "assistant") {
        avatarDiv.innerHTML = '<img src="/static/img/makino-avatar.svg" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;">';
    } else {
        avatarDiv.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
    }
    rowDiv.appendChild(avatarDiv);

    const bubbleDiv = document.createElement("div");
    bubbleDiv.className = "message-bubble";
    bubbleDiv.textContent = text;
    rowDiv.appendChild(bubbleDiv);

    messageDiv.appendChild(rowDiv);

    // 出典表示（アシスタントのみ）
    if (role === "assistant" && options.sources && options.sources.length > 0) {
        const sourcesDiv = document.createElement("details");
        sourcesDiv.className = "message-sources";
        sourcesDiv.innerHTML = `
            <summary>参考資料 (${options.sources.length}件)</summary>
            <ul>${options.sources.map(s => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
        `;
        messageDiv.appendChild(sourcesDiv);
    }

    // フィードバックボタン（アシスタントのみ、エスカレーション以外）
    if (role === "assistant" && options.conversationId && !options.escalated) {
        const feedbackDiv = document.createElement("div");
        feedbackDiv.className = "message-feedback";
        feedbackDiv.innerHTML = `
            <button class="feedback-btn" data-rating="good" data-conv-id="${options.conversationId}">役に立った</button>
            <button class="feedback-btn" data-rating="bad" data-conv-id="${options.conversationId}">改善が必要</button>
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
        <div class="message-row">
            <div class="message-avatar"><img src="/static/img/makino-avatar.svg" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:inherit;"></div>
            <div class="message-bubble">
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
                <span class="loading-dot"></span>
            </div>
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
    // 質問ナビ利用を記録
    interactionSignals.inputMethod = "guided_nav";
    interactionSignals.guideStepsTaken = 0;
    interactionSignals.guideBacktrack = 0;
    inputStartTime = Date.now();
    renderGuideStep();
}

function closeGuide() {
    if (!guideState.isOpen) return;
    guideState.isOpen = false;
    guidePanel.classList.add("guide-panel--closing");
    guidePanel.addEventListener("animationend", () => {
        guidePanel.classList.remove("guide-panel--open", "guide-panel--closing");
    }, { once: true });
    guideButton.classList.remove("guide-toggle--active");
}

/** ステップ切替アニメーション（前進/後退） */
function animateGuideStep(direction) {
    guideBody.classList.remove("guide-body--transitioning", "guide-body--back");
    // reflow trick to restart animation
    void guideBody.offsetWidth;
    guideBody.classList.add(direction === "back" ? "guide-body--back" : "guide-body--transitioning");
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
                interactionSignals.guideCategory = catLabel;
                interactionSignals.guideStepsTaken++;
                animateGuideStep("forward");
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
                interactionSignals.guideBacktrack++;
                animateGuideStep("back");
                renderGuideStep();
            });
        }

        // サブトピック選択
        guideBody.querySelectorAll(".guide-option").forEach(btn => {
            btn.addEventListener("click", () => {
                guideState.subCategory = btn.dataset.suggestion;
                guideState.step = 2;
                interactionSignals.guideSubTopic = btn.dataset.suggestion;
                interactionSignals.guideStepsTaken++;
                animateGuideStep("forward");
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
            interactionSignals.guideBacktrack++;
            animateGuideStep("back");
            renderGuideStep();
        });

        // 送信ボタン
        guideBody.querySelector("#guideSubmit").addEventListener("click", () => {
            const freetext = guideBody.querySelector("#guideFreetext").value.trim();
            interactionSignals.guideFreetextLen = freetext.length;
            interactionSignals.guideStepsTaken++;
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
            interactionSignals.guideAiUsed = true;
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
