"use strict";

const translations = {
  id: {
    tagline: "Studio dubbing lokal",
    connecting: "Menyambungkan…",
    live: "Live",
    reconnecting: "Menyambung ulang…",
    offline: "Terputus",
    heroEyebrow: "CPU • Offline • Lokal",
    heroTitleLead: "Ubah video menjadi",
    heroTitleAccent: "dubbing Indonesia.",
    heroText:
      "Unggah MP4, lalu pantau setiap tahap secara langsung. Semua proses berjalan di komputer ini tanpa mengirim file ke internet.",
    heroPoint1: "Video panjang hingga beberapa jam",
    heroPoint2: "Pembaruan progres otomatis real-time",
    heroPoint3: "Putar dan unduh hasil langsung",
    dropTitle: "Tarik video ke sini",
    dropHint: "atau pilih file dari komputer",
    chooseFiles: "Pilih file MP4",
    uploadLimit: "MP4 • maks {mb} MB • hingga {hours} jam",
    uploadLimitLoading: "MP4 • memuat batas…",
    statActive: "Sedang diproses",
    statActiveDetail: "termasuk antrean",
    statQueued: "Menunggu",
    statQueuedDetail: "siap diambil worker",
    statDone: "Selesai",
    statDoneDetail: "siap diputar",
    statFailed: "Gagal",
    statFailedDetail: "perlu diperiksa",
    tasksTitle: "Daftar dubbing",
    tasksSubtitle: "{count} task tersimpan • progres otomatis.",
    filterAll: "Semua",
    filterActive: "Aktif",
    filterPaused: "Dijeda",
    filterDone: "Selesai",
    filterFailed: "Gagal",
    searchPlaceholder: "Cari nama file…",
    colFileTask: "File / Task",
    colSizeUpload: "Ukuran & Unggah",
    colStages: "Tahap Pipeline",
    colStatusProgress: "Status & Progres",
    colActions: "Aksi",
    showingTasks: "Menampilkan {from} sampai {to} dari {total} task",
    rowsPerPage: "Baris per halaman:",
    prevPage: "Halaman sebelumnya",
    nextPage: "Halaman berikutnya",
    emptyTitle: "Belum ada video",
    emptyText: "Unggah MP4 pertama untuk memulai dubbing.",
    emptyFilterTitle: "Tidak ada task di filter ini",
    emptyFilterText: "Coba filter lain atau unggah video baru.",
    emptySearchTitle: "Tidak ada hasil",
    emptySearchText: "Tidak ada nama file yang cocok dengan “{query}”.",
    footerLocal: "Diproses lokal di perangkat ini.",
    footerApi: "Buka dokumentasi API",
    playerEyebrow: "Hasil dubbing",
    download: "Unduh",
    downloadVideo: "Unduh video",
    play: "Putar",
    copyId: "Salin ID",
    copied: "ID task disalin.",
    pause: "Jeda",
    pausing: "Menjeda…",
    pauseQueued: "Task dijeda. Checkpoint tersimpan dan bisa dilanjutkan kapan saja.",
    pauseFailed: "Tidak bisa menjeda task.",
    resume: "Lanjutkan",
    resuming: "Melanjutkan…",
    resumeQueued: "Task dilanjutkan dari checkpoint terakhir.",
    resumeFailed: "Tidak bisa melanjutkan task.",
    deleteTask: "Hapus",
    deleting: "Menghapus…",
    deleteSuccess: "Task dan file terkait berhasil dihapus.",
    deleteFailed: "Tidak bisa menghapus task.",
    retry: "Coba lagi",
    retrying: "Mengulang…",
    retryQueued: "Task dimasukkan ulang ke antrean, melanjutkan dari checkpoint.",
    retryFailed: "Tidak bisa mengulang task.",
    close: "Tutup",
    switchToLight: "Ganti ke tema terang",
    switchToDark: "Ganti ke tema gelap",
    statusQueued: "Menunggu",
    statusStarted: "Memulai",
    statusProcessing: "Diproses",
    statusPaused: "Dijeda",
    statusSuccess: "Selesai",
    statusFailure: "Gagal",
    statusRevoked: "Dibatalkan",
    stageExtract: "Ekstrak",
    stageTranscribe: "Transkripsi",
    stageTranslate: "Terjemah",
    stageSynthesize: "Sintesis",
    stageMerge: "Gabung",
    staleBadge: "• tidak ada update",
    staleHint:
      "Worker mungkin berhenti atau sedang memproses bagian yang panjang. Cek make status dan make logs-worker.",
    uploadPending: "Menunggu",
    uploadUploading: "Mengunggah {percent}%",
    uploadQueued: "Masuk antrean",
    uploadFailed: "Gagal diunggah",
    uploadAccepted: "{filename} masuk antrean.",
    uploadTooLarge: "{filename} melebihi batas {mb} MB.",
    uploadInvalidType: "{filename} bukan file MP4.",
    uploadEmpty: "{filename} kosong.",
    uploadNetwork: "Tidak bisa menghubungi API lokal.",
    uploadServerError: "Upload ditolak oleh server.",
    uploadQueueUnavailable: "Antrean Redis tidak tersedia. Jalankan make up.",
    taskFailedGeneric:
      "Dubbing gagal atau dibatalkan. Periksa log worker untuk detailnya.",
    unknownError: "Terjadi kesalahan.",
    rangeWarning: "Video ini melebihi batas durasi {hours} jam.",
    sizeMb: "{value} MB",
    sizeGb: "{value} GB",
    refresh: "Muat ulang",
    refreshQueue: "Muat ulang antrean",
  },
  en: {
    tagline: "Local dubbing studio",
    connecting: "Connecting…",
    live: "Live",
    reconnecting: "Reconnecting…",
    offline: "Offline",
    heroEyebrow: "CPU • Offline • Local",
    heroTitleLead: "Turn videos into",
    heroTitleAccent: "Indonesian dubs.",
    heroText:
      "Upload an MP4 and watch every stage live. Everything runs on this computer and no file leaves your machine.",
    heroPoint1: "Long videos up to several hours",
    heroPoint2: "Real-time automatic progress updates",
    heroPoint3: "Play and download results instantly",
    dropTitle: "Drop a video here",
    dropHint: "or choose a file from your computer",
    chooseFiles: "Choose MP4 files",
    uploadLimit: "MP4 • up to {mb} MB • {hours} hours max",
    uploadLimitLoading: "MP4 • loading limits…",
    statActive: "Processing",
    statActiveDetail: "including the queue",
    statQueued: "Waiting",
    statQueuedDetail: "ready for a worker",
    statDone: "Completed",
    statDoneDetail: "ready to play",
    statFailed: "Failed",
    statFailedDetail: "needs attention",
    tasksTitle: "Dubbing queue",
    tasksSubtitle: "{count} saved tasks • progress updates automatically.",
    filterAll: "All",
    filterActive: "Active",
    filterPaused: "Paused",
    filterDone: "Completed",
    filterFailed: "Failed",
    searchPlaceholder: "Search filenames…",
    colFileTask: "File / Task",
    colSizeUpload: "Size & Upload",
    colStages: "Pipeline Stages",
    colStatusProgress: "Status & Progress",
    colActions: "Actions",
    showingTasks: "Showing {from} to {to} of {total} tasks",
    rowsPerPage: "Rows per page:",
    prevPage: "Previous page",
    nextPage: "Next page",
    emptyTitle: "No videos yet",
    emptyText: "Upload your first MP4 to start dubbing.",
    emptyFilterTitle: "Nothing in this filter",
    emptyFilterText: "Try another filter or upload a new video.",
    emptySearchTitle: "No matches",
    emptySearchText: "No filename matches “{query}”.",
    footerLocal: "Processed locally on this device.",
    footerApi: "Open the API docs",
    playerEyebrow: "Dubbing result",
    download: "Download",
    downloadVideo: "Download video",
    play: "Play",
    copyId: "Copy ID",
    copied: "Task ID copied.",
    pause: "Pause",
    pausing: "Pausing…",
    pauseQueued: "Task paused. Checkpoints are saved so you can resume anytime.",
    pauseFailed: "Could not pause the task.",
    resume: "Resume",
    resuming: "Resuming…",
    resumeQueued: "Task requeued to resume from its saved checkpoint.",
    resumeFailed: "Could not resume the task.",
    deleteTask: "Delete",
    deleting: "Deleting…",
    deleteSuccess: "Task and associated files deleted.",
    deleteFailed: "Could not delete the task.",
    retry: "Retry",
    retrying: "Retrying…",
    retryQueued: "Task requeued and will resume from its checkpoint.",
    retryFailed: "Could not retry the task.",
    close: "Close",
    switchToLight: "Switch to light theme",
    switchToDark: "Switch to dark theme",
    statusQueued: "Waiting",
    statusStarted: "Starting",
    statusProcessing: "Processing",
    statusPaused: "Paused",
    statusSuccess: "Completed",
    statusFailure: "Failed",
    statusRevoked: "Cancelled",
    stageExtract: "Extract",
    stageTranscribe: "Transcribe",
    stageTranslate: "Translate",
    stageSynthesize: "Synthesize",
    stageMerge: "Merge",
    staleBadge: "• no updates",
    staleHint:
      "The worker may have stopped or is processing a long section. Check make status and make logs-worker.",
    uploadPending: "Waiting",
    uploadUploading: "Uploading {percent}%",
    uploadQueued: "Queued",
    uploadFailed: "Upload failed",
    uploadAccepted: "{filename} was queued.",
    uploadTooLarge: "{filename} exceeds the {mb} MB limit.",
    uploadInvalidType: "{filename} is not an MP4 file.",
    uploadEmpty: "{filename} is empty.",
    uploadNetwork: "Could not reach the local API.",
    uploadServerError: "The server rejected the upload.",
    uploadQueueUnavailable: "The Redis queue is unavailable. Run make up.",
    taskFailedGeneric: "Dubbing failed or was cancelled. Check the worker log for details.",
    unknownError: "Something went wrong.",
    rangeWarning: "This video exceeds the {hours} hour duration limit.",
    sizeMb: "{value} MB",
    sizeGb: "{value} GB",
    refresh: "Refresh",
    refreshQueue: "Refresh queue",
  },
};

const STAGES = [
  { key: "stageExtract", max: 10 },
  { key: "stageTranscribe", max: 30 },
  { key: "stageTranslate", max: 60 },
  { key: "stageSynthesize", max: 80 },
  { key: "stageMerge", max: 100 },
];

const STATUS_LABELS = {
  PENDING: "statusQueued",
  STARTED: "statusStarted",
  PROGRESS: "statusProcessing",
  PAUSED: "statusPaused",
  SUCCESS: "statusSuccess",
  FAILURE: "statusFailure",
  REVOKED: "statusRevoked",
};

const FAILED_STATUSES = new Set(["FAILURE", "REVOKED"]);
const ACTIVE_STATUSES = new Set(["PENDING", "STARTED", "PROGRESS"]);
const STALE_AFTER_MS = 120000;
const PAGE_SIZES = new Set([5, 10, 25]);

const state = {
  lang: "id",
  tasks: [],
  config: { max_upload_mb: 4096, max_media_hours: 6 },
  configLoaded: false,
  filter: "all",
  search: "",
  page: 1,
  pageSize: 5,
  connected: false,
  refreshInFlight: false,
  eventSource: null,
  uploads: new Map(),
  uploadOrder: [],
  draining: false,
};

const cardNodes = new Map();

const $ = (selector) => document.querySelector(selector);

const els = {
  langDropdownBtn: $("#lang-dropdown-btn"),
  langDropdownMenu: $("#lang-dropdown-menu"),
  queueRefreshBtn: $("#queue-refresh-btn"),
  themeToggle: $("#theme-toggle"),
  dropzone: $("#upload-form"),
  fileInput: $("#file-input"),
  browseButton: $("#browse-button"),
  uploadLimit: $("#upload-limit"),
  uploadQueue: $("#upload-queue"),
  tableWrap: $("#table-wrap"),
  taskList: $("#task-list"),
  tableFooter: $("#table-footer"),
  paginationInfo: $("#pagination-info"),
  paginationControls: $("#pagination-controls"),
  pageSizeTrigger: $("#page-size-trigger"),
  pageSizeMenu: $("#page-size-menu"),
  pageSizeCurrent: $("#page-size-current"),
  empty: $("#empty-state"),
  emptyTitle: $("#empty-title"),
  emptyText: $("#empty-text"),
  tasksSubtitle: $("#tasks-subtitle"),
  searchInput: $("#search-input"),
  statActive: $("#stat-active"),
  statQueued: $("#stat-queued"),
  statDone: $("#stat-done"),
  statFailed: $("#stat-failed"),
  toasts: $("#toasts"),
  playerDialog: $("#player-dialog"),
  playerTitle: $("#player-title"),
  playerVideo: $("#player-video"),
  playerDownload: $("#player-download"),
  playerClose: $("#player-close"),
};

function storageGet(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* Storage can be unavailable in private modes. */
  }
}

function t(key, variables = {}) {
  const table = translations[state.lang] || translations.en;
  const template = table[key] ?? translations.en[key] ?? key;
  return String(template).replace(/\{(\w+)\}/g, (match, name) =>
    variables[name] === undefined ? match : String(variables[name]),
  );
}

function locale() {
  return state.lang === "id" ? "id-ID" : "en-US";
}

function formatNumber(value, digits = 1) {
  return new Intl.NumberFormat(locale(), { maximumFractionDigits: digits }).format(value);
}

function formatSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 MB";
  }
  if (bytes >= 1024 ** 3) {
    return t("sizeGb", { value: formatNumber(bytes / 1024 ** 3) });
  }
  return t("sizeMb", { value: formatNumber(bytes / 1024 ** 2) });
}

function timeAgo(iso) {
  const timestamp = Date.parse(iso);
  if (!Number.isFinite(timestamp)) {
    return "";
  }
  const seconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  const formatter = new Intl.RelativeTimeFormat(locale(), { numeric: "auto" });
  if (seconds < 60) {
    return formatter.format(-seconds, "second");
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return formatter.format(-minutes, "minute");
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return formatter.format(-hours, "hour");
  }
  return formatter.format(-Math.round(hours / 24), "day");
}

function statusKey(task) {
  return STATUS_LABELS[task.status] || "statusProcessing";
}

function isStale(task) {
  if (!ACTIVE_STATUSES.has(task.status)) {
    return false;
  }
  const updated = Date.parse(task.updated_at);
  return Number.isFinite(updated) && Date.now() - updated > STALE_AFTER_MS;
}

function percentFor(task) {
  if (task.status === "SUCCESS") {
    return 100;
  }
  if (task.status === "PENDING") {
    return 0;
  }
  return Math.max(0, Math.min(100, Number(task.progress) || 0));
}

function pillClass(task) {
  if (task.status === "SUCCESS") {
    return "pill done";
  }
  if (task.status === "PAUSED") {
    return "pill paused";
  }
  if (FAILED_STATUSES.has(task.status)) {
    return "pill failed";
  }
  if (task.status === "PENDING") {
    return "pill queued";
  }
  return "pill";
}

function stageClass(task, index) {
  const percent = percentFor(task);
  const stage = STAGES[index];
  if (task.status === "SUCCESS") {
    return "stage is-done";
  }
  if (task.status === "PENDING") {
    return "stage";
  }
  if (task.status === "PAUSED") {
    if (percent >= stage.max) {
      return "stage is-done";
    }
    const previousDone = index === 0 || percent >= STAGES[index - 1].max;
    return previousDone ? "stage is-paused" : "stage";
  }
  if (FAILED_STATUSES.has(task.status)) {
    if (percent >= stage.max) {
      return "stage is-done";
    }
    const previousDone = index === 0 || percent >= STAGES[index - 1].max;
    return previousDone ? "stage is-failed" : "stage";
  }
  if (percent >= stage.max) {
    return "stage is-done";
  }
  const previousDone = index === 0 || percent >= STAGES[index - 1].max;
  return previousDone ? "stage is-current" : "stage";
}

function icon(name) {
  const paths = {
    video:
      '<path d="M15 10l4.553-2.276A1 1 0 0 1 21 8.618v6.764a1 1 0 0 1-1.447.894L15 14M5 18h8a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2Z"></path>',
    alert: '<path d="M12 8v5"></path><path d="M12 17h.01"></path><circle cx="12" cy="12" r="9"></circle>',
    upload: '<path d="M4 16v1a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-1m-4-8-4-4m0 0L8 8m4-4v12"></path>',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.video}</svg>`;
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  els.themeToggle.setAttribute(
    "aria-label",
    t(theme === "dark" ? "switchToLight" : "switchToDark"),
  );
  storageSet("mydubber:theme:meow", theme);
}

function setLanguage(language) {
  state.lang = language === "en" ? "en" : "id";
  storageSet("mydubber:lang", state.lang);
  document.documentElement.lang = state.lang;
  document.title = "MyDubber — Studio";
  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = t(element.dataset.i18n);
  }
  for (const element of document.querySelectorAll("[data-i18n-placeholder]")) {
    element.placeholder = t(element.dataset.i18nPlaceholder);
  }
  for (const code of document.querySelectorAll("[data-lang-code]")) {
    code.classList.toggle("is-active", code.dataset.langCode === state.lang);
  }
  for (const button of document.querySelectorAll("[data-lang]")) {
    button.classList.toggle("is-active", button.dataset.lang === state.lang);
    button.setAttribute("aria-pressed", String(button.dataset.lang === state.lang));
  }
  els.themeToggle.setAttribute(
    "aria-label",
    t(document.documentElement.dataset.theme === "dark" ? "switchToLight" : "switchToDark"),
  );
  els.playerClose.setAttribute("aria-label", t("close"));
  if (els.playerDownload) {
    els.playerDownload.textContent = t("downloadVideo");
  }
  updateUploadLimit();
  renderStats();
  renderTasks();
  renderUploads();
}

function loadPreferences() {
  const storedPageSize = Number.parseInt(String(storageGet("mydubber:page_size") ?? ""), 10);
  if (PAGE_SIZES.has(storedPageSize)) {
    state.pageSize = storedPageSize;
  }
}

function updateUploadLimit() {
  if (!state.configLoaded) {
    els.uploadLimit.textContent = t("uploadLimitLoading");
    return;
  }
  els.uploadLimit.textContent = t("uploadLimit", {
    mb: formatNumber(state.config.max_upload_mb, 0),
    hours: formatNumber(state.config.max_media_hours, 1),
  });
}

function showToast(message, tone = "info", timeout = 4200) {
  const toast = document.createElement("div");
  toast.className = `toast ${tone}`;
  const body = document.createElement("div");
  const text = document.createElement("p");
  text.textContent = message;
  body.append(text);
  toast.append(body);
  els.toasts.append(toast);
  window.setTimeout(() => toast.remove(), timeout);
}

function uploadsPending() {
  return state.uploadOrder
    .map((id) => state.uploads.get(id))
    .filter((item) => item && item.status === "pending");
}

function renderUploads() {
  const items = state.uploadOrder
    .map((id) => state.uploads.get(id))
    .filter((item) => item && item.status !== "removed");
  els.uploadQueue.hidden = items.length === 0;
  const fragment = document.createDocumentFragment();
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "upload-item";
    row.dataset.uploadId = item.id;
    if (item.status === "error") {
      row.classList.add("is-error");
    } else if (item.status === "done" || item.status === "queued") {
      row.classList.add("is-done");
    }
    const iconWrap = document.createElement("span");
    iconWrap.className = "upload-item-icon";
    iconWrap.innerHTML = icon(item.status === "error" ? "alert" : "upload");
    const body = document.createElement("div");
    body.className = "upload-item-body";
    const top = document.createElement("div");
    top.className = "upload-item-top";
    const name = document.createElement("span");
    name.className = "upload-item-name";
    name.textContent = item.file.name;
    const status = document.createElement("span");
    status.className = "upload-item-status";
    status.textContent = uploadStatusText(item);
    top.append(name, status);
    const bar = document.createElement("div");
    bar.className = "upload-item-bar";
    const fill = document.createElement("span");
    fill.style.width = `${item.progress}%`;
    bar.append(fill);
    body.append(top, bar);
    row.append(iconWrap, body);
    fragment.append(row);
  }
  els.uploadQueue.replaceChildren(fragment);
}

function uploadStatusText(item) {
  if (item.status === "uploading") {
    return t("uploadUploading", { percent: Math.round(item.progress) });
  }
  if (item.status === "queued" || item.status === "done") {
    return item.message || t("uploadQueued");
  }
  if (item.status === "error") {
    return item.message || t("uploadFailed");
  }
  return t("uploadPending");
}

function updateUploadProgress(item) {
  const row = els.uploadQueue.querySelector(`[data-upload-id="${item.id}"]`);
  if (!row) {
    return;
  }
  const fill = row.querySelector(".upload-item-bar span");
  const status = row.querySelector(".upload-item-status");
  if (fill) {
    fill.style.width = `${item.progress}%`;
  }
  if (status) {
    status.textContent = uploadStatusText(item);
  }
}

function removeUpload(id) {
  state.uploads.delete(id);
  state.uploadOrder = state.uploadOrder.filter((entry) => entry !== id);
  renderUploads();
}

function addFiles(fileList) {
  const files = Array.from(fileList || []);
  for (const file of files) {
    const name = file.name || "video.mp4";
    if (!name.toLowerCase().endsWith(".mp4")) {
      showToast(t("uploadInvalidType", { filename: name }), "error");
      continue;
    }
    if (file.size === 0) {
      showToast(t("uploadEmpty", { filename: name }), "error");
      continue;
    }
    if (file.size > state.config.max_upload_mb * 1024 * 1024) {
      showToast(
        t("uploadTooLarge", {
          filename: name,
          mb: formatNumber(state.config.max_upload_mb, 0),
        }),
        "error",
      );
      continue;
    }
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    state.uploads.set(id, {
      id,
      file,
      status: "pending",
      progress: 0,
      message: "",
    });
    state.uploadOrder.push(id);
  }
  renderUploads();
  void drainUploads();
}

async function drainUploads() {
  if (state.draining) {
    return;
  }
  state.draining = true;
  try {
    while (true) {
      const item = uploadsPending()[0];
      if (!item) {
        break;
      }
      await uploadOne(item);
    }
  } finally {
    state.draining = false;
  }
}

function uploadOne(item) {
  item.status = "uploading";
  item.progress = 0;
  renderUploads();
  return new Promise((resolve) => {
    const form = new FormData();
    form.append("file", item.file, item.file.name);
    const request = new XMLHttpRequest();
    request.open("POST", "/api/v1/dubbing/tasks");
    request.responseType = "json";
    request.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) {
        return;
      }
      item.progress = Math.min(98, Math.round((event.loaded / event.total) * 100));
      updateUploadProgress(item);
    });
    request.addEventListener("load", () => {
      if (request.status === 202) {
        item.progress = 100;
        item.status = "done";
        item.message = t("uploadQueued");
        updateUploadProgress(item);
        renderUploads();
        showToast(t("uploadAccepted", { filename: item.file.name }), "success");
        window.setTimeout(() => removeUpload(item.id), 3200);
      } else {
        item.status = "error";
        item.progress = 100;
        item.message = uploadErrorMessage(
          request.status,
          request.response,
          item.file.name,
        );
        renderUploads();
        showToast(item.message, "error", 6500);
        window.setTimeout(() => removeUpload(item.id), 9000);
      }
      resolve();
    });
    request.addEventListener("error", () => {
      item.status = "error";
      item.progress = 100;
      item.message = t("uploadNetwork");
      renderUploads();
      showToast(item.message, "error", 6500);
      window.setTimeout(() => removeUpload(item.id), 9000);
      resolve();
    });
    request.send(form);
  });
}

function uploadErrorMessage(status, payload, filename) {
  const name = filename || "File";
  if (status === 413) {
    return t("uploadTooLarge", {
      filename: name,
      mb: formatNumber(state.config.max_upload_mb, 0),
    });
  }
  if (status === 415) {
    return t("uploadInvalidType", { filename: name });
  }
  if (status === 400) {
    return t("uploadEmpty", { filename: name });
  }
  if (status === 503) {
    return t("uploadQueueUnavailable");
  }
  if (payload && typeof payload.detail === "string") {
    return payload.detail;
  }
  return t("uploadServerError");
}

function taskIsVisible(task) {
  const query = state.search.trim().toLowerCase();
  if (query && !task.filename.toLowerCase().includes(query)) {
    return false;
  }
  if (state.filter === "active") {
    return ACTIVE_STATUSES.has(task.status);
  }
  if (state.filter === "paused") {
    return task.status === "PAUSED";
  }
  if (state.filter === "done") {
    return task.status === "SUCCESS";
  }
  if (state.filter === "failed") {
    return FAILED_STATUSES.has(task.status);
  }
  return true;
}

function renderStats() {
  const counts = { active: 0, queued: 0, done: 0, failed: 0 };
  for (const task of state.tasks) {
    if (task.status === "PENDING") {
      counts.queued += 1;
    }
    if (ACTIVE_STATUSES.has(task.status)) {
      counts.active += 1;
    }
    if (task.status === "SUCCESS") {
      counts.done += 1;
    }
    if (FAILED_STATUSES.has(task.status)) {
      counts.failed += 1;
    }
  }
  els.statActive.textContent = String(counts.active);
  els.statQueued.textContent = String(counts.queued);
  els.statDone.textContent = String(counts.done);
  els.statFailed.textContent = String(counts.failed);
  els.tasksSubtitle.textContent = t("tasksSubtitle", { count: state.tasks.length });
}

function buildTaskCard() {
  const row = document.createElement("tr");
  row.className = "task-row";

  // Column 1: File / Task (filename + pipeline stages)
  const fileCell = document.createElement("td");
  const fileWrap = document.createElement("div");
  fileWrap.className = "task-file-cell";
  const iconWrap = document.createElement("span");
  iconWrap.className = "task-icon";
  iconWrap.innerHTML = icon("video");
  const fileMeta = document.createElement("div");
  fileMeta.className = "task-file-meta";
  const nameRow = document.createElement("div");
  nameRow.className = "task-name-row";
  const name = document.createElement("span");
  name.className = "task-name";
  const stale = document.createElement("span");
  stale.className = "stale-badge";
  stale.hidden = true;
  nameRow.append(name, stale);
  const stages = document.createElement("div");
  stages.className = "stage-row";
  const error = document.createElement("p");
  error.className = "task-error";
  error.hidden = true;
  fileMeta.append(nameRow, stages, error);
  fileWrap.append(iconWrap, fileMeta);
  fileCell.append(fileWrap);

  // Column 2: Size & Upload
  const sizeCell = document.createElement("td");
  sizeCell.className = "whitespace-nowrap";
  const sizeText = document.createElement("div");
  sizeText.className = "task-size";
  const uploadedText = document.createElement("div");
  uploadedText.className = "task-uploaded";
  sizeCell.append(sizeText, uploadedText);

  // Column 3: Status & Progress
  const statusCell = document.createElement("td");
  const statusBox = document.createElement("div");
  statusBox.className = "status-cell";
  const statusTop = document.createElement("div");
  statusTop.className = "status-cell-top";
  const pill = document.createElement("span");
  pill.className = "pill";
  const progressValue = document.createElement("span");
  progressValue.className = "progress-value";
  statusTop.append(pill, progressValue);
  const track = document.createElement("div");
  track.className = "progress-track";
  const fill = document.createElement("span");
  track.append(fill);
  statusBox.append(statusTop, track);
  statusCell.append(statusBox);

  // Column 4: Actions
  const actionsCell = document.createElement("td");
  actionsCell.className = "text-right";
  const actions = document.createElement("div");
  actions.className = "task-actions";
  actionsCell.append(actions);

  row.append(fileCell, sizeCell, statusCell, actionsCell);
  row._parts = {
    name,
    stale,
    stages,
    error,
    sizeText,
    uploadedText,
    pill,
    progressValue,
    fill,
    actions,
  };
  return row;
}

function updateTaskCard(row, task) {
  row._task = task;
  row.dataset.status = task.status;
  const parts = row._parts;

  parts.name.textContent = task.filename;
  parts.name.title = task.filename;

  if (isStale(task)) {
    parts.stale.hidden = false;
    parts.stale.textContent = t("staleBadge");
    parts.stale.title = t("staleHint");
  } else {
    parts.stale.hidden = true;
    parts.stale.textContent = "";
    parts.stale.removeAttribute("title");
  }

  if (task.error && FAILED_STATUSES.has(task.status)) {
    parts.error.hidden = false;
    parts.error.textContent =
      task.error === "Dubbing failed or was cancelled. Check the worker log for details."
        ? t("taskFailedGeneric")
        : task.error;
  } else {
    parts.error.hidden = true;
    parts.error.textContent = "";
  }

  parts.sizeText.textContent = formatSize(task.size_bytes);
  parts.uploadedText.textContent = timeAgo(task.created_at);

  parts.stages.replaceChildren();
  STAGES.forEach((stage, index) => {
    const chip = document.createElement("span");
    chip.className = stageClass(task, index);
    chip.textContent = t(stage.key);
    parts.stages.append(chip);
  });

  const percent = percentFor(task);
  parts.pill.className = pillClass(task);
  parts.pill.textContent = t(statusKey(task));
  parts.progressValue.textContent = `${percent}%`;
  parts.fill.style.width = `${percent}%`;

  renderTaskActions(parts.actions, task);
}

function renderTaskActions(container, task) {
  container.replaceChildren();

  if (ACTIVE_STATUSES.has(task.status)) {
    const pause = document.createElement("button");
    pause.type = "button";
    pause.className = "button subtle-outline xs";
    pause.dataset.action = "pause";
    pause.textContent = t("pause");
    container.append(pause);
    if (isStale(task)) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "button amber-outline xs";
      retry.dataset.action = "retry";
      retry.textContent = t("retry");
      container.append(retry);
    }
  } else if (task.status === "PAUSED") {
    const resume = document.createElement("button");
    resume.type = "button";
    resume.className = "button primary xs";
    resume.dataset.action = "resume";
    resume.textContent = t("resume");
    container.append(resume);
  } else if (task.status === "SUCCESS" && task.download_url) {
    const play = document.createElement("button");
    play.type = "button";
    play.className = "button play-btn xs";
    play.dataset.action = "play";
    play.textContent = t("play");
    const download = document.createElement("a");
    download.className = "button primary xs";
    download.href = task.download_url;
    download.download = task.filename || "";
    download.textContent = t("download");
    container.append(play, download);
  } else if (FAILED_STATUSES.has(task.status)) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "button amber-outline xs";
    retry.dataset.action = "retry";
    retry.textContent = t("retry");
    container.append(retry);
  }

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "button danger-ghost xs";
  remove.dataset.action = "delete";
  remove.textContent = t("deleteTask");
  container.append(remove);
}

function buildPageNumbers(currentPage, totalPages) {
  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  const pages = new Set([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);
  const sorted = Array.from(pages)
    .filter((page) => page >= 1 && page <= totalPages)
    .sort((a, b) => a - b);
  const items = [];
  for (let index = 0; index < sorted.length; index += 1) {
    if (index > 0 && sorted[index] - sorted[index - 1] > 1) {
      items.push("...");
    }
    items.push(sorted[index]);
  }
  return items;
}

function renderPagination(total, totalPages, startIndex, visibleCount) {
  if (!els.tableFooter) {
    return;
  }
  els.tableFooter.hidden = total === 0;
  if (total === 0) {
    return;
  }
  const from = startIndex + 1;
  const to = startIndex + visibleCount;
  if (els.paginationInfo) {
    els.paginationInfo.textContent = t("showingTasks", { from, to, total });
  }
  if (els.pageSizeCurrent) {
    els.pageSizeCurrent.textContent = String(state.pageSize);
  }
  for (const button of document.querySelectorAll("[data-page-size]")) {
    const active = Number(button.dataset.pageSize) === state.pageSize;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  if (!els.paginationControls) {
    return;
  }
  const fragment = document.createDocumentFragment();

  const prev = document.createElement("button");
  prev.type = "button";
  prev.className = "page-btn";
  prev.dataset.page = String(state.page - 1);
  prev.disabled = state.page <= 1;
  prev.title = t("prevPage");
  prev.setAttribute("aria-label", t("prevPage"));
  prev.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 19l-7-7 7-7"></path></svg>';
  fragment.append(prev);

  for (const item of buildPageNumbers(state.page, totalPages)) {
    if (item === "...") {
      const gap = document.createElement("span");
      gap.className = "page-ellipsis";
      gap.textContent = "…";
      fragment.append(gap);
      continue;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "page-btn";
    if (item === state.page) {
      button.classList.add("is-active");
    }
    button.dataset.page = String(item);
    button.textContent = String(item);
    button.setAttribute("aria-current", item === state.page ? "page" : "false");
    fragment.append(button);
  }

  const next = document.createElement("button");
  next.type = "button";
  next.className = "page-btn";
  next.dataset.page = String(state.page + 1);
  next.disabled = state.page >= totalPages;
  next.title = t("nextPage");
  next.setAttribute("aria-label", t("nextPage"));
  next.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"></path></svg>';
  fragment.append(next);

  els.paginationControls.replaceChildren(fragment);
}

function renderTasks() {
  const filtered = state.tasks.filter(taskIsVisible);
  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / state.pageSize));
  if (state.page > totalPages) {
    state.page = totalPages;
  }
  if (state.page < 1) {
    state.page = 1;
  }
  const startIndex = (state.page - 1) * state.pageSize;
  const visible = filtered.slice(startIndex, startIndex + state.pageSize);

  const ids = new Set();
  for (const task of visible) {
    ids.add(task.task_id);
    let row = cardNodes.get(task.task_id);
    if (!row) {
      row = buildTaskCard();
      cardNodes.set(task.task_id, row);
    }
    updateTaskCard(row, task);
    els.taskList.append(row);
  }
  for (const [id, row] of cardNodes) {
    if (!ids.has(id)) {
      row.remove();
      cardNodes.delete(id);
    }
  }
  renderEmpty(total);
  renderPagination(total, totalPages, startIndex, visible.length);
}

function renderEmpty(visibleCount) {
  const hasTasks = state.tasks.length > 0;
  const show = visibleCount === 0;
  els.empty.hidden = !show;
  if (els.tableWrap) {
    els.tableWrap.hidden = show;
  }
  if (!show) {
    return;
  }
  if (state.search.trim()) {
    els.emptyTitle.textContent = t("emptySearchTitle");
    els.emptyText.textContent = t("emptySearchText", { query: state.search.trim() });
  } else if (hasTasks) {
    els.emptyTitle.textContent = t("emptyFilterTitle");
    els.emptyText.textContent = t("emptyFilterText");
  } else {
    els.emptyTitle.textContent = t("emptyTitle");
    els.emptyText.textContent = t("emptyText");
  }
}

function renderAll() {
  renderStats();
  renderTasks();
}

async function refreshTasks() {
  if (state.refreshInFlight) {
    return;
  }
  state.refreshInFlight = true;
  try {
    const response = await fetch("/api/v1/dubbing/tasks?limit=200", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    if (Array.isArray(payload.tasks)) {
      state.tasks = payload.tasks;
      renderAll();
    }
  } catch {
    /* Network error will be retried on next poll or event. */
  } finally {
    state.refreshInFlight = false;
  }
}

function connectEvents() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  const source = new EventSource("/api/v1/dubbing/events");
  state.eventSource = source;
  source.addEventListener("tasks", (event) => {
    if (source !== state.eventSource) {
      return;
    }
    try {
      const payload = JSON.parse(event.data);
      if (Array.isArray(payload.tasks)) {
        state.tasks = payload.tasks;
        renderAll();
      }
    } catch {
      /* Ignore malformed events; the next snapshot will replace them. */
    }
  });
  source.addEventListener("error", () => {
    if (source !== state.eventSource) {
      return;
    }
    if (state.tasks.length === 0) {
      void refreshTasks();
    }
  });
}

async function loadConfig() {
  try {
    const response = await fetch("/api/v1/dubbing/config", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    state.config = {
      max_upload_mb: Number(payload.max_upload_mb) || state.config.max_upload_mb,
      max_media_hours: Number(payload.max_media_hours) || state.config.max_media_hours,
    };
    state.configLoaded = true;
    updateUploadLimit();
  } catch {
    updateUploadLimit();
  }
}

function openPlayer(task) {
  if (!task.download_url) {
    return;
  }
  els.playerTitle.textContent = task.filename;
  els.playerDownload.href = task.download_url;
  els.playerDownload.download = task.filename || "";
  els.playerVideo.src = task.download_url;
  if (typeof els.playerDialog.showModal === "function") {
    els.playerDialog.showModal();
  } else {
    window.open(task.download_url, "_blank", "noopener");
  }
}

function closePlayer() {
  els.playerVideo.pause();
  els.playerVideo.removeAttribute("src");
  els.playerVideo.load();
  if (els.playerDialog.open) {
    els.playerDialog.close();
  }
}

async function copyTaskId(taskId) {
  try {
    await navigator.clipboard.writeText(taskId);
  } catch {
    const area = document.createElement("textarea");
    area.value = taskId;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  showToast(t("copied"), "success", 2200);
}

async function taskControlRequest(url, method, button, pendingKey, successKey, failureKey) {
  const originalLabel = button ? button.textContent : "";
  if (button) {
    button.disabled = true;
    button.textContent = t(pendingKey);
  }
  try {
    const response = await fetch(url, {
      method,
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      const detail = payload && typeof payload.detail === "string" ? payload.detail : t(failureKey);
      showToast(detail, "error", 5500);
      if (button) {
        button.disabled = false;
        button.textContent = originalLabel;
      }
      return false;
    }
    showToast(t(successKey), "success");
    await refreshTasks();
    return true;
  } catch {
    showToast(t("uploadNetwork"), "error", 5500);
    if (button) {
      button.disabled = false;
      button.textContent = originalLabel;
    }
    return false;
  }
}

function retryTask(taskId, button) {
  return taskControlRequest(
    `/api/v1/dubbing/tasks/${encodeURIComponent(taskId)}/retry`,
    "POST",
    button,
    "retrying",
    "retryQueued",
    "retryFailed",
  );
}

function pauseTask(taskId, button) {
  return taskControlRequest(
    `/api/v1/dubbing/tasks/${encodeURIComponent(taskId)}/pause`,
    "POST",
    button,
    "pausing",
    "pauseQueued",
    "pauseFailed",
  );
}

function resumeTask(taskId, button) {
  return taskControlRequest(
    `/api/v1/dubbing/tasks/${encodeURIComponent(taskId)}/resume`,
    "POST",
    button,
    "resuming",
    "resumeQueued",
    "resumeFailed",
  );
}

async function deleteTask(taskId, button) {
  const ok = await taskControlRequest(
    `/api/v1/dubbing/tasks/${encodeURIComponent(taskId)}`,
    "DELETE",
    button,
    "deleting",
    "deleteSuccess",
    "deleteFailed",
  );
  if (ok) {
    state.tasks = state.tasks.filter((item) => item.task_id !== taskId);
    renderAll();
  }
}

function bindEvents() {
  els.browseButton.addEventListener("click", () => els.fileInput.click());
  els.dropzone.addEventListener("click", (event) => {
    if (event.target.closest("button")) {
      return;
    }
    els.fileInput.click();
  });
  els.dropzone.addEventListener("submit", (event) => event.preventDefault());
  els.fileInput.addEventListener("change", () => {
    addFiles(els.fileInput.files);
    els.fileInput.value = "";
  });

  let dragDepth = 0;
  els.dropzone.addEventListener("dragenter", (event) => {
    event.preventDefault();
    dragDepth += 1;
    els.dropzone.classList.add("is-dragging");
  });
  els.dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
  els.dropzone.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) {
      els.dropzone.classList.remove("is-dragging");
    }
  });
  els.dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dragDepth = 0;
    els.dropzone.classList.remove("is-dragging");
    addFiles(event.dataTransfer.files);
  });

  const dropdownPairs = [
    [els.langDropdownBtn, els.langDropdownMenu],
    [els.pageSizeTrigger, els.pageSizeMenu],
  ].filter(([trigger, menu]) => trigger && menu);

  const closeAllDropdowns = (exceptMenu = null) => {
    for (const [trigger, menu] of dropdownPairs) {
      if (menu === exceptMenu) {
        continue;
      }
      menu.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
    }
  };

  for (const [trigger, menu] of dropdownPairs) {
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = menu.hidden;
      closeAllDropdowns(menu);
      menu.hidden = !willOpen;
      trigger.setAttribute("aria-expanded", String(willOpen));
    });
    menu.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  }

  document.addEventListener("click", () => {
    closeAllDropdowns();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAllDropdowns();
    }
  });

  for (const button of document.querySelectorAll("[data-lang]")) {
    button.addEventListener("click", () => {
      setLanguage(button.dataset.lang);
      closeAllDropdowns();
    });
  }
  els.themeToggle.addEventListener("click", () => {
    const current = document.documentElement.dataset.theme;
    applyTheme(current === "dark" ? "light" : "dark");
  });

  for (const button of document.querySelectorAll("[data-filter]")) {
    button.addEventListener("click", () => {
      state.filter = button.dataset.filter;
      state.page = 1;
      for (const other of document.querySelectorAll("[data-filter]")) {
        other.classList.toggle("is-active", other === button);
      }
      renderTasks();
    });
  }
  els.searchInput.addEventListener("input", () => {
    state.search = els.searchInput.value;
    state.page = 1;
    renderTasks();
  });

  for (const button of document.querySelectorAll("[data-page-size]")) {
    button.addEventListener("click", () => {
      const size = Number(button.dataset.pageSize);
      closeAllDropdowns();
      if (!PAGE_SIZES.has(size) || size === state.pageSize) {
        return;
      }
      state.pageSize = size;
      state.page = 1;
      storageSet("mydubber:page_size", String(size));
      renderTasks();
    });
  }

  if (els.paginationControls) {
    els.paginationControls.addEventListener("click", (event) => {
      const button = event.target.closest("[data-page]");
      if (!button || button.disabled) {
        return;
      }
      const nextPage = Number(button.dataset.page);
      if (Number.isFinite(nextPage) && nextPage >= 1 && nextPage !== state.page) {
        state.page = nextPage;
        renderTasks();
      }
    });
  }

  els.taskList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) {
      return;
    }
    const row = button.closest(".task-row");
    const task = row && row._task;
    if (!task) {
      return;
    }
    if (button.dataset.action === "copy") {
      void copyTaskId(task.task_id);
    } else if (button.dataset.action === "play") {
      openPlayer(task);
    } else if (button.dataset.action === "pause") {
      void pauseTask(task.task_id, button);
    } else if (button.dataset.action === "resume") {
      void resumeTask(task.task_id, button);
    } else if (button.dataset.action === "retry") {
      void retryTask(task.task_id, button);
    } else if (button.dataset.action === "delete") {
      void deleteTask(task.task_id, button);
    }
  });

  els.playerClose.addEventListener("click", closePlayer);
  els.playerDialog.addEventListener("click", (event) => {
    if (event.target !== els.playerDialog) {
      return;
    }
    const rect = els.playerDialog.getBoundingClientRect();
    const outside =
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom;
    if (outside) {
      closePlayer();
    }
  });
  els.playerDialog.addEventListener("close", () => {
    els.playerVideo.pause();
    els.playerVideo.removeAttribute("src");
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      void refreshTasks();
    }
  });

  if (els.queueRefreshBtn) {
    els.queueRefreshBtn.addEventListener("click", () => {
      void refreshTasks();
    });
  }
}

function init() {
  loadPreferences();
  const storedTheme = storageGet("mydubber:theme:meow");
  applyTheme(storedTheme === "dark" ? "dark" : "light");

  const storedLang = storageGet("mydubber:lang");
  const browserLang = (navigator.language || "en").toLowerCase();
  setLanguage(
    storedLang === "id" || storedLang === "en"
      ? storedLang
      : browserLang.startsWith("id")
        ? "id"
        : "en",
  );

  bindEvents();
  renderAll();
  void loadConfig();
  connectEvents();
  window.setInterval(refreshTasks, 15000);
  window.setInterval(renderTasks, 30000);
}

init();
