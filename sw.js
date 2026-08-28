/* ============================================================
   アプリとして動かすための部品（Service Worker）
   これがあると「ホーム画面に追加」でアプリのように開けて、
   電波がないところでも使えるようになります。

   大事な決めごと：
     通信できるときは、かならずインターネットから最新を取ってきます。
     （とっておいたものを先に見せると、直したはずの画面が
       いつまでも古いままになってしまうため）
     取ってこられなかったときだけ、とっておいたものを使います。

   このファイルは build.py が書き出しています。直すのは mytools/sw-template.js
   ============================================================ */
const CACHE = "pksl-teams-20260828-132539";

/* 電波がないときのために、とっておくファイル */
const FILES = [
  "./",
  "./index.html",
  "./manifest.json",
  "./favicon-32.png",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png"
];

self.addEventListener("install", e => {
  /* 新しいものができたら、待たずに入れかえる */
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(FILES)).catch(() => {})
  );
});

self.addEventListener("activate", e => {
  /* 古いとっておきを片づける */
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  /* よそのサイトのもの（文字を読む部品など）はそのまま通す */
  if (new URL(req.url).origin !== self.location.origin) return;

  e.respondWith(
    fetch(req)
      .then(res => {
        /* 取れたものは、次に電波がないときのためにとっておく */
        const copy = res.clone();
        caches.open(CACHE).then(c => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() =>
        caches.match(req).then(hit => hit || caches.match("./index.html"))
      )
  );
});
