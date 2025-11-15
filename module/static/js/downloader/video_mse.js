/**
 * Message Downloader - MSE Video Player Module
 * 使用 Media Source Extensions API 實現真正的串流播放
 *
 * 參考 Telegram Web 的實現方式
 */

/**
 * MSE 播放器類
 */
class MSEVideoPlayer {
    constructor(videoElement, videoUrl) {
        this.videoElement = videoElement;
        this.videoUrl = videoUrl;
        this.mediaSource = null;
        this.sourceBuffer = null;
        this.isSourceOpen = false;
        this.isStreamEnded = false;
        this.pendingChunks = [];
        this.isAppending = false;
        this.totalBytesReceived = 0;
        this.reader = null;
        this.abortController = null;

        // 錯誤重試配置
        this.maxRetries = 3;
        this.retryCount = 0;
        this.retryDelay = 1000;
    }

    /**
     * 初始化並開始播放
     */
    async initialize() {
        try {
            console.log('🎬 初始化 MSE 播放器...');

            // 檢查瀏覽器支援
            if (!window.MediaSource) {
                throw new Error('瀏覽器不支持 Media Source Extensions');
            }

            // 創建 MediaSource
            this.mediaSource = new MediaSource();
            this.videoElement.src = URL.createObjectURL(this.mediaSource);

            // 等待 sourceopen 事件
            await new Promise((resolve, reject) => {
                this.mediaSource.addEventListener('sourceopen', () => {
                    console.log('✅ MediaSource 已開啟');
                    this.isSourceOpen = true;
                    resolve();
                }, { once: true });

                this.mediaSource.addEventListener('error', (e) => {
                    console.error('❌ MediaSource 錯誤:', e);
                    reject(new Error('MediaSource 開啟失敗'));
                }, { once: true });

                // 超時保護
                setTimeout(() => reject(new Error('MediaSource 開啟超時')), 10000);
            });

            // 創建 SourceBuffer
            await this.createSourceBuffer();

            // 開始串流下載
            await this.startStreaming();

            return true;

        } catch (error) {
            console.error('❌ MSE 播放器初始化失敗:', error);
            this.cleanup();
            throw error;
        }
    }

    /**
     * 創建 SourceBuffer
     */
    async createSourceBuffer() {
        try {
            // 檢測串流類型：如果 URL 包含 /stream/，使用 MPEG-TS；否則使用 MP4
            const isStreamUrl = this.videoUrl.includes('/stream/');

            let mimeCodec;
            let alternatives = [];

            if (isStreamUrl) {
                // MPEG-TS 格式（用於串流）
                console.log('🎬 檢測到串流模式，使用 MPEG-TS');
                mimeCodec = 'video/mp2t; codecs="avc1.42E01E, mp4a.40.2"';
                alternatives = [
                    'video/mp2t; codecs="avc1.42E01E"',  // MPEG-TS + H.264 Baseline
                    'video/mp2t',                        // 簡化版本
                ];
            } else {
                // MP4 格式（用於快取下載）
                console.log('📦 使用快取模式，使用 MP4');
                mimeCodec = 'video/mp4; codecs="avc1.42E01E, mp4a.40.2"';
                alternatives = [
                    'video/mp4; codecs="avc1.64001E, mp4a.40.2"', // High Profile
                    'video/mp4; codecs="avc1.4D401E, mp4a.40.2"', // Main Profile
                    'video/mp4; codecs="avc1.42E01E"',            // 只有視頻
                    'video/mp4',                                   // 簡化版本
                ];
            }

            // 檢查首選 codec 支援
            if (!MediaSource.isTypeSupported(mimeCodec)) {
                console.warn('⚠️ 不支援首選 codec，嘗試其他選項...', mimeCodec);

                // 嘗試替代方案
                for (const codec of alternatives) {
                    if (MediaSource.isTypeSupported(codec)) {
                        console.log('✅ 使用替代 codec:', codec);
                        mimeCodec = codec;
                        break;
                    }
                }

                // 如果都不支援
                if (!MediaSource.isTypeSupported(mimeCodec)) {
                    throw new Error(`沒有支援的 codec (格式: ${isStreamUrl ? 'MPEG-TS' : 'MP4'})`);
                }
            } else {
                console.log('✅ 使用 codec:', mimeCodec);
            }

            // 創建 SourceBuffer
            this.sourceBuffer = this.mediaSource.addSourceBuffer(mimeCodec);

            // 設置 SourceBuffer 模式
            if (this.sourceBuffer.mode !== 'sequence') {
                try {
                    this.sourceBuffer.mode = 'sequence';
                    console.log('✅ SourceBuffer 模式: sequence');
                } catch (e) {
                    console.warn('⚠️ 無法設置 sequence 模式，使用默認模式');
                }
            }

            // 監聽更新事件
            this.sourceBuffer.addEventListener('updateend', () => {
                this.onUpdateEnd();
            });

            this.sourceBuffer.addEventListener('error', (e) => {
                console.error('❌ SourceBuffer 錯誤:', e);
            });

            console.log('✅ SourceBuffer 創建成功');

        } catch (error) {
            console.error('❌ 創建 SourceBuffer 失敗:', error);
            throw error;
        }
    }

    /**
     * 開始串流下載
     */
    async startStreaming() {
        try {
            console.log('🌊 開始串流下載:', this.videoUrl);

            // 創建 AbortController 用於取消請求
            this.abortController = new AbortController();

            // 發起請求
            const response = await fetch(this.videoUrl, {
                signal: this.abortController.signal,
                headers: {
                    'Accept': 'video/mp4,video/*',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            console.log('✅ 串流連接建立成功');
            console.log('📦 Content-Type:', response.headers.get('Content-Type'));
            console.log('📦 Content-Length:', response.headers.get('Content-Length'));

            // 獲取 ReadableStream reader
            this.reader = response.body.getReader();

            // 開始讀取數據
            await this.readStream();

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('⏹️ 串流已取消');
            } else {
                console.error('❌ 串流下載失敗:', error);
                throw error;
            }
        }
    }

    /**
     * 讀取串流數據
     */
    async readStream() {
        try {
            let chunkCount = 0;

            while (true) {
                const { done, value } = await this.reader.read();

                if (done) {
                    console.log('✅ 串流讀取完成');
                    this.isStreamEnded = true;
                    this.finishStream();
                    break;
                }

                chunkCount++;
                this.totalBytesReceived += value.byteLength;

                // 記錄前 5 塊
                if (chunkCount <= 5) {
                    console.log(`📦 收到第 ${chunkCount} 塊: ${value.byteLength} bytes`);
                }

                // 每 10 塊記錄一次
                if (chunkCount % 10 === 0) {
                    const mb = (this.totalBytesReceived / 1024 / 1024).toFixed(1);
                    console.log(`📊 已接收 ${chunkCount} 塊 (~${mb} MB)`);
                }

                // 添加數據到 SourceBuffer
                await this.appendChunk(value);
            }

        } catch (error) {
            console.error('❌ 讀取串流失敗:', error);
            throw error;
        }
    }

    /**
     * 添加數據塊到 SourceBuffer
     */
    async appendChunk(chunk) {
        // 將 chunk 添加到待處理隊列
        this.pendingChunks.push(chunk);

        // 如果沒有正在添加，開始處理隊列
        if (!this.isAppending) {
            this.processChunks();
        }
    }

    /**
     * 處理待處理的數據塊隊列
     */
    processChunks() {
        if (this.pendingChunks.length === 0 || this.isAppending) {
            return;
        }

        if (!this.sourceBuffer || this.sourceBuffer.updating) {
            return;
        }

        try {
            const chunk = this.pendingChunks.shift();
            this.isAppending = true;

            // 添加到 SourceBuffer
            this.sourceBuffer.appendBuffer(chunk);

        } catch (error) {
            console.error('❌ appendBuffer 失敗:', error);
            this.isAppending = false;

            // 重試
            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                console.log(`🔄 重試 ${this.retryCount}/${this.maxRetries}...`);
                setTimeout(() => this.processChunks(), this.retryDelay);
            }
        }
    }

    /**
     * SourceBuffer updateend 事件處理
     */
    onUpdateEnd() {
        this.isAppending = false;
        this.retryCount = 0;

        // 繼續處理隊列
        if (this.pendingChunks.length > 0) {
            this.processChunks();
        } else if (this.isStreamEnded) {
            this.finishStream();
        }
    }

    /**
     * 完成串流
     */
    finishStream() {
        if (!this.mediaSource || this.mediaSource.readyState !== 'open') {
            return;
        }

        // 確保所有數據都已添加
        if (this.pendingChunks.length === 0 && !this.sourceBuffer.updating) {
            try {
                this.mediaSource.endOfStream();
                console.log('✅ 串流已結束');

                const mb = (this.totalBytesReceived / 1024 / 1024).toFixed(2);
                console.log(`📊 總共接收: ${mb} MB`);

            } catch (error) {
                console.error('❌ endOfStream 失敗:', error);
            }
        }
    }

    /**
     * 清理資源
     */
    cleanup() {
        console.log('🧹 清理 MSE 播放器資源...');

        // 取消 fetch 請求
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }

        // 取消 reader
        if (this.reader) {
            try {
                this.reader.cancel();
            } catch (e) {
                // ignore
            }
            this.reader = null;
        }

        // 清理 MediaSource
        if (this.mediaSource && this.mediaSource.readyState === 'open') {
            try {
                this.mediaSource.endOfStream();
            } catch (e) {
                // ignore
            }
        }

        // 釋放 object URL
        if (this.videoElement && this.videoElement.src) {
            try {
                URL.revokeObjectURL(this.videoElement.src);
                this.videoElement.src = '';
            } catch (e) {
                // ignore
            }
        }

        // 清空隊列
        this.pendingChunks = [];
        this.isAppending = false;
        this.isSourceOpen = false;
        this.isStreamEnded = false;
        this.totalBytesReceived = 0;

        console.log('✅ MSE 播放器資源已清理');
    }

    /**
     * 暫停播放
     */
    pause() {
        if (this.videoElement) {
            this.videoElement.pause();
        }
    }

    /**
     * 開始播放
     */
    async play() {
        if (this.videoElement) {
            try {
                await this.videoElement.play();
                console.log('▶️ 開始播放');
            } catch (error) {
                console.error('❌ 播放失敗:', error);
                throw error;
            }
        }
    }
}

/**
 * 創建 MSE 播放器實例
 */
function createMSEPlayer(videoElement, videoUrl) {
    return new MSEVideoPlayer(videoElement, videoUrl);
}

/**
 * 檢查瀏覽器是否支援 MSE
 */
function isMSESupported() {
    if (!window.MediaSource) {
        return false;
    }

    // 測試常見的 codec 支援
    const testCodecs = [
        'video/mp4; codecs="avc1.42E01E, mp4a.40.2"', // H.264 Baseline + AAC
        'video/mp4; codecs="avc1.64001E, mp4a.40.2"', // H.264 High + AAC
        'video/mp4; codecs="avc1.4D401E, mp4a.40.2"', // H.264 Main + AAC
        'video/mp4; codecs="avc1.42E01E"', // 只有視頻
        'video/mp4', // 簡化版本
    ];

    // 只要有一個 codec 被支援就可以
    for (const codec of testCodecs) {
        if (MediaSource.isTypeSupported(codec)) {
            console.log('✅ MSE 支援檢測通過，支援 codec:', codec);
            return true;
        }
    }

    console.warn('⚠️ MSE API 存在但不支援任何測試 codec');
    return false;
}
