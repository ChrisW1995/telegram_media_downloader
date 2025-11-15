/**
 * Message Downloader - Authentication Module
 * Telegram 認證相關功能
 *
 * 處理用戶登入、認證流程、會話管理等功能
 */

// ==================== 認證狀態管理 ====================

// 全域變數控制認證檢查狀態，防止重複調用
let isCheckingAuth = false;
let authCheckCompleted = false;

/**
 * 重置認證狀態，允許重新檢查
 */
function resetAuthStatus() {
    console.log('🔄 重置認證狀態');
    isCheckingAuth = false;
    authCheckCompleted = false;
}

/**
 * 檢查用戶認證狀態
 * 在頁面載入時檢查用戶是否已認證
 */
async function checkAuthStatus() {
    // 如果在登入頁面,不要檢查認證狀態(避免無限跳轉)
    if (window.location.pathname.includes('/login')) {
        console.log('⏭️  在登入頁面,跳過認證檢查');
        return;
    }

    // 防止重複調用認證檢查
    if (isCheckingAuth) {
        console.log('🔄 認證檢查已在進行中，跳過重複調用');
        return;
    }

    if (authCheckCompleted) {
        console.log('✅ 認證檢查已完成，跳過重複調用');
        return;
    }

    isCheckingAuth = true;
    showLoginStatusLoading();

    try {
        console.log('🔍 開始檢查認證狀態...');
        const response = await fetch('/api/auth/status');
        const data = await response.json();
        console.log('📋 認證狀態響應:', data);

        if (data.success && data.data && data.data.authenticated) {
            console.log('✅ 用戶已認證, 用戶資訊:', data.data.user_info);
            authCheckCompleted = true;
            isCheckingAuth = false;
            showLoginStatusSuccess(data.data.user_info);
            showAuthSuccess(data.data.user_info);
            loadGroups();
        } else {
            console.log('❌ 用戶未認證，data:', data);

            // 額外檢查：如果從登入頁面重新導向過來，再次確認
            if (window.location.pathname === '/message_downloader' && document.referrer.includes('/login')) {
                console.log('⏰ 從登入頁面跳轉，等待 1 秒後重新檢查...');
                setTimeout(async () => {
                    const retryResponse = await fetch('/api/auth/status');
                    const retryData = await retryResponse.json();
                    console.log('🔄 重新檢查認證狀態:', retryData);

                    if (retryData.success && retryData.data && retryData.data.authenticated) {
                        console.log('✅ 重新檢查：用戶已認證');
                        authCheckCompleted = true;
                        isCheckingAuth = false;
                        showLoginStatusSuccess(retryData.data.user_info);
                        showAuthSuccess(retryData.data.user_info);
                        loadGroups();
                    } else {
                        console.log('❌ 重新檢查：用戶仍未認證');
                        authCheckCompleted = true;
                        isCheckingAuth = false;
                        showLoginStatusError();
                        showAuthForm();
                    }
                }, 1000);
                return;
            }

            authCheckCompleted = true;
            isCheckingAuth = false;
            showLoginStatusError();
            showAuthForm();
        }
    } catch (error) {
        console.error('❌ 檢查認證狀態錯誤:', error);
        authCheckCompleted = true;
        isCheckingAuth = false;
        showLoginStatusError();
        showAuthForm();
    }
}

// ==================== 界面切換函數 ====================

/**
 * 顯示認證表單
 */
function showAuthForm() {
    // 防禦性檢查：如果當前在 message_downloader 主頁面且剛從登入頁面過來，給一點延遲時間
    if (window.location.pathname === '/message_downloader' && document.referrer.includes('/login')) {
        console.log('🔄 從登入頁面跳轉，延遲檢查認證狀態...');
        // 重置認證檢查狀態，允許重新檢查
        authCheckCompleted = false;
        isCheckingAuth = false;
        setTimeout(() => {
            checkAuthStatus();
        }, 500);
        return;
    }

    const authSection = document.getElementById('auth-section');
    const mainLayout = document.getElementById('main-app-layout');

    console.log('👤 顯示認證表單');
    if (authSection) authSection.style.display = 'block';
    if (mainLayout) mainLayout.style.display = 'none';

    setupAuthEventListeners();
}

/**
 * 顯示認證成功後的主界面
 * @param {Object} userInfo - 用戶資訊
 */
function showAuthSuccess(userInfo) {
    const authSection = document.getElementById('auth-section');
    const mainLayout = document.getElementById('main-app-layout');

    if (authSection) authSection.style.display = 'none';
    if (mainLayout) mainLayout.style.display = 'flex';

    // Show success message in a temporary alert
    const userName = userInfo.first_name || userInfo.phone_number || 'User';
    showAlert(`認證成功！歡迎，${userName}`, 'success');
}

// ==================== 登入狀態指示器函數 ====================

/**
 * 顯示登入狀態載入中
 */
function showLoginStatusLoading() {
    const loginStatus = document.getElementById('login-status');
    const loading = document.getElementById('login-status-loading');
    const success = document.getElementById('login-status-success');
    const error = document.getElementById('login-status-error');

    if (loginStatus) loginStatus.style.display = 'block';
    if (loading) loading.style.display = 'block';
    if (success) success.style.display = 'none';
    if (error) error.style.display = 'none';
}

/**
 * 顯示登入狀態成功
 * @param {Object} userInfo - 用戶資訊
 */
function showLoginStatusSuccess(userInfo) {
    const loginStatus = document.getElementById('login-status');
    const loading = document.getElementById('login-status-loading');
    const success = document.getElementById('login-status-success');
    const error = document.getElementById('login-status-error');

    if (loginStatus) loginStatus.style.display = 'block';
    if (loading) loading.style.display = 'none';
    if (success) success.style.display = 'block';
    if (error) error.style.display = 'none';

    const userName = userInfo.first_name || userInfo.phone_number || 'User';
    const userInfoElement = document.getElementById('login-user-info');
    if (userInfoElement) {
        userInfoElement.textContent = `: ${userName}`;
    }
}

/**
 * 顯示登入狀態錯誤
 */
function showLoginStatusError() {
    const loginStatus = document.getElementById('login-status');
    const loading = document.getElementById('login-status-loading');
    const success = document.getElementById('login-status-success');
    const error = document.getElementById('login-status-error');

    if (loginStatus) loginStatus.style.display = 'block';
    if (loading) loading.style.display = 'none';
    if (success) success.style.display = 'none';
    if (error) error.style.display = 'block';
}

/**
 * 隱藏登入狀態
 */
function hideLoginStatus() {
    const loginStatus = document.getElementById('login-status');
    if (loginStatus) {
        loginStatus.style.display = 'none';
    }
}

// ==================== 事件監聽器設置 ====================

/**
 * 設置認證相關的事件監聽器
 */
function setupAuthEventListeners() {
    // Authentication form buttons (only set up if not already done)
    const sendCodeBtn = document.getElementById('send-code-btn');
    const verifyCodeBtn = document.getElementById('verify-code-btn');
    const verifyPasswordBtn = document.getElementById('verify-password-btn');
    const phoneInput = document.getElementById('phone-number');
    const codeInput = document.getElementById('verification-code');
    const passwordInput = document.getElementById('two-factor-password');

    if (sendCodeBtn && !sendCodeBtn.hasAttribute('data-listener-added')) {
        sendCodeBtn.addEventListener('click', sendVerificationCode);
        sendCodeBtn.setAttribute('data-listener-added', 'true');
    }
    if (verifyCodeBtn && !verifyCodeBtn.hasAttribute('data-listener-added')) {
        verifyCodeBtn.addEventListener('click', verifyCode);
        verifyCodeBtn.setAttribute('data-listener-added', 'true');
    }
    if (verifyPasswordBtn && !verifyPasswordBtn.hasAttribute('data-listener-added')) {
        verifyPasswordBtn.addEventListener('click', verifyPassword);
        verifyPasswordBtn.setAttribute('data-listener-added', 'true');
    }

    // Enter key handlers
    if (phoneInput && !phoneInput.hasAttribute('data-listener-added')) {
        phoneInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendVerificationCode();
        });
        phoneInput.setAttribute('data-listener-added', 'true');
    }

    if (codeInput && !codeInput.hasAttribute('data-listener-added')) {
        codeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') verifyCode();
        });
        codeInput.setAttribute('data-listener-added', 'true');
    }

    if (passwordInput && !passwordInput.hasAttribute('data-listener-added')) {
        passwordInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') verifyPassword();
        });
        passwordInput.setAttribute('data-listener-added', 'true');
    }
}

// ==================== 認證流程函數 ====================

/**
 * 發送驗證碼
 */
async function sendVerificationCode() {
    const phoneNumber = document.getElementById('phone-number').value.trim();
    const sendBtn = document.getElementById('send-code-btn');

    if (!phoneNumber) {
        showAlert('請輸入電話號碼', 'warning');
        return;
    }

    // Show loading state
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 發送中...';

    try {
        const response = await fetch('/api/auth/send_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                phone_number: phoneNumber,
                api_id: 29060182,  // From config
                api_hash: '071ea901d6271a50e8f86b403b244826'  // From config
            })
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById('auth-phone-step').style.display = 'none';
            document.getElementById('auth-code-step').style.display = 'block';
            showAlert('驗證碼已發送，請檢查您的 Telegram', 'info');
        } else {
            showAlert('發送驗證碼失敗: ' + data.error, 'danger');
            // Reset button on error
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i> 發送驗證碼';
        }
    } catch (error) {
        console.error('發送驗證碼錯誤:', error);
        showAlert('發送驗證碼時發生錯誤', 'danger');
        // Reset button on error
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i> 發送驗證碼';
    }
}

/**
 * 驗證驗證碼
 */
async function verifyCode() {
    const verificationCode = document.getElementById('verification-code').value.trim();

    if (!verificationCode) {
        showAlert('請輸入驗證碼', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/auth/verify_code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                verification_code: verificationCode
            })
        });

        const data = await response.json();

        if (data.success) {
            if (data.requires_password) {
                document.getElementById('auth-code-step').style.display = 'none';
                document.getElementById('auth-password-step').style.display = 'block';
                showAlert('需要兩步驗證密碼', 'info');
            } else {
                // 認證成功，重置認證檢查狀態
                resetAuthStatus();
                showLoginStatusSuccess(data.user_info);
                showAuthSuccess(data.user_info);
                loadGroups();
            }
        } else {
            showAlert('驗證碼驗證失敗: ' + data.error, 'danger');
        }
    } catch (error) {
        console.error('驗證碼驗證錯誤:', error);
        showAlert('驗證碼驗證時發生錯誤', 'danger');
    }
}

/**
 * 驗證兩步驗證密碼
 */
async function verifyPassword() {
    const password = document.getElementById('two-factor-password').value.trim();

    if (!password) {
        showAlert('請輸入密碼', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/auth/verify_password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                password: password
            })
        });

        const data = await response.json();

        if (data.success) {
            // 認證成功，重置認證檢查狀態
            resetAuthStatus();
            showLoginStatusSuccess(data.user_info);
            showAuthSuccess(data.user_info);
            loadGroups();
        } else {
            showAlert('密碼驗證失敗: ' + data.error, 'danger');
        }
    } catch (error) {
        console.error('密碼驗證錯誤:', error);
        showAlert('密碼驗證時發生錯誤', 'danger');
    }
}

/**
 * 登出
 */
async function logout() {
    // 重置認證狀態
    resetAuthStatus();

    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showAlert('已成功登出', 'info');
            // 跳轉到登入頁面而不是顯示認證表單
            setTimeout(() => {
                window.location.href = '/message_downloader/login';
            }, 1000); // 給用戶時間看到登出成功訊息
        } else {
            showAlert('登出失敗: ' + data.error, 'danger');
        }
    } catch (error) {
        console.error('登出錯誤:', error);
        showAlert('登出時發生錯誤', 'danger');
    }
}