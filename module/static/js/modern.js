/**
 * Modern Telegram Downloader Interface
 * A complete rewrite of the UI with modern JavaScript practices
 */

const ModernTelegramDownloader = {
  // State management
  state: {
    currentTab: 'download-manager',
    downloadProgress: {
      active: false,
      total: 0,
      completed: 0,
      concurrentFiles: {}
    },
    selectedTasks: new Set(),
    selectedGroups: new Set(),
    groups: [],
    downloadHistory: [],
    pagination: {
      page: 1,
      limit: 20,  // 減少每頁顯示筆數
      total: 0
    },
    filters: {
      group: '',
      status: ''
    },
    completionReloadScheduled: false  // 防止重複的完成後刷新
  },

  // Configuration
  config: {
    progressUpdateInterval: 1000,
    retryAttempts: 3,
    debounceDelay: 300
  },

  // Initialize the application
  init() {
    this.setupEventListeners();
    this.loadAppVersion();
    this.loadGroups();
    this.loadDownloadHistory();
    this.startProgressUpdates();
    this.initSessionMonitoring();
    console.log('Modern Telegram Downloader initialized');
  },

  // Event listeners setup
  setupEventListeners() {
    // Tab navigation
    document.querySelectorAll('.modern-tabs-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const tabId = e.target.getAttribute('data-tab') || e.target.closest('[data-tab]').getAttribute('data-tab');
        this.switchTab(tabId);
      });
    });

    // Forms
    const customDownloadForm = document.getElementById('custom-download-form');
    if (customDownloadForm) {
      customDownloadForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleAddCustomDownload(new FormData(customDownloadForm));
      });
    }

    const addGroupForm = document.getElementById('add-group-form');
    if (addGroupForm) {
      addGroupForm.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleAddGroup(new FormData(addGroupForm));
      });
    }

    // Filter controls
    document.getElementById('group-filter')?.addEventListener('change', this.debounce(() => {
      this.state.filters.group = document.getElementById('group-filter').value;
      this.applyFilters();
    }, this.config.debounceDelay));

    document.getElementById('status-filter')?.addEventListener('change', this.debounce(() => {
      this.state.filters.status = document.getElementById('status-filter').value;
      this.applyFilters();
    }, this.config.debounceDelay));

    // Items per page selector
    document.getElementById('items-per-page')?.addEventListener('change', (e) => {
      this.state.pagination.limit = parseInt(e.target.value);
      this.state.pagination.page = 1; // Reset to first page
      this.loadDownloadHistory();
    });

    // Global keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case 'a':
            e.preventDefault();
            this.selectAllTasks();
            break;
          case 'Enter':
            e.preventDefault();
            this.startSelectedDownloads();
            break;
        }
      }
    });
  },

  // Tab switching
  switchTab(tabId) {
    // Update active tab
    document.querySelectorAll('.modern-tabs-link').forEach(link => link.classList.remove('active'));
    document.querySelectorAll('.modern-tabs-panel').forEach(panel => panel.classList.remove('active'));
    
    document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
    document.getElementById(tabId).classList.add('active');
    
    this.state.currentTab = tabId;

    // Load tab-specific data
    if (tabId === 'group-manager') {
      this.loadGroups();
    } else if (tabId === 'download-manager') {
      this.loadDownloadHistory();
    }
  },

  // Load application version
  async loadAppVersion() {
    try {
      const response = await fetch('/get_app_version');
      const version = await response.text();
      document.getElementById('app-version').textContent = version;
    } catch (error) {
      console.error('Failed to load app version:', error);
    }
  },

  // Load groups
  async loadGroups() {
    try {
      const response = await fetch('/get_groups');
      const data = await response.json();
      
      if (data.success) {
        this.state.groups = data.groups;
        this.renderGroups();
        this.updateGroupSelects();
      } else {
        this.showNotification('載入群組失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to load groups:', error);
      this.showNotification('載入群組時發生錯誤', 'error');
    }
  },

  // Render groups list
  renderGroups() {
    const container = document.getElementById('groups-list');
    if (!container) return;

    if (this.state.groups.length === 0) {
      container.innerHTML = `
        <div class="progress-empty-state">
          <svg class="progress-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
          <div class="progress-empty-title">尚未新增任何群組</div>
          <div class="progress-empty-description">請在上方表單中新增群組以開始使用</div>
        </div>
      `;
      return;
    }

    container.innerHTML = this.state.groups.map(group => `
      <div class="modern-list-item" data-group-id="${group.chat_id}">
        <div class="modern-checkbox">
          <input type="checkbox" class="modern-checkbox-input group-checkbox" value="${group.chat_id}">
          <div class="modern-checkbox-mark"></div>
        </div>
        
        <div class="modern-list-content">
          <div class="modern-list-title">${this.escapeHtml(group.name)}</div>
          <div class="modern-list-subtitle">
            Chat ID: <span class="font-mono">${group.chat_id}</span> • 
            待下載: <span class="modern-badge modern-badge-pending">${group.pending_count}</span>
          </div>
        </div>
        
        <div class="modern-list-actions">
          <button class="modern-btn modern-btn-sm modern-btn-secondary" onclick="ModernTelegramDownloader.editGroup('${group.chat_id}', '${this.escapeHtml(group.name)}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            編輯
          </button>
          <button class="modern-btn modern-btn-sm modern-btn-warning" onclick="ModernTelegramDownloader.clearGroupMessages('${group.chat_id}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 6h18"/>
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
            </svg>
            清空
          </button>
          <button class="modern-btn modern-btn-sm modern-btn-danger" onclick="ModernTelegramDownloader.deleteGroup('${group.chat_id}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3,6 5,6 21,6"/>
              <path d="M19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6M8,6V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"/>
            </svg>
            刪除
          </button>
        </div>
      </div>
    `).join('');

    // Add event listeners for group checkboxes
    container.querySelectorAll('.group-checkbox').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        const groupId = e.target.value;
        const listItem = e.target.closest('.modern-list-item');
        
        if (e.target.checked) {
          this.state.selectedGroups.add(groupId);
          listItem.classList.add('selected');
        } else {
          this.state.selectedGroups.delete(groupId);
          listItem.classList.remove('selected');
        }
      });
    });

    // Add click event listeners to group list items for row selection
    container.querySelectorAll('.modern-list-item').forEach(listItem => {
      listItem.addEventListener('click', (e) => {
        // Don't trigger if clicking on checkbox, button, or other interactive elements
        if (e.target.closest('.modern-checkbox, .modern-btn, button, a')) {
          return;
        }
        
        const checkbox = listItem.querySelector('.group-checkbox');
        if (checkbox) {
          checkbox.checked = !checkbox.checked;
          checkbox.dispatchEvent(new Event('change'));
        }
      });
    });
  },

  // Update group selects in forms
  updateGroupSelects() {
    const groupSelect = document.getElementById('group-select');
    const groupFilter = document.getElementById('group-filter');
    
    if (groupSelect) {
      groupSelect.innerHTML = '<option value="">請選擇群組...</option>' +
        this.state.groups.map(group => `<option value="${group.chat_id}">${this.escapeHtml(group.name)}</option>`).join('');
    }

    if (groupFilter) {
      const currentValue = groupFilter.value;
      groupFilter.innerHTML = '<option value="">🔍 全部群組</option>' +
        this.state.groups.map(group => `<option value="${this.escapeHtml(group.name)}">${this.escapeHtml(group.name)}</option>`).join('');
      groupFilter.value = currentValue;
    }
  },

  // Load download history
  async loadDownloadHistory(forceRefresh = false) {
    try {
      const params = new URLSearchParams({
        page: this.state.pagination.page,
        limit: this.state.pagination.limit,
        group_filter: this.state.filters.group,
        status_filter: this.state.filters.status
      });

      // Add cache-busting parameter when forcing refresh (after download completion)
      if (forceRefresh) {
        params.set('_t', Date.now().toString());
      }

      const response = await fetch('/get_download_history?' + params);
      const data = await response.json();
      
      if (data.success) {
        this.state.downloadHistory = data.history;
        this.state.pagination = data.pagination;
        this.renderDownloadHistory();
        this.updateSummaryCards();
        this.updateFilteredCount();
      } else {
        this.showNotification('載入下載歷史失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to load download history:', error);
      this.showNotification('載入下載歷史時發生錯誤', 'error');
    }
  },

  // Render download history
  renderDownloadHistory() {
    const container = document.getElementById('download-history-list');
    if (!container) return;

    if (this.state.downloadHistory.length === 0) {
      container.innerHTML = `
        <div class="progress-empty-state">
          <svg class="progress-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7,10 12,15 17,10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          <div class="progress-empty-title">尚無下載記錄</div>
          <div class="progress-empty-description">新增下載任務後將會顯示在這裡</div>
        </div>
      `;
      return;
    }

    container.innerHTML = this.state.downloadHistory.map(item => {
      const statusClass = this.getStatusClass(item.status);
      const statusText = this.getStatusText(item.status);
      const isSelected = this.state.selectedTasks.has(`${item.chat_id}_${item.message_id}`);
      
      return `
        <div class="modern-list-item ${isSelected ? 'selected' : ''} ${item.auto_select ? 'animate-fade-in' : ''}" 
             data-task-id="${item.chat_id}_${item.message_id}">
          <div class="modern-checkbox">
            <input type="checkbox" class="modern-checkbox-input task-checkbox" 
                   value="${item.chat_id}_${item.message_id}" ${isSelected ? 'checked' : ''}>
            <div class="modern-checkbox-mark"></div>
          </div>
          
          <div class="modern-list-content">
            <div class="modern-list-title">${this.escapeHtml(item.chat_name)}</div>
            <div class="modern-list-subtitle">
              訊息ID: <span class="font-mono">${item.message_id}</span> • 
              時間: ${item.timestamp}
            </div>
          </div>
          
          <div class="modern-list-actions">
            <span class="modern-badge ${statusClass}">${statusText}</span>
            ${item.status === 'failed_ids' || item.status === 'failed' ? `
              <button class="modern-btn modern-btn-sm modern-btn-warning" onclick="ModernTelegramDownloader.retryDownload('${item.chat_id}', '${item.message_id}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M1 4v6h6"/>
                  <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                </svg>
                重試
              </button>
            ` : ''}
          </div>
        </div>
      `;
    }).join('');

    // Add event listeners for task checkboxes
    container.querySelectorAll('.task-checkbox').forEach(checkbox => {
      checkbox.addEventListener('change', (e) => {
        const taskId = e.target.value;
        const listItem = e.target.closest('.modern-list-item');
        
        if (e.target.checked) {
          this.state.selectedTasks.add(taskId);
          listItem.classList.add('selected');
        } else {
          this.state.selectedTasks.delete(taskId);
          listItem.classList.remove('selected');
        }
        
        this.updateSelectedCount();
      });
    });

    // Add click event listeners to list items for row selection
    container.querySelectorAll('.modern-list-item').forEach(listItem => {
      listItem.addEventListener('click', (e) => {
        // Don't trigger if clicking on checkbox, button, or other interactive elements
        if (e.target.closest('.modern-checkbox, .modern-btn, button, a')) {
          return;
        }
        
        const checkbox = listItem.querySelector('.task-checkbox');
        if (checkbox) {
          checkbox.checked = !checkbox.checked;
          checkbox.dispatchEvent(new Event('change'));
        }
      });
    });

    this.renderPagination();
  },

  // Render pagination
  renderPagination() {
    const container = document.getElementById('pagination-container');
    if (!container || this.state.pagination.total_pages <= 1) {
      if (container) container.innerHTML = '';
      return;
    }

    const currentPage = this.state.pagination.page;
    const totalPages = this.state.pagination.total_pages;
    
    let paginationHtml = '<div class="flex items-center gap-sm">';
    
    // Previous button
    paginationHtml += `
      <button class="modern-btn modern-btn-sm modern-btn-secondary" 
              ${currentPage <= 1 ? 'disabled' : ''} 
              onclick="ModernTelegramDownloader.goToPage(${currentPage - 1})">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15,18 9,12 15,6"/>
        </svg>
        上一頁
      </button>
    `;

    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    if (startPage > 1) {
      paginationHtml += `<button class="modern-btn modern-btn-sm modern-btn-secondary" onclick="ModernTelegramDownloader.goToPage(1)">1</button>`;
      if (startPage > 2) {
        paginationHtml += '<span class="text-secondary">...</span>';
      }
    }

    for (let i = startPage; i <= endPage; i++) {
      paginationHtml += `
        <button class="modern-btn modern-btn-sm ${i === currentPage ? 'modern-btn-primary' : 'modern-btn-secondary'}" 
                onclick="ModernTelegramDownloader.goToPage(${i})">
          ${i}
        </button>
      `;
    }

    if (endPage < totalPages) {
      if (endPage < totalPages - 1) {
        paginationHtml += '<span class="text-secondary">...</span>';
      }
      paginationHtml += `<button class="modern-btn modern-btn-sm modern-btn-secondary" onclick="ModernTelegramDownloader.goToPage(${totalPages})">${totalPages}</button>`;
    }

    // Next button
    paginationHtml += `
      <button class="modern-btn modern-btn-sm modern-btn-secondary" 
              ${currentPage >= totalPages ? 'disabled' : ''} 
              onclick="ModernTelegramDownloader.goToPage(${currentPage + 1})">
        下一頁
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9,18 15,12 9,6"/>
        </svg>
      </button>
    `;

    paginationHtml += '</div>';
    container.innerHTML = paginationHtml;
  },

  // Go to specific page
  goToPage(page) {
    this.state.pagination.page = page;
    this.loadDownloadHistory();
  },

  // Update summary cards
  updateSummaryCards() {
    const counts = this.state.downloadHistory.reduce((acc, item) => {
      const status = item.status;
      if (status === 'pending') acc.pending++;
      else if (status === 'downloading') acc.downloading++;
      else if (status === 'downloaded_ids' || status === 'downloaded') acc.completed++;
      else if (status === 'failed_ids' || status === 'failed') acc.failed++;
      return acc;
    }, { pending: 0, downloading: 0, completed: 0, failed: 0 });

    document.getElementById('summary-pending').textContent = counts.pending;
    document.getElementById('summary-downloading').textContent = counts.downloading;
    document.getElementById('summary-completed').textContent = counts.completed;
    document.getElementById('summary-failed').textContent = counts.failed;
  },

  // Update selected count display
  updateSelectedCount() {
    const count = this.state.selectedTasks.size;
    const countElement = document.getElementById('selected-count');
    const badgeElement = document.getElementById('selected-count-badge');
    const startButton = document.getElementById('start-download-btn');
    
    if (countElement) countElement.textContent = count;
    
    // Update badge appearance based on count
    if (badgeElement) {
      if (count > 0) {
        badgeElement.style.background = 'linear-gradient(135deg, var(--success-green), #2FA748)';
        badgeElement.style.transform = 'scale(1.05)';
      } else {
        badgeElement.style.background = 'linear-gradient(135deg, var(--text-secondary), #666)';
        badgeElement.style.transform = 'scale(1)';
      }
    }
    
    // Enable/disable start button
    if (startButton) {
      startButton.disabled = count === 0;
      if (count > 0) {
        startButton.classList.add('pulse-ready');
      } else {
        startButton.classList.remove('pulse-ready');
      }
    }
  },

  // Update filtered count
  updateFilteredCount() {
    const count = this.state.downloadHistory.length;
    const total = this.state.pagination.total;
    document.getElementById('filtered-count').textContent = `📋 顯示：${count} / ${total} 項目`;
  },

  // Apply filters
  applyFilters() {
    this.state.pagination.page = 1; // Reset to first page
    this.loadDownloadHistory();
  },

  // Clear filters
  clearFilters() {
    document.getElementById('group-filter').value = '';
    document.getElementById('status-filter').value = '';
    this.state.filters.group = '';
    this.state.filters.status = '';
    this.applyFilters();
  },

  // Handle add custom download
  async handleAddCustomDownload(formData) {
    const chatId = formData.get('chat_id');
    const messageIds = formData.get('message_ids');

    if (!chatId || !messageIds) {
      this.showNotification('請填寫所有必需欄位', 'warning');
      return;
    }

    try {
      const response = await fetch('/add_custom_download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chat_id: chatId,
          message_ids: messageIds
        })
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        document.getElementById('custom-download-form').reset();
        
        // Parse the message IDs and auto-select them after refresh
        const newTaskIds = messageIds.split(',').map(id => `${chatId}_${id.trim()}`);
        
        // Refresh the history and auto-select new items
        await this.loadDownloadHistory();
        
        // Auto-select the newly added tasks
        newTaskIds.forEach(taskId => {
          this.state.selectedTasks.add(taskId);
          const checkbox = document.querySelector(`.task-checkbox[value="${taskId}"]`);
          if (checkbox) {
            checkbox.checked = true;
            checkbox.closest('.modern-list-item').classList.add('selected');
          }
        });
        
        this.updateSelectedCount();
      } else {
        this.showNotification('新增失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to add custom download:', error);
      this.showNotification('新增時發生錯誤', 'error');
    }
  },

  // Handle add group
  async handleAddGroup(formData) {
    const chatId = formData.get('chat_id');
    const name = formData.get('name');

    if (!chatId || !name) {
      this.showNotification('請填寫所有必需欄位', 'warning');
      return;
    }

    try {
      const response = await fetch('/add_group', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chat_id: chatId,
          name: name
        })
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        document.getElementById('add-group-form').reset();
        this.loadGroups(); // Refresh the groups
      } else {
        this.showNotification('新增群組失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to add group:', error);
      this.showNotification('新增群組時發生錯誤', 'error');
    }
  },

  // Start selected downloads
  async startSelectedDownloads() {
    const selectedTasks = Array.from(this.state.selectedTasks).map(taskId => {
      const [chatId, messageId] = taskId.split('_');
      return { chat_id: chatId, message_id: messageId };
    });

    if (selectedTasks.length === 0) {
      this.showNotification('請先選擇要下載的項目', 'warning');
      return;
    }

    try {
      const response = await fetch('/start_selected_download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tasks: selectedTasks })
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        this.state.selectedTasks.clear();
        this.updateSelectedCount();
        this.showDownloadProgress();
        updateDownloadControls('downloading');
      } else {
        this.showNotification('啟動下載失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to start downloads:', error);
      this.showNotification('啟動下載時發生錯誤', 'error');
    }
  },

  // Show download progress
  showDownloadProgress() {
    const progressArea = document.getElementById('download-progress-area');
    if (progressArea) {
      progressArea.style.display = 'block';
      progressArea.scrollIntoView({ behavior: 'smooth' });
    }
  },

  // Start progress updates
  startProgressUpdates() {
    setInterval(async () => {
      try {
        const response = await fetch('/get_download_progress');
        const data = await response.json();
        
        if (data.success) {
          this.updateProgressDisplay(data);
        }
      } catch (error) {
        console.error('Failed to update progress:', error);
      }
    }, this.config.progressUpdateInterval);
  },

  // Update progress display
  updateProgressDisplay(data) {
    console.log('updateProgressDisplay called with data:', data);
    
    // Update overall progress
    const percentage = data.total_count > 0 ? Math.round((data.completed_count / data.total_count) * 100) : 0;
    
    const completedEl = document.getElementById('overall-completed');
    const totalEl = document.getElementById('overall-total');
    const speedEl = document.getElementById('overall-speed');
    const statusEl = document.getElementById('overall-status-text');
    
    if (completedEl) completedEl.textContent = data.completed_count || 0;
    if (totalEl) totalEl.textContent = data.total_count || 0;
    if (speedEl) speedEl.textContent = data.total_download_speed || '0.00 B/s';
    if (statusEl) statusEl.textContent = data.status_text || '準備中...';
    
    const progressBar = document.getElementById('overall-progress-bar');
    const progressText = document.getElementById('overall-progress-text');
    
    if (progressBar) {
      progressBar.style.width = percentage + '%';
      // Store the percentage as a data attribute for reliable access
      progressBar.setAttribute('data-percentage', percentage);
    }
    if (progressText) {
      progressText.textContent = percentage + '%';
    }
    
    console.log('Updated hidden progress elements:', {
      completed: data.completed_count,
      total: data.total_count,
      percentage: percentage + '%',
      speed: data.total_download_speed
    });
    
    // Immediately sync to floating window
    setTimeout(() => {
      syncFloatingProgressData();
      syncMinimizedProgressData();
    }, 50);

    // Show/hide progress area
    const progressArea = document.getElementById('download-progress-area');
    const concurrentSection = document.getElementById('concurrent-downloads-section');
    
    if (data.active && data.total_count > 0) {
      // Keep progress area hidden - all progress shown in floating window
      // if (progressArea) progressArea.style.display = 'block';
      
      // Only update to downloading state if not already paused
      const pauseBtn = document.getElementById('pause-download-btn');
      const resumeBtn = document.getElementById('resume-download-btn');
      const isCurrentlyPaused = pauseBtn && pauseBtn.style.display === 'none' && resumeBtn && resumeBtn.style.display !== 'none';
      
      if (!isCurrentlyPaused) {
        updateDownloadControls('downloading');
      }
      
      // Update concurrent downloads (hidden in main view, shown in floating window)
      if (data.current_files && Object.keys(data.current_files).length > 0) {
        // if (concurrentSection) concurrentSection.style.display = 'block';
        this.updateConcurrentDownloads(data.current_files);
        // Update floating concurrent section
        this.updateFloatingConcurrentDownloads(data.current_files);
      } else {
        // Clear concurrent count when no files
        const countBadge = document.getElementById('concurrent-count');
        if (countBadge) countBadge.textContent = '0';
        // if (concurrentSection) concurrentSection.style.display = 'none';
      }
    } else {
      if (progressArea) progressArea.style.display = 'none';
      
      // Check if download was completed or cancelled
      if (data.total_count > 0 && data.completed_count >= data.total_count) {
        updateDownloadControls('completed');
        // Only reload once after completion to avoid infinite API calls
        if (!this.completionReloadScheduled) {
          this.completionReloadScheduled = true;
          setTimeout(() => {
            this.loadDownloadHistory(true);
            this.completionReloadScheduled = false;
          }, 3000);
        }
      } else if (!data.active && data.total_count === 0) {
        updateDownloadControls('completed');
      }
    }
  },

  // Update floating concurrent downloads display
  updateFloatingConcurrentDownloads(currentFiles) {
    const floatingContainer = document.getElementById('floating-concurrent-container');
    const floatingSection = document.getElementById('floating-concurrent-section');
    const floatingCount = document.getElementById('floating-concurrent-count');
    
    console.log('🔄 updateFloatingConcurrentDownloads called with:', currentFiles);
    
    if (!floatingContainer || !floatingSection || !floatingCount) {
      console.log('❌ Missing floating concurrent elements:', {
        container: !!floatingContainer,
        section: !!floatingSection,
        count: !!floatingCount
      });
      return;
    }
    
    const fileCount = Object.keys(currentFiles).length;
    floatingCount.textContent = fileCount;
    console.log(`📁 Processing ${fileCount} concurrent files`);
    
    if (fileCount > 0) {
      floatingSection.style.display = 'block';
      floatingContainer.innerHTML = '';
      
      Object.entries(currentFiles).forEach(([filename, fileInfo]) => {
        const item = document.createElement('div');
        item.className = 'floating-concurrent-item';
        
        // 計算文件進度百分比
        const downloadedBytes = fileInfo.downloaded_bytes || 0;
        const totalBytes = fileInfo.total_bytes || 0;
        const percentage = totalBytes > 0 ? Math.round((downloadedBytes / totalBytes) * 100) : 0;
        
        // 格式化下載速度
        const speed = fileInfo.download_speed || 0;
        const formattedSpeed = ModernTelegramDownloader.formatBytes(speed) + '/s';
        
        // 使用實際文件名稱
        const displayName = fileInfo.name || filename;
        
        console.log(`🔄 Updating concurrent file: ${displayName}, Progress: ${percentage}%, Speed: ${formattedSpeed}`);
        
        item.innerHTML = `
          <div class="floating-concurrent-file-info">
            <div class="floating-concurrent-filename" title="${displayName}">${displayName}</div>
            <div class="floating-concurrent-progress-info">
              <span class="floating-concurrent-speed">${formattedSpeed}</span>
              <span class="floating-concurrent-percentage">${percentage}%</span>
            </div>
          </div>
          <div class="floating-concurrent-progress-bar">
            <div class="floating-concurrent-progress-fill" style="width: ${percentage}%"></div>
          </div>
        `;
        floatingContainer.appendChild(item);
      });
    } else {
      floatingSection.style.display = 'none';
    }
  },

  // Update concurrent downloads display
  updateConcurrentDownloads(files) {
    const container = document.getElementById('concurrent-downloads-container');
    const countBadge = document.getElementById('concurrent-count');
    
    if (!container || !countBadge) return;

    const fileEntries = Object.entries(files);
    countBadge.textContent = fileEntries.length;

    container.innerHTML = fileEntries.map(([fileKey, file]) => {
      const percentage = file.total_bytes > 0 ? Math.round((file.downloaded_bytes / file.total_bytes) * 100) : 0;
      const downloadedSize = this.formatBytes(file.downloaded_bytes);
      const totalSize = this.formatBytes(file.total_bytes);
      const speed = this.formatBytes(file.download_speed) + '/s';

      return `
        <div class="file-progress-item">
          <div class="file-progress-header">
            <div class="file-info">
              <div class="file-name" title="${this.escapeHtml(file.name)}">${this.escapeHtml(file.name)}</div>
              <div class="file-stats">
                <span class="file-size">${downloadedSize} / ${totalSize}</span>
                <span class="download-speed">${speed}</span>
                <span>ID: ${file.message_id}</span>
              </div>
            </div>
          </div>
          <div class="file-progress">
            <div class="file-progress-bar" style="width: ${percentage}%"></div>
          </div>
        </div>
      `;
    }).join('');
  },

  // Task selection methods
  selectAllTasks() {
    const checkboxes = document.querySelectorAll('.task-checkbox');
    checkboxes.forEach(checkbox => {
      checkbox.checked = true;
      const taskId = checkbox.value;
      this.state.selectedTasks.add(taskId);
      checkbox.closest('.modern-list-item').classList.add('selected');
    });
    this.updateSelectedCount();
  },

  selectPendingTasks() {
    this.state.selectedTasks.clear();
    document.querySelectorAll('.modern-list-item').forEach(item => {
      const badge = item.querySelector('.modern-badge');
      const checkbox = item.querySelector('.task-checkbox');
      
      if (badge && badge.classList.contains('modern-badge-pending')) {
        checkbox.checked = true;
        this.state.selectedTasks.add(checkbox.value);
        item.classList.add('selected');
      } else {
        checkbox.checked = false;
        item.classList.remove('selected');
      }
    });
    this.updateSelectedCount();
  },

  deselectAllTasks() {
    const checkboxes = document.querySelectorAll('.task-checkbox');
    checkboxes.forEach(checkbox => {
      checkbox.checked = false;
      checkbox.closest('.modern-list-item').classList.remove('selected');
    });
    this.state.selectedTasks.clear();
    this.updateSelectedCount();
  },

  // Group management methods
  async editGroup(chatId, currentName) {
    const newName = prompt('請輸入新的群組名稱:', currentName);
    if (!newName || newName === currentName) return;

    try {
      const response = await fetch('/edit_group', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chat_id: chatId,
          name: newName
        })
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        this.loadGroups();
      } else {
        this.showNotification('編輯失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to edit group:', error);
      this.showNotification('編輯時發生錯誤', 'error');
    }
  },

  async deleteGroup(chatId) {
    if (!confirm('確定要刪除這個群組嗎？這將會移除所有相關的下載任務。')) return;

    try {
      const response = await fetch('/delete_group', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ chat_id: chatId })
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        this.loadGroups();
      } else {
        this.showNotification('刪除失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to delete group:', error);
      this.showNotification('刪除時發生錯誤', 'error');
    }
  },

  async clearGroupMessages(chatId) {
    if (!confirm('確定要清空這個群組的所有下載任務嗎？')) return;

    try {
      const response = await fetch('/clear_download_ids', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ chat_id: chatId })
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        this.loadGroups();
        this.loadDownloadHistory();
      } else {
        this.showNotification('清空失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to clear group messages:', error);
      this.showNotification('清空時發生錯誤', 'error');
    }
  },

  // Retry download
  async retryDownload(chatId, messageId) {
    try {
      const response = await fetch('/retry_download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chat_id: chatId,
          message_id: messageId
        })
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        this.loadDownloadHistory();
      } else {
        this.showNotification('重試失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to retry download:', error);
      this.showNotification('重試時發生錯誤', 'error');
    }
  },

  // Clean downloaded items
  async cleanDownloadedItems() {
    if (!confirm('確定要清理已下載的項目嗎？這將從待下載列表中移除已完成的項目。')) return;

    try {
      const response = await fetch('/clean_downloaded_from_targets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        this.loadDownloadHistory();
      } else {
        this.showNotification('清理失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to clean downloaded items:', error);
      this.showNotification('清理時發生錯誤', 'error');
    }
  },

  // Remove selected tasks
  async removeSelectedTasks() {
    const selectedTasks = Array.from(this.state.selectedTasks).map(taskId => {
      const [chatId, messageId] = taskId.split('_');
      return { chat_id: chatId, message_id: messageId };
    });

    if (selectedTasks.length === 0) {
      this.showNotification('請先選擇要移除的項目', 'warning');
      return;
    }

    if (!confirm(`確定要移除選中的 ${selectedTasks.length} 個項目嗎？`)) return;

    try {
      const response = await fetch('/remove_selected_tasks', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tasks: selectedTasks })
      });

      const data = await response.json();
      
      if (data.success) {
        this.showNotification(data.message, 'success');
        this.state.selectedTasks.clear();
        this.loadDownloadHistory();
      } else {
        this.showNotification('移除失敗: ' + (data.error || '未知錯誤'), 'error');
      }
    } catch (error) {
      console.error('Failed to remove tasks:', error);
      this.showNotification('移除時發生錯誤', 'error');
    }
  },

  // Helper methods
  getStatusClass(status) {
    switch (status) {
      case 'pending': return 'modern-badge-pending';
      case 'downloading': return 'modern-badge-downloading';
      case 'downloaded_ids':
      case 'downloaded': return 'modern-badge-completed';
      case 'failed_ids':
      case 'failed': return 'modern-badge-failed';
      default: return 'modern-badge-pending';
    }
  },

  getStatusText(status) {
    switch (status) {
      case 'pending': return '待下載';
      case 'downloading': return '下載中';
      case 'downloaded_ids':
      case 'downloaded': return '已完成';
      case 'failed_ids':
      case 'failed': return '失敗';
      default: return '未知';
    }
  },

  formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 16px 24px;
      background: ${type === 'success' ? 'var(--success-green)' : 
                   type === 'error' ? 'var(--error-red)' : 
                   type === 'warning' ? 'var(--warning-orange)' : 'var(--primary-blue)'};
      color: white;
      border-radius: var(--radius-md);
      box-shadow: var(--shadow-lg);
      z-index: 1000;
      max-width: 400px;
      opacity: 0;
      transform: translateX(100%);
      transition: all var(--transition-normal);
    `;
    
    notification.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          ${type === 'success' ? '<path d="M9 12l2 2 4-4"/><path d="M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9 9 4.03 9 9z"/>' :
            type === 'error' ? '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>' :
            type === 'warning' ? '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>' :
            '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'}
        </svg>
        <span>${this.escapeHtml(message)}</span>
        <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; color: white; cursor: pointer; margin-left: auto; padding: 4px;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    `;

    document.body.appendChild(notification);

    // Animate in
    requestAnimationFrame(() => {
      notification.style.opacity = '1';
      notification.style.transform = 'translateX(0)';
    });

    // Auto remove after 5 seconds
    setTimeout(() => {
      if (notification.parentNode) {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
          if (notification.parentNode) {
            notification.remove();
          }
        }, 200);
      }
    }, 5000);
  },

  // Session monitoring methods
  initSessionMonitoring() {
    // 立即檢查session狀態
    this.checkSessionStatus();
    
    // 每10秒檢查一次session狀態（更頻繁的檢查）
    this.sessionCheckInterval = setInterval(() => {
      this.checkSessionStatus();
    }, 10000);
    
    console.log('Session monitoring initialized');
  },

  async checkSessionStatus() {
    const indicator = document.getElementById('session-status-indicator');
    const icon = document.getElementById('session-status-icon');
    const text = document.getElementById('session-status-text');
    const reconnectBtn = document.getElementById('reconnect-btn');
    
    if (!indicator || !icon || !text) return;
    
    // 設置檢查中狀態
    indicator.className = 'session-status checking';
    icon.textContent = '🔄';
    text.textContent = '檢查連接中...';
    
    try {
      const response = await fetch('/check_session_status');
      const data = await response.json();
      
      if (data.success && data.valid) {
        // Session有效
        indicator.className = 'session-status valid';
        icon.textContent = '✅';
        text.textContent = data.user_info ? 
          `已連接 (${data.user_info.first_name})` : '連接正常';
        reconnectBtn.style.display = 'none';
      } else {
        // Session無效
        indicator.className = 'session-status invalid';
        icon.textContent = '❌';
        text.textContent = data.message || 'Session無效';
        reconnectBtn.style.display = 'inline-flex';
        
        // 根據錯誤類型顯示不同的處理方式
        if (data.error === 'AUTH_KEY_UNREGISTERED') {
          // 授權失效，自動觸發重新連接流程
          text.textContent = 'Telegram授權已失效，正在重新驗證...';
          this.showNotification('Telegram授權已失效，正在跳轉到驗證頁面...', 'warning', 3000);
          
          // 自動觸發重新連接，這將會跳轉到驗證頁面
          setTimeout(() => {
            this.forceReconnect();
          }, 1000);
          
          if (reconnectBtn) {
            reconnectBtn.textContent = '🔐 重新驗證';
          }
        } else {
          // 其他錯誤，顯示原來的邏輯
          this.showNotification(`Telegram連接問題: ${data.message}`, 'warning', 5000);
        }
      }
    } catch (error) {
      // 檢查失敗
      indicator.className = 'session-status invalid';
      icon.textContent = '⚠️';
      text.textContent = '連接檢查失敗';
      reconnectBtn.style.display = 'inline-flex';
      
      console.error('Session check failed:', error);
    }
  },

  async forceReconnect() {
    const reconnectBtn = document.getElementById('reconnect-btn');
    const indicator = document.getElementById('session-status-indicator');
    const icon = document.getElementById('session-status-icon');
    const text = document.getElementById('session-status-text');
    
    if (!reconnectBtn) return;
    
    // 禁用按鈕並顯示載入狀態
    reconnectBtn.disabled = true;
    reconnectBtn.innerHTML = '🔄 重連中...';
    
    if (indicator && icon && text) {
      indicator.className = 'session-status checking';
      icon.textContent = '🔄';
      text.textContent = '正在重新連接...';
    }
    
    try {
      const response = await fetch('/force_reconnect', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      const data = await response.json();
      
      if (data.success) {
        if (data.needs_auth) {
          // 需要重新驗證，跳轉到驗證頁面
          this.showNotification(data.message, 'info');
          setTimeout(() => {
            window.location.href = data.redirect_url;
          }, 1500);
        } else {
          // 正常重連
          this.showNotification(data.message, 'success');
          // 重新檢查session狀態
          setTimeout(() => {
            this.checkSessionStatus();
          }, 2000);
        }
      } else {
        this.showNotification(`重連失敗: ${data.message}`, 'error');
        
        // 如果需要重啟應用程序
        if (data.message.includes('重新啟動')) {
          this.showNotification('請重新啟動應用程序以修復連接問題', 'warning', 10000);
        }
      }
    } catch (error) {
      this.showNotification('重連請求失敗', 'error');
      console.error('Reconnect failed:', error);
    } finally {
      // 恢復按鈕狀態
      reconnectBtn.disabled = false;
      reconnectBtn.innerHTML = '🔄 重新連接';
    }
  }
};

// Global functions for backwards compatibility
window.startAllDownloads = () => ModernTelegramDownloader.startSelectedDownloads();
window.startSelectedDownloads = () => ModernTelegramDownloader.startSelectedDownloads();
window.selectAllTasks = () => ModernTelegramDownloader.selectAllTasks();
window.selectPendingTasks = () => ModernTelegramDownloader.selectPendingTasks();
window.deselectAllTasks = () => ModernTelegramDownloader.deselectAllTasks();
window.cleanDownloadedItems = () => ModernTelegramDownloader.cleanDownloadedItems();
window.removeSelectedTasks = () => ModernTelegramDownloader.removeSelectedTasks();
window.clearFilters = () => ModernTelegramDownloader.clearFilters();
window.selectAllGroups = () => {
  const checkboxes = document.querySelectorAll('.group-checkbox');
  checkboxes.forEach(checkbox => {
    checkbox.checked = true;
    ModernTelegramDownloader.state.selectedGroups.add(checkbox.value);
  });
};
window.deleteSelectedGroups = async () => {
  const selected = Array.from(ModernTelegramDownloader.state.selectedGroups);
  if (selected.length === 0) {
    ModernTelegramDownloader.showNotification('請先選擇要刪除的群組', 'warning');
    return;
  }
  
  if (!confirm(`確定要刪除選中的 ${selected.length} 個群組嗎？`)) return;

  try {
    const response = await fetch('/delete_multiple_groups', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ chat_ids: selected })
    });

    const data = await response.json();
    
    if (data.success) {
      ModernTelegramDownloader.showNotification(data.message, 'success');
      ModernTelegramDownloader.state.selectedGroups.clear();
      ModernTelegramDownloader.loadGroups();
    } else {
      ModernTelegramDownloader.showNotification('批量刪除失敗: ' + (data.error || '未知錯誤'), 'error');
    }
  } catch (error) {
    console.error('Failed to delete groups:', error);
    ModernTelegramDownloader.showNotification('批量刪除時發生錯誤', 'error');
  }
};
window.clearSelectedGroups = async () => {
  const selected = Array.from(ModernTelegramDownloader.state.selectedGroups);
  if (selected.length === 0) {
    ModernTelegramDownloader.showNotification('請先選擇要清空的群組', 'warning');
    return;
  }
  
  if (!confirm(`確定要清空選中的 ${selected.length} 個群組的下載任務嗎？`)) return;

  try {
    const response = await fetch('/clear_multiple_groups', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ chat_ids: selected })
    });

    const data = await response.json();
    
    if (data.success) {
      ModernTelegramDownloader.showNotification(data.message, 'success');
      ModernTelegramDownloader.state.selectedGroups.clear();
      ModernTelegramDownloader.loadGroups();
      ModernTelegramDownloader.loadDownloadHistory();
    } else {
      ModernTelegramDownloader.showNotification('批量清空失敗: ' + (data.error || '未知錯誤'), 'error');
    }
  } catch (error) {
    console.error('Failed to clear groups:', error);
    ModernTelegramDownloader.showNotification('批量清空時發生錯誤', 'error');
  }
};
window.checkGroupAccess = async () => {
  const chatId = document.getElementById('new-chat-id').value;
  if (!chatId) {
    ModernTelegramDownloader.showNotification('請先輸入 Chat ID', 'warning');
    return;
  }

  try {
    const response = await fetch('/check_group_access', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ chat_id: chatId })
    });

    const data = await response.json();
    
    if (data.success && data.accessible) {
      ModernTelegramDownloader.showNotification(`✅ 群組可訪問\n標題: ${data.info.title}\n類型: ${data.info.type}\n成員數: ${data.info.members_count}`, 'success');
    } else {
      ModernTelegramDownloader.showNotification(`❌ 群組無法訪問: ${data.info?.error || '未知原因'}`, 'error');
    }
  } catch (error) {
    console.error('Failed to check group access:', error);
    ModernTelegramDownloader.showNotification('檢查群組權限時發生錯誤', 'error');
  }
};

// Pause download functionality
window.pauseDownload = async () => {
  try {
    const response = await fetch('/set_download_state?state=pause', {
      method: 'POST'
    });

    const result = await response.text();
    
    if (response.ok) {
      ModernTelegramDownloader.showNotification('已暫停下載', 'success');
      updateDownloadControls('paused');
    } else {
      ModernTelegramDownloader.showNotification('暫停下載失敗', 'error');
    }
  } catch (error) {
    console.error('Failed to pause download:', error);
    ModernTelegramDownloader.showNotification('暫停下載時發生錯誤', 'error');
  }
};

// Cancel download functionality
window.cancelDownload = async () => {
  if (!confirm('確定要取消當前下載嗎？這將停止所有進行中的下載任務。')) {
    return;
  }

  try {
    const response = await fetch('/set_download_state?state=cancel', {
      method: 'POST'
    });

    const result = await response.text();
    
    if (response.ok) {
      ModernTelegramDownloader.showNotification('已取消下載', 'warning');
      updateDownloadControls('cancelled');
      updateFloatingProgressControls('cancelled');
      // Hide floating progress window
      const floatingProgress = document.querySelector('.floating-progress');
      if (floatingProgress) {
        floatingProgress.style.display = 'none';
      }
      ModernTelegramDownloader.loadDownloadHistory();
    } else {
      ModernTelegramDownloader.showNotification('取消下載失敗', 'error');
    }
  } catch (error) {
    console.error('Failed to cancel download:', error);
    ModernTelegramDownloader.showNotification('取消下載時發生錯誤', 'error');
  }
};

// Resume download functionality
window.resumeDownload = async () => {
  try {
    const response = await fetch('/set_download_state?state=continue', {
      method: 'POST'
    });

    const result = await response.text();
    
    if (response.ok) {
      ModernTelegramDownloader.showNotification('已恢復下載', 'success');
      updateDownloadControls('downloading');
    } else {
      ModernTelegramDownloader.showNotification('恢復下載失敗', 'error');
    }
  } catch (error) {
    console.error('Failed to resume download:', error);
    ModernTelegramDownloader.showNotification('恢復下載時發生錯誤', 'error');
  }
};

// Update download control buttons based on state
function updateDownloadControls(state) {
  const pauseBtn = document.getElementById('pause-download-btn');
  const cancelBtn = document.getElementById('cancel-download-btn');
  const resumeBtn = document.getElementById('resume-download-btn');
  const startBtn = document.getElementById('start-download-btn');

  if (pauseBtn && cancelBtn && resumeBtn && startBtn) {
    switch (state) {
      case 'downloading':
        pauseBtn.style.display = 'inline-flex';
        cancelBtn.style.display = 'inline-flex';
        resumeBtn.style.display = 'none';
        startBtn.textContent = '下載中...';
        startBtn.disabled = true;
        break;
      case 'paused':
        pauseBtn.style.display = 'none';
        cancelBtn.style.display = 'inline-flex';
        resumeBtn.style.display = 'inline-flex';
        startBtn.textContent = '已暫停';
        startBtn.disabled = true;
        break;
      case 'cancelled':
      case 'completed':
      default:
        pauseBtn.style.display = 'none';
        cancelBtn.style.display = 'none';
        resumeBtn.style.display = 'none';
        startBtn.textContent = '開始下載';
        startBtn.disabled = false;
        break;
    }
  }
  
  // Also update floating progress controls
  updateFloatingProgressControls(state);
}

// ==================== Floating Progress Modal Functions ====================

// Manual sync function accessible from console
window.forceSyncFloatingProgress = function() {
  console.log('Forcing floating progress sync...');
  syncFloatingProgressFromAPI();
  syncMinimizedProgressData();
};

// Test function to set progress manually for debugging
window.testFloatingProgress = function(completed, total) {
  const testData = {
    success: true,
    completed_count: completed || 5,
    total_count: total || 10,
    total_download_speed: '1.5 MB/s',
    current_files: {
      'test_file.mp4': { percentage: 75, speed: '500 KB/s' }
    }
  };
  console.log('🧪 Testing floating progress with frontend data:', testData);
  updateFloatingProgressWithData(testData);
};

// Force update download progress on backend and test
window.forceUpdateProgress = function(completed = 3, total = 8) {
  console.log('🚀 Forcing backend progress update:', { completed, total });
  
  fetch('/force_update_progress', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      completed_count: completed,
      total_count: total,
      status_text: '強制測試中...'
    })
  }).then(response => response.json())
    .then(data => {
      console.log('✅ Backend progress forced:', data);
      // Immediately sync from API
      setTimeout(() => {
        console.log('🔄 Syncing from API after backend update...');
        syncFloatingProgressFromAPI();
      }, 100);
    })
    .catch(error => {
      console.error('❌ Failed to force backend progress:', error);
    });
};

// Debug function to check floating progress elements
window.debugFloatingElements = function() {
  const elements = {
    modal: document.getElementById('floating-progress-modal'),
    completed: document.getElementById('floating-completed-count'),
    remaining: document.getElementById('floating-remaining-count'),
    speed: document.getElementById('floating-overall-speed'),
    progressBar: document.getElementById('floating-progress-bar'),
    progressText: document.getElementById('floating-progress-text'),
    concurrentCount: document.getElementById('floating-concurrent-count')
  };
  
  console.log('🔍 Floating Progress Elements Check:');
  for (const [name, element] of Object.entries(elements)) {
    if (element) {
      console.log(`✅ ${name}:`, element, `Text: "${element.textContent || 'N/A'}"`);
      if (name === 'progressBar') {
        console.log(`   Style width: ${element.style.width}`);
      }
    } else {
      console.log(`❌ ${name}: NOT FOUND`);
    }
  }
  
  // Check if modal is visible
  const modal = elements.modal;
  if (modal) {
    const isVisible = modal.style.display !== 'none' && 
                     !modal.classList.contains('closing') &&
                     getComputedStyle(modal).display !== 'none';
    console.log(`Modal visible: ${isVisible}`);
  }
  
  return elements;
};

// Show floating progress modal
window.showFloatingProgress = function() {
  const modal = document.getElementById('floating-progress-modal');
  const minimized = document.getElementById('minimized-progress-indicator');
  
  if (modal) {
    modal.style.display = 'block';
    modal.classList.remove('closing');
    
    // Hide minimized indicator
    if (minimized) {
      minimized.style.display = 'none';
    }
    
    // Sync progress data immediately and start periodic updates
    syncFloatingProgressData();
    
    // Set up periodic syncing while floating window is open
    if (window.floatingProgressSyncInterval) {
      clearInterval(window.floatingProgressSyncInterval);
    }
    
    window.floatingProgressSyncInterval = setInterval(() => {
      if (modal.style.display === 'block') {
        syncFloatingProgressData();
        syncMinimizedProgressData();
      } else {
        clearInterval(window.floatingProgressSyncInterval);
      }
    }, 1000);
  }
};

// Close floating progress modal
window.closeProgressModal = function() {
  const modal = document.getElementById('floating-progress-modal');
  
  if (modal) {
    modal.classList.add('closing');
    
    // Clear sync interval
    if (window.floatingProgressSyncInterval) {
      clearInterval(window.floatingProgressSyncInterval);
    }
    
    setTimeout(() => {
      modal.style.display = 'none';
      modal.classList.remove('closing');
    }, 300);
  }
};

// Minimize floating progress modal
window.minimizeProgressModal = function() {
  const modal = document.getElementById('floating-progress-modal');
  const minimized = document.getElementById('minimized-progress-indicator');
  
  if (modal) {
    modal.classList.add('closing');
    setTimeout(() => {
      modal.style.display = 'none';
      modal.classList.remove('closing');
      
      // Show minimized indicator
      if (minimized) {
        minimized.style.display = 'block';
        syncMinimizedProgressData();
      }
    }, 300);
  }
};

// Restore floating progress modal from minimized state
window.restoreProgressModal = function() {
  showFloatingProgress();
};

// Toggle concurrent downloads section in floating modal
window.toggleConcurrentSection = function() {
  const content = document.getElementById('floating-concurrent-content');
  const toggleBtn = document.getElementById('concurrent-toggle-btn');
  const toggleIcon = toggleBtn ? toggleBtn.querySelector('svg polyline') : null;
  
  if (content && toggleIcon) {
    const isCollapsed = content.classList.contains('collapsed');
    
    if (isCollapsed) {
      content.classList.remove('collapsed');
      content.style.maxHeight = content.scrollHeight + 'px';
      toggleIcon.setAttribute('points', '6,9 12,15 18,9'); // Down arrow
    } else {
      content.style.maxHeight = '0px';
      content.classList.add('collapsed');
      toggleIcon.setAttribute('points', '6,15 12,9 18,15'); // Up arrow
    }
  }
};

// Update floating progress controls based on download state
function updateFloatingProgressControls(state) {
  const floatingPauseBtn = document.getElementById('floating-pause-btn');
  const floatingResumeBtn = document.getElementById('floating-resume-btn');
  const floatingCancelBtn = document.getElementById('floating-cancel-btn');
  
  if (floatingPauseBtn && floatingResumeBtn && floatingCancelBtn) {
    switch (state) {
      case 'downloading':
        floatingPauseBtn.style.display = 'flex';
        floatingResumeBtn.style.display = 'none';
        floatingCancelBtn.style.display = 'flex';
        break;
      case 'paused':
        floatingPauseBtn.style.display = 'none';
        floatingResumeBtn.style.display = 'flex';
        floatingCancelBtn.style.display = 'flex';
        break;
      case 'cancelled':
      case 'completed':
        floatingPauseBtn.style.display = 'none';
        floatingResumeBtn.style.display = 'none';
        floatingCancelBtn.style.display = 'none';
        break;
      default:
        floatingPauseBtn.style.display = 'flex';
        floatingResumeBtn.style.display = 'none';
        floatingCancelBtn.style.display = 'flex';
        break;
    }
  }
}

// Direct API-based progress sync for floating modal
async function syncFloatingProgressFromAPI() {
  try {
    // Check download state first
    const stateResponse = await fetch('/get_download_state');
    const stateText = await stateResponse.text();
    
    // Don't show floating progress if download is cancelled or not active
    if (stateText === 'cancelled' || stateText === 'completed' || stateText === 'idle') {
      const floatingProgress = document.querySelector('.floating-progress');
      if (floatingProgress) {
        floatingProgress.style.display = 'none';
      }
      return { success: false, message: 'Download not active' };
    }
    
    const response = await fetch('/get_download_progress');
    const data = await response.json();
    
    if (data.success) {
      console.log('✅ API progress data received:', data);
      updateFloatingProgressWithData(data);
      return { success: true, data: data };
    } else {
      console.log('⚠️ API returned no progress data');
      return { success: false, message: 'No progress data' };
    }
  } catch (error) {
    console.error('❌ Failed to fetch progress from API:', error);
    // Fallback to element-based sync
    syncFloatingProgressFromElements();
    return { success: false, error: error.message };
  }
}

// Update floating progress with API data
function updateFloatingProgressWithData(data) {
  const completed = data.completed_count || 0;
  const total = data.total_count || 0;
  const remaining = Math.max(0, total - completed);
  
  // 計算進度：如果有正在下載的文件，使用文件進度的平均值
  let percentage = 0;
  if (data.current_files && Object.keys(data.current_files).length > 0) {
    // 計算所有文件的平均進度
    let totalFileProgress = 0;
    let fileCount = 0;
    
    Object.values(data.current_files).forEach(file => {
      if (file.total_bytes > 0) {
        const fileProgress = (file.downloaded_bytes / file.total_bytes) * 100;
        totalFileProgress += fileProgress;
        fileCount++;
      }
    });
    
    if (fileCount > 0) {
      // 混合文件進度和任務完成進度
      const avgFileProgress = totalFileProgress / fileCount;
      const taskCompletionProgress = total > 0 ? (completed / total) * 100 : 0;
      
      // 使用加權平均：70% 文件進度 + 30% 任務完成進度
      percentage = Math.round((avgFileProgress * 0.7) + (taskCompletionProgress * 0.3));
    } else {
      percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
    }
  } else {
    // 沒有正在下載的文件時，使用任務完成進度
    percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
  }
  
  const speed = data.total_download_speed || '0.00 B/s';
  const concurrentCount = data.current_files ? Object.keys(data.current_files).length : 0;
  
  console.log('🔄 API Data Received:', data);
  console.log('📊 Calculated Values:', { completed, total, remaining, percentage, speed, concurrentCount });
  
  // Update floating window elements with detailed logging
  const floatingCompleted = document.getElementById('floating-completed-count');
  const floatingRemaining = document.getElementById('floating-remaining-count');
  const floatingSpeed = document.getElementById('floating-overall-speed');
  const floatingProgressBar = document.getElementById('floating-progress-bar');
  const floatingProgressText = document.getElementById('floating-progress-text');
  const floatingConcurrentCount = document.getElementById('floating-concurrent-count');
  
  // Check if elements exist
  console.log('🔍 Element Check:', {
    floatingCompleted: !!floatingCompleted,
    floatingRemaining: !!floatingRemaining,
    floatingSpeed: !!floatingSpeed,
    floatingProgressBar: !!floatingProgressBar,
    floatingProgressText: !!floatingProgressText,
    floatingConcurrentCount: !!floatingConcurrentCount
  });
  
  if (floatingCompleted) {
    const oldValue = floatingCompleted.textContent;
    // 如果有文件進度，顯示基於百分比的虛擬完成數
    const displayCompleted = percentage > 0 && total > 0 ? 
      Math.floor((percentage / 100) * total) : completed;
    floatingCompleted.textContent = displayCompleted.toString();
    console.log('✅ Updated completed:', oldValue, '->', displayCompleted);
  } else {
    console.log('❌ floating-completed-count element not found');
  }
  
  if (floatingRemaining) {
    const oldValue = floatingRemaining.textContent;
    // 計算剩餘：基於百分比進度
    const displayCompleted = percentage > 0 && total > 0 ? 
      Math.floor((percentage / 100) * total) : completed;
    const displayRemaining = Math.max(0, total - displayCompleted);
    floatingRemaining.textContent = displayRemaining.toString();
    console.log('✅ Updated remaining:', oldValue, '->', displayRemaining);
  } else {
    console.log('❌ floating-remaining-count element not found');
  }
  
  if (floatingSpeed) {
    const oldValue = floatingSpeed.textContent;
    floatingSpeed.textContent = speed;
    console.log('✅ Updated speed:', oldValue, '->', speed);
  } else {
    console.log('❌ floating-overall-speed element not found');
  }
  
  if (floatingProgressBar && floatingProgressText) {
    const percentageText = percentage + '%';
    const oldWidth = floatingProgressBar.style.width;
    const oldText = floatingProgressText.textContent;
    
    floatingProgressBar.style.width = percentageText;
    floatingProgressText.textContent = percentageText;
    
    console.log('✅ Updated progress bar:', {
      width: oldWidth + ' -> ' + percentageText,
      text: oldText + ' -> ' + percentageText,
      actualPercentage: percentage,
      completed: completed,
      total: total
    });
    
    // Force a visual update
    floatingProgressBar.style.display = 'none';
    floatingProgressBar.offsetHeight; // Force reflow
    floatingProgressBar.style.display = '';
    
    // Additional visual feedback
    if (percentage > 0) {
      floatingProgressBar.style.backgroundColor = 'var(--primary-blue)';
      floatingProgressBar.setAttribute('data-percentage', percentage);
    }
  } else {
    console.log('❌ Progress bar elements not found:', {
      bar: !!floatingProgressBar,
      text: !!floatingProgressText
    });
  }
  
  if (floatingConcurrentCount) {
    const oldValue = floatingConcurrentCount.textContent;
    floatingConcurrentCount.textContent = concurrentCount.toString();
    console.log('✅ Updated concurrent count:', oldValue, '->', concurrentCount);
    
    // Show/hide concurrent section based on count
    const floatingConcurrentSection = document.getElementById('floating-concurrent-section');
    if (floatingConcurrentSection) {
      floatingConcurrentSection.style.display = concurrentCount > 0 ? 'block' : 'none';
    }
  } else {
    console.log('❌ floating-concurrent-count element not found');
  }
  
  // Update concurrent downloads display
  if (data.current_files && Object.keys(data.current_files).length > 0) {
    ModernTelegramDownloader.updateFloatingConcurrentDownloads(data.current_files);
  }
}

// Fallback: Sync progress data from DOM elements
function syncFloatingProgressFromElements() {
  console.log('Using fallback element-based sync...');
  
  // Get the basic data elements
  const mainCompleted = document.getElementById('overall-completed');
  const mainTotal = document.getElementById('overall-total');
  const mainSpeed = document.getElementById('overall-speed');
  const mainConcurrentCount = document.getElementById('concurrent-count');
  
  // Calculate values
  const completed = parseInt(mainCompleted ? mainCompleted.textContent : '0') || 0;
  const total = parseInt(mainTotal ? mainTotal.textContent : '0') || 0;
  const remaining = Math.max(0, total - completed);
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
  const speed = mainSpeed ? mainSpeed.textContent : '0.00 B/s';
  const concurrentCount = parseInt(mainConcurrentCount ? mainConcurrentCount.textContent : '0') || 0;
  
  console.log('Element-based progress data:', { completed, total, remaining, percentage, speed, concurrentCount });
  
  // Update floating window elements
  const floatingCompleted = document.getElementById('floating-completed-count');
  const floatingRemaining = document.getElementById('floating-remaining-count');
  const floatingSpeed = document.getElementById('floating-overall-speed');
  const floatingProgressBar = document.getElementById('floating-progress-bar');
  const floatingProgressText = document.getElementById('floating-progress-text');
  const floatingConcurrentCount = document.getElementById('floating-concurrent-count');
  
  if (floatingCompleted) {
    floatingCompleted.textContent = completed.toString();
  }
  
  if (floatingRemaining) {
    floatingRemaining.textContent = remaining.toString();
  }
  
  if (floatingSpeed) {
    floatingSpeed.textContent = speed;
  }
  
  if (floatingProgressBar && floatingProgressText) {
    const percentageText = percentage + '%';
    floatingProgressBar.style.width = percentageText;
    floatingProgressText.textContent = percentageText;
    console.log('📊 Updated floating progress bar (fallback) to:', percentageText);
  }
  
  if (floatingConcurrentCount) {
    floatingConcurrentCount.textContent = concurrentCount.toString();
    
    // Show/hide concurrent section based on count
    const floatingConcurrentSection = document.getElementById('floating-concurrent-section');
    if (floatingConcurrentSection) {
      floatingConcurrentSection.style.display = concurrentCount > 0 ? 'block' : 'none';
    }
  }
}

// Main sync function that tries API first, then falls back to elements
function syncFloatingProgressData() {
  syncFloatingProgressFromAPI();
}

// Sync minimized progress data
function syncMinimizedProgressData() {
  const mainCompleted = document.getElementById('overall-completed');
  const mainTotal = document.getElementById('overall-total');
  const minimizedProgressBar = document.getElementById('minimized-progress-bar');
  const minimizedProgressText = document.getElementById('minimized-progress-text');
  
  if (minimizedProgressBar && minimizedProgressText) {
    const completed = parseInt(mainCompleted ? mainCompleted.textContent : '0') || 0;
    const total = parseInt(mainTotal ? mainTotal.textContent : '0') || 0;
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
    const percentageText = percentage + '%';
    
    minimizedProgressBar.style.width = percentageText;
    minimizedProgressText.textContent = percentageText;
    console.log('Updated minimized progress to:', percentageText);
  }
}

// Enhanced start download function to show floating progress
const originalStartSelectedDownloads = ModernTelegramDownloader.startSelectedDownloads;
ModernTelegramDownloader.startSelectedDownloads = function() {
  // Check if there are selected tasks before showing progress modal
  if (this.state.selectedTasks.size === 0) {
    this.showNotification('請先選擇要下載的項目', 'warning');
    return;
  }
  
  const result = originalStartSelectedDownloads.call(this);
  
  // Show floating progress modal when download starts (only if tasks are selected)
  if (result && this.state.selectedTasks.size > 0) {
    setTimeout(() => {
      showFloatingProgress();
    }, 1000);
  }
  
  return result;
};

// Enhanced progress update display to sync floating progress
const originalUpdateProgressDisplay = ModernTelegramDownloader.updateProgressDisplay;
if (originalUpdateProgressDisplay) {
  ModernTelegramDownloader.updateProgressDisplay = function(data) {
    originalUpdateProgressDisplay.call(this, data);
    
    // Sync floating progress after main progress update
    setTimeout(() => {
      syncFloatingProgressData();
      syncMinimizedProgressData();
    }, 100);
  };
}

// Also hook into the main update progress monitoring function
const originalUpdateProgressMethod = ModernTelegramDownloader.updateProgress;
if (originalUpdateProgressMethod) {
  ModernTelegramDownloader.updateProgress = function() {
    const result = originalUpdateProgressMethod.call(this);
    
    // Trigger floating progress sync
    setTimeout(() => {
      syncFloatingProgressData();
      syncMinimizedProgressData();
    }, 200);
    
    return result;
  };
}

// Global functions for HTML onclick handlers
function forceReconnect() {
  ModernTelegramDownloader.forceReconnect();
}